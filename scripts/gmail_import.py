#!/usr/bin/env python3
"""
gmail_import.py — Importa registros financieros extraídos de Gmail a app.db

Uso:
    python3 scripts/gmail_import.py <ruta_al_json_de_registros>

El agente Claude lee los emails via MCP de Gmail, arma un JSON con los registros
y llama a este script. Toda la lógica de DB, categorías y deduplicación vive aquí.

Formato del JSON de entrada (lista de objetos):
[
  {
    "msg_id": "19d7e588eab26583",
    "purchase_date": "2026-04-11",
    "description": "CP*FACTURAS CLARO",
    "currency": "ARS",
    "amount_original": 31416.08,
    "installments_total": 1,
    "payment_method": "CARD",       # CARD | TRANSFER | CASH
    "card_id": 1,                   # null para transferencias
    "owner_person_id": 1,
    "category_concept": "servicios", # ver CATEGORY_KEYWORDS abajo
    "is_refund": 0,
    "debt_settled": 0,
    "is_common": 0
  },
  ...
]
"""

import sys
import os
import json
import glob
import shutil
import tempfile
from datetime import datetime


# ---------------------------------------------------------------------------
# Configuración de paths
# ---------------------------------------------------------------------------

def detect_db_path():
    mounts = glob.glob('/sessions/*/mnt/admin-consumos/data/app.db')
    if mounts:
        return mounts[0]
    # Fallback: path real en el equipo del usuario
    return '/Users/pablo/github/admin-consumos/data/app.db'


# ---------------------------------------------------------------------------
# Mapeo de conceptos a categorías de la DB (case-insensitive)
# Las claves son los valores que el agente debe usar en "category_concept".
# Los valores son búsquedas lowercase contra los nombres reales de la DB.
# Si la DB cambia el nombre de una categoría, solo hay que ajustar el valor
# de la derecha (o el nombre en la DB ya matchea por substring igualmente).
# ---------------------------------------------------------------------------

CATEGORY_CONCEPTS = {
    'servicios':       'servicios',
    'seguros':         'seguros',
    'impuestos':       'impuestos',
    'combustible':     'combustible',
    'supermercado':    'supermercado',
    'restaurantes':    'restaurantes',
    'entretenimiento': 'entretenimiento',
    'varios':          'varios',
    'autos':           'autos',
    'salud':           'salud',
    'educacion':       'educación',
    'hogar':           'hogar',
    'mascotas':        'mascotas',
    'ninos':           'niños',
    'peaje':           'peaje',
    'transporte':      'transporte',
    'regalos':         'regalos',
}


def load_db_categories(cur):
    """Retorna dict {nombre_lower: nombre_exacto} con todas las categorías de la DB."""
    cur.execute('SELECT name FROM category')
    return {row[0].lower(): row[0] for row in cur.fetchall()}


def resolve_category(concept, db_categories):
    """
    Convierte un concepto fijo (ej: 'servicios') al nombre exacto en la DB.
    - Busca por exact match lowercase primero.
    - Fallback: busca por substring.
    - Si no encuentra nada, retorna None y loguea un warning.
    """
    key = CATEGORY_CONCEPTS.get(concept, concept).lower()

    # Match exacto
    if key in db_categories:
        return db_categories[key]

    # Match por substring
    for db_key, db_name in db_categories.items():
        if key in db_key or db_key in key:
            print(f'  ⚠  categoría "{concept}" no encontrada exacta → usando "{db_name}" por similitud')
            return db_name

    print(f'  ⚠  categoría "{concept}" no existe en la DB → se guardará sin categoría')
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def add_months(ym, n):
    y, m = map(int, ym.split('-'))
    m += n
    while m > 12:
        m -= 12
        y += 1
    return f'{y:04d}-{m:02d}'


def is_duplicate(cur, date, desc, amount):
    cur.execute(
        'SELECT id FROM purchase WHERE purchase_date=? AND description=? AND ABS(amount_original-?)<=0.02',
        (date, desc, amount)
    )
    return cur.fetchone() is not None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print('Uso: python3 gmail_import.py <ruta_al_json>')
        sys.exit(1)

    json_path = sys.argv[1]
    with open(json_path, encoding='utf-8') as f:
        records = json.load(f)

    if not records:
        print('Sin registros en el JSON. Nada para importar.')
        sys.exit(0)

    DB_PATH = detect_db_path()
    ID_FILE = os.path.join(os.path.dirname(DB_PATH), 'gmail_processed_ids.json')
    WORK_DB = os.path.join(tempfile.gettempdir(), 'admin_consumos_work.db')

    print(f'DB: {DB_PATH}')
    print(f'IDs procesados: {ID_FILE}')
    print(f'Registros a evaluar: {len(records)}')
    print()

    # Cargar IDs ya procesados
    if os.path.exists(ID_FILE):
        with open(ID_FILE, encoding='utf-8') as f:
            processed_ids = set(json.load(f))
    else:
        processed_ids = set()

    # Copiar DB a directorio temporal (evita problemas de escritura en mount FUSE)
    shutil.copy2(DB_PATH, WORK_DB)

    import sqlite3
    conn = sqlite3.connect(WORK_DB, timeout=10)
    conn.execute('PRAGMA foreign_keys=ON')
    cur = conn.cursor()

    # Cargar categorías reales desde la DB
    db_categories = load_db_categories(cur)
    print(f'Categorías en DB: {sorted(db_categories.values())}')
    print()

    # Crear import batch
    now = datetime.now().isoformat()
    label = f'Gmail - tarea programada {now[:16]}'
    cur.execute(
        '''INSERT INTO importbatch (imported_at, provider, source_file, card_id,
           statement_year_month, purchases_created, purchases_skipped, purchases_parsed)
           VALUES (?, ?, ?, 1, ?, 0, 0, 0)''',
        (now, 'gmail', label, '2099-01')
    )
    batch_id = cur.lastrowid

    created = 0
    skipped_dup_id = 0
    skipped_dup_db = 0
    inserted_records = []
    all_reviewed_ids = set()

    for rec in records:
        msg_id = rec.get('msg_id', '')
        all_reviewed_ids.add(msg_id)

        # Skip si ya fue procesado
        if msg_id in processed_ids:
            print(f'  SKIP (ID ya procesado): {rec.get("description")}')
            skipped_dup_id += 1
            continue

        date = rec['purchase_date']
        desc = rec['description']
        amount = float(rec['amount_original'])
        installments = int(rec.get('installments_total', 1))
        installment_amount = round(amount / installments, 2)
        first_month = rec['first_installment_month']
        payment_method = rec.get('payment_method', 'CARD')
        card_id = rec.get('card_id')  # puede ser None
        owner_person_id = int(rec.get('owner_person_id', 1))
        currency = rec.get('currency', 'ARS')
        is_refund = int(rec.get('is_refund', 0))
        debt_settled = int(rec.get('debt_settled', 0))
        is_common = int(rec.get('is_common', 0))

        # Resolver categoría dinámicamente
        category_concept = rec.get('category_concept', 'varios')
        category = resolve_category(category_concept, db_categories)

        # Deduplicación por DB
        if is_duplicate(cur, date, desc, amount):
            print(f'  SKIP (duplicado DB): {date} | {desc} | ${amount}')
            skipped_dup_db += 1
            continue

        # Insertar purchase
        cur.execute(
            '''INSERT INTO purchase
               (card_id, payment_method, purchase_date, description, currency,
                amount_original, installments_total, installment_amount_original,
                first_installment_month, owner_person_id, category,
                is_refund, debt_settled, is_common, import_batch_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (card_id, payment_method, date, desc, currency,
             amount, installments, installment_amount,
             first_month, owner_person_id, category,
             is_refund, debt_settled, is_common, batch_id)
        )
        purchase_id = cur.lastrowid

        # Insertar cuotas
        for i in range(installments):
            ym = add_months(first_month, i)
            cur.execute(
                '''INSERT INTO installmentschedule
                   (purchase_id, year_month, installment_index, currency, amount_original)
                   VALUES (?, ?, ?, ?, ?)''',
                (purchase_id, ym, i + 1, currency, installment_amount)
            )

        # Insertar payer
        cur.execute(
            "INSERT INTO purchasepayer (purchase_id, person_id, share_type, share_value) VALUES (?, ?, 'PERCENT', 100.0)",
            (purchase_id, owner_person_id)
        )

        created += 1
        inserted_records.append(rec)
        print(f'  ✓ INSERTADO: {date} | {desc} | ${amount:,.2f} | {category or "sin categoría"}')

    # Actualizar batch
    total = created + skipped_dup_db
    cur.execute(
        'UPDATE importbatch SET purchases_created=?, purchases_skipped=?, purchases_parsed=? WHERE id=?',
        (created, skipped_dup_db, total, batch_id)
    )

    conn.commit()
    conn.close()

    # Copiar DB de vuelta al mount
    shutil.copy2(WORK_DB, DB_PATH)

    # Limpiar journal si existe
    journal = DB_PATH + '-journal'
    if os.path.exists(journal):
        with open(journal, 'wb') as f:
            f.truncate(0)

    # Guardar IDs procesados
    processed_ids.update(all_reviewed_ids)
    with open(ID_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(processed_ids), f, indent=2)

    # Reporte final
    print()
    print('=' * 50)
    print(f'Nuevos registros insertados : {created}')
    print(f'Saltados (ID ya procesado)  : {skipped_dup_id}')
    print(f'Saltados (duplicado en DB)  : {skipped_dup_db}')
    print(f'IDs guardados en archivo    : {len(processed_ids)}')
    if created == 0:
        print('Sin nuevos gastos para importar en esta corrida.')
    print('=' * 50)


if __name__ == '__main__':
    main()

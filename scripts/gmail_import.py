#!/usr/bin/env python3
"""
gmail_import.py — Importa registros financieros extraídos de Gmail a app.db

Uso:
    python3 scripts/gmail_import.py <ruta_al_json>

El agente Claude lee los emails via MCP de Gmail, arma un JSON y llama a este
script. Toda la lógica de DB, categorías y deduplicación vive aquí.

Formato del JSON de entrada:
{
  "records": [
    {
      "msg_id": "19d7e588eab26583",
      "purchase_date": "2026-04-11",
      "description": "CP*FACTURAS CLARO",
      "currency": "ARS",
      "amount_original": 31416.08,
      "installments_total": 1,
      "first_installment_month": "2026-05",
      "payment_method": "CARD",       # CARD | TRANSFER | CASH
      "card_id": 1,                   # null para transferencias
      "owner_person_id": 1,
      "category_concept": "servicios",
      "is_refund": 0,
      "debt_settled": 0,
      "is_common": 0
    }
  ],
  "ignored_ids": ["19dabc123", "19ddef456"]
}
"""

import re
import sys
import os
import json
import glob
import shutil
import sqlite3
import tempfile
from datetime import datetime


# ---------------------------------------------------------------------------
# Configuración de paths
# ---------------------------------------------------------------------------

def detect_db_path():
    mounts = glob.glob('/sessions/*/mnt/admin-consumos/data/app.db')
    if mounts:
        return mounts[0]
    return '/Users/pablo/github/admin-consumos/data/app.db'


# ---------------------------------------------------------------------------
# Mapeo de conceptos a categorías de la DB (case-insensitive)
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

    if key in db_categories:
        return db_categories[key]

    for db_key, db_name in db_categories.items():
        if key in db_key or db_key in key:
            print(f'  ⚠  categoría "{concept}" no encontrada exacta → usando "{db_name}" por similitud')
            return db_name

    print(f'  ⚠  categoría "{concept}" no existe en la DB → se guardará sin categoría')
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Description normalization (inlined from backend/app/importers/visa_xlsx.py)
# ---------------------------------------------------------------------------

_purchase_desc_cleanup_re = re.compile(
    r"\b(?:C\.)\s*\d+\s*/\s*\d+\b|\b\d+\s*de\s*\d+\b",
    re.IGNORECASE,
)
_purchase_desc_leading_code_re = re.compile(r"^\s*\d{3,}\s+")
_purchase_desc_trailing_code_re = re.compile(r"\s+\d{3,}\s*$")


def normalize_purchase_description(*, description: str) -> str:
    cleaned = _purchase_desc_cleanup_re.sub(" ", description)
    cleaned = _purchase_desc_leading_code_re.sub("", cleaned)
    cleaned = _purchase_desc_trailing_code_re.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def add_months(ym, n):
    y, m = map(int, ym.split('-'))
    m += n
    while m > 12:
        m -= 12
        y += 1
    return f'{y:04d}-{m:02d}'


def is_duplicate(cur, date, desc, amount):
    norm_desc = normalize_purchase_description(description=desc)
    cur.execute(
        'SELECT id, description FROM purchase WHERE purchase_date=? AND ABS(amount_original-?)<=0.02',
        (date, amount)
    )
    for row_id, row_desc in cur.fetchall():
        if normalize_purchase_description(description=row_desc) == norm_desc:
            return True
    return False


def _payer_for_record(rec: dict) -> int:
    """Returns person_id of who pays (card owner, not consumer)."""
    card_id = rec.get("card_id")
    if card_id == 1:
        return 1
    if card_id in (2, 3):
        return 2
    return int(rec.get("owner_person_id", 1))


def _build_api_payload(rec: dict) -> dict:
    """Build PurchaseCreate-compatible payload from a gmail record."""
    amount = float(rec["amount_original"])
    installments = int(rec.get("installments_total", 1))
    payer_person_id = _payer_for_record(rec)
    return {
        "card_id": rec.get("card_id"),
        "payment_method": rec.get("payment_method", "CARD"),
        "purchase_date": rec["purchase_date"],
        "description": normalize_purchase_description(description=rec["description"]),
        "currency": rec.get("currency", "ARS"),
        "amount_original": amount,
        "installments_total": installments,
        "first_installment_month": rec.get("first_installment_month"),
        "owner_person_id": int(rec.get("owner_person_id", 1)),
        "category": rec.get("category_concept"),
        "is_refund": bool(rec.get("is_refund", 0)),
        "is_common": bool(rec.get("is_common", 0)),
        "payers": [{"person_id": payer_person_id, "share_type": "PERCENT", "share_value": 100.0}],
    }


def insert_via_api(rec: dict, railway_url: str, auth: tuple) -> bool:
    """POST purchase to Railway API. Returns True if created, False if duplicate (409)."""
    import requests as req_lib
    payload = _build_api_payload(rec)
    resp = req_lib.post(f"{railway_url}/api/purchases", json=payload, auth=auth, timeout=15)
    if resp.status_code == 200:
        return True
    if resp.status_code == 409:
        return False
    resp.raise_for_status()
    return False


def _load_railway_categories(railway_url: str, auth: tuple) -> dict:
    """Fetches categories from Railway API. Returns {name_lower: name_exact}."""
    import requests as req_lib
    try:
        resp = req_lib.get(f"{railway_url}/api/categories", auth=auth, timeout=10)
        resp.raise_for_status()
        return {cat["name"].lower(): cat["name"] for cat in resp.json()}
    except Exception as e:
        print(f'  ⚠  No se pudieron cargar categorías desde Railway: {e}')
        return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print('Uso: python3 gmail_import.py <ruta_al_json>')
        sys.exit(1)

    json_path = sys.argv[1]
    with open(json_path, encoding='utf-8') as f:
        payload = json.load(f)

    if isinstance(payload, list):
        records = payload
        ignored_ids = []
    else:
        records = payload.get('records', [])
        ignored_ids = payload.get('ignored_ids', [])

    if not records and not ignored_ids:
        print('Sin registros ni IDs ignorados. Nada para procesar.')
        sys.exit(0)

    railway_url = os.environ.get('RAILWAY_URL', '').rstrip('/')
    if railway_url:
        _run_railway_mode(records, ignored_ids, railway_url)
    else:
        _run_local_mode(records, ignored_ids)


def _run_local_mode(records: list, ignored_ids: list) -> None:
    DB_PATH = detect_db_path()
    ID_FILE = os.path.join(os.path.dirname(DB_PATH), 'gmail_processed_ids.json')
    WORK_DB = os.path.join(tempfile.gettempdir(), 'admin_consumos_work.db')

    print(f'DB: {DB_PATH}')
    print(f'IDs procesados: {ID_FILE}')
    print(f'Registros a evaluar: {len(records)}')
    print(f'IDs ignorados a registrar: {len(ignored_ids)}')
    print()

    # Cargar IDs ya procesados
    if os.path.exists(ID_FILE):
        with open(ID_FILE, encoding='utf-8') as f:
            processed_ids = set(json.load(f))
    else:
        processed_ids = set()

    # Todos los IDs vistos en esta corrida (records + ignorados)
    all_reviewed_ids = set(ignored_ids)

    # Copiar DB a directorio temporal (evita problemas de escritura en mount FUSE)
    shutil.copy2(DB_PATH, WORK_DB)

    conn = sqlite3.connect(WORK_DB, timeout=10)
    conn.execute('PRAGMA foreign_keys=ON')
    cur = conn.cursor()

    # Cargar categorías reales desde la DB
    db_categories = load_db_categories(cur)
    print(f'Categorías en DB: {sorted(db_categories.values())}')
    print()

    # Crear import batch (card_id=NULL porque puede ser mixto cards/transfers)
    now = datetime.now().isoformat()
    label = f'Gmail - tarea programada {now[:16]}'
    cur.execute(
        '''INSERT INTO importbatch (imported_at, provider, source_file, card_id,
           statement_year_month, purchases_created, purchases_skipped, purchases_parsed)
           VALUES (?, ?, ?, NULL, ?, 0, 0, 0)''',
        (now, 'gmail', label, '2099-01')
    )
    batch_id = cur.lastrowid

    created = 0
    skipped_dup_id = 0
    skipped_dup_db = 0

    try:
        for rec in records:
            msg_id = rec.get('msg_id', '')
            all_reviewed_ids.add(msg_id)

            # Skip si ya fue procesado
            if msg_id in processed_ids:
                print(f'  SKIP (ID ya procesado): {rec.get("description")}')
                skipped_dup_id += 1
                continue

            date = rec['purchase_date']
            desc = normalize_purchase_description(description=rec['description'])
            amount = float(rec['amount_original'])
            installments = int(rec.get('installments_total', 1))
            installment_amount = round(amount / installments, 2)
            first_month = rec.get('first_installment_month') or _default_first_month(date, rec.get('payment_method', 'CARD'))
            payment_method = rec.get('payment_method', 'CARD')
            card_id = rec.get('card_id')
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

            # Insertar payer — quien paga es el dueño de la tarjeta, no el consumidor.
            # card_id=1 (Pablo) → payer=1; card_id=2/3 (Cintia) → payer=2.
            # Transferencias (card_id=None) → payer=owner.
            if card_id == 1:
                payer_person_id = 1
            elif card_id in (2, 3):
                payer_person_id = 2
            else:
                payer_person_id = owner_person_id
            cur.execute(
                "INSERT INTO purchasepayer (purchase_id, person_id, share_type, share_value) VALUES (?, ?, 'PERCENT', 100.0)",
                (purchase_id, payer_person_id)
            )

            created += 1
            print(f'  ✓ INSERTADO: {date} | {desc} | ${amount:,.2f} | {category or "sin categoría"} | owner={owner_person_id} payer={payer_person_id}')

        # Actualizar batch
        total = created + skipped_dup_db
        cur.execute(
            'UPDATE importbatch SET purchases_created=?, purchases_skipped=?, purchases_parsed=? WHERE id=?',
            (created, skipped_dup_db, total, batch_id)
        )

        conn.commit()

    finally:
        conn.close()

        # Copiar DB de vuelta al mount (siempre, incluso si hubo error parcial)
        shutil.copy2(WORK_DB, DB_PATH)

        # Limpiar journal si existe
        journal = DB_PATH + '-journal'
        if os.path.exists(journal):
            with open(journal, 'wb') as f:
                f.truncate(0)

        # Guardar IDs procesados (siempre, para no re-evaluar en la próxima corrida)
        processed_ids.update(all_reviewed_ids)
        with open(ID_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(processed_ids), f, indent=2)

    # Reporte final
    print()
    print('=' * 50)
    print(f'Nuevos registros insertados : {created}')
    print(f'Saltados (ID ya procesado)  : {skipped_dup_id}')
    print(f'Saltados (duplicado en DB)  : {skipped_dup_db}')
    print(f'IDs ignorados registrados   : {len(ignored_ids)}')
    print(f'IDs guardados en archivo    : {len(processed_ids)}')
    if created == 0:
        print('Sin nuevos gastos para importar en esta corrida.')
    print('=' * 50)


def _run_railway_mode(records: list, ignored_ids: list, railway_url: str) -> None:
    username = os.environ.get('APP_USERNAME', '')
    password = os.environ.get('APP_PASSWORD', '')
    auth = (username, password)

    DB_PATH = detect_db_path()
    ID_FILE = os.path.join(os.path.dirname(DB_PATH), 'gmail_processed_ids.json')

    if os.path.exists(ID_FILE):
        with open(ID_FILE, encoding='utf-8') as f:
            processed_ids = set(json.load(f))
    else:
        processed_ids = set()

    all_reviewed_ids = set(ignored_ids)
    created = 0
    skipped = 0

    print(f'Railway mode: {railway_url}')
    print(f'Registros a evaluar: {len(records)}')
    print()

    # Cargar categorías desde Railway API
    db_categories = _load_railway_categories(railway_url, auth)

    for rec in records:
        msg_id = rec.get('msg_id', '')
        all_reviewed_ids.add(msg_id)

        if msg_id in processed_ids:
            print(f'  SKIP (ID ya procesado): {rec.get("description")}')
            skipped += 1
            continue

        # Resolver categoría dinámicamente
        category_concept = rec.get('category_concept', 'varios')
        resolved = resolve_category(category_concept, db_categories)
        rec_with_category = {**rec, 'category_concept': resolved}

        try:
            ok = insert_via_api(rec_with_category, railway_url, auth)
        except Exception as e:
            print(f'  ERROR al insertar {rec.get("description")}: {e}')
            continue

        if ok:
            created += 1
            print(f'  ✓ INSERTADO: {rec["purchase_date"]} | {rec["description"]} | ${float(rec["amount_original"]):,.2f}')
        else:
            skipped += 1
            print(f'  SKIP (duplicado API): {rec["purchase_date"]} | {rec["description"]}')

    processed_ids.update(all_reviewed_ids)
    with open(ID_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(processed_ids), f, indent=2)

    print()
    print('=' * 50)
    print(f'Nuevos registros insertados : {created}')
    print(f'Saltados                    : {skipped}')
    print(f'IDs guardados en archivo    : {len(processed_ids)}')
    print('=' * 50)


def _default_first_month(purchase_date, payment_method):
    """Calcula first_installment_month si el agente lo omitió."""
    y, m, _ = purchase_date.split('-')
    ym = f'{y}-{m}'
    if payment_method == 'TRANSFER':
        return ym
    return add_months(ym, 1)


if __name__ == '__main__':
    main()

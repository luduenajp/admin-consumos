---
name: gmail-gastos-a-db
description: Importar gastos de emails no leídos de Gmail a app.db de admin-consumos
---

## Objetivo
Leer emails no leídos de Gmail de Juan Pablo (luduenajp@gmail.com), extraer gastos y transferencias bancarias, e insertarlos en la base de datos SQLite en `/Users/pablo/github/admin-consumos/data/app.db`. Evitar duplicados usando un archivo de IDs procesados y verificando contra registros ya existentes en la DB.

## Archivo de IDs procesados

Ruta: `/Users/pablo/github/admin-consumos/data/gmail_processed_ids.json`

- Si no existe, crearlo con contenido `[]`
- Al inicio de cada corrida, cargar la lista de IDs ya procesados
- Al finalizar, guardar todos los IDs procesados (anteriores + nuevos) en ese archivo
- Si un `messageId` ya está en la lista → saltarlo sin leerlo

Ejemplo de manejo:
```python
import json, os

ID_FILE = '/Users/pablo/github/admin-consumos/data/gmail_processed_ids.json'

if os.path.exists(ID_FILE):
    with open(ID_FILE) as f:
        processed_ids = set(json.load(f))
else:
    processed_ids = set()

# ... al final:
processed_ids.update(new_ids)
with open(ID_FILE, 'w') as f:
    json.dump(list(processed_ids), f)
```

## Paso 1 — Leer emails no leídos

Usar Gmail para buscar: query `is:unread`, maxResults: 50.

Para cada mensaje, si el `messageId` ya está en `processed_ids` → saltarlo.

Procesar SOLO los siguientes tipos (identificar por From y Subject antes de leer el body):

1. **Santander "Pagaste $X"** — From contiene `santander.com.ar`, Subject contiene "Pagaste". Del snippet extraer: Monto, Cuotas, Comercio, Fecha. No es necesario leer el body completo.
2. **Santander "Aviso de débito automático"** — From Santander, Subject "Aviso de débito automático". Leer body: Monto, Comercio, Fecha.
3. **Santander "Tu adicional hizo un consumo"** — From Santander. Leer body: Monto, Cuotas, Comercio, Fecha, número de tarjeta del adicional. Owner = Cintia (person_id=2).
4. **Santander "Aviso de transferencia"** — From Santander. Leer body: Importe, CUIT Destinatario, CBU Crédito, Fecha.
5. **MercadoPago "Tu transferencia fue enviada"** — From `info@mercadopago.com`. Leer body: monto (ej: "$ 70.000"), Nombre beneficiario, Fecha del header.
6. **BNA "Transferencia Debitada"** — From `noreply@bnainfo.bna.com.ar`. Leer body: Importe, CUIT del Destinatario, CBU Crédito, Fecha.

IGNORAR (marcar como procesado igualmente para no revisarlos en futuras corridas):
- Encuestas, opiniones, resúmenes de cuenta, vencimientos, alertas de seguridad, promociones, seguros (actualizaciones de cobertura)
- "Tu pago fue anulado" — ignorar y también ignorar el pago original del mismo comercio/monto/fecha
- Transferencias donde el beneficiario es el mismo Juan Pablo (CBU Santander de Pablo o nombre "Ludue" / "Juan Pablo")
- Solicitudes/notificaciones de reembolso sin monto de compra nuevo
- "Pago aprobado en X" de MercadoPago cuando ya existe notificación Santander del mismo comercio/monto/fecha

## Paso 2 — Mapear datos de cada registro

Para **compras con tarjeta** (Santander "Pagaste" y débitos automáticos):
- `card_id` = 1 (Visa Pablo 5623), si es tarjeta adicional 7550 → card_id=1, owner_person_id=2
- `payment_method` = 'CARD'
- `purchase_date` = fecha del email → YYYY-MM-DD
- `description` = nombre del comercio tal como viene
- `currency` = 'ARS'; si dice "U$S" → 'USD'
- `amount_original` = monto total (quitar puntos, reemplazar coma por punto decimal)
- `installments_total` = cuotas (número entero)
- `installment_amount_original` = round(amount_original / installments_total, 2)
- `first_installment_month` = mes siguiente a purchase_date en formato YYYY-MM
- `owner_person_id` = 1 (Pablo); adicional 7550 → 2 (Cintia)
- `category` según descripción:
  - EPEC, AguasCordobesas, ECOGAS, Personal, Claro, PAGOS360* → 'SERVICIOS'
  - SEGUROS RIVADAVIA, ADT, BINA SEGUROS, CHUBB, CHUBBTES → 'SEGUROS'
  - RENTAS, TACATACA*RENTAS, AFIP, CORDOBA.GOB, vep → 'IMPUESTOS'
  - YPF, SHELL, SHELLBOX, AXION, combustib, APPYPF → 'NAFTA'
  - LIBERTAD, WALMART, DISCO, supermercado → 'SUPER'
  - restaurante, café, confitería, GRIDO, PANINO, MARACUYA → 'restaurantes'
  - NETFLIX, YouTube, AUTOENTRADA, CINE → 'entretenimiento'
  - Todo lo demás → 'OTROS - VARIOS'
- `is_refund` = 0, `debt_settled` = 0, `is_common` = 0

Para **transferencias** (Santander, BNA, MercadoPago):
- `card_id` = NULL, `payment_method` = 'TRANSFER', `currency` = 'ARS'
- `installments_total` = 1, `installment_amount_original` = amount_original
- `first_installment_month` = mismo mes que purchase_date en formato YYYY-MM (las transferencias salen al instante, no al mes siguiente como las tarjetas)
- `owner_person_id` = 1
- `description`:
  - MP: "Transferencia MP a [Nombre beneficiario]"
  - Santander: "Transferencia Santander a CUIT [CUIT]"
  - BNA: "Transferencia BNA a CUIT [CUIT]"; si CBU destino = 0000003100075898344262 → "Transferencia BNA a Nancy Beatriz Videla"
- `category`: Nancy Beatriz Videla → 'SERVICIOS'; resto → 'OTROS - VARIOS'
- `is_refund` = 0, `debt_settled` = 0, `is_common` = 0

## Paso 3 — Insertar en la base de datos

**IMPORTANTE:** La DB tiene problemas de I/O en escritura directa (mount FUSE). Usar siempre copia local:

```python
import sqlite3, shutil, os
from datetime import datetime

# Detectar el path del mount dinámicamente (varía por sesión)
import glob
mounts = glob.glob('/sessions/*/mnt/admin-consumos/data/app.db')
DB_PATH = mounts[0] if mounts else '/sessions/gracious-compassionate-planck/mnt/admin-consumos/data/app.db'

# Usar directorio temporal de la sesión actual como WORK_DB
import tempfile
WORK_DB = os.path.join(tempfile.gettempdir(), 'admin_consumos_work.db')

shutil.copy2(DB_PATH, WORK_DB)
conn = sqlite3.connect(WORK_DB, timeout=10)
conn.execute('PRAGMA foreign_keys=ON')
cur = conn.cursor()
```

**Deduplicación por DB** (además del ID file):
```python
def is_duplicate(cur, date, desc, amount):
    cur.execute(
        'SELECT id FROM purchase WHERE purchase_date=? AND description=? AND ABS(amount_original-?)<=0.02',
        (date, desc, amount)
    )
    return cur.fetchone() is not None
```

**Para cada registro nuevo** (no duplicado):
1. INSERT en `purchase`
2. INSERT en `installmentschedule` — una fila por cuota:
   - `year_month` incremental desde `first_installment_month`
   - `installment_index` desde 1
   - `currency` y `amount_original` = installment_amount_original
3. INSERT en `purchasepayer`:
   - `(purchase_id, owner_person_id, 'PERCENT', 100.0)`

**Crear importbatch:**
```python
now = datetime.now().isoformat()
label = f'Gmail - tarea programada {now[:16]}'
cur.execute('''INSERT INTO importbatch (imported_at,provider,source_file,card_id,
    statement_year_month,purchases_created,purchases_skipped,purchases_parsed)
    VALUES (?,?,?,1,?,0,0,0)''', (now,'gmail',label,'2099-01'))
batch_id = cur.lastrowid
# ... insertar con import_batch_id=batch_id ...
cur.execute('UPDATE importbatch SET purchases_created=?,purchases_skipped=?,purchases_parsed=? WHERE id=?',
    (created, skipped, created+skipped, batch_id))
```

**Función add_months:**
```python
def add_months(ym, n):
    y, m = map(int, ym.split('-'))
    m += n
    while m > 12: m -= 12; y += 1
    return f'{y:04d}-{m:02d}'
```

**Commitar y copiar de vuelta:**
```python
conn.commit()
conn.close()
shutil.copy2(WORK_DB, DB_PATH)

# Vaciar journal si existe (no borrar)
journal = DB_PATH + '-journal'
if os.path.exists(journal):
    with open(journal, 'wb') as f:
        f.truncate(0)
```

**Nota sobre rutas:** La DB está montada en `/sessions/<session-id>/mnt/admin-consumos/data/app.db`. Usar `glob.glob('/sessions/*/mnt/admin-consumos/data/app.db')[0]` para detectar el path dinámicamente.

## Paso 4 — Guardar IDs procesados

Al finalizar (haya o no nuevos registros), guardar TODOS los messageIds revisados en el archivo:
```python
processed_ids.update(all_reviewed_ids)  # incluyendo los ignorados
with open(ID_FILE, 'w') as f:
    json.dump(list(processed_ids), f, indent=2)
```

**Nota sobre rutas:** El archivo de IDs está en el mismo directorio que la DB — usar `os.path.dirname(DB_PATH) + '/gmail_processed_ids.json'`.

## Paso 5 — Reportar resultado

Imprimir resumen:
- N nuevos registros insertados (listar fecha, descripción, monto)
- N duplicados saltados (por ID file o por DB)
- N emails ignorados (no financieros)
- Si no hay nada nuevo: "Sin nuevos gastos para importar en esta corrida."

## Datos de referencia

**Personas:** id=1 Pablo, id=2 Cintia
**Tarjetas:** id=1 Visa Pablo Santander 5623, id=2 Visa Nación Cintia, id=3 Master Nación Cintia
**DB:** detectar con `glob.glob('/sessions/*/mnt/admin-consumos/data/app.db')[0]`
**IDs procesados:** mismo directorio que la DB, archivo `gmail_processed_ids.json`

**Schema purchase:** card_id, payment_method (CARD/TRANSFER/CASH), purchase_date (DATE), description, currency (ARS/USD), amount_original, installments_total, installment_amount_original, first_installment_month (YYYY-MM), owner_person_id, category, is_refund, debt_settled, is_common, import_batch_id
**Schema installmentschedule:** purchase_id, year_month (YYYY-MM), installment_index, currency, amount_original
**Schema purchasepayer:** purchase_id, person_id, share_type ('PERCENT'), share_value (100.0)

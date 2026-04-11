---
name: gmail-gastos-a-db
description: Importar gastos de emails no leídos de Gmail a app.db de admin-consumos
---

## Objetivo

Leer emails no leídos de Gmail de Juan Pablo (luduenajp@gmail.com), extraer gastos y
transferencias bancarias, y ejecutar el script `scripts/gmail_import.py` que maneja
toda la lógica de inserción, deduplicación y categorías.

**El agente solo hace dos cosas:**
1. Leer emails via Gmail MCP y armar un JSON con los registros
2. Llamar al script Python con ese JSON

Toda la lógica de DB, categorías y deduplicación vive en el script.

---

## Paso 1 — Cargar IDs ya procesados

```python
import json, os, glob

mounts = glob.glob('/sessions/*/mnt/admin-consumos/data/app.db')
DB_PATH = mounts[0]
ID_FILE = os.path.dirname(DB_PATH) + '/gmail_processed_ids.json'

if os.path.exists(ID_FILE):
    with open(ID_FILE) as f:
        processed_ids = set(json.load(f))
else:
    processed_ids = set()
```

---

## Paso 2 — Leer emails no leídos

Buscar en Gmail: query `is:unread`, maxResults: 50.

Para cada mensaje, si el `messageId` ya está en `processed_ids` → saltar sin leerlo.

**Tipos a procesar** (identificar por From y Subject antes de leer el body):

1. **Santander "Pagaste $X"** — From contiene `santander.com.ar`, Subject contiene "Pagaste".
   Del snippet extraer: Monto, Cuotas, Comercio, Fecha. No hace falta leer el body.

2. **Santander "Aviso de débito automático"** — From Santander, Subject "Aviso de débito automático".
   Leer body: Monto, Comercio, Fecha.

3. **Santander "Tu adicional hizo un consumo"** — From Santander.
   Leer body: Monto, Cuotas, Comercio, Fecha, número de tarjeta del adicional. Owner = Cintia (person_id=2).

4. **Santander "Aviso de transferencia"** — From Santander.
   Leer body: Importe, CUIT Destinatario, CBU Crédito, Fecha.

5. **MercadoPago "Tu transferencia fue enviada"** — From `info@mercadopago.com`.
   Leer body: monto (ej: "$ 70.000"), Nombre beneficiario, Fecha del header.

6. **BNA "Transferencia Debitada"** — From `noreply@bnainfo.bna.com.ar`.
   Leer body: Importe, CUIT del Destinatario, CBU Crédito, Fecha.

**IGNORAR** (agregar a `processed_ids` igual para no revisarlos de nuevo):
- Encuestas, resúmenes de cuenta, vencimientos, alertas de seguridad, promociones, seguros (actualizaciones de cobertura)
- "Tu pago fue anulado" — ignorar y también ignorar el pago original del mismo comercio/monto/fecha
- Transferencias donde el beneficiario es el mismo Juan Pablo: CUIL **20339576786**, DNI **33957678**, nombre contiene "Ludue" o "Juan Pablo", o CBU conocido de Pablo
- "Pago aprobado en X" de MercadoPago cuando ya existe notificación Santander del mismo comercio/monto/fecha

---

## Paso 3 — Armar JSON con los registros

Construir una lista de objetos con este formato:

```json
[
  {
    "msg_id": "19d7e588eab26583",
    "purchase_date": "2026-04-11",
    "description": "CP*FACTURAS CLARO",
    "currency": "ARS",
    "amount_original": 31416.08,
    "installments_total": 1,
    "first_installment_month": "2026-05",
    "payment_method": "CARD",
    "card_id": 1,
    "owner_person_id": 1,
    "category_concept": "servicios",
    "is_refund": 0,
    "debt_settled": 0,
    "is_common": 0
  }
]
```

### Reglas de mapeo

**Compras con tarjeta** (Santander "Pagaste" y débitos automáticos):
- `card_id` = 1; si tarjeta adicional 7550 → card_id=1, owner_person_id=2
- `payment_method` = "CARD"
- `purchase_date` = fecha del email → YYYY-MM-DD
- `description` = nombre del comercio tal como viene
- `currency` = "ARS"; si dice "U$S" → "USD"
- `amount_original` = monto total (quitar puntos de miles, reemplazar coma por punto decimal)
- `installments_total` = número de cuotas
- `first_installment_month` = mes **siguiente** a purchase_date (YYYY-MM)
- `owner_person_id` = 1 (Pablo); adicional 7550 → 2 (Cintia)
- `category_concept` según descripción:
  - EPEC, AguasCordobesas, ECOGAS, Personal, Claro, PAGOS360* → `"servicios"`
  - SEGUROS RIVADAVIA, ADT, BINA SEGUROS, CHUBB, CHUBBTES → `"seguros"`
  - RENTAS, TACATACA*RENTAS, AFIP, CORDOBA.GOB, vep → `"impuestos"`
  - YPF, SHELL, SHELLBOX, AXION, combustib, APPYPF → `"combustible"`
  - LIBERTAD, WALMART, DISCO, supermercado → `"supermercado"`
  - restaurante, café, confitería, GRIDO, PANINO, MARACUYA → `"restaurantes"`
  - NETFLIX, YouTube, AUTOENTRADA, CINE → `"entretenimiento"`
  - Todo lo demás → `"varios"`

**Transferencias** (Santander, BNA, MercadoPago):
- `card_id` = null, `payment_method` = "TRANSFER", `currency` = "ARS"
- `installments_total` = 1
- `first_installment_month` = **mismo mes** que purchase_date (YYYY-MM)
- `owner_person_id` = 1
- `description`:
  - MP: "Transferencia MP a [Nombre beneficiario]"
  - Santander: "Transferencia Santander a CUIT [CUIT]"
  - BNA: "Transferencia BNA a CUIT [CUIT]"; si CBU destino = 0000003100075898344262 → "Transferencia BNA a Nancy Beatriz Videla"
- `category_concept`: Nancy Beatriz Videla → `"servicios"`; resto → `"varios"`

---

## Paso 4 — Ejecutar el script

Guardar el JSON en un archivo temporal y llamar al script:

```python
import json, tempfile, subprocess, glob, os

# Escribir JSON temporal
tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
json.dump(records, tmp, ensure_ascii=False)
tmp.close()

# Detectar path del proyecto
mounts = glob.glob('/sessions/*/mnt/admin-consumos')
project_root = mounts[0]
script = os.path.join(project_root, 'scripts', 'gmail_import.py')

# Ejecutar
result = subprocess.run(
    ['python3', script, tmp.name],
    capture_output=True, text=True
)
print(result.stdout)
if result.stderr:
    print('STDERR:', result.stderr)

os.unlink(tmp.name)  # limpiar archivo temporal
```

---

## Paso 5 — Reportar resultado

Mostrar la salida del script tal cual. El script ya imprime:
- Registros insertados (fecha, descripción, monto, categoría)
- Duplicados saltados
- Warnings de categorías no encontradas
- Resumen final

---

## Datos de referencia

**Personas:** id=1 Pablo, id=2 Cintia
**Tarjetas:** id=1 Visa Pablo Santander 5623, id=2 Visa Nación Cintia, id=3 Master Nación Cintia
**Script:** `scripts/gmail_import.py` (en la raíz del proyecto)
**Categorías:** el script las carga dinámicamente desde la DB — no hardcodear nombres

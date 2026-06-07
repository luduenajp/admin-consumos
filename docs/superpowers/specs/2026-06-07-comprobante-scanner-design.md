# Diseño: Escáner de Comprobantes de Transferencia

**Fecha:** 2026-06-07  
**Estado:** Aprobado

## Resumen

Feature para registrar transferencias bancarias subiendo un comprobante (PNG/JPG/PDF). Claude Vision API extrae el monto, fecha y destinatario. El formulario de compra se pre-completa con los datos extraídos. Una tabla de `Beneficiary` permite reconocer destinatarios frecuentes (verdulería, kiosco, servicios) y sugerir guardar nuevos.

---

## 1. Modelo de Datos

### Nueva tabla `Beneficiary`

| Columna | Tipo   | Notas |
|---------|--------|-------|
| `id`    | int PK | auto  |
| `name`  | str    | requerido, ej. "Verdulería Lopez" |
| `cbu`   | str?   | opcional |
| `cuit`  | str?   | opcional |
| `alias` | str?   | opcional, ej. "verduleria.lopez" |

- No hay FK desde `Purchase` hacia `Beneficiary` — el matching es un helper en tiempo de carga, no una relación persistente.
- No tiene relación con `Debtor`. Son conceptos distintos: un Debtor es quien te debe plata; un Beneficiary es a quien vos le pagás.
- La UI sugiere llenar al menos un identificador (CBU, CUIT o alias) pero no se fuerza a nivel DB.

### Migración

`db.py:_migrate_add_columns()` agrega la tabla `beneficiary` si no existe. Idempotente.

### Config

`ANTHROPIC_API_KEY` se agrega a `config.py` (sin default). Si no está configurada, el endpoint devuelve HTTP 503.

---

## 2. API Endpoints

### `POST /api/import/comprobante`

Extrae datos del comprobante usando Claude Vision API y retorna campos pre-completados con matching de beneficiario.

**Request:** `multipart/form-data`, campo `file` (PNG/JPG/PDF).

**Proceso:**
1. Llama a Claude Vision API con el archivo y un prompt estructurado.
2. Extrae: monto, fecha, moneda, nombre del destinatario, CBU, CUIT, alias (lo que sea visible).
3. Matching contra tabla `Beneficiary`:
   - **Exact:** CBU o CUIT idénticos.
   - **Fuzzy:** alias normalizado (lowercase, sin espacios) o nombre con similitud ≥ 80% (`difflib.SequenceMatcher`).
4. Devuelve resultado con confianza del match.

**Response 200:**
```json
{
  "amount": 4500.00,
  "date": "2026-06-07",
  "currency": "ARS",
  "description": "Verdulería Lopez",
  "matched_beneficiary": {
    "id": 3,
    "name": "Verdulería Lopez",
    "confidence": "exact"
  },
  "raw_extracted": {
    "cbu": "0720...",
    "nombre": "LOPEZ MARIA"
  }
}
```

`matched_beneficiary` es `null` si no hay match. `raw_extracted` siempre presente para que el frontend pueda pre-llenar el mini-modal de "guardar beneficiario".

**Errores:**
- `503` — `ANTHROPIC_API_KEY` no configurada.
- `422` — archivo no es imagen ni PDF.
- `502` — error al llamar a Claude API.

### CRUD `/api/beneficiaries`

| Método | Path | Acción |
|--------|------|--------|
| GET | `/api/beneficiaries` | Lista todos |
| POST | `/api/beneficiaries` | Crea nuevo (`name` requerido) |
| PUT | `/api/beneficiaries/{id}` | Edita |
| DELETE | `/api/beneficiaries/{id}` | Elimina |

---

## 3. Flujo de UI

### Punto de entrada — `/purchases`

Botón secundario **"Desde comprobante"** junto al botón "Nueva compra" existente. Abre file picker con `accept="image/*,application/pdf"`.

### Estados del flujo

**Caso A — Beneficiario reconocido:**
- `PurchaseForm` se abre pre-completado.
- Banner verde: "Destinatario reconocido: Verdulería Lopez".

**Caso B — No reconocido:**
- `PurchaseForm` se abre pre-completado (description = nombre extraído).
- Banner amarillo: "¿Guardar 'LOPEZ MARIA' como beneficiario frecuente?" con botones [Guardar] [Ignorar].
- Click en "Guardar": mini-modal con campos pre-completados (nombre, CBU/alias extraídos) editables. Confirmar → `POST /api/beneficiaries`.

**Caso C — Error de extracción:**
- Mensaje de error inline.
- `PurchaseForm` se abre vacío para carga manual.

### Campos pre-completados en `PurchaseForm`

| Campo | Valor |
|-------|-------|
| `amount` | extraído |
| `purchase_date` | extraído |
| `currency` | extraído (default ARS) |
| `description` | nombre del beneficiario |
| `payment_method` | `transfer` (fijo) |
| `installments` | `1` (fijo) |

Los campos `payer`, `is_common`, `category` quedan vacíos para completar manualmente.

### ABM de Beneficiarios

Nueva sección al final de `/admin` con tabla de beneficiarios y formulario inline para crear/editar. Mismo patrón que el ABM de Debtors existente.

---

## 4. Modelo Claude Vision

- **Modelo:** `claude-opus-4-8` con `thinking: {type: "adaptive"}`.
- **Input:** imagen o PDF enviado como contenido base64 en el mensaje.
- **Prompt:** solicita JSON estructurado con campos `monto`, `fecha`, `moneda`, `destinatario.nombre`, `destinatario.cbu`, `destinatario.cuit`, `destinatario.alias`. Incluye instrucción de devolver `null` para campos no visibles.
- **Parsing:** respuesta parseada como JSON. Si falla el parse, se devuelve error 502 al cliente.

---

## 5. Archivos a crear/modificar

### Backend
- `backend/app/models.py` — agregar `Beneficiary`
- `backend/app/schemas.py` — agregar `BeneficiaryCreate`, `BeneficiaryRead`
- `backend/app/crud.py` — agregar `list_beneficiaries`, `create_beneficiary`, `update_beneficiary`, `delete_beneficiary`, `match_beneficiary`
- `backend/app/api.py` — agregar CRUD endpoints de beneficiarios
- `backend/app/import_api.py` — agregar `POST /import/comprobante`
- `backend/app/db.py` — agregar migración de tabla `beneficiary`
- `backend/app/config.py` — agregar `ANTHROPIC_API_KEY`
- `backend/requirements.txt` — agregar `anthropic`
- `.env.example` — agregar `ANTHROPIC_API_KEY`

### Frontend
- `frontend/src/api/types.ts` — agregar `Beneficiary`, `ComprobanteExtraction`
- `frontend/src/api/endpoints.ts` — agregar funciones para beneficiarios y comprobante
- `frontend/src/pages/purchases-page.tsx` — agregar botón + flujo de carga
- `frontend/src/pages/admin-page.tsx` — agregar sección ABM de beneficiarios

### Tests
- `backend/tests/test_beneficiaries.py` — CRUD + matching logic
- `backend/tests/test_comprobante_import.py` — endpoint (mock de Claude API)

---

## 6. Fuera de scope

- Parsing heurístico sin Vision API (fallback si no hay API key).
- Historial de comprobantes procesados (no se guarda el archivo).
- Matching automático para PDF de resúmenes bancarios (eso ya existe en `visa_pdf.py`).
- Transfers entre Pablo y Cintia via este flujo (eso usa `DebtTransfer`, no `Purchase`).

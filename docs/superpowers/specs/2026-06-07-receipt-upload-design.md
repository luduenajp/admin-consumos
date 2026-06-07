# Spec: Upload de Comprobante y Botón Nueva Transferencia

**Fecha:** 2026-06-07  
**Contexto:** Mobile-first. El usuario quiere registrar transferencias desde el dashboard con soporte de comprobante (imagen/PDF) que auto-completa los campos del formulario vía OCR/extracción de texto.

---

## Objetivo

1. Agregar un botón **"+ Nueva transferencia"** en el dashboard que abra el `PurchaseForm` con `payment_method: 'transfer'` pre-seleccionado.
2. Agregar un **campo de comprobante** en `PurchaseForm` (para todos los tipos de compra) que permita subir una imagen o PDF para auto-completar `amount_original`, `purchase_date` y `description`.
3. Integrar la tabla `Beneficiary` existente para **auto-completar la descripción** cuando el destinatario del comprobante coincide con un beneficiario guardado.
4. Ofrecer **"¿Guardar como destinatario frecuente?"** cuando el destinatario extraído no existe en `Beneficiary`.

El archivo subido **no se persiste** — solo se usa durante la sesión para ayudar al usuario a completar el formulario.

---

## Componentes

### 1. Dashboard — Botón "Nueva transferencia"

- Nuevo botón secundario en el panel de controles del dashboard, debajo de "+ Nueva compra".
- Al hacer click abre el `PurchaseForm` pasando `initialValues: { payment_method: 'transfer' }`.
- No requiere lógica nueva — reutiliza el mecanismo `showAddForm` existente con un segundo estado `showTransferForm`.
- Estilo: mismo ancho que "+ Nueva compra", color secundario (no primary terracotta).

### 2. PurchaseForm — Campo de comprobante

- **Input file:** `accept="image/*,.pdf"`, atributo `capture="environment"` para activar cámara en mobile.
- **Preview:** thumbnail si es imagen, nombre de archivo si es PDF.
- **Flujo al seleccionar archivo:**
  1. Mostrar spinner de carga.
  2. POST a `/api/receipts/parse` (multipart/form-data).
  3. Al recibir respuesta exitosa: pre-llenar campos con badge visual "✓ auto-completado" (color `--color-primary` tenue).
  4. Campos pre-llenados: `amount_original`, `purchase_date`, `description`.
  5. Si hay `matched_beneficiary_name`: usar ese valor en `description`.
  6. Si `new_beneficiary_name` en respuesta: mostrar pill "¿Guardar '\{nombre\}' como destinatario frecuente?" con botón "Guardar".
  7. El usuario puede editar cualquier campo sin restricciones.
- **Errores de parse:** mostrar mensaje inline "No se pudo leer el comprobante. Completá los campos manualmente." Sin bloquear el formulario.
- El campo de comprobante se posiciona al inicio del formulario (antes del resto de los campos).

### 3. Backend — `POST /api/receipts/parse`

**Archivo nuevo:** `backend/app/receipt_parser.py`  
**Endpoint:** registrado en `api.py` dentro de `api_router`.

**Lógica de extracción:**

| Tipo de archivo | Método |
|---|---|
| PDF | `pdfplumber` — extracción de texto directo (no OCR) |
| JPG / PNG / WEBP | `Pillow` (preprocesamiento: escala de grises, contraste) + `pytesseract` |

**Pipeline de parseo (sobre el texto extraído):**

1. **Monto:** regex para formatos ARS (`$\s*\d{1,3}(\.\d{3})*,\d{2}`) y USD. Se queda con el monto más prominente (el mayor encontrado, o el primero si solo hay uno).
2. **Fecha:** regex `DD/MM/YYYY` o `DD-MM-YYYY`. Primera fecha encontrada.
3. **Destinatario:** busca líneas con "DESTINATARIO", "A:", "ALIAS:", "CBU:" u heurísticas por posición en el texto. Extrae nombre, CBU (22 dígitos) y/o alias.
4. **Matching de beneficiario:** si se extrajo CBU o alias, consulta `Beneficiary` table por coincidencia exacta. Si hay match, retorna `matched_beneficiary_name`.
5. **Moneda:** si hay símbolo "U$S" o "USD" cerca del monto → `USD`, default `ARS`.

**Response schema:**
```json
{
  "amount_original": 15000.50,
  "purchase_date": "2026-06-05",
  "description": "Nombre Destinatario",
  "currency": "ARS",
  "matched_beneficiary_name": "Supermercado Coto",
  "new_beneficiary_name": "Juan Pérez"
}
```
Todos los campos son opcionales (null si no se pudo extraer).

**Manejo de errores:** si el archivo no se puede leer o el texto está vacío, retorna HTTP 200 con todos los campos null (no un error HTTP — el frontend maneja gracefully).

### 4. Guardar destinatario frecuente

- Si la respuesta tiene `new_beneficiary_name` (destinatario no encontrado en Beneficiary):
  - El frontend muestra una pill debajo del campo de comprobante con el nombre.
  - Botón "Guardar" llama a `POST /api/beneficiaries` con el nombre extraído.
  - El CBU/alias extraído también se envía si está disponible.
  - Tras guardar: la pill cambia a "✓ Guardado".
- Esta acción es opcional — el usuario puede ignorar la sugerencia.

---

## Dependencias nuevas

### Python (pip)
```
pytesseract>=0.3.10
pdfplumber>=0.11.0
Pillow>=10.0.0  # probablemente ya instalado
```

### Sistema (prerequisito)
```bash
brew install tesseract
# Verificar: tesseract --version
```

Agregar a `backend/requirements.txt`. Documentar el prerequisito del sistema en `README` o `start.sh`.

---

## Patrones de regex (a validar con comprobantes reales)

Los patrones se afinarán una vez que el usuario provea ejemplos de comprobantes del Santander y BNA. Los formatos conocidos del proyecto (de la lógica de Gmail existente) son punto de partida:

- Santander: "Pagaste $X" / "Tu adicional hizo un consumo de $X"
- BNA: "Aviso de transferencia" / monto en formato tabla
- MercadoPago: "$ X.XXX,XX"

---

## Archivos a crear/modificar

| Archivo | Acción |
|---|---|
| `backend/app/receipt_parser.py` | Crear — lógica OCR + regex + matching de beneficiario |
| `backend/app/api.py` | Modificar — agregar endpoint `POST /api/receipts/parse` |
| `backend/requirements.txt` | Modificar — agregar `pytesseract`, `pdfplumber`, `Pillow` |
| `frontend/src/components/PurchaseForm.tsx` | Modificar — agregar campo comprobante con preview, parse y auto-fill |
| `frontend/src/pages/dashboard-page.tsx` | Modificar — agregar botón "Nueva transferencia" |
| `frontend/src/api/endpoints.ts` | Modificar — agregar `parseReceipt(file)` |
| `frontend/src/api/types.ts` | Modificar — agregar `ReceiptParseResult` interface |

---

## Flujo completo (mobile)

```
Usuario en Dashboard (mobile)
  → tap "+ Nueva transferencia"
  → PurchaseForm abre con payment_method=transfer
  → tap "Subir comprobante" → cámara o galería
  → selecciona foto del comprobante
  → preview aparece, spinner carga
  → campos se pre-llenan (monto, fecha, destinatario)
  → [opcional] "¿Guardar 'Juan Pérez' como destinatario frecuente?" → tap Guardar
  → usuario revisa campos, ajusta si hace falta
  → tap Guardar → compra registrada
```

---

## Fuera de scope

- Persistencia del archivo de comprobante adjunto a la compra (NTH del roadmap — ítem 6).
- Auto-fill para compras con tarjeta (cuotas, número de comprobante).
- OCR en idiomas distintos al español.
- Soporte para fotos de tickets físicos (la calidad variable hace poco confiable el OCR sin calibración).

# Formatos de importación – especificaciones

## Visa XLSX (implementado)

### Estructura del archivo
- Hoja única con tabla de movimientos.
- Header detectado: `Fecha`, `Descripción`, `Cuotas`, `Comprobante`, `Monto en pesos`, `Monto en dólares`.
- Puede haber múltiples tablas por tarjeta (titular/adicional) y filas de totales.

### Reglas de parseo
- **Fecha**: `dd/mm/YYYY`. Se convierte a `date`.
- **Cuotas**: texto `"x de y"` o `C.X/Y` (ej. `C.17/24`) → `(installment_index, installments_total)`. Si no hay, se asume `1/1`.
- **Monto**: formato argentino (`$1.443.685,70`, `U$S24,51`). Se limpia y convierte a `float`.
- **Moneda**: se infiere del monto no nulo (`Monto en pesos` → ARS; `Monto en dólares` → USD).

### Exclusiones (MVP)
- Montos `<= 0` (pagos, bonificaciones, devoluciones).
- Descripciones que empiezan con (case-insensitive):
  - `"Su pago"`
  - `"Promo"`
  - `"Cr."` o `"Cr "`
  - `"Total de"`
  - `"Tarjeta de"`
  - `"Tarjeta Visa"`
  - `"Movimientos del resumen"`
- Impuestos: `DB.RG 5617`, `IIBB PERCEP`, `IMPUESTO DE SELLOS`, `IMPUESTO AL SELLO`
- Bonificaciones: `BONIF.`
- Otros: `Pago de tarjeta`, `Resumen de [mes]`
- **Incluye**: devoluciones por compra anulada

### Deduplicación
- Se genera un `row_fingerprint` (SHA256) con: `provider + card_id + fecha + descripción + moneda + cuotas + monto`.
- Si ya existe en `ImportedRow`, se saltea la fila (`skipped`).

### Generación de calendario de cuotas
- `first_installment_month` = `statement_year_month - (installment_index - 1)`.
- Se crean `installments_total` filas en `InstallmentSchedule` con `year_month` consecutivos.

---

## Santander CSV (por implementar)

### Estructura esperada (ejemplo)
- Columnas: `Fecha`, `Descripción`, `Cuota Actual`, `Cuotas Totales`, `Importe`, `Moneda`.
- Separador: `,` o `;`.
- Encoding: UTF-8 o Latin-1.

### Reglas pendientes
- Detectar encoding y separador.
- Mapeo de moneda (`ARS`/`USD`).
- Exclusiones similares a Visa.

---

## Banco Nación CSV (por implementar)

### Estructura esperada
- Columnas: `Fecha`, `Concepto`, `Débito`, `Crédito`, `Cuotas`, `Moneda`.
- Posibles filas de resumen a excluir.

---

## MercadoPago CSV (por implementar)

### Estructura esperada
- Columnas: `Fecha`, `Concepto`, `Monto`, `Tipo`, `Cuotas`.
- Puede incluir movimientos de wallet y tarjeta; filtrar por tarjeta.

---

## PDF (implementado)

### Formatos soportados (orden de intento)
1. **Banco Nación Visa**: `FECHA COMPROBANTE DETALLE DE TRANSACCION PESOS DOLAR`, líneas `DD.MM.YY comprobante descripción C.X/Y monto_pesos monto_usd`
2. **Banco Nación Mastercard**: `DETALLES DEL MES` / `CUOTAS DEL MES`, líneas `DD-Mmm-YY descripción X/Y comprobante monto`
3. **MercadoPago**: líneas `DD/mmm descripción $ monto` (ej. `10/nov MERPAGO*COMERCIO 3 de 3 304823 $ 22.293,25`)

### Detección de mes de cierre
- Busca en texto: `CIERRE ACTUAL`, `Cierre actual X de febrero`, `Fecha de cierre`, `Resumen de febrero`

### Password
- Los PDFs pueden venir protegidos con contraseña (ej. Nación: `34247332`). Parámetro opcional `password` en el endpoint.

### Implementación
- Parser en `backend/app/importers/visa_pdf.py` (pypdf + pdfplumber).
- Endpoint: `POST /api/import/visa-pdf?provider=...&card_id=...`
- Mismas exclusiones y deduplicación que XLSX.

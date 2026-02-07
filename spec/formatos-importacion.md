# Formatos de importación – especificaciones

## Visa XLSX (implementado)

### Estructura del archivo
- Hoja única con tabla de movimientos.
- Header detectado: `Fecha`, `Descripción`, `Cuotas`, `Comprobante`, `Monto en pesos`, `Monto en dólares`.
- Puede haber múltiples tablas por tarjeta (titular/adicional) y filas de totales.

### Reglas de parseo
- **Fecha**: `dd/mm/YYYY`. Se convierte a `date`.
- **Cuotas**: texto `"x de y"` → `(installment_index, installments_total)`. Si no hay, se asume `1/1`.
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

## PDF (fase 2)

### Password
- Los PDFs pueden venir protegidos con contraseña: `34247332`.

### Estrategia
- Extraer tablas con librería PDF (ej. `pdfplumber` o `camelot`).
- Normalizar a mismo esquema que XLSX/CSV.
- Aplicar mismas exclusiones y deduplicación.

### Notas
- El layout puede cambiar entre bancos; se sugiere un parser por proveedor.
- Si el parseo falla, mostrar error claro y no importar nada.

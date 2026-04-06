# Card Statements — Fechas de Cierre y Vencimiento

**Fecha:** 2026-04-05  
**Estado:** Aprobado

## Problema

Las fechas de cierre y vencimiento de las tarjetas varían cada mes (fines de semana, feriados). Actualmente el sistema asume siempre "mes siguiente" para compras con tarjeta, lo que es incorrecto cuando la compra se hace antes del cierre del mes en curso. Esto afecta tanto al formulario manual como al proceso automático `gmail-gastos-a-db`.

## Solución

Nueva tabla `CardStatement` que almacena la fecha exacta de cierre y vencimiento por tarjeta por mes. Ambos clientes (frontend y gmail task) consultan esta tabla para calcular `first_installment_month` correctamente.

## Modelo de datos

### Tabla `CardStatement`

| Campo          | Tipo            | Descripción                              |
|----------------|-----------------|------------------------------------------|
| `id`           | int PK          |                                          |
| `card_id`      | int FK → card   |                                          |
| `year_month`   | str `YYYY-MM`   | Mes del resumen                          |
| `closing_date` | date            | Fecha exacta de cierre del resumen       |
| `due_date`     | date (opcional) | Fecha exacta de vencimiento del pago     |

**Constraint único:** `(card_id, year_month)` — un registro por tarjeta por mes.  
**Patrón:** upsert — si ya existe el par `(card_id, year_month)`, actualizar.

Normalmente se cargan 1-2 meses por adelantado (mes actual + siguiente).

## Lógica de sugerencia de mes

Dado `card_id` y `purchase_date`:

1. Buscar todos los `CardStatement` de esa tarjeta con `closing_date >= purchase_date`
2. Tomar el de `closing_date` más cercano
3. Retornar su `year_month` como `first_installment_month`
4. **Fallback:** si no hay registros → retornar `add_months(purchase_date[:7], 1)` (comportamiento actual)

Ejemplo: tarjeta Master MP Pablo, cierre 2026-04-06, compra 2026-04-05 → `closing_date (6) >= purchase_day (5)` → `first_installment_month = "2026-04"`.

## API

### Endpoints nuevos

| Método | Path | Descripción |
|--------|------|-------------|
| `GET` | `/api/card-statements?card_id=X` | Lista statements de una tarjeta |
| `POST` | `/api/card-statements` | Crea o actualiza (upsert por card_id + year_month) |
| `DELETE` | `/api/card-statements/{id}` | Elimina un statement |
| `GET` | `/api/card-statements/suggest-month?card_id=X&purchase_date=YYYY-MM-DD` | Retorna mes sugerido |

### Response de `suggest-month`

```json
{
  "year_month": "2026-04",
  "closing_date": "2026-04-06",
  "fallback": false
}
```

Cuando `fallback: true`, `closing_date` es `null` y `year_month` es el mes siguiente calculado.

### Schema `CardStatementCreate`

```python
card_id: int
year_month: str  # regex YYYY-MM
closing_date: date
due_date: Optional[date] = None
```

### Schema `CardStatementRead`

```python
id: int
card_id: int
year_month: str
closing_date: date
due_date: Optional[date]
```

## Backend — Implementación

### `models.py`
Agregar clase `CardStatement(SQLModel, table=True)`.

### `db.py`
Agregar migración idempotente en `_migrate_add_columns()` para crear la tabla si no existe (usar `CREATE TABLE IF NOT EXISTS`).

### `crud.py`
- `upsert_card_statement(session, payload)` — crea o actualiza por `(card_id, year_month)`
- `list_card_statements(session, card_id)` — lista ordenado por `year_month`
- `delete_card_statement(session, statement_id)`
- `suggest_first_installment_month(session, card_id, purchase_date)` — implementa la lógica de sugerencia, retorna `(year_month, closing_date_or_none, is_fallback)`

### `schemas.py`
Agregar `CardStatementCreate` y `CardStatementRead` con validación `year_month` regex.

### `api.py`
Registrar los 4 endpoints nuevos bajo el router existente.

## Frontend

### Admin page (`admin-page.tsx`)
Nueva sección "Fechas de Resumen" debajo de la lista de tarjetas:
- Selector de tarjeta
- Tabla con columnas: Mes, Cierre, Vencimiento, Eliminar
- Formulario inline: month picker, date inputs para closing_date y due_date
- Submit llama a `POST /api/card-statements`

### PurchaseForm (`PurchaseForm.tsx`)
- Al cambiar `card_id` o `purchase_date`, si `payment_method === 'card'`, llamar a `GET /api/card-statements/suggest-month`
- Actualizar `first_installment_month` con el resultado
- Mostrar hint debajo del campo:
  - Con datos: *"Cierre 6 abr → entra en abril"*
  - Fallback: *"Sin datos de cierre — asumiendo mes siguiente"*

### `api/endpoints.ts` y `api/types.ts`
Agregar tipos e interfaces `CardStatement`, funciones fetch para los 4 endpoints.

## Gmail task (`gmail-gastos-a-db.md`)

### Calcular `first_installment_month`
Reemplazar la lógica hardcodeada `add_months(purchase_date[:7], 1)` por:

```python
def suggest_first_installment_month(cur, card_id, purchase_date_str):
    cur.execute(
        '''SELECT year_month FROM cardstatement
           WHERE card_id=? AND closing_date >= ?
           ORDER BY closing_date ASC LIMIT 1''',
        (card_id, purchase_date_str)
    )
    row = cur.fetchone()
    if row:
        return row[0]
    # fallback
    y, m = map(int, purchase_date_str[:7].split('-'))
    m += 1
    if m > 12: m = 1; y += 1
    return f'{y:04d}-{m:02d}'
```

### Poblar `cardstatement` desde emails
Si el email contiene fechas de cierre/vencimiento (ej: "Tu resumen cierra el 6 de abril"), insertarlas:

```python
cur.execute(
    '''INSERT INTO cardstatement (card_id, year_month, closing_date, due_date)
       VALUES (?,?,?,?)
       ON CONFLICT(card_id, year_month) DO UPDATE SET
           closing_date=excluded.closing_date,
           due_date=excluded.due_date''',
    (card_id, year_month, closing_date, due_date)
)
```

### Corregir categorías desactualizadas
Reemplazar en la sección de mapeo:
- `'NAFTA'` → `'Combustible'`
- `'SUPER'` → `'Supermercado'`
- `'SERVICIOS'` → `'Servicios'`
- `'SEGUROS'` → `'Seguros'`
- `'IMPUESTOS'` → `'Impuestos'`
- `'restaurantes'` → `'Restaurantes'`
- `'entretenimiento'` → `'Entretenimiento'`
- `'OTROS - VARIOS'` → `'Varios'`

## Reglas de negocio

- **BR-nuevo-1:** `first_installment_month` para compras con tarjeta se determina por el `CardStatement` más próximo con `closing_date >= purchase_date`. Si no existe registro, se asume mes siguiente.
- **BR-nuevo-2:** Solo se almacena un `CardStatement` por `(card_id, year_month)`. Re-enviar el mismo par actualiza los valores existentes.
- **BR-nuevo-3:** Normalmente se cargan 1-2 meses. No hay validación que fuerce un límite.

## Testing

### Backend
- `suggest_first_installment_month`: compra antes del cierre → mes actual; compra después del cierre → mes siguiente; sin datos → fallback mes siguiente
- Upsert: crear nuevo, actualizar existente, unique constraint no genera duplicados
- Delete: elimina correctamente

### Frontend
- PurchaseForm: al seleccionar tarjeta con closing_date, hint muestra el mes correcto
- PurchaseForm: tarjeta sin datos → hint de fallback
- Admin page: CRUD de statements funciona correctamente

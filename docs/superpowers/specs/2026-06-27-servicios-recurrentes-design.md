# Diseño: Módulo de Servicios Recurrentes

**Fecha:** 2026-06-27
**Estado:** Aprobado

## Resumen

Módulo para hacer seguimiento mensual de servicios e impuestos recurrentes (luz, gas, agua, impuestos municipales, etc.). Reemplaza el control que el usuario llevaba en Excel. Permite saber de un vistazo qué servicios están pagados, cuáles están por vencer y cuáles están vencidos en el mes actual, y recibe una alerta en el dashboard cuando hay servicios pendientes.

---

## Modelo de Datos

### Tabla `Service`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `name` | str | Ej: "Gas", "Luz", "Impuesto Municipal" |
| `expected_amount` | float nullable | Monto esperado mensual de referencia |
| `typical_due_day` | int nullable | Día del mes en que suele vencer (1–31) |
| `is_active` | bool default True | Ocultar sin borrar |
| `sort_order` | int default 0 | Orden de las cards en la UI |

### Tabla `ServicePayment`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | int PK | |
| `service_id` | FK → Service | |
| `year_month` | str "YYYY-MM" | Mes al que corresponde la factura |
| `due_date` | date nullable | Fecha de vencimiento de este mes (editable) |
| `paid_date` | date nullable | Fecha en que se pagó; null = no pagado |
| `amount` | float nullable | Monto pagado; null = no pagado |
| `notes` | str nullable | Campo libre opcional |

**Unicidad:** `(service_id, year_month)` — un solo registro por servicio por mes.

Un registro con `paid_date = null` es un portador de `due_date` solamente (no es un pago). Un registro es "pagado" si y solo si `paid_date is not null`.

---

## Estados del Semáforo

El cálculo se hace con la fecha actual del cliente (enviada como parámetro o computada en el frontend) para evitar problemas de zona horaria UTC vs Argentina (UTC-3).

| Estado | Color | Condición |
|---|---|---|
| Pagado | 🟢 Verde | `paid_date is not null` |
| Por vencer | 🟡 Amarillo | Sin pagar y `due_date <= hoy + 3 días` |
| Vencido | 🔴 Rojo | Sin pagar y `due_date < hoy` |
| Sin fecha | ⚪ Gris | Sin pagar y sin `due_date` |

"Por vencer" incluye el día exacto de vencimiento (`due_date == hoy` → amarillo).

---

## API Endpoints

Todos bajo prefijo `/api`.

### Servicios (CRUD)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/services` | Lista todos los servicios (activos e inactivos) |
| `POST` | `/services` | Crear servicio |
| `PUT` | `/services/{id}` | Editar nombre, monto esperado, día de vencimiento, orden, activo |
| `DELETE` | `/services/{id}` | Borrar solo si no tiene pagos; si tiene, retorna 409 con mensaje "usar is_active=false" |

### Pagos de Servicios

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/service-payments?year_month=YYYY-MM` | Retorna todos los servicios activos con su registro del mes (o null si no existe). Incluye `suggested_due_date` calculado. |
| `POST` | `/service-payments` | Crear o actualizar registro del mes (upsert por `service_id + year_month`) |
| `PUT` | `/service-payments/{id}` | Editar `due_date`, `paid_date`, `amount`, `notes` |
| `DELETE` | `/service-payments/{id}` | Borrar registro completo (desmarcar pago y due_date) |

**Desmarcar pago sin perder due_date:** usar `PUT` seteando `paid_date=null, amount=null, notes=null` — no DELETE.

### Dashboard

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/service-payments/summary?year_month=YYYY-MM` | `{ unpaid_count, overdue_names, due_soon_names }` — liviano, para el widget del dashboard |

---

## Lógica de Negocio

### Auto-sugerencia de `due_date`

Cuando el GET de `/service-payments` construye la respuesta para un servicio sin registro en el mes pedido, calcula `suggested_due_date` así:

1. Busca `ServicePayment.due_date` del mes anterior para ese servicio → suma 1 mes
2. Si no existe, usa `Service.typical_due_day` con el año-mes pedido
3. Si tampoco existe, `suggested_due_date = null`

Si el día resultante no existe en el mes (ej: día 31 en abril), se clampea al último día del mes.

### Validaciones

- `amount > 0` si se provee (Pydantic)
- `year_month` con regex `^\d{4}-(0[1-9]|1[0-2])$`
- `typical_due_day` entre 1 y 31
- `paid_date` puede ser de cualquier mes (pagar tarde es válido — no restringir)
- Unicidad `(service_id, year_month)` → HTTP 409 si se intenta crear duplicado

### Borrado de Service

- Sin pagos asociados → DELETE real
- Con pagos asociados → HTTP 409, indicar que se use `is_active=false`

---

## Frontend

### Nueva página `/servicios`

- Selector de mes en el tope (mismo componente que el dashboard)
- Grid de cards, 2 columnas en mobile, 3–4 en desktop
- Cada card muestra:
  - Nombre del servicio
  - Indicador de semáforo (círculo de color)
  - Fecha de vencimiento del mes (editable inline)
  - Si pagado: monto + fecha de pago + diferencia vs `expected_amount` (ej. "+$1.200 sobre lo esperado")
  - Si pendiente: `expected_amount` como referencia (si está cargado)
  - Botón "Registrar pago" (pendiente) o "Editar / Desmarcar pago" (pagado)
- Al tocar "Registrar pago": formulario inline con fecha (default hoy), monto y nota opcional
- Sección de gestión al pie: agregar / editar / desactivar servicios

### Widget en el dashboard

- Aparece solo si `unpaid_count > 0` para el mes seleccionado
- Bloque de alerta en color ámbar (coherente con el sistema de diseño existente)
- Texto: "X servicios sin pagar: Gas (vence hoy), Agua (vencido), Municipal"
- Link directo a `/servicios`
- Si todos están pagados: no aparece nada (sin ruido visual)

### Navegación

- Nuevo ítem "Servicios" en el menú lateral y móvil
- Verificar en implementación que el menú móvil no quede saturado; si es necesario, reorganizar ítems menos usados

---

## Manejo de Errores

| Situación | Comportamiento |
|---|---|
| Duplicado `(service_id, year_month)` | HTTP 409 |
| DELETE de service con pagos | HTTP 409 con mensaje claro |
| `amount ≤ 0` | HTTP 422 (validación Pydantic) |
| `due_date` con día inválido para el mes | Backend clampea al último día válido |
| `paid_date` fuera del `year_month` | Permitido sin restricción |

---

## Tests

### Backend

- CRUD de `Service` (crear, editar, desactivar, borrar sin pagos, error al borrar con pagos)
- CRUD de `ServicePayment` (crear, editar, desmarcar preservando `due_date`, duplicado → 409)
- Lógica semáforo: los 4 estados según `paid_date` y `due_date`
- Auto-sugerencia de `due_date`: desde mes anterior, desde `typical_due_day`, sin dato
- Clampeo de día 31 en mes corto
- `GET /service-payments/summary` retorna conteos correctos

### Frontend

- Card en cada estado del semáforo renderiza el color y texto correcto
- Formulario de registro de pago: validación de monto, default de fecha a hoy
- "Desmarcar pago" conserva la `due_date` visible en la card

---

## Premortems considerados

1. **Zona horaria:** Semáforo calculado en el cliente con fecha local, no en el servidor con UTC.
2. **Día inválido en mes corto:** Clampeado al último día del mes.
3. **Auto-sugerencia:** Mes anterior tiene precedencia sobre `typical_due_day`.
4. **Registros sin pago:** `paid_date=null` no cuenta como gasto en ningún reporte.
5. **Desmarcar pago:** UPDATE (no DELETE) para preservar `due_date`.
6. **`paid_date` fuera del mes:** Sin restricción — pagar tarde es válido.
7. **Borrado con historial:** Solo desactivar; DELETE bloqueado si hay pagos.
8. **Menú móvil:** Verificar capacidad al implementar navegación.

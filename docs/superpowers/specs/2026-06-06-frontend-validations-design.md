# Frontend Validations — Design Spec

**Date:** 2026-06-06
**Phase:** Fase 2 — Mejoras de UX

## Objetivo

Estandarizar el manejo de errores de validación en todos los formularios del frontend. Eliminar `alert()`, `required` HTML nativo y patrones inconsistentes. Reemplazar con errores inline debajo de cada campo, en español, con un patrón uniforme en toda la app.

## CSS

Una sola clase nueva en `frontend/src/App.css`:

```css
.fieldError {
  color: #c0392b;
  font-size: 0.78rem;
  margin-top: 3px;
  display: block;
}
```

Uso: `{errors.campo && <span className="fieldError">{errors.campo}</span>}` debajo de cada `<input>` o `<select>`.

## Patrón de validación

Cada formulario implementa este patrón con estado local:

```ts
const [errors, setErrors] = useState<Record<string, string>>({})
const [touched, setTouched] = useState<Record<string, boolean>>({})

function validate(field: string, value: string): string {
  // reglas por campo — retorna mensaje de error o ''
}

function handleBlur(field: string, value: string) {
  setTouched(t => ({ ...t, [field]: true }))
  setErrors(e => ({ ...e, [field]: validate(field, value) }))
}

function handleSubmit(e: React.FormEvent) {
  e.preventDefault()
  const allErrors = validateAll()       // valida todos los campos obligatorios
  const allTouched = markAllTouched()   // marca todos como tocados
  setErrors(allErrors)
  setTouched(allTouched)
  if (Object.values(allErrors).some(Boolean)) return
  // dispara mutation
}
```

Al submit exitoso: `setErrors({})` y `setTouched({})` junto con el reset del form state.

### Cuándo se muestran los errores

- **Al salir del campo (blur):** si el campo fue tocado, valida y muestra error inmediatamente.
- **Al intentar enviar:** valida todos los campos obligatorios sin excepción, marca todos como tocados.

### Eliminaciones

- Todos los `alert()` de validación → reemplazados por `errors` state.
- Todos los atributos `required` HTML en inputs/selects → removidos (el browser muestra sus propios popups que se mezclan con los inline).
- Los guards con `return` temprano sin feedback visible → reemplazados con mensaje inline.

## Mensajes de error (en español)

| Situación | Mensaje |
|---|---|
| Campo de texto vacío | `"Requerido"` |
| Tarjeta no seleccionada (payment_method=card) | `"Seleccioná una tarjeta"` |
| Monto vacío o inválido | `"Ingresá un monto válido"` |
| Monto igual a 0 o negativo | `"El monto debe ser mayor a 0"` |
| Archivo no seleccionado | `"Seleccioná un archivo"` |
| URL de Google Sheets vacía | `"Ingresá la URL del sheet"` |
| Persona no seleccionada | `"Seleccioná una persona"` |
| Mes no seleccionado | `"Seleccioná un mes"` |

## Formularios afectados

### 1. `PurchaseForm` (`components/PurchaseForm.tsx`)

Campos a validar:
- `description`: requerido, no vacío
- `amount_original`: requerido, número > 0
- `owner_person_id`: requerido (persona que pagó)
- `card_id`: requerido solo si `payment_method === 'card'`

Cambio: reemplaza el `alert()` en `handleSubmit` por `errors` state. Agrega `onBlur` en los cuatro campos.

### 2. `import-page` (`pages/import-page.tsx`)

Campos a validar:
- `cardId`: requerido para formatos xlsx/pdf (no para gsheets)
- `file`: requerido para formatos xlsx/pdf
- `gsheetsUrl`: requerido para formato gsheets

Cambio: la validación sale del `mutationFn` (donde estaba como `throw new Error()`) y pasa a un `validate()` llamado en `handleSubmit` antes de disparar la mutation. Los errores se muestran inline sobre el botón de importar.

### 3. `admin-page` (`pages/admin-page.tsx`)

Cinco sub-formularios independientes, cada uno con su propio par `[errors, setErrors]`:

| Sub-form | Campos |
|---|---|
| Crear Persona | `name`: requerido |
| Crear Tarjeta | `name`: requerido, `ownerPersonId`: requerido |
| Crear FX Rate | `month`: requerido, `rate`: requerido y > 0 |
| Crear Deudor | `name`: requerido |
| Crear Resumen de Tarjeta | `cardId`: requerido, `month`: requerido, `closeDate`: requerido |

El sub-form de Resumen de Tarjeta ya tiene `setError('Tarjeta, mes y fecha de cierre son obligatorios')` como banner — migrar a inline.

### 4. `budget-page` (`pages/budget-page.tsx`)

Dos formularios:
- **Ingreso**: `person_id` requerido, `month` requerido, `amount` requerido y > 0
- **Transferencia**: `from_person_id` requerido, `to_person_id` requerido, `month` requerido, `amount` requerido y > 0

### 5. `categories-page` (`pages/categories-page.tsx`)

Un formulario simple. Actualmente tiene `if (!newCategory.name.trim()) return` sin feedback. Agregar `errors.name` con mensaje visible.

### 6. Edición inline en `purchases-page` (`pages/purchases-page.tsx`)

Los campos editables inline (description, amount) deben mostrar error si se vacían y se hace blur. No guardar hasta que el campo sea válido.

## Lo que NO cambia

- Errores de API (errores del servidor en `onError`) siguen usando `extractErrorMessage()` y se muestran como banner de error (`.error` class), no inline. Las validaciones inline son solo para errores del cliente antes de hacer el request.
- El patrón `disabled={mutation.isPending}` en botones se mantiene tal cual.
- La lógica de negocio (cuándo un campo es requerido según el estado del form) no cambia — solo la presentación del error.

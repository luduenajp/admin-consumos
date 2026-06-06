# Frontend Validations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estandarizar la validación de formularios en toda la app: errores inline debajo de cada campo, en español, con patrón uniforme (`errors` + `touched` state), eliminando todos los `alert()` y atributos `required` HTML nativos.

**Architecture:** Cada formulario tiene su propio `errors: Record<string, string>` y `touched: Record<string, boolean>` state. Una utilidad compartida `utils/formValidation.ts` expone los validadores primitivos (`requiredField`, `positiveNumber`). Cada componente tiene su propia función `validateField(field)` como closure sobre el estado del formulario. Los errores se muestran con `<span className="fieldError">` debajo de cada input.

**Tech Stack:** React 19 + TypeScript + Vitest + `@testing-library/react` (pero tests solo sobre utilidades puras, no componentes)

---

## Files Modified / Created

| File | Action |
|---|---|
| `frontend/src/App.css` | Modify — add `.fieldError` class |
| `frontend/src/utils/formValidation.ts` | Create — shared validation primitives |
| `frontend/src/utils/formValidation.test.ts` | Create — unit tests |
| `frontend/src/components/PurchaseForm.tsx` | Modify — errors/touched pattern, remove alert() |
| `frontend/src/pages/import-page.tsx` | Modify — inline errors para cardId, personId, gsheetsUrl |
| `frontend/src/pages/admin-page.tsx` | Modify — 5 sub-forms: PeopleSection, CardsSection, FxRatesSection, DebtorsSection, CardStatementsSection |
| `frontend/src/pages/budget-page.tsx` | Modify — 2 forms: income, transfer |
| `frontend/src/pages/categories-page.tsx` | Modify — add error display for name field |
| `frontend/src/pages/purchases-page.tsx` | Modify — EditableCell: validate required on blur |

---

## Task 1: CSS + formValidation utility

**Files:**
- Modify: `frontend/src/App.css`
- Create: `frontend/src/utils/formValidation.ts`
- Create: `frontend/src/utils/formValidation.test.ts`

- [ ] **Step 1: Add `.fieldError` class to App.css**

In `frontend/src/App.css`, find the `.hint` rule and add after it:

```css
.fieldError {
  color: var(--color-error-text);
  font-size: 0.78rem;
  margin-top: 3px;
  display: block;
}
```

- [ ] **Step 2: Create `frontend/src/utils/formValidation.ts`**

```ts
export function requiredField(value: string): string {
  return value.trim() ? '' : 'Requerido'
}

export function positiveNumber(value: string): string {
  if (!value.trim()) return 'Ingresá un monto válido'
  const n = parseFloat(value)
  if (isNaN(n) || n <= 0) return 'El monto debe ser mayor a 0'
  return ''
}
```

- [ ] **Step 3: Write `frontend/src/utils/formValidation.test.ts`**

```ts
import { describe, it, expect } from 'vitest'
import { requiredField, positiveNumber } from './formValidation'

describe('requiredField', () => {
  it('returns empty string for non-empty value', () => {
    expect(requiredField('hello')).toBe('')
  })

  it('returns error for empty string', () => {
    expect(requiredField('')).toBe('Requerido')
  })

  it('returns error for whitespace-only string', () => {
    expect(requiredField('   ')).toBe('Requerido')
  })
})

describe('positiveNumber', () => {
  it('returns empty string for valid positive number', () => {
    expect(positiveNumber('100')).toBe('')
    expect(positiveNumber('0.01')).toBe('')
    expect(positiveNumber('1234.56')).toBe('')
  })

  it('returns error for empty string', () => {
    expect(positiveNumber('')).toBe('Ingresá un monto válido')
  })

  it('returns error for whitespace', () => {
    expect(positiveNumber('   ')).toBe('Ingresá un monto válido')
  })

  it('returns error for zero', () => {
    expect(positiveNumber('0')).toBe('El monto debe ser mayor a 0')
  })

  it('returns error for negative number', () => {
    expect(positiveNumber('-5')).toBe('El monto debe ser mayor a 0')
  })

  it('returns error for non-numeric string', () => {
    expect(positiveNumber('abc')).toBe('El monto debe ser mayor a 0')
  })
})
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npm run test:run
```

Expected: all existing tests pass + 9 new tests for formValidation pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.css frontend/src/utils/formValidation.ts frontend/src/utils/formValidation.test.ts
git commit -m "feat: add fieldError CSS class and formValidation utility"
```

---

## Task 2: PurchaseForm

**Files:**
- Modify: `frontend/src/components/PurchaseForm.tsx`

The form has 4 required fields: `description`, `amount_original`, `owner_person_id`, `card_id` (last only when `payment_method === 'card'`). Currently validates in `handleSubmit` with `alert()`.

- [ ] **Step 1: Add imports and state at the top of `PurchaseForm`**

After the existing `import { getRelativeMonth }` line, add:

```ts
import { requiredField, positiveNumber } from '../utils/formValidation'
```

After the existing `const [amountInputValue, setAmountInputValue] = useState('')` line, add:

```ts
const [errors, setErrors] = useState<Record<string, string>>({})
const [touched, setTouched] = useState<Record<string, boolean>>({})
```

- [ ] **Step 2: Add `validateField`, `handleBlur`, and `validateAll` functions**

Add these three functions after the `useEffect` blocks (before `const createMutation`):

```ts
function validateField(field: string): string {
    switch (field) {
        case 'description': return requiredField(formData.description)
        case 'amount_original': return positiveNumber(formData.amount_original)
        case 'owner_person_id': return formData.owner_person_id ? '' : 'Seleccioná una persona'
        case 'card_id':
            return formData.payment_method === 'card' && !formData.card_id
                ? 'Seleccioná una tarjeta'
                : ''
        default: return ''
    }
}

function handleBlur(field: string) {
    setTouched(t => ({ ...t, [field]: true }))
    setErrors(e => ({ ...e, [field]: validateField(field) }))
}

function validateAll(): Record<string, string> {
    return {
        description: validateField('description'),
        amount_original: validateField('amount_original'),
        owner_person_id: validateField('owner_person_id'),
        card_id: validateField('card_id'),
    }
}
```

- [ ] **Step 3: Update `createMutation` to reset errors on success**

In the `onSuccess` callback of `createMutation`, add before `onSuccess?.()`:

```ts
setErrors({})
setTouched({})
```

- [ ] **Step 4: Replace `handleSubmit` body**

Replace the entire current `handleSubmit` function:

```ts
const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const allErrors = validateAll()
    setErrors(allErrors)
    setTouched({ description: true, amount_original: true, owner_person_id: true, card_id: true })
    if (Object.values(allErrors).some(Boolean)) return

    const payload: PurchaseCreate = {
        purchase_date: formData.purchase_date,
        description: formData.description,
        payment_method: formData.payment_method,
        amount_original: parseFloat(formData.amount_original),
        currency: formData.currency,
        owner_person_id: Number(formData.owner_person_id),
        category: formData.category || null,
        notes: formData.notes || null,
        is_common: formData.is_common,
        debtor_id: formData.debtor_id ? Number(formData.debtor_id) : null,
        beneficiary_person_id: (!formData.is_common && formData.beneficiary_person_id) ? Number(formData.beneficiary_person_id) : null,
        card_id: formData.card_id ? Number(formData.card_id) : null,
        installments_total: parseInt(formData.installments_total) || 1,
        first_installment_month: formData.first_installment_month,
    }

    createMutation.mutate(payload)
}
```

- [ ] **Step 5: Add `onBlur` and `fieldError` spans to the JSX**

In the JSX, make these four changes:

**Description field** — add `onBlur` and error span:
```tsx
<input
    className="input"
    type="text"
    placeholder="Ej: Supermercado"
    value={formData.description}
    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
    onBlur={() => handleBlur('description')}
/>
{errors.description && <span className="fieldError">{errors.description}</span>}
```

**Amount field** — add `onBlur` and error span (the input inside the amount row):
```tsx
<input
    className="input"
    type="number"
    step="0.01"
    min="0"
    placeholder="0.00"
    value={amountInputValue}
    onChange={(e) => setAmountInputValue(e.target.value)}
    onBlur={() => handleBlur('amount_original')}
/>
{errors.amount_original && <span className="fieldError">{errors.amount_original}</span>}
```

**Owner person field** — add `onBlur` and error span:
```tsx
<select
    className="input"
    value={formData.owner_person_id}
    onChange={(e) => setFormData({ ...formData, owner_person_id: e.target.value })}
    onBlur={() => handleBlur('owner_person_id')}
>
    <option value="">Seleccionar...</option>
    {people.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
</select>
{errors.owner_person_id && <span className="fieldError">{errors.owner_person_id}</span>}
```

**Card field** — add `onBlur` and error span:
```tsx
<select
    className="input"
    value={formData.card_id}
    disabled={formData.payment_method !== 'card'}
    onChange={(e) => setFormData({ ...formData, card_id: e.target.value })}
    onBlur={() => handleBlur('card_id')}
>
    <option value="">Seleccionar tarjeta...</option>
    {cards.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
</select>
{errors.card_id && <span className="fieldError">{errors.card_id}</span>}
```

Also remove the `required` attribute from the owner_person_id select and the amount input.

- [ ] **Step 6: Run build to verify TypeScript compiles**

```bash
cd frontend && npm run build
```

Expected: 0 TypeScript errors, build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/PurchaseForm.tsx
git commit -m "feat: inline validation on PurchaseForm — replace alert() with fieldError spans"
```

---

## Task 3: import-page

**Files:**
- Modify: `frontend/src/pages/import-page.tsx`

The import page has two flows: gsheets (personId + gsheetsUrl required) and xlsx/pdf (cardId required after detection). Validation currently lives inside `mutationFn` as `throw new Error(...)`, which shows as a bottom banner. Move to inline errors.

- [ ] **Step 1: Add `importErrors` state**

After the existing `useState` declarations (around line 35-50 of the file), add:

```ts
const [importErrors, setImportErrors] = useState<Record<string, string>>({})
```

- [ ] **Step 2: Replace the gsheets import button's `onClick`**

Find the gsheets "Comenzar Importación" button and replace its `onClick`:

```tsx
onClick={() => {
  const errors: Record<string, string> = {}
  if (!formState.personId) errors.personId = 'Seleccioná un responsable'
  if (!formState.gsheetsUrl.trim()) errors.gsheetsUrl = 'Ingresá la URL del sheet'
  if (Object.keys(errors).length > 0) {
    setImportErrors(errors)
    return
  }
  setImportErrors({})
  importMutation.mutate()
}}
```

- [ ] **Step 3: Add inline error spans in the gsheets section**

After the `<select>` for Persona Responsable, add:
```tsx
{importErrors.personId && <span className="fieldError">{importErrors.personId}</span>}
```

After the `<input>` for URL de Google Sheets, add:
```tsx
{importErrors.gsheetsUrl && <span className="fieldError">{importErrors.gsheetsUrl}</span>}
```

- [ ] **Step 4: Replace the xlsx/pdf "Confirmar e Importar" button's `onClick`**

Find the `onClick={() => importMutation.mutate()}` in the confirmation panel (the one with `disabled={importMutation.isPending || !formState.cardId}`) and replace:

```tsx
onClick={() => {
  if (!formState.cardId) {
    setImportErrors({ cardId: 'Seleccioná una tarjeta' })
    return
  }
  setImportErrors({})
  importMutation.mutate()
}}
```

- [ ] **Step 5: Add inline error span for cardId in the detection result panel**

After the `<select>` for Tarjeta Destino in the detection result panel, add:
```tsx
{importErrors.cardId && <span className="fieldError">{importErrors.cardId}</span>}
```

- [ ] **Step 6: Clean up `mutationFn` — remove client-side field checks**

In `importMutation.mutationFn`, remove these lines (keep file extension checks — those are format validation, not missing field checks):

```ts
// Remove these:
if (formState.format === 'gsheets') {
  if (!formState.personId) throw new Error('Seleccioná un responsable del gasto')
  if (!formState.gsheetsUrl) throw new Error('Ingresá la URL del archivo de Google Sheets')
  ...
}
if (!formState.cardId) throw new Error('Seleccioná una tarjeta')
if (!formState.file) throw new Error('Seleccioná un archivo')
```

The remaining `mutationFn` for xlsx/pdf should be:

```ts
mutationFn: async () => {
  if (formState.format === 'gsheets') {
    return importGSheets({
      url: formState.gsheetsUrl,
      owner_person_id: formState.personId!,
      is_common: formState.isCommon,
    })
  }

  const name = formState.file!.name.toLowerCase()
  if (formState.format === 'pdf') {
    if (!name.endsWith('.pdf')) throw new Error('El archivo debe ser .pdf')
    return importVisaPdf({
      provider: formState.provider,
      cardId: formState.cardId!,
      file: formState.file!,
      password: formState.pdfPassword || undefined,
      is_common: formState.isCommon,
    })
  }
  if (!name.endsWith('.xlsx') && !name.endsWith('.xls')) {
    throw new Error('El archivo debe ser .xlsx o .xls')
  }
  return importVisaXlsx({
    provider: formState.provider,
    cardId: formState.cardId!,
    file: formState.file!,
    is_common: formState.isCommon,
  })
},
```

- [ ] **Step 7: Clear importErrors on format change**

In the format select's `onChange`, add `setImportErrors({})`:

```tsx
onChange={(e) =>
  setFormState((s) => ({
    ...s,
    format: e.target.value as ImportFormat,
    file: undefined,
  }))
}
// After setFormState, also clear errors:
// Add: setImportErrors({})
```

Since `setFormState` is the only call, replace the `onChange` with:

```tsx
onChange={(e) => {
  setFormState((s) => ({ ...s, format: e.target.value as ImportFormat, file: undefined }))
  setImportErrors({})
}}
```

- [ ] **Step 8: Run build**

```bash
cd frontend && npm run build
```

Expected: 0 TypeScript errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/import-page.tsx
git commit -m "feat: inline validation on import-page — move field errors out of mutationFn"
```

---

## Task 4: admin-page

**Files:**
- Modify: `frontend/src/pages/admin-page.tsx`

Five independent section components. Each gets its own `errors` + `touched` state.

### PeopleSection

Currently: button `disabled={!name.trim()}`, no error message. Add blur + inline error for name.

- [ ] **Step 1: Add `nameError` and `nameTouched` state to `PeopleSection`**

After `const [name, setName] = useState('')`, add:

```ts
const [nameError, setNameError] = useState('')
```

- [ ] **Step 2: Update input to add `onBlur`**

```tsx
<input
  className="input"
  value={name}
  onChange={(e) => setName(e.target.value)}
  onBlur={() => setNameError(name.trim() ? '' : 'Requerido')}
  placeholder="Ej: Pablo"
/>
{nameError && <span className="fieldError">{nameError}</span>}
```

- [ ] **Step 3: Clear error on success**

In `createMutation.onSuccess`, add `setNameError('')` after `setName('')`.

### CardsSection

Currently: button disabled when `!form.name.trim() || !form.ownerPersonId`. No error messages.

- [ ] **Step 4: Add `errors` state to `CardsSection`**

After `const [form, setForm] = useState(...)`, add:

```ts
const [errors, setErrors] = useState<Record<string, string>>({})
```

- [ ] **Step 5: Add `onBlur` to name and ownerPersonId fields**

Name input:
```tsx
<input
  className="input"
  value={form.name}
  onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))}
  onBlur={() => setErrors(e => ({ ...e, name: form.name.trim() ? '' : 'Requerido' }))}
  placeholder="Ej: Visa Santander"
/>
{errors.name && <span className="fieldError">{errors.name}</span>}
```

Owner select:
```tsx
<select
  className="input"
  value={form.ownerPersonId}
  onChange={(e) => setForm((s) => ({ ...s, ownerPersonId: e.target.value }))}
  onBlur={() => setErrors(e => ({ ...e, ownerPersonId: form.ownerPersonId ? '' : 'Seleccioná una persona' }))}
>
  <option value="">Seleccioná...</option>
  {people.map((p) => (
    <option key={p.id} value={p.id}>{p.name}</option>
  ))}
</select>
{errors.ownerPersonId && <span className="fieldError">{errors.ownerPersonId}</span>}
```

- [ ] **Step 6: Validate all on the submit button click**

Replace `onClick={() => createMutation.mutate()}` with:

```tsx
onClick={() => {
  const e = {
    name: form.name.trim() ? '' : 'Requerido',
    ownerPersonId: form.ownerPersonId ? '' : 'Seleccioná una persona',
  }
  setErrors(e)
  if (Object.values(e).some(Boolean)) return
  createMutation.mutate()
}}
```

Also remove `!form.name.trim() || !form.ownerPersonId` from `disabled` (keep only `createMutation.isPending`):

```tsx
disabled={createMutation.isPending}
```

- [ ] **Step 7: Clear errors on success**

In `createMutation.onSuccess`, add:
```ts
setErrors({})
```

### FxRatesSection

Currently: has an inline hint for invalid rate, button disabled when `!form.yearMonth || !form.rate || Number(form.rate) <= 0`. Replace with standard pattern.

- [ ] **Step 8: Add `errors` state to `FxRatesSection`**

After `const [form, setForm] = useState(...)`, add:

```ts
const [errors, setErrors] = useState<Record<string, string>>({})
```

- [ ] **Step 9: Add `onBlur` to yearMonth and rate inputs, remove old inline hint**

YearMonth input:
```tsx
<input
  className="input"
  type="month"
  value={form.yearMonth}
  onChange={(e) => setForm((s) => ({ ...s, yearMonth: e.target.value }))}
  onBlur={() => setErrors(e => ({ ...e, yearMonth: form.yearMonth ? '' : 'Requerido' }))}
/>
{errors.yearMonth && <span className="fieldError">{errors.yearMonth}</span>}
```

Rate input — replace the existing rate `<div>` that has the old hint with:
```tsx
<div style={{ flex: 1 }}>
  <input
    className="input"
    type="number"
    step="0.01"
    min="0.01"
    value={form.rate}
    onChange={(e) => setForm((s) => ({ ...s, rate: e.target.value }))}
    onBlur={() => setErrors(e => ({ ...e, rate: positiveNumber(form.rate) }))}
    placeholder="Ej: 1150.50"
  />
  {errors.rate && <span className="fieldError">{errors.rate}</span>}
</div>
```

Add import at the top of admin-page.tsx:
```ts
import { positiveNumber } from '../utils/formValidation'
```

- [ ] **Step 10: Validate all on save click**

Replace `onClick={() => upsertMutation.mutate()}` with:

```tsx
onClick={() => {
  const e = {
    yearMonth: form.yearMonth ? '' : 'Requerido',
    rate: positiveNumber(form.rate),
  }
  setErrors(e)
  if (Object.values(e).some(Boolean)) return
  upsertMutation.mutate()
}}
```

Remove the disabled conditions leaving only `upsertMutation.isPending`:
```tsx
disabled={upsertMutation.isPending}
```

- [ ] **Step 11: Clear errors on success**

In `upsertMutation.onSuccess`, add `setErrors({})`.

### DebtorsSection

Same pattern as PeopleSection (single `name` field, button already disabled).

- [ ] **Step 12: Add `nameError` state to `DebtorsSection`**

After `const [name, setName] = useState('')`, add:

```ts
const [nameError, setNameError] = useState('')
```

- [ ] **Step 13: Update input with `onBlur` and error span**

```tsx
<input
  className="input"
  value={name}
  onChange={(e) => setName(e.target.value)}
  onBlur={() => setNameError(name.trim() ? '' : 'Requerido')}
  placeholder="Ej: Marcos"
/>
{nameError && <span className="fieldError">{nameError}</span>}
```

- [ ] **Step 14: Clear error on success**

In `createMutation.onSuccess`, add `setNameError('')` after `setName('')`.

### CardStatementsSection

Currently: has a `setError(...)` banner for missing fields. Migrate to inline errors.

- [ ] **Step 15: Replace `const [error, setError] = useState('')` with `errors` state**

```ts
const [errors, setErrors] = useState<Record<string, string>>({})
```

- [ ] **Step 16: Add `onBlur` to form fields and update `handleSubmit`**

Year month input:
```tsx
<input
  type="month"
  className="input"
  value={form.year_month}
  onChange={(e) => setForm(s => ({ ...s, year_month: e.target.value }))}
  onBlur={() => setErrors(e => ({ ...e, year_month: form.year_month ? '' : 'Requerido' }))}
/>
{errors.year_month && <span className="fieldError">{errors.year_month}</span>}
```

Closing date input:
```tsx
<input
  type="date"
  className="input"
  value={form.closing_date}
  onChange={(e) => setForm(s => ({ ...s, closing_date: e.target.value }))}
  onBlur={() => setErrors(e => ({ ...e, closing_date: form.closing_date ? '' : 'Requerido' }))}
/>
{errors.closing_date && <span className="fieldError">{errors.closing_date}</span>}
```

Card selector (already present in the section):
```tsx
<select
  className="input"
  value={selectedCardId}
  onChange={(e) => {
    setSelectedCardId(e.target.value)
    setErrors(e2 => ({ ...e2, cardId: '' }))
  }}
  onBlur={() => setErrors(e => ({ ...e, cardId: selectedCardId ? '' : 'Seleccioná una tarjeta' }))}
>
  <option value="">Seleccionar tarjeta...</option>
  {cards.map((c) => (
    <option key={c.id} value={c.id}>{c.name}</option>
  ))}
</select>
{errors.cardId && <span className="fieldError">{errors.cardId}</span>}
```

- [ ] **Step 17: Replace `handleSubmit` in `CardStatementsSection`**

```ts
const handleSubmit = () => {
  const e = {
    cardId: selectedCardId ? '' : 'Seleccioná una tarjeta',
    year_month: form.year_month ? '' : 'Requerido',
    closing_date: form.closing_date ? '' : 'Requerido',
  }
  setErrors(e)
  if (Object.values(e).some(Boolean)) return
  upsertMutation.mutate({
    card_id: Number(selectedCardId),
    year_month: form.year_month,
    closing_date: form.closing_date,
    due_date: form.due_date || null,
  })
}
```

- [ ] **Step 18: Remove old error banner and clear errors on success**

Remove the old `{error && <div className="error">...}` from the JSX.

In `upsertMutation.onSuccess`, replace `setError('')` with `setErrors({})`.

In `upsertMutation.onError`, replace `setError(extractErrorMessage(e))` with a banner pattern — keep the API error as a banner using `upsertMutation.isError`:

```tsx
{upsertMutation.isError && (
  <div className="error" style={{ marginTop: '12px' }}>
    {extractErrorMessage(upsertMutation.error)}
  </div>
)}
```

- [ ] **Step 19: Run build**

```bash
cd frontend && npm run build
```

Expected: 0 TypeScript errors.

- [ ] **Step 20: Commit**

```bash
git add frontend/src/pages/admin-page.tsx
git commit -m "feat: inline validation on admin-page — 5 sub-forms"
```

---

## Task 5: budget-page

**Files:**
- Modify: `frontend/src/pages/budget-page.tsx`

Two forms: income (selectedPersonId + amount required) and transfer (fromPersonId + toPersonId + transferAmount required, fromPersonId ≠ toPersonId).

- [ ] **Step 1: Add `incomeErrors` and `transferErrors` state**

After the existing `useState` declarations, add:

```ts
const [incomeErrors, setIncomeErrors] = useState<Record<string, string>>({})
const [transferErrors, setTransferErrors] = useState<Record<string, string>>({})
```

- [ ] **Step 2: Add import for `positiveNumber`**

```ts
import { positiveNumber } from '../utils/formValidation'
```

- [ ] **Step 3: Replace `handleSubmitIncome`**

```ts
const handleSubmitIncome = (e: React.FormEvent) => {
  e.preventDefault()
  const errors = {
    selectedPersonId: selectedPersonId ? '' : 'Seleccioná una persona',
    amount: positiveNumber(amount),
  }
  setIncomeErrors(errors)
  if (Object.values(errors).some(Boolean)) return

  createIncomeMutation.mutate({
    person_id: parseInt(selectedPersonId),
    year_month: yearMonth,
    amount: parseFloat(amount),
    notes: notes.trim() || null,
  })
}
```

- [ ] **Step 4: Replace `handleSubmitTransfer`**

```ts
const handleSubmitTransfer = (e: React.FormEvent) => {
  e.preventDefault()
  const errors: Record<string, string> = {
    fromPersonId: fromPersonId ? '' : 'Seleccioná una persona',
    toPersonId: toPersonId ? '' : 'Seleccioná una persona',
    transferAmount: positiveNumber(transferAmount),
  }
  if (fromPersonId && toPersonId && fromPersonId === toPersonId) {
    errors.toPersonId = 'Debe ser distinta a la persona origen'
  }
  setTransferErrors(errors)
  if (Object.values(errors).some(Boolean)) return

  createTransferMutation.mutate({
    from_person_id: parseInt(fromPersonId),
    to_person_id: parseInt(toPersonId),
    year_month: yearMonth,
    amount: parseFloat(transferAmount),
    notes: transferNotes.trim() || null,
  })
}
```

- [ ] **Step 5: Add `onBlur` and `fieldError` spans in the income form JSX**

Persona select:
```tsx
<select
  className="input"
  value={selectedPersonId}
  onChange={(e) => setSelectedPersonId(e.target.value)}
  onBlur={() => setIncomeErrors(e => ({ ...e, selectedPersonId: selectedPersonId ? '' : 'Seleccioná una persona' }))}
>
  <option value="">Seleccionar responsable...</option>
  {people?.map((person) => (
    <option key={person.id} value={person.id}>{person.name}</option>
  ))}
</select>
{incomeErrors.selectedPersonId && <span className="fieldError">{incomeErrors.selectedPersonId}</span>}
```

Amount input — remove `required` attribute and add `onBlur`:
```tsx
<input
  type="number"
  className="input"
  placeholder="0.00"
  value={amount}
  onChange={(e) => setAmount(e.target.value)}
  step="0.01"
  min="0"
  onBlur={() => setIncomeErrors(e => ({ ...e, amount: positiveNumber(amount) }))}
/>
{incomeErrors.amount && <span className="fieldError">{incomeErrors.amount}</span>}
```

- [ ] **Step 6: Add `onBlur` and `fieldError` spans in the transfer form JSX**

From person select — remove `required` and add `onBlur`:
```tsx
<select
  className="input"
  value={fromPersonId}
  onChange={(e) => setFromPersonId(e.target.value)}
  onBlur={() => setTransferErrors(e => ({ ...e, fromPersonId: fromPersonId ? '' : 'Seleccioná una persona' }))}
>
  <option value="">Seleccionar origen...</option>
  {people?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
</select>
{transferErrors.fromPersonId && <span className="fieldError">{transferErrors.fromPersonId}</span>}
```

To person select — remove `required` and add `onBlur`:
```tsx
<select
  className="input"
  value={toPersonId}
  onChange={(e) => setToPersonId(e.target.value)}
  onBlur={() => setTransferErrors(e => ({ ...e, toPersonId: toPersonId ? '' : 'Seleccioná una persona' }))}
>
  <option value="">Seleccionar destino...</option>
  {people?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
</select>
{transferErrors.toPersonId && <span className="fieldError">{transferErrors.toPersonId}</span>}
```

Transfer amount input — remove `required` and add `onBlur`:
```tsx
<input
  type="number"
  className="input"
  placeholder="0.00"
  value={transferAmount}
  onChange={(e) => setTransferAmount(e.target.value)}
  step="0.01"
  min="0"
  onBlur={() => setTransferErrors(e => ({ ...e, transferAmount: positiveNumber(transferAmount) }))}
/>
{transferErrors.transferAmount && <span className="fieldError">{transferErrors.transferAmount}</span>}
```

- [ ] **Step 7: Clear errors on success**

In `createIncomeMutation.onSuccess`, add `setIncomeErrors({})`.
In `createTransferMutation.onSuccess`, add `setTransferErrors({})`.

- [ ] **Step 8: Run build**

```bash
cd frontend && npm run build
```

Expected: 0 TypeScript errors.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/budget-page.tsx
git commit -m "feat: inline validation on budget-page — income and transfer forms"
```

---

## Task 6: categories-page

**Files:**
- Modify: `frontend/src/pages/categories-page.tsx`

Single field `name` required. Currently has `if (!newCategory.name.trim()) return` without feedback.

- [ ] **Step 1: Add `nameError` state**

After the existing `useState` declarations, add:

```ts
const [nameError, setNameError] = useState('')
```

- [ ] **Step 2: Update the name input to add `onBlur`**

```tsx
<input
  className="input"
  placeholder="Ej: Supermercado"
  value={newCategory.name}
  onChange={(e) => setNewCategory({ ...newCategory, name: e.target.value })}
  onBlur={() => setNameError(newCategory.name.trim() ? '' : 'Requerido')}
/>
{nameError && <span className="fieldError">{nameError}</span>}
```

- [ ] **Step 3: Update `handleCreate` to set visible error**

```ts
const handleCreate = () => {
  if (!newCategory.name.trim()) {
    setNameError('Requerido')
    return
  }
  setNameError('')
  createMutation.mutate(newCategory)
}
```

- [ ] **Step 4: Clear error on success**

In `createMutation.onSuccess`, add `setNameError('')`.

- [ ] **Step 5: Run build**

```bash
cd frontend && npm run build
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/categories-page.tsx
git commit -m "feat: inline validation on categories-page — name required"
```

---

## Task 7: EditableCell in purchases-page

**Files:**
- Modify: `frontend/src/pages/purchases-page.tsx`

`EditableCell` is used for inline description editing. Currently calls `onSave(draft)` on blur without checking if the value is empty. Add an optional `required` prop that prevents saving empty values and shows a `.fieldError`.

- [ ] **Step 1: Add `required` prop and `error` state to `EditableCell`**

Replace the existing `EditableCell` component interface and state:

```tsx
function EditableCell({
  value,
  placeholder,
  onSave,
  required = false,
}: {
  value: string | null | undefined
  placeholder: string
  onSave: (val: string) => void
  required?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value ?? '')
  const [cellError, setCellError] = useState('')
```

- [ ] **Step 2: Update the editing branch to show error and prevent saving empty**

Replace the editing `return` branch:

```tsx
return (
  <div>
    <input
      type="text"
      className="input"
      style={{ padding: '4px 8px', fontSize: '0.85rem', width: '100%' }}
      value={draft}
      autoFocus
      onChange={(e) => {
        setDraft(e.target.value)
        if (cellError) setCellError('')
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          if (required && !draft.trim()) {
            setCellError('Requerido')
            return
          }
          onSave(draft)
          setEditing(false)
          setCellError('')
        }
        if (e.key === 'Escape') {
          setEditing(false)
          setCellError('')
        }
      }}
      onBlur={() => {
        if (required && !draft.trim()) {
          setCellError('Requerido')
          return
        }
        onSave(draft)
        setEditing(false)
        setCellError('')
      }}
    />
    {cellError && <span className="fieldError">{cellError}</span>}
  </div>
)
```

- [ ] **Step 3: Pass `required` prop where description is used**

Find the `<EditableCell>` call for description in the purchases table and add `required`:

```tsx
<EditableCell
  value={purchase.description}
  placeholder="sin descripción"
  required
  onSave={(val) => updateMutation.mutate({ id: purchase.id, data: { description: val } })}
/>
```

- [ ] **Step 4: Run build**

```bash
cd frontend && npm run build
```

Expected: 0 TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/purchases-page.tsx
git commit -m "feat: inline validation on EditableCell — required prop prevents empty saves"
```

---

## Task 8: Final verification

- [ ] **Step 1: Run full test suite**

```bash
cd frontend && npm run test:run
```

Expected: all tests pass (0 failed).

- [ ] **Step 2: Run TypeScript build**

```bash
cd frontend && npm run build
```

Expected: 0 errors, build succeeds.

- [ ] **Step 3: Run backend tests (regression check)**

```bash
cd /path/to/project && source .venv/bin/activate && cd backend && python -m pytest tests/ -q
```

Expected: all backend tests pass (no regressions — this was a pure frontend change).

- [ ] **Step 4: Mark Fase 2 as complete in `spec/plan-de-accion.md`**

In `spec/plan-de-accion.md`, change:

```markdown
- [ ] Validaciones frontend antes de enviar (ej. tarjeta obligatoria)
```

to:

```markdown
- [x] Validaciones frontend antes de enviar (ej. tarjeta obligatoria)
```

- [ ] **Step 5: Final commit**

```bash
git add spec/plan-de-accion.md
git commit -m "docs: mark frontend validations as complete in roadmap"
```

# Receipt Upload & Nueva Transferencia Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Nueva transferencia" button to the dashboard and a comprobante upload field in PurchaseForm that auto-fills amount, date, and description via Claude Vision API.

**Architecture:** The backend (`POST /api/import/comprobante`) and all API client functions are already in place. This plan is **frontend-only**. Task 1 adds the dashboard button; Task 2 adds the upload section to PurchaseForm.

**Tech Stack:** React 19, TypeScript, @tanstack/react-query, existing CSS design system (`App.css`). No new dependencies.

---

## Context: What's Already Done

The following are **already implemented** — do not re-implement:

- `POST /api/import/comprobante` endpoint in `backend/app/import_api.py` (uses Claude Vision API)
- `ComprobanteExtraction` interface in `frontend/src/api/types.ts`
- `uploadComprobante(file: File)` function in `frontend/src/api/endpoints.ts`
- `createBeneficiary(payload)` function in `frontend/src/api/endpoints.ts`
- Backend tests in `backend/tests/test_comprobante_import.py`

---

## File Map

| File | Action | What changes |
|---|---|---|
| `frontend/src/pages/dashboard-page.tsx` | Modify | Add `showTransferForm` state + "Nueva transferencia" button + conditional PurchaseForm |
| `frontend/src/components/PurchaseForm.tsx` | Modify | Add comprobante upload section at top: file input, spinner, auto-fill, badges, "guardar destinatario" pill |

---

## Task 1: Dashboard "Nueva transferencia" Button

**Files:**
- Modify: `frontend/src/pages/dashboard-page.tsx`

- [ ] **Step 1: Add `showTransferForm` state**

In `dashboard-page.tsx`, locate the existing state declarations (around line 44) and add one new state:

```tsx
const [showAddForm, setShowAddForm] = useState(false)
const [showTransferForm, setShowTransferForm] = useState(false)  // add this line
```

- [ ] **Step 2: Add the button in the controls bar**

Locate the "Nueva compra" button (around line 228–234):

```tsx
<button
  onClick={() => setShowAddForm(!showAddForm)}
  className="button"
  style={{ background: 'var(--color-primary)', color: 'white' }}
>
  {showAddForm ? '✕ Cancelar' : '+ Nueva compra'}
</button>
```

Add a second button **after** it, before the "Exportar Excel" button:

```tsx
<button
  onClick={() => {
    setShowTransferForm(!showTransferForm)
    if (!showTransferForm) setShowAddForm(false)
  }}
  className="button"
  style={{ background: 'var(--color-surface)', color: 'var(--color-primary)', border: '1px solid var(--color-primary)' }}
>
  {showTransferForm ? '✕ Cancelar' : '+ Nueva transferencia'}
</button>
```

Also update the existing "Nueva compra" button click handler to close the transfer form when opening the purchase form:

```tsx
<button
  onClick={() => {
    setShowAddForm(!showAddForm)
    if (!showAddForm) setShowTransferForm(false)
  }}
  className="button"
  style={{ background: 'var(--color-primary)', color: 'white' }}
>
  {showAddForm ? '✕ Cancelar' : '+ Nueva compra'}
</button>
```

- [ ] **Step 3: Add the conditional PurchaseForm for transfers**

Locate the existing `{showAddForm && ...}` block (around line 248–256) and add a second block immediately after it:

```tsx
{showTransferForm && (
  <div className="panel" style={{ border: '1px solid var(--color-primary)', animation: 'fadeIn 0.3s ease' }}>
    <div className="panelTitle">Nueva transferencia</div>
    <PurchaseForm
      initialValues={{ payment_method: 'transfer' }}
      onSuccess={() => setShowTransferForm(false)}
      onCancel={() => setShowTransferForm(false)}
    />
  </div>
)}
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run build
```

Expected: zero TypeScript errors, build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/dashboard-page.tsx
git commit -m "feat(dashboard): add Nueva transferencia button with PurchaseForm"
```

---

## Task 2: PurchaseForm Comprobante Upload Section

This is the main feature. The upload section goes at the **top** of the form (before all other fields).

**Files:**
- Modify: `frontend/src/components/PurchaseForm.tsx`

### Step-by-step

- [ ] **Step 1: Add imports**

At the top of `PurchaseForm.tsx`, add the missing imports:

```tsx
import { uploadComprobante, createBeneficiary } from '../api/endpoints'
import type { ComprobanteExtraction } from '../api/types'
import { Spinner } from './Spinner'
```

The existing imports line is:
```tsx
import {
    fetchCards,
    fetchPeople,
    fetchDebtors,
    fetchCategories,
    createPurchase,
    fetchSuggestMonth,
} from '../api/endpoints'
```

Replace with:
```tsx
import {
    fetchCards,
    fetchPeople,
    fetchDebtors,
    fetchCategories,
    createPurchase,
    fetchSuggestMonth,
    uploadComprobante,
    createBeneficiary,
} from '../api/endpoints'
import type { ComprobanteExtraction } from '../api/types'
import { Spinner } from './Spinner'
```

- [ ] **Step 2: Add comprobante state variables**

Inside `PurchaseForm`, after the existing `useState` declarations (after line 55 — the `errors` state), add:

```tsx
const [parseStatus, setParseStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
const [parseResult, setParseResult] = useState<ComprobanteExtraction | null>(null)
const [autofilled, setAutofilled] = useState<Set<string>>(new Set())
const [saveBeneficiaryStatus, setSaveBeneficiaryStatus] = useState<'idle' | 'saving' | 'saved'>('idle')
const [previewName, setPreviewName] = useState<string | null>(null)
```

- [ ] **Step 3: Add the file change handler**

After the `handleBlur` function (around line 117), add:

```tsx
async function handleComprobanteChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    setPreviewName(file.name)
    setParseStatus('loading')
    setParseResult(null)
    setAutofilled(new Set())
    setSaveBeneficiaryStatus('idle')

    try {
        const result = await uploadComprobante(file)
        setParseResult(result)
        setParseStatus('done')

        const filled = new Set<string>()

        if (result.amount != null) {
            const amtStr = String(result.amount)
            setAmountInputValue(amtStr)
            setFormData(prev => ({ ...prev, amount_original: amtStr }))
            filled.add('amount_original')
        }
        if (result.date) {
            setFormData(prev => ({ ...prev, purchase_date: result.date! }))
            filled.add('purchase_date')
        }
        if (result.currency === 'USD') {
            setFormData(prev => ({ ...prev, currency: 'USD' }))
            filled.add('currency')
        }
        const autoDesc = result.matched_beneficiary?.name ?? result.raw_extracted.nombre ?? result.description
        if (autoDesc) {
            setFormData(prev => ({ ...prev, description: autoDesc }))
            filled.add('description')
        }

        setAutofilled(filled)
    } catch {
        setParseStatus('error')
    }
}
```

- [ ] **Step 4: Add the save beneficiary handler**

After `handleComprobanteChange`, add:

```tsx
async function handleSaveBeneficiary() {
    if (!parseResult) return
    const nombre = parseResult.raw_extracted.nombre
    if (!nombre) return

    setSaveBeneficiaryStatus('saving')
    try {
        await createBeneficiary({
            name: nombre,
            cbu: parseResult.raw_extracted.cbu ?? undefined,
            alias: parseResult.raw_extracted.alias ?? undefined,
            cuit: parseResult.raw_extracted.cuit ?? undefined,
        })
        setSaveBeneficiaryStatus('saved')
    } catch {
        setSaveBeneficiaryStatus('idle')
    }
}
```

- [ ] **Step 5: Add the comprobante section to the JSX**

The upload section goes **before** the `purchase-form-grid` div. Locate:

```tsx
return (
    <form onSubmit={handleSubmit} className="purchase-form">
        <div className="purchase-form-grid">
```

Insert the comprobante section between `<form>` opening and `<div className="purchase-form-grid">`:

```tsx
return (
    <form onSubmit={handleSubmit} className="purchase-form">
        {/* Comprobante upload section */}
        <div style={{ marginBottom: '16px', padding: '12px', background: 'var(--color-bg)', border: '1px dashed var(--color-border)', borderRadius: '8px' }}>
            <label className="label" style={{ display: 'block', marginBottom: '8px' }}>
                Comprobante (opcional)
            </label>
            <input
                type="file"
                accept="image/*,.pdf"
                capture="environment"
                className="input"
                style={{ fontSize: '14px' }}
                onChange={handleComprobanteChange}
                disabled={parseStatus === 'loading'}
            />

            {/* Spinner while parsing */}
            {parseStatus === 'loading' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
                    <Spinner size={16} />
                    <span className="muted" style={{ fontSize: '13px' }}>Leyendo comprobante...</span>
                </div>
            )}

            {/* Preview filename */}
            {parseStatus === 'done' && previewName && (
                <div style={{ marginTop: '6px', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
                    {previewName}
                </div>
            )}

            {/* Error message */}
            {parseStatus === 'error' && (
                <div className="error" style={{ marginTop: '8px', fontSize: '13px' }}>
                    No se pudo leer el comprobante. Completá los campos manualmente.
                </div>
            )}

            {/* "Guardar destinatario" pill */}
            {parseStatus === 'done' &&
                parseResult?.matched_beneficiary === null &&
                parseResult?.raw_extracted.nombre && (
                <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    {saveBeneficiaryStatus === 'saved' ? (
                        <span style={{ fontSize: '13px', color: 'var(--color-primary)', background: 'rgba(192,105,59,0.1)', padding: '4px 10px', borderRadius: '12px' }}>
                            ✓ Guardado como destinatario frecuente
                        </span>
                    ) : (
                        <>
                            <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
                                ¿Guardar <strong>{parseResult.raw_extracted.nombre}</strong> como destinatario frecuente?
                            </span>
                            <button
                                type="button"
                                className="button"
                                style={{ fontSize: '12px', padding: '4px 10px', background: 'var(--color-surface)', color: 'var(--color-primary)', border: '1px solid var(--color-primary)' }}
                                onClick={handleSaveBeneficiary}
                                disabled={saveBeneficiaryStatus === 'saving'}
                            >
                                {saveBeneficiaryStatus === 'saving' ? 'Guardando...' : 'Guardar'}
                            </button>
                        </>
                    )}
                </div>
            )}
        </div>

        <div className="purchase-form-grid">
```

- [ ] **Step 6: Add "auto-completado" badges next to auto-filled fields**

Add a small helper component inline — a badge that only renders when the field was auto-filled. Add this **before** the `return` statement:

```tsx
const AutoBadge = ({ field }: { field: string }) =>
    autofilled.has(field) ? (
        <span style={{ fontSize: '11px', color: 'var(--color-primary)', background: 'rgba(192,105,59,0.12)', padding: '1px 6px', borderRadius: '8px', marginLeft: '6px', verticalAlign: 'middle' }}>
            ✓ auto
        </span>
    ) : null
```

Then add `<AutoBadge field="..." />` next to the relevant field labels:

For the **description** field label:
```tsx
<label className="label">Descripción <AutoBadge field="description" /></label>
```

For the **amount** label area (locate the label for "Monto" and update it):
```tsx
<label className="label" style={{ margin: 0 }}>Monto <AutoBadge field="amount_original" /></label>
```

For the **date** field:
```tsx
<label className="label">Fecha compra <AutoBadge field="purchase_date" /></label>
```

- [ ] **Step 7: Verify TypeScript compiles**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run build
```

Expected: zero TypeScript errors, build succeeds.

- [ ] **Step 8: Run backend tests to confirm no regressions**

```bash
cd /Users/pablo/github/admin-consumos/backend && source ../.venv/bin/activate && python -m pytest tests/ -q
```

Expected: all tests pass, 0 failed.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/PurchaseForm.tsx
git commit -m "feat(purchase-form): add comprobante upload with auto-fill and save beneficiary"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec requirement | Covered by |
|---|---|
| Dashboard "Nueva transferencia" button | Task 1 Step 2 |
| Opens PurchaseForm with `payment_method: 'transfer'` pre-selected | Task 1 Step 3 |
| File input with `capture="environment"` | Task 2 Step 5 |
| Spinner while parsing | Task 2 Step 5 |
| Auto-fill amount, date, description | Task 2 Step 3 |
| Badge "✓ auto-completado" on filled fields | Task 2 Step 6 |
| Use `matched_beneficiary.name` as description if matched | Task 2 Step 3 |
| Show "¿Guardar destinatario?" when unmatched nombre | Task 2 Step 5 |
| "Guardar" button calls POST /api/beneficiaries | Task 2 Step 4 |
| Pill changes to "✓ Guardado" after save | Task 2 Step 5 |
| Error message if parse fails (graceful) | Task 2 Step 5 |
| File not persisted | Backend already returns nothing; frontend discards file reference |
| Both buttons mutually exclusive | Task 1 Step 2 |

### Type Consistency

- `ComprobanteExtraction.amount` (not `amount_original`) — used correctly in `handleComprobanteChange`
- `ComprobanteExtraction.date` (not `purchase_date`) — used correctly
- `ComprobanteExtraction.raw_extracted.nombre` — used for beneficiary pill and description fallback
- `AutoBadge` references `autofilled` Set<string> using field names matching `formData` keys — consistent
- `BeneficiaryCreate` has optional `cbu`, `alias`, `cuit` — matched in `handleSaveBeneficiary`

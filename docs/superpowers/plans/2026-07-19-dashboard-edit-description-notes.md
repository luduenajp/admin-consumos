# Editar Descripción y Detalle desde el Dashboard (Desktop) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user edit a purchase's Descripción and Detalle (notes) directly from the "Resumen del mes" table on the Dashboard, in desktop, by reusing the existing mobile edit sheet.

**Architecture:** Backend: add `description` as an editable field on `PurchaseUpdate` (normalized the same way `create_purchase` normalizes it). Frontend: add a `description` input to the existing `purchaseMobileEditSheet`, wire desktop table rows to open that same sheet (currently only mobile cards do), and relax the CSS that currently hides the sheet outside of the `max-width: 768px` breakpoint.

**Tech Stack:** FastAPI + SQLModel + Pydantic (backend), React 19 + TypeScript + React Query + Vitest/Testing Library (frontend).

## Global Constraints

- Backend tests: `cd backend && source ../.venv/bin/activate && python -m pytest tests/ -q` — must be 0 failed.
- Frontend tests: `cd frontend && npm run test:run` — must be 0 failed.
- Frontend build: `cd frontend && npm run build` — must compile with no TypeScript errors.
- Follow existing patterns: `PurchaseUpdate.model_dump(exclude_unset=True)` + generic `setattr` loop in `crud.py:update_purchase` (backend/app/crud.py:581-591) — do not restructure this function beyond what's needed.
- Do not touch Fondo Común calculation logic (`calculate_transfers`) or any BR-XXX business rule.
- No new CSS framework/class system — reuse `purchaseMobileEditSheet` / `App.css` classes.

---

### Task 1: Backend — allow `description` on `PurchaseUpdate`

**Files:**
- Modify: `backend/app/schemas.py:202-208` (`PurchaseUpdate`)
- Modify: `backend/app/crud.py:581-591` (`update_purchase`)
- Test: `backend/tests/test_api_integration.py` (extend `TestPurchasesEndpoints`)

**Interfaces:**
- Consumes: `app.importers.visa_xlsx.normalize_purchase_description(*, description: str) -> str` (already imported in `crud.py:68`).
- Produces: `PurchaseUpdate.description: Optional[str]` — later consumed by the frontend `PurchaseUpdate` TS type (Task 2) and the PATCH `/api/purchases/{id}` endpoint (unchanged, already generic).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_api_integration.py`, inside `class TestPurchasesEndpoints` (after `test_delete_nonexistent_returns_404`, still inside the class — mind indentation):

```python
    def test_update_description_is_normalized(self, client):
        _, card = self._setup(client)
        created = client.post(
            "/api/purchases",
            json={
                "card_id": card["id"],
                "purchase_date": "2025-01-15",
                "description": "Original",
                "currency": "ARS",
                "amount_original": 1000,
            },
        ).json()
        r = client.patch(f"/api/purchases/{created['id']}", json={"description": "  Nueva Descripcion  "})
        assert r.status_code == 200
        assert r.json()["description"] == "nueva descripcion"

    def test_update_description_empty_string_rejected(self, client):
        _, card = self._setup(client)
        created = client.post(
            "/api/purchases",
            json={
                "card_id": card["id"],
                "purchase_date": "2025-01-15",
                "description": "Original",
                "currency": "ARS",
                "amount_original": 1000,
            },
        ).json()
        r = client.patch(f"/api/purchases/{created['id']}", json={"description": ""})
        assert r.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source ../.venv/bin/activate && python -m pytest tests/test_api_integration.py -k test_update_description -v`
Expected: both tests FAIL — `test_update_description_is_normalized` fails because `description` is dropped (not a declared field on `PurchaseUpdate`, so it stays "original" from creation... actually creation normalizes "Original" -> "original", and PATCH silently ignores the unknown field since Pydantic ignores extra fields by default, so the assert on `"nueva descripcion"` fails); `test_update_description_empty_string_rejected` fails because there's no validation yet (PATCH is silently ignored, status is 200, not 422).

- [ ] **Step 3: Add `description` to `PurchaseUpdate` schema**

In `backend/app/schemas.py`, replace:

```python
class PurchaseUpdate(BaseModel):
    notes: Optional[str] = None
    category: Optional[str] = None
    is_common: Optional[bool] = None
    debtor_id: Optional[int] = None
    beneficiary_person_id: Optional[int] = None
    debt_settled: Optional[bool] = None
```

with:

```python
class PurchaseUpdate(BaseModel):
    description: Optional[str] = Field(default=None, min_length=1)
    notes: Optional[str] = None
    category: Optional[str] = None
    is_common: Optional[bool] = None
    debtor_id: Optional[int] = None
    beneficiary_person_id: Optional[int] = None
    debt_settled: Optional[bool] = None
```

(`Field` is already imported at the top of `schemas.py` — see `from pydantic import BaseModel, Field, model_validator`.)

- [ ] **Step 4: Normalize `description` in `update_purchase`**

In `backend/app/crud.py`, replace:

```python
def update_purchase(*, session: Session, purchase_id: int, payload: PurchaseUpdate) -> Purchase:
    """Update editable fields of an existing purchase (notes, category)."""
    purchase = session.get(Purchase, purchase_id)
    if purchase is None:
        raise ValueError(f"Purchase {purchase_id} not found")
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(purchase, field, value)
    session.commit()
    session.refresh(purchase)
    return purchase
```

with:

```python
def update_purchase(*, session: Session, purchase_id: int, payload: PurchaseUpdate) -> Purchase:
    """Update editable fields of an existing purchase (notes, category, description)."""
    purchase = session.get(Purchase, purchase_id)
    if purchase is None:
        raise ValueError(f"Purchase {purchase_id} not found")
    update_data = payload.model_dump(exclude_unset=True)
    if "description" in update_data:
        update_data["description"] = normalize_purchase_description(description=update_data["description"])
    for field, value in update_data.items():
        setattr(purchase, field, value)
    session.commit()
    session.refresh(purchase)
    return purchase
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && source ../.venv/bin/activate && python -m pytest tests/test_api_integration.py -k test_update_description -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend && source ../.venv/bin/activate && python -m pytest tests/ -q`
Expected: all tests pass, 0 failed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas.py backend/app/crud.py backend/tests/test_api_integration.py
git commit -m "feat(api): allow editing purchase description via PATCH"
```

---

### Task 2: Frontend — add `description` to the `PurchaseUpdate` TS type

**Files:**
- Modify: `frontend/src/api/types.ts:181-188`

**Interfaces:**
- Consumes: nothing new.
- Produces: `PurchaseUpdate.description?: string | null` — consumed by `patchMutation.mutate({ id, payload: { description } })` in Task 3.

- [ ] **Step 1: Update the type**

In `frontend/src/api/types.ts`, replace:

```typescript
export interface PurchaseUpdate {
  notes?: string | null
  category?: string | null
  is_common?: boolean
  debtor_id?: number | null
  beneficiary_person_id?: number | null
  debt_settled?: boolean
}
```

with:

```typescript
export interface PurchaseUpdate {
  description?: string
  notes?: string | null
  category?: string | null
  is_common?: boolean
  debtor_id?: number | null
  beneficiary_person_id?: number | null
  debt_settled?: boolean
}
```

(`description` is typed as plain `string`, not `string | null`, because the backend rejects empty/`None` — matching the `min_length=1` constraint added in Task 1.)

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors (this is a type-only additive change, nothing consumes it yet).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/types.ts
git commit -m "feat(types): add description to PurchaseUpdate"
```

---

### Task 3: Frontend — add Descripción field to the edit sheet

**Files:**
- Modify: `frontend/src/pages/dashboard-page.tsx`

**Interfaces:**
- Consumes: `PurchaseUpdate.description` (Task 2), `patchMutation` (already defined at `dashboard-page.tsx:135-143`), `MonthBreakdownRow.description: string` (already exists, `frontend/src/api/types.ts:70`).
- Produces: new state `mobileEditDescription: string`, setter `setMobileEditDescription` — consumed by Task 4 (desktop row `onClick`).

- [ ] **Step 1: Add the state**

In `frontend/src/pages/dashboard-page.tsx`, next to the existing `mobileEditNotes` state (around line 55), replace:

```typescript
  const [mobileEditId, setMobileEditId] = useState<number | null>(null)
  const [mobileEditNotes, setMobileEditNotes] = useState('')
```

with:

```typescript
  const [mobileEditId, setMobileEditId] = useState<number | null>(null)
  const [mobileEditNotes, setMobileEditNotes] = useState('')
  const [mobileEditDescription, setMobileEditDescription] = useState('')
```

- [ ] **Step 2: Seed it wherever the sheet is opened from mobile cards**

Around line 407-410, replace:

```typescript
                    onClick={() => { setMobileEditId(row.purchase_id); setMobileEditNotes(row.notes ?? '') }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { setMobileEditId(row.purchase_id); setMobileEditNotes(row.notes ?? '') } }}
```

with:

```typescript
                    onClick={() => { setMobileEditId(row.purchase_id); setMobileEditNotes(row.notes ?? ''); setMobileEditDescription(row.description) }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { setMobileEditId(row.purchase_id); setMobileEditNotes(row.notes ?? ''); setMobileEditDescription(row.description) } }}
```

- [ ] **Step 3: Add the input to the sheet body**

Around lines 465-478 (`purchaseMobileEditBody`, right before the "Categoría" `formRow`), replace:

```typescript
              <div className="purchaseMobileEditBody">
                <div className="formRow">
                  <label className="label">Categoría</label>
```

with:

```typescript
              <div className="purchaseMobileEditBody">
                <div className="formRow">
                  <label className="label">Descripción</label>
                  <input
                    type="text"
                    className="input"
                    value={mobileEditDescription}
                    placeholder="Descripción de la compra..."
                    onChange={(e) => setMobileEditDescription(e.target.value)}
                    onBlur={() => {
                      const trimmed = mobileEditDescription.trim()
                      if (trimmed && trimmed !== editRow.description) {
                        patchMutation.mutate({ id: editRow.purchase_id, payload: { description: trimmed } })
                      }
                    }}
                  />
                </div>
                <div className="formRow">
                  <label className="label">Categoría</label>
```

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/dashboard-page.tsx
git commit -m "feat(dashboard): add description field to purchase edit sheet"
```

---

### Task 4: Frontend — open the sheet from desktop table rows

**Files:**
- Modify: `frontend/src/pages/dashboard-page.tsx`

**Interfaces:**
- Consumes: `setMobileEditId`, `setMobileEditNotes`, `setMobileEditDescription` (Task 3).
- Produces: nothing new for later tasks.

- [ ] **Step 1: Add onClick to the desktop table row**

Around line 656-658 (inside the `.map((row) => ( ... ))` for the "Resumen del mes" desktop table), replace:

```typescript
                        .map((row) => (
                          <tr key={`${row.purchase_id}-${row.installment_index}`}>
                            <td>{row.purchase_date}</td>
```

with:

```typescript
                        .map((row) => (
                          <tr
                            key={`${row.purchase_id}-${row.installment_index}`}
                            onClick={() => {
                              setMobileEditId(row.purchase_id)
                              setMobileEditNotes(row.notes ?? '')
                              setMobileEditDescription(row.description)
                            }}
                            style={{ cursor: 'pointer' }}
                          >
                            <td>{row.purchase_date}</td>
```

This only wires the click — the tooltip on the Descripción cell (lines 660-716) is a pure CSS hover effect (`.tooltip-container:hover .tooltip-content`), it doesn't capture clicks or call `stopPropagation`, so clicking anywhere in the row (including over the tooltip trigger) still bubbles up and opens the sheet.

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/dashboard-page.tsx
git commit -m "feat(dashboard): open purchase edit sheet from desktop table rows"
```

---

### Task 5: CSS — make the edit sheet usable outside the mobile breakpoint

**Files:**
- Modify: `frontend/src/App.css:790-820`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing (leaf change).

- [ ] **Step 1: Remove the mobile-only gate on the overlay**

In `frontend/src/App.css`, replace:

```css
.purchaseMobileEditOverlay {
  display: none;
}

@media (max-width: 768px) {
  .purchaseMobileEditOverlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.5);
    z-index: 2000;
    animation: overlayFadeIn 0.2s ease;
  }
}

.purchaseMobileEditSheet {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--color-surface);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.15);
  max-height: 80vh;
  overflow-y: auto;
  animation: sheetSlideUp 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
```

with:

```css
.purchaseMobileEditOverlay {
  display: flex;
  align-items: center;
  justify-content: center;
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  z-index: 2000;
  animation: overlayFadeIn 0.2s ease;
}

.purchaseMobileEditSheet {
  position: relative;
  width: 100%;
  max-width: 480px;
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.15);
  max-height: 80vh;
  overflow-y: auto;
  animation: sheetFadeIn 0.2s ease;
}

@media (max-width: 768px) {
  .purchaseMobileEditOverlay {
    align-items: flex-end;
    justify-content: stretch;
  }

  .purchaseMobileEditSheet {
    max-width: none;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    animation: sheetSlideUp 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }
}
```

This keeps the exact mobile look (bottom sheet sliding up, full width) via the `max-width: 768px` override, while giving desktop a centered modal-style dialog instead of `display: none`.

- [ ] **Step 2: Add the new `sheetFadeIn` keyframe**

Directly below the existing `@keyframes sheetSlideUp` block (around line 822-825 in the original file), add:

```css
@keyframes sheetFadeIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
```

- [ ] **Step 3: Manual visual check**

Run: `cd frontend && npm run dev`, open `http://localhost:5173` in a desktop-width browser window, click a row in "Resumen del mes", confirm the sheet appears centered with a dimmed backdrop, and resize below 768px to confirm the mobile bottom-sheet look is unchanged.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.css
git commit -m "style(dashboard): show purchase edit sheet as centered modal on desktop"
```

---

### Task 6: Frontend — test the desktop edit flow

**Files:**
- Test: `frontend/src/pages/dashboard-page.test.tsx` (new)

**Interfaces:**
- Consumes: `DashboardPage` (default export shape: named export `DashboardPage` from `frontend/src/pages/dashboard-page.tsx`), all functions exported from `frontend/src/api/endpoints.ts` (mocked wholesale), `MonthBreakdownRow` / `MonthBreakdownResponse` types from `frontend/src/api/types.ts`.
- Produces: nothing (leaf test).

- [ ] **Step 1: Write the test file**

Create `frontend/src/pages/dashboard-page.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import '@testing-library/jest-dom'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DashboardPage } from './dashboard-page'
import { updatePurchase } from '../api/endpoints'
import type { MonthBreakdownResponse } from '../api/types'

const breakdown: MonthBreakdownResponse = {
  year_month: '2026-07',
  total_ars: 15000,
  items: [
    {
      purchase_id: 1,
      purchase_date: '2026-07-05',
      description: 'super chino',
      notes: 'compra semanal',
      category: 'Supermercado',
      payer_name: 'Pablo',
      payment_method: 'card',
      card_name: 'Visa',
      installment_index: 1,
      installments_total: 1,
      amount_ars: 15000,
      amount_original: 15000,
      currency: 'ARS',
      debtor_id: null,
      debtor_name: null,
      beneficiary_person_id: null,
      debt_settled: false,
      is_common: false,
    },
  ],
}

vi.mock('../api/endpoints', () => ({
  fetchPeople: vi.fn().mockResolvedValue([]),
  fetchCards: vi.fn().mockResolvedValue([]),
  fetchMonthBreakdown: vi.fn().mockResolvedValue(breakdown),
  fetchTimeline: vi.fn().mockResolvedValue([]),
  fetchDebtReport: vi.fn().mockResolvedValue([]),
  updatePurchase: vi.fn().mockResolvedValue({}),
  deletePurchase: vi.fn(),
  fetchCategories: vi.fn().mockResolvedValue([]),
  fetchCategorySpending: vi.fn().mockResolvedValue([]),
  fetchBudgets: vi.fn().mockResolvedValue([]),
  fetchServicePaymentSummary: vi.fn().mockResolvedValue({ unpaid_count: 0, overdue_names: [], due_soon_names: [] }),
  fetchMonthlyBalance: vi.fn().mockResolvedValue(null),
  fetchTransferCalculation: vi.fn().mockResolvedValue(null),
  fetchRecurringExpenses: vi.fn().mockResolvedValue([]),
  fetchMonthlyReport: vi.fn().mockResolvedValue([]),
}))

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DashboardPage — editar desde la tabla de escritorio', () => {
  beforeEach(() => {
    vi.mocked(updatePurchase).mockClear()
  })

  it('abre el sheet de edición al clickear una fila de la tabla de escritorio y persiste la descripción editada', async () => {
    const user = userEvent.setup()
    renderDashboard()

    const rows = await screen.findAllByText('super chino')
    // La tabla de escritorio muestra la descripción dentro de un tooltip-container;
    // clickeamos el <tr> ascendiendo desde el texto encontrado en esa tabla.
    const tableRow = rows[rows.length - 1].closest('tr')
    expect(tableRow).not.toBeNull()
    await user.click(tableRow as HTMLElement)

    const descriptionInput = await screen.findByDisplayValue('super chino')
    await user.clear(descriptionInput)
    await user.type(descriptionInput, 'super nuevo')
    await user.tab()

    await waitFor(() => {
      expect(updatePurchase).toHaveBeenCalledWith(1, { description: 'super nuevo' })
    })
  })

  it('no llama a updatePurchase si la descripción no cambió', async () => {
    const user = userEvent.setup()
    renderDashboard()

    const rows = await screen.findAllByText('super chino')
    const tableRow = rows[rows.length - 1].closest('tr')
    await user.click(tableRow as HTMLElement)

    const descriptionInput = await screen.findByDisplayValue('super chino')
    await user.click(descriptionInput)
    await user.tab()

    await new Promise((r) => setTimeout(r, 50))
    expect(updatePurchase).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run it and expect the first pass/fail signal**

Run: `cd frontend && npx vitest run src/pages/dashboard-page.test.tsx`
Expected before Tasks 3-4 are applied: FAIL (no description input to find / row click doesn't open the sheet). Since Tasks 3-4 are already implemented by this point in the plan, this step instead confirms the happy path: PASS. If it fails, re-check that `findAllByText('super chino')[rows.length - 1]` is indeed resolving to the desktop table row and not the "Top 5 Gastos" list or the mobile card list — all three render the same description text in this test's DOM (jsdom doesn't apply the `dashboard-desktop-only` / `@media` CSS that would normally hide the mobile list), so the test intentionally picks the *last* match, which is the "Resumen del mes" desktop table (rendered after Top 5 and after the mobile card list in source order — see `dashboard-page.tsx` structure: mobile card list ~line 402, desktop table ~line 656).

- [ ] **Step 3: Run full frontend suite**

Run: `cd frontend && npm run test:run`
Expected: all tests pass, 0 failed.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/dashboard-page.test.tsx
git commit -m "test(dashboard): cover desktop description edit flow"
```

---

### Task 7: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Backend suite**

Run: `cd backend && source ../.venv/bin/activate && python -m pytest tests/ -q`
Expected: 0 failed.

- [ ] **Step 2: Frontend suite**

Run: `cd frontend && npm run test:run`
Expected: 0 failed.

- [ ] **Step 3: Frontend build**

Run: `cd frontend && npm run build`
Expected: TypeScript + Vite build succeeds with no errors.

- [ ] **Step 4: Manual smoke test**

Run: `./start.sh`, open `http://localhost:5173` in a desktop-width window, go to Dashboard, click a row in "Resumen del mes", edit both Descripción and Detalle, blur each field, reload the page, and confirm both edits persisted.

- [ ] **Step 5: Update SPEC.md**

Per `CLAUDE.md`, after implementing a feature that touches purchase editing, add an entry to `SPEC.md` documenting that `PurchaseUpdate` now accepts `description` (normalized like on creation, `min_length=1`) and that the Dashboard's "Resumen del mes" table supports editing Descripción/Detalle from desktop via the same sheet used on mobile. Follow the existing UC-XXX/BR-XXX numbering — read the current end of the relevant section in `SPEC.md` first to pick the next free number.

- [ ] **Step 6: Commit**

```bash
git add SPEC.md
git commit -m "docs: update SPEC.md for editable purchase description on dashboard"
```

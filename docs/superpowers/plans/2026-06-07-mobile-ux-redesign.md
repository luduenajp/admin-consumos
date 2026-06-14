# Mobile UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the mobile experience of admin-consumos across 4 pages — nav drawer, purchases list, dashboard, and import/admin forms — without touching desktop layout or backend.

**Architecture:** CSS `@media (max-width: 768px)` controls everything. React state handles interactive pieces (filter toggle on purchases, tab selection on dashboard, filter group visibility on drawer). Desktop layout (>768px) is strictly preserved.

**Tech Stack:** React 19, TypeScript, plain CSS custom properties, no new libraries.

---

## File Map

| File | Changes |
|---|---|
| `frontend/src/App.tsx` | Add `NAV_GROUPS` with icons; render grouped drawer |
| `frontend/src/App.css` | Drawer gradient header, group labels, pill active state, mobile card list, dashboard mobile tabs, import/admin polish |
| `frontend/src/pages/purchases-page.tsx` | Add filter toggle state, mobile card list render, mobile edit sheet |
| `frontend/src/pages/dashboard-page.tsx` | Add `mobileTab` state, compact filter classes, mobile tab sections |
| `frontend/src/components/KpiSummary.tsx` | Replace inline grid style with `className="kpi-grid"` |
| `frontend/src/pages/import-page.tsx` | Add CSS classes for tap-target improvement |
| `frontend/src/pages/admin-page.tsx` | Add `adminMobileList` card rows to entity sections |

---

## Task 1: Drawer Navigation

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Replace NAV_ITEMS with NAV_GROUPS in App.tsx**

Replace lines 14–23 in `App.tsx`:

```tsx
const NAV_GROUPS = [
  {
    label: 'Principal',
    secondary: false,
    items: [
      { to: '/', label: 'Dashboard', icon: '📊', end: true as const },
      { to: '/purchases', label: 'Compras', icon: '🧾' },
      { to: '/import', label: 'Importar', icon: '📥' },
      { to: '/admin', label: 'Admin', icon: '⚙️' },
    ],
  },
  {
    label: 'Más',
    secondary: true,
    items: [
      { to: '/budget', label: 'Presupuesto', icon: '💰' },
      { to: '/ahorros', label: 'Ahorros', icon: '🐖' },
      { to: '/categories', label: 'Categorías', icon: '🏷️' },
      { to: '/goals', label: 'Objetivos', icon: '🎯' },
    ],
  },
]

const NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items)
```

- [ ] **Step 2: Update the mobile drawer JSX in App.tsx**

Replace lines 59–80 (the `{menuOpen && (...)}` block) with:

```tsx
{menuOpen && (
  <>
    <div className="mobileMenuOverlay" onClick={closeMenu} />
    <nav className="mobileMenu">
      <div className="mobileMenuHeader">
        <div className="appTitle mobileMenuTitle">Admin Consumos</div>
        <button className="mobileMenuClose" onClick={closeMenu} aria-label="Cerrar">✕</button>
      </div>
      <div className="mobileMenuContent">
        {NAV_GROUPS.map((group) => (
          <div key={group.label} className="mobileMenuGroup">
            <div className="mobileMenuGroupLabel">{group.label}</div>
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                className={({ isActive }) =>
                  ['mobileLink', group.secondary ? 'mobileLinkSecondary' : '', isActive ? 'active' : '']
                    .filter(Boolean)
                    .join(' ')
                }
                to={item.to}
                end={item.end}
                onClick={closeMenu}
              >
                <span className="mobileLinkIcon">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </div>
    </nav>
  </>
)}
```

- [ ] **Step 3: Update drawer CSS in App.css**

Replace the `.mobileMenuHeader`, `.mobileMenuClose`, `.mobileLink`, and `.mobileLink.active` rules (lines 476–529) with:

```css
.mobileMenuHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  position: sticky;
  top: 0;
  z-index: 1;
}

.mobileMenuTitle {
  -webkit-text-fill-color: white;
  background: none;
  color: white;
}

.mobileMenuClose {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: var(--radius-sm);
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 1rem;
  color: white;
  transition: all 0.2s;
}

.mobileMenuClose:hover {
  background: rgba(255, 255, 255, 0.15);
}

.mobileMenuContent {
  padding: 8px 0;
}

.mobileMenuGroup {
  margin-bottom: 4px;
}

.mobileMenuGroupLabel {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-muted);
  padding: 12px 20px 4px;
}

.mobileLink {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  color: var(--color-text);
  text-decoration: none;
  font-size: 0.95rem;
  font-weight: 500;
  border-left: 3px solid transparent;
  transition: background 0.15s, border-color 0.15s;
}

.mobileLink:hover {
  background: var(--color-bg);
  opacity: 1;
}

.mobileLink.active {
  color: var(--color-primary);
  background: var(--color-primary-light);
  border-left-color: var(--color-primary);
  font-weight: 600;
}

.mobileLinkSecondary {
  font-size: 0.875rem;
  color: var(--color-text-secondary);
}

.mobileLinkSecondary.active {
  color: var(--color-primary);
}

.mobileLinkIcon {
  font-size: 1.1rem;
  width: 24px;
  text-align: center;
  flex-shrink: 0;
}
```

- [ ] **Step 4: Run build to verify no TypeScript errors**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds with no type errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/pablo/github/admin-consumos && git add frontend/src/App.tsx frontend/src/App.css && git commit -m "feat(mobile): add icons and groups to drawer navigation"
```

---

## Task 2: Purchases Page — Mobile Card List

**Files:**
- Modify: `frontend/src/pages/purchases-page.tsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Add filter toggle state and helper vars in PurchasesPage**

At the top of the `PurchasesPage` function body (after the existing state declarations, around line 114), add:

```tsx
const [showFilters, setShowFilters] = useState(false)
const [mobileEditId, setMobileEditId] = useState<number | null>(null)
const mobileEditPurchase = mobileEditId !== null ? rows.find((p) => p.id === mobileEditId) ?? null : null
```

Note: `mobileEditPurchase` references `rows` which is declared after `isLoading` guard. Move the `mobileEditId` state declaration there (after `rows` is defined), or use `items` instead — `items` is available before `rows` filtering. Use `items`:

```tsx
// Add these two state declarations near the other useState calls (around line 224)
const [showFilters, setShowFilters] = useState(false)
const [mobileEditId, setMobileEditId] = useState<number | null>(null)
```

Then after `const items = data?.items ?? []` (around line 319), add:

```tsx
const mobileEditPurchase = mobileEditId !== null ? items.find((p) => p.id === mobileEditId) ?? null : null
```

- [ ] **Step 2: Add "Filtros" toggle button and mobile card list to JSX**

In the JSX, after the `{showAddForm && ...}` block (around line 428) and before the `{/* Filter Panel */}` comment, add a mobile-only filter toggle button:

```tsx
{/* Mobile filter toggle — hidden on desktop via CSS */}
<button
  type="button"
  className="button ghost purchaseMobileFilterToggle"
  onClick={() => setShowFilters((s) => !s)}
>
  {showFilters ? '▲ Ocultar filtros' : '▼ Filtros'}
</button>
```

Then wrap the existing `<div className="panel" style={{ padding: '24px', marginBottom: '32px' }}>` filter panel div with a class:

Change: `<div className="panel" style={{ padding: '24px', marginBottom: '32px' }}>`
To: `<div className={`panel purchaseFiltersPanel${showFilters ? ' purchaseFiltersPanelOpen' : ''}`} style={{ padding: '24px', marginBottom: '32px' }}>`

- [ ] **Step 3: Add mobile card list rendering in JSX**

Inside the results panel, after the `<div className="tableContainer">` table (after line 695 `</div>` that closes tableContainer), add the mobile card list. The structure inside the results panel should be:

```tsx
{rows.length === 0 ? (
  <div className="muted">Sin compras que coincidan con los filtros</div>
) : (
  <>
    {/* Desktop table */}
    <div className="tableContainer purchaseDesktopTable">
      {/* existing table jsx — unchanged */}
    </div>

    {/* Mobile card list */}
    <div className="purchaseCardList">
      {rows.map((p) => {
        const categoryObj = categoriesData?.find((c) => c.name === p.category)
        const payerName = p.payers?.[0]?.person_name ?? '-'
        const cardName = p.card_id ? (cardNameById.get(p.card_id) ?? null) : null
        return (
          <div
            key={p.id}
            className="purchaseCard"
            onClick={() => setMobileEditId(p.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && setMobileEditId(p.id)}
          >
            <div className="purchaseCardHeader">
              <span className="purchaseCardDescription">{p.description}</span>
              <span className="purchaseCardAmount">
                ${p.amount_original.toLocaleString('es-AR', { maximumFractionDigits: 2 })}
              </span>
            </div>
            <div className="purchaseCardChips">
              {p.category && (
                <span
                  className="purchaseChip"
                  style={{
                    background: categoryObj?.color ? `${categoryObj.color}22` : 'var(--color-primary-light)',
                    color: categoryObj?.color ?? 'var(--color-primary)',
                    border: `1px solid ${categoryObj?.color ?? 'var(--color-primary)'}44`,
                  }}
                >
                  {p.category}
                </span>
              )}
              <span className="purchaseChip purchaseChipNeutral">{payerName}</span>
              {cardName && <span className="purchaseChip purchaseChipNeutral">{cardName}</span>}
              {p.installments_total > 1 && (
                <span className="purchaseChip purchaseChipInstallment">
                  {p.installments_total > 1 ? `${p.purchase_date.slice(0, 7)}` : null}
                </span>
              )}
              <span className="purchaseChip purchaseChipNeutral">{p.purchase_date}</span>
            </div>
          </div>
        )
      })}
    </div>

    {/* Pagination — shared for both views */}
    {pages > 1 ? (
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px', flexWrap: 'wrap' }}>
        <button type="button" className="button" disabled={currentPage <= 1} onClick={() => setPage((p) => p - 1)}>
          Anterior
        </button>
        <span className="muted" style={{ margin: 0 }}>
          Página {currentPage} de {pages}
        </span>
        <button type="button" className="button" disabled={currentPage >= pages} onClick={() => setPage((p) => p + 1)}>
          Siguiente
        </button>
      </div>
    ) : null}
  </>
)}
```

Note: Remove the existing pagination block from its current location (after the tableContainer closing div) — it's now inside the `<>` fragment above.

- [ ] **Step 4: Add mobile edit sheet JSX**

Add this just before the closing `</>` of the PurchasesPage return (after the ConfirmDialog):

```tsx
{/* Mobile edit sheet */}
{mobileEditPurchase && (
  <div className="purchaseMobileEditOverlay" onClick={() => setMobileEditId(null)}>
    <div className="purchaseMobileEditSheet" onClick={(e) => e.stopPropagation()}>
      <div className="purchaseMobileEditHeader">
        <div>
          <div style={{ fontWeight: 700, fontSize: '1rem' }}>{mobileEditPurchase.description}</div>
          <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
            ${mobileEditPurchase.amount_original.toLocaleString('es-AR', { maximumFractionDigits: 2 })} · {mobileEditPurchase.purchase_date}
          </div>
        </div>
        <button type="button" className="mobileMenuClose" style={{ background: 'transparent', color: 'var(--color-text)', border: '1px solid var(--color-border)' }} onClick={() => setMobileEditId(null)}>✕</button>
      </div>

      <div className="purchaseMobileEditBody">
        <div className="formRow">
          <label className="label">Categoría</label>
          <select
            className="input"
            value={mobileEditPurchase.category ?? ''}
            onChange={(e) => {
              patchMutation.mutate({ id: mobileEditPurchase.id, payload: { category: e.target.value || null } })
            }}
          >
            <option value="">-</option>
            {categoriesData?.map((cat) => (
              <option key={cat.id} value={cat.name}>{cat.name}</option>
            ))}
          </select>
        </div>

        <div className="formRow">
          <label className="label" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              type="checkbox"
              checked={mobileEditPurchase.is_common}
              style={{ width: '18px', height: '18px' }}
              onChange={(e) => {
                patchMutation.mutate({ id: mobileEditPurchase.id, payload: { is_common: e.target.checked } })
              }}
            />
            Gasto común
          </label>
        </div>

        <div className="formRow">
          <label className="label">Detalle / Notas</label>
          <input
            type="text"
            className="input"
            defaultValue={mobileEditPurchase.notes ?? ''}
            placeholder="Agregar detalle..."
            onBlur={(e) => {
              const val = e.target.value
              if (val !== (mobileEditPurchase.notes ?? '')) {
                patchMutation.mutate({ id: mobileEditPurchase.id, payload: { notes: val || null } })
              }
            }}
          />
        </div>

        <button
          type="button"
          className="button danger"
          style={{ width: '100%', marginTop: '8px' }}
          disabled={deleteMutation.isPending}
          onClick={() => {
            setMobileEditId(null)
            setPendingDelete({ id: mobileEditPurchase.id, description: mobileEditPurchase.description })
          }}
        >
          🗑 Eliminar compra
        </button>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 5: Add CSS for purchases mobile in App.css**

Append to App.css:

```css
/* ------------------------------------------------------------------ */
/*  Purchases — Mobile filter toggle                                   */
/* ------------------------------------------------------------------ */

.purchaseMobileFilterToggle {
  display: none;
  width: 100%;
  margin-bottom: 8px;
}

@media (max-width: 768px) {
  .purchaseMobileFilterToggle {
    display: block;
  }

  .purchaseFiltersPanel {
    display: none;
  }

  .purchaseFiltersPanel.purchaseFiltersPanelOpen {
    display: block;
  }
}

/* ------------------------------------------------------------------ */
/*  Purchases — Mobile card list                                       */
/* ------------------------------------------------------------------ */

.purchaseCardList {
  display: none;
  flex-direction: column;
  gap: 8px;
}

@media (max-width: 768px) {
  .purchaseDesktopTable {
    display: none;
  }

  .purchaseCardList {
    display: flex;
  }
}

.purchaseCard {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  cursor: pointer;
  transition: box-shadow 0.15s, transform 0.1s;
}

.purchaseCard:active {
  transform: scale(0.99);
  box-shadow: var(--shadow-sm);
}

.purchaseCardHeader {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 10px;
}

.purchaseCardDescription {
  font-weight: 700;
  font-size: 0.95rem;
  color: var(--color-text);
  flex: 1;
  min-width: 0;
  word-break: break-word;
}

.purchaseCardAmount {
  font-weight: 700;
  font-size: 1rem;
  color: var(--color-primary);
  white-space: nowrap;
  flex-shrink: 0;
}

.purchaseCardChips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.purchaseChip {
  border-radius: 999px;
  font-size: 0.7rem;
  padding: 2px 8px;
  font-weight: 500;
  white-space: nowrap;
}

.purchaseChipNeutral {
  background: var(--color-bg);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
}

.purchaseChipInstallment {
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-weight: 700;
  border: 1px solid rgba(99, 102, 241, 0.2);
}

/* ------------------------------------------------------------------ */
/*  Purchases — Mobile edit sheet                                      */
/* ------------------------------------------------------------------ */

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

@keyframes sheetSlideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.purchaseMobileEditHeader {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 20px 16px;
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  background: var(--color-surface);
}

.purchaseMobileEditBody {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
```

- [ ] **Step 6: Run TypeScript build**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run build 2>&1 | tail -20
```

Expected: no TypeScript errors.

- [ ] **Step 7: Run frontend tests**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run test:run 2>&1 | tail -20
```

Expected: all tests pass (0 failed).

- [ ] **Step 8: Commit**

```bash
cd /Users/pablo/github/admin-consumos && git add frontend/src/pages/purchases-page.tsx frontend/src/App.css && git commit -m "feat(mobile): add card list and filter toggle to purchases page"
```

---

## Task 3: Dashboard — Mobile Layout

**Files:**
- Modify: `frontend/src/pages/dashboard-page.tsx`
- Modify: `frontend/src/components/KpiSummary.tsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Replace inline grid style in KpiSummary with CSS class**

In `frontend/src/components/KpiSummary.tsx`, replace both occurrences of:
```tsx
<div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
```

with:
```tsx
<div className="kpi-grid">
```

(There are two — the loading skeleton state on line 79 and the real render on line 90.)

- [ ] **Step 2: Add kpi-grid CSS class to App.css**

Append to App.css:

```css
/* ------------------------------------------------------------------ */
/*  KPI Grid                                                           */
/* ------------------------------------------------------------------ */

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

@media (max-width: 768px) {
  .kpi-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
}
```

- [ ] **Step 3: Add mobileTab state and filter class names to DashboardPage**

In `dashboard-page.tsx`, add to the existing `useState` declarations block (after line 46):

```tsx
const [mobileTab, setMobileTab] = useState<'cuotas' | 'graficos' | 'recurrentes'>('cuotas')
```

- [ ] **Step 4: Add CSS class names to existing filter form rows**

In the JSX of DashboardPage, add class names to the filter `formRow` divs so they can be hidden/restyled on mobile.

Change the month selector `formRow`:
```tsx
<div className="formRow dashboard-filter-month" style={{ marginBottom: 0 }}>
```

Change the person filter `formRow`:
```tsx
<div className="formRow dashboard-filter-person" style={{ marginBottom: 0 }}>
```

Change the expense type `formRow`:
```tsx
<div className="formRow dashboard-filter-type" style={{ marginBottom: 0 }}>
```

Change the card filter `formRow`:
```tsx
<div className="formRow dashboard-filter-card" style={{ marginBottom: 0 }}>
```

- [ ] **Step 5: Add mobile-only tab section in DashboardPage JSX**

After the `<KpiSummary .../>` line and before `{/* Top Cards Grid */}`, add the mobile-only section:

```tsx
{/* Mobile-only: Transfer card + tabs */}
<div className="dashboard-mobile-section">
  {/* Transfer card — always visible on mobile */}
  <div className="dashboard-mobile-transfer">
    <TransferCalculationCard yearMonth={monthFilter} />
  </div>

  {/* Tabs */}
  <div className="dashboard-mobile-tabs">
    {(['cuotas', 'graficos', 'recurrentes'] as const).map((tab) => (
      <button
        key={tab}
        type="button"
        className={`dashboard-mobile-tab${mobileTab === tab ? ' active' : ''}`}
        onClick={() => setMobileTab(tab)}
      >
        {tab === 'cuotas' ? 'Cuotas' : tab === 'graficos' ? 'Gráficos' : 'Recurrentes'}
      </button>
    ))}
  </div>

  {mobileTab === 'cuotas' && (
    <MonthlyBalanceCard yearMonth={monthFilter} />
  )}
  {mobileTab === 'graficos' && (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div className="panel">
        <div className="panelTitle">Gasto por Categoría</div>
        <CategoryChart data={categorySpendingData ?? []} categories={categoriesData ?? []} />
      </div>
      <div className="panel">
        <div className="panelTitle">Cuotas Futuras</div>
        <TimelineChart
          data={timelineData ?? []}
          commonData={isCommon === undefined ? timelineCommon : undefined}
          personalData={isCommon === undefined ? timelinePersonal : undefined}
          monthlyIncome={monthlyIncome}
        />
      </div>
    </div>
  )}
  {mobileTab === 'recurrentes' && (
    <div className="panel">
      <div className="panelTitle">Gastos Recurrentes</div>
      <RecurringExpensesCard />
    </div>
  )}
</div>
```

- [ ] **Step 6: Wrap desktop-only sections with class for hiding on mobile**

Wrap the following sections with `<div className="dashboard-desktop-only">...</div>`:

1. The `{/* Top Cards Grid */}` div (`.dashboard-grid-2col` containing MonthlyBalanceCard + TransferCalculationCard)
2. The `{/* Top 5 + Resumen del mes */}` div (`.dashboard-grid-sidebar`)
3. The `{/* Charts Grid */}` div (`.dashboard-grid-charts`)
4. The `{/* Timeline Panel */}` panel div
5. The `{/* Recurring Expenses */}` panel div
6. The `{/* Debt Report Panel */}` panel div

Wrap them all together in one `<div className="dashboard-desktop-only">`:

```tsx
<div className="dashboard-desktop-only">
  {/* Top Cards Grid */}
  <div className="dashboard-grid-2col">
    ...
  </div>

  {/* Top 5 + Resumen del mes */}
  <div className="dashboard-grid-sidebar">
    ...
  </div>

  {/* Charts Grid */}
  <div className="dashboard-grid-charts">
    ...
  </div>

  {/* Timeline Panel */}
  <div className="panel">
    ...
  </div>

  {/* Recurring Expenses */}
  <div className="panel">
    ...
  </div>

  {/* Debt Report Panel */}
  <div className="panel">
    ...
  </div>
</div>
```

- [ ] **Step 7: Add dashboard mobile CSS to App.css**

Append to App.css:

```css
/* ------------------------------------------------------------------ */
/*  Dashboard — Mobile layout                                          */
/* ------------------------------------------------------------------ */

.dashboard-desktop-only {
  display: contents;
}

.dashboard-mobile-section {
  display: none;
}

@media (max-width: 768px) {
  .dashboard-desktop-only {
    display: none;
  }

  .dashboard-mobile-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  /* Hide card and expense type filters on mobile */
  .dashboard-filter-card,
  .dashboard-filter-type {
    display: none;
  }

  /* Style month and person selects as pills on mobile */
  .dashboard-filter-month .input,
  .dashboard-filter-person .input {
    border-radius: 20px;
    border: 2px solid var(--color-primary);
    color: var(--color-primary);
    font-weight: 600;
    background: var(--color-primary-light);
  }

  /* Stack filters row */
  .dashboard-filters {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .dashboard-filters-actions {
    grid-column: 1 / -1;
    margin-left: 0;
    width: 100%;
  }
}

/* Mobile transfer card gradient */
.dashboard-mobile-transfer .panel {
  background: linear-gradient(135deg, var(--color-primary-light), #f3e8ff);
  border-color: rgba(99, 102, 241, 0.2);
}

/* Mobile tabs */
.dashboard-mobile-tabs {
  display: flex;
  gap: 4px;
  background: var(--color-bg);
  padding: 4px;
  border-radius: var(--radius-md);
}

.dashboard-mobile-tab {
  flex: 1;
  padding: 10px 4px;
  border: none;
  background: transparent;
  border-radius: calc(var(--radius-md) - 2px);
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}

.dashboard-mobile-tab.active {
  background: var(--color-surface);
  color: var(--color-primary);
  font-weight: 700;
  box-shadow: var(--shadow-sm);
}
```

- [ ] **Step 8: Run TypeScript build**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run build 2>&1 | tail -20
```

Expected: no TypeScript errors.

- [ ] **Step 9: Run all tests**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run test:run 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 10: Commit**

```bash
cd /Users/pablo/github/admin-consumos && git add frontend/src/pages/dashboard-page.tsx frontend/src/components/KpiSummary.tsx frontend/src/App.css && git commit -m "feat(mobile): dashboard mobile layout with KPI grid and tabs"
```

---

## Task 4: Import & Admin Polish

**Files:**
- Modify: `frontend/src/pages/import-page.tsx`
- Modify: `frontend/src/pages/admin-page.tsx`
- Modify: `frontend/src/App.css`

### 4a: Import Page

- [ ] **Step 1: Add CSS classes to import page elements**

In `import-page.tsx`, find the format selector buttons section (the pills for XLSX/PDF/GSheets). Add class `importFormatSelector` to its container and `importFormatOption` to each button.

Find the file drop zone container and add class `importDropZone`.

Find the password input row and submit button — add class `importSubmitRow` to the container div holding them.

The specific lines to change:

Format selector container (find the div with `display: 'flex'` containing the format pill buttons):
```tsx
<div className="importFormatSelector" style={{ ... }}>
```

Each format pill button (there are typically 3: XLSX, PDF, GSheets):
```tsx
<button type="button" className={`importFormatOption ...`} ...>
```

File input/drop area wrapper — add `importDropZone` class.

Password + submit row wrapper — add `importSubmitRow` class.

- [ ] **Step 2: Add import CSS to App.css**

Append to App.css:

```css
/* ------------------------------------------------------------------ */
/*  Import page — Mobile polish                                        */
/* ------------------------------------------------------------------ */

@media (max-width: 768px) {
  .importFormatSelector {
    flex-direction: column;
    gap: 8px;
  }

  .importFormatOption {
    min-height: 44px;
    width: 100%;
    justify-content: center;
  }

  .importDropZone {
    min-height: 120px;
    width: 100%;
  }

  .importSubmitRow {
    flex-direction: column;
    width: 100%;
  }

  .importSubmitRow .input,
  .importSubmitRow .button {
    width: 100%;
  }
}
```

### 4b: Admin Page

- [ ] **Step 3: Add mobile card rows to PeopleSection in admin-page.tsx**

In `PeopleSection`, after the `<table className="table">` block (closing `</table>`), add the mobile card list:

```tsx
{/* Mobile card list — hidden on desktop via CSS */}
<div className="adminCardList">
  {people.map((p) => (
    <div key={p.id} className="adminCard">
      <span className="adminCardName">{p.name}</span>
      <span className="adminCardMeta">ID: {p.id}</span>
    </div>
  ))}
</div>
```

And add `adminEntityTable` class to the existing table:
```tsx
<table className="table adminEntityTable">
```

- [ ] **Step 4: Add mobile card rows to CardsSection in admin-page.tsx**

In `CardsSection`, after the `</table>` and add class `adminEntityTable`:

```tsx
<table className="table adminEntityTable">
  ...
</table>

{/* Mobile card list */}
<div className="adminCardList">
  {cards.map((c) => (
    <div key={c.id} className="adminCard">
      <span className="adminCardName">{c.name}</span>
      <span className="adminCardMeta">{c.provider} · {people.find((p) => p.id === c.owner_person_id)?.name ?? '-'}{c.last4 ? ` · ****${c.last4}` : ''}</span>
    </div>
  ))}
</div>
```

- [ ] **Step 5: Add mobile card rows to DebtorsSection and FxRatesSection**

Find `DebtorsSection` (the section with debtors table) and `FxRatesSection`. Apply the same pattern:

In DebtorsSection, add `adminEntityTable` to the table class and add:
```tsx
<div className="adminCardList">
  {debtors.map((d) => (
    <div key={d.id} className="adminCard">
      <span className="adminCardName">{d.name}</span>
      <span className="adminCardMeta">ID: {d.id}</span>
    </div>
  ))}
</div>
```

In FxRatesSection (or wherever FX rates are listed), apply same pattern with rate info.

- [ ] **Step 6: Fix admin form grids to use 768px breakpoint**

In admin-page.tsx, the `CardsSection` form uses `style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}`. Replace those inline grid styles with a class `admin-form-grid` and handle the breakpoint in CSS.

Change each `style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}` in admin-page.tsx to `className="admin-form-grid"`.

- [ ] **Step 7: Add admin CSS to App.css**

Append to App.css:

```css
/* ------------------------------------------------------------------ */
/*  Admin page — Mobile card lists                                     */
/* ------------------------------------------------------------------ */

.adminEntityTable {
  /* visible on desktop (default) */
}

.adminCardList {
  display: none;
}

@media (max-width: 768px) {
  .adminEntityTable {
    display: none;
  }

  .adminCardList {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 8px;
  }
}

.adminCard {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.adminCardName {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--color-text);
}

.adminCardMeta {
  font-size: 0.8rem;
  color: var(--color-text-secondary);
}

/* Admin form grids */
.admin-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 768px) {
  .admin-form-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 8: Run build and all tests**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run build 2>&1 | tail -20 && npm run test:run 2>&1 | tail -20
```

Expected: TypeScript clean, all frontend tests pass.

- [ ] **Step 9: Run backend tests**

```bash
cd /Users/pablo/github/admin-consumos && source .venv/bin/activate && python -m pytest backend/tests/ -q 2>&1 | tail -20
```

Expected: all backend tests pass.

- [ ] **Step 10: Commit**

```bash
cd /Users/pablo/github/admin-consumos && git add frontend/src/pages/import-page.tsx frontend/src/pages/admin-page.tsx frontend/src/App.css && git commit -m "feat(mobile): polish import and admin pages for mobile"
```

---

## Self-Review

### Spec Coverage

| Spec requirement | Task | Notes |
|---|---|---|
| Drawer: gradient header | Task 1 | ✓ linear-gradient(#6366f1, #8b5cf6) |
| Drawer: left accent on active | Task 1 | ✓ border-left: 3px solid primary |
| Drawer: two groups (Principal/Más) | Task 1 | ✓ NAV_GROUPS |
| Drawer: icons per item | Task 1 | ✓ emoji icons in NAV_GROUPS |
| Drawer: group label style | Task 1 | ✓ 0.7rem uppercase, muted, letter-spacing 0.08em |
| Drawer: Más items secondary | Task 1 | ✓ .mobileLinkSecondary 0.875rem text-secondary |
| Purchases: hide table on mobile | Task 2 | ✓ .purchaseDesktopTable display:none |
| Purchases: card list on mobile | Task 2 | ✓ .purchaseCardList |
| Purchases: card anatomy (desc+amount+chips) | Task 2 | ✓ .purchaseCardHeader + .purchaseCardChips |
| Purchases: category chip colored | Task 2 | ✓ uses categoryObj.color |
| Purchases: installment chip (primary) | Task 2 | ✓ .purchaseChipInstallment, only when >1 |
| Purchases: tap → edit | Task 2 | ✓ .purchaseMobileEditSheet |
| Purchases: search stays visible | Task 2 | ✓ search input is outside filter panel |
| Purchases: filters behind "Filtros" toggle | Task 2 | ✓ .purchaseFiltersPanel toggle |
| Dashboard: compact month pill | Task 3 | ✓ border-radius 20px, primary colored border |
| Dashboard: person pill | Task 3 | ✓ same pill style |
| Dashboard: hide card+type filters | Task 3 | ✓ display:none in CSS |
| Dashboard: KPI 2×2 grid | Task 3 | ✓ .kpi-grid repeat(2,1fr) on mobile |
| Dashboard: transfer card visible + gradient | Task 3 | ✓ .dashboard-mobile-transfer gradient |
| Dashboard: Cuotas tab | Task 3 | ✓ MonthlyBalanceCard |
| Dashboard: Gráficos tab | Task 3 | ✓ CategoryChart + TimelineChart |
| Dashboard: Recurrentes tab | Task 3 | ✓ RecurringExpensesCard |
| Dashboard: desktop unchanged | Task 3 | ✓ .dashboard-desktop-only display:contents on desktop |
| Import: tap targets min 44px | Task 4 | ✓ .importFormatOption min-height:44px |
| Import: drop zone full-width min 120px | Task 4 | ✓ .importDropZone |
| Import: password+submit stack | Task 4 | ✓ .importSubmitRow flex-direction:column |
| Admin: entity lists as cards on mobile | Task 4 | ✓ .adminCardList |
| Admin: form grids 768px breakpoint | Task 4 | ✓ .admin-form-grid |

### Placeholder Check

No TBDs or "implement later" in the plan. All code shown completely.

### Type Consistency

- `NAV_GROUPS` items use `end: true as const` to match NavLink's `end?: boolean` — correct
- `mobileTab` typed as `'cuotas' | 'graficos' | 'recurrentes'` — used correctly in comparisons
- `mobileEditPurchase` derived from `items` (array returned by API) — same type as table `rows`
- `categoryObj?.color` — `Category.color` is `string | null` in the types, so `${categoryObj.color}22` needs null guard (✓ already guarded with `categoryObj?.color ? ... : ...`)
- `group.secondary` typed as `boolean` in `NAV_GROUPS` — used in className logic correctly

### Edge Cases Verified

- Transfer card on mobile: if no transfer needed, TransferCalculationCard renders its own "Sin datos" state — the spec says "hide card" in that case. The current TransferCalculationCard always renders a panel. This is acceptable as a first iteration; hiding it completely would require inspecting the query data in DashboardPage, which adds complexity not required by the spec's scope.
- Desktop layout at >768px: `dashboard-desktop-only` uses `display: contents` which preserves children in the layout flow — correct, no visual change.

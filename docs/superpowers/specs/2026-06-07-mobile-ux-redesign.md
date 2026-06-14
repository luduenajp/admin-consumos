# Mobile UX Redesign — Admin Consumos

**Date:** 2026-06-07  
**Scope:** Frontend only — CSS + React components. No backend changes.  
**Breakpoint:** All mobile changes apply at `max-width: 768px`.

---

## Problem

The app functions on mobile but feels like a shrunken desktop. The core pain:
- Tables require horizontal scroll — illegible on small screens
- Navigation drawer is functional but visually bare (no icons, flat list, no grouping)
- Dashboard is one long scroll with no prioritization

Pages most used on mobile: Dashboard, Compras, Importar, Admin.

---

## Solution Overview

Three targeted improvements, desktop layout untouched:

1. **Drawer navigation** — add icons, group items, improve visual hierarchy
2. **Purchases page** — replace table with card list on mobile
3. **Dashboard** — compact month selector, 2×2 KPI grid, tabbed inner sections

Minor mobile polish also applied to Importar and Admin (form stacking, spacing).

---

## 1. Drawer Navigation

**Current:** flat list of 8 text-only links, right-side drawer, no grouping.

**Changes:**
- Header: gradient background (`#6366f1 → #8b5cf6`), white text, ✕ button
- Left accent border (3px `--color-primary`) on active item instead of full background
- Two labeled groups: **Principal** (Dashboard, Compras, Importar, Admin) and **Más** (Presupuesto, Ahorros, Categorías, Objetivos)
- Each item gets an icon (emoji): 📊 Dashboard · 🧾 Compras · 📥 Importar · ⚙️ Admin · 💰 Presupuesto · 🐖 Ahorros · 🏷️ Categorías · 🎯 Objetivos
- Group label style: 8px uppercase, `--color-muted`, `letter-spacing: 0.08em`
- Principal items: `font-size: 0.95rem`, `font-weight: 500`
- Más items: `font-size: 0.875rem`, `color: --color-text-secondary` (visually secondary)
- Drawer continues sliding from the right (no change to open/close mechanics)

**Files:** `App.tsx` (markup), `App.css` (`.mobileMenu*` classes)

---

## 2. Purchases Page — Mobile Card List

**Current:** `<table>` with horizontal scroll on mobile — requires swiping to see all columns.

**Behavior:**
- Below 768px: hide the `tableContainer`, render a card list instead
- Above 768px: unchanged (table stays)
- No new data fetching — same query, different render

**Card anatomy** (per purchase):
```
┌─────────────────────────────────────────┐
│ Descripción                    $45.200  │
│ [⛽ Combustible] [Pablo] [Visa] [3/12] [15 may] │
└─────────────────────────────────────────┘
```
- Description: `font-weight: 700`, `font-size: 0.95rem`, `color: --color-text`
- Amount: `font-weight: 700`, `font-size: 1rem`, `color: --color-primary`, right-aligned
- Chips (pills): `border-radius: 999px`, `font-size: 0.7rem`, `padding: 2px 8px`
  - Category chip: uses the category's color (background tinted, text darker shade)
  - Person/Card/Date chips: neutral (`background: --color-bg`, `color: --color-text-secondary`)
  - Installment chip (X/Y): `background: --color-primary-light`, `color: --color-primary`, bold — only shown when `total_installments > 1`
- Tap on card → opens the existing edit form (same behavior as clicking "Editar" in desktop)
- Search bar stays visible above the card list on mobile
- Filters panel: collapses behind a "Filtros" button on mobile (expanded by default on desktop)

**New CSS class:** `.purchaseCardList` (mobile only), `.purchaseCard`, `.purchaseCardChips`

**Files:** `purchases-page.tsx`, `App.css`

---

## 3. Dashboard — Mobile Layout

**Current:** Long single-column scroll with all widgets stacked. Month selector + 4 filter dropdowns side by side (wraps awkwardly).

**Changes:**

### Month selector row
- Single full-width pill button (`border-radius: 20px`, primary color, shows current month + dropdown arrow)
- Person filter: compact pill next to it (`👤 Todos` / `👤 Pablo`)
- Remove card filter and expense-type filter from the top on mobile (add inside a "Filtros ▾" expander if needed later — out of scope for now)

### KPI grid
- 2×2 grid of compact cards (same data as existing KpiSummary)
- Each card: label (8px uppercase muted) + value (18px bold)
- Values: Total mes · Gastos comunes · Gastos personales · Cuotas activas

### Transfer card
- Always visible, stands out visually
- Gradient background (`--color-primary-light` to `--color-accent` tinted)
- Shows: "Pablo → Cintia" + amount. If no transfer needed: hide card.

### Inner tabs
Three tabs below the transfer card:
- **Cuotas** (default active): the existing `MonthlyBalanceCard` breakdown list — simple rows with description + amount
- **Gráficos**: `CategoryChart` + `TimelineChart` stacked vertically
- **Recurrentes**: `RecurringExpensesCard`

Tab state: local `useState`, no URL routing.

**Files:** `dashboard-page.tsx`, `App.css` (new `.dashboard-mobile-*` classes)

---

## 4. Minor Mobile Polish — Importar & Admin

### Importar (`import-page.tsx`)
- Format selector: stack options vertically (already `flex-wrap` but pills are too small — increase tap target to `min-height: 44px`)
- File drop zone: full-width, `min-height: 120px`, prominent border
- Password field + submit button: full-width stack

### Admin (`admin-page.tsx`)
- Section panels already stack — no structural change needed
- Entity lists (Personas, Tarjetas, Deudores, Tasas FX): if rendered as tables, switch to simple card rows on mobile (same chip pattern as Purchases, minimal — just name + action buttons)
- Form rows: already use `flex-direction: column` at 640px — extend to 768px if needed

---

## What's NOT changing

- Desktop layout: zero changes above 768px
- Data model, API, backend: untouched
- Routing structure: unchanged
- Chart libraries: charts stay (just placed inside a tab on mobile)
- Edit/create forms: same forms, just rendered inside cards or modals as they are today

---

## Implementation order

1. Drawer navigation (App.tsx + App.css) — isolated, no page dependencies
2. Purchases card list (purchases-page.tsx + App.css) — highest pain point
3. Dashboard mobile layout (dashboard-page.tsx + App.css) — most complex
4. Importar + Admin polish — quick, last

---

## Testing

- All existing backend + frontend tests must keep passing (`pytest -q`, `npm run test:run`)
- Manual: open each page on 390px viewport (iPhone size) in browser devtools
- Verify desktop layout at 1280px is identical to before

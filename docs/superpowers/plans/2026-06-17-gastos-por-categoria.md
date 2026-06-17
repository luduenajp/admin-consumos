# Gastos por Categoría — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar la página `/gastos-categorias` con filtros de mes, persona y tipo, reemplazando "Compras" en la navegación.

**Architecture:** Nueva página que reutiliza `CategoryChart`, `fetchCategorySpending`, `fetchPeople` y `fetchCategories` ya existentes. Sin cambios en backend. Dos archivos tocados: la página nueva y `App.tsx`.

**Tech Stack:** React 19, TypeScript, @tanstack/react-query, CSS classes existentes.

## Global Constraints

- Sin dependencias nuevas
- CSS: solo clases existentes (`page`, `pageTitle`, `panel`, `panelTitle`, `formRow`, `label`, `input`, `table`, `muted`)
- Formato de montos: `formatCurrency()` de `../utils/format`
- Mes inicial: `getCurrentYearMonth()` de `../utils/dates`
- `queryKey` arrays deben incluir todos los parámetros activos

---

### Task 1: Crear `gastos-categorias-page.tsx`

**Files:**
- Create: `frontend/src/pages/gastos-categorias-page.tsx`

**Interfaces:**
- Consumes:
  - `fetchCategorySpending({ yearMonth, personId, isCommon })` → `Promise<CategorySpendingRow[]>`
  - `fetchPeople()` → `Promise<Person[]>`
  - `fetchCategories()` → `Promise<Category[]>`
  - `CategoryChart({ data, categories })` from `../components/CategoryChart`
  - `getCurrentYearMonth()` → `string` (YYYY-MM)
  - `formatCurrency(amount: number)` → `string`
- Produces: exported `GastosCategoriaPage` component (used in Task 2)

- [ ] **Step 1: Crear el archivo de la página**

Crear `frontend/src/pages/gastos-categorias-page.tsx` con el siguiente contenido:

```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchCategorySpending, fetchPeople, fetchCategories } from '../api/endpoints'
import { CategoryChart } from '../components/CategoryChart'
import { getCurrentYearMonth } from '../utils/dates'
import { formatCurrency } from '../utils/format'

export function GastosCategoriaPage() {
  const [yearMonth, setYearMonth] = useState<string>(() => getCurrentYearMonth())
  const [personId, setPersonId] = useState<string>('')
  const [isCommonFilter, setIsCommonFilter] = useState<string>('all')

  const isCommon = isCommonFilter === 'all' ? undefined : isCommonFilter === 'common'
  const personIdNum = personId ? Number(personId) : undefined

  const { data: people = [] } = useQuery({
    queryKey: ['people'],
    queryFn: fetchPeople,
    staleTime: 10 * 60 * 1000,
  })

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
    staleTime: 10 * 60 * 1000,
  })

  const { data: spending = [], isLoading } = useQuery({
    queryKey: ['reports', 'category-spending', { yearMonth, personId, isCommon }],
    queryFn: () => fetchCategorySpending({ yearMonth, personId: personIdNum, isCommon }),
  })

  const grandTotal = spending.reduce((sum, d) => sum + d.total_ars, 0)

  function prevMonth() {
    const [y, m] = yearMonth.split('-').map(Number)
    const d = new Date(y, m - 2, 1)
    setYearMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }

  function nextMonth() {
    const [y, m] = yearMonth.split('-').map(Number)
    const d = new Date(y, m, 1)
    setYearMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }

  return (
    <div className="page">
      <div className="pageTitle">Gastos por Categoría</div>

      <div className="panel">
        <div className="formRow" style={{ flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
          {/* Selector de mes */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button className="button" onClick={prevMonth} style={{ padding: '0.25rem 0.6rem' }}>‹</button>
            <span style={{ minWidth: '6rem', textAlign: 'center', fontWeight: 500 }}>{yearMonth}</span>
            <button className="button" onClick={nextMonth} style={{ padding: '0.25rem 0.6rem' }}>›</button>
          </div>

          {/* Filtro persona */}
          <select
            className="input"
            value={personId}
            onChange={(e) => setPersonId(e.target.value)}
            style={{ minWidth: '8rem' }}
          >
            <option value="">Todos</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>

          {/* Filtro tipo */}
          <select
            className="input"
            value={isCommonFilter}
            onChange={(e) => setIsCommonFilter(e.target.value)}
            style={{ minWidth: '10rem' }}
          >
            <option value="all">Todos los gastos</option>
            <option value="common">Solo comunes</option>
            <option value="personal">Solo personales</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="muted" style={{ padding: '2rem', textAlign: 'center' }}>Cargando…</div>
      ) : spending.length === 0 ? (
        <div className="muted" style={{ padding: '2rem', textAlign: 'center' }}>Sin datos de categorías para este mes</div>
      ) : (
        <>
          <div className="panel">
            <div className="panelTitle">Gráfico</div>
            <CategoryChart data={spending} categories={categories} />
          </div>

          <div className="panel">
            <div className="panelTitle">Detalle</div>
            <table className="table">
              <thead>
                <tr>
                  <th>Categoría</th>
                  <th style={{ textAlign: 'right' }}>Monto</th>
                  <th style={{ textAlign: 'right' }}>%</th>
                </tr>
              </thead>
              <tbody>
                {[...spending]
                  .sort((a, b) => b.total_ars - a.total_ars)
                  .map((row) => (
                    <tr key={row.category}>
                      <td>{row.category || 'Sin categoría'}</td>
                      <td style={{ textAlign: 'right' }}>{formatCurrency(row.total_ars)}</td>
                      <td style={{ textAlign: 'right' }}>
                        {grandTotal > 0 ? ((row.total_ars / grandTotal) * 100).toFixed(1) : '0.0'}%
                      </td>
                    </tr>
                  ))}
              </tbody>
              <tfoot>
                <tr style={{ fontWeight: 600 }}>
                  <td>Total</td>
                  <td style={{ textAlign: 'right' }}>{formatCurrency(grandTotal)}</td>
                  <td style={{ textAlign: 'right' }}>100%</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verificar TypeScript**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run build 2>&1 | tail -20
```

Esperado: sin errores de TypeScript referidos a `GastosCategoriaPage`.

- [ ] **Step 3: Commit**

```bash
cd /Users/pablo/github/admin-consumos && git add frontend/src/pages/gastos-categorias-page.tsx
git commit -m "feat(gastos): nueva página gastos por categoría con filtros"
```

---

### Task 2: Integrar en App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `GastosCategoriaPage` de `./pages/gastos-categorias-page`
- Produces: ruta `/gastos-categorias` activa; nav item "Categorías" reemplaza "Compras"

- [ ] **Step 1: Agregar lazy import**

En `frontend/src/App.tsx`, después de la línea de `SavingsPage`:

```tsx
// Antes (línea ~15):
const SavingsPage = lazy(() => import('./pages/savings-page').then((m) => ({ default: m.SavingsPage })))

// Agregar después:
const GastosCategoriaPage = lazy(() =>
  import('./pages/gastos-categorias-page').then((m) => ({ default: m.GastosCategoriaPage })),
)
```

- [ ] **Step 2: Reemplazar ítem "Compras" en NAV_GROUPS**

En `frontend/src/App.tsx`, en el array `NAV_GROUPS` grupo `'Principal'`:

```tsx
// Reemplazar:
{ to: '/purchases', label: 'Compras', icon: '🧾' },

// Por:
{ to: '/gastos-categorias', label: 'Categorías', icon: '📊' },
```

- [ ] **Step 3: Agregar Route**

En `frontend/src/App.tsx`, dentro del bloque `<Routes>`:

```tsx
// Agregar junto a las otras rutas:
<Route element={<GastosCategoriaPage />} path="/gastos-categorias" />
```

- [ ] **Step 4: Verificar TypeScript y lint**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run build 2>&1 | tail -20
```

Esperado: build exitoso sin errores.

- [ ] **Step 5: Correr tests frontend**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run test:run 2>&1 | tail -20
```

Esperado: todos los tests pasan.

- [ ] **Step 6: Commit**

```bash
cd /Users/pablo/github/admin-consumos && git add frontend/src/App.tsx
git commit -m "feat(nav): reemplazar Compras por Gastos por Categoría en la nav"
```

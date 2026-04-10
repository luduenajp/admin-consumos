# Design: Evolución del Total de Ahorros

**Date:** 2026-04-09  
**Status:** Approved

## Summary

Add a new chart panel to the Savings page showing how the total savings (ARS, USD, and combined) evolve over time. Each time a snapshot is registered for any investment, a new data point appears on the chart. Historical values are forward-filled: if an investment hasn't been updated since a prior date, its last known value is used.

## Backend

### New endpoint

`GET /api/savings/total-history`

Returns a list of data points, one per unique snapshot date across all investments, sorted ascending by date.

**Response shape:**
```json
[
  {
    "date": "2025-11-01",
    "total_ars": 150000.0,
    "total_usd": 500.0,
    "total_in_ars": 725000.0,
    "total_in_usd": 612.5
  }
]
```

`total_in_ars` and `total_in_usd` are `null` when no `SavingsExchangeRate` exists at or before that date.

### New CRUD function: `get_savings_total_history(session)`

Location: `backend/app/crud.py`

Algorithm:
1. Fetch all `SavingSnapshot` rows joined with their `Saving` (to get currency).
2. Collect all unique `date` values across snapshots — these are the chart's x-axis points.
3. For each date, compute each saving's value by forward-fill: the most recent snapshot with `date <= current_date` for that saving_id.
4. Sum by currency: `total_ars` (sum of ARS savings), `total_usd` (sum of USD savings).
5. Look up the applicable exchange rate: the `SavingsExchangeRate` with the largest `date <= current_date`.
6. If a rate exists:
   - `total_in_ars = total_ars + total_usd × rate.usd_buy`
   - `total_in_usd = total_ars / rate.usd_sell + total_usd`
7. Return sorted list of `{date, total_ars, total_usd, total_in_ars, total_in_usd}`.

### Tests

New tests in `backend/tests/`:
- Forward-fill works correctly when not all savings have snapshots on the same date.
- Combined totals are computed correctly when an exchange rate is available.
- `total_in_ars` and `total_in_usd` are `null` when no exchange rate exists for or before that date.
- Uses the correct (most recent prior) exchange rate, not just the latest one overall.

## Frontend

### New component: `TotalHistoryChart`

Location: inline in `frontend/src/pages/savings-page.tsx`

- Fetches from `GET /api/savings/total-history` via a new `fetchSavingsTotalHistory()` function in `api/endpoints.ts` (with matching type in `api/types.ts`).
- Single `useQuery(['savings-total-history'])`.
- Four toggleable lines via checkboxes:
  - Total ARS
  - Total USD
  - Total en ARS (combinado, using `usd_buy`)
  - Total en USD (combinado, using `usd_sell`)
- Gap handling: `connectNulls={false}` — combined lines have gaps where no exchange rate was available.
- Tooltip shows formatted amounts with correct currency label per line.
- Uses same visual style as existing `HistoryChart`: Recharts `LineChart`, `LINE_COLORS`, existing CSS variables.

### UI placement

New panel titled **"Evolución del total"** inserted between the existing "Total ahorros" panel and the "Mis inversiones" table.

### New API additions

**`api/types.ts`:**
```typescript
export interface SavingsTotalHistoryPoint {
  date: string
  total_ars: number
  total_usd: number
  total_in_ars: number | null
  total_in_usd: number | null
}
```

**`api/endpoints.ts`:**
```typescript
export async function fetchSavingsTotalHistory(): Promise<SavingsTotalHistoryPoint[]>
```

## Scope

This design does not change the existing `HistoryChart` (per-investment history) or the `SavingsTotalsPanel` (current totals). It only adds new read-only data on top of existing snapshot data.

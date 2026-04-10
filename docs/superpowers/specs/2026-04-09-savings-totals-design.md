# Savings Totals with Exchange Rate Conversion

**Date:** 2026-04-09  
**Feature:** Display total savings in ARS and USD, with unified totals using official buy/sell exchange rate

---

## Overview

Add a totals summary panel to the Ahorros page showing the combined value of all savings, both per-currency and unified via the official dollar exchange rate. Users can register the current compra/venta of the official dollar to enable conversion.

---

## Data Model

### New table: `SavingsExchangeRate`

| Field | Type | Notes |
|---|---|---|
| `id` | int PK | auto |
| `date` | string (YYYY-MM-DD) | date the rate was registered |
| `usd_buy` | float | price bank pays when buying USD (lo que recibís al vender dólares) |
| `usd_sell` | float | price bank charges when selling USD (lo que pagás al comprar dólares) |

- No `year_month` — official rate changes daily, stored by exact date
- Always use the most recent entry for calculations
- No delete endpoint needed (append-only log)

---

## Backend

### New file: `backend/app/models.py`
Add `SavingsExchangeRate` SQLModel table.

### New schemas: `backend/app/schemas.py`
- `SavingsExchangeRateCreate`: `date`, `usd_buy`, `usd_sell` (both > 0)
- `SavingsExchangeRateRead`: adds `id`

### New endpoints: `backend/app/api.py`
- `POST /api/savings-exchange-rate` — create new rate entry
- `GET /api/savings-exchange-rate` — return all entries ordered by date desc

---

## Frontend

### Types: `frontend/src/api/types.ts`
Add `SavingsExchangeRate` and `SavingsExchangeRateCreate` interfaces.

### Endpoints: `frontend/src/api/endpoints.ts`
- `fetchSavingsExchangeRates()` → `GET /api/savings-exchange-rate`
- `createSavingsExchangeRate(payload)` → `POST /api/savings-exchange-rate`

### New component: `SavingsTotalsPanel` (inline in savings-page.tsx)

Displayed as the first panel on the Ahorros page.

**Totals displayed:**
- **Total ARS**: sum of `current_amount` for savings where `currency === 'ARS'`
- **Total USD**: sum of `current_amount` for savings where `currency === 'USD'`
- **Total en ARS**: `totalARS + totalUSD × latestRate.usd_buy`  
  (uses buy rate: liquidating USD means selling to bank at buy price)
- **Total en USD**: `totalARS / latestRate.usd_sell + totalUSD`  
  (uses sell rate: converting ARS to USD costs the sell price)

**Exchange rate section (collapsible):**
- Shows latest rate: date, compra, venta
- "Actualizar" button opens inline form: date (default today), usd_buy, usd_sell
- On success: invalidates `['savings-exchange-rates']` query, collapses form

**Edge cases:**
- Savings with `current_amount == null` are excluded from totals with a count note ("N inversiones sin valor registrado")
- If no exchange rate exists: show ARS and USD totals normally, show "—" for unified totals with hint "Registrá un tipo de cambio para ver el total unificado"

---

## Conversion Logic

| Desired total | Rate used | Reason |
|---|---|---|
| USD → ARS | `usd_buy` | You sell your USD; bank pays at buy price |
| ARS → USD | `usd_sell` | You buy USD with ARS; bank charges sell price |

---

## Out of Scope

- Historical rate chart
- Multiple currencies beyond ARS/USD
- Automatic rate fetching from external APIs

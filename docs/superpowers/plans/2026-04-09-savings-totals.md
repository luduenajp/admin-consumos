# Savings Totals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a totals panel to the Ahorros page showing Total ARS, Total USD, and unified totals converted via the official buy/sell exchange rate, with a form to register new rates.

**Architecture:** New `SavingsExchangeRate` SQLModel table stores dated compra/venta rates. Two new backend endpoints expose CRUD. A new `SavingsTotalsPanel` component renders above the existing savings table, fetching both savings and rates, computing totals client-side.

**Tech Stack:** Python 3.11 + FastAPI + SQLModel (backend) · React 19 + TypeScript + React Query (frontend)

---

### Task 1: Add `SavingsExchangeRate` model + schemas + tests

**Files:**
- Modify: `backend/app/models.py` (append new model)
- Modify: `backend/app/schemas.py` (append new schemas)
- Modify: `backend/tests/test_savings.py` (append new test class)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_savings.py`:

```python
from app.crud import (
    create_saving,
    create_saving_snapshot,
    create_savings_exchange_rate,
    delete_saving,
    delete_saving_snapshot,
    list_saving_snapshots,
    list_savings,
    list_savings_exchange_rates,
    update_saving,
)
from app.schemas import (
    SavingCreate,
    SavingSnapshotCreate,
    SavingUpdate,
    SavingsExchangeRateCreate,
)


class TestSavingsExchangeRate:
    def test_create_and_list(self, session):
        rate = create_savings_exchange_rate(
            session=session,
            payload=SavingsExchangeRateCreate(date="2026-04-09", usd_buy=1150.0, usd_sell=1200.0),
        )
        assert rate.id is not None
        assert rate.usd_buy == 1150.0
        assert rate.usd_sell == 1200.0

        rates = list_savings_exchange_rates(session=session)
        assert len(rates) == 1
        assert rates[0].id == rate.id

    def test_list_ordered_desc(self, session):
        create_savings_exchange_rate(
            session=session,
            payload=SavingsExchangeRateCreate(date="2026-01-01", usd_buy=1000.0, usd_sell=1050.0),
        )
        create_savings_exchange_rate(
            session=session,
            payload=SavingsExchangeRateCreate(date="2026-04-09", usd_buy=1150.0, usd_sell=1200.0),
        )
        rates = list_savings_exchange_rates(session=session)
        assert rates[0].date == "2026-04-09"
        assert rates[1].date == "2026-01-01"


class TestSavingsExchangeRateAPI:
    def test_create_endpoint(self, client):
        resp = client.post(
            "/api/savings-exchange-rate",
            json={"date": "2026-04-09", "usd_buy": 1150.0, "usd_sell": 1200.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] is not None
        assert data["usd_buy"] == 1150.0
        assert data["usd_sell"] == 1200.0
        assert data["date"] == "2026-04-09"

    def test_list_endpoint(self, client):
        client.post(
            "/api/savings-exchange-rate",
            json={"date": "2026-01-01", "usd_buy": 1000.0, "usd_sell": 1050.0},
        )
        client.post(
            "/api/savings-exchange-rate",
            json={"date": "2026-04-09", "usd_buy": 1150.0, "usd_sell": 1200.0},
        )
        resp = client.get("/api/savings-exchange-rate")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["date"] == "2026-04-09"  # most recent first

    def test_create_invalid_buy(self, client):
        resp = client.post(
            "/api/savings-exchange-rate",
            json={"date": "2026-04-09", "usd_buy": 0, "usd_sell": 1200.0},
        )
        assert resp.status_code == 422

    def test_create_invalid_sell(self, client):
        resp = client.post(
            "/api/savings-exchange-rate",
            json={"date": "2026-04-09", "usd_buy": 1150.0, "usd_sell": -1},
        )
        assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/pablo/github/admin-consumos/backend
source ../.venv/bin/activate
python -m pytest tests/test_savings.py::TestSavingsExchangeRate tests/test_savings.py::TestSavingsExchangeRateAPI -v
```

Expected: ImportError or similar — `create_savings_exchange_rate` doesn't exist yet.

- [ ] **Step 3: Add `SavingsExchangeRate` model to `models.py`**

Append at the end of `backend/app/models.py`:

```python
class SavingsExchangeRate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: str = Field(index=True)  # YYYY-MM-DD
    usd_buy: float   # price bank pays when buying USD (you receive this when selling USD)
    usd_sell: float  # price bank charges when selling USD (you pay this when buying USD)
```

- [ ] **Step 4: Add schemas to `schemas.py`**

Append at the end of `backend/app/schemas.py`:

```python
class SavingsExchangeRateCreate(BaseModel):
    date: str  # YYYY-MM-DD
    usd_buy: float = Field(gt=0)
    usd_sell: float = Field(gt=0)


class SavingsExchangeRateRead(BaseModel):
    id: int
    date: str
    usd_buy: float
    usd_sell: float
```

- [ ] **Step 5: Add CRUD functions to `crud.py`**

Append at the end of `backend/app/crud.py`:

```python
# --- SavingsExchangeRate CRUD ---

def list_savings_exchange_rates(*, session: Session) -> list[SavingsExchangeRate]:
    """Returns all exchange rates ordered by date descending."""
    stmt = select(SavingsExchangeRate).order_by(SavingsExchangeRate.date.desc())
    return list(session.exec(stmt).all())


def create_savings_exchange_rate(
    *, session: Session, payload: SavingsExchangeRateCreate
) -> SavingsExchangeRate:
    rate = SavingsExchangeRate(
        date=payload.date,
        usd_buy=payload.usd_buy,
        usd_sell=payload.usd_sell,
    )
    session.add(rate)
    session.commit()
    session.refresh(rate)
    return rate
```

Also add the imports at the top of `crud.py` if not already present:
- `from app.models import SavingsExchangeRate` (add to the existing models import line)
- `from app.schemas import SavingsExchangeRateCreate` (add to the existing schemas import line)

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd /Users/pablo/github/admin-consumos/backend
python -m pytest tests/test_savings.py::TestSavingsExchangeRate tests/test_savings.py::TestSavingsExchangeRateAPI -v
```

Expected: Some pass (CRUD tests), API tests still fail (no endpoints yet). That's fine — we wire endpoints in Task 2.

- [ ] **Step 7: Commit**

```bash
cd /Users/pablo/github/admin-consumos
git add backend/app/models.py backend/app/schemas.py backend/app/crud.py backend/tests/test_savings.py
git commit -m "feat: add SavingsExchangeRate model, schemas, and CRUD"
```

---

### Task 2: Add backend API endpoints

**Files:**
- Modify: `backend/app/api.py`

- [ ] **Step 1: Add imports to `api.py`**

In `api.py`, add to the `from app.crud import (...)` block:

```python
    create_savings_exchange_rate,
    list_savings_exchange_rates,
```

Add to the `from app.schemas import (...)` block:

```python
    SavingsExchangeRateCreate,
    SavingsExchangeRateRead,
```

- [ ] **Step 2: Add endpoints to `api.py`**

Find the savings endpoints section (near `@api_router.get("/savings")`) and add after the existing saving endpoints:

```python
@api_router.get("/savings-exchange-rate", response_model=list[SavingsExchangeRateRead])
def get_savings_exchange_rates():
    with get_session() as session:
        return list_savings_exchange_rates(session=session)


@api_router.post("/savings-exchange-rate", response_model=SavingsExchangeRateRead)
def post_savings_exchange_rate(payload: SavingsExchangeRateCreate):
    with get_session() as session:
        return create_savings_exchange_rate(session=session, payload=payload)
```

- [ ] **Step 3: Run the full test suite**

```bash
cd /Users/pablo/github/admin-consumos/backend
python -m pytest tests/test_savings.py -v
```

Expected: All tests in `test_savings.py` pass including `TestSavingsExchangeRateAPI`.

- [ ] **Step 4: Run full backend suite to check no regressions**

```bash
cd /Users/pablo/github/admin-consumos/backend
python -m pytest tests/ -q
```

Expected: 0 failures.

- [ ] **Step 5: Commit**

```bash
cd /Users/pablo/github/admin-consumos
git add backend/app/api.py
git commit -m "feat: add GET/POST /api/savings-exchange-rate endpoints"
```

---

### Task 3: Frontend types and API functions

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/endpoints.ts`

- [ ] **Step 1: Add TypeScript interfaces to `types.ts`**

Append at the end of `frontend/src/api/types.ts`:

```typescript
export interface SavingsExchangeRate {
  id: number
  date: string
  usd_buy: number
  usd_sell: number
}

export interface SavingsExchangeRateCreate {
  date: string
  usd_buy: number
  usd_sell: number
}
```

- [ ] **Step 2: Add API functions to `endpoints.ts`**

First, add the imports at the top of `endpoints.ts` — add `SavingsExchangeRate` and `SavingsExchangeRateCreate` to the existing import from `./types`:

```typescript
import type {
  // ... existing imports ...
  SavingsExchangeRate,
  SavingsExchangeRateCreate,
} from './types'
```

Then append the two API functions at the end of `endpoints.ts`:

```typescript
export function fetchSavingsExchangeRates(): Promise<SavingsExchangeRate[]> {
  return getJson<SavingsExchangeRate[]>('/api/savings-exchange-rate')
}

export function createSavingsExchangeRate(
  payload: SavingsExchangeRateCreate,
): Promise<SavingsExchangeRate> {
  return postJson<SavingsExchangeRate>('/api/savings-exchange-rate', payload)
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/pablo/github/admin-consumos/frontend
npm run build
```

Expected: Build succeeds, 0 TypeScript errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/pablo/github/admin-consumos
git add frontend/src/api/types.ts frontend/src/api/endpoints.ts
git commit -m "feat: add SavingsExchangeRate TypeScript types and API functions"
```

---

### Task 4: Add `SavingsTotalsPanel` to savings page

**Files:**
- Modify: `frontend/src/pages/savings-page.tsx`

- [ ] **Step 1: Add imports at the top of `savings-page.tsx`**

Add to the existing imports from `../api/endpoints`:
```typescript
  fetchSavingsExchangeRates,
  createSavingsExchangeRate,
```

Add to the existing imports from `../api/types`:
```typescript
  SavingsExchangeRate,
```

- [ ] **Step 2: Add `SavingsTotalsPanel` component**

Add this new component function before the `SavingsPage` function (after the `HistoryChart` function):

```typescript
function SavingsTotalsPanel({ savings }: { savings: Saving[] }) {
  const queryClient = useQueryClient()
  const today = new Date().toISOString().split('T')[0]
  const [showRateForm, setShowRateForm] = useState(false)
  const [rateDate, setRateDate] = useState(today)
  const [usdBuy, setUsdBuy] = useState('')
  const [usdSell, setUsdSell] = useState('')
  const [rateError, setRateError] = useState('')

  const ratesQuery = useQuery({
    queryKey: ['savings-exchange-rates'],
    queryFn: fetchSavingsExchangeRates,
  })

  const rateMutation = useMutation({
    mutationFn: () =>
      createSavingsExchangeRate({
        date: rateDate,
        usd_buy: parseFloat(usdBuy),
        usd_sell: parseFloat(usdSell),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savings-exchange-rates'] })
      setShowRateForm(false)
      setUsdBuy('')
      setUsdSell('')
      setRateError('')
    },
    onError: (err) => setRateError(extractErrorMessage(err)),
  })

  const latestRate: SavingsExchangeRate | null = ratesQuery.data?.[0] ?? null

  const withAmount = savings.filter((s) => s.current_amount != null)
  const withoutAmount = savings.length - withAmount.length

  const totalARS = withAmount
    .filter((s) => s.currency === 'ARS')
    .reduce((sum, s) => sum + (s.current_amount ?? 0), 0)

  const totalUSD = withAmount
    .filter((s) => s.currency === 'USD')
    .reduce((sum, s) => sum + (s.current_amount ?? 0), 0)

  const totalInARS = latestRate != null ? totalARS + totalUSD * latestRate.usd_buy : null
  const totalInUSD = latestRate != null ? totalARS / latestRate.usd_sell + totalUSD : null

  const locale = 'es-AR'

  return (
    <div className="panel">
      <div className="panelTitle">Total ahorros</div>

      <div style={{ display: 'flex', gap: '32px', flexWrap: 'wrap', marginBottom: '16px' }}>
        <div>
          <div className="label">Total ARS</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 600, color: 'var(--color-text)' }}>
            ${totalARS.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div>
          <div className="label">Total USD</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 600, color: 'var(--color-text)' }}>
            U$S {totalUSD.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div>
          <div className="label">Total en ARS (incl. USD)</div>
          {totalInARS != null ? (
            <div style={{ fontSize: '1.4rem', fontWeight: 600, color: 'var(--color-primary)' }}>
              ${totalInARS.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          ) : (
            <div style={{ fontSize: '1.1rem', color: 'var(--color-text-secondary)' }}>—</div>
          )}
        </div>
        <div>
          <div className="label">Total en USD (incl. ARS)</div>
          {totalInUSD != null ? (
            <div style={{ fontSize: '1.4rem', fontWeight: 600, color: 'var(--color-primary)' }}>
              U$S {totalInUSD.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          ) : (
            <div style={{ fontSize: '1.1rem', color: 'var(--color-text-secondary)' }}>—</div>
          )}
        </div>
      </div>

      {withoutAmount > 0 && (
        <div className="hint" style={{ marginBottom: '12px' }}>
          {withoutAmount} inversión{withoutAmount > 1 ? 'es' : ''} sin valor registrado (excluida{withoutAmount > 1 ? 's' : ''} del total)
        </div>
      )}

      {/* Exchange rate section */}
      <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '12px', marginTop: '4px' }}>
        {latestRate != null ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <span className="muted" style={{ fontSize: '0.85rem' }}>
              Tipo de cambio oficial ({latestRate.date}): compra ${latestRate.usd_buy.toLocaleString(locale)} · venta ${latestRate.usd_sell.toLocaleString(locale)}
            </span>
            <button
              className="button"
              style={{ fontSize: '0.8rem', padding: '4px 10px', background: 'var(--color-surface)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}
              onClick={() => setShowRateForm((v) => !v)}
              type="button"
            >
              {showRateForm ? 'Cancelar' : 'Actualizar'}
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span className="hint">Registrá un tipo de cambio para ver el total unificado</span>
            <button
              className="button"
              style={{ fontSize: '0.8rem', padding: '4px 10px' }}
              onClick={() => setShowRateForm((v) => !v)}
              type="button"
            >
              {showRateForm ? 'Cancelar' : 'Registrar tipo de cambio'}
            </button>
          </div>
        )}

        {showRateForm && (
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap', marginTop: '12px' }}>
            <div className="formRow" style={{ marginBottom: 0 }}>
              <label className="label">Fecha</label>
              <input
                className="input"
                type="date"
                value={rateDate}
                onChange={(e) => setRateDate(e.target.value)}
                style={{ width: '140px' }}
              />
            </div>
            <div className="formRow" style={{ marginBottom: 0 }}>
              <label className="label">Compra (ARS/USD)</label>
              <input
                className="input"
                type="number"
                step="0.01"
                min="0.01"
                value={usdBuy}
                onChange={(e) => setUsdBuy(e.target.value)}
                placeholder="1150.00"
                style={{ width: '130px' }}
              />
            </div>
            <div className="formRow" style={{ marginBottom: 0 }}>
              <label className="label">Venta (ARS/USD)</label>
              <input
                className="input"
                type="number"
                step="0.01"
                min="0.01"
                value={usdSell}
                onChange={(e) => setUsdSell(e.target.value)}
                placeholder="1200.00"
                style={{ width: '130px' }}
              />
            </div>
            <button
              className="button"
              disabled={
                rateMutation.isPending ||
                !usdBuy ||
                !usdSell ||
                parseFloat(usdBuy) <= 0 ||
                parseFloat(usdSell) <= 0
              }
              onClick={() => rateMutation.mutate()}
              type="button"
            >
              {rateMutation.isPending ? 'Guardando…' : 'Guardar'}
            </button>
            {rateError && <span className="error">{rateError}</span>}
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Render `SavingsTotalsPanel` in `SavingsPage`**

In the `SavingsPage` return, add `<SavingsTotalsPanel savings={savings} />` as the very first panel, before `{/* ---- Panel 1: Table ---- */}`:

```typescript
return (
  <div className="page">
    <h1 className="pageTitle">Ahorros e Inversiones</h1>

    <SavingsTotalsPanel savings={savings} />

    {/* ---- Panel 1: Table ---- */}
    ...
```

- [ ] **Step 4: Build to verify TypeScript**

```bash
cd /Users/pablo/github/admin-consumos/frontend
npm run build
```

Expected: Build succeeds, 0 TypeScript errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/pablo/github/admin-consumos
git add frontend/src/pages/savings-page.tsx
git commit -m "feat: add SavingsTotalsPanel with ARS/USD totals and exchange rate registration"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run full backend tests**

```bash
cd /Users/pablo/github/admin-consumos/backend
python -m pytest tests/ -q
```

Expected: 0 failures.

- [ ] **Step 2: Run full frontend build**

```bash
cd /Users/pablo/github/admin-consumos/frontend
npm run build
```

Expected: Successful build.

- [ ] **Step 3: Run frontend tests**

```bash
cd /Users/pablo/github/admin-consumos/frontend
npm run test:run
```

Expected: 0 failures.

# Savings Total History Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a chart panel to the Savings page showing how total ARS, total USD, and combined savings evolve over time, with per-line toggles.

**Architecture:** New `GET /api/savings/total-history` endpoint backed by `get_savings_total_history()` in `crud.py`. The function collects all unique snapshot dates, forward-fills each saving's last known value to that date, sums by currency, and looks up the closest prior exchange rate for combined totals. The frontend adds a new `TotalHistoryChart` component and panel between "Total ahorros" and "Mis inversiones".

**Tech Stack:** Python 3.11 + SQLModel (backend), React 19 + TypeScript + Recharts (frontend), pytest (tests).

---

## Files

| Action | Path |
|--------|------|
| Modify | `backend/app/schemas.py` |
| Modify | `backend/app/crud.py` |
| Modify | `backend/app/api.py` |
| Modify | `frontend/src/api/types.ts` |
| Modify | `frontend/src/api/endpoints.ts` |
| Modify | `frontend/src/pages/savings-page.tsx` |
| Modify | `backend/tests/test_savings.py` |

---

## Task 1: Add `SavingsTotalHistoryPoint` schema

**Files:**
- Modify: `backend/app/schemas.py` (after line 449, end of file)

- [ ] **Step 1: Add schema class**

Append to the end of `backend/app/schemas.py`:

```python
class SavingsTotalHistoryPoint(BaseModel):
    date: str
    total_ars: float
    total_usd: float
    total_in_ars: float | None
    total_in_usd: float | None
```

- [ ] **Step 2: Commit**

```bash
cd /Users/pablo/github/admin-consumos
git add backend/app/schemas.py
git commit -m "feat: add SavingsTotalHistoryPoint schema"
```

---

## Task 2: Implement `get_savings_total_history` in `crud.py` (TDD)

**Files:**
- Modify: `backend/app/crud.py` (append after `create_savings_exchange_rate`)
- Modify: `backend/tests/test_savings.py`

- [ ] **Step 1: Write the failing tests**

Open `backend/tests/test_savings.py`. Add at the bottom:

```python
class TestGetSavingsTotalHistory:
    from app.crud import get_savings_total_history  # noqa: E402 (resolved at class body time)

    def _make_ars_saving(self, session, two_persons):
        alice, _ = two_persons
        return create_saving(
            session=session,
            payload=SavingCreate(
                person_id=alice.id,
                investment_type="FCI",
                institution="BNA",
                currency=CurrencyCode.ARS,
            ),
        )

    def _make_usd_saving(self, session, two_persons):
        alice, _ = two_persons
        return create_saving(
            session=session,
            payload=SavingCreate(
                person_id=alice.id,
                investment_type="Bono",
                institution="BNA",
                currency=CurrencyCode.USD,
            ),
        )

    def test_no_savings_returns_empty(self, session):
        from app.crud import get_savings_total_history
        result = get_savings_total_history(session=session)
        assert result == []

    def test_no_snapshots_returns_empty(self, session, two_persons):
        from app.crud import get_savings_total_history
        self._make_ars_saving(session, two_persons)
        result = get_savings_total_history(session=session)
        assert result == []

    def test_single_ars_saving_two_snapshots(self, session, two_persons):
        from app.crud import get_savings_total_history
        saving = self._make_ars_saving(session, two_persons)
        create_saving_snapshot(
            session=session, saving_id=saving.id,
            payload=SavingSnapshotCreate(date=date(2025, 1, 1), amount=100_000),
        )
        create_saving_snapshot(
            session=session, saving_id=saving.id,
            payload=SavingSnapshotCreate(date=date(2025, 3, 1), amount=150_000),
        )
        result = get_savings_total_history(session=session)
        assert len(result) == 2
        assert result[0].date == "2025-01-01"
        assert result[0].total_ars == 100_000
        assert result[0].total_usd == 0.0
        assert result[0].total_in_ars is None  # no exchange rate
        assert result[1].date == "2025-03-01"
        assert result[1].total_ars == 150_000

    def test_forward_fill_across_savings(self, session, two_persons):
        """When saving B hasn't been updated on a date, its last known value is used."""
        from app.crud import get_savings_total_history
        ars = self._make_ars_saving(session, two_persons)
        usd = self._make_usd_saving(session, two_persons)
        # ARS saving: snapshot on Jan 1
        create_saving_snapshot(
            session=session, saving_id=ars.id,
            payload=SavingSnapshotCreate(date=date(2025, 1, 1), amount=100_000),
        )
        # USD saving: snapshot on Feb 1 only
        create_saving_snapshot(
            session=session, saving_id=usd.id,
            payload=SavingSnapshotCreate(date=date(2025, 2, 1), amount=500),
        )
        result = get_savings_total_history(session=session)
        # Two dates: 2025-01-01 and 2025-02-01
        assert len(result) == 2
        jan = result[0]
        feb = result[1]
        assert jan.date == "2025-01-01"
        assert jan.total_ars == 100_000
        assert jan.total_usd == 0.0  # USD saving has no snapshot yet on Jan 1
        assert feb.date == "2025-02-01"
        assert feb.total_ars == 100_000  # forward-filled from Jan 1
        assert feb.total_usd == 500

    def test_combined_totals_with_exchange_rate(self, session, two_persons):
        from app.crud import get_savings_total_history
        ars = self._make_ars_saving(session, two_persons)
        usd = self._make_usd_saving(session, two_persons)
        create_saving_snapshot(
            session=session, saving_id=ars.id,
            payload=SavingSnapshotCreate(date=date(2025, 3, 1), amount=100_000),
        )
        create_saving_snapshot(
            session=session, saving_id=usd.id,
            payload=SavingSnapshotCreate(date=date(2025, 3, 1), amount=100),
        )
        create_savings_exchange_rate(
            session=session,
            payload=SavingsExchangeRateCreate(date="2025-02-01", usd_buy=1000.0, usd_sell=1050.0),
        )
        result = get_savings_total_history(session=session)
        assert len(result) == 1
        point = result[0]
        assert point.total_ars == 100_000
        assert point.total_usd == 100
        assert point.total_in_ars == pytest.approx(100_000 + 100 * 1000.0)
        assert point.total_in_usd == pytest.approx(100_000 / 1050.0 + 100)

    def test_combined_null_when_no_prior_rate(self, session, two_persons):
        from app.crud import get_savings_total_history
        saving = self._make_ars_saving(session, two_persons)
        create_saving_snapshot(
            session=session, saving_id=saving.id,
            payload=SavingSnapshotCreate(date=date(2025, 1, 1), amount=50_000),
        )
        # Exchange rate registered AFTER the snapshot date
        create_savings_exchange_rate(
            session=session,
            payload=SavingsExchangeRateCreate(date="2025-02-01", usd_buy=1000.0, usd_sell=1050.0),
        )
        result = get_savings_total_history(session=session)
        assert len(result) == 1
        assert result[0].total_in_ars is None  # no rate at or before 2025-01-01
        assert result[0].total_in_usd is None

    def test_uses_closest_prior_exchange_rate(self, session, two_persons):
        """Uses the most recent rate at or before the snapshot date, not just the latest."""
        from app.crud import get_savings_total_history
        usd = self._make_usd_saving(session, two_persons)
        create_saving_snapshot(
            session=session, saving_id=usd.id,
            payload=SavingSnapshotCreate(date=date(2025, 3, 1), amount=100),
        )
        # Two rates: one before, one after the snapshot
        create_savings_exchange_rate(
            session=session,
            payload=SavingsExchangeRateCreate(date="2025-02-01", usd_buy=1000.0, usd_sell=1050.0),
        )
        create_savings_exchange_rate(
            session=session,
            payload=SavingsExchangeRateCreate(date="2025-04-01", usd_buy=2000.0, usd_sell=2100.0),
        )
        result = get_savings_total_history(session=session)
        assert len(result) == 1
        # Should use the Feb rate (1000), not the Apr rate (2000)
        assert result[0].total_in_ars == pytest.approx(100 * 1000.0)

    def test_returns_sorted_by_date(self, session, two_persons):
        from app.crud import get_savings_total_history
        saving = self._make_ars_saving(session, two_persons)
        # Add snapshots out of order
        create_saving_snapshot(
            session=session, saving_id=saving.id,
            payload=SavingSnapshotCreate(date=date(2025, 3, 1), amount=300_000),
        )
        create_saving_snapshot(
            session=session, saving_id=saving.id,
            payload=SavingSnapshotCreate(date=date(2025, 1, 1), amount=100_000),
        )
        result = get_savings_total_history(session=session)
        dates = [r.date for r in result]
        assert dates == sorted(dates)
```

Also add to the imports at the top of `test_savings.py`:
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
```
(The new `get_savings_total_history` is imported inline inside each test to keep the existing import block unchanged — or add it to the top-level import if preferred.)

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/pablo/github/admin-consumos
source .venv/bin/activate
cd backend && python -m pytest tests/test_savings.py::TestGetSavingsTotalHistory -v 2>&1 | head -30
```

Expected: multiple failures with `ImportError` or `AttributeError: module 'app.crud' has no attribute 'get_savings_total_history'`.

- [ ] **Step 3: Implement `get_savings_total_history` in `crud.py`**

First, add `SavingsTotalHistoryPoint` to the imports from `app.schemas` in `crud.py` (around line 32):

```python
from app.schemas import (
    CardCreate,
    CategoryCreate,
    CategoryUpdate,
    DebtorCreate,
    FamilyGoalCreate,
    FamilyGoalUpdate,
    FxRateUpsert,
    IncomeCreate,
    MonthlyBudgetCreate,
    PersonCreate,
    PurchaseCreate,
    PurchaseUpdate,
    SavingCreate,
    SavingUpdate,
    SavingSnapshotCreate,
    SavingsExchangeRateCreate,
    SavingsTotalHistoryPoint,  # <-- add this line
)
```

Then append after the `create_savings_exchange_rate` function (end of savings section, around line 1810):

```python
def get_savings_total_history(*, session: Session) -> list[SavingsTotalHistoryPoint]:
    """Return forward-filled total savings per snapshot date.

    For each unique date on which any snapshot was registered, computes:
      - total_ars: sum of ARS savings (forward-filled)
      - total_usd: sum of USD savings (forward-filled)
      - total_in_ars: combined total converted to ARS using closest prior exchange rate (None if unavailable)
      - total_in_usd: combined total converted to USD using closest prior exchange rate (None if unavailable)
    """
    from collections import defaultdict

    savings = list(session.exec(select(Saving)).all())
    if not savings:
        return []

    snapshots = list(
        session.exec(select(SavingSnapshot).order_by(SavingSnapshot.date.asc())).all()
    )
    if not snapshots:
        return []

    # Group snapshots by saving_id (already sorted ascending by date)
    snap_by_saving: dict[int, list[tuple[str, float]]] = defaultdict(list)
    for snap in snapshots:
        snap_by_saving[snap.saving_id].append((str(snap.date), snap.amount))

    currency_by_saving: dict[int, CurrencyCode] = {
        s.id: s.currency for s in savings if s.id is not None
    }

    all_dates = sorted({str(snap.date) for snap in snapshots})

    rates = list(
        session.exec(
            select(SavingsExchangeRate).order_by(SavingsExchangeRate.date.asc())
        ).all()
    )

    result: list[SavingsTotalHistoryPoint] = []
    for d in all_dates:
        total_ars = 0.0
        total_usd = 0.0

        for saving_id, snap_list in snap_by_saving.items():
            # Forward-fill: latest snapshot with date <= d
            value: float | None = None
            for snap_date, snap_amount in snap_list:
                if snap_date <= d:
                    value = snap_amount
                else:
                    break
            if value is not None:
                currency = currency_by_saving.get(saving_id)
                if currency == CurrencyCode.ARS:
                    total_ars += value
                elif currency == CurrencyCode.USD:
                    total_usd += value

        # Find the most recent exchange rate at or before d
        applicable_rate: SavingsExchangeRate | None = None
        for rate in rates:
            if rate.date <= d:
                applicable_rate = rate
            else:
                break

        total_in_ars: float | None = None
        total_in_usd: float | None = None
        if applicable_rate is not None:
            total_in_ars = total_ars + total_usd * applicable_rate.usd_buy
            total_in_usd = total_ars / applicable_rate.usd_sell + total_usd

        result.append(
            SavingsTotalHistoryPoint(
                date=d,
                total_ars=total_ars,
                total_usd=total_usd,
                total_in_ars=total_in_ars,
                total_in_usd=total_in_usd,
            )
        )

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/pablo/github/admin-consumos/backend
python -m pytest tests/test_savings.py::TestGetSavingsTotalHistory -v
```

Expected: all tests pass (0 failed).

- [ ] **Step 5: Run full backend test suite**

```bash
python -m pytest tests/ -q
```

Expected: 0 failed.

- [ ] **Step 6: Commit**

```bash
cd /Users/pablo/github/admin-consumos
git add backend/app/crud.py backend/app/schemas.py backend/tests/test_savings.py
git commit -m "feat: add get_savings_total_history CRUD with tests"
```

---

## Task 3: Expose `GET /api/savings/total-history` endpoint

**Files:**
- Modify: `backend/app/api.py`

- [ ] **Step 1: Add import of new CRUD function**

In `backend/app/api.py`, add `get_savings_total_history` to the `from app.crud import (...)` block (around line 44, after `update_saving`):

```python
    list_savings_exchange_rates,
    update_saving,
    get_savings_total_history,  # <-- add this line
    get_distinct_categories,
```

- [ ] **Step 2: Add schema import**

In `backend/app/api.py`, add `SavingsTotalHistoryPoint` to the `from app.schemas import (...)` block (around line 107, after `SavingsExchangeRateRead`):

```python
    SavingsExchangeRateCreate,
    SavingsExchangeRateRead,
    SavingsTotalHistoryPoint,  # <-- add this line
)
```

- [ ] **Step 3: Add endpoint**

In `backend/app/api.py`, find the line `@router.get("/savings", response_model=list[SavingRead])` (around line 750). Add the new endpoint **before** the existing `@router.patch("/savings/{saving_id}", ...)` route so it is never shadowed by a path-parameter route. Insert after the `post_saving` function body (after `@router.post("/savings", ...)` closes):

```python
@router.get("/savings/total-history", response_model=list[SavingsTotalHistoryPoint])
def get_savings_total_history_endpoint() -> list[SavingsTotalHistoryPoint]:
    with get_session() as session:
        return get_savings_total_history(session=session)
```

- [ ] **Step 4: Verify endpoint works**

Start the backend and hit the endpoint manually:

```bash
cd /Users/pablo/github/admin-consumos/backend
uvicorn app.main:app --port 8000 &
sleep 2
curl -s http://localhost:8000/api/savings/total-history | python3 -m json.tool
kill %1
```

Expected: JSON array (possibly empty if no snapshots in dev DB). No 404 or 500.

- [ ] **Step 5: Run full backend test suite**

```bash
python -m pytest tests/ -q
```

Expected: 0 failed.

- [ ] **Step 6: Commit**

```bash
cd /Users/pablo/github/admin-consumos
git add backend/app/api.py
git commit -m "feat: add GET /api/savings/total-history endpoint"
```

---

## Task 4: Add frontend type + API function

**Files:**
- Modify: `frontend/src/api/types.ts` (append)
- Modify: `frontend/src/api/endpoints.ts` (append)

- [ ] **Step 1: Add TypeScript type**

Open `frontend/src/api/types.ts`. Append at the end of the file:

```typescript
export interface SavingsTotalHistoryPoint {
  date: string
  total_ars: number
  total_usd: number
  total_in_ars: number | null
  total_in_usd: number | null
}
```

- [ ] **Step 2: Add API function**

Open `frontend/src/api/endpoints.ts`. After the last `fetchSavingsExchangeRates` function, append:

```typescript
export function fetchSavingsTotalHistory(): Promise<SavingsTotalHistoryPoint[]> {
  return getJson<SavingsTotalHistoryPoint[]>('/api/savings/total-history')
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/pablo/github/admin-consumos/frontend
npm run build 2>&1 | tail -10
```

Expected: no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/pablo/github/admin-consumos
git add frontend/src/api/types.ts frontend/src/api/endpoints.ts
git commit -m "feat: add SavingsTotalHistoryPoint type and fetchSavingsTotalHistory API function"
```

---

## Task 5: Add `TotalHistoryChart` component and panel to `savings-page.tsx`

**Files:**
- Modify: `frontend/src/pages/savings-page.tsx`

- [ ] **Step 1: Add import for new API function and type**

In `savings-page.tsx`, update the import from `'../api/endpoints'` to include `fetchSavingsTotalHistory`:

```typescript
import {
  createSaving,
  createSavingSnapshot,
  createSavingsExchangeRate,
  deleteSaving,
  fetchPeople,
  fetchSavingSnapshots,
  fetchSavings,
  fetchSavingsExchangeRates,
  fetchSavingsTotalHistory,  // <-- add this
} from '../api/endpoints'
```

Update the import from `'../api/types'` to include `SavingsTotalHistoryPoint`:

```typescript
import type { CurrencyCode, Saving, SavingSnapshot, SavingsExchangeRate, SavingsTotalHistoryPoint } from '../api/types'
```

- [ ] **Step 2: Add `TotalHistoryChart` component**

Insert this new component after the `SavingsTotalsPanel` component and before the `/* Main page */` comment (around line 408):

```tsx
/* ------------------------------------------------------------------ */
/*  Total history chart                                                */
/* ------------------------------------------------------------------ */

const TOTAL_LINES: Array<{ key: keyof SavingsTotalHistoryPoint; label: string; color: string }> = [
  { key: 'total_ars',    label: 'Total ARS',              color: LINE_COLORS[0] },
  { key: 'total_usd',    label: 'Total USD',              color: LINE_COLORS[1] },
  { key: 'total_in_ars', label: 'Total en ARS (combinado)', color: LINE_COLORS[2] },
  { key: 'total_in_usd', label: 'Total en USD (combinado)', color: LINE_COLORS[3] },
]

function TotalHistoryChart() {
  const [visibleLines, setVisibleLines] = useState<Set<string>>(
    new Set(['total_ars', 'total_usd'])
  )

  const query = useQuery({
    queryKey: ['savings-total-history'],
    queryFn: fetchSavingsTotalHistory,
  })

  const toggleLine = (key: string) => {
    setVisibleLines((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(id)
      return next
    })
  }

  if (query.isLoading) return <div className="muted">Cargando…</div>

  const data = query.data ?? []

  if (data.length === 0) {
    return <div className="muted">Sin snapshots registrados para mostrar el historial total</div>
  }

  const activeLines = TOTAL_LINES.filter(({ key }) => visibleLines.has(key))

  return (
    <>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
        {TOTAL_LINES.map(({ key, label, color }) => (
          <label
            key={key}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '0.9rem', color: 'var(--color-text)' }}
          >
            <input
              type="checkbox"
              checked={visibleLines.has(key)}
              onChange={() => toggleLine(key)}
            />
            <span style={{ color }}>{label}</span>
          </label>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="date" stroke="var(--color-text-secondary)" style={{ fontSize: '0.85rem' }} />
          <YAxis
            stroke="var(--color-text-secondary)"
            style={{ fontSize: '0.85rem' }}
            tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '6px',
              fontSize: '0.9rem',
            }}
            formatter={(value, name) => {
              const line = TOTAL_LINES.find((l) => l.key === String(name))
              const isUsd = String(name).includes('usd')
              const numValue = Number(value)
              const formatted = isUsd
                ? `U$S ${numValue.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                : `$${numValue.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
              return [formatted, line?.label ?? String(name)]
            }}
          />
          {activeLines.map(({ key, color }) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={color}
              strokeWidth={2}
              dot={{ r: 4 }}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </>
  )
}
```

**Fix typo in toggleLine:** The `add(id)` above is a typo — it should be `add(key)`. Here is the correct `toggleLine` function:

```typescript
  const toggleLine = (key: string) => {
    setVisibleLines((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }
```

- [ ] **Step 3: Add the panel in `SavingsPage`**

In the `SavingsPage` component, the JSX currently starts with `<SavingsTotalsPanel savings={savings} />` followed by the "Mis inversiones" panel. Insert the new panel between them:

```tsx
      <SavingsTotalsPanel savings={savings} />

      {/* ---- Panel: Total history chart ---- */}
      <div className="panel">
        <div className="panelTitle">Evolución del total</div>
        <TotalHistoryChart />
      </div>

      {/* ---- Panel 1: Table ---- */}
      <div className="panel">
```

- [ ] **Step 4: Verify TypeScript compiles**

```bash
cd /Users/pablo/github/admin-consumos/frontend
npm run build 2>&1 | tail -15
```

Expected: 0 TypeScript errors, build succeeds.

- [ ] **Step 5: Manual smoke test**

Start the app and navigate to the Savings page:

```bash
cd /Users/pablo/github/admin-consumos
./start.sh
```

Open `http://localhost:5173` → Ahorros. Verify:
- "Evolución del total" panel appears between "Total ahorros" and "Mis inversiones"
- If there are snapshots: chart renders with the selected lines
- Checkboxes toggle lines on/off
- Combined lines (total_in_ars / total_in_usd) show gaps on dates without an exchange rate

- [ ] **Step 6: Commit**

```bash
cd /Users/pablo/github/admin-consumos
git add frontend/src/pages/savings-page.tsx
git commit -m "feat: add TotalHistoryChart panel to savings page"
```

---

## Task 6: Final verification

- [ ] **Step 1: Run full backend test suite**

```bash
cd /Users/pablo/github/admin-consumos/backend
source ../.venv/bin/activate
python -m pytest tests/ -q
```

Expected: 0 failed.

- [ ] **Step 2: Run frontend build**

```bash
cd /Users/pablo/github/admin-consumos/frontend
npm run build
```

Expected: 0 errors.

- [ ] **Step 3: Run frontend tests**

```bash
npm run test:run
```

Expected: 0 failed.

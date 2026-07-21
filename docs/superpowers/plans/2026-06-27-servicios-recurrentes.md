# Servicios Recurrentes Implementation Plan

> **Status: DONE.** Implemented and merged via PR #15 (`fix/servicios-mobile-layout`), commits `cee1fe6`..`24952f1`. All checkboxes below reflect the completed state.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a `/servicios` module to track recurring household bills (gas, electricity, taxes) with per-month payment status and a dashboard alert widget.

**Architecture:** Two new SQLModel tables (`Service`, `ServicePayment`) with CRUD + business logic in `crud.py`, REST endpoints in `api.py`, a new frontend page `servicios-page.tsx` with semaphore card grid, and a dashboard summary widget. Semaphore status is computed client-side using the browser's local date.

**Tech Stack:** Python 3.11 / SQLModel / FastAPI (backend) · React 19 + TypeScript + Vite + React Query (frontend) · pytest (backend tests) · Vitest (frontend tests)

## Global Constraints

- Python 3.11+ required (`StrEnum` usage in codebase)
- All API routes under `/api` prefix
- `year_month` fields: regex `^\d{4}-(0[1-9]|1[0-2])$`
- `amount > 0` enforced in Pydantic (not nullable-zero)
- Uniqueness `(service_id, year_month)` → HTTP 409 on duplicate create
- DELETE of `Service` with existing payments → HTTP 409
- Semaphore states computed in frontend from client date; backend only returns `due_date` and `paid_date`
- Use existing CSS class names from `App.css`; no new CSS frameworks
- Run `python -m pytest tests/ -q` and `npm run test:run` + `npm run build` before marking done

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `backend/app/models.py` | Modify | Add `Service` and `ServicePayment` SQLModel tables |
| `backend/app/db.py` | Modify | Add `_migrate_add_service_tables()` migration |
| `backend/app/schemas.py` | Modify | Add service/payment Pydantic schemas |
| `backend/app/crud.py` | Modify | Add CRUD + suggested_due_date + summary logic |
| `backend/app/api.py` | Modify | Add 7 new REST endpoints |
| `backend/tests/test_services.py` | Create | All backend tests for this module |
| `frontend/src/api/types.ts` | Modify | Add `Service`, `ServicePaymentRead`, `ServicePaymentWithMeta`, `ServicePaymentSummary` interfaces |
| `frontend/src/api/endpoints.ts` | Modify | Add API client functions |
| `frontend/src/utils/services.ts` | Create | `getServiceStatus()` pure function (semaphore) |
| `frontend/src/utils/services.test.ts` | Create | Unit tests for semaphore logic |
| `frontend/src/pages/servicios-page.tsx` | Create | Full services page with card grid |
| `frontend/src/App.tsx` | Modify | Add `/servicios` route + nav item |
| `frontend/src/pages/dashboard-page.tsx` | Modify | Add `ServicePaymentSummary` widget |

---

## Task 1: Backend Models + DB Migration

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/db.py`

**Interfaces:**
- Produces: `Service` class, `ServicePayment` class (used by Tasks 2, 3, 4)

- [x] **Step 1: Write the failing test**

In `backend/tests/test_services.py` (create it):

```python
"""Tests for Service and ServicePayment models and CRUD."""
from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.models import Service, ServicePayment


class TestModels:
    def test_service_table_exists(self, session: Session):
        """Service table can be created and queried."""
        svc = Service(name="Gas")
        session.add(svc)
        session.commit()
        session.refresh(svc)
        assert svc.id is not None
        assert svc.name == "Gas"
        assert svc.is_active is True
        assert svc.sort_order == 0

    def test_service_payment_unique_constraint(self, session: Session):
        """Inserting duplicate (service_id, year_month) raises IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        svc = Service(name="Luz")
        session.add(svc)
        session.commit()
        session.refresh(svc)

        p1 = ServicePayment(service_id=svc.id, year_month="2026-06")
        session.add(p1)
        session.commit()

        p2 = ServicePayment(service_id=svc.id, year_month="2026-06")
        session.add(p2)
        with pytest.raises(IntegrityError):
            session.commit()
```

- [x] **Step 2: Run test to verify it fails**

```bash
cd /Users/pablo/github/admin-consumos
source .venv/bin/activate
python -m pytest backend/tests/test_services.py::TestModels -v
```
Expected: FAIL with `ImportError: cannot import name 'Service' from 'app.models'`

- [x] **Step 3: Add models to `backend/app/models.py`**

Add after the `SavingsExchangeRate` class at the end of the file:

```python
class Service(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    expected_amount: Optional[float] = None
    typical_due_day: Optional[int] = None  # 1–31
    is_active: bool = Field(default=True)
    sort_order: int = Field(default=0)


class ServicePayment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("service_id", "year_month", name="uq_servicepayment_service_month"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    service_id: int = Field(foreign_key="service.id", index=True)
    year_month: str = Field(index=True)  # YYYY-MM
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    amount: Optional[float] = None
    notes: Optional[str] = None
```

- [x] **Step 4: Add migration to `backend/app/db.py`**

In `init_db()`, add a call to the new migration function before the return:

```python
def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_add_columns()
    _migrate_dedupe_installments()
    _migrate_lowercase_descriptions()
    _migrate_uppercase_categories()
    _migrate_reorganize_categories()
    _migrate_add_service_tables()   # <-- add this line
```

Then add the function itself at the end of `db.py`:

```python
def _migrate_add_service_tables() -> None:
    """Create service and servicepayment tables if they don't exist (idempotent)."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS service (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                expected_amount REAL,
                typical_due_day INTEGER,
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS servicepayment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL REFERENCES service(id),
                year_month TEXT NOT NULL,
                due_date TEXT,
                paid_date TEXT,
                amount REAL,
                notes TEXT,
                CONSTRAINT uq_servicepayment_service_month UNIQUE (service_id, year_month)
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_servicepayment_service_id ON servicepayment(service_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_servicepayment_year_month ON servicepayment(year_month)"
        ))
        conn.commit()
```

- [x] **Step 5: Run tests to verify they pass**

```bash
python -m pytest backend/tests/test_services.py::TestModels -v
```
Expected: PASS (2 tests)

- [x] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/db.py backend/tests/test_services.py
git commit -m "feat(servicios): add Service and ServicePayment models + migration"
```

---

## Task 2: Backend Schemas

**Files:**
- Modify: `backend/app/schemas.py`

**Interfaces:**
- Produces: `ServiceCreate`, `ServiceRead`, `ServiceUpdate`, `ServicePaymentCreate`, `ServicePaymentUpdate`, `ServicePaymentRead`, `ServicePaymentWithMeta`, `ServicePaymentSummary` (used by Tasks 3 and 4)

- [x] **Step 1: Write the failing test**

Add to `backend/tests/test_services.py`:

```python
class TestSchemas:
    def test_service_create_typical_due_day_valid(self):
        from app.schemas import ServiceCreate
        s = ServiceCreate(name="Gas", typical_due_day=20)
        assert s.typical_due_day == 20

    def test_service_create_typical_due_day_out_of_range(self):
        from app.schemas import ServiceCreate
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            ServiceCreate(name="Gas", typical_due_day=32)

    def test_service_payment_create_amount_must_be_positive(self):
        from app.schemas import ServicePaymentCreate
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            ServicePaymentCreate(service_id=1, year_month="2026-06", amount=-100)

    def test_service_payment_create_year_month_regex(self):
        from app.schemas import ServicePaymentCreate
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            ServicePaymentCreate(service_id=1, year_month="2026-13")

    def test_service_payment_create_null_amount_ok(self):
        from app.schemas import ServicePaymentCreate
        p = ServicePaymentCreate(service_id=1, year_month="2026-06")
        assert p.amount is None
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest backend/tests/test_services.py::TestSchemas -v
```
Expected: FAIL with `ImportError: cannot import name 'ServiceCreate' from 'app.schemas'`

- [x] **Step 3: Add schemas to `backend/app/schemas.py`**

Add at the end of the file (after the last class):

```python
class ServiceCreate(BaseModel):
    name: str
    expected_amount: Optional[float] = None
    typical_due_day: Optional[int] = Field(default=None, ge=1, le=31)
    is_active: bool = True
    sort_order: int = 0


class ServiceRead(BaseModel):
    id: int
    name: str
    expected_amount: Optional[float]
    typical_due_day: Optional[int]
    is_active: bool
    sort_order: int


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    expected_amount: Optional[float] = None
    typical_due_day: Optional[int] = Field(default=None, ge=1, le=31)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ServicePaymentCreate(BaseModel):
    service_id: int
    year_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    amount: Optional[float] = Field(default=None, gt=0)
    notes: Optional[str] = None


class ServicePaymentUpdate(BaseModel):
    due_date: Optional[date] = None
    paid_date: Optional[date] = None
    amount: Optional[float] = Field(default=None, gt=0)
    notes: Optional[str] = None


class ServicePaymentRead(BaseModel):
    id: int
    service_id: int
    year_month: str
    due_date: Optional[date]
    paid_date: Optional[date]
    amount: Optional[float]
    notes: Optional[str]


class ServicePaymentWithMeta(BaseModel):
    service: ServiceRead
    payment: Optional[ServicePaymentRead]
    suggested_due_date: Optional[date]


class ServicePaymentSummary(BaseModel):
    unpaid_count: int
    overdue_names: list[str]
    due_soon_names: list[str]
```

- [x] **Step 4: Run tests to verify they pass**

```bash
python -m pytest backend/tests/test_services.py::TestSchemas -v
```
Expected: PASS (5 tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_services.py
git commit -m "feat(servicios): add service schemas with validation"
```

---

## Task 3: Backend CRUD Functions

**Files:**
- Modify: `backend/app/crud.py`

**Interfaces:**
- Consumes: `Service`, `ServicePayment` (from models), all service schemas (from schemas)
- Produces: `list_services`, `create_service`, `update_service`, `delete_service`, `get_service_payments_for_month`, `upsert_service_payment`, `update_service_payment`, `delete_service_payment`, `get_service_payment_summary` (used by Task 4)

- [x] **Step 1: Write the failing tests**

Add to `backend/tests/test_services.py`:

```python
from datetime import date as dt_date


class TestServiceCRUD:
    def test_create_and_list_services(self, session: Session):
        from app.crud import create_service, list_services
        from app.schemas import ServiceCreate
        create_service(session, ServiceCreate(name="Gas", sort_order=0))
        create_service(session, ServiceCreate(name="Luz", sort_order=1, is_active=False))
        all_svcs = list_services(session)
        assert len(all_svcs) == 2
        assert all_svcs[0].name == "Gas"

    def test_update_service(self, session: Session):
        from app.crud import create_service, update_service
        from app.schemas import ServiceCreate, ServiceUpdate
        svc = create_service(session, ServiceCreate(name="Gas"))
        updated = update_service(session, svc.id, ServiceUpdate(name="Gas Natural", expected_amount=15000))
        assert updated.name == "Gas Natural"
        assert updated.expected_amount == 15000

    def test_update_service_not_found(self, session: Session):
        from app.crud import update_service
        from app.schemas import ServiceUpdate
        with pytest.raises(ValueError, match="not found"):
            update_service(session, 999, ServiceUpdate(name="X"))

    def test_delete_service_without_payments(self, session: Session):
        from app.crud import create_service, delete_service
        from app.schemas import ServiceCreate
        svc = create_service(session, ServiceCreate(name="Gas"))
        delete_service(session, svc.id)
        from sqlmodel import select
        result = session.exec(select(Service).where(Service.id == svc.id)).first()
        assert result is None

    def test_delete_service_with_payments_raises_409(self, session: Session):
        from app.crud import create_service, delete_service, upsert_service_payment
        from app.schemas import ServiceCreate, ServicePaymentCreate
        svc = create_service(session, ServiceCreate(name="Luz"))
        upsert_service_payment(session, ServicePaymentCreate(service_id=svc.id, year_month="2026-06"))
        with pytest.raises(ValueError, match="pagos"):
            delete_service(session, svc.id)


class TestServicePaymentCRUD:
    def test_upsert_creates_new(self, session: Session):
        from app.crud import create_service, upsert_service_payment
        from app.schemas import ServiceCreate, ServicePaymentCreate
        svc = create_service(session, ServiceCreate(name="Gas"))
        p = upsert_service_payment(session, ServicePaymentCreate(
            service_id=svc.id, year_month="2026-06",
            due_date=dt_date(2026, 6, 20), paid_date=dt_date(2026, 6, 18), amount=15000
        ))
        assert p.id is not None
        assert p.amount == 15000

    def test_upsert_updates_existing(self, session: Session):
        from app.crud import create_service, upsert_service_payment
        from app.schemas import ServiceCreate, ServicePaymentCreate
        svc = create_service(session, ServiceCreate(name="Gas"))
        p1 = upsert_service_payment(session, ServicePaymentCreate(
            service_id=svc.id, year_month="2026-06", due_date=dt_date(2026, 6, 20)
        ))
        p2 = upsert_service_payment(session, ServicePaymentCreate(
            service_id=svc.id, year_month="2026-06", amount=16000, paid_date=dt_date(2026, 6, 18)
        ))
        assert p1.id == p2.id  # same record updated
        assert p2.amount == 16000

    def test_update_payment_unmark_preserves_due_date(self, session: Session):
        from app.crud import create_service, upsert_service_payment, update_service_payment
        from app.schemas import ServiceCreate, ServicePaymentCreate, ServicePaymentUpdate
        svc = create_service(session, ServiceCreate(name="Luz"))
        p = upsert_service_payment(session, ServicePaymentCreate(
            service_id=svc.id, year_month="2026-06",
            due_date=dt_date(2026, 6, 15), paid_date=dt_date(2026, 6, 14), amount=10000
        ))
        updated = update_service_payment(session, p.id, ServicePaymentUpdate(
            paid_date=None, amount=None, notes=None
        ))
        assert updated.paid_date is None
        assert updated.amount is None
        assert updated.due_date == dt_date(2026, 6, 15)  # preserved

    def test_delete_payment(self, session: Session):
        from app.crud import create_service, upsert_service_payment, delete_service_payment
        from app.schemas import ServiceCreate, ServicePaymentCreate
        svc = create_service(session, ServiceCreate(name="Luz"))
        p = upsert_service_payment(session, ServicePaymentCreate(service_id=svc.id, year_month="2026-06"))
        delete_service_payment(session, p.id)
        result = session.exec(select(ServicePayment).where(ServicePayment.id == p.id)).first()
        assert result is None

    def test_delete_payment_not_found(self, session: Session):
        from app.crud import delete_service_payment
        with pytest.raises(ValueError, match="not found"):
            delete_service_payment(session, 999)


class TestSuggestedDueDate:
    def test_suggested_from_previous_month_payment(self, session: Session):
        from app.crud import create_service, upsert_service_payment, get_service_payments_for_month
        from app.schemas import ServiceCreate, ServicePaymentCreate
        svc = create_service(session, ServiceCreate(name="Gas"))
        # May payment had due_date=15
        upsert_service_payment(session, ServicePaymentCreate(
            service_id=svc.id, year_month="2026-05",
            due_date=dt_date(2026, 5, 15)
        ))
        results = get_service_payments_for_month(session, "2026-06")
        item = next(r for r in results if r.service.id == svc.id)
        assert item.suggested_due_date == dt_date(2026, 6, 15)

    def test_suggested_from_typical_due_day(self, session: Session):
        from app.crud import create_service, get_service_payments_for_month
        from app.schemas import ServiceCreate
        svc = create_service(session, ServiceCreate(name="Luz", typical_due_day=10))
        results = get_service_payments_for_month(session, "2026-06")
        item = next(r for r in results if r.service.id == svc.id)
        assert item.suggested_due_date == dt_date(2026, 6, 10)

    def test_suggested_clamps_day_31_to_last_day_of_february(self, session: Session):
        from app.crud import create_service, get_service_payments_for_month
        from app.schemas import ServiceCreate
        svc = create_service(session, ServiceCreate(name="Agua", typical_due_day=31))
        results = get_service_payments_for_month(session, "2026-02")
        item = next(r for r in results if r.service.id == svc.id)
        assert item.suggested_due_date == dt_date(2026, 2, 28)

    def test_suggested_null_when_no_data(self, session: Session):
        from app.crud import create_service, get_service_payments_for_month
        from app.schemas import ServiceCreate
        svc = create_service(session, ServiceCreate(name="Municipal"))
        results = get_service_payments_for_month(session, "2026-06")
        item = next(r for r in results if r.service.id == svc.id)
        assert item.suggested_due_date is None

    def test_prev_month_takes_precedence_over_typical_due_day(self, session: Session):
        from app.crud import create_service, upsert_service_payment, get_service_payments_for_month
        from app.schemas import ServiceCreate, ServicePaymentCreate
        svc = create_service(session, ServiceCreate(name="Gas", typical_due_day=20))
        # Prev month had due_date=10 (different from typical)
        upsert_service_payment(session, ServicePaymentCreate(
            service_id=svc.id, year_month="2026-05", due_date=dt_date(2026, 5, 10)
        ))
        results = get_service_payments_for_month(session, "2026-06")
        item = next(r for r in results if r.service.id == svc.id)
        assert item.suggested_due_date == dt_date(2026, 6, 10)  # from prev month, not typical_due_day=20

    def test_inactive_services_not_returned(self, session: Session):
        from app.crud import create_service, get_service_payments_for_month
        from app.schemas import ServiceCreate
        create_service(session, ServiceCreate(name="Inactive", is_active=False))
        results = get_service_payments_for_month(session, "2026-06")
        assert all(r.service.is_active for r in results)


class TestServicePaymentSummary:
    def test_summary_counts_unpaid(self, session: Session):
        from app.crud import create_service, upsert_service_payment, get_service_payment_summary
        from app.schemas import ServiceCreate, ServicePaymentCreate
        svc_gas = create_service(session, ServiceCreate(name="Gas"))
        svc_luz = create_service(session, ServiceCreate(name="Luz"))
        # Gas: paid; Luz: unpaid with past due_date (overdue)
        upsert_service_payment(session, ServicePaymentCreate(
            service_id=svc_gas.id, year_month="2026-06",
            paid_date=dt_date(2026, 6, 10), amount=15000
        ))
        upsert_service_payment(session, ServicePaymentCreate(
            service_id=svc_luz.id, year_month="2026-06",
            due_date=dt_date(2026, 6, 1)  # overdue (past)
        ))
        today = dt_date(2026, 6, 27)
        summary = get_service_payment_summary(session, "2026-06", today)
        assert summary["unpaid_count"] == 1
        assert "Luz" in summary["overdue_names"]
        assert summary["due_soon_names"] == []

    def test_summary_due_soon(self, session: Session):
        from app.crud import create_service, upsert_service_payment, get_service_payment_summary
        from app.schemas import ServiceCreate, ServicePaymentCreate
        svc = create_service(session, ServiceCreate(name="Agua"))
        upsert_service_payment(session, ServicePaymentCreate(
            service_id=svc.id, year_month="2026-06",
            due_date=dt_date(2026, 6, 29)  # 2 days from today=2026-06-27
        ))
        today = dt_date(2026, 6, 27)
        summary = get_service_payment_summary(session, "2026-06", today)
        assert summary["unpaid_count"] == 1
        assert "Agua" in summary["due_soon_names"]
        assert summary["overdue_names"] == []

    def test_summary_all_paid_returns_zero(self, session: Session):
        from app.crud import create_service, upsert_service_payment, get_service_payment_summary
        from app.schemas import ServiceCreate, ServicePaymentCreate
        svc = create_service(session, ServiceCreate(name="Gas"))
        upsert_service_payment(session, ServicePaymentCreate(
            service_id=svc.id, year_month="2026-06",
            paid_date=dt_date(2026, 6, 10), amount=15000
        ))
        today = dt_date(2026, 6, 27)
        summary = get_service_payment_summary(session, "2026-06", today)
        assert summary["unpaid_count"] == 0
        assert summary["overdue_names"] == []
        assert summary["due_soon_names"] == []

    def test_summary_active_service_without_payment_counted_as_unpaid(self, session: Session):
        from app.crud import create_service, get_service_payment_summary
        from app.schemas import ServiceCreate
        create_service(session, ServiceCreate(name="Gas"))
        today = dt_date(2026, 6, 27)
        summary = get_service_payment_summary(session, "2026-06", today)
        assert summary["unpaid_count"] == 1
```

- [x] **Step 2: Run tests to verify they fail**

```bash
python -m pytest backend/tests/test_services.py::TestServiceCRUD backend/tests/test_services.py::TestServicePaymentCRUD backend/tests/test_services.py::TestSuggestedDueDate backend/tests/test_services.py::TestServicePaymentSummary -v
```
Expected: FAIL with `ImportError: cannot import name 'create_service' from 'app.crud'`

- [x] **Step 3: Add CRUD functions to `backend/app/crud.py`**

First, add imports at the top of `crud.py` (near the existing imports):

```python
import calendar  # add near the top with other stdlib imports
```

Then add these imports to the existing `from app.models import ...` line — append `Service, ServicePayment` to it.

Then add these imports to the existing `from app.schemas import ...` line — append:
```
ServiceCreate, ServiceRead, ServiceUpdate,
ServicePaymentCreate, ServicePaymentUpdate, ServicePaymentRead,
ServicePaymentWithMeta
```

Then add all the service functions at the end of `crud.py`:

```python
# ─── Services ────────────────────────────────────────────────────────────────

def list_services(session: Session) -> list[Service]:
    return list(session.exec(select(Service).order_by(Service.sort_order, Service.id)).all())


def create_service(session: Session, payload: ServiceCreate) -> Service:
    svc = Service(**payload.model_dump())
    session.add(svc)
    session.commit()
    session.refresh(svc)
    return svc


def update_service(session: Session, service_id: int, payload: ServiceUpdate) -> Service:
    svc = session.get(Service, service_id)
    if svc is None:
        raise ValueError(f"Service {service_id} not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(svc, field, value)
    session.add(svc)
    session.commit()
    session.refresh(svc)
    return svc


def delete_service(session: Session, service_id: int) -> None:
    svc = session.get(Service, service_id)
    if svc is None:
        raise ValueError(f"Service {service_id} not found")
    has_payments = session.exec(
        select(ServicePayment).where(ServicePayment.service_id == service_id)
    ).first()
    if has_payments:
        raise ValueError("Este servicio tiene pagos registrados. Usá is_active=false para desactivarlo.")
    session.delete(svc)
    session.commit()


def _suggested_due_date_for(session: Session, service: Service, year_month: str) -> Optional[date]:
    """Compute suggested due_date: previous month's due_date + 1 month, or typical_due_day."""
    year, month = int(year_month[:4]), int(year_month[5:7])
    total_prev = year * 12 + (month - 1) - 1
    prev_year, prev_month_0 = divmod(total_prev, 12)
    prev_ym = f"{prev_year:04d}-{prev_month_0 + 1:02d}"

    prev_payment = session.exec(
        select(ServicePayment).where(
            ServicePayment.service_id == service.id,
            ServicePayment.year_month == prev_ym,
            ServicePayment.due_date.is_not(None),  # type: ignore[attr-defined]
        )
    ).first()

    if prev_payment and prev_payment.due_date:
        max_day = calendar.monthrange(year, month)[1]
        day = min(prev_payment.due_date.day, max_day)
        return date(year, month, day)

    if service.typical_due_day:
        max_day = calendar.monthrange(year, month)[1]
        day = min(service.typical_due_day, max_day)
        return date(year, month, day)

    return None


def get_service_payments_for_month(session: Session, year_month: str) -> list[ServicePaymentWithMeta]:
    services = session.exec(
        select(Service).where(Service.is_active == True).order_by(Service.sort_order, Service.id)  # noqa: E712
    ).all()

    results = []
    for svc in services:
        payment = session.exec(
            select(ServicePayment).where(
                ServicePayment.service_id == svc.id,
                ServicePayment.year_month == year_month,
            )
        ).first()

        suggested = None if payment else _suggested_due_date_for(session, svc, year_month)

        results.append(ServicePaymentWithMeta(
            service=ServiceRead(**svc.model_dump()),
            payment=ServicePaymentRead(**payment.model_dump()) if payment else None,
            suggested_due_date=suggested,
        ))
    return results


def upsert_service_payment(session: Session, payload: ServicePaymentCreate) -> ServicePayment:
    existing = session.exec(
        select(ServicePayment).where(
            ServicePayment.service_id == payload.service_id,
            ServicePayment.year_month == payload.year_month,
        )
    ).first()

    if existing:
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field not in ("service_id", "year_month"):
                setattr(existing, field, value)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    p = ServicePayment(**payload.model_dump())
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def update_service_payment(session: Session, payment_id: int, payload: ServicePaymentUpdate) -> ServicePayment:
    p = session.get(ServicePayment, payment_id)
    if p is None:
        raise ValueError(f"ServicePayment {payment_id} not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def delete_service_payment(session: Session, payment_id: int) -> None:
    p = session.get(ServicePayment, payment_id)
    if p is None:
        raise ValueError(f"ServicePayment {payment_id} not found")
    session.delete(p)
    session.commit()


def get_service_payment_summary(session: Session, year_month: str, today: date) -> dict:
    services = session.exec(
        select(Service).where(Service.is_active == True).order_by(Service.sort_order, Service.id)  # noqa: E712
    ).all()

    unpaid_count = 0
    overdue_names: list[str] = []
    due_soon_names: list[str] = []

    for svc in services:
        payment = session.exec(
            select(ServicePayment).where(
                ServicePayment.service_id == svc.id,
                ServicePayment.year_month == year_month,
            )
        ).first()

        if payment and payment.paid_date is not None:
            continue  # paid — skip

        unpaid_count += 1
        due_date = payment.due_date if payment else None

        if due_date is None:
            continue

        if due_date < today:
            overdue_names.append(svc.name)
        elif due_date <= date(today.year, today.month, today.day + 3) if today.day + 3 <= calendar.monthrange(today.year, today.month)[1] else _add_days(today, 3):
            due_soon_names.append(svc.name)

    return {
        "unpaid_count": unpaid_count,
        "overdue_names": overdue_names,
        "due_soon_names": due_soon_names,
    }
```

Wait, the due_soon calculation has a bug in the plan. Let me fix it with a cleaner approach. Replace the `get_service_payment_summary` function with:

```python
def get_service_payment_summary(session: Session, year_month: str, today: date) -> dict:
    from datetime import timedelta

    services = session.exec(
        select(Service).where(Service.is_active == True).order_by(Service.sort_order, Service.id)  # noqa: E712
    ).all()

    unpaid_count = 0
    overdue_names: list[str] = []
    due_soon_names: list[str] = []
    cutoff = today + timedelta(days=3)

    for svc in services:
        payment = session.exec(
            select(ServicePayment).where(
                ServicePayment.service_id == svc.id,
                ServicePayment.year_month == year_month,
            )
        ).first()

        if payment and payment.paid_date is not None:
            continue

        unpaid_count += 1
        due_date = payment.due_date if payment else None

        if due_date is None:
            continue
        if due_date < today:
            overdue_names.append(svc.name)
        elif due_date <= cutoff:
            due_soon_names.append(svc.name)

    return {
        "unpaid_count": unpaid_count,
        "overdue_names": overdue_names,
        "due_soon_names": due_soon_names,
    }
```

The complete `get_service_payment_summary` to add to `crud.py`:

```python
def get_service_payment_summary(session: Session, year_month: str, today: date) -> dict:
    from datetime import timedelta

    services = session.exec(
        select(Service).where(Service.is_active == True).order_by(Service.sort_order, Service.id)  # noqa: E712
    ).all()

    unpaid_count = 0
    overdue_names: list[str] = []
    due_soon_names: list[str] = []
    cutoff = today + timedelta(days=3)

    for svc in services:
        payment = session.exec(
            select(ServicePayment).where(
                ServicePayment.service_id == svc.id,
                ServicePayment.year_month == year_month,
            )
        ).first()

        if payment and payment.paid_date is not None:
            continue

        unpaid_count += 1
        due_date = payment.due_date if payment else None

        if due_date is None:
            continue
        if due_date < today:
            overdue_names.append(svc.name)
        elif due_date <= cutoff:
            due_soon_names.append(svc.name)

    return {
        "unpaid_count": unpaid_count,
        "overdue_names": overdue_names,
        "due_soon_names": due_soon_names,
    }
```

- [x] **Step 4: Run tests to verify they pass**

```bash
python -m pytest backend/tests/test_services.py -v --ignore=backend/tests/test_services.py -k "not TestSchemas and not TestModels"
python -m pytest backend/tests/test_services.py -v
```

Run the full test file:
```bash
python -m pytest backend/tests/test_services.py -v
```
Expected: All tests PASS

- [x] **Step 5: Run full suite to check for regressions**

```bash
python -m pytest backend/tests/ -q
```
Expected: 0 failures

- [x] **Step 6: Commit**

```bash
git add backend/app/crud.py backend/tests/test_services.py
git commit -m "feat(servicios): add service CRUD functions with suggested due_date logic"
```

---

## Task 4: Backend API Endpoints

**Files:**
- Modify: `backend/app/api.py`

**Interfaces:**
- Consumes: all `crud.py` service functions and all service schemas
- Produces: 7 REST endpoints under `/api`

- [x] **Step 1: Write the failing integration test**

Add to `backend/tests/test_services.py`:

```python
class TestServiceAPI:
    def test_create_and_get_services(self, client):
        r = client.post("/api/services", json={"name": "Gas", "typical_due_day": 20, "sort_order": 0})
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Gas"
        assert data["typical_due_day"] == 20

        r2 = client.get("/api/services")
        assert r2.status_code == 200
        assert len(r2.json()) == 1

    def test_update_service(self, client):
        r = client.post("/api/services", json={"name": "Gas"})
        svc_id = r.json()["id"]
        r2 = client.put(f"/api/services/{svc_id}", json={"name": "Gas Natural", "is_active": True})
        assert r2.status_code == 200
        assert r2.json()["name"] == "Gas Natural"

    def test_delete_service_no_payments(self, client):
        r = client.post("/api/services", json={"name": "Temp"})
        svc_id = r.json()["id"]
        r2 = client.delete(f"/api/services/{svc_id}")
        assert r2.status_code == 204

    def test_delete_service_with_payments_returns_409(self, client):
        r = client.post("/api/services", json={"name": "Gas"})
        svc_id = r.json()["id"]
        client.post("/api/service-payments", json={"service_id": svc_id, "year_month": "2026-06"})
        r2 = client.delete(f"/api/services/{svc_id}")
        assert r2.status_code == 409

    def test_get_service_payments_for_month(self, client):
        r = client.post("/api/services", json={"name": "Gas", "typical_due_day": 15})
        svc_id = r.json()["id"]
        r2 = client.get("/api/service-payments?year_month=2026-06")
        assert r2.status_code == 200
        items = r2.json()
        assert len(items) == 1
        assert items[0]["service"]["id"] == svc_id
        assert items[0]["payment"] is None
        assert items[0]["suggested_due_date"] == "2026-06-15"

    def test_upsert_service_payment(self, client):
        r = client.post("/api/services", json={"name": "Luz"})
        svc_id = r.json()["id"]
        r2 = client.post("/api/service-payments", json={
            "service_id": svc_id, "year_month": "2026-06",
            "due_date": "2026-06-20", "paid_date": "2026-06-18", "amount": 10000
        })
        assert r2.status_code == 201
        assert r2.json()["amount"] == 10000

    def test_upsert_duplicate_updates_in_place(self, client):
        r = client.post("/api/services", json={"name": "Gas"})
        svc_id = r.json()["id"]
        r1 = client.post("/api/service-payments", json={"service_id": svc_id, "year_month": "2026-06"})
        r2 = client.post("/api/service-payments", json={"service_id": svc_id, "year_month": "2026-06", "amount": 5000})
        assert r2.status_code == 200
        assert r2.json()["id"] == r1.json()["id"]
        assert r2.json()["amount"] == 5000

    def test_put_service_payment(self, client):
        r = client.post("/api/services", json={"name": "Gas"})
        svc_id = r.json()["id"]
        rp = client.post("/api/service-payments", json={"service_id": svc_id, "year_month": "2026-06", "due_date": "2026-06-20"})
        pid = rp.json()["id"]
        r2 = client.put(f"/api/service-payments/{pid}", json={"paid_date": "2026-06-18", "amount": 15000})
        assert r2.status_code == 200
        assert r2.json()["paid_date"] == "2026-06-18"

    def test_delete_service_payment(self, client):
        r = client.post("/api/services", json={"name": "Gas"})
        svc_id = r.json()["id"]
        rp = client.post("/api/service-payments", json={"service_id": svc_id, "year_month": "2026-06"})
        pid = rp.json()["id"]
        r2 = client.delete(f"/api/service-payments/{pid}")
        assert r2.status_code == 204

    def test_service_payment_summary(self, client):
        r = client.post("/api/services", json={"name": "Gas"})
        svc_id = r.json()["id"]
        client.post("/api/service-payments", json={"service_id": svc_id, "year_month": "2026-06", "due_date": "2026-06-01"})
        r2 = client.get("/api/service-payments/summary?year_month=2026-06&today=2026-06-27")
        assert r2.status_code == 200
        data = r2.json()
        assert data["unpaid_count"] == 1
        assert "Gas" in data["overdue_names"]
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest backend/tests/test_services.py::TestServiceAPI -v
```
Expected: FAIL with 404 (endpoints don't exist yet)

- [x] **Step 3: Add endpoints to `backend/app/api.py`**

First, add the schema imports to the existing import block in `api.py`. Find the line that imports from `app.schemas` and add:
```
ServiceCreate, ServiceRead, ServiceUpdate,
ServicePaymentCreate, ServicePaymentUpdate, ServicePaymentRead,
ServicePaymentWithMeta, ServicePaymentSummary,
```

Add the crud function imports to the `from app.crud import` line:
```
list_services, create_service, update_service, delete_service,
get_service_payments_for_month, upsert_service_payment,
update_service_payment, delete_service_payment, get_service_payment_summary,
```

Then add the endpoints at the end of `api.py` (before or after the last endpoint block):

```python
# ─── Services ────────────────────────────────────────────────────────────────

@router.get("/services", response_model=list[ServiceRead])
def get_services() -> list[ServiceRead]:
    with get_session() as session:
        return [ServiceRead(**s.model_dump()) for s in list_services(session)]


@router.post("/services", response_model=ServiceRead, status_code=201)
def post_service(payload: ServiceCreate) -> ServiceRead:
    with get_session() as session:
        svc = create_service(session, payload)
        return ServiceRead(**svc.model_dump())


@router.put("/services/{service_id}", response_model=ServiceRead)
def put_service(service_id: int, payload: ServiceUpdate) -> ServiceRead:
    with get_session() as session:
        try:
            svc = update_service(session, service_id, payload)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return ServiceRead(**svc.model_dump())


@router.delete("/services/{service_id}", status_code=204, response_model=None)
def del_service(service_id: int) -> None:
    with get_session() as session:
        try:
            delete_service(session, service_id)
        except ValueError as e:
            msg = str(e)
            if "pagos" in msg:
                raise HTTPException(status_code=409, detail=msg)
            raise HTTPException(status_code=404, detail=msg)


# NOTE: /service-payments/summary must be defined BEFORE /service-payments/{id}
# so FastAPI doesn't interpret "summary" as a path parameter.

@router.get("/service-payments/summary", response_model=ServicePaymentSummary)
def get_service_payments_summary(
    year_month: str,
    today: Optional[str] = None,
) -> ServicePaymentSummary:
    from datetime import date as dt_date, datetime
    today_date = dt_date.fromisoformat(today) if today else dt_date.today()
    with get_session() as session:
        result = get_service_payment_summary(session, year_month, today_date)
        return ServicePaymentSummary(**result)


@router.get("/service-payments", response_model=list[ServicePaymentWithMeta])
def get_service_payments(year_month: str) -> list[ServicePaymentWithMeta]:
    with get_session() as session:
        return get_service_payments_for_month(session, year_month)


@router.post("/service-payments", response_model=ServicePaymentRead)
def post_service_payment(payload: ServicePaymentCreate, response: Response) -> ServicePaymentRead:
    with get_session() as session:
        existing = session.exec(
            select(ServicePayment).where(
                ServicePayment.service_id == payload.service_id,
                ServicePayment.year_month == payload.year_month,
            )
        ).first()
        p = upsert_service_payment(session, payload)
        if existing is None:
            response.status_code = 201
        return ServicePaymentRead(**p.model_dump())


@router.put("/service-payments/{payment_id}", response_model=ServicePaymentRead)
def put_service_payment(payment_id: int, payload: ServicePaymentUpdate) -> ServicePaymentRead:
    with get_session() as session:
        try:
            p = update_service_payment(session, payment_id, payload)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return ServicePaymentRead(**p.model_dump())


@router.delete("/service-payments/{payment_id}", status_code=204, response_model=None)
def del_service_payment(payment_id: int) -> None:
    with get_session() as session:
        try:
            delete_service_payment(session, payment_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
```

Note: `ServicePayment` must be imported in `api.py`. Add it to the `from app.models import ...` line.

- [x] **Step 4: Run tests to verify they pass**

```bash
python -m pytest backend/tests/test_services.py -v
```
Expected: All tests PASS

- [x] **Step 5: Run full suite**

```bash
python -m pytest backend/tests/ -q
```
Expected: 0 failures

- [x] **Step 6: Commit**

```bash
git add backend/app/api.py backend/tests/test_services.py
git commit -m "feat(servicios): add REST endpoints for services and service-payments"
```

---

## Task 5: Frontend Types + API Client

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/endpoints.ts`

**Interfaces:**
- Produces: `Service`, `ServicePaymentRead`, `ServicePaymentWithMeta`, `ServicePaymentSummary` TypeScript interfaces and fetch functions (used by Tasks 6 and 7)

- [x] **Step 1: Add TypeScript interfaces to `frontend/src/api/types.ts`**

Add at the end of `types.ts`:

```typescript
export interface Service {
  id: number
  name: string
  expected_amount: number | null
  typical_due_day: number | null
  is_active: boolean
  sort_order: number
}

export interface ServiceCreate {
  name: string
  expected_amount?: number | null
  typical_due_day?: number | null
  is_active?: boolean
  sort_order?: number
}

export interface ServiceUpdate {
  name?: string
  expected_amount?: number | null
  typical_due_day?: number | null
  is_active?: boolean
  sort_order?: number
}

export interface ServicePaymentRead {
  id: number
  service_id: number
  year_month: string
  due_date: string | null   // ISO date string
  paid_date: string | null  // ISO date string
  amount: number | null
  notes: string | null
}

export interface ServicePaymentCreate {
  service_id: number
  year_month: string
  due_date?: string | null
  paid_date?: string | null
  amount?: number | null
  notes?: string | null
}

export interface ServicePaymentUpdate {
  due_date?: string | null
  paid_date?: string | null
  amount?: number | null
  notes?: string | null
}

export interface ServicePaymentWithMeta {
  service: Service
  payment: ServicePaymentRead | null
  suggested_due_date: string | null  // ISO date string
}

export interface ServicePaymentSummary {
  unpaid_count: number
  overdue_names: string[]
  due_soon_names: string[]
}
```

- [x] **Step 2: Add API client functions to `frontend/src/api/endpoints.ts`**

First, add the new types to the import block at the top of `endpoints.ts`:
```typescript
  Service,
  ServiceCreate,
  ServiceUpdate,
  ServicePaymentRead,
  ServicePaymentCreate,
  ServicePaymentUpdate,
  ServicePaymentWithMeta,
  ServicePaymentSummary,
```

Then add at the end of `endpoints.ts`:

```typescript
// ─── Services ──────────────────────────────────────────────────────────────

export function fetchServices(): Promise<Service[]> {
  return getJson('/api/services')
}

export function createService(payload: ServiceCreate): Promise<Service> {
  return postJson('/api/services', payload)
}

export function updateService(id: number, payload: ServiceUpdate): Promise<Service> {
  return putJson(`/api/services/${id}`, payload)
}

export function deleteService(id: number): Promise<void> {
  return deleteHttp(`/api/services/${id}`)
}

export function fetchServicePayments(yearMonth: string): Promise<ServicePaymentWithMeta[]> {
  return getJson(`/api/service-payments?year_month=${yearMonth}`)
}

export function upsertServicePayment(payload: ServicePaymentCreate): Promise<ServicePaymentRead> {
  return postJson('/api/service-payments', payload)
}

export function updateServicePayment(id: number, payload: ServicePaymentUpdate): Promise<ServicePaymentRead> {
  return putJson(`/api/service-payments/${id}`, payload)
}

export function deleteServicePayment(id: number): Promise<void> {
  return deleteHttp(`/api/service-payments/${id}`)
}

export function fetchServicePaymentSummary(yearMonth: string, today: string): Promise<ServicePaymentSummary> {
  return getJson(`/api/service-payments/summary?year_month=${yearMonth}&today=${today}`)
}
```

- [x] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run build 2>&1 | tail -20
```
Expected: Build succeeds with no TypeScript errors

- [x] **Step 4: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/endpoints.ts
git commit -m "feat(servicios): add TypeScript types and API client functions"
```

---

## Task 6: Semaphore Utility + Tests

**Files:**
- Create: `frontend/src/utils/services.ts`
- Create: `frontend/src/utils/services.test.ts`

**Interfaces:**
- Produces: `getServiceStatus(payment, dueDate, today) → ServiceStatus` (used by Task 7)

- [x] **Step 1: Write the failing tests**

Create `frontend/src/utils/services.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { getServiceStatus } from './services'

describe('getServiceStatus', () => {
  const today = new Date('2026-06-27')

  it('returns paid when paid_date is set', () => {
    expect(getServiceStatus({ paid_date: '2026-06-18' } as any, new Date('2026-06-20'), today)).toBe('paid')
  })

  it('returns no_date when no due_date and not paid', () => {
    expect(getServiceStatus(null, null, today)).toBe('no_date')
  })

  it('returns overdue when due_date is before today and not paid', () => {
    expect(getServiceStatus(null, new Date('2026-06-26'), today)).toBe('overdue')
  })

  it('returns due_soon when due_date equals today (yellow)', () => {
    expect(getServiceStatus(null, new Date('2026-06-27'), today)).toBe('due_soon')
  })

  it('returns due_soon when due_date is 3 days from today', () => {
    expect(getServiceStatus(null, new Date('2026-06-30'), today)).toBe('due_soon')
  })

  it('returns no_date (grey) when due_date is more than 3 days away', () => {
    expect(getServiceStatus(null, new Date('2026-07-10'), today)).toBe('no_date')
  })

  it('paid takes priority over overdue due_date', () => {
    expect(getServiceStatus({ paid_date: '2026-06-01' } as any, new Date('2026-06-01'), today)).toBe('paid')
  })
})
```

- [x] **Step 2: Run to verify it fails**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run test:run -- src/utils/services.test.ts 2>&1 | tail -20
```
Expected: FAIL with `Cannot find module './services'`

- [x] **Step 3: Create `frontend/src/utils/services.ts`**

```typescript
import type { ServicePaymentRead } from '../api/types'

export type ServiceStatus = 'paid' | 'due_soon' | 'overdue' | 'no_date'

export function getServiceStatus(
  payment: Pick<ServicePaymentRead, 'paid_date'> | null,
  dueDate: Date | null,
  today: Date,
): ServiceStatus {
  if (payment?.paid_date) return 'paid'
  if (!dueDate) return 'no_date'

  const todayMs = today.getTime()
  const dueDateMs = dueDate.getTime()
  const threeDaysMs = 3 * 24 * 60 * 60 * 1000

  if (dueDateMs < todayMs) return 'overdue'
  if (dueDateMs <= todayMs + threeDaysMs) return 'due_soon'
  return 'no_date'
}

export const STATUS_COLORS: Record<ServiceStatus, string> = {
  paid: '#22c55e',     // green
  due_soon: '#f59e0b', // amber
  overdue: '#ef4444',  // red
  no_date: '#9ca3af',  // grey
}

export const STATUS_LABELS: Record<ServiceStatus, string> = {
  paid: 'Pagado',
  due_soon: 'Por vencer',
  overdue: 'Vencido',
  no_date: 'Sin fecha',
}
```

- [x] **Step 4: Run tests to verify they pass**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run test:run -- src/utils/services.test.ts
```
Expected: All 7 tests PASS

- [x] **Step 5: Commit**

```bash
git add frontend/src/utils/services.ts frontend/src/utils/services.test.ts
git commit -m "feat(servicios): add semaphore status utility with tests"
```

---

## Task 7: Servicios Page + Navigation

**Files:**
- Create: `frontend/src/pages/servicios-page.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `fetchServicePayments`, `upsertServicePayment`, `updateServicePayment`, `deleteServicePayment`, `fetchServices`, `createService`, `updateService`, `deleteService` (from endpoints.ts), `getServiceStatus`, `STATUS_COLORS`, `STATUS_LABELS` (from utils/services.ts), `getCurrentYearMonth` (from utils/dates.ts)

- [x] **Step 1: Create `frontend/src/pages/servicios-page.tsx`**

```tsx
import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getCurrentYearMonth } from '../utils/dates'
import { getServiceStatus, STATUS_COLORS, STATUS_LABELS } from '../utils/services'
import {
  fetchServicePayments,
  upsertServicePayment,
  updateServicePayment,
  deleteServicePayment,
  fetchServices,
  createService,
  updateService,
  deleteService,
} from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import type { Service, ServicePaymentWithMeta } from '../api/types'

function buildMonthOptions(): { value: string; label: string }[] {
  const months: { value: string; label: string }[] = []
  const now = new Date()
  for (let i = -2; i <= 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1)
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    const label = d.toLocaleString('es-AR', { month: 'long', year: 'numeric' })
    months.push({ value, label })
  }
  return months
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(amount)
}

function getTodayLocalDate(): Date {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

interface PaymentFormState {
  paid_date: string
  amount: string
  notes: string
  due_date: string
}

function ServiceCard({ item, onPaymentSaved }: { item: ServicePaymentWithMeta; onPaymentSaved: () => void }) {
  const [showForm, setShowForm] = useState(false)
  const [formError, setFormError] = useState('')
  const [form, setForm] = useState<PaymentFormState>(() => ({
    paid_date: new Date().toISOString().slice(0, 10),
    amount: '',
    notes: '',
    due_date: item.payment?.due_date ?? item.suggested_due_date ?? '',
  }))

  const today = getTodayLocalDate()
  const dueDate = item.payment?.due_date
    ? new Date(item.payment.due_date + 'T00:00:00')
    : item.suggested_due_date
    ? new Date(item.suggested_due_date + 'T00:00:00')
    : null
  const status = getServiceStatus(item.payment, dueDate, today)
  const statusColor = STATUS_COLORS[status]
  const statusLabel = STATUS_LABELS[status]

  const queryClient = useQueryClient()

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!form.amount || Number(form.amount) <= 0) throw new Error('El monto debe ser mayor a 0')
      const payload = {
        service_id: item.service.id,
        year_month: item.payment?.year_month ?? '',  // filled by caller
        paid_date: form.paid_date || null,
        amount: Number(form.amount),
        notes: form.notes || null,
        due_date: form.due_date || null,
      }
      if (item.payment) {
        return updateServicePayment(item.payment.id, {
          paid_date: payload.paid_date,
          amount: payload.amount,
          notes: payload.notes,
          due_date: payload.due_date,
        })
      }
      return upsertServicePayment({ ...payload, year_month: item.payment?.year_month ?? '' })
    },
    onSuccess: () => {
      setShowForm(false)
      setFormError('')
      queryClient.invalidateQueries({ queryKey: ['service-payments'] })
      queryClient.invalidateQueries({ queryKey: ['service-payment-summary'] })
      onPaymentSaved()
    },
    onError: (e: Error) => setFormError(extractErrorMessage(e)),
  })

  const unmarkMutation = useMutation({
    mutationFn: () => {
      if (!item.payment) throw new Error('No payment to unmark')
      return updateServicePayment(item.payment.id, { paid_date: null, amount: null, notes: null })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['service-payments'] })
      queryClient.invalidateQueries({ queryKey: ['service-payment-summary'] })
      onPaymentSaved()
    },
    onError: (e: Error) => setFormError(extractErrorMessage(e)),
  })

  const diffText = useMemo(() => {
    if (!item.payment?.paid_date || !item.payment.amount || !item.service.expected_amount) return null
    const diff = item.payment.amount - item.service.expected_amount
    if (Math.abs(diff) < 1) return null
    return diff > 0
      ? `+${formatCurrency(diff)} sobre lo esperado`
      : `${formatCurrency(Math.abs(diff))} menos de lo esperado`
  }, [item])

  return (
    <div className="panel" style={{ position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <span
          style={{
            width: 12, height: 12, borderRadius: '50%',
            backgroundColor: statusColor, flexShrink: 0, display: 'inline-block',
          }}
          title={statusLabel}
        />
        <span className="panelTitle" style={{ margin: 0, fontSize: '1rem' }}>{item.service.name}</span>
      </div>

      <div className="muted" style={{ fontSize: '0.8rem', marginBottom: '0.4rem' }}>{statusLabel}</div>

      {dueDate && (
        <div style={{ fontSize: '0.875rem', marginBottom: '0.4rem' }}>
          Vence: {dueDate.toLocaleDateString('es-AR')}
        </div>
      )}

      {item.payment?.paid_date ? (
        <div style={{ fontSize: '0.875rem' }}>
          <div>Pagado: {new Date(item.payment.paid_date + 'T00:00:00').toLocaleDateString('es-AR')}</div>
          {item.payment.amount && <div>Monto: {formatCurrency(item.payment.amount)}</div>}
          {diffText && <div className="hint" style={{ fontSize: '0.8rem' }}>{diffText}</div>}
          {item.payment.notes && <div className="hint">{item.payment.notes}</div>}
        </div>
      ) : (
        item.service.expected_amount && (
          <div className="muted" style={{ fontSize: '0.875rem' }}>
            Referencia: {formatCurrency(item.service.expected_amount)}
          </div>
        )
      )}

      {formError && <div className="error" style={{ fontSize: '0.8rem', marginTop: '0.4rem' }}>{formError}</div>}

      {showForm && (
        <div style={{ marginTop: '0.75rem', borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem' }}>
          <div className="formRow">
            <label className="label">Fecha de pago</label>
            <input
              className="input"
              type="date"
              value={form.paid_date}
              onChange={e => setForm(f => ({ ...f, paid_date: e.target.value }))}
            />
          </div>
          <div className="formRow">
            <label className="label">Monto ($)</label>
            <input
              className="input"
              type="number"
              min="0.01"
              step="0.01"
              placeholder="0"
              value={form.amount}
              onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
            />
          </div>
          <div className="formRow">
            <label className="label">Nota (opcional)</label>
            <input
              className="input"
              type="text"
              value={form.notes}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            />
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
            <button className="button" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Guardando…' : 'Guardar'}
            </button>
            <button className="button" style={{ background: 'var(--color-border)', color: 'var(--color-text)' }} onClick={() => setShowForm(false)}>
              Cancelar
            </button>
          </div>
        </div>
      )}

      {!showForm && (
        <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {item.payment?.paid_date ? (
            <button
              className="button"
              style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem' }}
              onClick={() => { setShowForm(true); setForm(f => ({ ...f, amount: String(item.payment!.amount ?? ''), paid_date: item.payment!.paid_date! })) }}
            >
              Editar pago
            </button>
          ) : (
            <button
              className="button"
              style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem' }}
              onClick={() => setShowForm(true)}
            >
              Registrar pago
            </button>
          )}
          {item.payment?.paid_date && (
            <button
              className="button"
              style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem', background: 'var(--color-border)', color: 'var(--color-text)' }}
              onClick={() => unmarkMutation.mutate()}
              disabled={unmarkMutation.isPending}
            >
              Desmarcar
            </button>
          )}
        </div>
      )}
    </div>
  )
}

interface ServiceFormState {
  name: string
  expected_amount: string
  typical_due_day: string
  sort_order: string
}

function ManageServicesSection({ services }: { services: Service[] }) {
  const queryClient = useQueryClient()
  const [editingId, setEditingId] = useState<number | null>(null)
  const [form, setForm] = useState<ServiceFormState>({ name: '', expected_amount: '', typical_due_day: '', sort_order: '0' })
  const [error, setError] = useState('')

  const createMutation = useMutation({
    mutationFn: () => {
      if (!form.name.trim()) throw new Error('El nombre es requerido')
      return createService({
        name: form.name.trim(),
        expected_amount: form.expected_amount ? Number(form.expected_amount) : null,
        typical_due_day: form.typical_due_day ? Number(form.typical_due_day) : null,
        sort_order: Number(form.sort_order) || 0,
      })
    },
    onSuccess: () => {
      setForm({ name: '', expected_amount: '', typical_due_day: '', sort_order: '0' })
      setError('')
      queryClient.invalidateQueries({ queryKey: ['services'] })
      queryClient.invalidateQueries({ queryKey: ['service-payments'] })
    },
    onError: (e: Error) => setError(extractErrorMessage(e)),
  })

  const updateMutation = useMutation({
    mutationFn: (payload: { id: number; is_active: boolean }) =>
      updateService(payload.id, { is_active: payload.is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] })
      queryClient.invalidateQueries({ queryKey: ['service-payments'] })
    },
  })

  return (
    <div className="panel" style={{ marginTop: '2rem' }}>
      <h2 className="panelTitle">Gestionar servicios</h2>

      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '0.5rem', marginBottom: '0.5rem' }}>
          <input className="input" placeholder="Nombre *" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          <input className="input" placeholder="Monto esperado" type="number" min="0" value={form.expected_amount} onChange={e => setForm(f => ({ ...f, expected_amount: e.target.value }))} />
          <input className="input" placeholder="Día venc. (1-31)" type="number" min="1" max="31" value={form.typical_due_day} onChange={e => setForm(f => ({ ...f, typical_due_day: e.target.value }))} />
          <input className="input" placeholder="Orden" type="number" value={form.sort_order} onChange={e => setForm(f => ({ ...f, sort_order: e.target.value }))} />
        </div>
        {error && <div className="error" style={{ marginBottom: '0.5rem' }}>{error}</div>}
        <button className="button" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
          {createMutation.isPending ? 'Agregando…' : 'Agregar servicio'}
        </button>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Monto ref.</th>
            <th>Día venc.</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {services.map(svc => (
            <tr key={svc.id} style={{ opacity: svc.is_active ? 1 : 0.5 }}>
              <td>{svc.name}</td>
              <td>{svc.expected_amount ? formatCurrency(svc.expected_amount) : '—'}</td>
              <td>{svc.typical_due_day ?? '—'}</td>
              <td>{svc.is_active ? 'Activo' : 'Inactivo'}</td>
              <td>
                <button
                  className="button"
                  style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem' }}
                  onClick={() => updateMutation.mutate({ id: svc.id, is_active: !svc.is_active })}
                >
                  {svc.is_active ? 'Desactivar' : 'Activar'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ServiciosPage() {
  const [monthFilter, setMonthFilter] = useState<string>(() => getCurrentYearMonth())
  const monthOptions = useMemo(() => buildMonthOptions(), [])
  const queryClient = useQueryClient()

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['service-payments', monthFilter],
    queryFn: () => fetchServicePayments(monthFilter),
  })

  const { data: allServices = [] } = useQuery({
    queryKey: ['services'],
    queryFn: fetchServices,
  })

  // Inject year_month into the ServicePaymentWithMeta items for the card mutation
  const enrichedItems = useMemo(() =>
    items.map(item => ({
      ...item,
      payment: item.payment ? { ...item.payment, year_month: monthFilter } : null,
      _yearMonth: monthFilter,
    })), [items, monthFilter])

  const handlePaymentSaved = () => {
    queryClient.invalidateQueries({ queryKey: ['service-payments', monthFilter] })
  }

  return (
    <div className="page">
      <h1 className="pageTitle">Servicios</h1>

      <div className="formRow" style={{ marginBottom: '1.5rem' }}>
        <label className="label">Mes</label>
        <select className="input" style={{ width: 'auto' }} value={monthFilter} onChange={e => setMonthFilter(e.target.value)}>
          {monthOptions.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {isLoading && <div className="muted">Cargando…</div>}

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
        gap: '1rem',
      }}>
        {enrichedItems.map(item => (
          <ServiceCard
            key={item.service.id}
            item={item}
            onPaymentSaved={handlePaymentSaved}
          />
        ))}
      </div>

      {!isLoading && items.length === 0 && (
        <div className="muted">No hay servicios activos. Agregá uno abajo.</div>
      )}

      <ManageServicesSection services={allServices} />
    </div>
  )
}
```

- [x] **Step 2: Add route and nav to `frontend/src/App.tsx`**

Add lazy import after the `NuevaTransferenciaPage` import line:

```tsx
const ServiciosPage = lazy(() =>
  import('./pages/servicios-page').then((m) => ({ default: m.ServiciosPage })),
)
```

Add nav item to the `'Principal'` group's `items` array (after `{ to: '/import', ...}` line):

```tsx
{ to: '/servicios', label: 'Servicios', icon: '🧾' },
```

Add route inside the `<Routes>` block (after the other routes):

```tsx
<Route element={<ServiciosPage />} path="/servicios" />
```

- [x] **Step 3: TypeScript compile check**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run build 2>&1 | tail -30
```
Expected: Build succeeds with no TypeScript errors

- [x] **Step 4: Run frontend tests**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run test:run
```
Expected: All tests PASS (including the new services.test.ts)

- [x] **Step 5: Commit**

```bash
git add frontend/src/pages/servicios-page.tsx frontend/src/App.tsx
git commit -m "feat(servicios): add servicios page with card grid and navigation"
```

---

## Task 8: Dashboard Widget

**Files:**
- Modify: `frontend/src/pages/dashboard-page.tsx`

**Interfaces:**
- Consumes: `fetchServicePaymentSummary` (from endpoints.ts), `ServicePaymentSummary` (from types.ts)

- [x] **Step 1: Add summary query to `dashboard-page.tsx`**

First, add to the imports at the top of `dashboard-page.tsx`:

```tsx
import { fetchServicePaymentSummary } from '../api/endpoints'
import type { ServicePaymentSummary } from '../api/types'
```

Then, inside the `DashboardPage` component (after the existing query declarations), add:

```tsx
const todayStr = useMemo(() => new Date().toISOString().slice(0, 10), [])

const { data: serviceSummary } = useQuery<ServicePaymentSummary>({
  queryKey: ['service-payment-summary', monthFilter, todayStr],
  queryFn: () => fetchServicePaymentSummary(monthFilter, todayStr),
})
```

- [x] **Step 2: Add the widget to the JSX**

Find where the dashboard renders its first panel/section (typically after the month selector row). Add the widget immediately after the month selector `<div>` and before the first panel:

```tsx
{serviceSummary && serviceSummary.unpaid_count > 0 && (
  <div style={{
    background: '#fffbeb',
    border: '1px solid #f59e0b',
    borderRadius: '0.5rem',
    padding: '0.875rem 1rem',
    marginBottom: '1rem',
    display: 'flex',
    alignItems: 'flex-start',
    gap: '0.75rem',
  }}>
    <span style={{ fontSize: '1.1rem', flexShrink: 0 }}>⚠️</span>
    <div>
      <strong style={{ color: '#92400e' }}>
        {serviceSummary.unpaid_count} {serviceSummary.unpaid_count === 1 ? 'servicio sin pagar' : 'servicios sin pagar'}
      </strong>
      {(serviceSummary.overdue_names.length > 0 || serviceSummary.due_soon_names.length > 0) && (
        <div style={{ fontSize: '0.875rem', color: '#78350f', marginTop: '0.25rem' }}>
          {[
            ...serviceSummary.overdue_names.map(n => `${n} (vencido)`),
            ...serviceSummary.due_soon_names.map(n => `${n} (vence pronto)`),
          ].join(', ')}
        </div>
      )}
      <Link
        to="/servicios"
        style={{ fontSize: '0.875rem', color: '#b45309', fontWeight: 500, display: 'inline-block', marginTop: '0.25rem' }}
      >
        Ver servicios →
      </Link>
    </div>
  </div>
)}
```

Add the `Link` import at the top of `dashboard-page.tsx` if not already there:
```tsx
import { Link } from 'react-router-dom'
```

- [x] **Step 3: TypeScript compile check**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run build 2>&1 | tail -20
```
Expected: Build succeeds with no TypeScript errors

- [x] **Step 4: Run full test suite**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run test:run
```
Expected: All tests PASS

- [x] **Step 5: Run backend tests too**

```bash
cd /Users/pablo/github/admin-consumos && source .venv/bin/activate && python -m pytest backend/tests/ -q
```
Expected: 0 failures

- [x] **Step 6: Commit**

```bash
git add frontend/src/pages/dashboard-page.tsx
git commit -m "feat(servicios): add unpaid services alert widget to dashboard"
```

---

## Post-Implementation Checklist

- [x] Run `python -m pytest backend/tests/ -q` → 0 failures
- [x] Run `npm run test:run` → 0 failures
- [x] Run `npm run build` → 0 TypeScript errors
- [x] Manual smoke: start app with `./start.sh`, navigate to `/servicios`, create a service, register a payment, verify semaphore colors
- [x] Manual smoke: check dashboard widget appears when a service is unpaid for the selected month, disappears when all are paid

---

## Self-Review vs Spec

| Spec requirement | Covered in |
|---|---|
| `Service` table with 6 fields | Task 1 |
| `ServicePayment` table with 7 fields, unique `(service_id, year_month)` | Task 1 |
| 4 semaphore states (paid/due_soon/overdue/no_date) | Task 6 |
| `GET/POST/PUT/DELETE /services` | Task 4 |
| `GET /service-payments?year_month` with suggested_due_date | Tasks 3+4 |
| `POST /service-payments` (upsert) | Task 4 |
| `PUT /service-payments/{id}` | Task 4 |
| `DELETE /service-payments/{id}` | Task 4 |
| `GET /service-payments/summary` | Tasks 3+4 |
| Auto-suggest from prev month → typical_due_day → null | Task 3 |
| Clamping day 31 in short months | Task 3 |
| DELETE service with payments → 409 | Tasks 3+4 |
| `amount > 0` validation | Task 2 |
| `year_month` regex | Task 2 |
| `typical_due_day` 1–31 | Task 2 |
| `/servicios` page with month selector + card grid | Task 7 |
| Semaphore dot on each card | Task 7 |
| "Registrar pago" inline form (date default today, amount, notes) | Task 7 |
| "Editar / Desmarcar pago" buttons | Task 7 |
| Manage section at bottom (add/deactivate) | Task 7 |
| Dashboard widget (amber, names, link) | Task 8 |
| Widget hidden when all paid | Task 8 |
| Nav item "Servicios" | Task 7 |
| Semaphore computed client-side from browser date | Tasks 6+7 |
| `today` param on summary endpoint | Task 4 |
| Backend tests (all cases) | Tasks 1–4 |
| Frontend tests (semaphore logic, form, unmark) | Tasks 5–6 |

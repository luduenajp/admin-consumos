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

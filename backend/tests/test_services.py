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

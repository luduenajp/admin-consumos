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

"""Tests for basic CRUD operations (people, cards, debtors, FX rates, incomes)."""
from datetime import date

import pytest

from app.crud import (
    create_card,
    create_debtor,
    create_income,
    create_person,
    get_monthly_budget,
    list_cards,
    list_debtors,
    list_fx_rates,
    list_people,
    upsert_fx_rate,
)
from app.models import CurrencyCode
from app.schemas import (
    CardCreate,
    DebtorCreate,
    FxRateUpsert,
    IncomeCreate,
    PersonCreate,
)


class TestPersonCRUD:
    def test_create_and_list(self, session):
        p = create_person(session=session, payload=PersonCreate(name="Carlos"))
        assert p.id is not None
        assert p.name == "Carlos"
        people = list_people(session=session)
        assert len(people) == 1
        assert people[0].name == "Carlos"

    def test_multiple_people_sorted(self, session):
        create_person(session=session, payload=PersonCreate(name="Zoe"))
        create_person(session=session, payload=PersonCreate(name="Ana"))
        people = list_people(session=session)
        assert [p.name for p in people] == ["Ana", "Zoe"]


class TestCardCRUD:
    def test_create_with_valid_person(self, session, two_persons):
        alice, _ = two_persons
        card = create_card(
            session=session,
            payload=CardCreate(name="Visa", provider="visa", owner_person_id=alice.id),
        )
        assert card.id is not None
        assert card.owner_person_id == alice.id

    def test_create_with_invalid_person_raises(self, session):
        with pytest.raises(ValueError, match="Person not found"):
            create_card(
                session=session,
                payload=CardCreate(name="Visa", provider="visa", owner_person_id=9999),
            )

    def test_list_cards(self, session, two_persons):
        alice, _ = two_persons
        create_card(
            session=session,
            payload=CardCreate(name="Mastercard", provider="mastercard", owner_person_id=alice.id),
        )
        cards = list_cards(session=session)
        assert len(cards) == 1
        assert cards[0].name == "Mastercard"


class TestDebtorCRUD:
    def test_create_and_list(self, session):
        d = create_debtor(session=session, payload=DebtorCreate(name="Juan"))
        assert d.id is not None
        debtors = list_debtors(session=session)
        assert len(debtors) == 1
        assert debtors[0].name == "Juan"


class TestFxRateCRUD:
    def test_create_new(self, session):
        fx = upsert_fx_rate(
            session=session,
            payload=FxRateUpsert(year_month="2025-01", currency=CurrencyCode.USD, rate_to_ars=1200.0),
        )
        assert fx.id is not None
        assert fx.rate_to_ars == 1200.0

    def test_upsert_updates_existing(self, session):
        upsert_fx_rate(
            session=session,
            payload=FxRateUpsert(year_month="2025-01", currency=CurrencyCode.USD, rate_to_ars=1200.0),
        )
        updated = upsert_fx_rate(
            session=session,
            payload=FxRateUpsert(year_month="2025-01", currency=CurrencyCode.USD, rate_to_ars=1300.0),
        )
        assert updated.rate_to_ars == 1300.0
        rates = list_fx_rates(session=session)
        assert len(rates) == 1

    def test_different_months_create_separate(self, session):
        upsert_fx_rate(
            session=session,
            payload=FxRateUpsert(year_month="2025-01", currency=CurrencyCode.USD, rate_to_ars=1200.0),
        )
        upsert_fx_rate(
            session=session,
            payload=FxRateUpsert(year_month="2025-02", currency=CurrencyCode.USD, rate_to_ars=1250.0),
        )
        rates = list_fx_rates(session=session)
        assert len(rates) == 2


class TestIncomeCRUD:
    def test_create_income_creates_budget(self, session, two_persons):
        alice, _ = two_persons
        income = create_income(
            session=session,
            payload=IncomeCreate(person_id=alice.id, year_month="2025-01", amount=500000),
        )
        assert income.id is not None

        budget = get_monthly_budget(session=session, year_month="2025-01")
        assert budget is not None
        assert budget.total_income == 500000

    def test_multiple_incomes_sum_in_budget(self, session, two_persons):
        alice, bob = two_persons
        create_income(
            session=session,
            payload=IncomeCreate(person_id=alice.id, year_month="2025-01", amount=500000),
        )
        create_income(
            session=session,
            payload=IncomeCreate(person_id=bob.id, year_month="2025-01", amount=300000),
        )
        budget = get_monthly_budget(session=session, year_month="2025-01")
        assert budget is not None
        assert budget.total_income == 800000

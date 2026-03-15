"""Tests for report functions (month breakdown, monthly totals, etc.)."""
from datetime import date

import pytest

from app.crud import (
    calculate_monthly_balance,
    create_income,
    create_purchase,
    report_month_breakdown,
    report_monthly_totals_converted,
    report_spending_by_category,
    upsert_fx_rate,
)
from app.models import CurrencyCode
from app.schemas import (
    FxRateUpsert,
    IncomeCreate,
    MonthlyBudgetCreate,
    PurchaseCreate,
)
from app.crud import create_monthly_budget


class TestMonthBreakdown:
    def test_ars_breakdown(self, session, two_person_scenario):
        s = two_person_scenario
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 10),
                description="Groceries",
                currency=CurrencyCode.ARS,
                amount_original=50000,
                first_installment_month="2025-01",
            ),
        )
        total, items = report_month_breakdown(session=session, year_month="2025-01")
        assert total == 50000.0
        assert len(items) == 1
        purchase, schedule, amount_ars, debtor_name, payer_name, card_name = items[0]
        assert amount_ars == 50000.0
        assert payer_name == "Alice"

    def test_usd_with_fx(self, session, two_person_scenario):
        s = two_person_scenario
        # FX rate for 2025-01 is 1200 (from fixture)
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 10),
                description="Steam USD",
                currency=CurrencyCode.USD,
                amount_original=10,
                first_installment_month="2025-01",
            ),
        )
        total, items = report_month_breakdown(session=session, year_month="2025-01")
        assert total == 12000.0  # 10 USD * 1200
        assert len(items) == 1

    def test_usd_without_fx_excluded(self, session, two_person_scenario):
        s = two_person_scenario
        # No FX rate for 2025-03
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 3, 10),
                description="Netflix USD",
                currency=CurrencyCode.USD,
                amount_original=15,
                first_installment_month="2025-03",
            ),
        )
        total, items = report_month_breakdown(session=session, year_month="2025-03")
        assert total == 0.0
        assert len(items) == 0

    def test_person_filter(self, session, two_person_scenario):
        s = two_person_scenario
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 10),
                description="Alice purchase",
                currency=CurrencyCode.ARS,
                amount_original=30000,
                first_installment_month="2025-01",
            ),
        )
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["bob_card"].id,
                purchase_date=date(2025, 1, 10),
                description="Bob purchase",
                currency=CurrencyCode.ARS,
                amount_original=20000,
                first_installment_month="2025-01",
            ),
        )
        # Filter by Alice
        total, items = report_month_breakdown(
            session=session, year_month="2025-01", person_id=s["alice"].id
        )
        assert total == 30000.0
        assert len(items) == 1


class TestMonthlyTotals:
    def test_basic_totals(self, session, two_person_scenario):
        s = two_person_scenario
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 10),
                description="Jan purchase",
                currency=CurrencyCode.ARS,
                amount_original=50000,
                first_installment_month="2025-01",
            ),
        )
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 2, 10),
                description="Feb purchase",
                currency=CurrencyCode.ARS,
                amount_original=30000,
                first_installment_month="2025-02",
            ),
        )
        totals = report_monthly_totals_converted(session=session)
        totals_dict = dict(totals)
        assert totals_dict["2025-01"] == 50000.0
        assert totals_dict["2025-02"] == 30000.0


class TestSpendingByCategory:
    def test_category_breakdown(self, session, two_person_scenario):
        s = two_person_scenario
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 10),
                description="Food",
                currency=CurrencyCode.ARS,
                amount_original=30000,
                category="supermercado",
                first_installment_month="2025-01",
            ),
        )
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Gas",
                currency=CurrencyCode.ARS,
                amount_original=20000,
                category="transporte",
                first_installment_month="2025-01",
            ),
        )
        spending = report_spending_by_category(session=session, year_month="2025-01")
        spending_dict = dict(spending)
        assert spending_dict["supermercado"] == 30000.0
        assert spending_dict["transporte"] == 20000.0


class TestMonthlyBalance:
    def test_with_budget(self, session, two_person_scenario):
        s = two_person_scenario
        create_monthly_budget(
            session=session,
            payload=MonthlyBudgetCreate(year_month="2025-01", total_income=800000),
        )
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 10),
                description="Expense",
                currency=CurrencyCode.ARS,
                amount_original=200000,
                first_installment_month="2025-01",
            ),
        )
        balance = calculate_monthly_balance(session=session, year_month="2025-01")
        assert balance is not None
        assert balance["presupuesto"] == 800000
        assert balance["gastos_acumulados"] == 200000
        assert balance["sobrante_total"] == 600000
        assert balance["sobrante_por_persona"] == 300000

    def test_without_budget_returns_none(self, session):
        balance = calculate_monthly_balance(session=session, year_month="2025-01")
        assert balance is None

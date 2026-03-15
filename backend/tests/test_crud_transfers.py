"""Tests for the Fondo Común transfer calculation logic — the most critical business logic."""
from datetime import date

import pytest

from app.crud import (
    calculate_transfers,
    create_income,
    create_purchase,
    create_debt_transfer,
    upsert_fx_rate,
)
from app.models import CurrencyCode, PaymentMethod, ShareType
from app.schemas import (
    DebtTransferCreate,
    FxRateUpsert,
    IncomeCreate,
    PurchaseCreate,
    PurchasePayerCreate,
)


def _setup_incomes(session, alice_id, bob_id, month, alice_amount, bob_amount):
    """Helper to create incomes for both persons."""
    create_income(session=session, payload=IncomeCreate(person_id=alice_id, year_month=month, amount=alice_amount))
    create_income(session=session, payload=IncomeCreate(person_id=bob_id, year_month=month, amount=bob_amount))


def _create_common_purchase(session, card_id, amount, month="2025-01"):
    """Helper: ARS common purchase on card."""
    create_purchase(
        session=session,
        payload=PurchaseCreate(
            card_id=card_id,
            purchase_date=date(int(month[:4]), int(month[5:7]), 15),
            description=f"Common {amount}",
            currency=CurrencyCode.ARS,
            amount_original=amount,
            is_common=True,
            first_installment_month=month,
        ),
    )


def _create_personal_purchase(session, card_id, amount, month="2025-01", beneficiary_id=None):
    """Helper: ARS personal purchase on card."""
    create_purchase(
        session=session,
        payload=PurchaseCreate(
            card_id=card_id,
            purchase_date=date(int(month[:4]), int(month[5:7]), 15),
            description=f"Personal {amount}",
            currency=CurrencyCode.ARS,
            amount_original=amount,
            is_common=False,
            first_installment_month=month,
            beneficiary_person_id=beneficiary_id,
        ),
    )


class TestCalculateTransfersBasic:
    def test_no_incomes_returns_none(self, session, two_person_scenario):
        result = calculate_transfers(session=session, year_month="2025-01")
        assert result is None

    def test_equal_incomes_equal_common_expenses_no_transfer(self, session, two_person_scenario):
        s = two_person_scenario
        _setup_incomes(session, s["alice"].id, s["bob"].id, "2025-01", 500000, 500000)

        # Each pays 100k common from their own card
        _create_common_purchase(session, s["alice_card"].id, 100000)
        _create_common_purchase(session, s["bob_card"].id, 100000)

        result = calculate_transfers(session=session, year_month="2025-01")
        assert result is not None
        assert result["is_balanced"] is True
        # Both paid equally, both should pay equally → no transfers needed
        assert len(result["transferencias"]) == 0


class TestCalculateTransfersUnequalIncomes:
    def test_unequal_incomes_common_expenses(self, session, two_person_scenario):
        """Alice earns more but both should contribute proportionally to common pool."""
        s = two_person_scenario
        _setup_incomes(session, s["alice"].id, s["bob"].id, "2025-01", 600000, 400000)

        # Alice pays all 200k in common expenses from her card
        _create_common_purchase(session, s["alice_card"].id, 200000)

        result = calculate_transfers(session=session, year_month="2025-01")
        assert result is not None
        assert result["total_ingresos"] == 1000000
        assert result["total_common_expenses"] == 200000

        # Sobrante base = (1000000 - 200000) / 2 = 400000
        # Alice: target_cash = 400000, should_pay = 600000 - 400000 = 200000, paid 200000 → diff = 0
        # Bob: target_cash = 400000, should_pay = 400000 - 400000 = 0, paid 0 → diff = 0
        # No transfers needed since the common expenses match Alice's should_pay
        assert result["is_balanced"] is True


class TestCalculateTransfersPersonalExpenses:
    def test_personal_expenses_affect_target_cash(self, session, two_person_scenario):
        """Personal expenses reduce target_cash for that person."""
        s = two_person_scenario
        _setup_incomes(session, s["alice"].id, s["bob"].id, "2025-01", 500000, 500000)

        # Common: Alice pays 200k
        _create_common_purchase(session, s["alice_card"].id, 200000)
        # Personal: Alice buys 50k for herself
        _create_personal_purchase(session, s["alice_card"].id, 50000)

        result = calculate_transfers(session=session, year_month="2025-01")
        assert result is not None

        # Sobrante base = (1000000 - 200000) / 2 = 400000
        # Alice: target_cash = 400000 - 50000 = 350000, should_pay = 500000 - 350000 = 150000
        #   Alice paid 200000 (common) + 50000 (personal) = 250000
        #   diff = 250000 - 150000 = 100000 (Alice overpaid)
        # Bob: target_cash = 400000 - 0 = 400000, should_pay = 500000 - 400000 = 100000
        #   Bob paid 0
        #   diff = 0 - 100000 = -100000 (Bob underpaid)
        # Bob should transfer 100000 to Alice

        gastos = {g["person_name"]: g for g in result["gastos_por_persona"]}
        alice_g = gastos["Alice"]
        bob_g = gastos["Bob"]

        assert alice_g["paid_amount"] == 250000.0
        assert alice_g["should_pay"] == 150000.0
        assert alice_g["difference"] == 100000.0

        assert bob_g["paid_amount"] == 0.0
        assert bob_g["should_pay"] == 100000.0
        assert bob_g["difference"] == -100000.0

        assert len(result["transferencias"]) == 1
        t = result["transferencias"][0]
        assert t["from_person"] == "Bob"
        assert t["to_person"] == "Alice"
        assert t["amount"] == 100000.0


class TestCalculateTransfersBeneficiary:
    def test_beneficiary_overrides_personal_expense_owner(self, session, two_person_scenario):
        """beneficiary_person_id makes the expense count as the beneficiary's personal expense."""
        s = two_person_scenario
        _setup_incomes(session, s["alice"].id, s["bob"].id, "2025-01", 500000, 500000)

        # Alice pays from her card but it's Bob's personal expense
        _create_personal_purchase(
            session, s["alice_card"].id, 50000, beneficiary_id=s["bob"].id
        )

        result = calculate_transfers(session=session, year_month="2025-01")
        assert result is not None

        # Sobrante base = (1000000 - 0) / 2 = 500000
        # Alice: target_cash = 500000 - 0 = 500000, should_pay = 500000 - 500000 = 0
        #   Alice paid 50000, diff = 50000 - 0 = 50000 (overpaid)
        # Bob: target_cash = 500000 - 50000 = 450000, should_pay = 500000 - 450000 = 50000
        #   Bob paid 0, diff = 0 - 50000 = -50000 (underpaid)

        gastos = {g["person_name"]: g for g in result["gastos_por_persona"]}
        assert gastos["Alice"]["difference"] == 50000.0
        assert gastos["Bob"]["difference"] == -50000.0


class TestCalculateTransfersDebtTransfer:
    def test_debt_transfer_adjusts_difference(self, session, two_person_scenario):
        """DebtTransfers adjust the final difference."""
        s = two_person_scenario
        _setup_incomes(session, s["alice"].id, s["bob"].id, "2025-01", 500000, 500000)

        # Alice pays all 200k common
        _create_common_purchase(session, s["alice_card"].id, 200000)

        # Without debt transfer:
        # Sobrante base = (1000000 - 200000) / 2 = 400000
        # Alice: should_pay = 500000 - 400000 = 100000, paid 200000, diff = 100000
        # Bob: should_pay = 100000, paid 0, diff = -100000

        # Bob transfers 50000 to Alice
        create_debt_transfer(
            session=session,
            payload=DebtTransferCreate(
                from_person_id=s["bob"].id,
                to_person_id=s["alice"].id,
                year_month="2025-01",
                amount=50000,
            ),
        )

        result = calculate_transfers(session=session, year_month="2025-01")
        gastos = {g["person_name"]: g for g in result["gastos_por_persona"]}

        # Alice: initial_diff=100000, adjustment=0-50000=-50000, final_diff=50000
        assert gastos["Alice"]["adjustment"] == -50000.0
        assert gastos["Alice"]["difference"] == 50000.0
        # Bob: initial_diff=-100000, adjustment=50000-0=50000, final_diff=-50000
        assert gastos["Bob"]["adjustment"] == 50000.0
        assert gastos["Bob"]["difference"] == -50000.0


class TestCalculateTransfersDeterministic:
    def test_full_scenario(self, session, two_person_scenario):
        """
        Deterministic test with known numbers:
        - Alice earns 500k, Bob earns 300k
        - 200k in common expenses (paid by Alice)
        - 50k personal Alice, 30k personal Bob
        """
        s = two_person_scenario
        _setup_incomes(session, s["alice"].id, s["bob"].id, "2025-01", 500000, 300000)

        _create_common_purchase(session, s["alice_card"].id, 200000)
        _create_personal_purchase(session, s["alice_card"].id, 50000)
        _create_personal_purchase(session, s["bob_card"].id, 30000)

        result = calculate_transfers(session=session, year_month="2025-01")
        assert result is not None

        # Total income = 800000
        # Common expenses = 200000
        # Sobrante base = (800000 - 200000) / 2 = 300000
        #
        # Alice: target_cash = 300000 - 50000 = 250000
        #   should_pay = 500000 - 250000 = 250000
        #   paid = 200000 + 50000 = 250000
        #   diff = 250000 - 250000 = 0
        #
        # Bob: target_cash = 300000 - 30000 = 270000
        #   should_pay = 300000 - 270000 = 30000
        #   paid = 30000
        #   diff = 30000 - 30000 = 0

        assert result["total_ingresos"] == 800000
        assert result["total_common_expenses"] == 200000
        assert result["total_personal_expenses"] == 80000

        gastos = {g["person_name"]: g for g in result["gastos_por_persona"]}

        assert gastos["Alice"]["paid_amount"] == 250000.0
        assert gastos["Alice"]["should_pay"] == 250000.0
        assert gastos["Alice"]["difference"] == 0.0

        assert gastos["Bob"]["paid_amount"] == 30000.0
        assert gastos["Bob"]["should_pay"] == 30000.0
        assert gastos["Bob"]["difference"] == 0.0

        assert result["is_balanced"] is True
        assert len(result["transferencias"]) == 0

    def test_unbalanced_scenario(self, session, two_person_scenario):
        """
        Alice earns 500k, Bob 300k.
        Common 200k paid ALL by Alice, no personal expenses.
        """
        s = two_person_scenario
        _setup_incomes(session, s["alice"].id, s["bob"].id, "2025-01", 500000, 300000)
        _create_common_purchase(session, s["alice_card"].id, 200000)

        result = calculate_transfers(session=session, year_month="2025-01")

        # Sobrante base = (800000 - 200000) / 2 = 300000
        # Alice: should_pay = 500000 - 300000 = 200000, paid 200000, diff = 0
        # Bob: should_pay = 300000 - 300000 = 0, paid 0, diff = 0

        gastos = {g["person_name"]: g for g in result["gastos_por_persona"]}
        assert gastos["Alice"]["difference"] == 0.0
        assert gastos["Bob"]["difference"] == 0.0


class TestCalculateTransfersUSD:
    def test_usd_without_fx_excluded(self, session, two_person_scenario):
        """USD expenses without FX rate for that month are excluded."""
        s = two_person_scenario
        _setup_incomes(session, s["alice"].id, s["bob"].id, "2025-02", 500000, 300000)

        # No FX rate for 2025-02, only for 2025-01
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 2, 15),
                description="USD Purchase",
                currency=CurrencyCode.USD,
                amount_original=100,
                is_common=True,
                first_installment_month="2025-02",
            ),
        )

        result = calculate_transfers(session=session, year_month="2025-02")
        assert result is not None
        # USD expense should be excluded (amount_ars is None for USD without FX)
        # The total_common_expenses should be 0 since the only expense is USD with no FX
        assert result["total_common_expenses"] == 0.0

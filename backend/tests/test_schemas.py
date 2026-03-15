"""Tests for backend/app/schemas.py — validation rules."""
from datetime import date

import pytest
from pydantic import ValidationError

from app.models import CurrencyCode, PaymentMethod, ShareType
from app.schemas import (
    FxRateUpsert,
    IncomeCreate,
    PurchaseCreate,
    PurchasePayerCreate,
)


class TestYearMonthRegex:
    def test_valid(self):
        r = FxRateUpsert(year_month="2025-01", currency=CurrencyCode.USD, rate_to_ars=1200)
        assert r.year_month == "2025-01"

    def test_valid_december(self):
        r = FxRateUpsert(year_month="2025-12", currency=CurrencyCode.USD, rate_to_ars=1200)
        assert r.year_month == "2025-12"

    def test_invalid_month_13(self):
        with pytest.raises(ValidationError):
            FxRateUpsert(year_month="2025-13", currency=CurrencyCode.USD, rate_to_ars=1200)

    def test_invalid_month_00(self):
        with pytest.raises(ValidationError):
            FxRateUpsert(year_month="2025-00", currency=CurrencyCode.USD, rate_to_ars=1200)

    def test_invalid_format(self):
        with pytest.raises(ValidationError):
            FxRateUpsert(year_month="abc", currency=CurrencyCode.USD, rate_to_ars=1200)

    def test_invalid_single_digit_month(self):
        with pytest.raises(ValidationError):
            FxRateUpsert(year_month="2025-1", currency=CurrencyCode.USD, rate_to_ars=1200)


class TestShareValueConstraint:
    def test_positive_share(self):
        p = PurchasePayerCreate(person_id=1, share_type=ShareType.PERCENT, share_value=50)
        assert p.share_value == 50

    def test_zero_share_rejected(self):
        with pytest.raises(ValidationError):
            PurchasePayerCreate(person_id=1, share_type=ShareType.PERCENT, share_value=0)

    def test_negative_share_rejected(self):
        with pytest.raises(ValidationError):
            PurchasePayerCreate(person_id=1, share_type=ShareType.PERCENT, share_value=-10)


class TestPayerSharesSum:
    def test_percent_sums_100(self):
        p = PurchaseCreate(
            card_id=1,
            payment_method=PaymentMethod.CARD,
            purchase_date=date(2025, 1, 15),
            description="Test",
            currency=CurrencyCode.ARS,
            amount_original=1000,
            payers=[
                PurchasePayerCreate(person_id=1, share_type=ShareType.PERCENT, share_value=60),
                PurchasePayerCreate(person_id=2, share_type=ShareType.PERCENT, share_value=40),
            ],
        )
        assert len(p.payers) == 2

    def test_percent_not_100_rejected(self):
        with pytest.raises(ValidationError, match="must sum to 100"):
            PurchaseCreate(
                card_id=1,
                payment_method=PaymentMethod.CARD,
                purchase_date=date(2025, 1, 15),
                description="Test",
                currency=CurrencyCode.ARS,
                amount_original=1000,
                payers=[
                    PurchasePayerCreate(person_id=1, share_type=ShareType.PERCENT, share_value=60),
                    PurchasePayerCreate(person_id=2, share_type=ShareType.PERCENT, share_value=20),
                ],
            )

    def test_fixed_shares_no_sum_validation(self):
        """FIXED shares don't require summing to 100."""
        p = PurchaseCreate(
            card_id=1,
            payment_method=PaymentMethod.CARD,
            purchase_date=date(2025, 1, 15),
            description="Test",
            currency=CurrencyCode.ARS,
            amount_original=1000,
            payers=[
                PurchasePayerCreate(person_id=1, share_type=ShareType.FIXED, share_value=600),
                PurchasePayerCreate(person_id=2, share_type=ShareType.FIXED, share_value=400),
            ],
        )
        assert len(p.payers) == 2


class TestCardRequired:
    def test_card_method_without_card_rejected(self):
        with pytest.raises(ValidationError, match="card_id is required"):
            PurchaseCreate(
                card_id=None,
                payment_method=PaymentMethod.CARD,
                purchase_date=date(2025, 1, 15),
                description="Test",
                currency=CurrencyCode.ARS,
                amount_original=1000,
            )

    def test_transfer_without_card_ok(self):
        p = PurchaseCreate(
            card_id=None,
            payment_method=PaymentMethod.TRANSFER,
            purchase_date=date(2025, 1, 15),
            description="Test",
            currency=CurrencyCode.ARS,
            amount_original=1000,
            owner_person_id=1,
        )
        assert p.card_id is None

    def test_cash_without_card_ok(self):
        p = PurchaseCreate(
            card_id=None,
            payment_method=PaymentMethod.CASH,
            purchase_date=date(2025, 1, 15),
            description="Test",
            currency=CurrencyCode.ARS,
            amount_original=1000,
            owner_person_id=1,
        )
        assert p.payment_method == PaymentMethod.CASH


class TestIncomeValidation:
    def test_valid_income(self):
        i = IncomeCreate(person_id=1, year_month="2025-01", amount=500000)
        assert i.amount == 500000

    def test_zero_amount_rejected(self):
        with pytest.raises(ValidationError):
            IncomeCreate(person_id=1, year_month="2025-01", amount=0)

    def test_negative_amount_rejected(self):
        with pytest.raises(ValidationError):
            IncomeCreate(person_id=1, year_month="2025-01", amount=-100)

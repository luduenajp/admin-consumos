"""Tests for purchase CRUD, installment schedule, and related logic."""
from datetime import date

import pytest
from sqlmodel import select

from app.crud import (
    create_purchase,
    delete_purchase,
    find_existing_purchase_for_installment_import,
    list_purchases,
    update_purchase,
)
from app.models import (
    CurrencyCode,
    InstallmentSchedule,
    PaymentMethod,
    Purchase,
    PurchasePayer,
    ShareType,
)
from app.schemas import (
    PurchaseCreate,
    PurchasePayerCreate,
    PurchaseUpdate,
)


class TestCreatePurchase:
    def test_with_card_default_payer(self, session, two_person_scenario):
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Supermercado",
                currency=CurrencyCode.ARS,
                amount_original=50000,
            ),
        )
        assert p.id is not None
        payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.purchase_id == p.id)))
        assert len(payers) == 1
        assert payers[0].person_id == s["alice"].id
        assert payers[0].share_type == ShareType.PERCENT
        assert payers[0].share_value == 100.0

    def test_without_card_with_owner(self, session, two_person_scenario):
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=None,
                payment_method=PaymentMethod.TRANSFER,
                purchase_date=date(2025, 1, 15),
                description="Transferencia",
                currency=CurrencyCode.ARS,
                amount_original=10000,
                owner_person_id=s["alice"].id,
            ),
        )
        assert p.id is not None
        assert p.payment_method == PaymentMethod.TRANSFER

    def test_invalid_card_raises(self, session):
        with pytest.raises(ValueError, match="Card not found"):
            create_purchase(
                session=session,
                payload=PurchaseCreate(
                    card_id=9999,
                    purchase_date=date(2025, 1, 15),
                    description="Test",
                    currency=CurrencyCode.ARS,
                    amount_original=1000,
                ),
            )

    def test_invalid_owner_raises(self, session, two_person_scenario):
        with pytest.raises(ValueError, match="Person not found"):
            create_purchase(
                session=session,
                payload=PurchaseCreate(
                    card_id=None,
                    payment_method=PaymentMethod.CASH,
                    purchase_date=date(2025, 1, 15),
                    description="Test",
                    currency=CurrencyCode.ARS,
                    amount_original=1000,
                    owner_person_id=9999,
                ),
            )

    def test_explicit_payers(self, session, two_person_scenario):
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Shared",
                currency=CurrencyCode.ARS,
                amount_original=10000,
                payers=[
                    PurchasePayerCreate(person_id=s["alice"].id, share_type=ShareType.PERCENT, share_value=60),
                    PurchasePayerCreate(person_id=s["bob"].id, share_type=ShareType.PERCENT, share_value=40),
                ],
            ),
        )
        payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.purchase_id == p.id)))
        assert len(payers) == 2
        shares = {pp.person_id: pp.share_value for pp in payers}
        assert shares[s["alice"].id] == 60.0
        assert shares[s["bob"].id] == 40.0


class TestInstallmentSchedule:
    def test_single_installment(self, session, two_person_scenario):
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="One-time",
                currency=CurrencyCode.ARS,
                amount_original=50000,
                installments_total=1,
            ),
        )
        schedules = list(
            session.exec(select(InstallmentSchedule).where(InstallmentSchedule.purchase_id == p.id))
        )
        assert len(schedules) == 1
        assert schedules[0].installment_index == 1
        assert schedules[0].amount_original == 50000.0
        assert schedules[0].year_month == "2025-01"

    def test_twelve_installments(self, session, two_person_scenario):
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="TV",
                currency=CurrencyCode.ARS,
                amount_original=120000,
                installments_total=12,
            ),
        )
        schedules = list(
            session.exec(
                select(InstallmentSchedule)
                .where(InstallmentSchedule.purchase_id == p.id)
                .order_by(InstallmentSchedule.installment_index)
            )
        )
        assert len(schedules) == 12
        assert schedules[0].year_month == "2025-01"
        assert schedules[11].year_month == "2025-12"
        assert all(s.amount_original == 10000.0 for s in schedules)

    def test_custom_first_installment_month(self, session, two_person_scenario):
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Delayed",
                currency=CurrencyCode.ARS,
                amount_original=60000,
                installments_total=3,
                first_installment_month="2025-03",
            ),
        )
        schedules = list(
            session.exec(
                select(InstallmentSchedule)
                .where(InstallmentSchedule.purchase_id == p.id)
                .order_by(InstallmentSchedule.installment_index)
            )
        )
        assert schedules[0].year_month == "2025-03"
        assert schedules[1].year_month == "2025-04"
        assert schedules[2].year_month == "2025-05"


class TestDeletePurchase:
    def test_deletes_purchase_and_children(self, session, two_person_scenario):
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="To Delete",
                currency=CurrencyCode.ARS,
                amount_original=10000,
                installments_total=3,
            ),
        )
        pid = p.id
        delete_purchase(session=session, purchase_id=pid)

        assert session.get(Purchase, pid) is None
        assert list(session.exec(select(InstallmentSchedule).where(InstallmentSchedule.purchase_id == pid))) == []
        assert list(session.exec(select(PurchasePayer).where(PurchasePayer.purchase_id == pid))) == []

    def test_delete_nonexistent_raises(self, session):
        with pytest.raises(ValueError, match="not found"):
            delete_purchase(session=session, purchase_id=9999)


class TestUpdatePurchase:
    def test_update_notes_and_category(self, session, two_person_scenario):
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Something",
                currency=CurrencyCode.ARS,
                amount_original=5000,
            ),
        )
        updated = update_purchase(
            session=session,
            purchase_id=p.id,
            payload=PurchaseUpdate(notes="my note", category="supermercado"),
        )
        assert updated.notes == "my note"
        assert updated.category == "supermercado"


class TestFindExistingPurchaseForInstallmentImport:
    def test_exact_match(self, session, two_person_scenario):
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="MERPAGO*TIENDA",
                currency=CurrencyCode.ARS,
                amount_original=30000,
                installments_total=3,
                installment_amount_original=10000,
            ),
        )
        found = find_existing_purchase_for_installment_import(
            session=session,
            card_id=s["alice_card"].id,
            purchase_date=date(2025, 1, 15),
            description="MERPAGO*TIENDA",
            currency=CurrencyCode.ARS,
            installments_total=3,
            installment_amount_original=10000,
        )
        assert found is not None
        assert found.id == p.id

    def test_no_match(self, session, two_person_scenario):
        s = two_person_scenario
        found = find_existing_purchase_for_installment_import(
            session=session,
            card_id=s["alice_card"].id,
            purchase_date=date(2025, 1, 15),
            description="NONEXISTENT",
            currency=CurrencyCode.ARS,
            installments_total=3,
            installment_amount_original=10000,
        )
        assert found is None

    def test_fuzzy_match_single_candidate(self, session, two_person_scenario):
        """Fuzzy match: same date/card/currency/amount but different description."""
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Original Name",
                currency=CurrencyCode.ARS,
                amount_original=30000,
                installments_total=3,
                installment_amount_original=10000,
            ),
        )
        found = find_existing_purchase_for_installment_import(
            session=session,
            card_id=s["alice_card"].id,
            purchase_date=date(2025, 1, 15),
            description="Renamed By User",
            currency=CurrencyCode.ARS,
            installments_total=3,
            installment_amount_original=10000,
        )
        assert found is not None
        assert found.id == p.id

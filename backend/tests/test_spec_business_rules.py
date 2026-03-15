"""
Tests explícitamente mapeados a las Business Rules del SPEC.md.
Cada clase y test cita el BR-XXX correspondiente.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import select

from app.crud import (
    _normalize_installment_amount,
    _round_money,
    calculate_monthly_balance,
    create_income,
    create_person,
    create_purchase,
    delete_purchase,
    list_people,
    report_month_breakdown,
    upsert_fx_rate,
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
    CardCreate,
    FxRateUpsert,
    IncomeCreate,
    MonthlyBudgetCreate,
    PersonCreate,
    PurchaseCreate,
    PurchasePayerCreate,
)
from app.crud import create_card, create_monthly_budget


# ---------------------------------------------------------------------------
# BR-007: _round_money con nudge de floating-point
# ---------------------------------------------------------------------------

class TestBR007RoundMoney:
    def test_nudge_fixes_float_representation(self):
        """BR-007: round(value + 1e-9, 2) corrige 0.994999... → 0.995 → 1.00."""
        # 100 / 3 * 3 puede dar 99.99999... en float
        # _round_money debe devolver 100.0, no 99.99
        result = _round_money(100 / 3 * 3)
        assert result == 100.0

    def test_normal_rounding_unchanged(self):
        """BR-007: valores normales no se ven afectados por el nudge."""
        assert _round_money(1234.567) == 1234.57
        assert _round_money(0.005) == 0.01  # el nudge empuja 0.005 a 0.01

    def test_integer_value(self):
        assert _round_money(50000.0) == 50000.0

    def test_two_decimal_places(self):
        assert _round_money(123.456) == 123.46


# ---------------------------------------------------------------------------
# BR-007: _normalize_installment_amount — las tres ramas
# ---------------------------------------------------------------------------

class TestBR007NormalizeInstallmentAmount:
    def test_single_installment_uses_total(self):
        """BR-007: installments_total ≤ 1 → installment_amount = amount_original."""
        result = _normalize_installment_amount(
            amount_original=50000,
            installments_total=1,
            installment_amount_original=None,
        )
        assert result == 50000.0

    def test_uses_provided_installment_amount(self):
        """BR-007: si se provee installment_amount_original, se usa directamente."""
        result = _normalize_installment_amount(
            amount_original=30000,
            installments_total=3,
            installment_amount_original=10500,
        )
        assert result == 10500.0

    def test_divides_when_no_installment_amount(self):
        """BR-007: sin installment_amount_original → amount_original / installments_total."""
        result = _normalize_installment_amount(
            amount_original=30000,
            installments_total=3,
            installment_amount_original=None,
        )
        assert result == 10000.0


# ---------------------------------------------------------------------------
# BR-008: amount_ars es siempre None en InstallmentSchedule
# ---------------------------------------------------------------------------

class TestBR008InstallmentAmountArsAlwaysNone:
    def test_amount_ars_is_none(self, session, two_person_scenario):
        """BR-008: InstallmentSchedule.amount_ars siempre es None. Conversión es en query time."""
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Test",
                currency=CurrencyCode.USD,
                amount_original=100,
                installments_total=3,
            ),
        )
        schedules = list(
            session.exec(select(InstallmentSchedule).where(InstallmentSchedule.purchase_id == p.id))
        )
        assert all(sch.amount_ars is None for sch in schedules)


# ---------------------------------------------------------------------------
# BR-004: Default payer logic
# ---------------------------------------------------------------------------

class TestBR004DefaultPayer:
    def test_no_card_no_owner_raises(self, session):
        """BR-004: sin card_id ni owner_person_id debe lanzar ValueError."""
        with pytest.raises(ValueError, match="owner_person_id is required"):
            create_purchase(
                session=session,
                payload=PurchaseCreate(
                    card_id=None,
                    payment_method=PaymentMethod.CASH,
                    purchase_date=date(2025, 1, 15),
                    description="Cash expense",
                    currency=CurrencyCode.ARS,
                    amount_original=1000,
                    owner_person_id=None,
                ),
            )

    def test_with_card_defaults_to_card_owner(self, session, two_person_scenario):
        """BR-004: con card, el payer default es card.owner_person_id al 100%."""
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Default payer",
                currency=CurrencyCode.ARS,
                amount_original=5000,
            ),
        )
        payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.purchase_id == p.id)))
        assert len(payers) == 1
        assert payers[0].person_id == s["alice"].id
        assert payers[0].share_type == ShareType.PERCENT
        assert payers[0].share_value == 100.0

    def test_without_card_with_owner_defaults_to_owner(self, session, two_person_scenario):
        """BR-004: sin card pero con owner_person_id, el payer default es owner."""
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=None,
                payment_method=PaymentMethod.TRANSFER,
                purchase_date=date(2025, 1, 15),
                description="Transfer expense",
                currency=CurrencyCode.ARS,
                amount_original=5000,
                owner_person_id=s["bob"].id,
            ),
        )
        payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.purchase_id == p.id)))
        assert len(payers) == 1
        assert payers[0].person_id == s["bob"].id


# ---------------------------------------------------------------------------
# BR-011: Manual cascade delete
# ---------------------------------------------------------------------------

class TestBR011ManualCascadeDelete:
    def test_delete_removes_installments_and_payers(self, session, two_person_scenario):
        """BR-011: delete_purchase elimina installments y payers antes del padre."""
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Will be deleted",
                currency=CurrencyCode.ARS,
                amount_original=60000,
                installments_total=6,
                payers=[
                    PurchasePayerCreate(person_id=s["alice"].id, share_type=ShareType.PERCENT, share_value=60),
                    PurchasePayerCreate(person_id=s["bob"].id, share_type=ShareType.PERCENT, share_value=40),
                ],
            ),
        )
        pid = p.id
        # Verify children exist
        assert len(list(session.exec(select(InstallmentSchedule).where(InstallmentSchedule.purchase_id == pid)))) == 6
        assert len(list(session.exec(select(PurchasePayer).where(PurchasePayer.purchase_id == pid)))) == 2

        delete_purchase(session=session, purchase_id=pid)

        # All children must be gone
        assert session.get(Purchase, pid) is None
        assert list(session.exec(select(InstallmentSchedule).where(InstallmentSchedule.purchase_id == pid))) == []
        assert list(session.exec(select(PurchasePayer).where(PurchasePayer.purchase_id == pid))) == []


# ---------------------------------------------------------------------------
# BR-012: sobrante_por_persona hardcodeado en /2
# ---------------------------------------------------------------------------

class TestBR012SobrantePorPersonaHardcoded:
    def test_sobrante_divided_by_two(self, session, two_person_scenario):
        """BR-012: sobrante_por_persona = sobrante_total / 2 (hardcodeado para 2 personas)."""
        s = two_person_scenario
        create_monthly_budget(
            session=session,
            payload=MonthlyBudgetCreate(year_month="2025-01", total_income=1000000),
        )
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Expense",
                currency=CurrencyCode.ARS,
                amount_original=400000,
                first_installment_month="2025-01",
            ),
        )
        balance = calculate_monthly_balance(session=session, year_month="2025-01")
        assert balance is not None
        assert balance["sobrante_total"] == 600000.0
        assert balance["sobrante_por_persona"] == 300000.0  # siempre /2


# ---------------------------------------------------------------------------
# BR-013: Atomic purchase creation (flush + single commit)
# ---------------------------------------------------------------------------

class TestBR013AtomicPurchaseCreation:
    def test_purchase_id_available_for_payers_and_schedule(self, session, two_person_scenario):
        """BR-013: session.flush() provee el purchase.id antes del commit, permitiendo crear hijos."""
        s = two_person_scenario
        p = create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="Atomic test",
                currency=CurrencyCode.ARS,
                amount_original=12000,
                installments_total=3,
                payers=[
                    PurchasePayerCreate(person_id=s["alice"].id, share_type=ShareType.PERCENT, share_value=100),
                ],
            ),
        )
        # All three entities must share the same purchase.id
        payers = list(session.exec(select(PurchasePayer).where(PurchasePayer.purchase_id == p.id)))
        schedules = list(session.exec(select(InstallmentSchedule).where(InstallmentSchedule.purchase_id == p.id)))
        assert len(payers) == 1
        assert len(schedules) == 3
        assert all(pp.purchase_id == p.id for pp in payers)
        assert all(sch.purchase_id == p.id for sch in schedules)


# ---------------------------------------------------------------------------
# BR-024: Person filter allocation con FIXED shares
# ---------------------------------------------------------------------------

class TestBR024FixedShareAllocation:
    def test_fixed_share_uses_value_directly(self, session, two_person_scenario):
        """BR-024: con FIXED share, el monto asignado a la persona es share_value directo."""
        s = two_person_scenario
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="FIXED split",
                currency=CurrencyCode.ARS,
                amount_original=10000,
                first_installment_month="2025-01",
                payers=[
                    PurchasePayerCreate(person_id=s["alice"].id, share_type=ShareType.FIXED, share_value=7000),
                    PurchasePayerCreate(person_id=s["bob"].id, share_type=ShareType.FIXED, share_value=3000),
                ],
            ),
        )
        # Alice debe recibir exactamente 7000, Bob exactamente 3000
        total_alice, _ = report_month_breakdown(
            session=session, year_month="2025-01", person_id=s["alice"].id
        )
        total_bob, _ = report_month_breakdown(
            session=session, year_month="2025-01", person_id=s["bob"].id
        )
        assert total_alice == 7000.0
        assert total_bob == 3000.0

    def test_percent_share_uses_proportion(self, session, two_person_scenario):
        """BR-024: con PERCENT share, el monto es proporcional."""
        s = two_person_scenario
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="PERCENT split",
                currency=CurrencyCode.ARS,
                amount_original=10000,
                first_installment_month="2025-01",
                payers=[
                    PurchasePayerCreate(person_id=s["alice"].id, share_type=ShareType.PERCENT, share_value=70),
                    PurchasePayerCreate(person_id=s["bob"].id, share_type=ShareType.PERCENT, share_value=30),
                ],
            ),
        )
        total_alice, _ = report_month_breakdown(
            session=session, year_month="2025-01", person_id=s["alice"].id
        )
        total_bob, _ = report_month_breakdown(
            session=session, year_month="2025-01", person_id=s["bob"].id
        )
        assert total_alice == 7000.0
        assert total_bob == 3000.0


# ---------------------------------------------------------------------------
# BR-002 / BR-019: FX missing = skip (no zero)
# ---------------------------------------------------------------------------

class TestBR002FxMissingSkip:
    def test_usd_without_fx_excluded_not_zero(self, session, two_person_scenario):
        """BR-002: USD sin FX rate se excluye (skip), no cuenta como 0."""
        s = two_person_scenario
        # ARS purchase: 50000
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 3, 15),
                description="ARS item",
                currency=CurrencyCode.ARS,
                amount_original=50000,
                first_installment_month="2025-03",
            ),
        )
        # USD purchase sin FX para 2025-03
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 3, 15),
                description="USD item",
                currency=CurrencyCode.USD,
                amount_original=100,
                first_installment_month="2025-03",
            ),
        )
        total, items = report_month_breakdown(session=session, year_month="2025-03")
        # Solo el ARS aparece; el USD está completamente excluido
        assert total == 50000.0
        assert len(items) == 1
        assert items[0][0].description == "ARS item"

    def test_usd_with_fx_included(self, session, two_person_scenario):
        """BR-019: USD con FX rate se convierte correctamente."""
        s = two_person_scenario
        # FX para 2025-01 ya existe (rate=1200) desde el fixture two_person_scenario
        create_purchase(
            session=session,
            payload=PurchaseCreate(
                card_id=s["alice_card"].id,
                purchase_date=date(2025, 1, 15),
                description="USD item with FX",
                currency=CurrencyCode.USD,
                amount_original=50,
                first_installment_month="2025-01",
            ),
        )
        total, items = report_month_breakdown(session=session, year_month="2025-01")
        assert total == 60000.0  # 50 USD * 1200


# ---------------------------------------------------------------------------
# UC-001: Duplicate people allowed (sin unicidad en nombre)
# ---------------------------------------------------------------------------

class TestUC001DuplicatePeopleAllowed:
    def test_two_people_same_name(self, session):
        """UC-001: no hay constraint de unicidad en Person.name — duplicados permitidos."""
        p1 = create_person(session=session, payload=PersonCreate(name="Juan"))
        p2 = create_person(session=session, payload=PersonCreate(name="Juan"))
        assert p1.id != p2.id
        assert p1.name == p2.name
        people = list_people(session=session)
        assert len(people) == 2


# ---------------------------------------------------------------------------
# BR-003: PERCENT/FIXED mixto no activa validación de suma
# ---------------------------------------------------------------------------

class TestBR003MixedShareTypes:
    def test_mixed_percent_and_fixed_no_sum_validation(self, session, two_person_scenario):
        """BR-003: la validación de suma 100 solo aplica cuando TODOS los payers son PERCENT."""
        from app.schemas import PurchaseCreate, PurchasePayerCreate
        from app.models import CurrencyCode, PaymentMethod, ShareType

        # Si hay al menos un FIXED, no debe aplicar la validación de suma PERCENT
        p = PurchaseCreate(
            card_id=1,
            payment_method=PaymentMethod.CARD,
            purchase_date=date(2025, 1, 15),
            description="Mixed",
            currency=CurrencyCode.ARS,
            amount_original=1000,
            payers=[
                PurchasePayerCreate(person_id=1, share_type=ShareType.PERCENT, share_value=60),
                PurchasePayerCreate(person_id=2, share_type=ShareType.FIXED, share_value=400),
            ],
        )
        # No debe lanzar ValidationError (mezcla PERCENT + FIXED no se valida)
        assert len(p.payers) == 2


# ---------------------------------------------------------------------------
# BR-022: MonthlyBudget upsert
# ---------------------------------------------------------------------------

class TestBR022MonthlyBudgetUpsert:
    def test_upsert_creates_new(self, session):
        """BR-022: crear budget para mes nuevo crea registro."""
        budget = create_monthly_budget(
            session=session,
            payload=MonthlyBudgetCreate(year_month="2025-04", total_income=500000),
        )
        assert budget.id is not None
        assert budget.year_month == "2025-04"

    def test_upsert_updates_existing(self, session):
        """BR-022: crear budget para mes que ya existe actualiza el registro."""
        create_monthly_budget(
            session=session,
            payload=MonthlyBudgetCreate(year_month="2025-04", total_income=500000),
        )
        updated = create_monthly_budget(
            session=session,
            payload=MonthlyBudgetCreate(year_month="2025-04", total_income=750000, notes="actualizado"),
        )
        assert updated.total_income == 750000
        assert updated.notes == "actualizado"

    def test_upsert_does_not_create_duplicate(self, session):
        """BR-022: hacer upsert dos veces para el mismo mes no crea dos registros."""
        from sqlmodel import select
        from app.models import MonthlyBudget

        create_monthly_budget(session=session, payload=MonthlyBudgetCreate(year_month="2025-04", total_income=500000))
        create_monthly_budget(session=session, payload=MonthlyBudgetCreate(year_month="2025-04", total_income=600000))
        budgets = list(session.exec(select(MonthlyBudget).where(MonthlyBudget.year_month == "2025-04")))
        assert len(budgets) == 1
        assert budgets[0].total_income == 600000

"""
Tests de deduplicación end-to-end (BR-005).
Simula el flujo completo de importación: importar → re-importar → verificar skipped.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlmodel import select

from app.crud import create_person, create_card
from app.importers.visa_xlsx import (
    ParsedPurchaseRow,
    compute_row_fingerprint,
    mark_imported,
    was_already_imported,
)
from app.import_api import _process_installment_row
from app.models import ImportedRow, Purchase
from app.schemas import CardCreate, PersonCreate


@pytest.fixture()
def import_scenario(session):
    """Persona + tarjeta listos para importar."""
    alice = create_person(session=session, payload=PersonCreate(name="Alice"))
    card = create_card(
        session=session,
        payload=CardCreate(name="Visa Alice", provider="visa", owner_person_id=alice.id),
    )
    return {"alice": alice, "card": card}


def _make_row(description="MERPAGO*TIENDA", amount=10000.0, idx=1, total=3, occurrence=1):
    return ParsedPurchaseRow(
        purchase_date=date(2025, 1, 15),
        description=description,
        currency="ARS",
        installment_index=idx,
        installments_total=total,
        installment_amount=amount,
        statement_year_month="2025-01",
        occurrence_index=occurrence,
    )


class TestFingerprintDeduplication:
    def test_was_already_imported_false_initially(self, session, import_scenario):
        """BR-005: fingerprint nuevo → was_already_imported devuelve False."""
        row = _make_row()
        fp = compute_row_fingerprint(provider="visa_xlsx", card_id=import_scenario["card"].id, row=row)
        assert was_already_imported(session=session, fingerprint=fp) is False

    def test_mark_imported_then_was_already_imported_true(self, session, import_scenario):
        """BR-005: después de mark_imported, was_already_imported devuelve True."""
        row = _make_row()
        fp = compute_row_fingerprint(provider="visa_xlsx", card_id=import_scenario["card"].id, row=row)
        mark_imported(
            session=session,
            provider="visa_xlsx",
            source_file="test.xlsx",
            fingerprint=fp,
            payload={"desc": "test"},
        )
        session.commit()
        assert was_already_imported(session=session, fingerprint=fp) is True

    def test_different_rows_different_fingerprints(self, import_scenario):
        """BR-005: dos filas distintas producen fingerprints distintos."""
        row1 = _make_row(description="TIENDA A")
        row2 = _make_row(description="TIENDA B")
        fp1 = compute_row_fingerprint(provider="visa_xlsx", card_id=import_scenario["card"].id, row=row1)
        fp2 = compute_row_fingerprint(provider="visa_xlsx", card_id=import_scenario["card"].id, row=row2)
        assert fp1 != fp2

    def test_same_row_different_occurrence_different_fingerprint(self, import_scenario):
        """BR-005: misma compra dos veces en el mismo día → occurrence_index las distingue."""
        row1 = _make_row(occurrence=1)
        row2 = _make_row(occurrence=2)
        fp1 = compute_row_fingerprint(provider="visa_xlsx", card_id=import_scenario["card"].id, row=row1)
        fp2 = compute_row_fingerprint(provider="visa_xlsx", card_id=import_scenario["card"].id, row=row2)
        assert fp1 != fp2

    def test_fingerprint_is_deterministic(self, import_scenario):
        """BR-005: mismo input siempre produce el mismo fingerprint."""
        row = _make_row()
        fp1 = compute_row_fingerprint(provider="visa_xlsx", card_id=import_scenario["card"].id, row=row)
        fp2 = compute_row_fingerprint(provider="visa_xlsx", card_id=import_scenario["card"].id, row=row)
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA256 hex = 64 chars


class TestProcessInstallmentRowEndToEnd:
    def test_first_import_creates_purchase(self, session, import_scenario):
        """BR-005 end-to-end: primera importación crea el Purchase y retorna True."""
        row = _make_row()
        claimed: list[int] = []
        result = _process_installment_row(
            session=session,
            r=row,
            card_id=import_scenario["card"].id,
            provider="visa_xlsx",
            filename="test.xlsx",
            is_common=False,
            claimed_ids=claimed,
        )
        assert result is True
        purchases = list(session.exec(select(Purchase)))
        assert len(purchases) == 1

    def test_reimport_skips_same_row(self, session, import_scenario):
        """BR-005 end-to-end: reimportar la misma fila → retorna False y no crea duplicado."""
        row = _make_row()
        claimed: list[int] = []
        # Primera importación
        _process_installment_row(
            session=session,
            r=row,
            card_id=import_scenario["card"].id,
            provider="visa_xlsx",
            filename="test.xlsx",
            is_common=False,
            claimed_ids=claimed,
        )
        # Re-importación
        result = _process_installment_row(
            session=session,
            r=row,
            card_id=import_scenario["card"].id,
            provider="visa_xlsx",
            filename="test.xlsx",
            is_common=False,
            claimed_ids=[],
        )
        assert result is False
        # Solo debe haber 1 Purchase
        purchases = list(session.exec(select(Purchase)))
        assert len(purchases) == 1

    def test_multiple_rows_all_imported_then_all_skipped(self, session, import_scenario):
        """BR-005: importar N filas → re-importar las mismas N → todas skipped."""
        rows = [
            _make_row(description="TIENDA A", idx=1),
            _make_row(description="TIENDA B", idx=1),
            _make_row(description="TIENDA C", idx=1),
        ]
        card_id = import_scenario["card"].id

        # Primera pasada
        created = 0
        for r in rows:
            if _process_installment_row(
                session=session, r=r, card_id=card_id,
                provider="visa_xlsx", filename="test.xlsx",
                is_common=False, claimed_ids=[],
            ):
                created += 1
        assert created == 3

        # Segunda pasada (re-import)
        skipped = 0
        for r in rows:
            if not _process_installment_row(
                session=session, r=r, card_id=card_id,
                provider="visa_xlsx", filename="test.xlsx",
                is_common=False, claimed_ids=[],
            ):
                skipped += 1
        assert skipped == 3

    def test_reimport_later_installment_adds_schedule_no_new_purchase(self, session, import_scenario):
        """
        BR-005 + BR-018: importar cuota 1/3 crea el Purchase con 3 schedules.
        Importar cuota 2/3 del mismo Purchase no crea nuevo Purchase — solo agrega el schedule faltante.
        """
        card_id = import_scenario["card"].id
        row_cuota1 = _make_row(description="TIENDA NUBE", amount=10000, idx=1, total=3)
        row_cuota2 = _make_row(description="TIENDA NUBE", amount=10000, idx=2, total=3)

        # statement_year_month distinto para que tengan fingerprints distintos
        row_cuota2 = ParsedPurchaseRow(
            purchase_date=date(2025, 1, 15),
            description="TIENDA NUBE",
            currency="ARS",
            installment_index=2,
            installments_total=3,
            installment_amount=10000.0,
            statement_year_month="2025-02",
            occurrence_index=1,
        )

        # Importar cuota 1
        claimed: list[int] = []
        result1 = _process_installment_row(
            session=session, r=row_cuota1, card_id=card_id,
            provider="visa_xlsx", filename="enero.xlsx",
            is_common=False, claimed_ids=claimed,
        )
        assert result1 is True
        assert len(list(session.exec(select(Purchase)))) == 1

        # Importar cuota 2 (del mismo Purchase, distinto statement_year_month)
        result2 = _process_installment_row(
            session=session, r=row_cuota2, card_id=card_id,
            provider="visa_xlsx", filename="febrero.xlsx",
            is_common=False, claimed_ids=[],
        )
        assert result2 is True
        # Sigue siendo 1 Purchase, no creó otro
        assert len(list(session.exec(select(Purchase)))) == 1

    def test_importedrow_record_created_on_import(self, session, import_scenario):
        """BR-005: cada fila importada genera un registro en ImportedRow."""
        row = _make_row()
        _process_installment_row(
            session=session,
            r=row,
            card_id=import_scenario["card"].id,
            provider="visa_xlsx",
            filename="test.xlsx",
            is_common=False,
            claimed_ids=[],
        )
        imported_rows = list(session.exec(select(ImportedRow)))
        assert len(imported_rows) == 1
        assert imported_rows[0].provider == "visa_xlsx"
        assert imported_rows[0].source_file == "test.xlsx"

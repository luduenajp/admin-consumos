"""
Tests for deduplication fixes from the dedupe sprint (Tasks 1-4).

Groups:
  A) Re-import of installment from a later statement month does NOT create a duplicate InstallmentSchedule
  B) _has_installment_by_index correctly detects an existing installment by index (regardless of year_month)
  C) POST /purchases returns 409 on strict duplicate
  D) POST /purchases returns 200 on same-day/amount with different normalized description
  E) normalize_purchase_description behavior: both backend and gmail versions strip codes/installment
     markers identically; cross-source case mismatch is documented as a known limitation.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select, text

from app.crud import create_card, create_person, find_duplicate_purchase
from app.import_api import _has_installment_by_index, _process_installment_row
from app.importers.visa_xlsx import (
    ParsedPurchaseRow,
    normalize_purchase_description as backend_norm,
)
from app.models import InstallmentSchedule, Purchase
from app.schemas import CardCreate, PersonCreate


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_row(
    description="MERPAGO*TIENDA",
    amount=10000.0,
    idx=1,
    total=3,
    statement_ym="2025-01",
    purchase_date=date(2025, 1, 15),
    currency="ARS",
):
    return ParsedPurchaseRow(
        purchase_date=purchase_date,
        description=description,
        currency=currency,
        installment_index=idx,
        installments_total=total,
        installment_amount=amount,
        statement_year_month=statement_ym,
        occurrence_index=1,
    )


@pytest.fixture()
def scenario(session):
    """One person + one card ready for import tests."""
    alice = create_person(session=session, payload=PersonCreate(name="Alice"))
    card = create_card(
        session=session,
        payload=CardCreate(name="Visa Alice", provider="visa", owner_person_id=alice.id),
    )
    return {"alice": alice, "card": card}


# ---------------------------------------------------------------------------
# A) Re-import of later statement month does NOT create duplicate InstallmentSchedule
# ---------------------------------------------------------------------------

class TestInstallmentNoDoubleDupe:
    def test_reimport_same_installment_index_does_not_create_duplicate_schedule(
        self, session, scenario
    ):
        """
        Import installment 1/3 from statement 2025-01, then import the SAME
        installment index 1 again from statement 2025-02 (different fingerprint).
        Must result in exactly ONE InstallmentSchedule row with installment_index=1.
        """
        card_id = scenario["card"].id

        row_first = _make_row(idx=1, total=3, statement_ym="2025-01")

        # Build a second row: same purchase, same index, different statement month → different fingerprint
        row_second = ParsedPurchaseRow(
            purchase_date=date(2025, 1, 15),
            description="MERPAGO*TIENDA",
            currency="ARS",
            installment_index=1,  # same index as first
            installments_total=3,
            installment_amount=10000.0,
            statement_year_month="2025-02",  # different → different fingerprint
            occurrence_index=1,
        )

        claimed: list[int] = []

        # First import creates the purchase (and all 3 schedules)
        result1 = _process_installment_row(
            session=session,
            r=row_first,
            card_id=card_id,
            provider="visa_xlsx",
            filename="enero.xlsx",
            is_common=False,
            claimed_ids=claimed,
        )
        assert result1 is True

        purchase_count_after_first = len(list(session.exec(select(Purchase))))
        assert purchase_count_after_first == 1

        # Second import: same installment_index on the same purchase from a later statement
        result2 = _process_installment_row(
            session=session,
            r=row_second,
            card_id=card_id,
            provider="visa_xlsx",
            filename="febrero.xlsx",
            is_common=False,
            claimed_ids=claimed,
        )
        assert result2 is True  # returns True (did something), but…

        # Still exactly 1 Purchase
        assert len(list(session.exec(select(Purchase)))) == 1

        # And exactly 1 InstallmentSchedule with installment_index=1 for that purchase
        purchase = session.exec(select(Purchase)).first()
        assert purchase is not None
        schedules_for_index_1 = list(
            session.exec(
                select(InstallmentSchedule).where(
                    InstallmentSchedule.purchase_id == purchase.id,
                    InstallmentSchedule.installment_index == 1,
                )
            )
        )
        assert len(schedules_for_index_1) == 1, (
            f"Expected 1 InstallmentSchedule for index=1, got {len(schedules_for_index_1)}"
        )

    def test_new_installment_index_is_added_not_skipped(self, session, scenario):
        """
        Import installment 1/3, then import installment 2/3 of the same purchase.
        The second row should ADD a new InstallmentSchedule for index=2, not skip it.
        """
        card_id = scenario["card"].id

        row_idx1 = _make_row(idx=1, total=3, statement_ym="2025-01")
        row_idx2 = ParsedPurchaseRow(
            purchase_date=date(2025, 1, 15),
            description="MERPAGO*TIENDA",
            currency="ARS",
            installment_index=2,
            installments_total=3,
            installment_amount=10000.0,
            statement_year_month="2025-02",
            occurrence_index=1,
        )

        claimed: list[int] = []
        _process_installment_row(
            session=session,
            r=row_idx1,
            card_id=card_id,
            provider="visa_xlsx",
            filename="enero.xlsx",
            is_common=False,
            claimed_ids=claimed,
        )

        result2 = _process_installment_row(
            session=session,
            r=row_idx2,
            card_id=card_id,
            provider="visa_xlsx",
            filename="febrero.xlsx",
            is_common=False,
            claimed_ids=claimed,
        )
        assert result2 is True

        purchase = session.exec(select(Purchase)).first()
        assert purchase is not None

        all_schedules = list(
            session.exec(
                select(InstallmentSchedule).where(
                    InstallmentSchedule.purchase_id == purchase.id
                )
            )
        )
        # Should have index 1 (from create_purchase) and index 2 (added by re-import)
        indices = {s.installment_index for s in all_schedules}
        assert 1 in indices
        assert 2 in indices


# ---------------------------------------------------------------------------
# B) _has_installment_by_index detects existing row by index (regardless of year_month)
# ---------------------------------------------------------------------------

class TestHasInstallmentByIndex:
    def test_returns_false_when_no_schedule_exists(self, session, scenario):
        card_id = scenario["card"].id
        row = _make_row(idx=1, total=3)
        claimed: list[int] = []
        _process_installment_row(
            session=session,
            r=row,
            card_id=card_id,
            provider="visa_xlsx",
            filename="test.xlsx",
            is_common=False,
            claimed_ids=claimed,
        )
        purchase = session.exec(select(Purchase)).first()
        assert purchase is not None

        # Index 1 exists; index 99 does not
        assert _has_installment_by_index(
            session=session, purchase_id=purchase.id, installment_index=99
        ) is False

    def test_returns_true_for_existing_index(self, session, scenario):
        card_id = scenario["card"].id
        row = _make_row(idx=1, total=3)
        claimed: list[int] = []
        _process_installment_row(
            session=session,
            r=row,
            card_id=card_id,
            provider="visa_xlsx",
            filename="test.xlsx",
            is_common=False,
            claimed_ids=claimed,
        )
        purchase = session.exec(select(Purchase)).first()
        assert purchase is not None

        assert _has_installment_by_index(
            session=session, purchase_id=purchase.id, installment_index=1
        ) is True

    def test_detects_index_regardless_of_year_month(self, session, scenario):
        """
        Even if the InstallmentSchedule has year_month != expected,
        _has_installment_by_index should detect it by index alone.
        """
        card_id = scenario["card"].id
        row = _make_row(idx=2, total=3, statement_ym="2025-01")
        # Manually import first so we have a purchase
        row1 = _make_row(idx=1, total=3, statement_ym="2025-01")
        claimed: list[int] = []
        _process_installment_row(
            session=session,
            r=row1,
            card_id=card_id,
            provider="visa_xlsx",
            filename="test.xlsx",
            is_common=False,
            claimed_ids=claimed,
        )
        purchase = session.exec(select(Purchase)).first()
        assert purchase is not None

        # Manually insert a schedule for index=2 with an "unexpected" year_month
        session.add(
            InstallmentSchedule(
                purchase_id=purchase.id,
                year_month="2099-01",  # wrong year_month on purpose
                installment_index=2,
                currency="ARS",
                amount_original=10000.0,
                amount_ars=None,
            )
        )
        session.commit()

        # Must still detect it
        assert _has_installment_by_index(
            session=session, purchase_id=purchase.id, installment_index=2
        ) is True


# ---------------------------------------------------------------------------
# C) POST /purchases returns 409 on strict duplicate
# ---------------------------------------------------------------------------

class TestPostPurchase409:
    """Integration tests using the FastAPI TestClient (client fixture)."""

    def _base_payload(self, card_id: int) -> dict:
        return {
            "card_id": card_id,
            "payment_method": "card",
            "purchase_date": "2025-03-10",
            "description": "TIENDA EJEMPLO",
            "currency": "ARS",
            "amount_original": 5000.0,
            "installments_total": 1,
            "installment_amount_original": 5000.0,
            "first_installment_month": "2025-04",
            "owner_person_id": None,
            "category": None,
            "notes": None,
            "is_refund": False,
            "is_common": False,
            "payers": [{"person_id": None, "share_type": "percent", "share_value": 100.0}],
        }

    def _setup_person_card(self, client) -> tuple[int, int]:
        """Create a person and card via API, return (person_id, card_id)."""
        r = client.post("/api/people", json={"name": "TestUser"})
        assert r.status_code == 200, r.text
        person_id = r.json()["id"]

        r = client.post(
            "/api/cards",
            json={"name": "Test Visa", "provider": "visa", "owner_person_id": person_id},
        )
        assert r.status_code == 200, r.text
        card_id = r.json()["id"]
        return person_id, card_id

    def test_second_identical_post_returns_409(self, client):
        """Posting the same purchase twice must return 409 on the second call."""
        person_id, card_id = self._setup_person_card(client)
        payload = self._base_payload(card_id)
        payload["payers"][0]["person_id"] = person_id

        r1 = client.post("/api/purchases", json=payload)
        assert r1.status_code == 200, r1.text

        r2 = client.post("/api/purchases", json=payload)
        assert r2.status_code == 409, f"Expected 409, got {r2.status_code}: {r2.text}"

    def test_duplicate_with_tiny_amount_diff_returns_409(self, client):
        """Amount within ±0.02 tolerance is still a duplicate → 409."""
        person_id, card_id = self._setup_person_card(client)
        payload = self._base_payload(card_id)
        payload["payers"][0]["person_id"] = person_id

        r1 = client.post("/api/purchases", json=payload)
        assert r1.status_code == 200

        payload2 = {**payload, "amount_original": 5000.01}  # within ±0.02
        payload2["installment_amount_original"] = 5000.01
        r2 = client.post("/api/purchases", json=payload2)
        assert r2.status_code == 409, f"Expected 409, got {r2.status_code}: {r2.text}"


# ---------------------------------------------------------------------------
# D) POST /purchases returns 200 on same-day/amount with different description
# ---------------------------------------------------------------------------

class TestPostPurchaseNotDuplicate:
    def _setup_person_card(self, client) -> tuple[int, int]:
        r = client.post("/api/people", json={"name": "TestUser2"})
        assert r.status_code == 200
        person_id = r.json()["id"]
        r = client.post(
            "/api/cards",
            json={"name": "Visa2", "provider": "visa", "owner_person_id": person_id},
        )
        assert r.status_code == 200
        card_id = r.json()["id"]
        return person_id, card_id

    def _base_payload(self, card_id: int, person_id: int) -> dict:
        return {
            "card_id": card_id,
            "payment_method": "card",
            "purchase_date": "2025-03-15",
            "description": "TIENDA A",
            "currency": "ARS",
            "amount_original": 3000.0,
            "installments_total": 1,
            "installment_amount_original": 3000.0,
            "first_installment_month": "2025-04",
            "owner_person_id": None,
            "category": None,
            "notes": None,
            "is_refund": False,
            "is_common": False,
            "payers": [{"person_id": person_id, "share_type": "percent", "share_value": 100.0}],
        }

    def test_different_description_same_date_amount_is_not_duplicate(self, client):
        """Same date + amount but different normalized description → 200, not 409."""
        person_id, card_id = self._setup_person_card(client)
        payload_a = self._base_payload(card_id, person_id)
        payload_b = {**payload_a, "description": "TIENDA B"}  # different description

        r1 = client.post("/api/purchases", json=payload_a)
        assert r1.status_code == 200

        r2 = client.post("/api/purchases", json=payload_b)
        assert r2.status_code == 200, (
            f"Expected 200 for different description, got {r2.status_code}: {r2.text}"
        )

    def test_different_date_same_description_amount_is_not_duplicate(self, client):
        """Same description + amount but different date → 200."""
        person_id, card_id = self._setup_person_card(client)
        payload = self._base_payload(card_id, person_id)

        r1 = client.post("/api/purchases", json=payload)
        assert r1.status_code == 200

        payload2 = {**payload, "purchase_date": "2025-03-20"}
        r2 = client.post("/api/purchases", json=payload2)
        assert r2.status_code == 200, (
            f"Expected 200 for different date, got {r2.status_code}: {r2.text}"
        )


# ---------------------------------------------------------------------------
# E) normalize_purchase_description: backend vs gmail_import behavior
# ---------------------------------------------------------------------------

class TestNormalizeDescription:
    """
    Both backend (importers/visa_xlsx.py) and gmail_import.py expose
    normalize_purchase_description. They use identical regex logic.
    """

    def test_backend_strips_installment_marker(self):
        assert backend_norm(description="TIENDA C. 1/3 EJEMPLO") == "tienda ejemplo"

    def test_backend_strips_numeric_installment(self):
        assert backend_norm(description="TIENDA 2 de 3 EJEMPLO") == "tienda ejemplo"

    def test_backend_strips_leading_numeric_code(self):
        result = backend_norm(description="12345 MERPAGO*TIENDA")
        assert result == "merpago*tienda"

    def test_backend_strips_trailing_numeric_code(self):
        result = backend_norm(description="MERPAGO*TIENDA 304823")
        assert result == "merpago*tienda"

    def test_backend_collapses_whitespace(self):
        result = backend_norm(description="TIENDA   EJEMPLO")
        assert result == "tienda ejemplo"

    def test_gmail_norm_matches_backend_norm_for_clean_description(self):
        """
        The gmail_import normalize_purchase_description uses the same regex logic.
        For descriptions without codes, both produce identical output.
        """
        try:
            import sys
            import importlib
            # Add scripts dir to path temporarily
            import os
            scripts_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "scripts"
            )
            sys.path.insert(0, os.path.abspath(scripts_dir))
            from gmail_import import normalize_purchase_description as gmail_norm

            desc = "MERPAGO*SUPERMAMI 304823"
            assert gmail_norm(description=desc) == backend_norm(description=desc)
        finally:
            sys.path.pop(0)

    def test_case_insensitive_normalization(self):
        """normalize_purchase_description lowercases output — cross-source dedup works."""
        lower = backend_norm(description="merpago*tienda")
        upper = backend_norm(description="MERPAGO*TIENDA")
        assert lower == upper == "merpago*tienda"

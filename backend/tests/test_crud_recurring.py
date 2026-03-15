"""Tests para detect_recurring_expenses."""
from __future__ import annotations

from datetime import date

from app.crud import create_purchase, detect_recurring_expenses
from app.models import CurrencyCode
from app.schemas import PurchaseCreate


def _purchase(session, card_id, description, purchase_date, amount=5000):
    return create_purchase(
        session=session,
        payload=PurchaseCreate(
            card_id=card_id,
            purchase_date=purchase_date,
            description=description,
            currency=CurrencyCode.ARS,
            amount_original=amount,
        ),
    )


class TestDetectRecurringExpenses:
    def test_finds_recurring_above_threshold(self, session, two_person_scenario):
        s = two_person_scenario
        # Netflix aparece en 3 meses distintos
        _purchase(session, s["alice_card"].id, "NETFLIX", date(2025, 1, 15))
        _purchase(session, s["alice_card"].id, "NETFLIX", date(2025, 2, 15))
        _purchase(session, s["alice_card"].id, "NETFLIX", date(2025, 3, 15))

        results = detect_recurring_expenses(session=session, min_occurrences=3)
        assert len(results) == 1
        assert results[0]["description"] == "NETFLIX"
        assert results[0]["occurrences"] == 3

    def test_below_threshold_not_included(self, session, two_person_scenario):
        s = two_person_scenario
        # Solo 2 meses → no pasa el umbral de 3
        _purchase(session, s["alice_card"].id, "SPOTIFY", date(2025, 1, 15))
        _purchase(session, s["alice_card"].id, "SPOTIFY", date(2025, 2, 15))

        results = detect_recurring_expenses(session=session, min_occurrences=3)
        assert all(r["description"] != "SPOTIFY" for r in results)

    def test_custom_min_occurrences(self, session, two_person_scenario):
        s = two_person_scenario
        _purchase(session, s["alice_card"].id, "DISNEY PLUS", date(2025, 1, 15))
        _purchase(session, s["alice_card"].id, "DISNEY PLUS", date(2025, 2, 15))

        results = detect_recurring_expenses(session=session, min_occurrences=2)
        descriptions = [r["description"] for r in results]
        assert "DISNEY PLUS" in descriptions

    def test_same_month_counts_as_one(self, session, two_person_scenario):
        """Dos compras del mismo gasto en el mismo mes cuentan como 1 mes."""
        s = two_person_scenario
        _purchase(session, s["alice_card"].id, "YPF", date(2025, 1, 5))
        _purchase(session, s["alice_card"].id, "YPF", date(2025, 1, 20))  # mismo mes
        _purchase(session, s["alice_card"].id, "YPF", date(2025, 2, 15))
        _purchase(session, s["alice_card"].id, "YPF", date(2025, 3, 15))

        results = detect_recurring_expenses(session=session, min_occurrences=3)
        ypf = next((r for r in results if r["description"] == "YPF"), None)
        # Solo 3 meses distintos (enero, febrero, marzo), no 4
        assert ypf is not None
        assert ypf["occurrences"] == 3

    def test_sorted_by_occurrences_descending(self, session, two_person_scenario):
        s = two_person_scenario
        # Netflix: 4 meses, Spotify: 3 meses
        for m in range(1, 5):
            _purchase(session, s["alice_card"].id, "NETFLIX", date(2025, m, 15))
        for m in range(1, 4):
            _purchase(session, s["alice_card"].id, "SPOTIFY", date(2025, m, 15))

        results = detect_recurring_expenses(session=session, min_occurrences=3)
        assert results[0]["description"] == "NETFLIX"  # más recurrente primero
        assert results[0]["occurrences"] == 4
        assert results[1]["description"] == "SPOTIFY"
        assert results[1]["occurrences"] == 3

    def test_avg_amount_calculated(self, session, two_person_scenario):
        s = two_person_scenario
        _purchase(session, s["alice_card"].id, "OSDE", date(2025, 1, 15), amount=10000)
        _purchase(session, s["alice_card"].id, "OSDE", date(2025, 2, 15), amount=12000)
        _purchase(session, s["alice_card"].id, "OSDE", date(2025, 3, 15), amount=11000)

        results = detect_recurring_expenses(session=session, min_occurrences=3)
        osde = next(r for r in results if r["description"] == "OSDE")
        assert osde["avg_amount"] == 11000.0

    def test_normalized_description_groups_variants(self, session, two_person_scenario):
        """Compras con patrones de cuotas en descripción deben agruparse bajo la misma descripción normalizada."""
        s = two_person_scenario
        # "TIENDA NUBE C.1/12" y "TIENDA NUBE C.2/12" deberían normalizarse a "TIENDA NUBE"
        _purchase(session, s["alice_card"].id, "TIENDA NUBE C.1/12", date(2025, 1, 15))
        _purchase(session, s["alice_card"].id, "TIENDA NUBE C.1/12", date(2025, 2, 15))
        _purchase(session, s["alice_card"].id, "TIENDA NUBE C.1/12", date(2025, 3, 15))

        results = detect_recurring_expenses(session=session, min_occurrences=3)
        assert len(results) >= 1
        # La descripción normalizada no debe contener el patrón C.X/Y
        tienda = next((r for r in results if "TIENDA NUBE" in r["description"]), None)
        assert tienda is not None

    def test_empty_db_returns_empty(self, session):
        results = detect_recurring_expenses(session=session, min_occurrences=3)
        assert results == []

    def test_months_list_sorted_descending(self, session, two_person_scenario):
        s = two_person_scenario
        _purchase(session, s["alice_card"].id, "CABLEVISION", date(2025, 1, 15))
        _purchase(session, s["alice_card"].id, "CABLEVISION", date(2025, 3, 15))
        _purchase(session, s["alice_card"].id, "CABLEVISION", date(2025, 2, 15))

        results = detect_recurring_expenses(session=session, min_occurrences=3)
        cable = next(r for r in results if r["description"] == "CABLEVISION")
        # months debe estar ordenado descendentemente
        assert cable["months"] == ["2025-03", "2025-02", "2025-01"]
        assert cable["last_seen"] == "2025-03"

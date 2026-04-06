"""Tests for CardStatement CRUD and suggest-month logic."""
from datetime import date

import pytest

from app.schemas import CardStatementCreate, SuggestMonthResponse


class TestCardStatementSchemas:
    def test_valid_schema(self):
        cs = CardStatementCreate(
            card_id=1,
            year_month="2026-04",
            closing_date=date(2026, 4, 6),
            due_date=date(2026, 4, 28),
        )
        assert cs.card_id == 1
        assert cs.year_month == "2026-04"

    def test_invalid_year_month_format(self):
        with pytest.raises(Exception):
            CardStatementCreate(
                card_id=1,
                year_month="04-2026",  # wrong format
                closing_date=date(2026, 4, 6),
            )

    def test_due_date_optional(self):
        cs = CardStatementCreate(
            card_id=1,
            year_month="2026-04",
            closing_date=date(2026, 4, 6),
        )
        assert cs.due_date is None

    def test_suggest_month_response(self):
        r = SuggestMonthResponse(year_month="2026-04", closing_date=date(2026, 4, 6), fallback=False)
        assert r.year_month == "2026-04"
        assert r.fallback is False

    def test_suggest_month_fallback_has_no_closing_date(self):
        r = SuggestMonthResponse(year_month="2026-05", closing_date=None, fallback=True)
        assert r.closing_date is None

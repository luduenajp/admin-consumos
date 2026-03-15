"""Tests for backend/app/utils_dates.py."""
from datetime import date

from app.utils_dates import add_months, to_year_month


class TestToYearMonth:
    def test_basic(self):
        assert to_year_month(date(2025, 1, 15)) == "2025-01"

    def test_december(self):
        assert to_year_month(date(2025, 12, 31)) == "2025-12"

    def test_single_digit_month(self):
        assert to_year_month(date(2025, 3, 1)) == "2025-03"


class TestAddMonths:
    def test_positive(self):
        assert add_months("2025-01", 3) == "2025-04"

    def test_year_rollover(self):
        assert add_months("2025-11", 3) == "2026-02"

    def test_negative(self):
        assert add_months("2025-03", -2) == "2025-01"

    def test_negative_year_rollover(self):
        assert add_months("2025-01", -1) == "2024-12"

    def test_zero(self):
        assert add_months("2025-06", 0) == "2025-06"

    def test_large_positive(self):
        assert add_months("2025-01", 24) == "2027-01"

    def test_large_negative(self):
        assert add_months("2025-01", -12) == "2024-01"

    def test_december_to_january(self):
        assert add_months("2025-12", 1) == "2026-01"

    def test_january_to_december(self):
        assert add_months("2026-01", -1) == "2025-12"

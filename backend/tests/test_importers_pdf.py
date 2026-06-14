"""Tests for PDF importer internal parsing functions."""
from app.importers.visa_pdf import _detect_statement_year_month_from_text


class TestDetectStatementYearMonth:
    # _detect_statement_year_month_from_text returns a tuple
    # (year_month, closing_date_or_none); these tests assert on the year_month.

    def test_cierre_actual_with_date(self):
        text = "CIERRE ACTUAL: 22 Ene 25\nsome other stuff"
        ym, _close = _detect_statement_year_month_from_text(text)
        assert ym == "2025-01"

    def test_resumen_de_mes(self):
        # "Resumen de febrero" means the billing statement is FOR February,
        # so the closing month is January (the month before).
        text = "Resumen de febrero\nblah blah"
        ym, _close = _detect_statement_year_month_from_text(text)
        assert ym is not None
        # The function subtracts 1 month: febrero → enero (01)
        assert "-01" in ym

    def test_fecha_de_cierre_dd_mm_yyyy(self):
        text = "Fecha de cierre: 22/03/2025"
        ym, _close = _detect_statement_year_month_from_text(text)
        assert ym == "2025-03"

    def test_no_pattern_returns_none(self):
        text = "Random text without any date patterns"
        ym, _close = _detect_statement_year_month_from_text(text)
        assert ym is None

    def test_cierre_actual_x_de_mes(self):
        text = "Cierre actual 5 de marzo de 2025"
        ym, _close = _detect_statement_year_month_from_text(text)
        assert ym is not None
        assert "-03" in ym

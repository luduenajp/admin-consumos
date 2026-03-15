"""Tests for PDF importer internal parsing functions."""
from app.importers.visa_pdf import _detect_statement_year_month_from_text


class TestDetectStatementYearMonth:
    def test_cierre_actual_with_date(self):
        text = "CIERRE ACTUAL: 22 Ene 25\nsome other stuff"
        result = _detect_statement_year_month_from_text(text)
        assert result == "2025-01"

    def test_resumen_de_mes(self):
        # "Resumen de febrero" means the billing statement is FOR February,
        # so the closing month is January (the month before).
        text = "Resumen de febrero\nblah blah"
        result = _detect_statement_year_month_from_text(text)
        assert result is not None
        # The function subtracts 1 month: febrero → enero (01)
        assert "-01" in result

    def test_fecha_de_cierre_dd_mm_yyyy(self):
        text = "Fecha de cierre: 22/03/2025"
        result = _detect_statement_year_month_from_text(text)
        assert result == "2025-03"

    def test_no_pattern_returns_none(self):
        text = "Random text without any date patterns"
        result = _detect_statement_year_month_from_text(text)
        assert result is None

    def test_cierre_actual_x_de_mes(self):
        text = "Cierre actual 5 de marzo de 2025"
        result = _detect_statement_year_month_from_text(text)
        assert result is not None
        assert "-03" in result

"""Tests for Google Sheets CSV importer."""
from datetime import date

from app.importers.gsheets_importer import parse_gsheets_csv


class TestParseGsheetsCsv:
    def test_valid_csv(self):
        csv_content = """fecha,tipo,monto,moneda,descripcion
2026-02-19,compra,18464.36,ARS,*MERPAGO*TIENDA NUBE
2026-02-20,compra,5000.00,ARS,COTO DIGITAL
"""
        rows = parse_gsheets_csv(csv_content)
        assert len(rows) == 2
        assert rows[0].purchase_date == date(2026, 2, 19)
        assert rows[0].installment_amount == 18464.36
        assert rows[0].currency == "ARS"
        assert rows[0].installments_total == 1

    def test_zero_amount_excluded(self):
        csv_content = """fecha,tipo,monto,moneda,descripcion
2026-02-19,compra,0,ARS,Bad row
2026-02-20,compra,5000,ARS,Good row
"""
        rows = parse_gsheets_csv(csv_content)
        assert len(rows) == 1
        assert rows[0].description == "Good row"

    def test_negative_amount_excluded(self):
        csv_content = """fecha,tipo,monto,moneda,descripcion
2026-02-19,compra,-500,ARS,Refund
"""
        rows = parse_gsheets_csv(csv_content)
        assert len(rows) == 0

    def test_timestamp_in_date(self):
        """Dates with timestamps like '2026-02-19 00:00:00' should parse correctly."""
        csv_content = """fecha,tipo,monto,moneda,descripcion
2026-02-19 00:00:00,compra,1234.56,ARS,Timestamped
"""
        rows = parse_gsheets_csv(csv_content)
        assert len(rows) == 1
        assert rows[0].purchase_date == date(2026, 2, 19)

    def test_usd_currency(self):
        csv_content = """fecha,tipo,monto,moneda,descripcion
2026-02-19,compra,10.99,USD,Steam Purchase
"""
        rows = parse_gsheets_csv(csv_content)
        assert len(rows) == 1
        assert rows[0].currency == "USD"
        assert rows[0].installment_amount == 10.99

    def test_occurrence_tracking(self):
        """Duplicate rows on same day get different occurrence indices."""
        csv_content = """fecha,tipo,monto,moneda,descripcion
2026-02-19,compra,100,ARS,Same Purchase
2026-02-19,compra,100,ARS,Same Purchase
"""
        rows = parse_gsheets_csv(csv_content)
        assert len(rows) == 2
        assert rows[0].occurrence_index == 1
        assert rows[1].occurrence_index == 2

    def test_empty_csv(self):
        csv_content = """fecha,tipo,monto,moneda,descripcion
"""
        rows = parse_gsheets_csv(csv_content)
        assert len(rows) == 0

    def test_invalid_date_skipped(self):
        csv_content = """fecha,tipo,monto,moneda,descripcion
not-a-date,compra,100,ARS,Bad Date
2026-02-20,compra,200,ARS,Good Row
"""
        rows = parse_gsheets_csv(csv_content)
        assert len(rows) == 1
        assert rows[0].description == "Good Row"

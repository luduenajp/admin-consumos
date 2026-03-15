"""Tests for pure helper functions in importers (no DB needed)."""
from datetime import date

from app.importers.visa_xlsx import (
    ParsedPurchaseRow,
    _is_excluded_description,
    _parse_installments,
    _parse_money,
    compute_row_fingerprint,
    normalize_purchase_description,
)


class TestParseMoney:
    def test_ars_with_separators(self):
        assert _parse_money("$1.443.685,70") == 1443685.70

    def test_usd(self):
        assert _parse_money("U$S24,51") == 24.51

    def test_negative(self):
        result = _parse_money("$-7.778,81")
        assert result is not None
        assert abs(result - (-7778.81)) < 0.01

    def test_none(self):
        assert _parse_money(None) is None

    def test_empty_string(self):
        assert _parse_money("") is None

    def test_nan(self):
        assert _parse_money("nan") is None

    def test_plain_number(self):
        result = _parse_money("1234,56")
        assert result is not None
        assert abs(result - 1234.56) < 0.01

    def test_usd_negative(self):
        result = _parse_money("U$S-17,87")
        assert result is not None
        assert abs(result - (-17.87)) < 0.01


class TestParseInstallments:
    def test_basic(self):
        assert _parse_installments("3 de 12") == (3, 12)

    def test_banco_nacion_format(self):
        assert _parse_installments("C.17/24") == (17, 24)

    def test_none(self):
        assert _parse_installments(None) == (1, 1)

    def test_empty(self):
        assert _parse_installments("") == (1, 1)

    def test_nan(self):
        assert _parse_installments("nan") == (1, 1)

    def test_single_installment(self):
        assert _parse_installments("1 de 1") == (1, 1)

    def test_in_middle_of_text(self):
        """MercadoPago: '3 de 3' embedded in a larger string."""
        assert _parse_installments("some text 3 de 3 more") == (3, 3)

    def test_current_clamped_to_total(self):
        """Current > total should be clamped."""
        assert _parse_installments("15 de 12") == (12, 12)


class TestIsExcludedDescription:
    def test_payment_excluded(self):
        assert _is_excluded_description("Su pago en efectivo") is True

    def test_tax_excluded(self):
        assert _is_excluded_description("DB.RG 5617 Perc.Ganan") is True

    def test_iibb_excluded(self):
        assert _is_excluded_description("IIBB PERCEP BS.AS.") is True

    def test_impuesto_sellos_excluded(self):
        assert _is_excluded_description("Impuesto de sellos") is True

    def test_promo_excluded(self):
        assert _is_excluded_description("Promo dto 20%") is True

    def test_resumen_excluded(self):
        assert _is_excluded_description("Resumen de enero") is True

    def test_bonificacion_excluded(self):
        assert _is_excluded_description("Bonif. beneficio") is True

    def test_total_excluded(self):
        assert _is_excluded_description("Total del resumen") is True

    def test_normal_purchase_not_excluded(self):
        assert _is_excluded_description("MERPAGO*TIENDA NUBE") is False

    def test_yp_not_excluded(self):
        assert _is_excluded_description("YPF - Estacion 1234") is False


class TestNormalizePurchaseDescription:
    def test_removes_installment_pattern(self):
        result = normalize_purchase_description(description="TIENDA NUBE C.3/12 12345")
        assert "C.3/12" not in result

    def test_removes_leading_code(self):
        result = normalize_purchase_description(description="12345 MERPAGO*TIENDA")
        assert result == "MERPAGO*TIENDA"

    def test_removes_trailing_code(self):
        result = normalize_purchase_description(description="MERPAGO*TIENDA 12345")
        assert result == "MERPAGO*TIENDA"

    def test_collapses_spaces(self):
        result = normalize_purchase_description(description="MERPAGO   TIENDA   NUBE")
        assert result == "MERPAGO TIENDA NUBE"

    def test_removes_de_pattern(self):
        result = normalize_purchase_description(description="TIENDA 3 de 12 compra")
        assert "3 de 12" not in result


class TestComputeRowFingerprint:
    def test_same_input_same_hash(self):
        row = ParsedPurchaseRow(
            purchase_date=date(2025, 1, 15),
            description="Test",
            currency="ARS",
            installment_index=1,
            installments_total=1,
            installment_amount=1000.0,
            statement_year_month="2025-01",
        )
        h1 = compute_row_fingerprint(provider="visa_xlsx", card_id=1, row=row)
        h2 = compute_row_fingerprint(provider="visa_xlsx", card_id=1, row=row)
        assert h1 == h2

    def test_different_input_different_hash(self):
        row1 = ParsedPurchaseRow(
            purchase_date=date(2025, 1, 15),
            description="Test A",
            currency="ARS",
            installment_index=1,
            installments_total=1,
            installment_amount=1000.0,
            statement_year_month="2025-01",
        )
        row2 = ParsedPurchaseRow(
            purchase_date=date(2025, 1, 15),
            description="Test B",
            currency="ARS",
            installment_index=1,
            installments_total=1,
            installment_amount=1000.0,
            statement_year_month="2025-01",
        )
        h1 = compute_row_fingerprint(provider="visa_xlsx", card_id=1, row=row1)
        h2 = compute_row_fingerprint(provider="visa_xlsx", card_id=1, row=row2)
        assert h1 != h2

    def test_different_card_different_hash(self):
        row = ParsedPurchaseRow(
            purchase_date=date(2025, 1, 15),
            description="Test",
            currency="ARS",
            installment_index=1,
            installments_total=1,
            installment_amount=1000.0,
            statement_year_month="2025-01",
        )
        h1 = compute_row_fingerprint(provider="visa_xlsx", card_id=1, row=row)
        h2 = compute_row_fingerprint(provider="visa_xlsx", card_id=2, row=row)
        assert h1 != h2

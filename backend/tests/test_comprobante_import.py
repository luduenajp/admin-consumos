"""Tests for POST /import/comprobante endpoint (mocked Claude API + local fallback)."""
from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.crud import create_beneficiary
from app.importers.comprobante_local import LocalExtraction, _parse_text
from app.schemas import BeneficiaryCreate


class TestComprobanteEndpoint:
    def _make_claude_response(self, json_text: str):
        mock_content = MagicMock()
        mock_content.text = json_text
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        return mock_response

    def test_returns_422_for_invalid_file_type(self, client):
        data = {"file": ("test.txt", BytesIO(b"hello"), "text/plain")}
        resp = client.post("/api/import/comprobante", files=data)
        assert resp.status_code == 422

    def test_no_api_key_falls_back_to_local_returns_200(self, client):
        # Without API key, local extraction is tried (returns empty fields on fake image — still 200)
        with patch("app.import_api.get_anthropic_api_key", return_value=None), \
             patch("app.import_api.extract_from_image", return_value=LocalExtraction()):
            data = {"file": ("test.png", BytesIO(b"fake_image"), "image/png")}
            resp = client.post("/api/import/comprobante", files=data)
        assert resp.status_code == 200
        body = resp.json()
        assert body["extraction_source"] == "empty"
        assert body["amount"] is None

    def test_successful_extraction_no_match(self, client):
        claude_json = '{"monto": 4500.0, "fecha": "2026-06-07", "moneda": "ARS", "destinatario": {"nombre": "LOPEZ MARIA", "cbu": null, "cuit": null, "alias": null}}'
        mock_resp = self._make_claude_response(claude_json)

        with patch("app.import_api.get_anthropic_api_key", return_value="sk-test"), \
             patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            data = {"file": ("test.png", BytesIO(b"fake_image"), "image/png")}
            resp = client.post("/api/import/comprobante", files=data)

        assert resp.status_code == 200
        body = resp.json()
        assert body["amount"] == 4500.0
        assert body["date"] == "2026-06-07"
        assert body["currency"] == "ARS"
        assert body["description"] == "LOPEZ MARIA"
        assert body["matched_beneficiary"] is None
        assert body["raw_extracted"]["nombre"] == "LOPEZ MARIA"
        assert body["extraction_source"] == "claude"

    def test_successful_extraction_with_match(self, client, session):
        create_beneficiary(
            session=session,
            payload=BeneficiaryCreate(name="Lopez Maria", cbu="1234567890123456789012"),
        )
        claude_json = '{"monto": 4500.0, "fecha": "2026-06-07", "moneda": "ARS", "destinatario": {"nombre": "LOPEZ MARIA", "cbu": "1234567890123456789012", "cuit": null, "alias": null}}'
        mock_resp = self._make_claude_response(claude_json)

        with patch("app.import_api.get_anthropic_api_key", return_value="sk-test"), \
             patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            data = {"file": ("test.png", BytesIO(b"fake_image"), "image/png")}
            resp = client.post("/api/import/comprobante", files=data)

        assert resp.status_code == 200
        body = resp.json()
        assert body["matched_beneficiary"] is not None
        assert body["matched_beneficiary"]["confidence"] == "exact"
        assert body["matched_beneficiary"]["name"] == "Lopez Maria"

    def test_claude_error_falls_back_to_local(self, client):
        # Claude raises an exception → local extraction is tried → 200 with empty fields on fake image
        with patch("app.import_api.get_anthropic_api_key", return_value="sk-test"), \
             patch("anthropic.Anthropic") as MockClient, \
             patch("app.import_api.extract_from_image", return_value=LocalExtraction()):
            MockClient.return_value.messages.create.side_effect = Exception("Connection timeout")
            data = {"file": ("test.png", BytesIO(b"fake_image"), "image/png")}
            resp = client.post("/api/import/comprobante", files=data)

        assert resp.status_code == 200
        body = resp.json()
        assert body["extraction_source"] == "empty"

    def test_claude_invalid_json_falls_back_to_local(self, client):
        mock_resp = self._make_claude_response("Este no es JSON válido")

        with patch("app.import_api.get_anthropic_api_key", return_value="sk-test"), \
             patch("anthropic.Anthropic") as MockClient, \
             patch("app.import_api.extract_from_image", return_value=LocalExtraction()):
            MockClient.return_value.messages.create.return_value = mock_resp
            data = {"file": ("test.png", BytesIO(b"fake_image"), "image/png")}
            resp = client.post("/api/import/comprobante", files=data)

        assert resp.status_code == 200
        body = resp.json()
        assert body["extraction_source"] == "empty"

    def test_pdf_accepted_via_claude(self, client):
        claude_json = '{"monto": 1000.0, "fecha": "2026-06-01", "moneda": "ARS", "destinatario": {"nombre": null, "cbu": null, "cuit": null, "alias": null}}'
        mock_resp = self._make_claude_response(claude_json)

        with patch("app.import_api.get_anthropic_api_key", return_value="sk-test"), \
             patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            data = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
            resp = client.post("/api/import/comprobante", files=data)

        assert resp.status_code == 200
        assert resp.json()["extraction_source"] == "claude"

    def test_local_fallback_extracts_from_pdf_text(self, client):
        # Claude unavailable → local pdfplumber extraction returns data
        local_result = LocalExtraction(monto=15000.0, fecha="2026-06-15", nombre="Juan Perez", cbu="0720490088000012345678")

        with patch("app.import_api.get_anthropic_api_key", return_value=None), \
             patch("app.import_api.extract_from_pdf", return_value=local_result):
            data = {"file": ("comp.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
            resp = client.post("/api/import/comprobante", files=data)

        assert resp.status_code == 200
        body = resp.json()
        assert body["amount"] == 15000.0
        assert body["date"] == "2026-06-15"
        assert body["raw_extracted"]["nombre"] == "Juan Perez"
        assert body["raw_extracted"]["cbu"] == "0720490088000012345678"
        assert body["extraction_source"] == "local"


class TestLocalExtraction:
    def test_parses_santander_style_amount(self):
        text = "Importe: $ 25.000,00\nFecha: 15/06/2026\nDestinatario: JUAN PABLO LOPEZ"
        result = _parse_text(text)
        assert result.monto == 25000.0
        assert result.fecha == "2026-06-15"
        assert result.nombre == "Juan Pablo Lopez"

    def test_parses_cbu(self):
        text = "CBU: 0720490088000012345678\nImporte: $ 1.000,00"
        result = _parse_text(text)
        assert result.cbu == "0720490088000012345678"
        assert result.monto == 1000.0

    def test_parses_cuit(self):
        text = "CUIT: 20-33957678-6\nImporte: $ 500,00"
        result = _parse_text(text)
        assert result.cuit == "20-33957678-6"

    def test_parses_alias(self):
        text = "Alias: juan.lopez.mp\nImporte: $ 200,00"
        result = _parse_text(text)
        assert result.alias == "juan.lopez.mp"

    def test_detects_usd(self):
        text = "Importe: $ 100,00 USD"
        result = _parse_text(text)
        assert result.moneda == "USD"

    def test_empty_text_returns_empty(self):
        result = _parse_text("")
        assert result.monto is None
        assert result.fecha is None
        assert result.nombre is None

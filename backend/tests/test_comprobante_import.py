"""Tests for POST /import/comprobante endpoint (mocked Claude API)."""
from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.crud import create_beneficiary
from app.schemas import BeneficiaryCreate


class TestComprobanteEndpoint:
    def _make_claude_response(self, json_text: str):
        """Build a mock Anthropic API response."""
        mock_content = MagicMock()
        mock_content.text = json_text
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        return mock_response

    def test_returns_422_for_invalid_file_type(self, client):
        data = {"file": ("test.txt", BytesIO(b"hello"), "text/plain")}
        resp = client.post("/api/import/comprobante", files=data)
        assert resp.status_code == 422

    def test_returns_503_when_api_key_missing(self, client, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        # Patch get_anthropic_api_key to return None
        with patch("app.import_api.get_anthropic_api_key", return_value=None):
            data = {"file": ("test.png", BytesIO(b"fake_image"), "image/png")}
            resp = client.post("/api/import/comprobante", files=data)
        assert resp.status_code == 503

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

    def test_successful_extraction_with_match(self, client, session):
        # Pre-create a beneficiary with CBU
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

    def test_returns_502_on_invalid_json(self, client):
        mock_resp = self._make_claude_response("Este no es JSON válido")

        with patch("app.import_api.get_anthropic_api_key", return_value="sk-test"), \
             patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            data = {"file": ("test.png", BytesIO(b"fake_image"), "image/png")}
            resp = client.post("/api/import/comprobante", files=data)

        assert resp.status_code == 502

    def test_returns_502_on_api_error(self, client):
        with patch("app.import_api.get_anthropic_api_key", return_value="sk-test"), \
             patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = Exception("Connection timeout")
            data = {"file": ("test.png", BytesIO(b"fake_image"), "image/png")}
            resp = client.post("/api/import/comprobante", files=data)

        assert resp.status_code == 502

    def test_pdf_file_accepted(self, client):
        claude_json = '{"monto": 1000.0, "fecha": "2026-06-01", "moneda": "ARS", "destinatario": {"nombre": null, "cbu": null, "cuit": null, "alias": null}}'
        mock_resp = self._make_claude_response(claude_json)

        with patch("app.import_api.get_anthropic_api_key", return_value="sk-test"), \
             patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            data = {"file": ("test.pdf", BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
            resp = client.post("/api/import/comprobante", files=data)

        assert resp.status_code == 200

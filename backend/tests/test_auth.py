"""Tests for Basic Auth middleware."""
from __future__ import annotations

import base64
import pytest
from starlette.testclient import TestClient

from app.main import create_app


def _auth_header(user: str, password: str) -> dict:
    credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


@pytest.fixture()
def auth_client(engine, monkeypatch):
    import app.db as db_module
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setenv("APP_USERNAME", "testuser")
    monkeypatch.setenv("APP_PASSWORD", "testpass")
    application = create_app()
    with TestClient(application, raise_server_exceptions=True) as c:
        yield c


def test_health_no_auth(auth_client):
    """Health endpoint is exempt from auth."""
    r = auth_client.get("/health")
    assert r.status_code == 200


def test_api_no_auth_returns_401(auth_client):
    r = auth_client.get("/api/people")
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate") == 'Basic realm="Admin Consumos"'


def test_api_wrong_password_returns_401(auth_client):
    r = auth_client.get("/api/people", headers=_auth_header("testuser", "wrong"))
    assert r.status_code == 401


def test_api_correct_credentials_pass(auth_client):
    r = auth_client.get("/api/people", headers=_auth_header("testuser", "testpass"))
    assert r.status_code == 200


def test_api_malformed_auth_returns_401(auth_client):
    """Non-Basic schemes should be rejected."""
    r = auth_client.get("/api/people", headers={"Authorization": "Bearer sometoken"})
    assert r.status_code == 401


def test_no_auth_config_allows_all(client):
    """When APP_USERNAME is not set, middleware does not enforce auth."""
    r = client.get("/api/people")
    assert r.status_code == 200

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


def test_pwa_assets_no_auth(auth_client):
    """Manifest, service worker e iconos están exentos de auth (Chrome los
    fetchea sin credenciales; un 401 hace la PWA no instalable)."""
    for path in ("/manifest.webmanifest", "/sw.js", "/icons/icon-192.png"):
        r = auth_client.get(path)
        assert r.status_code != 401, path


def test_spa_deep_link_serves_index(auth_client):
    """Rutas client-side como /nueva-transferencia sirven index.html (SPA fallback)."""
    from pathlib import Path
    dist = Path(__file__).parent.parent.parent / "frontend" / "dist" / "index.html"
    if not dist.exists():
        pytest.skip("frontend/dist no está buildeado")
    r = auth_client.get("/nueva-transferencia", headers=_auth_header("testuser", "testpass"))
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    # los 404 de API no se enmascaran con index.html
    r = auth_client.get("/api/nope", headers=_auth_header("testuser", "testpass"))
    assert r.status_code == 404


def test_share_target_fallback_no_auth(auth_client):
    """POST /share-target sin credenciales redirige al formulario vacío."""
    r = auth_client.post("/share-target", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/nueva-transferencia"


def test_share_target_fallback_with_file_stashes_and_redirects_with_token(auth_client):
    """Si el SW no interceptó pero llegó un archivo, el backend lo guarda y
    agrega ?token= para que el frontend lo recupere (UC-054)."""
    r = auth_client.post(
        "/share-target",
        files={"file": ("comprobante.png", b"fake-image-bytes", "image/png")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    location = r.headers["location"]
    assert location.startswith("/nueva-transferencia?shared=1&token=")
    token = location.split("token=", 1)[1]

    r2 = auth_client.get(
        f"/api/share-target/pending/{token}", headers=_auth_header("testuser", "testpass")
    )
    assert r2.status_code == 200
    assert r2.content == b"fake-image-bytes"
    assert r2.headers["content-type"] == "image/png"

    # one-shot: consumido, la segunda vez es 404
    r3 = auth_client.get(
        f"/api/share-target/pending/{token}", headers=_auth_header("testuser", "testpass")
    )
    assert r3.status_code == 404


def test_share_target_recovers_malformed_samsung_internet_body(auth_client):
    """Samsung Internet sends a valid multipart body with a stray NUL byte
    before the closing boundary, which breaks the standard parser. The
    backend's lenient fallback (app/multipart_recovery.py) should still
    extract the file (UC-054)."""
    boundary = "----MultipartBoundary--abc123----"
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00fakeIEND\xaeB\x60\x82"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="comprobante.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode("latin-1") + png_bytes + b"\r\n\x00" + f"--{boundary}--\r\n".encode("latin-1")

    r = auth_client.post(
        "/share-target",
        content=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    location = r.headers["location"]
    assert location.startswith("/nueva-transferencia?shared=1&token=")
    token = location.split("token=", 1)[1]

    r2 = auth_client.get(
        f"/api/share-target/pending/{token}", headers=_auth_header("testuser", "testpass")
    )
    assert r2.status_code == 200
    assert r2.content == png_bytes


def test_share_target_pending_unknown_token_returns_404(auth_client):
    r = auth_client.get(
        "/api/share-target/pending/does-not-exist", headers=_auth_header("testuser", "testpass")
    )
    assert r.status_code == 404


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

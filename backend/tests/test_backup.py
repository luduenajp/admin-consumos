"""Tests for GET /api/backup/db endpoint."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import create_app
import app.db as db_module


@pytest.fixture()
def backup_client(engine, monkeypatch, tmp_path):
    """TestClient with BACKUP_TOKEN set and DB pointing to a real SQLite file."""
    # Point the engine at a real file so sqlite3.connect().backup() works
    import sqlite3
    from sqlmodel import SQLModel, create_engine
    from sqlalchemy import event as sa_event

    db_file = tmp_path / "app.db"
    file_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    @sa_event.listens_for(file_engine, "connect")
    def _pragma(conn, _):
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(file_engine)

    monkeypatch.setattr(db_module, "engine", file_engine)
    monkeypatch.setenv("BACKUP_TOKEN", "supersecret")
    monkeypatch.setenv("DB_PATH", str(db_file))

    application = create_app()
    with TestClient(application, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture()
def no_token_client(engine, monkeypatch):
    """TestClient WITHOUT BACKUP_TOKEN set."""
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.delenv("BACKUP_TOKEN", raising=False)

    application = create_app()
    with TestClient(application, raise_server_exceptions=True) as c:
        yield c


def test_backup_503_when_token_not_configured(no_token_client):
    """Returns 503 when BACKUP_TOKEN env var is not set."""
    r = no_token_client.get("/api/backup/db", headers={"Authorization": "Bearer anything"})
    assert r.status_code == 503


def test_backup_401_wrong_token(backup_client):
    """Returns 401 when the provided token doesn't match."""
    r = backup_client.get("/api/backup/db", headers={"Authorization": "Bearer wrongtoken"})
    assert r.status_code == 401


def test_backup_401_missing_auth_header(backup_client):
    """Returns 401 when no Authorization header is provided."""
    r = backup_client.get("/api/backup/db")
    assert r.status_code == 401


def test_backup_401_non_bearer_scheme(backup_client):
    """Returns 401 when Authorization scheme is not Bearer."""
    r = backup_client.get("/api/backup/db", headers={"Authorization": "Basic supersecret"})
    assert r.status_code == 401


def test_backup_200_valid_token(backup_client):
    """Returns 200 with SQLite file when token is correct."""
    r = backup_client.get("/api/backup/db", headers={"Authorization": "Bearer supersecret"})
    assert r.status_code == 200

    # Check Content-Disposition header has attachment filename
    content_disposition = r.headers.get("content-disposition", "")
    assert "attachment" in content_disposition
    assert "app_" in content_disposition
    assert ".db" in content_disposition

    # Check Content-Length header is present and matches content
    content_length = r.headers.get("content-length")
    assert content_length is not None
    assert int(content_length) == len(r.content)

    # Check SQLite magic bytes at the start of the file
    content = r.content
    assert len(content) > 0
    assert content[:16] == b"SQLite format 3\x00"

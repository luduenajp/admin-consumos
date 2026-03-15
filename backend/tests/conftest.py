"""Test fixtures for the admin-consumos backend."""
from __future__ import annotations

from datetime import date
from typing import Iterator

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

import app.db as db_module
from app.main import create_app
from app.models import (
    Card,
    CurrencyCode,
    FxRate,
    Income,
    Person,
    ShareType,
)
from app.schemas import (
    CardCreate,
    FxRateUpsert,
    IncomeCreate,
    PersonCreate,
    PurchaseCreate,
    PurchasePayerCreate,
)
from app.crud import create_card, create_person, create_purchase, upsert_fx_rate, create_income


@pytest.fixture(scope="session")
def _engine(tmp_path_factory):
    """Session-scoped SQLite engine in a temp directory."""
    db_path = tmp_path_factory.mktemp("data") / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def engine(tmp_path):
    """Function-scoped engine — each test gets its own fresh DB."""
    db_path = tmp_path / "test.db"
    eng = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(eng, "connect")
    def _set_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine, monkeypatch):
    """Function-scoped session that monkeypatches app.db.engine."""
    monkeypatch.setattr(db_module, "engine", engine)
    with Session(engine) as sess:
        yield sess


@pytest.fixture()
def client(engine, monkeypatch):
    """FastAPI TestClient with monkeypatched engine."""
    monkeypatch.setattr(db_module, "engine", engine)
    from starlette.testclient import TestClient

    application = create_app()
    with TestClient(application, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture()
def two_persons(session):
    """Create Alice and Bob, return (alice, bob)."""
    alice = create_person(session=session, payload=PersonCreate(name="Alice"))
    bob = create_person(session=session, payload=PersonCreate(name="Bob"))
    return alice, bob


@pytest.fixture()
def two_person_scenario(session, two_persons):
    """
    Alice & Bob with cards and an FX rate.
    Returns dict with alice, bob, alice_card, bob_card.
    """
    alice, bob = two_persons
    alice_card = create_card(
        session=session,
        payload=CardCreate(name="Visa Alice", provider="visa", owner_person_id=alice.id),
    )
    bob_card = create_card(
        session=session,
        payload=CardCreate(name="Visa Bob", provider="visa", owner_person_id=bob.id),
    )
    upsert_fx_rate(
        session=session,
        payload=FxRateUpsert(year_month="2025-01", currency=CurrencyCode.USD, rate_to_ars=1200.0),
    )
    return {
        "alice": alice,
        "bob": bob,
        "alice_card": alice_card,
        "bob_card": bob_card,
    }

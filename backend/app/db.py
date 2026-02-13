from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import event, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_sqlite_url

engine = create_engine(
    get_sqlite_url(),
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_add_columns()


def _migrate_add_columns() -> None:
    """Add columns to existing tables (idempotent)."""
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(purchase)")).fetchall()
        columns = {row[1] for row in rows}
        if "debtor_id" not in columns:
            conn.execute(text("ALTER TABLE purchase ADD COLUMN debtor_id INTEGER REFERENCES debtor(id)"))
        if "debt_settled" not in columns:
            conn.execute(text("ALTER TABLE purchase ADD COLUMN debt_settled BOOLEAN DEFAULT 0 NOT NULL"))
        conn.commit()


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session

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
    _migrate_dedupe_installments()
    _migrate_lowercase_descriptions()


def _migrate_add_columns() -> None:
    """Add columns to existing tables (idempotent)."""
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(purchase)")).fetchall()
        columns = {row[1] for row in rows}
        if "debtor_id" not in columns:
            conn.execute(text("ALTER TABLE purchase ADD COLUMN debtor_id INTEGER REFERENCES debtor(id)"))
        if "debt_settled" not in columns:
            conn.execute(text("ALTER TABLE purchase ADD COLUMN debt_settled BOOLEAN DEFAULT 0 NOT NULL"))
        if "beneficiary_person_id" not in columns:
            conn.execute(text("ALTER TABLE purchase ADD COLUMN beneficiary_person_id INTEGER REFERENCES person(id)"))
        if "import_batch_id" not in columns:
            conn.execute(text("ALTER TABLE purchase ADD COLUMN import_batch_id INTEGER REFERENCES importbatch(id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_purchase_import_batch_id ON purchase(import_batch_id)"))

        # Create beneficiary table if it doesn't exist
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS beneficiary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cbu TEXT,
                cuit TEXT,
                alias TEXT
            )
        """))
        conn.commit()


def _add_months_inline(year_month: str, months: int) -> str:
    """Add N months to a YYYY-MM string. Inline to avoid circular imports."""
    year, month = int(year_month[:4]), int(year_month[5:7])
    total = (year * 12 + (month - 1)) + months
    new_year, new_month = divmod(total, 12)
    return f"{new_year:04d}-{new_month + 1:02d}"


def _migrate_dedupe_installments() -> None:
    """Remove duplicate (purchase_id, installment_index) rows and add UNIQUE index (idempotent)."""
    with engine.connect() as conn:
        # Find all duplicate groups
        dupes = conn.execute(text("""
            SELECT purchase_id, installment_index, COUNT(*) as cnt
            FROM installmentschedule
            GROUP BY purchase_id, installment_index
            HAVING COUNT(*) > 1
        """)).fetchall()

        for purchase_id, installment_index, _ in dupes:
            # Get all duplicate rows for this group
            rows = conn.execute(text("""
                SELECT id, year_month
                FROM installmentschedule
                WHERE purchase_id = :pid AND installment_index = :idx
                ORDER BY year_month
            """), {"pid": purchase_id, "idx": installment_index}).fetchall()

            # Determine which row to keep
            keep_id: int | None = None

            # Try to find the expected year_month from first_installment_month
            purchase_row = conn.execute(text("""
                SELECT first_installment_month FROM purchase WHERE id = :pid
            """), {"pid": purchase_id}).fetchone()

            if purchase_row and purchase_row[0]:
                expected_ym = _add_months_inline(purchase_row[0], installment_index - 1)
                for row_id, row_ym in rows:
                    if row_ym == expected_ym:
                        keep_id = row_id
                        break

            # Fall back to MIN(year_month) — first in sorted order
            if keep_id is None:
                keep_id = rows[0][0]

            # Delete all other rows in the group
            ids_to_delete = [row_id for row_id, _ in rows if row_id != keep_id]
            for del_id in ids_to_delete:
                conn.execute(text("DELETE FROM installmentschedule WHERE id = :id"), {"id": del_id})

        # Create UNIQUE INDEX as DB-level guard (idempotent)
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_installment_purchase_index
            ON installmentschedule(purchase_id, installment_index)
        """))
        conn.commit()


def _migrate_lowercase_descriptions() -> None:
    """Lowercase all purchase descriptions for case-insensitive deduplication (idempotent)."""
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM purchase WHERE description != lower(description)")
        ).scalar()
        if count:
            conn.execute(text("UPDATE purchase SET description = lower(description)"))
            conn.commit()


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session

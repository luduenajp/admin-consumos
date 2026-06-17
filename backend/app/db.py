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
    _migrate_uppercase_categories()
    _migrate_reorganize_categories()


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


def _migrate_uppercase_categories() -> None:
    """Convert all category names to uppercase using Python (handles accented chars). Idempotent."""
    with engine.connect() as conn:
        cats = conn.execute(text("SELECT id, name FROM category")).fetchall()
        for cat_id, name in cats:
            upper = name.upper()
            if upper != name:
                conn.execute(text("UPDATE category SET name = :name WHERE id = :id"), {"name": upper, "id": cat_id})

        purchases = conn.execute(text("SELECT id, category FROM purchase WHERE category IS NOT NULL")).fetchall()
        for p_id, cat in purchases:
            upper = cat.upper()
            if upper != cat:
                conn.execute(text("UPDATE purchase SET category = :cat WHERE id = :id"), {"cat": upper, "id": p_id})

        conn.commit()


def _migrate_reorganize_categories() -> None:
    """Reorganize categories: split SERVICIOS, remove VARIOS, add new ones. Idempotent."""
    NEW_CATEGORIES = [
        ("FIAMBRERÍA", "#8B4513"),
        ("KIOSCO", "#DAA520"),
        ("GASTRONOMÍA", "#E07B39"),
        ("SERVICIOS PÚBLICOS", "#4A90D9"),
        ("TELEFONÍA", "#7B68EE"),
        ("INTERNET", "#20B2AA"),
        ("SUSCRIPCIONES", "#9370DB"),
        ("INDUMENTARIA", "#DB7093"),
        ("VIAJES", "#32CD32"),
        ("GASTOS PERSONALES", "#A0A0A0"),
        ("NO DEFINIDO", "#808080"),
    ]
    RENAME = {"RESTAURANTES": "GASTRONOMÍA"}
    RESET_AND_DELETE = {"VARIOS", "SERVICIOS", "ADELANTO DE SUELDO"}

    with engine.connect() as conn:
        existing = {row[0] for row in conn.execute(text("SELECT name FROM category")).fetchall()}

        # Skip entirely if already reorganized (all new cats exist and old ones are gone)
        already_done = all(name in existing for name, _ in NEW_CATEGORIES) and not existing.intersection(RESET_AND_DELETE | set(RENAME.keys()))
        if already_done:
            return

        for name, color in NEW_CATEGORIES:
            if name not in existing:
                conn.execute(text("INSERT INTO category (name, color) VALUES (:name, :color)"), {"name": name, "color": color})
        conn.commit()

        # Rename RESTAURANTES → GASTRONOMÍA
        for old, new in RENAME.items():
            if old in existing:
                conn.execute(text("UPDATE purchase SET category = :new WHERE category = :old"), {"new": new, "old": old})
                conn.execute(text("DELETE FROM category WHERE name = :name"), {"name": old})
        conn.commit()

        # Reset obsolete categories to NULL so auto_categorize can re-assign
        for cat in RESET_AND_DELETE:
            if cat in existing:
                conn.execute(text("UPDATE purchase SET category = NULL WHERE category = :cat"), {"cat": cat})
                conn.execute(text("DELETE FROM category WHERE name = :name"), {"name": cat})
        conn.commit()

    # Run auto_categorize to re-assign purchases that were reset to NULL
    from app.crud import auto_categorize_purchases
    with Session(engine) as session:
        auto_categorize_purchases(session=session)
        session.commit()


@contextmanager
def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session

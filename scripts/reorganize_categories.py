"""
One-time script to reorganize categories:
- Creates new categories (FIAMBRERÍA, KIOSCO, GASTRONOMÍA, SERVICIOS PÚBLICOS, TELEFONÍA, INTERNET, SUSCRIPCIONES, INDUMENTARIA, VIAJES)
- Renames RESTAURANTES → GASTRONOMÍA
- Resets purchases in VARIOS / SERVICIOS / ADELANTO DE SUELDO to NULL so auto_categorize re-assigns them
- Deletes obsolete categories
- Runs auto_categorize with updated keyword rules
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.db import init_db, engine
from app.crud import auto_categorize_purchases
from sqlalchemy import text
from sqlmodel import Session

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
]

RENAME = {
    "RESTAURANTES": "GASTRONOMÍA",
}

# Purchases in these categories get reset to NULL for re-categorization
RESET_CATEGORIES = {"VARIOS", "SERVICIOS", "ADELANTO DE SUELDO", "RESTAURANTES"}

# These categories are deleted after reset (RESTAURANTES is renamed, not deleted)
DELETE_CATEGORIES = {"VARIOS", "SERVICIOS", "ADELANTO DE SUELDO"}


def run():
    init_db()

    with engine.connect() as conn:
        existing = {row[0] for row in conn.execute(text("SELECT name FROM category")).fetchall()}

        # 1. Create new categories (skip if already exist)
        for name, color in NEW_CATEGORIES:
            if name not in existing:
                conn.execute(text("INSERT INTO category (name, color) VALUES (:name, :color)"), {"name": name, "color": color})
                print(f"  Creada: {name}")
            else:
                print(f"  Ya existe: {name}")

        conn.commit()

        # 2. Rename RESTAURANTES → GASTRONOMÍA (only if GASTRONOMÍA doesn't already have purchases)
        for old, new in RENAME.items():
            if old in existing:
                gastro_purchases = conn.execute(
                    text("SELECT COUNT(*) FROM purchase WHERE category = :cat"), {"cat": new}
                ).scalar()
                old_purchases = conn.execute(
                    text("SELECT COUNT(*) FROM purchase WHERE category = :cat"), {"cat": old}
                ).scalar()
                if old_purchases > 0:
                    conn.execute(
                        text("UPDATE purchase SET category = :new WHERE category = :old"),
                        {"new": new, "old": old}
                    )
                    print(f"  Renombradas {old_purchases} compras: {old} → {new}")
                conn.execute(text("DELETE FROM category WHERE name = :name"), {"name": old})
                print(f"  Categoría eliminada: {old}")

        conn.commit()

        # 3. Reset purchases in obsolete categories to NULL
        for cat in DELETE_CATEGORIES:
            count = conn.execute(
                text("SELECT COUNT(*) FROM purchase WHERE category = :cat"), {"cat": cat}
            ).scalar()
            if count:
                conn.execute(
                    text("UPDATE purchase SET category = NULL WHERE category = :cat"), {"cat": cat}
                )
                print(f"  Reseteadas {count} compras de '{cat}' → NULL")

        conn.commit()

        # 4. Delete obsolete categories
        for cat in DELETE_CATEGORIES:
            if cat in existing:
                conn.execute(text("DELETE FROM category WHERE name = :name"), {"name": cat})
                print(f"  Categoría eliminada: {cat}")

        conn.commit()

    # 5. Run auto_categorize with updated keyword rules
    print("\n  Ejecutando auto-categorización...")
    with Session(engine) as session:
        count = auto_categorize_purchases(session=session)
        session.commit()
        print(f"  Categorizadas automáticamente: {count} compras")

    # 6. Report final state
    with engine.connect() as conn:
        print("\n=== DISTRIBUCIÓN FINAL ===")
        rows = conn.execute(text(
            "SELECT COALESCE(category, 'NULL') as cat, COUNT(*) as cnt "
            "FROM purchase GROUP BY category ORDER BY cnt DESC"
        )).fetchall()
        for cat, cnt in rows:
            print(f"  {cat}: {cnt}")

        null_count = conn.execute(text("SELECT COUNT(*) FROM purchase WHERE category IS NULL")).scalar()
        print(f"\n  Sin categoría (quedan para asignar manualmente): {null_count}")


if __name__ == "__main__":
    print("=== REORGANIZACIÓN DE CATEGORÍAS ===\n")
    run()
    print("\nListo.")

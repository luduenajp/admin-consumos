from __future__ import annotations

from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_sqlite_db_path() -> Path:
    return get_project_root() / "data" / "app.db"


def get_sqlite_url() -> str:
    db_path = get_sqlite_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"  # absolute path

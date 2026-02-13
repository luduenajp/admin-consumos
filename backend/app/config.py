from __future__ import annotations

import os
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_sqlite_db_path() -> Path:
    env_path = os.environ.get("DB_PATH")
    if env_path:
        return Path(env_path)
    return get_project_root() / "data" / "app.db"


def get_sqlite_url() -> str:
    db_path = get_sqlite_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"  # absolute path


def get_cors_origins() -> list[str]:
    env_origins = os.environ.get("CORS_ORIGINS")
    if env_origins:
        return [o.strip() for o in env_origins.split(",")]
    return ["http://localhost:5173"]

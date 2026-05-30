from __future__ import annotations

import base64
import logging
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from starlette.responses import Response

from app.api import router as api_router
from app.config import get_auth_credentials, get_cors_origins
from app.db import init_db
from app.import_api import router as import_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="Admin Consumos", version="0.1.0")

    @app.middleware("http")
    async def basic_auth_middleware(request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        username, password = get_auth_credentials()
        if username and password:
            auth_header = request.headers.get("Authorization", "")
            try:
                scheme, credentials = auth_header.split(" ", 1)
                decoded = base64.b64decode(credentials).decode("utf-8")
                req_user, req_pass = decoded.split(":", 1)
            except Exception:
                return Response(
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Admin Consumos"'},
                )

            valid = (
                secrets.compare_digest(req_user, username)
                and secrets.compare_digest(req_pass, password)
            )
            if not valid:
                return Response(
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Admin Consumos"'},
                )

        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "Conflict: duplicate or constraint violation"})

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    app.include_router(api_router, prefix="/api")
    app.include_router(import_router, prefix="/api")

    dist_path = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if dist_path.exists():
        app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="static")

    return app


app = create_app()

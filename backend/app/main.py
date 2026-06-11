from __future__ import annotations

import base64
import logging
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

# Rutas públicas: /health para healthchecks; manifest/sw/icons porque Chrome
# los fetchea sin credenciales y un 401 hace la PWA no instalable;
# /share-target porque el POST del share sheet llega sin Authorization.
PUBLIC_PATHS = {"/health", "/manifest.webmanifest", "/sw.js", "/share-target"}


class SPAStaticFiles(StaticFiles):
    """Sirve index.html para rutas client-side (deep links del SPA)."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # No enmascarar 404 de API con index.html
            if exc.status_code == 404 and not path.startswith("api/"):
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and not path.startswith("api/"):
            return await super().get_response("index.html", scope)
        return response

from app.api import router as api_router
from app.config import get_auth_credentials, get_cors_origins
from app.db import init_db
from app.import_api import router as import_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="Admin Consumos", version="0.1.0")

    @app.middleware("http")
    async def basic_auth_middleware(request: Request, call_next):
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith("/icons/"):
            return await call_next(request)

        username, password = get_auth_credentials()
        if username and password:
            auth_header = request.headers.get("Authorization", "")
            try:
                scheme, credentials = auth_header.split(" ", 1)
                if scheme.lower() != "basic":
                    raise ValueError("not basic")
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

    @app.post("/share-target")
    def share_target_fallback() -> RedirectResponse:
        # Fallback si el service worker no intercepta el POST del share sheet
        # (p. ej. site data borrado): se descarta el archivo y se abre el form vacío.
        return RedirectResponse("/nueva-transferencia", status_code=303)

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    app.include_router(api_router, prefix="/api")
    app.include_router(import_router, prefix="/api")

    dist_path = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if dist_path.exists():
        app.mount("/", SPAStaticFiles(directory=str(dist_path), html=True), name="static")

    return app


app = create_app()

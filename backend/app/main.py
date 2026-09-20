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
# /share-target porque el POST del share sheet llega sin Authorization;
# /api/backup/db porque tiene su propia auth por Bearer token (BACKUP_TOKEN),
# el backup externo manda solo ese header (no Basic Auth).
PUBLIC_PATHS = {"/health", "/manifest.webmanifest", "/sw.js", "/share-target", "/api/backup/db"}


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
from app.multipart_recovery import recover_file_part
from app.share_target_store import put as store_pending_share

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
    async def share_target_fallback(request: Request) -> RedirectResponse:
        # El service worker no intercepta este POST (ver frontend/public/sw.js):
        # en Chrome/Android el archivo se pierde antes de llegar a la red (bug
        # conocido de Chrome 153, ver SPEC.md UC-054). Acá se maneja el POST
        # directamente. request.body() se llama primero (y se cachea) para
        # poder loguear el raw body si el parser de multipart no encuentra
        # partes, en vez de perder esa información.
        body = await request.body()
        content_type = request.headers.get("content-type", "")

        content: bytes | None = None
        filename = "comprobante"
        file_content_type = "application/octet-stream"
        try:
            form = await request.form()
            for key, value in form.multi_items():
                if hasattr(value, "filename") and value.filename:
                    content = await value.read()
                    filename = value.filename
                    file_content_type = value.content_type or file_content_type
                    break
        except Exception as exc:
            print(f"[share-target] request.form() raised: {exc!r}", flush=True)

        if not content:
            # Starlette encontró 0 partes: algunos navegadores (confirmado con
            # Samsung Internet) mandan un body multipart válido pero con un
            # byte de más antes del boundary de cierre, lo que rompe el
            # parser estándar. Reintentamos con un parser más tolerante antes
            # de darnos por vencidos.
            recovered = recover_file_part(body, content_type)
            if recovered:
                content, filename, file_content_type = recovered
                print(
                    f"[share-target] RECOVERED via lenient parser: file={filename!r} "
                    f"type={file_content_type!r} size={len(content)}",
                    flush=True,
                )

        if content:
            token = store_pending_share(content, filename, file_content_type)
            print(
                f"[share-target] OK file={filename!r} type={file_content_type!r} size={len(content)}",
                flush=True,
            )
            return RedirectResponse(f"/nueva-transferencia?shared=1&token={token}", status_code=303)

        # Diagnóstico temporal: el body tiene bytes (a veces cientos de KB)
        # pero el parser de multipart no encontró ninguna parte. Volcamos
        # content-type/length + una porción del raw body (inicio y fin, donde
        # están los boundaries y headers de cada parte) para ver qué formato
        # está mandando realmente el navegador.
        head = body[:400]
        tail = body[-200:] if len(body) > 400 else b""
        print(
            f"[share-target] NO FILE. content-type={content_type!r} body_len={len(body)} "
            f"head={head!r} tail={tail!r}",
            flush=True,
        )
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

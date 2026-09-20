from __future__ import annotations

import base64
import logging
import secrets
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
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
    async def share_target_fallback(request: Request, file: UploadFile | None = File(None)) -> RedirectResponse:
        # El service worker no intercepta este POST (ver frontend/public/sw.js):
        # en Android/Chrome el body de la navegación del share target no le
        # llega de forma confiable al fetch handler del SW. Se maneja acá,
        # guardando el archivo server-side con un token de un solo uso.
        if file is not None and file.filename:
            content = await file.read()
            if content:
                token = store_pending_share(
                    content, file.filename, file.content_type or "application/octet-stream"
                )
                print(
                    f"[share-target] OK file={file.filename!r} type={file.content_type!r} "
                    f"size={len(content)}",
                    flush=True,
                )
                return RedirectResponse(f"/nueva-transferencia?shared=1&token={token}", status_code=303)

        # Diagnóstico temporal: no vino un archivo utilizable bajo el campo
        # "file". Volcamos headers + el resto de los campos del form (si los
        # hay) para ver qué mandó realmente el share sheet de Android.
        form_parts = []
        for key, value in (await request.form()).multi_items():
            if hasattr(value, "filename"):
                blob = await value.read()
                form_parts.append(f"{key}=file({value.filename!r},{value.content_type!r},{len(blob)}b)")
            else:
                form_parts.append(f"{key}={value!r}")
        print(
            f"[share-target] NO FILE. content-type={request.headers.get('content-type')!r} "
            f"content-length={request.headers.get('content-length')!r} "
            f"file-param={file!r} form=[{', '.join(form_parts)}]",
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

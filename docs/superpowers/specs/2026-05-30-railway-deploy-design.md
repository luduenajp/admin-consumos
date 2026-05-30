# Railway Deploy Design

**Date:** 2026-05-30  
**Goal:** Deploy admin-consumos to Railway so the app is accessible from multiple PCs via browser.

## Context

The app is currently local-only (FastAPI + React/Vite + SQLite). The user wants to access it from a second PC. A scheduled Cowork task (`gmail-gastos-a-db`) writes purchases directly to the SQLite file and must keep working after migration.

## Architecture

Single Railway service. FastAPI serves the React frontend as static files and handles all API routes. SQLite is stored on a Railway persistent volume.

```
Railway Service: admin-consumos
├── Build:   cd frontend && npm install && npm run build
├── Start:   cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
├── Volume:  /data  →  DB_PATH=/data/app.db
└── URL:     https://admin-consumos-xxxx.up.railway.app
```

Request routing:
- `GET /health` → health check (no auth, required by Railway)
- `POST|GET|... /api/*` → FastAPI routers (after Basic Auth)
- `GET /*` → `frontend/dist/` static files via `StaticFiles(html=True)` (after Basic Auth)

## Basic Auth Middleware

Added to `backend/app/main.py` as an HTTP middleware. Runs before all routes. Uses `secrets.compare_digest` to prevent timing attacks. Returns 401 with `WWW-Authenticate: Basic` header on failure. The `/health` path is exempt.

Credentials are read from two new env vars: `APP_USERNAME` and `APP_PASSWORD`, added to `backend/app/config.py`.

## Static Files

After all routers are mounted in `create_app()`:

```python
app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
```

`html=True` ensures unknown paths return `index.html`, which is required for React Router client-side routing to work.

## Railway Configuration (`railway.json`)

```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "cd frontend && npm install && npm run build"
  },
  "deploy": {
    "startCommand": "cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

Railway auto-detects Python from `backend/requirements.txt` and installs deps. The `/data` volume is configured from the Railway dashboard.

## Environment Variables (Railway Dashboard)

| Variable | Value |
|---|---|
| `DB_PATH` | `/data/app.db` |
| `CORS_ORIGINS` | `https://admin-consumos-xxxx.up.railway.app` |
| `APP_USERNAME` | chosen username |
| `APP_PASSWORD` | chosen password |

## Gmail Task Migration

The `gmail-gastos-a-db` Cowork task currently writes directly to SQLite. After migration it must use the Railway REST API instead.

**Change:** Replace all direct SQLite `INSERT` statements with `POST /api/purchases` and `POST /api/purchases` (transfer variant) HTTP calls using Basic Auth.

```python
import requests, os

RAILWAY_URL = os.environ["RAILWAY_URL"]
AUTH = (os.environ["APP_USERNAME"], os.environ["APP_PASSWORD"])

response = requests.post(
    f"{RAILWAY_URL}/api/purchases",
    json=purchase_payload,
    auth=AUTH
)
```

The task already builds the correct purchase payloads — only the destination changes.

**New env vars required in Cowork agent:**

| Variable | Value |
|---|---|
| `RAILWAY_URL` | Railway app URL |
| `APP_USERNAME` | same as Railway |
| `APP_PASSWORD` | same as Railway |

## Files to Create / Modify

| File | Change |
|---|---|
| `railway.json` | New — build + start config |
| `backend/app/main.py` | Add Basic Auth middleware + StaticFiles mount |
| `backend/app/config.py` | Add `APP_USERNAME`, `APP_PASSWORD` settings |
| `.claude/tasks/gmail-gastos-a-db.md` | Replace direct DB writes with API calls |

## Out of Scope

- Custom domain (no real domain available)
- Database migration tool (SQLite volume starts empty; user manually imports existing data or copies DB file via Railway CLI)
- CI/CD pipeline (Railway auto-deploys from GitHub `main` branch)

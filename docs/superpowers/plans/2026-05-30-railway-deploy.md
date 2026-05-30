# Railway Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy admin-consumos to Railway as a single service so the app is accessible from any browser, with Basic Auth protection and the Gmail import task migrated to use the REST API.

**Architecture:** FastAPI serves the React frontend as static files from `frontend/dist/` and handles all API routes. A Basic Auth HTTP middleware protects every route except `/health`. SQLite lives on a Railway persistent volume at `/data/app.db`. The `gmail_import.py` script detects a `RAILWAY_URL` env var and calls `POST /api/purchases` instead of writing to SQLite directly.

**Tech Stack:** FastAPI, Starlette StaticFiles, Railway (Nixpacks), SQLite volume, `requests` library in gmail_import.py

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `railway.json` | Create | Build + start command for Railway |
| `backend/app/config.py` | Modify | Add `get_auth_credentials()` |
| `backend/app/main.py` | Modify | Basic Auth middleware + StaticFiles mount |
| `backend/tests/test_auth.py` | Create | Tests for auth middleware |
| `scripts/gmail_import.py` | Modify | Railway API mode when `RAILWAY_URL` is set |
| `.claude/tasks/gmail-gastos-a-db.md` | Modify | Use Railway API for suggest-month + env vars |

---

## Task 1: Create `railway.json`

**Files:**
- Create: `railway.json`

- [ ] **Step 1: Create the file**

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

- [ ] **Step 2: Commit**

```bash
git add railway.json
git commit -m "feat: add Railway deployment config"
```

---

## Task 2: Add auth credentials to `config.py`

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add `get_auth_credentials()` at the bottom of `config.py`**

```python
def get_auth_credentials() -> tuple[str, str]:
    return os.environ.get("APP_USERNAME", ""), os.environ.get("APP_PASSWORD", "")
```

No test needed — it's a one-liner env read, same pattern as `get_cors_origins()` already in the file.

- [ ] **Step 2: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add APP_USERNAME/APP_PASSWORD config"
```

---

## Task 3: Add Basic Auth middleware and StaticFiles to `main.py`

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_auth.py`:

```python
"""Tests for Basic Auth middleware."""
from __future__ import annotations

import base64
import pytest
from starlette.testclient import TestClient

from app.main import create_app


def _auth_header(user: str, password: str) -> dict:
    credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


@pytest.fixture()
def auth_client(engine, monkeypatch):
    import app.db as db_module
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setenv("APP_USERNAME", "testuser")
    monkeypatch.setenv("APP_PASSWORD", "testpass")
    application = create_app()
    with TestClient(application, raise_server_exceptions=True) as c:
        yield c


def test_health_no_auth(auth_client):
    """Health endpoint is exempt from auth."""
    r = auth_client.get("/health")
    assert r.status_code == 200


def test_api_no_auth_returns_401(auth_client):
    r = auth_client.get("/api/persons")
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate") == 'Basic realm="Admin Consumos"'


def test_api_wrong_password_returns_401(auth_client):
    r = auth_client.get("/api/persons", headers=_auth_header("testuser", "wrong"))
    assert r.status_code == 401


def test_api_correct_credentials_pass(auth_client):
    r = auth_client.get("/api/persons", headers=_auth_header("testuser", "testpass"))
    assert r.status_code == 200


def test_no_auth_config_allows_all(client):
    """When APP_USERNAME is not set, middleware does not enforce auth."""
    r = client.get("/api/persons")
    assert r.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && source ../.venv/bin/activate && python -m pytest tests/test_auth.py -v
```

Expected: FAIL — `create_app` doesn't have auth middleware yet.

- [ ] **Step 3: Add imports and middleware to `main.py`**

Add to the imports section at the top of `backend/app/main.py`:

```python
import base64
import secrets
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.config import get_auth_credentials, get_cors_origins
```

Add the middleware inside `create_app()`, **before** `app.add_middleware(CORSMiddleware, ...)`:

```python
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
```

Add the StaticFiles mount at the **end** of `create_app()`, after both `include_router` calls and **before** `return app`:

```python
dist_path = Path(__file__).parent.parent.parent / "frontend" / "dist"
if dist_path.exists():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="static")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_auth.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd backend && python -m pytest tests/ -q
```

Expected: 0 failed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_auth.py
git commit -m "feat: add Basic Auth middleware and StaticFiles serving"
```

---

## Task 4: Add Railway API mode to `gmail_import.py`

**Files:**
- Modify: `scripts/gmail_import.py`

The script currently writes directly to SQLite. When `RAILWAY_URL` is set as an env var, it should instead call `POST /api/purchases` on Railway using HTTP Basic Auth. Local SQLite mode is unchanged.

- [ ] **Step 1: Add `_payer_for_record()` helper and Railway mode functions after the `is_duplicate` function (around line 128)**

```python
def _payer_for_record(rec: dict) -> int:
    """Returns person_id of who pays (card owner, not consumer)."""
    card_id = rec.get("card_id")
    if card_id == 1:
        return 1
    if card_id in (2, 3):
        return 2
    return int(rec.get("owner_person_id", 1))


def _build_api_payload(rec: dict) -> dict:
    """Build PurchaseCreate-compatible payload from a gmail record."""
    amount = float(rec["amount_original"])
    installments = int(rec.get("installments_total", 1))
    payer_person_id = _payer_for_record(rec)
    return {
        "card_id": rec.get("card_id"),
        "payment_method": rec.get("payment_method", "CARD"),
        "purchase_date": rec["purchase_date"],
        "description": rec["description"],
        "currency": rec.get("currency", "ARS"),
        "amount_original": amount,
        "installments_total": installments,
        "first_installment_month": rec.get("first_installment_month"),
        "owner_person_id": int(rec.get("owner_person_id", 1)),
        "category": rec.get("category_concept"),
        "is_refund": bool(rec.get("is_refund", 0)),
        "is_common": bool(rec.get("is_common", 0)),
        "payers": [{"person_id": payer_person_id, "share_type": "PERCENT", "share_value": 100.0}],
    }


def insert_via_api(rec: dict, railway_url: str, auth: tuple) -> bool:
    """POST purchase to Railway API. Returns True if created, False if duplicate (409)."""
    import requests as req_lib
    payload = _build_api_payload(rec)
    resp = req_lib.post(f"{railway_url}/api/purchases", json=payload, auth=auth, timeout=15)
    if resp.status_code == 201:
        return True
    if resp.status_code == 409:
        return False
    resp.raise_for_status()
    return False
```

- [ ] **Step 2: Modify `main()` to branch between Railway mode and local SQLite mode**

Replace the entire block from `DB_PATH = detect_db_path()` down to the end of `main()` with:

```python
def main():
    if len(sys.argv) < 2:
        print('Uso: python3 gmail_import.py <ruta_al_json>')
        sys.exit(1)

    json_path = sys.argv[1]
    with open(json_path, encoding='utf-8') as f:
        payload = json.load(f)

    if isinstance(payload, list):
        records = payload
        ignored_ids = []
    else:
        records = payload.get('records', [])
        ignored_ids = payload.get('ignored_ids', [])

    if not records and not ignored_ids:
        print('Sin registros ni IDs ignorados. Nada para procesar.')
        sys.exit(0)

    railway_url = os.environ.get('RAILWAY_URL', '').rstrip('/')
    if railway_url:
        _run_railway_mode(records, ignored_ids, railway_url)
    else:
        _run_local_mode(records, ignored_ids)
```

- [ ] **Step 3: Extract existing local SQLite logic into `_run_local_mode()`**

Rename the current body of `main()` (from `DB_PATH = detect_db_path()` to the final print block) into a new function `_run_local_mode(records, ignored_ids)`. The logic is unchanged — just wrap it in the function.

- [ ] **Step 4: Add `_run_railway_mode()` function**

```python
def _run_railway_mode(records: list, ignored_ids: list, railway_url: str) -> None:
    username = os.environ.get('APP_USERNAME', '')
    password = os.environ.get('APP_PASSWORD', '')
    auth = (username, password)

    DB_PATH = detect_db_path()
    ID_FILE = os.path.join(os.path.dirname(DB_PATH), 'gmail_processed_ids.json')

    if os.path.exists(ID_FILE):
        with open(ID_FILE, encoding='utf-8') as f:
            processed_ids = set(json.load(f))
    else:
        processed_ids = set()

    all_reviewed_ids = set(ignored_ids)
    created = 0
    skipped = 0

    print(f'Railway mode: {railway_url}')
    print(f'Registros a evaluar: {len(records)}')
    print()

    for rec in records:
        msg_id = rec.get('msg_id', '')
        all_reviewed_ids.add(msg_id)

        if msg_id in processed_ids:
            print(f'  SKIP (ID ya procesado): {rec.get("description")}')
            skipped += 1
            continue

        try:
            ok = insert_via_api(rec, railway_url, auth)
        except Exception as e:
            print(f'  ERROR al insertar {rec.get("description")}: {e}')
            continue

        if ok:
            created += 1
            print(f'  ✓ INSERTADO: {rec["purchase_date"]} | {rec["description"]} | ${float(rec["amount_original"]):,.2f}')
        else:
            skipped += 1
            print(f'  SKIP (duplicado API): {rec["purchase_date"]} | {rec["description"]}')

    processed_ids.update(all_reviewed_ids)
    with open(ID_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(processed_ids), f, indent=2)

    print()
    print('=' * 50)
    print(f'Nuevos registros insertados : {created}')
    print(f'Saltados                    : {skipped}')
    print(f'IDs guardados en archivo    : {len(processed_ids)}')
    print('=' * 50)
```

- [ ] **Step 5: Verify the script still runs locally without errors**

```bash
cd /Users/pablo/github/admin-consumos
source .venv/bin/activate
echo '{"records":[],"ignored_ids":[]}' > /tmp/test_empty.json
python3 scripts/gmail_import.py /tmp/test_empty.json
```

Expected output: `Sin registros ni IDs ignorados. Nada para procesar.`

- [ ] **Step 6: Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -q
```

Expected: 0 failed.

- [ ] **Step 7: Commit**

```bash
git add scripts/gmail_import.py
git commit -m "feat: add Railway API mode to gmail_import.py"
```

---

## Task 5: Update Gmail task file for Railway

**Files:**
- Modify: `.claude/tasks/gmail-gastos-a-db.md`

The task file needs to: (1) replace the inline `suggest_first_installment_month` SQLite function with a call to the Railway API endpoint `GET /api/card-statements/suggest-month`, and (2) document the required env vars.

- [ ] **Step 1: Replace the `suggest_first_installment_month` function in Paso 3**

Find the inline Python function `suggest_first_installment_month` in Paso 3 (the block starting with `def suggest_first_installment_month(cur, card_id, purchase_date_str):`).

Replace it with:

```python
def suggest_first_installment_month(card_id, purchase_date_str):
    """Calls Railway API to get the correct first_installment_month.
    Falls back to next month for CARD, same month for TRANSFER.
    """
    import requests, os
    railway_url = os.environ.get('RAILWAY_URL', '').rstrip('/')
    username = os.environ.get('APP_USERNAME', '')
    password = os.environ.get('APP_PASSWORD', '')
    if railway_url and card_id:
        try:
            resp = requests.get(
                f'{railway_url}/api/card-statements/suggest-month',
                params={'card_id': card_id, 'purchase_date': purchase_date_str},
                auth=(username, password),
                timeout=10,
            )
            if resp.ok:
                return resp.json()['year_month']
        except Exception:
            pass
    # Fallback: next month for cards
    y, m = map(int, purchase_date_str[:7].split('-'))
    m += 1
    if m > 12:
        m, y = 1, y + 1
    return f'{y:04d}-{m:02d}'
```

Also update the call site in Paso 3 (the mapping rule for `first_installment_month`) from:
```
`first_installment_month` = `suggest_first_installment_month(cur, card_id, purchase_date)` — usa la tabla `cardstatement` si hay datos; fallback al mes siguiente
```
to:
```
`first_installment_month` = `suggest_first_installment_month(card_id, purchase_date)` — llama a Railway API; fallback al mes siguiente
```

- [ ] **Step 2: Add env vars section to the task file**

Add a new section at the very end of `.claude/tasks/gmail-gastos-a-db.md`:

```markdown
---

## Variables de entorno requeridas (Cowork)

| Variable | Descripción |
|---|---|
| `RAILWAY_URL` | URL del servicio en Railway, ej: `https://admin-consumos-xxxx.up.railway.app` |
| `APP_USERNAME` | Usuario de Basic Auth configurado en Railway |
| `APP_PASSWORD` | Contraseña de Basic Auth configurada en Railway |
```

- [ ] **Step 3: Commit**

```bash
git add .claude/tasks/gmail-gastos-a-db.md
git commit -m "feat: update gmail task to use Railway API for suggest-month"
```

---

## Task 6: Manual setup on Railway (checklist)

These steps happen in Railway's dashboard, not in code.

- [ ] Create a new Railway project and connect the GitHub repo (`luduenajp/admin-consumos` or equivalent)
- [ ] Railway auto-detects `railway.json` — verify build command is `cd frontend && npm install && npm run build`
- [ ] Add a **Volume** mounted at `/data`
- [ ] Set environment variables in Railway dashboard:
  - `DB_PATH` = `/data/app.db`
  - `CORS_ORIGINS` = `https://<your-railway-url>.up.railway.app`
  - `APP_USERNAME` = your chosen username
  - `APP_PASSWORD` = your chosen password
- [ ] Trigger first deploy and verify `/health` returns `{"status":"ok"}`
- [ ] Open `https://<your-railway-url>.up.railway.app` in browser — should prompt for Basic Auth
- [ ] Set `RAILWAY_URL`, `APP_USERNAME`, `APP_PASSWORD` as env vars in Cowork for the `gmail-gastos-a-db` task

---

## Self-Review

**Spec coverage:**
- ✅ `railway.json` — Task 1
- ✅ Basic Auth middleware — Task 3
- ✅ `APP_USERNAME`/`APP_PASSWORD` in config — Task 2
- ✅ StaticFiles serving `frontend/dist` — Task 3
- ✅ Gmail task migrated to API — Tasks 4 + 5
- ✅ Manual Railway setup — Task 6

**Placeholders:** None.

**Type consistency:**
- `get_auth_credentials()` returns `tuple[str, str]` — used in Task 3 as `username, password = get_auth_credentials()` ✅
- `insert_via_api(rec, railway_url, auth)` defined in Task 4 Step 1, called in Task 4 Step 4 ✅
- `_run_railway_mode` / `_run_local_mode` defined in Task 4 Steps 4+3, called in Task 4 Step 2 ✅
- `suggest_first_installment_month(card_id, purchase_date_str)` — new signature (no `cur` param) matches updated call site in Task 5 ✅

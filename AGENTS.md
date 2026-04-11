# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project overview
Admin Consumos is a local-only household finance app to track credit card purchases, installments, shared/common expenses, and monthly balancing transfers.  
Stack:
- Backend: FastAPI + SQLModel + SQLite (`backend/app`)
- Frontend: React + TypeScript + Vite + React Query (`frontend/src`)

No authentication and no cloud backend by design.

## Mandatory spec workflow
- `SPEC.md` is the source of truth for business rules and invariants.
- Before implementing a new feature, verify it does not conflict with existing UC/BR rules in `SPEC.md`.
- If there is a conflict, stop and ask the user.
- After implementing behavior changes, update `SPEC.md` accordingly.

## Common commands
Run from repository root unless noted.

### Full local dev (recommended)
```bash
./start.sh
```
- Starts backend on `:8000` and frontend on `:5173`
- Auto-creates `.venv` and installs dependencies if missing
- Uses `DB_PATH=data/test.db` for dev runs

### Backend setup and run
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000
```

### Frontend setup and run
```bash
cd frontend
npm install
npm run dev
```

### Quality checks
```bash
# Backend tests (from backend/)
source ../.venv/bin/activate
python -m pytest tests/ -q

# Frontend tests (from frontend/)
npm run test:run

# Frontend lint + type/build check (from frontend/)
npm run lint
npm run build
```

### Run a single test
```bash
# Backend single test (from backend/)
source ../.venv/bin/activate
python -m pytest tests/test_crud_reports.py::test_report_month_breakdown -q

# Frontend single test file (from frontend/)
npm run test:run -- src/pages/dashboard-page.test.tsx
```

## High-level architecture
### Request/data flow
1. UI pages call typed API functions in `frontend/src/api/endpoints.ts`.
2. HTTP helpers in `frontend/src/api/http.ts` apply consistent fetch behavior (30s timeout, normalized error extraction).
3. FastAPI routes in `backend/app/api.py` and `backend/app/import_api.py` expose `/api/*`.
4. Business logic lives in `backend/app/crud.py`.
5. Persistence models are defined in `backend/app/models.py`, with DB setup in `backend/app/db.py`.

### Backend structure (big picture)
- `main.py`: app factory, CORS wiring, global `IntegrityError`/`ValueError` handlers, startup `init_db()`, router mounting.
- `api.py`: CRUD + reporting + budgeting/transfers/savings endpoints.
- `import_api.py`: file import workflows (detect card holder, import XLSX/PDF/Sheets), import batch tracking.
- `crud.py`: domain logic (purchase creation, payer allocation, installment schedule generation, reporting, transfer calculation, categorization, exports).
- `models.py` + `schemas.py`: SQLModel entities and API validation contracts.

### Frontend structure (big picture)
- `App.tsx` defines top-level routes/navigation.
- Page components orchestrate data queries/mutations.
- Shared data layer in `src/api/*` keeps endpoint contracts centralized.
- React Query defaults are configured in `src/main.tsx` (`staleTime: 2m`, `gcTime: 10m`, `retry: 1`, no refetch on window focus).

## Domain invariants and patterns to preserve
- Fondo Común transfer logic is core behavior (see `crud.py:calculate_transfers` and BR-001 in `SPEC.md`); do not alter semantics without explicit user request.
- `create_purchase` is atomic: purchase + payers + installment schedule are created in one transaction.
- For `TRANSFER` and `CASH` purchases, installment month is forced to purchase month.
- If no payers are provided, payer defaults to card owner (or `owner_person_id` for non-card purchases).
- Missing FX for USD rows means exclusion from totals (skip), not conversion to zero.
- Import deduplication relies on SHA256 fingerprints in `ImportedRow`; re-import must remain idempotent.

## Import pipeline notes
- Importers parse source rows, normalize descriptions, and compute fingerprints.
- Installment import attempts two-pass matching to avoid duplicate purchases:
  1. Exact normalized description + amount match
  2. Unique fuzzy candidate by date/card/currency/amount
- Imports are grouped in `ImportBatch` for traceability.

## Scheduled task integration
There is an automated Cowork task at `.claude/tasks/gmail-gastos-a-db.md` that writes directly to `data/app.db`.  
If DB schema changes touch `purchase`, `installmentschedule`, or `purchasepayer`, update that task document’s schema section to keep automation working.

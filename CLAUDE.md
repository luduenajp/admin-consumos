# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Admin Consumos is a local-only web app for managing credit card expenses with installment tracking. It supports importing bank statements (Visa XLSX, PDF de resúmenes), splitting payments between people, filtering by who paid, and generating monthly reports with USD→ARS conversion. No authentication — single-user household tool.

## Development Commands

### Arranque rápido (recomendado)

```bash
./start.sh
```

Levanta backend (port 8000) y frontend (port 5173) en paralelo. Crea venv e instala dependencias si faltan.

### Backend (Python 3.11+ required — uses `StrEnum`)

```bash
# Setup (from project root — use python3.11 explicitly if python3 defaults to <3.11)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Run
cd backend && uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000`. SQLite database auto-creates at `data/app.db` on first startup via `init_db()`.

### Frontend (React + TypeScript + Vite)

```bash
cd frontend && npm install
cd frontend && npm run dev       # Dev server at http://localhost:5173
cd frontend && npm run build     # TypeScript check + Vite production build
cd frontend && npm run lint      # ESLint
```

The Vite dev server proxies `/api` requests to `http://localhost:8000` (configured in `vite.config.ts`).

### Environment Variables

Configured in `backend/app/config.py`, with sensible defaults:

| Variable | Default | Description |
|---|---|---|
| `DB_PATH` | `<project_root>/data/app.db` | Absolute path to SQLite database |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |

See `.env.example` for reference.

### Testing

No test suite configured yet. Planned: pytest + FastAPI TestClient (backend), Vitest + React Testing Library (frontend).

## Architecture

**Monorepo** with independent backend and frontend:

### Backend (`backend/app/`)

| File | Role |
|---|---|
| `main.py` | FastAPI app factory, CORS (configurable via env), router mounting, `init_db()` on startup |
| `api.py` | REST endpoints — CRUD for people, cards, purchases, FX rates; monthly reports; `GET /reports/month-breakdown`. POST /cards catches `ValueError` for FK validation |
| `import_api.py` | File import endpoints (Visa XLSX, Visa/Mastercard PDF) |
| `crud.py` | Business logic — atomic purchase creation (flush + single commit), FK existence validation, installment schedule generation, monthly report queries, `list_purchases` (person_id filter), `report_month_breakdown` (desglose de cuotas por mes) |
| `models.py` | SQLModel ORM models (7 tables: Person, Card, Purchase, PurchasePayer, InstallmentSchedule, FxRate, ImportedRow) |
| `schemas.py` | Pydantic schemas with `year_month` regex validation (`YYYY-MM`), `share_value > 0` constraint, and `model_validator` ensuring PERCENT payer shares sum to 100 |
| `db.py` | SQLite engine with `PRAGMA foreign_keys=ON` enforcement, session context manager |
| `config.py` | Environment-based configuration (DB_PATH, CORS_ORIGINS) with defaults |
| `importers/visa_xlsx.py` | XLSX parser with deduplication via SHA256 fingerprints |
| `importers/visa_pdf.py` | PDF parser (Banco Nación Visa/Mastercard, MercadoPago). Soporta contraseña. |

All API routes use prefix `/api`. Routers: `api_router` (CRUD + reports) and `import_router` (file imports).

### Importación PDF

Formatos soportados (orden de intento):

1. **Banco Nación Visa**: `FECHA COMPROBANTE DETALLE DE TRANSACCION PESOS DOLAR`, líneas `DD.MM.YY comprobante descripción C.X/Y monto_pesos monto_usd`
2. **Banco Nación Mastercard**: `DETALLES DEL MES` / `CUOTAS DEL MES`, líneas `DD-Mmm-YY descripción X/Y comprobante monto`
3. **MercadoPago**: líneas `DD/mmm descripción $ monto` (ej. `10/nov MERPAGO*COMERCIO 3 de 3 304823 $ 22.293,25`)

Detecta mes de cierre en: "CIERRE ACTUAL", "Cierre actual X de febrero", "Fecha de cierre", "Resumen de febrero".

### Frontend (`frontend/src/`)

| Path | Role |
|---|---|
| `App.tsx` | React Router layout with 4 routes: `/`, `/purchases`, `/import`, `/admin`. Wraps routes in `ErrorBoundary` |
| `components/ErrorBoundary.tsx` | Class component catching render errors with fallback UI |
| `api/types.ts` | TypeScript interfaces matching backend schemas (read + create payloads) |
| `api/http.ts` | Fetch wrappers with 30s timeout (`AbortController`) + `extractErrorMessage()` utility for parsing backend error payloads |
| `api/endpoints.ts` | API client functions for all endpoints |
| `pages/dashboard-page.tsx` | Dashboard con selector de mes, resumen del mes (desglose de cuotas), totales mensuales, timeline de cuotas futuras, gráficos por categoría, filtro por persona |
| `pages/purchases-page.tsx` | Listado de compras con filtros (categoría, fechas, montos, descripción, pagado por, deudor), paginación, edición inline |
| `pages/import-page.tsx` | Importación XLSX o PDF (Banco Nación, MercadoPago). Campo de contraseña para PDF protegidos |
| `pages/admin-page.tsx` | Entity management — create People, Cards, FX Rates (3 sections with inline forms + tables) |

Uses React Query (`@tanstack/react-query`) with configured defaults: `staleTime: 2min`, `gcTime: 10min`, `retry: 1`, `refetchOnWindowFocus: false`.

### CSS Design System

Warm color palette defined as CSS custom properties in `index.css`:

| Variable | Value | Usage |
|---|---|---|
| `--color-bg` | `#faf6f1` | Page background (cream) |
| `--color-surface` | `#ffffff` | Panel/card background |
| `--color-primary` | `#c0693b` | Buttons, active nav, focus rings (terracotta) |
| `--color-text` | `#3d2c1e` | Main text (dark brown) |
| `--color-text-secondary` | `#7a6455` | Labels, secondary text |
| `--color-border` | `#e8ddd3` | Borders and dividers (beige) |

All component styles use these variables via `App.css`. No CSS framework — plain CSS with class names: `page`, `pageTitle`, `panel`, `panelTitle`, `table`, `formRow`, `label`, `input`, `button`, `error`, `success`, `muted`, `hint`.

## Data Integrity Patterns

- **Atomic transactions**: `create_purchase` uses `session.flush()` (not commit) to get the purchase ID, then creates payers + installment schedule in a single `session.commit()`
- **FK enforcement**: SQLite `PRAGMA foreign_keys=ON` enabled via SQLAlchemy event listener in `db.py`
- **FK validation**: `create_card` and `create_purchase` validate that referenced Person/Card IDs exist before creating, raising `ValueError` (caught as HTTP 400)
- **Input validation**: `year_month` fields use regex `^\d{4}-(0[1-9]|1[0-2])$`; payer `share_value` must be `> 0`; PERCENT shares must sum to 100 (model_validator)

## Key Domain Concepts

- **Installments (cuotas)**: Purchases can have N installments. Importing parses "x de y" format. `InstallmentSchedule` entries are auto-generated on purchase creation, one per month.
- **FX rates**: USD→ARS exchange rates are entered manually per month via `/admin` page. If missing for a given month, USD installments are excluded from reports (not zero — omitted).
- **Payment split**: Default is 100% to card owner. `PurchasePayer` supports percent or fixed splits across multiple people.
- **Deduplication**: Import creates SHA256 fingerprints per row (`ImportedRow`). Re-importing the same file skips already-imported rows.
- **Exclusion heuristic**: Se excluyen pagos, promos, bonificaciones, impuestos (DB.RG 5617, IIBB PERCEP, Impuesto de sellos, Impuesto al sello), "Pago de tarjeta", "Resumen de [mes]". Sí se incluyen devoluciones por compra anulada.

## Adding a New Import Provider

1. Create `backend/app/importers/<provider>.py` implementing `parse_<provider>(path) -> list[ParsedPurchaseRow]` (o extender `visa_pdf.py` con nuevo formato)
2. Add endpoint in `backend/app/import_api.py`
3. Add UI option in `frontend/src/pages/import-page.tsx`

## Scripts útiles

- **`./start.sh`**: Inicia backend y frontend en paralelo. Crea virtualenv si no existe, instala deps.
- **`examples/validate_pdf.py`**: Valida formato de PDFs. Uso: `python validate_pdf.py <archivo.pdf> [contraseña] [--debug]`

## Adding New Reports

1. Add query logic in `backend/app/crud.py`
2. Expose endpoint in `backend/app/api.py`
3. Consume from a page component in `frontend/src/pages/`

## Frontend Patterns to Follow

- Use `useQuery` with descriptive `queryKey` arrays (include filter params as last element)
- Use `useMutation` with `onSuccess` that calls `queryClient.invalidateQueries()` for affected queries
- Use `extractErrorMessage()` from `api/http.ts` for all error displays
- Use existing CSS class names from `App.css` — don't introduce new styling systems
- All forms follow the pattern: `useState` for form state, `useMutation` for submission, inline error/success feedback

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Admin Consumos is a local-only web app for managing credit card expenses with installment tracking. It supports importing bank statements (Visa XLSX, PDF de resúmenes), splitting payments between people, filtering by who paid, and generating monthly reports with USD→ARS conversion. No authentication — single-user household tool.

## Specification Document

`SPEC.md` (project root) is the formal software specification. It catalogs every use case (UC-XXX), business rule (BR-XXX), data model, API endpoint, validation rule, and data integrity invariant.

**Regla obligatoria para nuevas features:**
1. **Antes de implementar**, leer SPEC.md y validar que la feature propuesta no entre en conflicto con casos de uso (UC-XXX), reglas de negocio (BR-XXX) o invariantes ya definidos.
2. Si hay conflicto, informar al usuario antes de proceder.
3. **Después de implementar**, actualizar SPEC.md agregando los nuevos UC, BR, endpoints, o modelos que correspondan, manteniendo la numeración y formato existente.

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

```bash
# Backend (desde backend/)
source ../.venv/bin/activate
python -m pytest tests/ -q

# Frontend (desde frontend/)
npm run test:run
```

**Regla obligatoria:** Los tests deben correrse y pasar completamente antes de considerar cualquier cambio o feature como terminado. Un desarrollo está completo cuando:
1. `python -m pytest tests/ -q` → todos los tests pasan (0 failed)
2. `npm run test:run` → todos los tests pasan (0 failed)
3. `npm run build` → TypeScript compila sin errores

**Regla para tests que fallan tras un cambio:** Si un cambio rompe un test existente, NO modificar el test automáticamente. Primero consultar al usuario explicando:
- Qué test falló y por qué
- Si el fallo indica un bug en el código nuevo (fix el código) o si el comportamiento cambió intencionalmente (ahí sí actualizar el test con aprobación)

**Regla para nuevas features:** Al agregar una feature, agregar también los tests correspondientes. Si la feature toca lógica de negocio existente (BR-XXX en SPEC.md), agregar o extender los tests en `test_spec_business_rules.py`.

## Architecture

**Monorepo** with independent backend and frontend:

### Backend (`backend/app/`)

| File | Role |
|---|---|
| `main.py` | FastAPI app factory, CORS (configurable via env), router mounting, `init_db()` on startup |
| `api.py` | REST endpoints — full CRUD for all entities; monthly reports (`GET /reports/month-breakdown`); categories; budgets; incomes; debt transfers; `calculate_transfers` (Fondo Común logic); `export_dashboard_to_excel`. `POST /cards` y `POST /purchases` capturan `ValueError` para FK validation (HTTP 400) |
| `import_api.py` | File import endpoints (Visa XLSX, Visa/Mastercard PDF, Google Sheets CSV) |
| `crud.py` | Business logic — atomic purchase creation (flush + single commit), FK existence validation, installment schedule generation, all report queries (`list_purchases` con person_id filter, `report_month_breakdown` desglose de cuotas por mes), `calculate_transfers` (Fondo Común), `auto_categorize_purchases`, `calculate_monthly_balance`, `export_dashboard_to_excel` |
| `models.py` | SQLModel ORM models (12 tables: Person, Card, Debtor, Category, Purchase, PurchasePayer, InstallmentSchedule, FxRate, ImportedRow, MonthlyBudget, Income, DebtTransfer) |
| `schemas.py` | Pydantic schemas with `year_month` regex validation (`YYYY-MM`), `share_value > 0` constraint, and `model_validator` ensuring PERCENT payer shares sum to 100 |
| `db.py` | SQLite engine with `PRAGMA foreign_keys=ON` enforcement, session context manager |
| `config.py` | Environment-based configuration (DB_PATH, CORS_ORIGINS) with defaults |
| `utils_dates.py` | Date helpers (e.g., `add_months`) |
| `importers/visa_xlsx.py` | XLSX parser with deduplication via SHA256 fingerprints |
| `importers/visa_pdf.py` | PDF parser (Banco Nación Visa/Mastercard, MercadoPago). Soporta contraseña. |
| `importers/gsheets_importer.py` | Google Sheets CSV importer — downloads public sheet URL and parses rows |

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
| `App.tsx` | React Router layout: `/`, `/purchases`, `/import`, `/budget`, `/categories`, `/goals`, `/ahorros`, `/nueva-transferencia`, `/admin`. Wraps routes in `ErrorBoundary` |
| `api/types.ts` | TypeScript interfaces matching backend schemas (read + create payloads) |
| `api/http.ts` | Fetch wrappers with 30s timeout (`AbortController`) + `extractErrorMessage()` utility for parsing backend error payloads |
| `api/endpoints.ts` | API client functions for all endpoints |
| `pages/dashboard-page.tsx` | Dashboard con selector de mes, resumen del mes (desglose de cuotas), totales mensuales, timeline de cuotas futuras, gráficos por categoría, filtro por persona |
| `pages/purchases-page.tsx` | Listado de compras con filtros (categoría, fechas, montos, descripción, pagado por, deudor), paginación, edición inline |
| `pages/import-page.tsx` | Importación XLSX, PDF (Banco Nación, MercadoPago) o Google Sheets CSV. Campo de contraseña para PDF protegidos |
| `pages/budget-page.tsx` | Gestión de ingresos por persona/mes y registro de transferencias realizadas (DebtTransfer) |
| `pages/categories-page.tsx` | ABM de categorías con nombre y color |
| `pages/admin-page.tsx` | Entity management — create People, Cards, Debtors, FX Rates |
| `pages/nueva-transferencia-page.tsx` | Destino del Web Share Target (Android): recupera el comprobante compartido y abre `PurchaseForm` pre-llenado con `payment_method: 'transfer'` |
| `utils/sharedFile.ts` | `retrieveSharedFile()` — lee/borra el comprobante que el SW dejó en Cache API |
| `public/manifest.webmanifest` | Manifest PWA con `share_target` (POST `/share-target`, campo `file`) |
| `public/sw.js` | Service worker mínimo: solo intercepta el POST del share target y guarda el archivo en Cache API (no cachea assets) |
| `components/TransferCalculationCard.tsx` | Muestra el resultado de `calculate_transfers` (Fondo Común) para un mes |
| `components/MonthlyBalanceCard.tsx` | Resumen de balance mensual |
| `components/TimelineChart.tsx` | Gráfico de timeline de cuotas futuras |
| `components/CategoryChart.tsx` | Gráfico de gastos por categoría |
| `components/PurchaseForm.tsx` | Formulario reutilizable para crear/editar compras |
| `components/ConfirmDialog.tsx` | Modal de confirmación reutilizable para acciones destructivas |

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
- **Global error handlers** in `main.py`: `IntegrityError` → 409, `ValueError` → 400
- **Basic Auth exemptions** (`PUBLIC_PATHS` in `main.py`): `/health`, `/manifest.webmanifest`, `/sw.js`, `/icons/*`, `/share-target` — Chrome fetchea manifest/íconos sin credenciales; un 401 hace la PWA no instalable
- **SPA fallback**: `SPAStaticFiles` en `main.py` sirve `index.html` para deep links client-side (ej. `/nueva-transferencia`); los 404 de `/api` no se enmascaran
- **DB migrations**: `db.py:_migrate_add_columns()` runs on startup to add columns (`debtor_id`, `debt_settled`, `beneficiary_person_id`) to existing databases. Idempotent via `PRAGMA table_info` check.
- **Manual cascade delete**: `delete_purchase` uses raw SQL to delete children (installments, payers) before parent, because SQLModel doesn't emit `ON DELETE CASCADE` DDL. If new child tables are added, their DELETE must go here too.

## Key Domain Concepts

- **Installments (cuotas)**: Purchases can have N installments. Importing parses "x de y" format. `InstallmentSchedule` entries are auto-generated on purchase creation, one per month.
- **Purchase flags**: `is_common` marks a purchase as shared expense (Fondo Común); `is_refund` marks credit/refund; `debtor_id` links to a `Debtor` entity for third-party debt tracking; `debt_settled` marks debts as resolved. `payment_method` is `card`, `transfer`, or `cash`.
- **Categories**: User-managed via `/categories` page (`Category` table). `auto_categorize_purchases` in `crud.py` applies keyword-based mapping from description → category.
- **Incomes & budgets**: `Income` records per-person per-month income; `MonthlyBudget` records aggregate monthly income with notes. Used by `calculate_transfers` and displayed on the `/budget` page.
- **DebtTransfer**: Records actual money transfers made between people for a month, so the dashboard can show "pending" vs "settled" transfer amounts.
- **FX rates**: USD→ARS exchange rates are entered manually per month via `/admin` page. If missing for a given month, USD installments are excluded from reports (not zero — omitted).
- **Payment split / Transferencias**: El sistema utiliza una lógica de **Fondo Común** (Core Rule). Los ingresos se suman y los gastos comunes se pagan de ese pozo. El dinero sobrante se divide 50/50 entre los participantes. Las transferencias sugeridas buscan que, después de pagar sus gastos personales correspondientes, a ambos les quede exactamente la misma cantidad de "dinero libre" del pozo común. No cambiar esta lógica a menos que se pida explícitamente una re-arquitectura financiera.
- **Deduplication**: Import creates SHA256 fingerprints per row (`ImportedRow`). Re-importing the same file skips already-imported rows.
- **Exclusion heuristic**: Se excluyen pagos, promos, bonificaciones, impuestos (DB.RG 5617, IIBB PERCEP, Impuesto de sellos, Impuesto al sello), "Pago de tarjeta", "Resumen de [mes]". Sí se incluyen devoluciones por compra anulada.

### Importación Google Sheets

`gsheets_importer.py` descarga un CSV público desde una URL de Google Sheets y parsea columnas: `fecha` (YYYY-MM-DD), `tipo`, `monto`, `moneda` (ARS/USD), `descripcion`. Las filas con `monto <= 0` se descartan. Deduplica por fingerprint SHA256 igual que XLSX.

### Import Installment Matching

`_process_installment_row` in `import_api.py` handles re-import of installment rows. It uses `find_existing_purchase_for_installment_import` in `crud.py` with two-pass matching:
1. **Exact match**: normalized description + amount (±0.01 or ±1%)
2. **Fuzzy match**: if exactly ONE candidate matches by date/card/currency/amount (ignoring description), it's returned — supports manually renamed purchases.

If an existing purchase is found, only the missing `InstallmentSchedule` entry is added (no duplicate purchase created).

## Adding a New Import Provider

1. Create `backend/app/importers/<provider>.py` implementing `parse_<provider>(path) -> list[ParsedPurchaseRow]` (o extender `visa_pdf.py` con nuevo formato)
2. Add endpoint in `backend/app/import_api.py`
3. Add UI option in `frontend/src/pages/import-page.tsx`

## Scripts útiles

- **`./start.sh`**: Inicia backend y frontend en paralelo. Crea virtualenv si no existe, instala deps.
- **`examples/validate_pdf.py`**: Valida formato de PDFs. Uso: \`python validate_pdf.py <archivo.pdf> [contraseña] [--debug]\`
- **`scripts/smoke_test.sh`**: Pega los endpoints clave de una instancia corriendo y verifica que respondan 200. Uso: `./scripts/smoke_test.sh` (default `http://localhost:8000`); `BASE_URL=...` para apuntar a prod; `APP_USERNAME=... APP_PASSWORD=...` si tiene Basic Auth.

## Red de seguridad (hooks)

- **Hook `pre-push`** (`.githooks/pre-push`): antes de cada `git push` corre la suite completa — `pytest` (backend) + `vitest` (frontend) + `npm run build` (TypeScript + Vite). Bloquea el push si algo falla.
  - **Instalación (una sola vez por clon):** `git config core.hooksPath .githooks`
  - **Emergencia:** `git push --no-verify` saltea el gate.
  - Se eligió `pre-push` y no `pre-commit` para no frenar el flujo de commits (la suite tarda ~30-40s); el gate corre donde importa: antes de compartir/deployar.

## Core Financial Logic (Fondo Común)

Esta es la regla inamovible para el cálculo de transferencias en `crud.py -> calculate_transfers`:
1. `Sobrante Base` = (Total Ingresos - Total Gastos Comunes) / N (N = personas con ingreso en el mes)
2. `Target Cash Persona A` = Sobrante Base - Gastos Personales Persona A
3. `Lo que Persona A debe pagar` = Ingreso Persona A - Target Cash Persona A
4. `Transferencia` = Lo que Persona A pagó de su bolsillo - Lo que Persona A debe pagar
5. `Ajuste` = DebtTransfers enviados - DebtTransfers recibidos (por persona/mes)
6. `Diferencia final` = (Pagó - Debe pagar) + Ajuste

El objetivo final es que a todos les quede el mismo sobrante base después de gastos comunes, ajustado por sus consumos personales. Ver SPEC.md BR-001 para la fórmula completa.

## Adding New Reports

1. Add query logic in `backend/app/crud.py`
2. Expose endpoint in `backend/app/api.py`
3. Consume from a page component in `frontend/src/pages/`

## Backend Patterns to Follow

- **Upsert pattern**: `upsert_fx_rate` and `create_monthly_budget` check for existing records by logical key before creating. Follow this pattern for new entities with natural uniqueness.
- **Income → Budget sync**: Creating an `Income` auto-recalculates `MonthlyBudget.total_income` for that month via `_update_monthly_budget_from_incomes`. Any new income-like entity should follow this pattern.
- **Category cascade**: Renaming a category cascades to all `Purchase.category` values. Deleting nullifies them. See SPEC.md BR-009, BR-010.
- **FX conversion at query time**: `amount_ars` on `InstallmentSchedule` is always `None`. All ARS conversion happens in report queries using `_fx_rate_map()`. Don't pre-compute `amount_ars`.
- **Person filter allocation**: When filtering reports by `person_id`, amounts are proportionally allocated via `PurchasePayer` shares using `_allocate_amount_to_person`. Don't filter by simple equality.

## Frontend Patterns to Follow

- Use `useQuery` with descriptive `queryKey` arrays (include filter params as last element)
- Use `useMutation` with `onSuccess` that calls `queryClient.invalidateQueries()` for affected queries
- Use `extractErrorMessage()` from `api/http.ts` for all error displays
- Use existing CSS class names from `App.css` — don't introduce new styling systems
- All forms follow the pattern: `useState` for form state, `useMutation` for submission, inline error/success feedback

## Tareas Programadas (Cowork Scheduled Tasks)

Este proyecto tiene tareas automáticas que corren desde **Cowork** (la app de escritorio de Anthropic), usando el Claude Agent SDK. Claude Code puede necesitar leer o modificar estas tareas.

### Ubicación

```
.claude/tasks/          ← archivos de instrucciones de cada tarea
data/gmail_processed_ids.json   ← IDs de emails ya procesados (evita duplicados)
```

### Tarea activa: `gmail-gastos-a-db`

**Archivo:** `.claude/tasks/gmail-gastos-a-db.md`

**Qué hace:** Lee emails no leídos de Gmail (luduenajp@gmail.com), extrae gastos y transferencias bancarias, y los inserta directamente en `data/app.db`.

**Cómo se ejecuta:** Cowork lanza un agente Claude con acceso al MCP de Gmail. El agente lee el archivo de instrucciones y ejecuta todo en Python via bash, usando una copia local de la DB para evitar errores de escritura en el mount FUSE:
1. Copia `data/app.db` a `/tmp/admin_consumos_work.db`
2. Opera sobre la copia
3. Copia de vuelta al path original

**Fuentes de email procesadas:**
- Santander "Pagaste $X" → compra con tarjeta (card_id=1, Pablo)
- Santander "Tu adicional hizo un consumo" → compra (card_id=1, Cintia person_id=2)
- Santander / BNA "Aviso de transferencia" → `payment_method=TRANSFER`
- MercadoPago "Tu transferencia fue enviada" → `payment_method=TRANSFER`

**Emails ignorados:** promociones, resúmenes, transferencias donde el destinatario es el propio Pablo (CUIL 20339576786).

**Anti-duplicación:** doble mecanismo — archivo `gmail_processed_ids.json` (por messageId) + query a la DB por fecha/descripción/monto.

**`first_installment_month`:**
- Compras con tarjeta → mes **siguiente** a la fecha de compra
- Transferencias → **mismo mes** que la fecha de la transferencia

### Si modificás el schema de la DB

Si agregás columnas a `purchase`, `installmentschedule` o `purchasepayer`, actualizá también el archivo `.claude/tasks/gmail-gastos-a-db.md` (sección "Schema" al final) para que la tarea programada no falle.

## Roadmap / Nice To Have (NTH)

Ideas para futuras mejoras que aportarían valor estratégico:

1. **Simulador de Compra (What-if?)**: Vista para previsualizar el impacto de una nueva compra en cuotas sobre la línea de tiempo y el presupuesto mensual antes de realizarla.
2. **Motor de Categorización Inteligente**: Mapeo automático de "Descripción -> Categoría" basado en el historial (ej: "YPF" -> "Combustible").
3. **Proyección de Flujo de Caja (Cash Flow)**: Vista de `Ingresos Estimados - Cuotas Comprometidas` para proyectar el "dinero libre" real de los próximos meses.
4. **Exportación Compartible**: Generación de imagen o PDF simplificado con el resumen de "Transferencias a realizar" para compartir por WhatsApp.
5. **Gestión de Fechas de Tarjeta**: Configurar días de cierre y vencimiento por tarjeta para recibir alertas sobre cuándo conviene comprar (patear cuotas al mes siguiente).
6. **Comprobantes**: Soporte para adjuntar fotos o PDFs de los tickets de compra a cada registro.

# Admin Consumos – Especificaciones y guía de desarrollo

## Resumen del proyecto
App web local para controlar gastos con tarjeta de crédito (vos + tu pareja). Permite importar resúmenes (CSV/XLSX/PDF), modelar cuotas, asignar quién paga, y generar reportes mensuales y proyecciones.

## Stack
- **Backend**: Python 3.11+ + FastAPI + SQLite + SQLModel
- **Frontend**: React 19 + Vite + TypeScript + React Query + CSS custom properties (paleta cálida)
- **Importación**: pandas + openpyxl (XLSX/CSV); PDF en segunda fase
- **Ejecución local**: backend en `http://localhost:8000`, frontend en `http://localhost:5173` (proxy `/api`)

## Decisiones de diseño clave
- **Sin login**: app local, sin autenticación.
- **Moneda**: ARS + USD. Tipo de cambio USD->ARS **manual por mes** (`FxRate`).
- **Cuotas**: se imputa **solo el valor de la cuota del mes** en reportes.
- **Pagadores**: split flexible; por defecto **paga el dueño de la tarjeta**. Shares PERCENT deben sumar 100.
- **Importación**: excluye pagos/promos/ajustes (MVP). Soporta Visa XLSX primero.
- **Conciliación de pagos de tarjeta**: fuera de alcance (solo consumos + proyección).
- **Configuración portable**: DB_PATH y CORS_ORIGINS configurables via variables de entorno (ver `.env.example`).

## Estructura del repo
```
/
├─ backend/
│  ├─ app/
│  │  ├─ api.py          # endpoints CRUD + reportes (ValueError → 400)
│  │  ├─ config.py       # configuración via env vars (DB_PATH, CORS_ORIGINS)
│  │  ├─ crud.py         # lógica de negocio + reportes (transacciones atómicas, validación FK)
│  │  ├─ db.py           # engine + session + init_db + PRAGMA foreign_keys=ON
│  │  ├─ main.py         # FastAPI app + CORS configurable + routers
│  │  ├─ models.py       # SQLModel (tablas) — requiere Python 3.11+ (StrEnum)
│  │  ├─ schemas.py      # Pydantic (validación regex year_month, share_value > 0, model_validator)
│  │  ├─ import_api.py   # endpoint de importación
│  │  ├─ utils_dates.py  # utilidades de fecha (add_months, to_year_month)
│  │  └─ importers/
│  │     └─ visa_xlsx.py # parser para XLSX Visa
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  │  ├─ api/            # cliente HTTP (con timeout 30s) + tipos + endpoints
│  │  ├─ components/     # ErrorBoundary
│  │  ├─ pages/          # dashboard, purchases, import, admin
│  │  ├─ App.tsx         # routing (4 rutas) + ErrorBoundary wrapper
│  │  ├─ App.css         # design system (CSS custom properties, paleta cálida)
│  │  └─ index.css       # variables CSS globales (--color-primary, --color-bg, etc.)
│  └─ package.json
├─ resumenes/            # ejemplos de archivos para importar
├─ spec/                 # esta carpeta (documentación)
├─ .env.example          # referencia de variables de entorno
└─ .gitignore            # excluye .venv/, data/, .env, __pycache__/
```

## Modelo de datos (SQLModel)

### Personas
```python
class Person(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
```

### Tarjetas
```python
class Card(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    provider: str
    owner_person_id: int = Field(foreign_key="person.id")
    last4: str | None = None
```

### Compras
```python
class Purchase(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="card.id")
    purchase_date: date
    description: str
    currency: CurrencyCode  # "ARS" | "USD"
    amount_original: float
    amount_ars: float | None = None
    installments_total: int = Field(default=1)
    installment_amount_original: float | None = None
    first_installment_month: str | None = None  # YYYY-MM (regex validado en schema)
    owner_person_id: int | None = None
    category: str | None = None
    notes: str | None = None
    is_refund: bool = False
```

### Split de pagadores
```python
class PurchasePayer(SQLModel, table=True):
    purchase_id: int = Field(primary_key=True, foreign_key="purchase.id")
    person_id: int = Field(primary_key=True, foreign_key="person.id")
    share_type: ShareType  # "percent" | "fixed"
    share_value: float     # validado > 0 en schema; PERCENT deben sumar 100
```

### Calendario de cuotas (para reportes)
```python
class InstallmentSchedule(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    purchase_id: int = Field(foreign_key="purchase.id")
    year_month: str = Field(index=True)  # YYYY-MM
    installment_index: int
    currency: CurrencyCode
    amount_original: float
    amount_ars: float | None = None
```

### Tipo de cambio USD->ARS (manual por mes)
```python
class FxRate(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    year_month: str = Field(index=True)  # YYYY-MM (regex validado en schema)
    currency: CurrencyCode
    rate_to_ars: float
```

### Trazabilidad de importación (deduplicación)
```python
class ImportedRow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    provider: str = Field(index=True)
    source_file: str
    row_fingerprint: str = Field(unique=True, index=True)
    parsed_payload_json: str
```

## Endpoints públicos (FastAPI)

Base: `http://localhost:8000/api`

### CRUD
- `GET /people` – lista personas
- `POST /people` – crea persona
- `GET /cards` – lista tarjetas
- `POST /cards` – crea tarjeta (valida que owner_person_id exista → 400 si no)
- `GET /purchases?year_month=YYYY-MM` – lista compras (opcional filtro por mes)
- `POST /purchases` – crea compra (valida card_id, owner_person_id, payers existan → 400 si no; genera calendario de cuotas atómicamente)

### Reportes
- `GET /reports/monthly?card_id=...&person_id=...` – totales mensuales en ARS (conversión USD si hay FX)

### FX (USD->ARS manual)
- `GET /fx` – lista FX cargados
- `POST /fx` – upsert FX por mes/moneda (year_month validado con regex YYYY-MM, rate_to_ars > 0)

### Importación
- `POST /import/visa-xlsx?provider=...&card_id=...` – multipart file upload (XLSX)
  - Parsea tabla Fecha/Descripción/Cuotas/Monto en pesos/Monto en dólares
  - Detecta cuotas `"x de y"`
  - Excluye pagos/promos/ajustes y montos <= 0
  - Deduplica por `row_fingerprint`
  - Crea `Purchase` + `InstallmentSchedule` + `PurchasePayer` (por defecto dueño de tarjeta)

### Health
- `GET /health` – devuelve `{"status": "ok"}`

## Flujo de importación (Visa XLSX)

1) Detectar `year_month` del resumen (fila "Fecha de cierre")
2) Encontrar tabla de movimientos (header con "Descripción" y "Monto en pesos")
3) Por cada fila:
   - Parsear fecha, descripción, cuotas (`"x de y"`), montos
   - Si monto <= 0 o descripción empieza con "Su pago", "Promo", "Cr.", etc. → **excluir**
   - Calcular `first_installment_month` a partir de `year_month` y `installment_index`
   - Calcular `amount_original = installment_amount * installments_total`
4) Crear `Purchase` (split por defecto al dueño de la tarjeta)
5) Generar `InstallmentSchedule` para cada cuota
6) Guardar `ImportedRow` con fingerprint para evitar duplicados

## Cómo levantar el proyecto (local)

### Backend
```bash
# Requiere Python 3.11+ (usa StrEnum)
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev  # http://localhost:5173
```

### Primer flujo de prueba (desde la UI)
1. Ir a `/admin` → crear personas (ej: "Pablo", "Cintia")
2. Crear tarjeta (ej: "Visa Santander", asignada a Pablo)
3. Cargar tipo de cambio USD→ARS para el mes del resumen
4. Ir a `/import` → subir el XLSX
5. Ver resultados en `/purchases` y `/` (Dashboard)

## Extensiones futuras (no en MVP)
- Importación PDF (con contraseña)
- Reglas de categorización automática
- Presupuestos y alertas
- Exportación de reportes
- Conciliación de pagos de tarjeta
- Multi-moneda avanzada (con tipo de cambio histórico)
- Adjuntos de comprobantes
- Endpoints PUT/DELETE para editar y borrar entidades
- Alembic para migraciones de DB
- Tests (pytest + Vitest)

## Guía para otros agentes/IDEs

### Agregar un nuevo proveedor de importación
1) Crear `backend/app/importers/<proveedor>.py`
2) Implementar `parse_<proveedor>(path: Path) -> list[ParsedPurchaseRow]`
3) Exponer en `backend/app/import_api.py` un nuevo endpoint
4) Actualizar UI en `frontend/src/pages/import-page.tsx`

### Agregar nuevos reportes
- Agregar queries en `backend/app/crud.py`
- Exponer endpoint en `backend/app/api.py`
- Consumir en `frontend/src/pages/...-page.tsx`

### Agregar nuevas páginas frontend
1) Crear `frontend/src/pages/<nombre>-page.tsx` usando los patrones existentes:
   - `useQuery` con queryKey descriptivo para lectura
   - `useMutation` con `onSuccess` + `queryClient.invalidateQueries()` para escritura
   - `extractErrorMessage()` de `api/http.ts` para errores
   - Clases CSS existentes: `page`, `pageTitle`, `panel`, `panelTitle`, `table`, `formRow`, `label`, `input`, `button`, `error`, `success`, `muted`, `hint`
2) Registrar ruta en `frontend/src/App.tsx` (dentro del `<ErrorBoundary>`)
3) Agregar `<NavLink>` en la nav del header

### Paleta de colores (CSS custom properties)
Las variables están en `frontend/src/index.css`. Para cambiar la paleta, solo modificar las variables `--color-*`. Todos los componentes las consumen vía `App.css`.

### Migraciones de DB
- El `init_db()` actual crea tablas con SQLModel.metadata.create_all.
- Para migraciones futuras: configurar Alembic.

### Integridad de datos
- `db.py` habilita `PRAGMA foreign_keys=ON` — SQLite enforcea FK
- `crud.py` valida existencia de FK antes de crear (Person, Card, payers)
- `schemas.py` valida formato `year_month` con regex, `share_value > 0`, y suma de PERCENT = 100
- `create_purchase` usa `flush()` + `commit()` único para atomicidad

## Notas de implementación
- El frontend usa proxy Vite (`/api` → `http://localhost:8000`) para evitar CORS en desarrollo.
- El importador excluye filas no-consumo según heurística (`_is_excluded_description`).
- Si falta FX de un mes, las cuotas USD **no se suman** en reportes (para evitar totales incorrectos).
- `InstallmentSchedule` se genera automáticamente al crear una compra con cuotas.
- `PurchasePayer` por defecto: 100% al dueño de la tarjeta.
- El frontend tiene timeout de 30s en todas las llamadas API (`AbortController` en `http.ts`).
- React Query configurado con `staleTime: 2min`, `refetchOnWindowFocus: false`.
- `ErrorBoundary` en `App.tsx` previene pantalla blanca en errores de render.
- Cache invalidation automática: importar XLSX invalida queries de purchases y reports.

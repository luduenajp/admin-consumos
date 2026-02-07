# Admin Consumos – Especificaciones y guía de desarrollo

## Resumen del proyecto
App web local para controlar gastos con tarjeta de crédito (vos + tu pareja). Permite importar resúmenes (CSV/XLSX/PDF), modelar cuotas, asignar quién paga, y generar reportes mensuales y proyecciones.

## Stack
- **Backend**: Python + FastAPI + SQLite + SQLModel + Alembic (migraciones)
- **Frontend**: React + Vite + TypeScript + React Query + CSS (sin framework por ahora)
- **Importación**: pandas + openpyxl (XLSX/CSV); PDF en segunda fase
- **Ejecución local**: backend en `http://localhost:8000`, frontend en `http://localhost:5173` (proxy `/api`)

## Decisiones de diseño clave
- **Sin login**: app local, sin autenticación.
- **Moneda**: ARS + USD. Tipo de cambio USD->ARS **manual por mes** (`FxRate`).
- **Cuotas**: se imputa **solo el valor de la cuota del mes** en reportes.
- **Pagadores**: split flexible; por defecto **paga el dueño de la tarjeta**.
- **Importación**: excluye pagos/promos/ajustes (MVP). Soporta Visa XLSX primero.
- **Conciliación de pagos de tarjeta**: fuera de alcance (solo consumos + proyección).

## Estructura del repo
```
/
├─ backend/
│  ├─ app/
│  │  ├─ api.py          # endpoints CRUD + reportes
│  │  ├─ config.py       # paths y URL de SQLite
│  │  ├─ crud.py         # lógica de negocio + reportes
│  │  ├─ db.py          # engine + session + init_db
│  │  ├─ main.py         # FastAPI app + routers
│  │  ├─ models.py       # SQLModel (tablas)
│  │  ├─ schemas.py      # Pydantic (request/response)
│  │  ├─ import_api.py   # endpoint de importación
│  │  └─ importers/
│  │     └─ visa_xlsx.py # parser para XLSX Visa
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  │  ├─ api/           # cliente HTTP + tipos + endpoints
│  │  ├─ pages/         # componentes de página
│  │  └─ App.tsx        # routing + layout
│  └─ package.json
├─ resumenes/           # ejemplos de archivos para importar
└─ spec/               # esta carpeta (documentación)
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
    first_installment_month: str | None = None  # YYYY-MM
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
    share_value: float
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
    year_month: str = Field(index=True)
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
- `POST /cards` – crea tarjeta
- `GET /purchases?year_month=YYYY-MM` – lista compras (opcional filtro por mes)
- `POST /purchases` – crea compra (genera calendario de cuotas)

### Reportes
- `GET /reports/monthly?card_id=...&person_id=...` – totales mensuales en ARS (conversión USD si hay FX)

### FX (USD->ARS manual)
- `GET /fx` – lista FX cargados
- `POST /fx` – upsert FX por mes/moneda

### Importación
- `POST /import/visa-xlsx?provider=...&card_id=...` – multipart file upload (XLSX)
  - Parsea tabla Fecha/Descripción/Cuotas/Monto en pesos/Monto en dólares
  - Detecta cuotas `"x de y"`
  - Excluye pagos/promos/ajustes y montos <= 0
  - Deduplica por `row_fingerprint`
  - Crea `Purchase` + `InstallmentSchedule` + `PurchasePayer` (por defecto dueño de tarjeta)

## Flujo de importación (Visa XLSX)

1) Detectar `year_month` del resumen (fila “Fecha de cierre”)
2) Encontrar tabla de movimientos (header con “Descripción” y “Monto en pesos”)
3) Por cada fila:
   - Parsear fecha, descripción, cuotas (`"x de y"`), montos
   - Si monto <= 0 o descripción empieza con “Su pago”, “Promo”, “Cr.”, etc. → **excluir**
   - Calcular `first_installment_month` a partir de `year_month` y `installment_index`
   - Calcular `amount_original = installment_amount * installments_total`
4) Crear `Purchase` (split por defecto al dueño de la tarjeta)
5) Generar `InstallmentSchedule` para cada cuota
6) Guardar `ImportedRow` con fingerprint para evitar duplicados

## Cómo levantar el proyecto (local)

### Backend
```bash
# Opción A: venv
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --port 8000

# Opción B: conda (si usás)
conda env create -f environment.yml
conda activate admin-consumos
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev  # http://localhost:5173
```

### Primer flujo de prueba (postman/curl)
```bash
# 1) Crear personas
curl -X POST http://localhost:8000/api/people -H 'Content-Type: application/json' -d '{"name":"Pablo"}'
curl -X POST http://localhost:8000/api/people -H 'Content-Type: application/json' -d '{"name":"Cintia"}'

# 2) Crear tarjeta (asignada a Pablo, id 1)
curl -X POST http://localhost:8000/api/cards -H 'Content-Type: application/json' -d '{"name":"Visa Pablo","provider":"santander","owner_person_id":1,"last4":"5623"}'

# 3) Cargar FX (USD->ARS para el mes del resumen)
curl -X POST http://localhost:8000/api/fx -H 'Content-Type: application/json' -d '{"year_month":"2026-01","currency":"USD","rate_to_ars":1200}'

# 4) Importar XLSX (desde UI o curl)
curl -X POST 'http://localhost:8000/api/import/visa-xlsx?provider=santander&card_id=1' -F 'file=@resumenes/pablo-visa-enero.xlsx'
```

## Extensiones futuras (no en MVP)
- Importación PDF (con contraseña: `34247332`)
- Reglas de categorización automática
- Presupuestos y alertas
- Exportación de reportes
- Conciliación de pagos de tarjeta
- Multi-moneda avanzada (con tipo de cambio histórico)
- Adjuntos de comprobantes

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

### Migraciones de DB
- Usar Alembic: `alembic revision --autogenerate -m "msg"` y `alembic upgrade head`
- El `init_db()` actual crea tablas con SQLModel; en prod preferir migraciones.

### Tests
- Backend: pytest + FastAPI TestClient
- Frontend: Vitest + React Testing Library

## Notas de implementación
- El frontend usa proxy Vite (`/api` → `http://localhost:8000`) para evitar CORS.
- El importador excluye filas no-consumo según heurística (`_is_excluded_description`).
- Si falta FX de un mes, las cuotas USD **no se suman** en reportes (para evitar totales incorrectos).
- `InstallmentSchedule` se genera automáticamente al crear una compra con cuotas.
- `PurchasePayer` por defecto: 100% al dueño de la tarjeta.

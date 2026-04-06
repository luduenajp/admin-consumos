# Card Statements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar tabla `CardStatement` que almacena fechas reales de cierre y vencimiento por tarjeta/mes, y usarla para calcular `first_installment_month` correctamente en el formulario y en el gmail task.

**Architecture:** Nueva tabla `CardStatement (card_id, year_month, closing_date, due_date)` con unique constraint en `(card_id, year_month)`. Backend expone 4 endpoints. Frontend auto-sugiere el mes al seleccionar tarjeta. Gmail task consulta la tabla directamente via SQLite para calcular el mes correcto.

**Tech Stack:** SQLModel + FastAPI (backend) · React 19 + React Query (frontend) · SQLite (gmail task)

---

## File Map

| Archivo | Acción | Qué cambia |
|---------|--------|------------|
| `backend/app/models.py` | Modificar | Agregar clase `CardStatement` |
| `backend/app/schemas.py` | Modificar | Agregar `CardStatementCreate`, `CardStatementRead`, `SuggestMonthResponse` |
| `backend/app/crud.py` | Modificar | Agregar 4 funciones de card statements |
| `backend/app/api.py` | Modificar | Registrar 4 endpoints + imports |
| `backend/tests/test_card_statements.py` | Crear | Tests unitarios e integración |
| `frontend/src/api/types.ts` | Modificar | Agregar `CardStatement`, `CardStatementCreate`, `SuggestMonthResponse` |
| `frontend/src/api/endpoints.ts` | Modificar | Agregar 4 funciones fetch |
| `frontend/src/pages/admin-page.tsx` | Modificar | Agregar `CardStatementsSection` |
| `frontend/src/components/PurchaseForm.tsx` | Modificar | Auto-sugerir mes al cambiar tarjeta/fecha |
| `.claude/tasks/gmail-gastos-a-db.md` | Modificar | Corregir `first_installment_month` + categorías |

---

## Task 1: Modelo CardStatement

**Files:**
- Modify: `backend/app/models.py`

- [ ] **Step 1: Agregar el modelo**

En `backend/app/models.py`, agregar el import de `UniqueConstraint` y la clase al final del archivo (antes de cualquier clase que dependa de él, después de `Card`):

```python
# Al inicio del archivo, agregar a los imports existentes:
from sqlalchemy import UniqueConstraint

# Al final del archivo, después de la clase Card:
class CardStatement(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("card_id", "year_month", name="uq_cardstatement_card_month"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="card.id", index=True)
    year_month: str  # YYYY-MM — mes del resumen
    closing_date: date  # fecha exacta de cierre
    due_date: Optional[date] = None  # fecha de vencimiento del pago
```

> Nota: `SQLModel.metadata.create_all(engine)` en `db.py` ya crea tablas nuevas automáticamente al iniciar el servidor. No se necesita migración manual para tablas nuevas.

- [ ] **Step 2: Verificar que el servidor arranca sin errores**

```bash
cd backend && python -c "from app.models import CardStatement; print('OK', CardStatement.__tablename__)"
```
Expected: `OK cardstatement`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models.py
git commit -m "feat: add CardStatement model with unique constraint on (card_id, year_month)"
```

---

## Task 2: Schemas

**Files:**
- Modify: `backend/app/schemas.py`

- [ ] **Step 1: Escribir tests fallidos para validación de schemas**

En `backend/tests/test_card_statements.py` (archivo nuevo):

```python
"""Tests for CardStatement CRUD and suggest-month logic."""
from datetime import date

import pytest

from app.schemas import CardStatementCreate, SuggestMonthResponse


class TestCardStatementSchemas:
    def test_valid_schema(self):
        cs = CardStatementCreate(
            card_id=1,
            year_month="2026-04",
            closing_date=date(2026, 4, 6),
            due_date=date(2026, 4, 28),
        )
        assert cs.card_id == 1
        assert cs.year_month == "2026-04"

    def test_invalid_year_month_format(self):
        with pytest.raises(Exception):
            CardStatementCreate(
                card_id=1,
                year_month="04-2026",  # wrong format
                closing_date=date(2026, 4, 6),
            )

    def test_due_date_optional(self):
        cs = CardStatementCreate(
            card_id=1,
            year_month="2026-04",
            closing_date=date(2026, 4, 6),
        )
        assert cs.due_date is None

    def test_suggest_month_response(self):
        r = SuggestMonthResponse(year_month="2026-04", closing_date=date(2026, 4, 6), fallback=False)
        assert r.year_month == "2026-04"
        assert r.fallback is False

    def test_suggest_month_fallback_has_no_closing_date(self):
        r = SuggestMonthResponse(year_month="2026-05", closing_date=None, fallback=True)
        assert r.closing_date is None
```

- [ ] **Step 2: Correr tests para verificar que fallan**

```bash
cd backend && python -m pytest tests/test_card_statements.py::TestCardStatementSchemas -v
```
Expected: `ImportError` o `ModuleNotFoundError` porque los schemas no existen aún.

- [ ] **Step 3: Agregar los schemas**

En `backend/app/schemas.py`, agregar al final del archivo:

```python
class CardStatementCreate(BaseModel):
    card_id: int
    year_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    closing_date: date
    due_date: Optional[date] = None


class CardStatementRead(BaseModel):
    id: int
    card_id: int
    year_month: str
    closing_date: date
    due_date: Optional[date] = None


class SuggestMonthResponse(BaseModel):
    year_month: str
    closing_date: Optional[date] = None
    fallback: bool
```

- [ ] **Step 4: Correr tests — deben pasar**

```bash
cd backend && python -m pytest tests/test_card_statements.py::TestCardStatementSchemas -v
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_card_statements.py
git commit -m "feat: add CardStatement schemas with year_month validation"
```

---

## Task 3: CRUD functions

**Files:**
- Modify: `backend/app/crud.py`
- Modify: `backend/tests/test_card_statements.py`

- [ ] **Step 1: Agregar tests de CRUD**

Agregar al final de `backend/tests/test_card_statements.py`:

```python
from app.crud import (
    delete_card_statement,
    list_card_statements,
    suggest_first_installment_month,
    upsert_card_statement,
)
from app.models import CardStatement
from app.schemas import CardStatementCreate


class TestCardStatementCRUD:
    def test_upsert_creates_new(self, session, two_person_scenario):
        s = two_person_scenario
        cs = upsert_card_statement(
            session=session,
            payload=CardStatementCreate(
                card_id=s["alice_card"].id,
                year_month="2026-04",
                closing_date=date(2026, 4, 6),
                due_date=date(2026, 4, 28),
            ),
        )
        assert cs.id is not None
        assert cs.closing_date == date(2026, 4, 6)

    def test_upsert_updates_existing(self, session, two_person_scenario):
        s = two_person_scenario
        payload = CardStatementCreate(
            card_id=s["alice_card"].id,
            year_month="2026-04",
            closing_date=date(2026, 4, 6),
        )
        upsert_card_statement(session=session, payload=payload)
        # Upsert again with different closing_date
        updated = upsert_card_statement(
            session=session,
            payload=CardStatementCreate(
                card_id=s["alice_card"].id,
                year_month="2026-04",
                closing_date=date(2026, 4, 8),  # changed
                due_date=date(2026, 4, 30),
            ),
        )
        assert updated.closing_date == date(2026, 4, 8)
        # Only one record exists
        records = list_card_statements(session=session, card_id=s["alice_card"].id)
        assert len(records) == 1

    def test_list_card_statements_ordered(self, session, two_person_scenario):
        s = two_person_scenario
        upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-05",
            closing_date=date(2026, 5, 8),
        ))
        upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-04",
            closing_date=date(2026, 4, 6),
        ))
        records = list_card_statements(session=session, card_id=s["alice_card"].id)
        assert len(records) == 2
        assert records[0].year_month == "2026-04"
        assert records[1].year_month == "2026-05"

    def test_delete_card_statement(self, session, two_person_scenario):
        s = two_person_scenario
        cs = upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-04",
            closing_date=date(2026, 4, 6),
        ))
        delete_card_statement(session=session, statement_id=cs.id)
        records = list_card_statements(session=session, card_id=s["alice_card"].id)
        assert len(records) == 0

    def test_delete_nonexistent_raises(self, session):
        with pytest.raises(ValueError, match="CardStatement 999 not found"):
            delete_card_statement(session=session, statement_id=999)


class TestSuggestFirstInstallmentMonth:
    def test_purchase_before_closing(self, session, two_person_scenario):
        s = two_person_scenario
        upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-04",
            closing_date=date(2026, 4, 6),
        ))
        ym, closing, fallback = suggest_first_installment_month(
            session=session, card_id=s["alice_card"].id, purchase_date=date(2026, 4, 5)
        )
        assert ym == "2026-04"
        assert closing == date(2026, 4, 6)
        assert fallback is False

    def test_purchase_on_closing_day(self, session, two_person_scenario):
        s = two_person_scenario
        upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-04",
            closing_date=date(2026, 4, 6),
        ))
        ym, closing, fallback = suggest_first_installment_month(
            session=session, card_id=s["alice_card"].id, purchase_date=date(2026, 4, 6)
        )
        assert ym == "2026-04"
        assert fallback is False

    def test_purchase_after_closing_uses_next_statement(self, session, two_person_scenario):
        s = two_person_scenario
        upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-04",
            closing_date=date(2026, 4, 6),
        ))
        upsert_card_statement(session=session, payload=CardStatementCreate(
            card_id=s["alice_card"].id, year_month="2026-05",
            closing_date=date(2026, 5, 8),
        ))
        ym, closing, fallback = suggest_first_installment_month(
            session=session, card_id=s["alice_card"].id, purchase_date=date(2026, 4, 7)
        )
        assert ym == "2026-05"
        assert closing == date(2026, 5, 8)
        assert fallback is False

    def test_no_statement_falls_back_to_next_month(self, session, two_person_scenario):
        s = two_person_scenario
        ym, closing, fallback = suggest_first_installment_month(
            session=session, card_id=s["alice_card"].id, purchase_date=date(2026, 4, 5)
        )
        assert ym == "2026-05"
        assert closing is None
        assert fallback is True

    def test_fallback_wraps_december_to_january(self, session, two_person_scenario):
        s = two_person_scenario
        ym, closing, fallback = suggest_first_installment_month(
            session=session, card_id=s["alice_card"].id, purchase_date=date(2026, 12, 15)
        )
        assert ym == "2027-01"
        assert fallback is True
```

- [ ] **Step 2: Correr tests para verificar que fallan**

```bash
cd backend && python -m pytest tests/test_card_statements.py::TestCardStatementCRUD tests/test_card_statements.py::TestSuggestFirstInstallmentMonth -v
```
Expected: `ImportError` — funciones no existen aún.

- [ ] **Step 3: Agregar CardStatement al import de models en crud.py**

En `backend/app/crud.py`, localizar la línea que importa desde `app.models` (cerca del inicio del archivo) y agregar `CardStatement`:

```python
from app.models import (
    # ... modelos existentes ...,
    CardStatement,
)
```

- [ ] **Step 4: Implementar las 4 funciones en crud.py**

Agregar al final de `backend/app/crud.py`, antes de `detect_recurring_expenses`:

```python
def upsert_card_statement(
    *, session: Session, payload: "CardStatementCreate"
) -> CardStatement:
    existing = session.exec(
        select(CardStatement).where(
            CardStatement.card_id == payload.card_id,
            CardStatement.year_month == payload.year_month,
        )
    ).first()

    if existing:
        existing.closing_date = payload.closing_date
        existing.due_date = payload.due_date
        session.add(existing)
    else:
        existing = CardStatement(
            card_id=payload.card_id,
            year_month=payload.year_month,
            closing_date=payload.closing_date,
            due_date=payload.due_date,
        )
        session.add(existing)

    session.commit()
    session.refresh(existing)
    return existing


def list_card_statements(*, session: Session, card_id: int) -> list[CardStatement]:
    return list(
        session.exec(
            select(CardStatement)
            .where(CardStatement.card_id == card_id)
            .order_by(CardStatement.year_month)
        )
    )


def delete_card_statement(*, session: Session, statement_id: int) -> None:
    record = session.get(CardStatement, statement_id)
    if not record:
        raise ValueError(f"CardStatement {statement_id} not found")
    session.delete(record)
    session.commit()


def suggest_first_installment_month(
    *, session: Session, card_id: int, purchase_date: date
) -> tuple[str, date | None, bool]:
    """
    Returns (year_month, closing_date_or_none, is_fallback).
    Finds the nearest CardStatement with closing_date >= purchase_date.
    Falls back to next month if no record exists.
    """
    record = session.exec(
        select(CardStatement)
        .where(
            CardStatement.card_id == card_id,
            CardStatement.closing_date >= purchase_date,
        )
        .order_by(CardStatement.closing_date)
    ).first()

    if record:
        return record.year_month, record.closing_date, False

    # Fallback: next calendar month
    y, m = purchase_date.year, purchase_date.month
    m += 1
    if m > 12:
        m = 1
        y += 1
    return f"{y:04d}-{m:02d}", None, True
```

- [ ] **Step 5: Correr tests — deben pasar**

```bash
cd backend && python -m pytest tests/test_card_statements.py -v
```
Expected: todos los tests pasan.

- [ ] **Step 6: Correr suite completa para verificar que no se rompió nada**

```bash
cd backend && python -m pytest tests/ -q
```
Expected: `0 failed`

- [ ] **Step 7: Commit**

```bash
git add backend/app/crud.py backend/tests/test_card_statements.py
git commit -m "feat: add CardStatement CRUD and suggest_first_installment_month"
```

---

## Task 4: API endpoints

**Files:**
- Modify: `backend/app/api.py`
- Modify: `backend/tests/test_card_statements.py`

- [ ] **Step 1: Agregar tests de integración de la API**

Agregar al final de `backend/tests/test_card_statements.py`:

```python
class TestCardStatementsAPI:
    def test_create_statement(self, client, two_person_scenario):
        s = two_person_scenario
        resp = client.post("/api/card-statements", json={
            "card_id": s["alice_card"].id,
            "year_month": "2026-04",
            "closing_date": "2026-04-06",
            "due_date": "2026-04-28",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["year_month"] == "2026-04"
        assert data["closing_date"] == "2026-04-06"
        assert data["id"] is not None

    def test_upsert_updates_existing(self, client, two_person_scenario):
        s = two_person_scenario
        client.post("/api/card-statements", json={
            "card_id": s["alice_card"].id,
            "year_month": "2026-04",
            "closing_date": "2026-04-06",
        })
        resp = client.post("/api/card-statements", json={
            "card_id": s["alice_card"].id,
            "year_month": "2026-04",
            "closing_date": "2026-04-08",
        })
        assert resp.status_code == 200
        assert resp.json()["closing_date"] == "2026-04-08"

    def test_list_statements(self, client, two_person_scenario):
        s = two_person_scenario
        client.post("/api/card-statements", json={
            "card_id": s["alice_card"].id,
            "year_month": "2026-04",
            "closing_date": "2026-04-06",
        })
        resp = client.get(f"/api/card-statements?card_id={s['alice_card'].id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_delete_statement(self, client, two_person_scenario):
        s = two_person_scenario
        create_resp = client.post("/api/card-statements", json={
            "card_id": s["alice_card"].id,
            "year_month": "2026-04",
            "closing_date": "2026-04-06",
        })
        stmt_id = create_resp.json()["id"]
        del_resp = client.delete(f"/api/card-statements/{stmt_id}")
        assert del_resp.status_code == 204
        list_resp = client.get(f"/api/card-statements?card_id={s['alice_card'].id}")
        assert len(list_resp.json()) == 0

    def test_suggest_month_before_closing(self, client, two_person_scenario):
        s = two_person_scenario
        client.post("/api/card-statements", json={
            "card_id": s["alice_card"].id,
            "year_month": "2026-04",
            "closing_date": "2026-04-06",
        })
        resp = client.get(
            f"/api/card-statements/suggest-month"
            f"?card_id={s['alice_card'].id}&purchase_date=2026-04-05"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["year_month"] == "2026-04"
        assert data["fallback"] is False

    def test_suggest_month_fallback(self, client, two_person_scenario):
        s = two_person_scenario
        resp = client.get(
            f"/api/card-statements/suggest-month"
            f"?card_id={s['alice_card'].id}&purchase_date=2026-04-05"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["year_month"] == "2026-05"
        assert data["fallback"] is True
        assert data["closing_date"] is None
```

- [ ] **Step 2: Correr tests para verificar que fallan**

```bash
cd backend && python -m pytest tests/test_card_statements.py::TestCardStatementsAPI -v
```
Expected: `404 Not Found` — endpoints no existen aún.

- [ ] **Step 3: Registrar imports en api.py**

En `backend/app/api.py`, agregar a la lista de imports de `app.crud`:

```python
from app.crud import (
    # ... imports existentes ...
    delete_card_statement,
    list_card_statements,
    suggest_first_installment_month,
    upsert_card_statement,
)
```

Y agregar a los imports de schemas:

```python
from app.schemas import (
    # ... imports existentes ...
    CardStatementCreate,
    CardStatementRead,
    SuggestMonthResponse,
)
```

- [ ] **Step 4: Agregar los 4 endpoints a api.py**

Agregar al final del archivo `backend/app/api.py`, antes del último bloque si lo hubiera:

```python
# --- Card Statements ---

@router.get("/card-statements/suggest-month", response_model=SuggestMonthResponse)
def get_suggest_month(card_id: int, purchase_date: date) -> SuggestMonthResponse:
    """Suggest first_installment_month based on card closing dates."""
    with get_session() as session:
        ym, closing, fallback = suggest_first_installment_month(
            session=session, card_id=card_id, purchase_date=purchase_date
        )
        return SuggestMonthResponse(year_month=ym, closing_date=closing, fallback=fallback)


@router.get("/card-statements", response_model=list[CardStatementRead])
def get_card_statements(card_id: int) -> list[CardStatementRead]:
    with get_session() as session:
        return list_card_statements(session=session, card_id=card_id)


@router.post("/card-statements", response_model=CardStatementRead)
def post_card_statement(payload: CardStatementCreate) -> CardStatementRead:
    with get_session() as session:
        return upsert_card_statement(session=session, payload=payload)


@router.delete("/card-statements/{statement_id}", status_code=204)
def del_card_statement(statement_id: int) -> Response:
    with get_session() as session:
        try:
            delete_card_statement(session=session, statement_id=statement_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
    return Response(status_code=204)
```

> **Importante:** El endpoint `/card-statements/suggest-month` debe estar definido ANTES de `/card-statements/{statement_id}` en el archivo para evitar que FastAPI interprete "suggest-month" como un `statement_id`.

- [ ] **Step 5: Correr tests — deben pasar**

```bash
cd backend && python -m pytest tests/test_card_statements.py -v
```
Expected: todos los tests pasan.

- [ ] **Step 6: Suite completa**

```bash
cd backend && python -m pytest tests/ -q
```
Expected: `0 failed`

- [ ] **Step 7: Commit**

```bash
git add backend/app/api.py backend/tests/test_card_statements.py
git commit -m "feat: add card-statements API endpoints (CRUD + suggest-month)"
```

---

## Task 5: Frontend — Types y endpoints

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/endpoints.ts`

- [ ] **Step 1: Agregar tipos en types.ts**

En `frontend/src/api/types.ts`, agregar al final del archivo:

```typescript
export interface CardStatement {
  id: number
  card_id: number
  year_month: string
  closing_date: string   // YYYY-MM-DD
  due_date?: string | null
}

export interface CardStatementCreate {
  card_id: number
  year_month: string
  closing_date: string
  due_date?: string | null
}

export interface SuggestMonthResponse {
  year_month: string
  closing_date: string | null
  fallback: boolean
}
```

- [ ] **Step 2: Agregar funciones fetch en endpoints.ts**

En `frontend/src/api/endpoints.ts`, agregar el import de los tipos nuevos al bloque existente:

```typescript
import type {
  // ... imports existentes ...
  CardStatement,
  CardStatementCreate,
  SuggestMonthResponse,
} from './types'
```

Y agregar las funciones al final del archivo:

```typescript
export function fetchCardStatements(cardId: number): Promise<CardStatement[]> {
  return getJson<CardStatement[]>(`/api/card-statements?card_id=${cardId}`)
}

export function upsertCardStatement(payload: CardStatementCreate): Promise<CardStatement> {
  return postJson<CardStatement>('/api/card-statements', payload)
}

export function deleteCardStatement(id: number): Promise<void> {
  return deleteHttp(`/api/card-statements/${id}`)
}

export function fetchSuggestMonth(cardId: number, purchaseDate: string): Promise<SuggestMonthResponse> {
  return getJson<SuggestMonthResponse>(
    `/api/card-statements/suggest-month?card_id=${cardId}&purchase_date=${purchaseDate}`
  )
}
```

- [ ] **Step 3: Verificar que TypeScript compila**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error|TS"
```
Expected: sin errores de TypeScript.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/endpoints.ts
git commit -m "feat: add CardStatement types and fetch functions"
```

---

## Task 6: Admin page — Sección CardStatements

**Files:**
- Modify: `frontend/src/pages/admin-page.tsx`

- [ ] **Step 1: Agregar la sección CardStatementsSection**

En `frontend/src/pages/admin-page.tsx`, agregar los imports necesarios al bloque existente:

```typescript
import {
  // ... imports existentes ...
  fetchCardStatements,
  upsertCardStatement,
  deleteCardStatement,
} from '../api/endpoints'
import type {
  // ... imports existentes ...
  CardStatement,
  CardStatementCreate,
} from '../api/types'
```

Agregar el componente `CardStatementsSection` antes de la función `AdminPage`:

```typescript
function CardStatementsSection() {
  const queryClient = useQueryClient()
  const [selectedCardId, setSelectedCardId] = useState<string>('')
  const [form, setForm] = useState({ year_month: '', closing_date: '', due_date: '' })
  const [error, setError] = useState('')

  const cardsQuery = useQuery({ queryKey: ['cards'], queryFn: fetchCards })
  const cards = cardsQuery.data ?? []

  const statementsQuery = useQuery({
    queryKey: ['card-statements', selectedCardId],
    queryFn: () => fetchCardStatements(Number(selectedCardId)),
    enabled: !!selectedCardId,
  })
  const statements = statementsQuery.data ?? []

  const upsertMutation = useMutation({
    mutationFn: (payload: CardStatementCreate) => upsertCardStatement(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['card-statements', selectedCardId] })
      setForm({ year_month: '', closing_date: '', due_date: '' })
      setError('')
    },
    onError: (e) => setError(extractErrorMessage(e)),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteCardStatement(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['card-statements', selectedCardId] }),
  })

  const handleSubmit = () => {
    if (!selectedCardId || !form.year_month || !form.closing_date) {
      setError('Tarjeta, mes y fecha de cierre son obligatorios')
      return
    }
    upsertMutation.mutate({
      card_id: Number(selectedCardId),
      year_month: form.year_month,
      closing_date: form.closing_date,
      due_date: form.due_date || null,
    })
  }

  return (
    <div className="panel">
      <div className="panelTitle">Fechas de Resumen por Tarjeta</div>

      <div className="formRow">
        <label className="label">Tarjeta</label>
        <select
          className="input"
          value={selectedCardId}
          onChange={(e) => setSelectedCardId(e.target.value)}
        >
          <option value="">Seleccionar tarjeta...</option>
          {cards.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>

      {selectedCardId && (
        <>
          {statements.length === 0 ? (
            <div className="muted" style={{ marginBottom: '16px' }}>Sin fechas cargadas para esta tarjeta</div>
          ) : (
            <table className="table" style={{ marginBottom: '16px' }}>
              <thead>
                <tr>
                  <th>Mes</th>
                  <th>Cierre</th>
                  <th>Vencimiento</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {statements.map((s) => (
                  <tr key={s.id}>
                    <td>{s.year_month}</td>
                    <td>{s.closing_date}</td>
                    <td>{s.due_date ?? '—'}</td>
                    <td>
                      <button
                        className="button"
                        style={{ background: 'var(--color-error, #dc2626)', padding: '4px 10px', fontSize: '12px' }}
                        onClick={() => deleteMutation.mutate(s.id)}
                        type="button"
                      >
                        Eliminar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div className="formRow" style={{ flex: 1, minWidth: '120px', marginBottom: 0 }}>
              <label className="label">Mes (YYYY-MM)</label>
              <input
                type="month"
                className="input"
                value={form.year_month}
                onChange={(e) => setForm({ ...form, year_month: e.target.value })}
              />
            </div>
            <div className="formRow" style={{ flex: 1, minWidth: '140px', marginBottom: 0 }}>
              <label className="label">Fecha de Cierre</label>
              <input
                type="date"
                className="input"
                value={form.closing_date}
                onChange={(e) => setForm({ ...form, closing_date: e.target.value })}
              />
            </div>
            <div className="formRow" style={{ flex: 1, minWidth: '140px', marginBottom: 0 }}>
              <label className="label">Vencimiento (opcional)</label>
              <input
                type="date"
                className="input"
                value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })}
              />
            </div>
            <button
              className="button"
              style={{ height: '42px' }}
              disabled={upsertMutation.isPending}
              onClick={handleSubmit}
              type="button"
            >
              Guardar
            </button>
          </div>
          {error && <div className="error" style={{ marginTop: '8px' }}>{error}</div>}
        </>
      )}
    </div>
  )
}
```

Agregar `<CardStatementsSection />` al return de `AdminPage`, después de la sección de tarjetas (CardsSection):

```typescript
export function AdminPage() {
  return (
    <div className="page">
      <div className="pageTitle">Administración</div>
      <PeopleSection />
      <CardsSection />
      <CardStatementsSection />   {/* ← agregar aquí */}
      <DebtorsSection />
      <FxRatesSection />
    </div>
  )
}
```

- [ ] **Step 2: Verificar que TypeScript compila**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error|TS"
```
Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin-page.tsx
git commit -m "feat: add CardStatements management section to admin page"
```

---

## Task 7: PurchaseForm — Auto-sugerencia de mes

**Files:**
- Modify: `frontend/src/components/PurchaseForm.tsx`

- [ ] **Step 1: Agregar import de fetchSuggestMonth y SuggestMonthResponse**

En la sección de imports de `frontend/src/components/PurchaseForm.tsx`:

```typescript
import {
    fetchCards,
    fetchPeople,
    fetchDebtors,
    fetchCategories,
    createPurchase,
    fetchSuggestMonth,   // ← agregar
} from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import type { CurrencyCode, PaymentMethod, PurchaseCreate, Category, SuggestMonthResponse } from '../api/types'  // ← agregar SuggestMonthResponse
```

- [ ] **Step 2: Agregar query de sugerencia y useEffect que actualiza el form**

Después de la línea que define `const { data: categories = [] }`, agregar:

```typescript
    // Suggest first_installment_month based on card closing dates
    const suggestQuery = useQuery<SuggestMonthResponse>({
        queryKey: ['suggest-month', formData.card_id, formData.purchase_date],
        queryFn: () => fetchSuggestMonth(Number(formData.card_id), formData.purchase_date),
        enabled: formData.payment_method === 'card' && !!formData.card_id,
        staleTime: 0,
    })

    // When suggestion changes, update first_installment_month automatically
    useEffect(() => {
        if (suggestQuery.data) {
            setFormData(prev => ({ ...prev, first_installment_month: suggestQuery.data!.year_month }))
        }
    }, [suggestQuery.data?.year_month])
```

- [ ] **Step 3: Reemplazar el useEffect de payment_method**

Localizar el `useEffect` que escucha `formData.payment_method` (líneas ~47-63) y reemplazarlo:

```typescript
    // Update first_installment_month when payment_method changes
    useEffect(() => {
        if (formData.payment_method === 'card') {
            // Default to next month; suggestQuery overrides this once a card is selected
            setFormData(prev => ({
                ...prev,
                first_installment_month: getRelativeMonth(1)
            }))
        } else {
            setFormData(prev => ({
                ...prev,
                first_installment_month: getRelativeMonth(0),
                card_id: '',
                installments_total: '1'
            }))
            setAmountInputMode('total')
        }
    }, [formData.payment_method])
```

- [ ] **Step 4: Agregar hint debajo del campo "Mes primer cuota"**

Localizar el `<div className="formRow">` que contiene el `input type="month"` para `first_installment_month` y agregar el hint después del input:

```typescript
                <div className="formRow">
                    <label className="label">Mes primer cuota</label>
                    <input
                        type="month"
                        className="input"
                        disabled={formData.payment_method !== 'card'}
                        value={formData.first_installment_month}
                        onChange={(e) => setFormData({ ...formData, first_installment_month: e.target.value })}
                        style={{ opacity: formData.payment_method === 'card' ? 1 : 0.5 }}
                    />
                    {formData.payment_method === 'card' && formData.card_id && (
                        <div className="hint">
                            {suggestQuery.isLoading
                                ? 'Calculando...'
                                : suggestQuery.data?.fallback
                                    ? 'Sin datos de cierre — asumiendo mes siguiente'
                                    : `Cierre ${suggestQuery.data?.closing_date} → entra en ${suggestQuery.data?.year_month}`
                            }
                        </div>
                    )}
                </div>
```

- [ ] **Step 5: Verificar que TypeScript compila**

```bash
cd frontend && npm run build 2>&1 | grep -E "error|Error|TS"
```
Expected: sin errores.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/PurchaseForm.tsx
git commit -m "feat: auto-suggest first_installment_month in PurchaseForm based on card closing date"
```

---

## Task 8: Gmail task — Actualizar first_installment_month y categorías

**Files:**
- Modify: `.claude/tasks/gmail-gastos-a-db.md`

- [ ] **Step 1: Agregar función `suggest_first_installment_month` al paso 3**

En la sección **"Paso 3 — Insertar en la base de datos"**, agregar la función helper después del bloque de deduplicación:

````markdown
**Calcular primer mes de cuota:**
```python
def suggest_first_installment_month(cur, card_id, purchase_date_str):
    """Usa CardStatement para calcular el mes correcto. Fallback: mes siguiente."""
    cur.execute(
        '''SELECT year_month FROM cardstatement
           WHERE card_id=? AND closing_date >= ?
           ORDER BY closing_date ASC LIMIT 1''',
        (card_id, purchase_date_str)
    )
    row = cur.fetchone()
    if row:
        return row[0]
    # Fallback: mes siguiente
    y, m = map(int, purchase_date_str[:7].split('-'))
    m += 1
    if m > 12:
        m = 1
        y += 1
    return f'{y:04d}-{m:02d}'
```
````

- [ ] **Step 2: Reemplazar la línea de first_installment_month en compras con tarjeta**

En la sección **"Paso 2 — Mapear datos"**, localizar:

```
- `first_installment_month` = mes siguiente a purchase_date en formato YYYY-MM
```

Reemplazarlo con:

```
- `first_installment_month` = `suggest_first_installment_month(cur, card_id, purchase_date)` — usa la tabla `cardstatement`; si no hay datos cargados, fallback al mes siguiente
```

- [ ] **Step 3: Corregir categorías desactualizadas**

En la sección **"Paso 2 — Mapear datos"**, localizar el bloque de mapeo de categorías para compras con tarjeta y reemplazar:

```markdown
- `category` según descripción:
  - EPEC, AguasCordobesas, ECOGAS, Personal, Claro, PAGOS360* → 'Servicios'
  - SEGUROS RIVADAVIA, ADT, BINA SEGUROS, CHUBB, CHUBBTES → 'Seguros'
  - RENTAS, TACATACA*RENTAS, AFIP, CORDOBA.GOB, vep → 'Impuestos'
  - YPF, SHELL, SHELLBOX, AXION, combustib, APPYPF → 'Combustible'
  - LIBERTAD, WALMART, DISCO, supermercado → 'Supermercado'
  - restaurante, café, confitería, GRIDO, PANINO, MARACUYA → 'Restaurantes'
  - NETFLIX, YouTube, AUTOENTRADA, CINE → 'Entretenimiento'
  - Todo lo demás → 'Varios'
```

Y para transferencias cambiar:
```
  - Nancy Beatriz Videla → 'Servicios'; resto → 'Varios'
```

- [ ] **Step 4: Agregar nota en "Datos de referencia" sobre cardstatement**

En la sección **"Datos de referencia"**, agregar:

```markdown
**Tabla cardstatement:** `card_id, year_month (YYYY-MM), closing_date (DATE), due_date (DATE nullable)` — usar para calcular `first_installment_month` via `suggest_first_installment_month()`
```

- [ ] **Step 5: Commit**

```bash
git add .claude/tasks/gmail-gastos-a-db.md
git commit -m "feat: update gmail task to use CardStatement for first_installment_month and fix category names"
```

---

## Task 9: Verificación final

- [ ] **Step 1: Suite completa backend**

```bash
cd /Users/pablo/github/admin-consumos && source .venv/bin/activate && cd backend && python -m pytest tests/ -q
```
Expected: `0 failed`

- [ ] **Step 2: Build frontend limpio**

```bash
cd /Users/pablo/github/admin-consumos/frontend && npm run build
```
Expected: sin errores TypeScript.

- [ ] **Step 3: Cargar datos de prueba para Master MP Pablo**

Con el servidor corriendo (`./start.sh`), llamar a la API para cargar el cierre del mes actual:

```bash
curl -X POST http://localhost:8000/api/card-statements \
  -H "Content-Type: application/json" \
  -d '{"card_id": 4, "year_month": "2026-04", "closing_date": "2026-04-06", "due_date": null}'
```
Expected: `{"id": 1, "card_id": 4, "year_month": "2026-04", "closing_date": "2026-04-06", ...}`

- [ ] **Step 4: Verificar suggest-month**

```bash
curl "http://localhost:8000/api/card-statements/suggest-month?card_id=4&purchase_date=2026-04-05"
```
Expected: `{"year_month": "2026-04", "closing_date": "2026-04-06", "fallback": false}`

- [ ] **Step 5: Commit final**

```bash
git add -A
git commit -m "feat: card statements — add closing date data for Master MP Pablo"
```

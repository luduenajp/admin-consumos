# Endpoints – API Reference

Base URL: `http://localhost:8000/api`

## Personas

### GET /people
Lista todas las personas.

**Response**
```json
[
  {"id": 1, "name": "Pablo"},
  {"id": 2, "name": "Cintia"}
]
```

### POST /people
Crea una persona.

**Body**
```json
{"name": "Pablo"}
```

**Response**
```json
{"id": 1, "name": "Pablo"}
```

---

## Tarjetas

### GET /cards
Lista todas las tarjetas.

**Response**
```json
[
  {
    "id": 1,
    "name": "Visa Pablo",
    "provider": "santander",
    "owner_person_id": 1,
    "last4": "5623"
  }
]
```

### POST /cards
Crea una tarjeta.

**Body**
```json
{
  "name": "Visa Pablo",
  "provider": "santander",
  "owner_person_id": 1,
  "last4": "5623"
}
```

**Response**
```json
{
  "id": 1,
  "name": "Visa Pablo",
  "provider": "santander",
  "owner_person_id": 1,
  "last4": "5623"
}
```

---

## Compras

### GET /purchases?year_month=YYYY-MM&person_id=...&card_id=...&...
Lista compras. Parámetros opcionales:
- `year_month`: mes formato `YYYY-MM`
- `person_id`: filtrar por persona que pagó (join con PurchasePayer)
- `card_id`, `category`, `min_amount`, `max_amount`, `description`, `debtor_person_id`, etc.

**Response**
```json
[
  {
    "id": 1,
    "card_id": 1,
    "purchase_date": "2026-01-23",
    "description": "Veterinaria alem joc",
    "currency": "ARS",
    "amount_original": 14066.66,
    "installments_total": 3,
    "installment_amount_original": 4688.88,
    "first_installment_month": "2025-11",
    "owner_person_id": 1,
    "category": null,
    "notes": null,
    "is_refund": false
  }
]
```

### POST /purchases
Crea una compra (genera calendario de cuotas y split por defecto al dueño de la tarjeta).

**Body**
```json
{
  "card_id": 1,
  "purchase_date": "2026-01-23",
  "description": "Veterinaria alem joc",
  "currency": "ARS",
  "amount_original": 14066.66,
  "installments_total": 3,
  "installment_amount_original": 4688.88,
  "first_installment_month": "2025-11",
  "owner_person_id": 1,
  "category": null,
  "notes": null,
  "is_refund": false,
  "payers": null
}
```

**Response**
```json
{
  "id": 1,
  "card_id": 1,
  "purchase_date": "2026-01-23",
  "description": "Veterinaria alem joc",
  "currency": "ARS",
  "amount_original": 14066.66,
  "installments_total": 3,
  "installment_amount_original": 4688.88,
  "first_installment_month": "2025-11",
  "owner_person_id": 1,
  "category": null,
  "notes": null,
  "is_refund": false
}
```

---

## Reportes

### GET /reports/monthly?card_id=...&person_id=...
Totales mensuales en ARS (conversión USD si hay FX). Filtros opcionales por tarjeta y/o persona.

**Response**
```json
[
  {"year_month": "2025-11", "total_ars": 4688.88},
  {"year_month": "2025-12", "total_ars": 4688.88},
  {"year_month": "2026-01", "total_ars": 4688.88}
]
```

### GET /reports/month-breakdown?year_month=YYYY-MM&person_id=...&card_id=...
Desglose de cuotas por mes. Lista de compras con sus cuotas que caen en el mes indicado.

**Query params**
- `year_month`: obligatorio, formato `YYYY-MM`
- `person_id`, `card_id`: opcionales

**Response**
```json
{
  "year_month": "2026-02",
  "total_ars": 125000.50,
  "rows": [
    {
      "purchase_id": 1,
      "purchase_date": "2026-01-15",
      "description": "Supermercado",
      "category": "Alimentos",
      "installment_index": 1,
      "installments_total": 3,
      "amount_ars": 45000.00
    }
  ]
}
```

### GET /reports/timeline?person_id=...&card_id=...
Timeline de cuotas futuras por mes (para gráfico de barras).

### GET /reports/category-spending?year_month=...&person_id=...&card_id=...
Gasto por categoría (para gráfico de torta).

### GET /reports/debts?person_id=...
Resumen de deudas entre personas (quién debe a quién).

---

## Tipo de cambio (FX)

### GET /fx
Lista todos los FX cargados.

**Response**
```json
[
  {"id": 1, "year_month": "2026-01", "currency": "USD", "rate_to_ars": 1200.0}
]
```

### POST /fx
Crea o actualiza un FX por mes/moneda.

**Body**
```json
{
  "year_month": "2026-01",
  "currency": "USD",
  "rate_to_ars": 1200.0
}
```

**Response**
```json
{
  "id": 1,
  "year_month": "2026-01",
  "currency": "USD",
  "rate_to_ars": 1200.0
}
```

---

## Importación

### POST /import/visa-xlsx?provider=...&card_id=...
Importa un archivo XLSX de Visa (multipart). Excluye pagos/promos/ajustes y deduplica.

**Query params**
- `provider`: string (ej. `santander`)
- `card_id`: int

**Body (multipart)**
- `file`: File (XLSX)

**Response**
```json
{
  "created": 12,
  "skipped": 0,
  "parsed": 12
}
```

### POST /import/visa-pdf?provider=...&card_id=...
Importa un PDF de resumen (Banco Nación Visa/Mastercard, MercadoPago).

**Query params**
- `provider`: string (ej. `banco_nacion`)
- `card_id`: int

**Body (multipart)**
- `file`: File (PDF)
- `password`: string (opcional, para PDFs protegidos)

**Response**
```json
{
  "created": 8,
  "skipped": 2,
  "parsed": 10
}
```

---

## Health

### GET /health
Estado del servicio.

**Response**
```json
{"status": "ok"}
```

# Diagrama Entidad-Relación - Admin Consumos

## Entidades Principales

```
┌─────────────────┐       ┌─────────────────┐
│     PERSON      │       │      CARD       │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │◄──────┤ id (PK)         │
│ name            │       │ name            │
│                 │       │ provider        │
│                 │       │ owner_person_id │
│                 │       │ last4           │
└─────────────────┘       └─────────────────┘
         │                           │
         │                           │
         │              ┌────────────┴─────────────┐
         │              │                          │
         │              ▼                          ▼
         │      ┌─────────────────┐       ┌─────────────────┐
         │      │    PURCHASE     │       │  PURCHASEPAYER  │
         │      ├─────────────────┤       ├─────────────────┤
         │      │ id (PK)         │◄─────┤ purchase_id (PK)│
         │      │ card_id (FK)    │       │ person_id (PK) │
         │      │ purchase_date   │       │ share_type      │
         │      │ description     │       │ share_value     │
         │      │ currency        │       └─────────────────┘
         │      │ amount_original │
         │      │ amount_ars      │
         │      │ installments_   │
         │      │ total           │
         │      │ installment_    │
         │      │ amount_original │
         │      │ first_install-  │
         │      │ ment_month      │
         │      │ owner_person_id │
         │      │ category        │
         │      │ notes           │
         │      │ is_refund       │
         │      │ debtor_id       │
         │      │ debt_settled    │
         │      └─────────────────┘
         │              │
         │              │
         │              ▼
         │      ┌─────────────────┐
         │      │INSTALLMENT SCHED │
         │      ├─────────────────┤
         │      │ id (PK)         │
         │      │ purchase_id (FK)│
         │      │ year_month      │
         │      │ installment_idx │
         │      │ currency        │
         │      │ amount_original │
         │      │ amount_ars      │
         │      └─────────────────┘
```

## Entidades Auxiliares

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     DEBTOR      │       │     FXRATE      │       │  IMPORTEDROW   │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)        │
│ name            │       │ year_month      │       │ provider        │
│                 │       │ currency        │       │ source_file     │
│                 │       │ rate_to_ars     │       │ row_fingerprint │
│                 │       │                 │       │ parsed_payload  │
└─────────────────┘       └─────────────────┘       └─────────────────┘
         ▲                                           ▲
         │                                           │
         │                                           │
         │                           ┌───────────────┴───────────────┐
         │                           │                               │
         │                           ▼                               ▼
         │                   ┌─────────────────┐           ┌─────────────────┐
         │                   │    PURCHASE     │           │    PURCHASE     │
         │                   │ (debtor_id FK)  │           │ (imports)       │
         │                   └─────────────────┘           └─────────────────┘
```

## Relaciones y Cardinalidad

### Relaciones Principales
- **PERSON → CARD**: 1:N (una persona puede tener muchas tarjetas)
- **CARD → PURCHASE**: 1:N (una tarjeta tiene muchas compras)
- **PERSON → PURCHASE**: 1:N (dueño de la compra)
- **PURCHASE → INSTALLMENT SCHEDULE**: 1:N (una compra tiene muchas cuotas)
- **PURCHASE → PURCHASEPAYER**: 1:N (una compra puede tener múltiples pagadores)

### Relaciones Auxiliares
- **DEBTOR → PURCHASE**: 1:N (un deudor puede tener muchas compras)
- **FXRATE**: Entidad independiente (tasas de cambio por mes/moneda)
- **IMPORTEDROW**: Control de duplicados por fingerprint único

## Índices Principales

```sql
-- Rendimiento de consultas
ix_purchase_card_id
ix_purchase_purchase_date
ix_purchase_category
ix_installmentschedule_year_month
ix_importedrow_row_fingerprint (UNIQUE)
```

## Flujo de Datos

1. **Importación**: `IMPORTEDROW` → `PURCHASE` → `INSTALLMENT SCHEDULE`
2. **Consultas**: `INSTALLMENT SCHEDULE` ← `PURCHASE` ← `CARD` ← `PERSON`
3. **Pagadores**: `PURCHASEPAYER` conecta `PURCHASE` con `PERSON`
4. **Deudas**: `DEBTOR` se asocia a `PURCHASE`

## Características Clave

- **Prevención de duplicados**: `IMPORTEDROW.row_fingerprint` UNIQUE
- **Sistema de cuotas**: `INSTALLMENT SCHEDULE` separado de `PURCHASE`
- **Pagos compartidos**: `PURCHASEPAYER` permite múltiples pagadores
- **Conversiones de moneda**: `FXRATE` por mes y tipo de moneda
- **Gestión de deudas**: `DEBTOR` + `debt_settled` en `PURCHASE`

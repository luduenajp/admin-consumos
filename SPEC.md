# Software Specification Document (SDD)

**Project:** Admin Consumos
**Version:** 1.0
**Last Updated:** 2026-03-14

---

## 1. Overview

Admin Consumos is a local-only, single-user web application for managing household credit card expenses with installment (cuota) tracking, multi-person payment splitting, and monthly financial reports with USD→ARS conversion.

### 1.1 Glossary

| Term | Definition |
|---|---|
| **Cuota** (Installment) | One monthly payment of a multi-installment purchase. A purchase of 12 cuotas generates 12 `InstallmentSchedule` entries. |
| **Fondo Común** (Common Pool) | Financial model where all incomes are pooled, common expenses are deducted, and the remainder is split equally. See BR-001. |
| **Payer** (`PurchasePayer`) | The person who actually paid for a purchase. Defaults to the card owner (100%). Can be split among multiple people. |
| **Beneficiary** (`beneficiary_person_id`) | The person who benefits from a purchase. Used in transfer calculations to attribute personal expenses. Overrides the payer for expense attribution. |
| **Owner** (`owner_person_id`) | The person who owns the expense record. For card purchases, defaults to the card's `owner_person_id`. |
| **Debtor** | A third-party (non-household member) who owes money for a purchase made on their behalf. Tracked via `debtor_id`. |
| **Statement Month** (`statement_year_month`) | The billing cycle month from the bank statement. Format: `YYYY-MM`. |
| **FX Rate** | Exchange rate from a foreign currency (USD) to ARS for a specific month. |
| **is_common** | Boolean flag marking a purchase as a shared/common expense included in the Fondo Común calculation. |
| **is_refund** | Boolean flag marking a purchase as a credit/refund. |
| **Fingerprint** | SHA256 hash used for import deduplication. Computed from provider, card_id, and row fields. |

---

## 2. Data Model

### 2.1 Enums

| Enum | Values | Usage |
|---|---|---|
| `CurrencyCode` | `ARS`, `USD` | Currency of a purchase or FX rate |
| `ShareType` | `percent`, `fixed` | How a payer's share is calculated |
| `PaymentMethod` | `card`, `transfer`, `cash` | How a purchase was paid |

### 2.2 Entities (12 tables)

#### Person
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `name` | str | required |

#### Card
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `name` | str | required |
| `provider` | str | required |
| `owner_person_id` | int | FK → `person.id`, required |
| `last4` | str? | optional, last 4 digits |

#### Debtor
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `name` | str | required |

#### Category
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `name` | str | required, unique, indexed |
| `color` | str? | optional, CSS color |

#### FxRate
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `year_month` | str | indexed, format `YYYY-MM` |
| `currency` | CurrencyCode | indexed |
| `rate_to_ars` | float | required |

Unique constraint: logical (year_month, currency) — enforced via upsert logic (BR-023).

#### Purchase
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `card_id` | int? | FK → `card.id`, indexed. Required if `payment_method == CARD` (BR-015) |
| `payment_method` | PaymentMethod | default `CARD`, indexed |
| `purchase_date` | date | required, indexed |
| `description` | str | required |
| `currency` | CurrencyCode | required, indexed |
| `amount_original` | float | required, total purchase amount |
| `amount_ars` | float? | currently unused (conversion happens at query time) |
| `installments_total` | int | default 1, ≥ 1 |
| `installment_amount_original` | float? | per-installment amount (computed if not provided) |
| `first_installment_month` | str? | `YYYY-MM`, defaults to purchase_date month |
| `owner_person_id` | int? | FK → `person.id` |
| `beneficiary_person_id` | int? | FK → `person.id`, indexed |
| `category` | str? | free-text, indexed |
| `notes` | str? | optional |
| `is_refund` | bool | default false |
| `is_common` | bool | default false |
| `debtor_id` | int? | FK → `debtor.id`, indexed |
| `debt_settled` | bool | default false |

#### PurchasePayer
| Field | Type | Constraints |
|---|---|---|
| `purchase_id` | int | PK, FK → `purchase.id` |
| `person_id` | int | PK, FK → `person.id` |
| `share_type` | ShareType | required |
| `share_value` | float | required, > 0 |

Composite PK: (`purchase_id`, `person_id`).

#### InstallmentSchedule
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `purchase_id` | int | FK → `purchase.id`, indexed |
| `year_month` | str | indexed, `YYYY-MM` |
| `installment_index` | int | 1-based |
| `currency` | CurrencyCode | required |
| `amount_original` | float | per-installment amount |
| `amount_ars` | float? | currently unused |

#### ImportedRow
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `provider` | str | indexed |
| `source_file` | str | required |
| `row_fingerprint` | str | indexed, unique |
| `parsed_payload_json` | str | JSON blob of parsed row data |

#### MonthlyBudget
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `year_month` | str | unique, indexed, `YYYY-MM` |
| `total_income` | float | required |
| `notes` | str? | optional |

#### Income
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `person_id` | int | FK → `person.id`, indexed |
| `year_month` | str | indexed, `YYYY-MM` |
| `amount` | float | required |
| `notes` | str? | optional |

Multiple incomes per person per month are allowed.

#### DebtTransfer
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `from_person_id` | int | FK → `person.id`, indexed |
| `to_person_id` | int | FK → `person.id`, indexed |
| `year_month` | str | indexed, `YYYY-MM` |
| `amount` | float | required |
| `transfer_date` | date | default today |
| `notes` | str? | optional |

---

## 3. Business Rules

### BR-001: Fondo Común Algorithm (Transfer Calculation)

The core financial logic for `calculate_transfers`:

1. **Inputs:** All `Income` records for the month, all `InstallmentSchedule` entries for the month joined with their `Purchase`.
2. **Classify expenses:** Each installment is classified as either *common* (`is_common == true`) or *personal*. Personal expenses are attributed to `beneficiary_person_id` if set, otherwise to `owner_person_id` or `card.owner_person_id`.
3. **Target Base Take-Home** = `(Total Incomes − Total Common Expenses) / N` where N = number of people with income for that month.
4. **Target Cash per Person** = `Target Base Take-Home − Personal Expenses for that Person`.
5. **Should Pay per Person** = `Income − Target Cash`.
6. **Paid Amount per Person:** Sum of installment amounts allocated via `PurchasePayer` shares; if no payers exist, 100% goes to `owner_person_id` or `card.owner_person_id`.
7. **Difference** = `(Paid − Should Pay) + Adjustment` where Adjustment = `Sent DebtTransfers − Received DebtTransfers` for the month.
8. **Transfers:** People with `difference < 0` (underpaid) transfer to people with `difference > 0` (overpaid).
9. **is_balanced** = `true` if `|sum of all differences| ≤ 0.01`.

### BR-002: FX Missing = Skip

When converting USD installments to ARS: if no `FxRate` record exists for `(year_month, currency)`, the installment is **skipped** (excluded from totals), not treated as zero. This applies to all report queries: monthly totals, month breakdown, timeline, category spending.

### BR-003: Payer Share Validation

When all payers use `ShareType.PERCENT`, their `share_value` fields must sum to exactly 100 (tolerance: ±0.01). Validated in `PurchaseCreate._validate_payer_shares`. Each `share_value` must be `> 0`.

### BR-004: Default Payer Logic

When no explicit `payers` are provided on purchase creation:
- If `card_id` is set → default payer is `card.owner_person_id` at 100% PERCENT.
- Else if `owner_person_id` is set → default payer is `owner_person_id` at 100% PERCENT.
- Else → `ValueError("owner_person_id is required for non-card expenses")`.

### BR-005: Import Deduplication (SHA256 Fingerprints)

Each imported row produces a SHA256 fingerprint from: `{provider, card_id, purchase_date, description, currency, installment_index, installments_total, installment_amount, statement_year_month, occurrence_index}`. The fingerprint is stored in `ImportedRow.row_fingerprint` (unique). Re-importing the same file skips rows whose fingerprint already exists.

For Google Sheets imports, fingerprint is computed from: `{fecha, tipo, monto, moneda, descripcion}`.

### BR-006: Import Exclusion Heuristics

Rows matching any of these patterns are excluded during import:

**Excluded prefixes** (case-insensitive):
- `su pago`, `pago de tarjeta`, `resumen de `, `promo`, `cr.`, `cr `, `total de`, `total`, `tarjeta de`, `tarjeta visa`, `movimientos del resumen`, `bonif.`

**Excluded if description contains** (case-insensitive):
- `total`

**Tax patterns excluded:**
- `db.rg 5617`, `iibb percep`, `impuesto de sellos`, `impuesto de sello`, `impuesto al sello`

**Amounts ≤ 0** are always excluded.

Refunds from cancelled purchases (devoluciones por compra anulada) are **not** excluded.

### BR-007: Installment Amount Normalization

`_normalize_installment_amount` logic:
- If `installments_total ≤ 1` → installment amount = `amount_original`
- If `installment_amount_original` is provided → use it directly
- Otherwise → `amount_original / installments_total`

All amounts are rounded using `_round_money()`: `round(value + 1e-9, 2)` to compensate for floating-point errors.

### BR-008: Installment Schedule Generation

On `create_purchase`, `_create_installment_schedule` generates entries:
- `first_month` = `first_installment_month` or `to_year_month(purchase_date)`
- For single installment: one entry at `first_month` with `installment_index=1`
- For N installments: N entries from `first_month` to `first_month + (N-1)`, with `installment_index` 1..N
- Each entry's `amount_original` = normalized installment amount (BR-007)
- `amount_ars` is always `None` (conversion happens at query time)

### BR-009: Category Rename Cascade

When a `Category` is renamed via `update_category`, all `Purchase` records with `category == old_name` are updated to the new name in the same transaction.

### BR-010: Category Delete Nullify

When a `Category` is deleted via `delete_category`, all `Purchase` records with `category == category.name` have their `category` set to `None`.

### BR-011: Purchase Delete Manual Cascade

`delete_purchase` uses raw SQL to delete children before the parent:
1. `DELETE FROM installmentschedule WHERE purchase_id = :pid`
2. `DELETE FROM purchasepayer WHERE purchase_id = :pid`
3. `DELETE FROM purchase WHERE id = :pid`

This is necessary because SQLModel doesn't emit `ON DELETE CASCADE` in DDL by default.

### BR-012: Monthly Balance /2 Hardcoded

`calculate_monthly_balance` divides `sobrante_total` by 2 (hardcoded) to compute `sobrante_por_persona`. This assumes exactly 2 people in the household.

### BR-013: Atomic Purchase Creation

`create_purchase` uses `session.flush()` (not commit) to obtain the `purchase.id`, then creates `PurchasePayer` and `InstallmentSchedule` entries, and finally issues a single `session.commit()`. This ensures all-or-nothing semantics.

### BR-014: year_month Regex Validation

All `year_month` input fields use the pattern: `^\d{4}-(0[1-9]|1[0-2])$`. Applied in `PurchaseCreate.first_installment_month`, `FxRateUpsert.year_month`, `MonthlyBudgetCreate.year_month`, `IncomeCreate.year_month`, `DebtTransferCreate.year_month`.

### BR-015: card_id Required for CARD Payment

`PurchaseCreate._validate_card_presence`: if `payment_method == PaymentMethod.CARD` and `card_id is None`, a `ValueError` is raised.

### BR-016: Income Auto-Updates MonthlyBudget

When an `Income` is created, `_update_monthly_budget_from_incomes` recalculates the sum of all incomes for that month and creates or updates the corresponding `MonthlyBudget` record.

### BR-017: Beneficiary Override in Transfer Calc

In `calculate_transfers`, personal expenses are attributed to `beneficiary_person_id` if set, otherwise to `owner_person_id` (or `card.owner_person_id`). This allows a purchase paid by Person A to be counted as a personal expense of Person B.

### BR-018: Import Installment Matching (Exact + Fuzzy)

`find_existing_purchase_for_installment_import` uses two-pass matching:

1. **Pass 1 (Exact):** Matches on `card_id`, `purchase_date`, `currency`, `installments_total`, normalized description, and amount (±0.01 absolute or ±1% relative).
2. **Pass 2 (Fuzzy):** If no exact match, checks all candidates matching `card_id`, `purchase_date`, `currency`, `installments_total` with matching amount. If exactly ONE candidate matches, it's returned regardless of description.

The `exclude_ids` parameter prevents the same purchase from being claimed by multiple imported rows.

### BR-019: FX Conversion Logic

- **ARS:** `amount_ars = amount_original` (no conversion needed)
- **USD:** `amount_ars = amount_original × fx_rate.rate_to_ars` where `fx_rate` is looked up by `(year_month, currency)`
- If no FX rate exists → installment is skipped (BR-002)

### BR-020: Description Normalization

`normalize_purchase_description` removes:
1. Installment patterns: `C.X/Y` and `N de N`
2. Leading numeric codes: `^\s*\d{3,}\s+`
3. Trailing numeric codes: `\s+\d{3,}\s*$`
4. Collapses multiple spaces to single space, trims

### BR-021: Transfer Calc with DebtTransfer Adjustments

In `calculate_transfers`, each person's `difference` is adjusted by their net `DebtTransfer` activity:
- `adjustment = sent_transfers − received_transfers`
- `final_difference = (paid − should_pay) + adjustment`

This means if Person A already sent money to Person B for this month, that reduces the pending transfer amount.

### BR-022: MonthlyBudget Upsert

`create_monthly_budget` checks if a budget for the given `year_month` already exists. If yes, updates `total_income` and `notes`; otherwise creates a new record.

### BR-023: FxRate Upsert

`upsert_fx_rate` checks if a rate for `(year_month, currency)` exists. If yes, updates `rate_to_ars`; otherwise creates a new record.

### BR-024: Person Filter Allocation via PurchasePayer Shares

When reports are filtered by `person_id`, amounts are allocated proportionally based on the person's `PurchasePayer` share:
- `PERCENT` share: `amount_ars × (share_value / 100)`
- `FIXED` share: `share_value` directly
- If person has no payer record for a purchase, they get 0 (unless they are the owner, in which case 100%).

---

## 4. Use Cases — Entity Management

### UC-001: Create Person

- **Endpoint:** `POST /api/people`
- **Payload:** `{ name: str }`
- **Steps:** Creates a `Person` record.
- **Result:** `201` → `PersonRead { id, name }`
- **Edge Cases:** No uniqueness constraint on name — duplicates allowed.

### UC-002: List People

- **Endpoint:** `GET /api/people`
- **Steps:** Returns all people ordered by name.
- **Result:** `200` → `PersonRead[]`

### UC-003: Create Card

- **Endpoint:** `POST /api/cards`
- **Payload:** `{ name, provider, owner_person_id, last4? }`
- **Preconditions:** `owner_person_id` must reference an existing `Person`.
- **Steps:** Validates FK, creates `Card`.
- **Result:** `201` → `CardRead`
- **Business Rules:** BR-004 (FK validation)
- **Edge Cases:** Invalid `owner_person_id` → `400 "Person not found"`.

### UC-004: List Cards

- **Endpoint:** `GET /api/cards`
- **Result:** `200` → `CardRead[]` ordered by name.

### UC-005: Create Debtor

- **Endpoint:** `POST /api/debtors`
- **Payload:** `{ name: str }`
- **Result:** `201` → `DebtorRead { id, name }`

### UC-006: List Debtors

- **Endpoint:** `GET /api/debtors`
- **Result:** `200` → `DebtorRead[]` ordered by name.

### UC-007: Upsert FX Rate

- **Endpoint:** `POST /api/fx`
- **Payload:** `{ year_month, currency, rate_to_ars }`
- **Steps:** If rate for `(year_month, currency)` exists → update; else → create.
- **Result:** `200` → `FxRateRead`
- **Business Rules:** BR-023, BR-014
- **Validation:** `year_month` must match `YYYY-MM`; `rate_to_ars > 0`.

### UC-008: List FX Rates

- **Endpoint:** `GET /api/fx`
- **Result:** `200` → `FxRateRead[]` ordered by year_month, currency.

### UC-009: Create Category

- **Endpoint:** `POST /api/categories`
- **Payload:** `{ name, color? }`
- **Result:** `200` → `CategoryRead`
- **Edge Cases:** Duplicate name → `400` (IntegrityError caught).

### UC-010: List Categories

- **Endpoint:** `GET /api/categories`
- **Result:** `200` → `CategoryRead[]` ordered by name.

### UC-011: Update Category

- **Endpoint:** `PATCH /api/categories/{category_id}`
- **Payload:** `{ name?, color? }`
- **Steps:** If `name` changed, cascades to all purchases (BR-009).
- **Result:** `200` → `CategoryRead`
- **Business Rules:** BR-009
- **Edge Cases:** Category not found → `404`.

### UC-012: Delete Category

- **Endpoint:** `DELETE /api/categories/{category_id}`
- **Steps:** Sets `category = None` on all affected purchases (BR-010), then deletes the category.
- **Result:** `204` No Content
- **Business Rules:** BR-010
- **Edge Cases:** Category not found → `404`.

### UC-013: List Distinct Categories (from Purchases)

- **Endpoint:** `GET /api/categories/distinct`
- **Steps:** Returns unique non-null category values from `Purchase.category`.
- **Result:** `200` → `string[]` (sorted).

---

## 5. Use Cases — Purchase Lifecycle

### UC-020: Create Purchase

- **Endpoint:** `POST /api/purchases`
- **Payload:** `PurchaseCreate` (see schemas)
- **Preconditions:**
  - If `payment_method == CARD` → `card_id` required (BR-015)
  - If `card_id` set → card must exist
  - If `owner_person_id` set → person must exist
  - If `payers` set → each `person_id` must exist
  - If no card and no `owner_person_id` → error (BR-004)
- **Steps:**
  1. Validate all FK references
  2. Compute `first_installment_month` (default: purchase date month)
  3. Normalize installment amount (BR-007)
  4. Create `Purchase` record, flush to get ID
  5. Create `PurchasePayer` records (explicit or default per BR-004)
  6. Create `InstallmentSchedule` entries (BR-008)
  7. Single commit (BR-013)
- **Result:** `201` → `PurchaseRead` with populated `payers`
- **Business Rules:** BR-003, BR-004, BR-007, BR-008, BR-013, BR-014, BR-015
- **Edge Cases:**
  - Missing card → `400 "Card not found"`
  - Missing person → `400 "Person not found"`
  - PERCENT shares don't sum to 100 → `400`

### UC-021: Update Purchase (Partial)

- **Endpoint:** `PATCH /api/purchases/{purchase_id}`
- **Payload:** `PurchaseUpdate { notes?, category?, is_common?, debtor_id?, beneficiary_person_id?, debt_settled? }`
- **Steps:** Updates only provided fields. Does **not** regenerate installment schedule.
- **Result:** `200` → `PurchaseRead`
- **Edge Cases:** Purchase not found → `404`.

### UC-022: Delete Purchase

- **Endpoint:** `DELETE /api/purchases/{purchase_id}`
- **Steps:** Manual cascade delete (BR-011): installments → payers → purchase.
- **Result:** `204` No Content
- **Business Rules:** BR-011
- **Edge Cases:** Purchase not found → `404`.

### UC-023: Bulk Update Purchases

- **Endpoint:** `POST /api/purchases/bulk`
- **Payload:** `{ purchase_ids: int[], update: PurchaseUpdate }`
- **Steps:** Iterates over IDs, applies `update_purchase` to each. Skips IDs not found.
- **Result:** `200` → `{ updated: int }`

### UC-024: Auto-Categorize Purchases

- **Endpoint:** `POST /api/purchases/auto-categorize`
- **Steps:**
  1. Ensures all keyword categories exist in `Category` table (creates missing ones)
  2. Finds purchases where `category IS NULL OR category == 'Sin categoría'`
  3. Matches description (case-insensitive) against keyword map (see Appendix A)
  4. First keyword match wins; updates `purchase.category`
- **Result:** `200` → `{ updated: int }`
- **Business Rules:** Keyword map is hardcoded in `auto_categorize_purchases` (see Appendix A)

### UC-025: List Purchases (with Filters)

- **Endpoint:** `GET /api/purchases`
- **Query Params:**
  - `year_month` (YYYY-MM) — filters by `purchase_date` within that calendar month
  - `category` — exact match; use `"null"` to filter for NULL categories
  - `start_date`, `end_date` — date range on `purchase_date`
  - `min_amount`, `max_amount` — range on `amount_original`
  - `description_search` — case-insensitive substring match
  - `person_id` — filters to purchases where person has a `PurchasePayer` entry
  - `page` (default 1), `page_size` (default 50)
- **Result:** `200` → `PaginatedResponse<PurchaseRead>` with `{ items, total, page, page_size, pages }`
- **Business Rules:** BR-024 (person filter uses PurchasePayer join)
- **Edge Cases:** No matches → `{ items: [], total: 0, page: 1, page_size: 50, pages: 0 }`

---

## 6. Use Cases — Reports

### UC-030: Month Breakdown

- **Endpoint:** `GET /api/reports/month-breakdown`
- **Query Params:** `year_month` (required), `card_id?`, `person_id?`, `is_common?`
- **Steps:** Joins `InstallmentSchedule` with `Purchase`, `Debtor`, `Card`, `Person` (owner). Converts USD using FX rates (BR-019). If `person_id` filter, allocates amounts via PurchasePayer shares (BR-024).
- **Result:** `200` → `MonthBreakdownResponse { year_month, total_ars, items: MonthBreakdownRow[] }`
- **Business Rules:** BR-002, BR-019, BR-024

### UC-031: Monthly Totals

- **Endpoint:** `GET /api/reports/monthly`
- **Query Params:** `card_id?`, `person_id?`
- **Steps:** Aggregates all installment schedule entries by `year_month`, converting USD via FX rates.
- **Result:** `200` → `ReportMonthlyRow[] { year_month, total_ars }` (sorted ascending)
- **Business Rules:** BR-002, BR-019, BR-024

### UC-032: Installment Timeline

- **Endpoint:** `GET /api/reports/timeline`
- **Query Params:** `months_ahead` (default 12), `card_id?`, `person_id?`, `is_common?`
- **Steps:** Returns installment commitments from `current_month - 3` to `current_month + months_ahead`.
- **Result:** `200` → `TimelineRow[] { year_month, total_ars }` (sorted ascending)
- **Business Rules:** BR-002, BR-019, BR-024

### UC-033: Category Spending

- **Endpoint:** `GET /api/reports/category-spending`
- **Query Params:** `card_id?`, `person_id?`, `year_month?`, `is_common?`
- **Steps:** Aggregates installment amounts by `purchase.category`. Categories with `NULL` name show as `"Sin categoría"`.
- **Result:** `200` → `CategorySpendingRow[] { category, total_ars }` (sorted by total descending)
- **Business Rules:** BR-002, BR-019, BR-024

### UC-034: Debt Summary

- **Endpoint:** `GET /api/reports/debts`
- **Steps:** For each debtor, sums `amount_original` of their purchases, split by `debt_settled` flag.
- **Result:** `200` → `DebtSummaryRow[] { debtor_id, debtor_name, total_owed, total_settled, pending_purchases }`
- **Edge Cases:** Only includes debtors with at least one purchase (`total_owed > 0 || total_settled > 0`).

### UC-035: Monthly Balance

- **Endpoint:** `GET /api/reports/monthly-balance`
- **Query Params:** `year_month` (required)
- **Steps:** Looks up `MonthlyBudget` for the month. Sums all installment ARS amounts for the month. Computes surplus.
- **Result:** `200` → `MonthlyBalanceResponse { year_month, presupuesto, gastos_acumulados, sobrante_total, sobrante_por_persona, porcentaje_gastado }`
- **Business Rules:** BR-012 (divides surplus by 2)
- **Edge Cases:** No budget → `404 "Budget not found for this month"`.

### UC-036: Transfer Calculation (Fondo Común)

- **Endpoint:** `GET /api/reports/transfers`
- **Query Params:** `year_month` (required)
- **Steps:** Executes Fondo Común algorithm (BR-001).
- **Result:** `200` → `TransferCalculationResponse { year_month, ingresos, total_ingresos, gastos_por_persona, transferencias, is_balanced, balance_delta, transferencias_internas }`
- **Business Rules:** BR-001, BR-017, BR-021
- **Edge Cases:** No incomes for the month → `404 "No incomes found for this month"`.

### UC-037: Export Dashboard to Excel

- **Endpoint:** `GET /api/reports/export-excel`
- **Query Params:** `year_month` (required)
- **Steps:** Generates an XLSX file with sheets: Balance, Gastos por Persona, Transferencias, Detalle del Mes, Mes Siguiente (forecast), Deudas de Terceros.
- **Result:** `200` → binary XLSX file with `Content-Disposition: attachment; filename=reporte_YYYY-MM.xlsx`
- **Business Rules:** Uses same data as UC-035, UC-036, UC-030, UC-034.

---

## 7. Use Cases — Income & Budget

### UC-040: Create Income

- **Endpoint:** `POST /api/incomes`
- **Payload:** `{ person_id, year_month, amount, notes? }`
- **Preconditions:** `person_id` must reference existing Person.
- **Steps:**
  1. Validates person exists (404 if not)
  2. Creates `Income` record
  3. Auto-updates `MonthlyBudget` for the month (BR-016)
- **Result:** `200` → `IncomeRead { id, person_id, person_name, year_month, amount, notes }`
- **Business Rules:** BR-014, BR-016
- **Validation:** `amount > 0`, `year_month` matches regex.

### UC-041: List Incomes

- **Endpoint:** `GET /api/incomes`
- **Query Params:** `year_month?`
- **Steps:** Returns all incomes (optionally filtered by month), joined with Person for name. Ordered by `year_month DESC, person.name`.
- **Result:** `200` → `IncomeRead[]`

### UC-042: Create Monthly Budget (Manual)

- **Endpoint:** `POST /api/budgets`
- **Payload:** `{ year_month, total_income, notes? }`
- **Steps:** Upserts budget (BR-022).
- **Result:** `200` → `MonthlyBudgetRead`
- **Business Rules:** BR-014, BR-022
- **Validation:** `total_income > 0`.

### UC-043: List Monthly Budgets

- **Endpoint:** `GET /api/budgets`
- **Result:** `200` → `MonthlyBudgetRead[]` ordered by `year_month DESC`.

### UC-044: Create Debt Transfer

- **Endpoint:** `POST /api/debt-transfers`
- **Payload:** `{ from_person_id, to_person_id, year_month, amount, transfer_date?, notes? }`
- **Preconditions:** Both person IDs must exist.
- **Steps:** Validates persons, creates `DebtTransfer` record.
- **Result:** `200` → `DebtTransferRead`
- **Business Rules:** BR-014
- **Validation:** `amount > 0`; persons not found → `404`.

### UC-045: List Debt Transfers

- **Endpoint:** `GET /api/debt-transfers`
- **Query Params:** `year_month?`
- **Result:** `200` → `DebtTransferRead[]` ordered by `transfer_date DESC`.

### UC-046: Delete Debt Transfer

- **Endpoint:** `DELETE /api/debt-transfers/{transfer_id}`
- **Steps:** Finds and deletes the transfer.
- **Result:** `204` No Content
- **Edge Cases:** Not found → `404`.

---

## 8. Use Cases — Import

### UC-050: Import Visa XLSX

- **Endpoint:** `POST /api/import/visa-xlsx`
- **Form Params:** `card_id` (int), `provider` (str), `is_common` (bool, default false), `file` (UploadFile)
- **Preconditions:** File must have `.xlsx` or `.xls` extension.
- **Steps:**
  1. Parse XLSX: detect `statement_year_month` from "Fecha de cierre" row
  2. Find header row containing "Descripción" and "Monto en pesos"
  3. For each data row: parse date, description, amounts (ARS/USD), installments
  4. Apply exclusion heuristics (BR-006); skip amounts ≤ 0
  5. For each parsed row: compute fingerprint (BR-005), check dedup, find existing purchase (BR-018), create or link installment
  6. Mark imported (store fingerprint)
- **Result:** `200` → `{ created, skipped, parsed }`
- **Business Rules:** BR-005, BR-006, BR-007, BR-018, BR-020
- **Edge Cases:**
  - Can't detect statement month → `400`
  - Can't find header row → `400`
  - Wrong file extension → `400`

### UC-051: Import Visa/Mastercard PDF

- **Endpoint:** `POST /api/import/visa-pdf`
- **Form Params:** `card_id` (int), `provider` (str), `file` (UploadFile), `password?` (str), `is_common` (bool, default false)
- **Preconditions:** File must have `.pdf` extension.
- **Steps:**
  1. Decrypt PDF if password-protected
  2. Extract text and tables using pdfplumber
  3. Detect `statement_year_month` from text patterns (see Appendix C)
  4. Try parsers in order: Banco Nación Visa → Banco Nación Mastercard → MercadoPago App → MercadoPago PDF → Table-based fallback
  5. First parser that returns results wins
  6. For each parsed row: same processing as UC-050 step 5-6
- **Result:** `200` → `{ created, skipped, parsed }`
- **Business Rules:** BR-005, BR-006, BR-018, BR-020
- **Supported Formats:**
  - **Banco Nación Visa:** `DD.MM.YY comprobante descripción C.X/Y monto_pesos monto_usd`
  - **Banco Nación Mastercard:** `DD-Mmm-YY descripción X/Y comprobante monto`
  - **MercadoPago App:** `DD/mmm descripción $ monto`
  - **MercadoPago PDF:** `DD/MM/YYYY descripción monto_ars [monto_usd]`
  - **Table-based fallback:** Structured tables with recognized column headers
- **Edge Cases:**
  - Encrypted PDF without password → `400 "El PDF está protegido con contraseña..."`
  - Can't detect statement month → `400`
  - No rows parsed → `{ created: 0, skipped: 0, parsed: 0 }`

### UC-052: Import Google Sheets CSV

- **Endpoint:** `POST /api/import/gsheets`
- **Payload:** `{ url, owner_person_id, is_common }`
- **Steps:**
  1. Convert Google Sheets URL to CSV export URL
  2. Download CSV (30s timeout)
  3. Parse columns: `fecha` (YYYY-MM-DD), `tipo`, `monto`, `moneda`, `descripcion`
  4. Skip rows with `amount ≤ 0`
  5. All imports use `payment_method = TRANSFER`, `installments_total = 1`
  6. Dedup via SHA256 fingerprint
- **Result:** `200` → `{ created, skipped, parsed }`
- **Business Rules:** BR-005
- **Edge Cases:** Invalid URL or network error → `500`.

---

## 9. Use Cases — Frontend Pages

### UC-060: Dashboard Page (`/`)

- **Features:**
  - Month selector (YYYY-MM)
  - Monthly breakdown table with installment details (UC-030)
  - Monthly balance card showing budget vs expenses (UC-035)
  - Transfer calculation card with Fondo Común results (UC-036)
  - Timeline chart for future installments (UC-032)
  - Category spending chart (UC-033)
  - Person filter dropdown
  - is_common filter toggle
  - Export to Excel button (UC-037)

### UC-061: Purchases Page (`/purchases`)

- **Features:**
  - Filterable/paginated purchase list (UC-025)
  - Filters: category, date range, amount range, description search, payer person, debtor
  - Inline editing of: notes, category, is_common, debtor, beneficiary, debt_settled (UC-021)
  - Bulk update via checkbox selection (UC-023)
  - Auto-categorize button (UC-024)
  - Delete purchase with confirmation dialog (UC-022)
  - Create new purchase form (UC-020)

### UC-062: Import Page (`/import`)

- **Features:**
  - Card selector dropdown
  - Provider selector
  - File upload (XLSX or PDF)
  - Password field for encrypted PDFs
  - is_common checkbox
  - Google Sheets URL input with owner person selector
  - Import result display (created/skipped/parsed)

### UC-063: Budget Page (`/budget`)

- **Features:**
  - Income creation form (person, month, amount, notes) (UC-040)
  - Income list for selected month (UC-041)
  - Debt transfer creation form (UC-044)
  - Debt transfer list (UC-045)
  - Monthly balance display (UC-035)
  - Transfer calculation display (UC-036)

### UC-064: Categories Page (`/categories`)

- **Features:**
  - Category list with name and color (UC-010)
  - Create category form (UC-009)
  - Inline edit category name/color (UC-011)
  - Delete category with confirmation (UC-012)

### UC-065: Admin Page (`/admin`)

- **Features:**
  - People management: create (UC-001), list (UC-002)
  - Cards management: create (UC-003), list (UC-004)
  - Debtors management: create (UC-005), list (UC-006)
  - FX Rates management: upsert (UC-007), list (UC-008)

### UC-066: ConfirmDialog Component

- **Features:**
  - Reusable modal dialog for delete confirmations
  - Props: `open`, `title`, `message`, `onConfirm`, `onCancel`
  - Used by: purchase delete, category delete, debt transfer delete

---

## 10. API Endpoint Reference

| Method | Path | UC | Description |
|---|---|---|---|
| `GET` | `/health` | — | Health check |
| `GET` | `/api/people` | UC-002 | List people |
| `POST` | `/api/people` | UC-001 | Create person |
| `GET` | `/api/cards` | UC-004 | List cards |
| `POST` | `/api/cards` | UC-003 | Create card |
| `GET` | `/api/debtors` | UC-006 | List debtors |
| `POST` | `/api/debtors` | UC-005 | Create debtor |
| `GET` | `/api/fx` | UC-008 | List FX rates |
| `POST` | `/api/fx` | UC-007 | Upsert FX rate |
| `GET` | `/api/categories` | UC-010 | List categories |
| `POST` | `/api/categories` | UC-009 | Create category |
| `PATCH` | `/api/categories/{id}` | UC-011 | Update category |
| `DELETE` | `/api/categories/{id}` | UC-012 | Delete category |
| `GET` | `/api/categories/distinct` | UC-013 | Distinct purchase categories |
| `GET` | `/api/purchases` | UC-025 | List purchases (paginated, filtered) |
| `POST` | `/api/purchases` | UC-020 | Create purchase |
| `PATCH` | `/api/purchases/{id}` | UC-021 | Update purchase |
| `DELETE` | `/api/purchases/{id}` | UC-022 | Delete purchase |
| `POST` | `/api/purchases/bulk` | UC-023 | Bulk update purchases |
| `POST` | `/api/purchases/auto-categorize` | UC-024 | Auto-categorize |
| `GET` | `/api/reports/month-breakdown` | UC-030 | Month breakdown |
| `GET` | `/api/reports/monthly` | UC-031 | Monthly totals |
| `GET` | `/api/reports/timeline` | UC-032 | Installment timeline |
| `GET` | `/api/reports/category-spending` | UC-033 | Category spending |
| `GET` | `/api/reports/debts` | UC-034 | Debt summary |
| `GET` | `/api/reports/monthly-balance` | UC-035 | Monthly balance |
| `GET` | `/api/reports/transfers` | UC-036 | Transfer calculation |
| `GET` | `/api/reports/export-excel` | UC-037 | Export dashboard XLSX |
| `GET` | `/api/incomes` | UC-041 | List incomes |
| `POST` | `/api/incomes` | UC-040 | Create income |
| `GET` | `/api/budgets` | UC-043 | List budgets |
| `POST` | `/api/budgets` | UC-042 | Create/upsert budget |
| `GET` | `/api/debt-transfers` | UC-045 | List debt transfers |
| `POST` | `/api/debt-transfers` | UC-044 | Create debt transfer |
| `DELETE` | `/api/debt-transfers/{id}` | UC-046 | Delete debt transfer |
| `POST` | `/api/import/visa-xlsx` | UC-050 | Import Visa XLSX |
| `POST` | `/api/import/visa-pdf` | UC-051 | Import Visa/MC PDF |
| `POST` | `/api/import/gsheets` | UC-052 | Import Google Sheets CSV |

---

## 11. Validation Rules Summary

| Field / Context | Rule | Error |
|---|---|---|
| `year_month` | `^\d{4}-(0[1-9]\|1[0-2])$` | 422 Validation Error |
| `PurchasePayerCreate.share_value` | `> 0` | 422 |
| `PurchaseCreate` with all PERCENT payers | `sum(share_value) == 100 ± 0.01` | 400 ValueError |
| `PurchaseCreate` with `payment_method=CARD` | `card_id` must not be None | 400 ValueError |
| `PurchaseCreate` without card or payers | `owner_person_id` required | 400 ValueError |
| `CardCreate.owner_person_id` | Must reference existing Person | 400 ValueError |
| `PurchaseCreate.card_id` | Must reference existing Card | 400 ValueError |
| `PurchaseCreate.owner_person_id` | Must reference existing Person (if set) | 400 ValueError |
| `PurchaseCreate.payers[].person_id` | Each must reference existing Person | 400 ValueError |
| `IncomeCreate.person_id` | Must reference existing Person | 404 |
| `DebtTransferCreate.from/to_person_id` | Both must reference existing Person | 404 |
| `FxRateUpsert.rate_to_ars` | `> 0` | 422 |
| `IncomeCreate.amount` | `> 0` | 422 |
| `DebtTransferCreate.amount` | `> 0` | 422 |
| `MonthlyBudgetCreate.total_income` | `> 0` | 422 |
| `PurchaseCreate.installments_total` | `≥ 1` | 422 |
| Import file extension | `.xlsx`/`.xls` for XLSX; `.pdf` for PDF | 400 |
| Import file name | Must not be empty | 400 |
| PDF password | Required if PDF is encrypted | 400 |

---

## 12. Data Integrity Invariants

These conditions must always hold true. Useful as assertions for future test suites.

1. **INV-001:** Every `InstallmentSchedule` has a valid `purchase_id` pointing to an existing `Purchase`.
2. **INV-002:** Every `PurchasePayer` has a valid `purchase_id` and `person_id`.
3. **INV-003:** Every `Card.owner_person_id` points to an existing `Person`.
4. **INV-004:** `ImportedRow.row_fingerprint` is globally unique.
5. **INV-005:** For any purchase with `installments_total = N`, there exist exactly N `InstallmentSchedule` entries (unless additional installments were added by re-import).
6. **INV-006:** `MonthlyBudget.year_month` is unique — at most one budget per month.
7. **INV-007:** `Category.name` is unique.
8. **INV-008:** If `Purchase.payment_method == CARD`, then `Purchase.card_id IS NOT NULL`.
9. **INV-009:** Every `Purchase` has at least one `PurchasePayer` entry.
10. **INV-010:** `PRAGMA foreign_keys = ON` is enforced on every SQLite connection.
11. **INV-011:** When a `Category` is renamed, no `Purchase` retains the old category name.
12. **INV-012:** When a `Category` is deleted, all formerly-associated `Purchase.category` values become `NULL`.
13. **INV-013:** All monetary amounts are rounded to 2 decimal places in output.
14. **INV-014:** The sum of all `difference` values in a transfer calculation equals `balance_delta`, which should be ≤ 0.01 for a balanced month.

---

## 13. Appendices

### Appendix A: Auto-Categorize Keyword Map

| Category | Keywords (case-insensitive substring match on description) |
|---|---|
| `supermercado` | COTO, CARREFOUR, JUMBO, DISCO, VEA, DIA, LA ANONIMA |
| `servicios` | AYSA, EDESUR, EDENOR, METROGAS, PERSONAL, MOVISTAR, CLARO, CABLEVISION, TELECENTRO |
| `restaurantes` | MC DONALDS, BURGER KING, STARBUCKS, PEDIDOSYA, RAPPI, RESTAURANT, CAFE, CERVECERIA |
| `transporte` | SUBE, UBER, CABIFY, DIDI, AXION, YPF, SHELL, ESTACION DE SERV |
| `hogar` | EASY, SODIMAC, FERRETERIA, BLANQUERIA |
| `salud` | OSDE, SWISS MEDICAL, FARMACIA, LABORATORIO |
| `educacion` | COLEGIO, UNIVERSIDAD, LIBRE RIA |
| `entretenimiento` | NETFLIX, SPOTIFY, DISNEY, CINEMA, TEATRO |

First match wins. Categories are auto-created in the `Category` table if they don't exist.

### Appendix B: Import Exclusion Patterns

See BR-006 for the full list. Summary of regex/string patterns used:

```
Prefixes: su pago, pago de tarjeta, resumen de, promo, cr., cr , total de, total,
          tarjeta de, tarjeta visa, movimientos del resumen, bonif.
Contains: total
Tax:      db.rg 5617, iibb percep, impuesto de sellos, impuesto de sello, impuesto al sello
Amount:   ≤ 0
```

### Appendix C: PDF Statement Month Detection

`_detect_statement_year_month_from_text` tries these patterns in order:

1. **MercadoPago "cierre actual" / "resumen de":** `(cierre actual|resumen de) [N de] <mes_nombre>` → extract month. For "resumen de", the closing month is one month prior.
2. **Date-based cierre:** `(fecha de cierre|cierre): DD/MM/YYYY` → extract month/year.
3. **Banco Nación Visa:** `cierre actual: DD Mmm YY` → parse `Mmm YY`.
4. **Banco Nación Mastercard:** `(estado de cuenta al|cierre anterior): DD-Mmm-YY` → parse `Mmm YY`.
5. **Fallback patterns:** Various `DD/MM/YYYY...cierre` and `cierre...DD/MM/YYYY` patterns.

### Appendix D: Description Normalization Regex

```python
# Remove installment patterns like "C.17/24" or "3 de 3"
_purchase_desc_cleanup_re = r"\b(?:C\.)\s*\d+\s*/\s*\d+\b|\b\d+\s*de\s*\d+\b"

# Remove leading numeric codes (3+ digits)
_purchase_desc_leading_code_re = r"^\s*\d{3,}\s+"

# Remove trailing numeric codes (3+ digits)
_purchase_desc_trailing_code_re = r"\s+\d{3,}\s*$"

# Collapse whitespace
re.sub(r"\s+", " ", cleaned).strip()
```

### Appendix E: Installment Parsing Patterns

Three patterns tried in order:
1. `^(\d+)\s*de\s*(\d+)$` — standalone "X de Y"
2. `C\.(\d+)/(\d+)` — Banco Nación format "C.17/24"
3. `(\d+)\s+de\s+(\d+)` — embedded "3 de 3" (MercadoPago)

If no match: defaults to `(1, 1)` (single installment). `total ≤ 0` also defaults to `(1, 1)`. `current` is clamped to `[1, total]`.

### Appendix F: Global Error Handlers

Defined in `main.py`:
- `IntegrityError` → `409 { detail: "Conflict: duplicate or constraint violation" }`
- `ValueError` → `400 { detail: str(exc) }`

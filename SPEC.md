# Software Specification Document (SDD)

**Project:** Admin Consumos
**Version:** 1.1
**Last Updated:** 2026-06-14

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

### 2.2 Entities (19 tables)

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

#### CardStatement
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `card_id` | int | FK → `card.id`, indexed |
| `year_month` | str | `YYYY-MM` — statement (billing-cycle) month |
| `closing_date` | date | exact closing date of the statement |
| `due_date` | date? | optional payment due date |

Unique constraint: `UNIQUE(card_id, year_month)` (`uq_cardstatement_card_month`). Records the closing/due dates per card per month, used to suggest `first_installment_month` for a purchase (BR-027, UC-091).

#### Debtor
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `name` | str | required |

#### Beneficiary
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `name` | str | required |
| `cbu` | str? | optional, bank CBU |
| `cuit` | str? | optional, tax ID |
| `alias` | str? | optional, transfer alias |

A transfer recipient (e.g. a third-party CBU/alias). Used by comprobante extraction (UC-053) to match an extracted nombre/CBU/CUIT/alias against a known recipient. Created via the `beneficiary` table at startup by `db.py:_migrate_add_columns()` if missing.

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
| `import_batch_id` | int? | FK → `importbatch.id`, indexed. Set when the purchase originated from a file/CSV import (UC-056). |

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

Unique constraint: `UNIQUE INDEX ux_installment_purchase_index (purchase_id, installment_index)` — created at startup by `db.py:_migrate_dedupe_installments()` (after de-duplicating any pre-existing rows). Prevents two schedule entries for the same installment of a purchase. See BR-026.

#### ImportedRow
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `provider` | str | indexed |
| `source_file` | str | required |
| `row_fingerprint` | str | indexed, unique |
| `parsed_payload_json` | str | JSON blob of parsed row data |

#### ImportBatch
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `imported_at` | str | ISO-8601 datetime |
| `provider` | str | indexed |
| `source_file` | str | required |
| `card_id` | int? | FK → `card.id` |
| `statement_year_month` | str? | `YYYY-MM` |
| `purchases_created` | int | default 0 |
| `purchases_skipped` | int | default 0 |
| `purchases_parsed` | int | default 0 |

One record per import run (UC-050/051/052). Purchases created in the run link back via `Purchase.import_batch_id`, enabling per-batch listing (UC-025 `import_batch_id` filter) and batch history (UC-056).

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

#### FamilyGoal
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `title` | str | required |
| `description` | str? | optional |
| `target_amount` | float? | optional, estimated budget in ARS |
| `due_date` | str? | `YYYY-MM` |
| `is_completed` | bool | default false |
| `notes` | str? | optional |
| `priority` | str? | free text: `"low"`, `"medium"`, `"high"` |

A household savings/spending goal shown on the `/goals` page (UC-068, UC-080..083).

#### Saving
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `person_id` | int | FK → `person.id`, indexed |
| `investment_type` | str | free text: "FCI", "Bono", "CDAR", etc. |
| `institution` | str | free text: "Banco Nación", "MP", etc. |
| `currency` | CurrencyCode | ARS or USD |
| `notes` | str? | optional |

#### SavingSnapshot
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `saving_id` | int | FK → `saving.id`, indexed |
| `date` | date | snapshot date |
| `amount` | float | `> 0` |

Current value of a `Saving` is derived from its most recent `SavingSnapshot`. No `current_amount` field is stored on `Saving`.

#### SavingsExchangeRate
| Field | Type | Constraints |
|---|---|---|
| `id` | int | PK, auto |
| `date` | str | indexed, `YYYY-MM-DD` |
| `usd_buy` | float | price the bank pays when buying USD (received when selling USD) |
| `usd_sell` | float | price the bank charges when selling USD (paid when buying USD) |

Manually-entered USD buy/sell quotes used to value mixed-currency savings totals over time (UC-079). Independent from `FxRate` (which is monthly and report-oriented).

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
- `first_month`:
  - If `payment_method` is `TRANSFER` or `CASH`: always `to_year_month(purchase_date)` — money exits immediately, belongs to the purchase month regardless of any `first_installment_month` provided (BR-024)
  - Otherwise (CARD): `first_installment_month` if provided, else `to_year_month(purchase_date)`
- For single installment: one entry at `first_month` with `installment_index=1`
- For N installments: N entries from `first_month` to `first_month + (N-1)`, with `installment_index` 1..N
- Each entry's `amount_original` = normalized installment amount (BR-007)
- `amount_ars` is always `None` (conversion happens at query time)

### BR-024: Transfer/Cash Month = Purchase Month

For `payment_method` in `{TRANSFER, CASH}`, `first_installment_month` is always forced to `to_year_month(purchase_date)` by `create_purchase`, ignoring any caller-supplied value. Rationale: transfers and cash payments exit the account immediately; they must appear in the dashboard for the month the transaction occurred, not a billing cycle later.

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

### BR-025: Person Filter Allocation via PurchasePayer Shares

When reports are filtered by `person_id`, amounts are allocated proportionally based on the person's `PurchasePayer` share:
- `PERCENT` share: `amount_ars × (share_value / 100)`
- `FIXED` share: `share_value` directly
- If person has no payer record for a purchase, they get 0 (unless they are the owner, in which case 100%).

### BR-026: Installment Schedule Uniqueness

A purchase may have at most one `InstallmentSchedule` entry per `installment_index`. Enforced by `UNIQUE INDEX ux_installment_purchase_index (purchase_id, installment_index)`, created at startup by `db.py:_migrate_dedupe_installments()` after removing any pre-existing duplicates. This is the constraint that makes re-import idempotent: BR-018 matching links a re-imported row to an existing purchase and only **adds the missing** installment, and this index guarantees a duplicate index can never be inserted. (Supersedes the earlier assumption in INV-005 that re-import could create extra installments.)

### BR-027: First Installment Month Suggestion from Card Statements

`suggest_first_installment_month(card_id, purchase_date)` (UC-091) returns the `year_month` whose billing cycle a purchase falls into:
1. Find the nearest `CardStatement` for the card with `closing_date >= purchase_date` (ordered ascending). If found → return `(its year_month, its closing_date, fallback=False)`.
2. Otherwise → fall back to the **next calendar month** after `purchase_date` and return `(year_month, None, fallback=True)`.

This only suggests a value for the UI; it does not change how `create_purchase` generates the schedule (BR-008).

### BR-028: Strict Duplicate Purchase Rejection

`POST /api/purchases` (UC-020) calls `find_duplicate_purchase` before creating. If an existing purchase matches on `card_id`, `payment_method`, `purchase_date`, `description`, `currency`, `amount_original`, and `installments_total`, the request is rejected with `409 "Duplicate purchase"`. This guards against accidental double-submits (e.g. the comprobante flow, UC-053/054) and is independent of import deduplication (BR-005, which uses fingerprints on `ImportedRow`).

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

### UC-014: List Beneficiaries

- **Endpoint:** `GET /api/beneficiaries`
- **Result:** `200` → `BeneficiaryRead[]` `{ id, name, cbu?, cuit?, alias? }`

### UC-015: Create Beneficiary

- **Endpoint:** `POST /api/beneficiaries`
- **Payload:** `{ name, cbu?, cuit?, alias? }`
- **Result:** `201` → `BeneficiaryRead`

### UC-016: Update Beneficiary

- **Endpoint:** `PUT /api/beneficiaries/{beneficiary_id}`
- **Payload:** `BeneficiaryUpdate { name?, cbu?, cuit?, alias? }`
- **Result:** `200` → `BeneficiaryRead`
- **Edge Cases:** Not found → `404`.

### UC-017: Delete Beneficiary

- **Endpoint:** `DELETE /api/beneficiaries/{beneficiary_id}`
- **Result:** `204` No Content
- **Edge Cases:** Not found → `404`.

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
- **Business Rules:** BR-003, BR-004, BR-007, BR-008, BR-013, BR-014, BR-015, BR-028
- **Steps (pre-check):** Before step 1, `find_duplicate_purchase` runs; an exact match → `409 "Duplicate purchase"` (BR-028).
- **Edge Cases:**
  - Duplicate purchase (BR-028) → `409 "Duplicate purchase"`
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
  - `import_batch_id` — filters to purchases created by a specific import batch (UC-056)
  - `page` (default 1), `page_size` (default 50)
- **Result:** `200` → `PaginatedResponse<PurchaseRead>` with `{ items, total, page, page_size, pages }`
- **Business Rules:** BR-025 (person filter uses PurchasePayer join)
- **Edge Cases:** No matches → `{ items: [], total: 0, page: 1, page_size: 50, pages: 0 }`

### UC-026: Get Categorization Rules

- **Endpoint:** `GET /api/purchases/categorization-rules`
- **Steps:** Returns the rules used by auto-categorization (UC-024): the hardcoded keyword map (Appendix A) plus any learned CUIL/description → category rules derived from the existing data.
- **Result:** `200` → `{ ... }` (object describing keyword and learned rules; consumed by the Purchases page for display/explanation).

---

## 6. Use Cases — Reports

### UC-030: Month Breakdown

- **Endpoint:** `GET /api/reports/month-breakdown`
- **Query Params:** `year_month` (required), `card_id?`, `person_id?`, `is_common?`
- **Steps:** Joins `InstallmentSchedule` with `Purchase`, `Debtor`, `Card`, `Person` (owner). Converts USD using FX rates (BR-019). If `person_id` filter, allocates amounts via PurchasePayer shares (BR-025).
- **Result:** `200` → `MonthBreakdownResponse { year_month, total_ars, items: MonthBreakdownRow[] }`
- **Business Rules:** BR-002, BR-019, BR-025

### UC-031: Monthly Totals

- **Endpoint:** `GET /api/reports/monthly`
- **Query Params:** `card_id?`, `person_id?`
- **Steps:** Aggregates all installment schedule entries by `year_month`, converting USD via FX rates.
- **Result:** `200` → `ReportMonthlyRow[] { year_month, total_ars }` (sorted ascending)
- **Business Rules:** BR-002, BR-019, BR-025

### UC-032: Installment Timeline

- **Endpoint:** `GET /api/reports/timeline`
- **Query Params:** `months_ahead` (default 12), `card_id?`, `person_id?`, `is_common?`
- **Steps:** Returns installment commitments from `current_month - 3` to `current_month + months_ahead`.
- **Result:** `200` → `TimelineRow[] { year_month, total_ars }` (sorted ascending)
- **Business Rules:** BR-002, BR-019, BR-025

### UC-033: Category Spending

- **Endpoint:** `GET /api/reports/category-spending`
- **Query Params:** `card_id?`, `person_id?`, `year_month?`, `is_common?`
- **Steps:** Aggregates installment amounts by `purchase.category`. Categories with `NULL` name show as `"Sin categoría"`.
- **Result:** `200` → `CategorySpendingRow[] { category, total_ars }` (sorted by total descending)
- **Business Rules:** BR-002, BR-019, BR-025

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
- **Result:** `200` → `TransferCalculationResponse`:

  | Field | Type | Meaning |
  |---|---|---|
  | `year_month` | str | The requested month. |
  | `ingresos` | `IngresoItem[]` | `{ person_id, person_name, amount }` — incomes per person (BR-001 input). |
  | `total_ingresos` | float | Sum of all incomes for the month. |
  | `total_common_expenses` | float | Sum of common (`is_common`) installment amounts in ARS (BR-001 step 1). |
  | `total_personal_expenses` | float | Sum of personal (non-common) installment amounts in ARS, attributed per BR-017. |
  | `gastos_por_persona` | `GastoPersonaItem[]` | Per-person breakdown — see below. |
  | `transferencias` | `TransferenciaItem[]` | `{ from_person, to_person, amount }` — the suggested transfers to balance the month. |
  | `is_balanced` | bool | `true` if `|balance_delta| ≤ 0.01` (BR-001 step 9). |
  | `balance_delta` | float | Sum of all per-person `difference` values (should be ~0 — INV-014). |
  | `transferencias_internas` | `DebtTransferRead[]` | DebtTransfers already recorded for the month, used as the adjustment (BR-021). |

  **`GastoPersonaItem`** `{ person_id, person_name, ... }`:

  | Field | Meaning |
  |---|---|
  | `paid_amount` | What this person actually paid (installments allocated via `PurchasePayer` shares, BR-001 step 6). |
  | `common_paid` | Portion of `paid_amount` that went to **common** expenses. |
  | `common_should_pay` | This person's fair share of `total_common_expenses` (the pool split). |
  | `should_pay` | What they *should* have paid = `Income − Target Cash` (BR-001 step 5). |
  | `adjustment` | Net DebtTransfer activity = sent − received (BR-021). |
  | `difference` | `(paid_amount − should_pay) + adjustment` (BR-001 step 7). `< 0` underpaid, `> 0` overpaid. |

- **Business Rules:** BR-001, BR-017, BR-021
- **Edge Cases:** No incomes for the month → `404 "No incomes found for this month"`.

### UC-037: Export Dashboard to Excel

- **Endpoint:** `GET /api/reports/export-excel`
- **Query Params:** `year_month` (required)
- **Steps:** Generates an XLSX file with sheets: Balance, Gastos por Persona, Transferencias, Detalle del Mes, Mes Siguiente (forecast), Deudas de Terceros.
- **Result:** `200` → binary XLSX file with `Content-Disposition: attachment; filename=reporte_YYYY-MM.xlsx`
- **Business Rules:** Uses same data as UC-035, UC-036, UC-030, UC-034.

### UC-038: Recurring Expenses

- **Endpoint:** `GET /api/reports/recurring-expenses`
- **Query Params:** `min_occurrences` (default 3)
- **Steps:** Groups purchases by normalized description (BR-020) + currency; returns groups that appear in at least `min_occurrences` distinct months.
- **Result:** `200` → `RecurringExpenseRow[] { description, category?, currency, occurrences, total_purchases, avg_amount, months[], last_seen }`
- **Business Rules:** BR-020 (normalization)

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

### UC-053: Extracción de Comprobante (Claude Vision)

- **Endpoint:** `POST /api/import/comprobante`
- **Form Params:** `file` (UploadFile — `image/png|jpeg|gif|webp` o `application/pdf`)
- **Steps:**
  1. Validate content type; reject unsupported → `400`
  2. Send file to Claude Vision API (`ANTHROPIC_API_KEY`) for extraction
  3. Match extracted nombre/CBU/CUIT/alias against `Beneficiary` table (exact/fuzzy)
- **Result:** `200` → `ComprobanteExtraction { amount, date, currency, description, matched_beneficiary, raw_extracted { nombre, cbu, cuit, alias } }`
- **Notes:** The file is not persisted. No purchase is created — the frontend pre-fills `PurchaseForm` and the user confirms manually.

### UC-054: Compartir Comprobante desde Android (Web Share Target)

- **Flow:** The frontend is an installable PWA (`manifest.webmanifest` with `share_target`). On Android, sharing an image/PDF to the installed app POSTs it to `/share-target` (multipart, field `file`).
- **Steps:**
  1. The service worker (`frontend/public/sw.js`) intercepts `POST /share-target`, stashes the file in Cache API (`shared-comprobante`), and responds `303 → /nueva-transferencia?shared=1` — the request never reaches the backend
  2. The `/nueva-transferencia` page retrieves and deletes the stashed file (`retrieveSharedFile()` in `frontend/src/utils/sharedFile.ts`)
  3. The file is injected into `PurchaseForm` (`initialFile` prop) with `payment_method: 'transfer'`, triggering UC-053 extraction and auto-fill
  4. The user confirms and saves manually (confirm-before-save)
- **Backend fallback:** `POST /share-target` (no auth) returns `303 → /nueva-transferencia` discarding the file, for the case where the SW is not controlling the page.
- **Auth exemptions:** `/manifest.webmanifest`, `/sw.js`, `/icons/*` and `/share-target` are exempt from Basic Auth (Chrome fetches manifest/icons without credentials; a 401 makes the PWA non-installable). See `PUBLIC_PATHS` in `backend/app/main.py`.
- **SPA fallback:** `SPAStaticFiles` in `main.py` serves `index.html` for client-side deep links (e.g. `/nueva-transferencia`); API 404s are not masked.

### UC-055: Detect Card from Statement File

- **Endpoint:** `POST /api/import/detect`
- **Form Params:** `file` (UploadFile — `.xlsx`/`.xls`/`.pdf`), `password?` (str, for encrypted PDFs)
- **Steps:**
  1. Validate extension; unsupported → `400`
  2. Parse the file (XLSX or PDF) and extract a holder hint (nombre, last4, card type, bank)
  3. Match the holder against existing `Card` records to suggest a card; detect the statement month from the parsed rows
  4. **Nothing is created** — this is a pre-flight to pre-select the card/provider in the Import UI
- **Result:** `200` → `{ detected_holder, detected_last4, detected_card_type, detected_bank, suggested_card_id, suggested_card_name, statement_year_month, row_count }`
- **Edge Cases:** Wrong extension → `400`; parse failure → `500`.

### UC-056: List Import Batches

- **Endpoint:** `GET /api/import/batches`
- **Steps:** Returns the history of import runs (`ImportBatch`), joined with `Card` for the card name.
- **Result:** `200` → `ImportBatchRead[] { id, imported_at, provider, source_file, card_id, card_name?, statement_year_month?, purchases_created, purchases_skipped, purchases_parsed }`
- **Notes:** Each purchase created by a run carries `import_batch_id`; the Purchases page can filter by it (UC-025).

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

### UC-067: Ahorros Page (`/ahorros`)

**Actor:** User  
**Goal:** View, manage, and track historical values of personal savings and investments.

**Main Flow:**
1. User navigates to `/ahorros`.
2. System displays a table of all savings showing owner, type, institution, currency, current amount, and last updated date.
3. User can click "Actualizar valor" on any row to open an inline form; enters date and amount to create a new `SavingSnapshot`.
4. User can delete a saving (with confirmation); all associated snapshots are also deleted.
5. The history chart panel shows checkboxes for each saving; user selects one or more to display their historical snapshots as lines on a Recharts LineChart.
6. The new saving form allows creation of a saving with owner (person), investment type, institution, currency, and optional notes.

### UC-068: Goals Page (`/goals`)

- **Features:**
  - List of family goals with title, description, target amount, due month, priority, completion status (UC-080)
  - Create goal form (UC-081)
  - Inline edit / mark complete (UC-082)
  - Delete goal with confirmation (UC-083)

### UC-070: List Savings

**Actor:** Frontend  
**Trigger:** `GET /api/savings`  
**Returns:** `list[SavingRead]` — each item includes `current_amount` and `current_amount_date` from the most recent `SavingSnapshot` (null if no snapshots exist), ordered by `saving.id` ASC.

### UC-071: Create Saving

**Actor:** User  
**Trigger:** `POST /api/savings` with `SavingCreate` payload  
**Rules:**
- `person_id` must reference an existing `Person` — raises `ValueError` (→ HTTP 400) if not found.
- Returns `SavingRead` with `current_amount = null`.

### UC-072: Update Saving

**Actor:** User
**Trigger:** `PATCH /api/savings/{saving_id}` with `SavingUpdate { investment_type?, institution?, notes? }`
**Rules:**
- Updates only the provided fields. `currency` and `person_id` are **not** editable.
- Returns `SavingRead` with `current_amount`/`current_amount_date` recomputed from the latest `SavingSnapshot`.
- Raises `ValueError` (→ HTTP 404) if the saving is not found.

### UC-073: Delete Saving (Cascade)

**Actor:** User  
**Trigger:** `DELETE /api/savings/{id}`  
**Rules:**
- All `SavingSnapshot` records for that saving are deleted first (raw SQL, manual cascade).
- Then the `Saving` record is deleted.
- Raises `ValueError` (→ HTTP 404) if saving not found.

### UC-074: List Snapshot History

**Actor:** Frontend  
**Trigger:** `GET /api/savings/{id}/snapshots`  
**Returns:** `list[SavingSnapshotRead]` ordered by `date` ASC.

### UC-075: Add Snapshot

**Actor:** User  
**Trigger:** `POST /api/savings/{id}/snapshots` with `SavingSnapshotCreate`  
**Rules:**
- `amount` must be `> 0` (Pydantic validation, → HTTP 422 if violated).
- `saving_id` must reference an existing `Saving` — raises `ValueError` (→ HTTP 404) if not found.

### UC-076: Delete Snapshot

**Trigger:** `DELETE /api/savings/{saving_id}/snapshots/{snapshot_id}`
**Rules:** Deletes the snapshot; `204` on success, `404` if not found.

### UC-077: List Savings Exchange Rates

**Trigger:** `GET /api/savings-exchange-rate`
**Returns:** `list[SavingsExchangeRateRead] { id, date, usd_buy, usd_sell }`.

### UC-078: Create Savings Exchange Rate

**Trigger:** `POST /api/savings-exchange-rate` with `{ date (YYYY-MM-DD), usd_buy, usd_sell }`
**Rules:** `usd_buy > 0`, `usd_sell > 0` (→ 422). Stores a manual USD buy/sell quote for valuing mixed-currency savings (UC-079).

### UC-079: Savings Total History

**Trigger:** `GET /api/savings/total-history`
**Steps:** For each date on which any `SavingSnapshot` exists, forward-fills each saving's last known value and sums by currency. Converts the combined total to ARS and to USD using the closest **prior** `SavingsExchangeRate`.
**Returns:** `list[SavingsTotalHistoryPoint] { date, total_ars, total_usd, total_in_ars?, total_in_usd? }`. The `total_in_*` fields are `null` when no exchange rate is available for/before that date.

---

## 9b. Use Cases — Family Goals

### UC-080: List Goals

- **Endpoint:** `GET /api/goals`
- **Result:** `200` → `FamilyGoalRead[]`

### UC-081: Create Goal

- **Endpoint:** `POST /api/goals`
- **Payload:** `FamilyGoalCreate { title, description?, target_amount?, due_date? (YYYY-MM), notes?, priority? }`
- **Result:** `201` → `FamilyGoalRead`

### UC-082: Update Goal

- **Endpoint:** `PATCH /api/goals/{goal_id}`
- **Payload:** `FamilyGoalUpdate { title?, description?, target_amount?, due_date?, is_completed?, notes?, priority? }`
- **Result:** `200` → `FamilyGoalRead`
- **Edge Cases:** Not found → `404`.

### UC-083: Delete Goal

- **Endpoint:** `DELETE /api/goals/{goal_id}`
- **Result:** `204` No Content
- **Edge Cases:** Not found → `404`.

---

## 9c. Use Cases — Card Statements

### UC-090: List Card Statements

- **Endpoint:** `GET /api/card-statements`
- **Query Params:** `card_id` (required)
- **Result:** `200` → `CardStatementRead[] { id, card_id, year_month, closing_date, due_date? }`

### UC-091: Suggest First Installment Month

- **Endpoint:** `GET /api/card-statements/suggest-month`
- **Query Params:** `card_id` (required), `purchase_date` (required)
- **Steps:** Applies BR-027 to suggest the billing-cycle month for a purchase.
- **Result:** `200` → `SuggestMonthResponse { year_month, closing_date?, fallback }` — `fallback=true` means no matching statement existed and the next-calendar-month heuristic was used.
- **Business Rules:** BR-027

### UC-092: Upsert Card Statement

- **Endpoint:** `POST /api/card-statements`
- **Payload:** `CardStatementCreate { card_id, year_month, closing_date, due_date? }`
- **Steps:** Upserts by `(card_id, year_month)` — updates `closing_date`/`due_date` if a record exists, else creates.
- **Result:** `200` → `CardStatementRead`
- **Validation:** `year_month` matches `YYYY-MM`.

### UC-093: Delete Card Statement

- **Endpoint:** `DELETE /api/card-statements/{statement_id}`
- **Result:** `204` No Content
- **Edge Cases:** Not found → `404`.

---

## 9d. Use Cases — Operations

### UC-100: Download Database Backup

- **Endpoint:** `GET /api/backup/db`
- **Auth:** `Authorization: Bearer <BACKUP_TOKEN>` (env var). Separate from the app's Basic Auth.
- **Steps:**
  1. If `BACKUP_TOKEN` is not configured → `503 "Backup not configured"`
  2. If the bearer token is missing/invalid (constant-time compare) → `401 "Unauthorized"`
  3. Take a consistent SQLite snapshot via `sqlite3.Connection.backup()` into a temp file, then stream it (deleting the temp file afterwards)
- **Result:** `200` → binary `application/octet-stream`, `Content-Disposition: attachment; filename=app_YYYY-MM-DD.db`
- **Edge Cases:** DB file missing → `503 "Database not found"`.
- **Notes:** Used by the local backup script (`backup_railway.sh` + launchd plist). Documented as ops tooling, not a user-facing page.

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
| `POST` | `/api/import/comprobante` | UC-053 | Extract comprobante data (Claude Vision) |
| `POST` | `/share-target` | UC-054 | Web Share Target fallback (303 redirect, no auth) |
| `GET` | `/api/savings` | UC-070 | List savings with current value |
| `POST` | `/api/savings` | UC-071 | Create saving |
| `PATCH` | `/api/savings/{id}` | UC-072 | Update saving |
| `DELETE` | `/api/savings/{id}` | UC-073 | Delete saving and cascade snapshots |
| `GET` | `/api/savings/{id}/snapshots` | UC-074 | List snapshot history for a saving |
| `POST` | `/api/savings/{id}/snapshots` | UC-075 | Add snapshot to saving |
| `DELETE` | `/api/savings/{id}/snapshots/{snapshot_id}` | UC-076 | Delete snapshot |
| `GET` | `/api/beneficiaries` | UC-014 | List beneficiaries |
| `POST` | `/api/beneficiaries` | UC-015 | Create beneficiary |
| `PUT` | `/api/beneficiaries/{id}` | UC-016 | Update beneficiary |
| `DELETE` | `/api/beneficiaries/{id}` | UC-017 | Delete beneficiary |
| `GET` | `/api/purchases/categorization-rules` | UC-026 | Categorization rules (keyword + learned) |
| `GET` | `/api/reports/recurring-expenses` | UC-038 | Recurring expenses |
| `POST` | `/api/import/detect` | UC-055 | Detect card from statement file |
| `GET` | `/api/import/batches` | UC-056 | List import batches |
| `GET` | `/api/goals` | UC-080 | List family goals |
| `POST` | `/api/goals` | UC-081 | Create family goal |
| `PATCH` | `/api/goals/{id}` | UC-082 | Update family goal |
| `DELETE` | `/api/goals/{id}` | UC-083 | Delete family goal |
| `GET` | `/api/savings/total-history` | UC-079 | Savings total history (FX-converted) |
| `GET` | `/api/savings-exchange-rate` | UC-077 | List savings USD quotes |
| `POST` | `/api/savings-exchange-rate` | UC-078 | Create savings USD quote |
| `GET` | `/api/card-statements` | UC-090 | List card statements |
| `GET` | `/api/card-statements/suggest-month` | UC-091 | Suggest first installment month |
| `POST` | `/api/card-statements` | UC-092 | Upsert card statement |
| `DELETE` | `/api/card-statements/{id}` | UC-093 | Delete card statement |
| `GET` | `/api/backup/db` | UC-100 | Download SQLite backup (Bearer token) |

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
5. **INV-005:** For any purchase with `installments_total = N`, there exist **at most** N `InstallmentSchedule` entries, and `(purchase_id, installment_index)` is unique (BR-026). A fully-imported purchase has exactly N; a partially re-imported one may have fewer until all monthly statements are imported. The previous wording ("additional installments could be added by re-import") no longer holds — the `ux_installment_purchase_index` UNIQUE index prevents duplicate indices.
6. **INV-006:** `MonthlyBudget.year_month` is unique — at most one budget per month.
7. **INV-007:** `Category.name` is unique.
8. **INV-008:** If `Purchase.payment_method == CARD`, then `Purchase.card_id IS NOT NULL`.
9. **INV-009:** Every `Purchase` has at least one `PurchasePayer` entry.
10. **INV-010:** `PRAGMA foreign_keys = ON` is enforced on every SQLite connection.
11. **INV-011:** When a `Category` is renamed, no `Purchase` retains the old category name.
12. **INV-012:** When a `Category` is deleted, all formerly-associated `Purchase.category` values become `NULL`.
13. **INV-013:** All monetary amounts are rounded to 2 decimal places in output.
14. **INV-014:** The sum of all `difference` values in a transfer calculation equals `balance_delta`, which should be ≤ 0.01 for a balanced month.
15. **INV-015:** `(InstallmentSchedule.purchase_id, installment_index)` is unique — no purchase has two schedule entries for the same installment index (BR-026).
16. **INV-016:** `(CardStatement.card_id, year_month)` is unique — at most one statement record per card per month.
17. **INV-017:** Every `Purchase.import_batch_id`, when set, points to an existing `ImportBatch`.

### Startup Migrations (`db.py`)

Run on every startup, idempotent:
- `_migrate_add_columns()`: adds `purchase.debtor_id`, `purchase.debt_settled`, `purchase.beneficiary_person_id`, `purchase.import_batch_id` (+ index), and creates the `beneficiary` table if missing. Guarded via `PRAGMA table_info`.
- `_migrate_dedupe_installments()`: removes duplicate `(purchase_id, installment_index)` rows, then creates `UNIQUE INDEX ux_installment_purchase_index` (BR-026).

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

---

## 14. Automated Processes (outside the HTTP API)

These run independently of the FastAPI app and write to the same SQLite DB.

### AP-001: Gmail → DB Ingestion (Cowork Scheduled Task)

- **Definition:** `.claude/tasks/gmail-gastos-a-db.md` (run by Cowork via the Claude Agent SDK with the Gmail MCP).
- **What it does:** Reads unread emails (luduenajp@gmail.com), extracts card purchases and bank transfers, and inserts them directly into `data/app.db` as `Purchase` (+ `PurchasePayer` + `InstallmentSchedule`) rows.
- **Sources:** Santander "Pagaste $X" (card, Pablo), Santander "Tu adicional hizo un consumo" (card, Cintia), Santander/BNA "Aviso de transferencia" and MercadoPago "Tu transferencia fue enviada" (`payment_method=TRANSFER`).
- **Ignored:** promos, summaries, and transfers where the recipient is Pablo himself (CUIL 20339576786).
- **De-duplication:** dual mechanism — `data/gmail_processed_ids.json` (per messageId) plus a DB query by date/description/amount.
- **`first_installment_month`:** card purchases → month **after** purchase date; transfers → **same** month as the transfer date.
- **Safety:** operates on a temp copy (`/tmp/admin_consumos_work.db`) then copies back, to avoid writes on the FUSE mount.
- **Schema coupling:** changes to `purchase` / `installmentschedule` / `purchasepayer` must be mirrored in the task's "Schema" section.

### AP-002: Local DB Backup (launchd)

- **Mechanism:** `backup_railway.sh` + a launchd plist call `GET /api/backup/db` (UC-100) with the `BACKUP_TOKEN` bearer and store a timestamped snapshot under `backups/railway/`.

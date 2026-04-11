export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface Person {
  id: number
  name: string
}

export interface Card {
  id: number
  name: string
  provider: string
  owner_person_id: number
  last4?: string | null
}

export type CurrencyCode = 'ARS' | 'USD'
export type PaymentMethod = 'card' | 'transfer' | 'cash'

export interface PurchasePayer {
  person_id: number
  person_name: string
  share_type: 'percent' | 'fixed'
  share_value: number
}

export interface Purchase {
  id: number
  card_id?: number | null
  payment_method: PaymentMethod
  purchase_date: string
  description: string
  currency: CurrencyCode
  amount_original: number
  installments_total: number
  installment_amount_original?: number | null
  first_installment_month?: string | null
  owner_person_id?: number | null
  category?: string | null
  notes?: string | null
  is_refund: boolean
  is_common: boolean
  debtor_id?: number | null
  beneficiary_person_id?: number | null
  debt_settled: boolean
  import_batch_id?: number | null
  payers: PurchasePayer[]
}

export interface FxRate {
  id: number
  year_month: string
  currency: CurrencyCode
  rate_to_ars: number
}

export interface MonthlyReportRow {
  year_month: string
  total_ars: number
}

export interface MonthBreakdownRow {
  purchase_id: number
  purchase_date: string
  description: string
  notes?: string | null
  category: string | null
  payer_name?: string | null
  payment_method?: string | null
  card_name?: string | null
  installment_index: number
  installments_total: number
  amount_ars: number
  amount_original: number
  currency: string
  debtor_id?: number | null
  debtor_name?: string | null
  beneficiary_person_id?: number | null
  debt_settled: boolean
  is_common: boolean
}

export interface MonthBreakdownResponse {
  year_month: string
  total_ars: number
  items: MonthBreakdownRow[]
}

export interface ImportResult {
  created: number
  skipped: number
  parsed: number
  batch_id?: number
}

export interface ImportBatch {
  id: number
  imported_at: string
  provider: string
  source_file: string
  card_id?: number | null
  card_name?: string | null
  statement_year_month?: string | null
  purchases_created: number
  purchases_skipped: number
  purchases_parsed: number
}

export interface PersonCreate {
  name: string
}

export interface CardCreate {
  name: string
  provider: string
  owner_person_id: number
  last4?: string | null
}

export interface FxRateUpsert {
  year_month: string
  currency: CurrencyCode
  rate_to_ars: number
}

export interface PurchaseCreate {
  card_id?: number | null
  payment_method: PaymentMethod
  purchase_date: string
  description: string
  currency: CurrencyCode
  amount_original: number
  installments_total?: number
  installment_amount_original?: number | null
  first_installment_month?: string | null
  owner_person_id?: number | null
  category?: string | null
  notes?: string | null
  is_refund?: boolean
  is_common?: boolean
  debtor_id?: number | null
  beneficiary_person_id?: number | null
  payers?: {
    person_id: number
    share_type: 'percent' | 'fixed'
    share_value: number
  }[]
}

export interface TimelineRow {
  year_month: string
  total_ars: number
}

export interface Category {
  id: number
  name: string
  color?: string | null
}

export interface CategoryCreate {
  name: string
  color?: string | null
}

export interface CategoryUpdate {
  name?: string | null
  color?: string | null
}

export interface CategorySpendingRow {
  category: string
  total_ars: number
}

export interface PurchaseUpdate {
  notes?: string | null
  category?: string | null
  is_common?: boolean
  debtor_id?: number | null
  beneficiary_person_id?: number | null
  debt_settled?: boolean
}

export interface Debtor {
  id: number
  name: string
}

export interface DebtorCreate {
  name: string
}

export interface DebtSummaryRow {
  debtor_id: number
  debtor_name: string
  total_owed: number
  total_settled: number
  pending_purchases: number
}

export interface MonthlyBudget {
  id: number
  year_month: string
  total_income: number
  notes?: string | null
}

export interface MonthlyBudgetCreate {
  year_month: string
  total_income: number
  notes?: string | null
}

export interface MonthlyBalanceResponse {
  year_month: string
  presupuesto: number
  gastos_acumulados: number
  sobrante_total: number
  sobrante_por_persona: number
  porcentaje_gastado: number
}

export interface Income {
  id: number
  person_id: number
  person_name: string
  year_month: string
  amount: number
  notes?: string | null
}

export interface IncomeCreate {
  person_id: number
  year_month: string
  amount: number
  notes?: string | null
}

export interface TransferCalculationResponse {
  year_month: string
  ingresos: Array<{ person_id: number, person_name: string, amount: number }>
  total_ingresos: number
  total_common_expenses: number
  total_personal_expenses: number
  gastos_por_persona: Array<{
    person_id: number
    person_name: string
    paid_amount: number
    common_paid: number
    common_should_pay: number
    should_pay: number
    adjustment: number
    difference: number
  }>
  transferencias: Array<{ from_person: string, to_person: string, amount: number }>
  is_balanced: boolean
  balance_delta: number
  transferencias_internas: DebtTransfer[]
}

export interface DebtTransfer {
  id: number
  from_person_id: number
  from_person_name: string
  to_person_id: number
  to_person_name: string
  year_month: string
  amount: number
  transfer_date: string
  notes?: string | null
}

export interface DebtTransferCreate {
  from_person_id: number
  to_person_id: number
  year_month: string
  amount: number
  transfer_date?: string
  notes?: string | null
}

export interface GSheetsImportRequest {
  url: string
  owner_person_id: number
  is_common: boolean
}

export interface RecurringExpenseRow {
  description: string
  category: string | null
  currency: string
  occurrences: number
  total_purchases: number
  avg_amount: number
  months: string[]
  last_seen: string
}

export interface FamilyGoal {
  id: number
  title: string
  description?: string | null
  target_amount?: number | null
  due_date?: string | null
  is_completed: boolean
  notes?: string | null
  priority?: string | null
}

export interface FamilyGoalCreate {
  title: string
  description?: string | null
  target_amount?: number | null
  due_date?: string | null
  notes?: string | null
  priority?: string | null
}

export interface FamilyGoalUpdate {
  title?: string | null
  description?: string | null
  target_amount?: number | null
  due_date?: string | null
  is_completed?: boolean | null
  notes?: string | null
  priority?: string | null
}

export interface Saving {
  id: number
  person_id: number
  investment_type: string
  institution: string
  currency: CurrencyCode
  notes?: string | null
  current_amount?: number | null
  current_amount_date?: string | null
}

export interface SavingCreate {
  person_id: number
  investment_type: string
  institution: string
  currency: CurrencyCode
  notes?: string | null
}

export interface SavingUpdate {
  investment_type?: string | null
  institution?: string | null
  notes?: string | null
}

export interface SavingSnapshot {
  id: number
  saving_id: number
  date: string
  amount: number
}

export interface SavingSnapshotCreate {
  date: string
  amount: number
}

export interface SavingsExchangeRate {
  id: number
  date: string
  usd_buy: number
  usd_sell: number
}

export interface SavingsExchangeRateCreate {
  date: string
  usd_buy: number
  usd_sell: number
}

export interface SavingsTotalHistoryPoint {
  date: string
  total_ars: number
  total_usd: number
  total_in_ars: number | null
  total_in_usd: number | null
}

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

export interface Purchase {
  id: number
  card_id: number
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
  debtor_id?: number | null
  debt_settled: boolean
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
  category: string | null
  installment_index: number
  installments_total: number
  amount_ars: number
  currency: string
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

export interface TimelineRow {
  year_month: string
  total_ars: number
}

export interface CategoryRead {
  categories: string[]
}

export interface CategorySpendingRow {
  category: string
  total_ars: number
}

export interface PurchaseUpdate {
  notes?: string | null
  category?: string | null
  debtor_id?: number | null
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

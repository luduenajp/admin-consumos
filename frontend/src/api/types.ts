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

export interface ImportResult {
  created: number
  skipped: number
  parsed: number
}

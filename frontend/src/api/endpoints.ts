import { getJson, patchJson, postForm, postJson } from './http'
import type {
  Card,
  CategoryRead,
  CategorySpendingRow,
  Debtor,
  DebtorCreate,
  DebtSummaryRow,
  FxRate,
  ImportResult,
  MonthlyReportRow,
  MonthBreakdownResponse,
  PaginatedResponse,
  Person,
  Purchase,
  PurchaseUpdate,
  TimelineRow,
} from './types'

export function fetchPeople(): Promise<Person[]> {
  return getJson<Person[]>('/api/people')
}

export function createPerson(payload: { name: string }): Promise<Person> {
  return postJson<Person>('/api/people', payload)
}

export function fetchCards(): Promise<Card[]> {
  return getJson<Card[]>('/api/cards')
}

export function createCard(payload: {
  name: string
  provider: string
  owner_person_id: number
  last4?: string | null
}): Promise<Card> {
  return postJson<Card>('/api/cards', payload)
}

export function fetchPurchases(filters?: {
  yearMonth?: string
  category?: string
  startDate?: string
  endDate?: string
  minAmount?: number
  maxAmount?: number
  descriptionSearch?: string
  personId?: number
  page?: number
  pageSize?: number
}): Promise<PaginatedResponse<Purchase>> {
  const qs = new URLSearchParams()
  if (filters?.yearMonth) qs.set('year_month', filters.yearMonth)
  if (filters?.category) qs.set('category', filters.category)
  if (filters?.startDate) qs.set('start_date', filters.startDate)
  if (filters?.endDate) qs.set('end_date', filters.endDate)
  if (filters?.minAmount !== undefined) qs.set('min_amount', String(filters.minAmount))
  if (filters?.maxAmount !== undefined) qs.set('max_amount', String(filters.maxAmount))
  if (filters?.descriptionSearch) qs.set('description_search', filters.descriptionSearch)
  if (filters?.personId !== undefined) qs.set('person_id', String(filters.personId))
  if (filters?.page !== undefined) qs.set('page', String(filters.page))
  if (filters?.pageSize !== undefined) qs.set('page_size', String(filters.pageSize))
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return getJson<PaginatedResponse<Purchase>>(`/api/purchases${suffix}`)
}

export function fetchMonthBreakdown(params: {
  yearMonth: string
  cardId?: number
  personId?: number
}): Promise<MonthBreakdownResponse> {
  const qs = new URLSearchParams()
  qs.set('year_month', params.yearMonth)
  if (params.cardId) qs.set('card_id', String(params.cardId))
  if (params.personId) qs.set('person_id', String(params.personId))
  return getJson<MonthBreakdownResponse>(`/api/reports/month-breakdown?${qs.toString()}`)
}

export function fetchMonthlyReport(params?: { cardId?: number; personId?: number }): Promise<MonthlyReportRow[]> {
  const qs = new URLSearchParams()
  if (params?.cardId) qs.set('card_id', String(params.cardId))
  if (params?.personId) qs.set('person_id', String(params.personId))
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return getJson<MonthlyReportRow[]>(`/api/reports/monthly${suffix}`)
}

export function fetchTimeline(params?: {
  monthsAhead?: number
  cardId?: number
  personId?: number
}): Promise<TimelineRow[]> {
  const qs = new URLSearchParams()
  if (params?.monthsAhead) qs.set('months_ahead', String(params.monthsAhead))
  if (params?.cardId) qs.set('card_id', String(params.cardId))
  if (params?.personId) qs.set('person_id', String(params.personId))
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return getJson<TimelineRow[]>(`/api/reports/timeline${suffix}`)
}

export function fetchCategories(): Promise<CategoryRead> {
  return getJson<CategoryRead>('/api/categories')
}

export function fetchCategorySpending(params?: {
  cardId?: number
  personId?: number
}): Promise<CategorySpendingRow[]> {
  const qs = new URLSearchParams()
  if (params?.cardId) qs.set('card_id', String(params.cardId))
  if (params?.personId) qs.set('person_id', String(params.personId))
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return getJson<CategorySpendingRow[]>(`/api/reports/category-spending${suffix}`)
}

export function updatePurchase(id: number, payload: PurchaseUpdate): Promise<Purchase> {
  return patchJson<Purchase>(`/api/purchases/${id}`, payload)
}

export function fetchDebtors(): Promise<Debtor[]> {
  return getJson<Debtor[]>('/api/debtors')
}

export function createDebtor(payload: DebtorCreate): Promise<Debtor> {
  return postJson<Debtor>('/api/debtors', payload)
}

export function fetchDebtReport(): Promise<DebtSummaryRow[]> {
  return getJson<DebtSummaryRow[]>('/api/reports/debts')
}

export function fetchFxRates(): Promise<FxRate[]> {
  return getJson<FxRate[]>('/api/fx')
}

export function upsertFxRate(payload: { year_month: string; currency: 'USD' | 'ARS'; rate_to_ars: number }): Promise<FxRate> {
  return postJson<FxRate>('/api/fx', payload)
}

export function importVisaXlsx(payload: { provider: string; cardId: number; file: File }): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', payload.file)
  const url = `/api/import/visa-xlsx?provider=${encodeURIComponent(payload.provider)}&card_id=${encodeURIComponent(
    String(payload.cardId),
  )}`
  return postForm<ImportResult>(url, formData)
}

export function importVisaPdf(payload: {
  provider: string
  cardId: number
  file: File
  password?: string
}): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', payload.file)
  if (payload.password && payload.password.trim()) {
    formData.append('password', payload.password.trim())
  }
  const url = `/api/import/visa-pdf?provider=${encodeURIComponent(payload.provider)}&card_id=${encodeURIComponent(
    String(payload.cardId),
  )}`
  return postForm<ImportResult>(url, formData)
}

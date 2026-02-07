import { getJson, postForm, postJson } from './http'
import type { Card, FxRate, ImportResult, MonthlyReportRow, Person, Purchase } from './types'

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

export function fetchPurchases(yearMonth?: string): Promise<Purchase[]> {
  const url = yearMonth ? `/api/purchases?year_month=${encodeURIComponent(yearMonth)}` : '/api/purchases'
  return getJson<Purchase[]>(url)
}

export function fetchMonthlyReport(params?: { cardId?: number; personId?: number }): Promise<MonthlyReportRow[]> {
  const qs = new URLSearchParams()
  if (params?.cardId) qs.set('card_id', String(params.cardId))
  if (params?.personId) qs.set('person_id', String(params.personId))
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return getJson<MonthlyReportRow[]>(`/api/reports/monthly${suffix}`)
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

import { deleteHttp, getJson, patchJson, postForm, postJson } from './http'
import type {
  Card,
  Category,
  CategoryCreate,
  CategoryUpdate,
  CategorySpendingRow,
  Debtor,
  DebtorCreate,
  DebtSummaryRow,
  FxRate,
  GSheetsImportRequest,
  ImportBatch,
  ImportResult,
  Income,
  IncomeCreate,
  MonthlyBalanceResponse,
  MonthlyBudget,
  MonthlyBudgetCreate,
  MonthlyReportRow,
  MonthBreakdownResponse,
  PaginatedResponse,
  Person,
  Purchase,
  PurchaseCreate,
  PurchaseUpdate,
  TimelineRow,
  TransferCalculationResponse,
  DebtTransfer,
  DebtTransferCreate,
  FamilyGoal,
  FamilyGoalCreate,
  FamilyGoalUpdate,
  Saving,
  SavingCreate,
  SavingUpdate,
  SavingSnapshot,
  SavingSnapshotCreate,
  SavingsExchangeRate,
  SavingsExchangeRateCreate,
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
  importBatchId?: number
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
  if (filters?.importBatchId !== undefined) qs.set('import_batch_id', String(filters.importBatchId))
  if (filters?.page !== undefined) qs.set('page', String(filters.page))
  if (filters?.pageSize !== undefined) qs.set('page_size', String(filters.pageSize))
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return getJson<PaginatedResponse<Purchase>>(`/api/purchases${suffix}`)
}

export function fetchImportBatches(): Promise<ImportBatch[]> {
  return getJson<ImportBatch[]>('/api/import/batches')
}

export function createPurchase(payload: PurchaseCreate): Promise<Purchase> {
  return postJson<Purchase>('/api/purchases', payload)
}

export function fetchMonthBreakdown(params: {
  yearMonth: string
  cardId?: number
  personId?: number
  isCommon?: boolean
}): Promise<MonthBreakdownResponse> {
  const qs = new URLSearchParams()
  qs.set('year_month', params.yearMonth)
  if (params.cardId) qs.set('card_id', String(params.cardId))
  if (params.personId) qs.set('person_id', String(params.personId))
  if (params.isCommon !== undefined) qs.set('is_common', String(params.isCommon))
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
  isCommon?: boolean
}): Promise<TimelineRow[]> {
  const qs = new URLSearchParams()
  if (params?.monthsAhead) qs.set('months_ahead', String(params.monthsAhead))
  if (params?.cardId) qs.set('card_id', String(params.cardId))
  if (params?.personId) qs.set('person_id', String(params.personId))
  if (params?.isCommon !== undefined) qs.set('is_common', String(params.isCommon))
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return getJson<TimelineRow[]>(`/api/reports/timeline${suffix}`)
}

export function fetchCategories(): Promise<Category[]> {
  return getJson<Category[]>('/api/categories')
}

export function fetchDistinctCategories(): Promise<string[]> {
  return getJson<string[]>('/api/categories/distinct')
}

export function createCategory(payload: CategoryCreate): Promise<Category> {
  return postJson<Category>('/api/categories', payload)
}

export function updateCategory(id: number, payload: CategoryUpdate): Promise<Category> {
  return patchJson<Category>(`/api/categories/${id}`, payload)
}

export function deleteCategory(id: number): Promise<void> {
  return deleteHttp(`/api/categories/${id}`)
}

export function autoCategorizePurchases(): Promise<{ updated: number }> {
  return postJson<{ updated: number }>('/api/purchases/auto-categorize', {})
}

export function fetchCategorySpending(params?: {
  cardId?: number
  personId?: number
  yearMonth?: string
  isCommon?: boolean
}): Promise<CategorySpendingRow[]> {
  const qs = new URLSearchParams()
  if (params?.cardId) qs.set('card_id', String(params.cardId))
  if (params?.personId) qs.set('person_id', String(params.personId))
  if (params?.yearMonth) qs.set('year_month', params.yearMonth)
  if (params?.isCommon !== undefined) qs.set('is_common', String(params.isCommon))
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return getJson<CategorySpendingRow[]>(`/api/reports/category-spending${suffix}`)
}

export function updatePurchase(id: number, payload: PurchaseUpdate): Promise<Purchase> {
  return patchJson<Purchase>(`/api/purchases/${id}`, payload)
}

export function bulkUpdatePurchases(payload: { purchase_ids: number[]; update: PurchaseUpdate }): Promise<{ updated: number }> {
  return postJson<{ updated: number }>('/api/purchases/bulk', payload)
}

export function deletePurchase(id: number): Promise<void> {
  return deleteHttp(`/api/purchases/${id}`)
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

export interface DetectImportResult {
  detected_holder: string | null
  detected_last4: string | null
  detected_card_type: string | null
  detected_bank: string | null
  suggested_card_id: number | null
  suggested_card_name: string | null
  statement_year_month: string | null
  row_count: number
}

export function detectImportCard(payload: { file: File; password?: string }): Promise<DetectImportResult> {
  const formData = new FormData()
  formData.append('file', payload.file)
  if (payload.password && payload.password.trim()) {
    formData.append('password', payload.password.trim())
  }
  return postForm<DetectImportResult>('/api/import/detect', formData)
}

export function importVisaXlsx(payload: { provider: string; cardId: number; file: File; is_common?: boolean }): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', payload.file)
  const url = `/api/import/visa-xlsx?provider=${encodeURIComponent(payload.provider)}&card_id=${encodeURIComponent(
    String(payload.cardId),
  )}&is_common=${payload.is_common ? 'true' : 'false'}`
  return postForm<ImportResult>(url, formData)
}

export function importVisaPdf(payload: {
  provider: string
  cardId: number
  file: File
  password?: string
  is_common?: boolean
}): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', payload.file)
  if (payload.password && payload.password.trim()) {
    formData.append('password', payload.password.trim())
  }
  const url = `/api/import/visa-pdf?provider=${encodeURIComponent(payload.provider)}&card_id=${encodeURIComponent(
    String(payload.cardId),
  )}&is_common=${payload.is_common ? 'true' : 'false'}`
  return postForm<ImportResult>(url, formData)
}

export function fetchBudgets(): Promise<MonthlyBudget[]> {
  return getJson<MonthlyBudget[]>('/api/budgets')
}

export function createBudget(payload: MonthlyBudgetCreate): Promise<MonthlyBudget> {
  return postJson<MonthlyBudget>('/api/budgets', payload)
}

export function fetchMonthlyBalance(yearMonth: string): Promise<MonthlyBalanceResponse> {
  return getJson<MonthlyBalanceResponse>(`/api/reports/monthly-balance?year_month=${yearMonth}`)
}

export function fetchIncomes(yearMonth?: string): Promise<Income[]> {
  const url = yearMonth ? `/api/incomes?year_month=${yearMonth}` : '/api/incomes'
  return getJson<Income[]>(url)
}

export function createIncome(payload: IncomeCreate): Promise<Income> {
  return postJson<Income>('/api/incomes', payload)
}

export function fetchTransferCalculation(yearMonth: string): Promise<TransferCalculationResponse> {
  return getJson<TransferCalculationResponse>(`/api/reports/transfers?year_month=${yearMonth}`)
}

export function importGSheets(payload: GSheetsImportRequest): Promise<ImportResult> {
  return postJson<ImportResult>('/api/import/gsheets', payload)
}

export function fetchDebtTransfers(yearMonth?: string): Promise<DebtTransfer[]> {
  const url = yearMonth ? `/api/debt-transfers?year_month=${yearMonth}` : '/api/debt-transfers'
  return getJson<DebtTransfer[]>(url)
}

export function createDebtTransfer(payload: DebtTransferCreate): Promise<DebtTransfer> {
  return postJson<DebtTransfer>('/api/debt-transfers', payload)
}

export function deleteDebtTransfer(id: number): Promise<void> {
  return deleteHttp(`/api/debt-transfers/${id}`)
}

export function fetchRecurringExpenses(minOccurrences: number = 3): Promise<import('./types').RecurringExpenseRow[]> {
  return getJson<import('./types').RecurringExpenseRow[]>(`/api/reports/recurring-expenses?min_occurrences=${minOccurrences}`)
}

export function fetchGoals(): Promise<FamilyGoal[]> {
  return getJson<FamilyGoal[]>('/api/goals')
}

export function createGoal(payload: FamilyGoalCreate): Promise<FamilyGoal> {
  return postJson<FamilyGoal>('/api/goals', payload)
}

export function updateGoal(id: number, payload: FamilyGoalUpdate): Promise<FamilyGoal> {
  return patchJson<FamilyGoal>(`/api/goals/${id}`, payload)
}

export function deleteGoal(id: number): Promise<void> {
  return deleteHttp(`/api/goals/${id}`)
}

export function fetchSavings(): Promise<Saving[]> {
  return getJson<Saving[]>('/api/savings')
}

export function createSaving(payload: SavingCreate): Promise<Saving> {
  return postJson<Saving>('/api/savings', payload)
}

export function updateSaving(id: number, payload: SavingUpdate): Promise<Saving> {
  return patchJson<Saving>(`/api/savings/${id}`, payload)
}

export function deleteSaving(id: number): Promise<void> {
  return deleteHttp(`/api/savings/${id}`)
}

export function fetchSavingSnapshots(savingId: number): Promise<SavingSnapshot[]> {
  return getJson<SavingSnapshot[]>(`/api/savings/${savingId}/snapshots`)
}

export function createSavingSnapshot(savingId: number, payload: SavingSnapshotCreate): Promise<SavingSnapshot> {
  return postJson<SavingSnapshot>(`/api/savings/${savingId}/snapshots`, payload)
}

export function deleteSavingSnapshot(savingId: number, snapshotId: number): Promise<void> {
  return deleteHttp(`/api/savings/${savingId}/snapshots/${snapshotId}`)
}

export function fetchSavingsExchangeRates(): Promise<SavingsExchangeRate[]> {
  return getJson<SavingsExchangeRate[]>('/api/savings-exchange-rate')
}

export function createSavingsExchangeRate(
  payload: SavingsExchangeRateCreate,
): Promise<SavingsExchangeRate> {
  return postJson<SavingsExchangeRate>('/api/savings-exchange-rate', payload)
}

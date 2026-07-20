import { describe, it, expect, vi, beforeEach } from 'vitest'
import '@testing-library/jest-dom'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DashboardPage } from './dashboard-page'
import { updatePurchase } from '../api/endpoints'
import type { MonthBreakdownResponse } from '../api/types'

const { breakdown } = vi.hoisted(() => {
  const breakdown: MonthBreakdownResponse = {
    year_month: '2026-07',
    total_ars: 15000,
    items: [
      {
        purchase_id: 1,
        purchase_date: '2026-07-05',
        description: 'super chino',
        notes: 'compra semanal',
        category: 'Supermercado',
        payer_name: 'Pablo',
        payment_method: 'card',
        card_name: 'Visa',
        installment_index: 1,
        installments_total: 1,
        amount_ars: 15000,
        amount_original: 15000,
        currency: 'ARS',
        debtor_id: null,
        debtor_name: null,
        beneficiary_person_id: null,
        debt_settled: false,
        is_common: false,
      },
    ],
  }
  return { breakdown }
})

vi.mock('../api/endpoints', () => ({
  fetchPeople: vi.fn().mockResolvedValue([]),
  fetchCards: vi.fn().mockResolvedValue([]),
  fetchMonthBreakdown: vi.fn().mockResolvedValue(breakdown),
  fetchTimeline: vi.fn().mockResolvedValue([]),
  fetchDebtReport: vi.fn().mockResolvedValue([]),
  updatePurchase: vi.fn().mockResolvedValue({}),
  deletePurchase: vi.fn(),
  fetchCategories: vi.fn().mockResolvedValue([]),
  fetchCategorySpending: vi.fn().mockResolvedValue([]),
  fetchBudgets: vi.fn().mockResolvedValue([]),
  fetchServicePaymentSummary: vi.fn().mockResolvedValue({ unpaid_count: 0, overdue_names: [], due_soon_names: [] }),
  fetchMonthlyBalance: vi.fn().mockResolvedValue(null),
  fetchTransferCalculation: vi.fn().mockResolvedValue(null),
  fetchRecurringExpenses: vi.fn().mockResolvedValue([]),
  fetchMonthlyReport: vi.fn().mockResolvedValue([]),
}))

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DashboardPage — editar desde la tabla de escritorio', () => {
  beforeEach(() => {
    vi.mocked(updatePurchase).mockClear()
  })

  it('abre el sheet de edición al clickear una fila de la tabla de escritorio y persiste la descripción editada', async () => {
    const user = userEvent.setup()
    renderDashboard()

    const rows = await screen.findAllByText('super chino')
    // La tabla de escritorio muestra la descripción dentro de un tooltip-container;
    // clickeamos el <tr> ascendiendo desde el texto encontrado en esa tabla.
    const tableRow = rows[rows.length - 1].closest('tr')
    expect(tableRow).not.toBeNull()
    await user.click(tableRow as HTMLElement)

    const descriptionInput = await screen.findByDisplayValue('super chino')
    await user.clear(descriptionInput)
    await user.type(descriptionInput, 'super nuevo')
    await user.tab()

    await waitFor(() => {
      expect(updatePurchase).toHaveBeenCalledWith(1, { description: 'super nuevo' })
    })
  })

  it('no llama a updatePurchase si la descripción no cambió', async () => {
    const user = userEvent.setup()
    renderDashboard()

    const rows = await screen.findAllByText('super chino')
    const tableRow = rows[rows.length - 1].closest('tr')
    await user.click(tableRow as HTMLElement)

    const descriptionInput = await screen.findByDisplayValue('super chino')
    await user.click(descriptionInput)
    await user.tab()

    await new Promise((r) => setTimeout(r, 50))
    expect(updatePurchase).not.toHaveBeenCalled()
  })
})

import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import {
  fetchPeople,
  fetchCards,
  fetchMonthBreakdown,
  fetchTimeline,
  fetchDebtReport,
  updatePurchase,
  deletePurchase,
  fetchCategories,
  fetchCategorySpending,
  fetchBudgets,
  fetchServicePaymentSummary,
} from '../api/endpoints'
import type { ServicePaymentSummary } from '../api/types'
import { Spinner } from '../components/Spinner'
import { TimelineChart } from '../components/TimelineChart'
import { CategoryChart } from '../components/CategoryChart'
import { MonthlyBalanceCard } from '../components/MonthlyBalanceCard'
import { TransferCalculationCard } from '../components/TransferCalculationCard'
import { KpiSummary } from '../components/KpiSummary'
import { MonthlyEvolutionChart } from '../components/MonthlyEvolutionChart'
import { RecurringExpensesCard } from '../components/RecurringExpensesCard'
import { PurchaseForm } from '../components/PurchaseForm'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { formatCurrency } from '../utils/format'
import { getCurrentYearMonth } from '../utils/dates'

function buildMonthOptions(): { value: string; label: string }[] {
  const now = new Date()
  const options: { value: string; label: string }[] = []
  const mesNombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
  for (let i = -6; i <= 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1)
    const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    options.push({ value: ym, label: `${mesNombres[d.getMonth()]} ${d.getFullYear()}` })
  }
  return options
}

export function DashboardPage() {
  const [personFilter, setPersonFilter] = useState<string>('')
  const [cardFilter, setCardFilter] = useState<string>('')
  const [monthFilter, setMonthFilter] = useState<string>(() => getCurrentYearMonth())
  const [expenseTypeFilter, setExpenseTypeFilter] = useState<string>('all')
  const [showAddForm, setShowAddForm] = useState(false)
  const [showTransferForm, setShowTransferForm] = useState(false)
  const [tableSearch, setTableSearch] = useState('')
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: 'asc' | 'desc' } | null>(null)
  const [mobileResumenSearch, setMobileResumenSearch] = useState('')
  const [mobileEditId, setMobileEditId] = useState<number | null>(null)
  const [mobileEditNotes, setMobileEditNotes] = useState('')
  const [mobileEditDescription, setMobileEditDescription] = useState('')
  const [pendingDelete, setPendingDelete] = useState<{ id: number; description: string } | null>(null)
  const personId = personFilter ? Number(personFilter) : undefined
  const cardId = cardFilter ? Number(cardFilter) : undefined
  const isCommon = expenseTypeFilter === 'all' ? undefined : expenseTypeFilter === 'common'
  const monthOptions = useMemo(() => buildMonthOptions(), [])

  const queryClient = useQueryClient()
  const { data: peopleData } = useQuery({
    queryKey: ['people'],
    queryFn: fetchPeople,
  })
  const people = peopleData ?? []

  const { data: cardsData } = useQuery({
    queryKey: ['cards'],
    queryFn: fetchCards,
  })
  const cards = cardsData ?? []


  const { data: timelineData, isLoading: timelineLoading } = useQuery({
    queryKey: ['reports', 'timeline', { personId, isCommon }],
    queryFn: () => fetchTimeline({ monthsAhead: 12, personId, isCommon }),
  })

  const { data: timelineCommon } = useQuery({
    queryKey: ['reports', 'timeline', { personId, isCommon: true }],
    queryFn: () => fetchTimeline({ monthsAhead: 12, personId, isCommon: true }),
  })

  const { data: timelinePersonal } = useQuery({
    queryKey: ['reports', 'timeline', { personId, isCommon: false }],
    queryFn: () => fetchTimeline({ monthsAhead: 12, personId, isCommon: false }),
  })

  const { data: budgetsData } = useQuery({
    queryKey: ['budgets'],
    queryFn: fetchBudgets,
  })

  const { data: debtData, isLoading: debtLoading } = useQuery({
    queryKey: ['reports', 'debts'],
    queryFn: fetchDebtReport,
  })

  const { data: monthBreakdownData, isLoading: monthBreakdownLoading } = useQuery({
    queryKey: ['reports', 'month-breakdown', { yearMonth: monthFilter, personId, cardId, isCommon }],
    queryFn: () => fetchMonthBreakdown({ yearMonth: monthFilter, personId, cardId, isCommon }),
  })

  const { data: categoriesData } = useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
  })

  const { data: categorySpendingData, isLoading: categorySpendingLoading } = useQuery({
    queryKey: ['reports', 'category-spending', { personId, yearMonth: monthFilter, isCommon }],
    queryFn: () => fetchCategorySpending({ personId, yearMonth: monthFilter, isCommon }),
  })

  const todayStr = useMemo(() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }, [])

  const { data: serviceSummary } = useQuery<ServicePaymentSummary>({
    queryKey: ['service-payment-summary', monthFilter, todayStr],
    queryFn: () => fetchServicePaymentSummary(monthFilter, todayStr),
  })

  const commonMutation = useMutation({
    mutationFn: ({ id, is_common }: { id: number; is_common: boolean }) => updatePurchase(id, { is_common }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      queryClient.invalidateQueries({ queryKey: ['transfer-calculation'] })
      queryClient.invalidateQueries({ queryKey: ['monthly-balance'] })
    },
  })

  const patchMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Parameters<typeof updatePurchase>[1] }) =>
      updatePurchase(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      queryClient.invalidateQueries({ queryKey: ['transfer-calculation'] })
      queryClient.invalidateQueries({ queryKey: ['monthly-balance'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deletePurchase(id),
    onSuccess: () => {
      setMobileEditId(null)
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      queryClient.invalidateQueries({ queryKey: ['transfer-calculation'] })
      queryClient.invalidateQueries({ queryKey: ['monthly-balance'] })
    },
  })

  const requestSort = (key: string) => {
    let direction: 'asc' | 'desc' = 'asc';
    if (sortConfig && sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const getSortIcon = (key: string) => {
    if (!sortConfig || sortConfig.key !== key) return ' ↕';
    return sortConfig.direction === 'asc' ? ' ↑' : ' ↓';
  };

  // Top 5 biggest expenses this month
  const top5 = useMemo(() => {
    if (!monthBreakdownData?.items) return []
    return [...monthBreakdownData.items]
      .sort((a, b) => b.amount_ars - a.amount_ars)
      .slice(0, 5)
  }, [monthBreakdownData])

  // Current month's budget total_income for the reference line
  const currentBudget = budgetsData?.find((b) => b.year_month === monthFilter)
  const monthlyIncome = currentBudget?.total_income

  // Filter table items by search
  const filteredItems = useMemo(() => {
    if (!monthBreakdownData?.items) return []
    if (!tableSearch.trim()) return monthBreakdownData.items
    const search = tableSearch.toLowerCase()
    return monthBreakdownData.items.filter(
      (row) =>
        row.description.toLowerCase().includes(search) ||
        (row.notes && row.notes.toLowerCase().includes(search)) ||
        (row.category && row.category.toLowerCase().includes(search))
    )
  }, [monthBreakdownData, tableSearch])

  return (
    <section className="page">
      <h2 className="pageTitle">Dashboard</h2>

      {/* Filters Container */}
      <div className="panel" style={{ padding: '24px' }}>
        <div className="dashboard-filters">
          <div className="formRow dashboard-filter-month" style={{ marginBottom: 0 }}>
            <label className="label">Mes a ver</label>
            <select
              className="input"
              value={monthFilter}
              onChange={(e) => setMonthFilter(e.target.value)}
            >
              {monthOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <div className="hint">Cuotas que vencen este mes</div>
          </div>
          {people.length > 0 && (
            <div className="formRow dashboard-filter-person" style={{ marginBottom: 0 }}>
              <label className="label">Ver gastos de</label>
              <select
                className="input"
                value={personFilter}
                onChange={(e) => setPersonFilter(e.target.value)}
              >
                <option value="">Todos</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <div className="hint">
                {personFilter ? `Pagado por ${people.find((x) => String(x.id) === personFilter)?.name}` : 'Totales combinados'}
              </div>
            </div>
          )}
          <div className="formRow dashboard-filter-type" style={{ marginBottom: 0 }}>
            <label className="label">Tipo de gasto</label>
            <select
              className="input"
              value={expenseTypeFilter}
              onChange={(e) => setExpenseTypeFilter(e.target.value)}
            >
              <option value="all">Todos</option>
              <option value="common">Comunes</option>
              <option value="personal">Personales</option>
            </select>
            <div className="hint">Filtro por tipo de gasto</div>
          </div>
          {cards.length > 0 && (
            <div className="formRow dashboard-filter-card" style={{ marginBottom: 0 }}>
              <label className="label">Tarjeta</label>
              <select
                className="input"
                value={cardFilter}
                onChange={(e) => setCardFilter(e.target.value)}
              >
                <option value="">Todas</option>
                {cards.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <div className="hint">Filtro por tarjeta</div>
            </div>
          )}
          <div className="dashboard-filters-actions">
            <button
              onClick={() => {
                setShowAddForm(!showAddForm)
                if (!showAddForm) setShowTransferForm(false)
              }}
              className="button"
              style={{ background: 'var(--color-primary)', color: 'white' }}
            >
              {showAddForm ? '✕ Cancelar' : '+ Nueva compra'}
            </button>
            <button
              onClick={() => {
                setShowTransferForm(!showTransferForm)
                if (!showTransferForm) setShowAddForm(false)
              }}
              className="button"
              style={{ background: 'var(--color-surface)', color: 'var(--color-primary)', border: '1px solid var(--color-primary)' }}
            >
              {showTransferForm ? '✕ Cancelar' : '+ Nueva transferencia'}
            </button>
            <button
              onClick={() => {
                window.location.href = `/api/reports/export-excel?year_month=${monthFilter}`
              }}
              className="button desktopOnly"
              style={{ background: 'var(--color-success)', color: 'white', borderColor: 'var(--color-success)', fontWeight: 600 }}
            >
              Exportar Excel
            </button>
          </div>
        </div>
      </div>

      {showAddForm && (
        <div className="panel" style={{ border: '1px solid var(--color-primary)', animation: 'fadeIn 0.3s ease' }}>
          <div className="panelTitle">Nueva compra</div>
          <PurchaseForm
            onSuccess={() => setShowAddForm(false)}
            onCancel={() => setShowAddForm(false)}
          />
        </div>
      )}
      {showTransferForm && (
        <div className="panel" style={{ border: '1px solid var(--color-primary)', animation: 'fadeIn 0.3s ease' }}>
          <div className="panelTitle">Nueva transferencia</div>
          <PurchaseForm
            initialValues={{ payment_method: 'transfer' }}
            onSuccess={() => setShowTransferForm(false)}
            onCancel={() => setShowTransferForm(false)}
          />
        </div>
      )}

      {/* Servicios sin pagar widget */}
      {serviceSummary && serviceSummary.unpaid_count > 0 && (
        <div style={{
          background: '#fffbeb',
          border: '1px solid #f59e0b',
          borderRadius: '0.5rem',
          padding: '0.875rem 1rem',
          marginBottom: '1rem',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '0.75rem',
        }}>
          <span style={{ fontSize: '1.1rem', flexShrink: 0 }}>⚠️</span>
          <div>
            <strong style={{ color: '#92400e' }}>
              {serviceSummary.unpaid_count} {serviceSummary.unpaid_count === 1 ? 'servicio sin pagar' : 'servicios sin pagar'}
            </strong>
            {(serviceSummary.overdue_names.length > 0 || serviceSummary.due_soon_names.length > 0) && (
              <div style={{ fontSize: '0.875rem', color: '#78350f', marginTop: '0.25rem' }}>
                {[
                  ...serviceSummary.overdue_names.map(n => `${n} (vencido)`),
                  ...serviceSummary.due_soon_names.map(n => `${n} (vence pronto)`),
                ].join(', ')}
              </div>
            )}
            <Link
              to="/servicios"
              style={{ fontSize: '0.875rem', color: '#b45309', fontWeight: 500, display: 'inline-block', marginTop: '0.25rem' }}
            >
              Ver servicios →
            </Link>
          </div>
        </div>
      )}

      {/* KPI Summary Cards */}
      <KpiSummary yearMonth={monthFilter} personId={personId} cardId={cardId} isCommon={isCommon} />

      {/* Mobile-only: Resumen del mes */}
      <div className="dashboard-mobile-section">
        <div className="panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
            <div className="panelTitle" style={{ marginBottom: 0 }}>
              Resumen del mes
            </div>
            <input
              type="text"
              className="input"
              placeholder="Buscar..."
              value={mobileResumenSearch}
              onChange={(e) => setMobileResumenSearch(e.target.value)}
              style={{ fontSize: '0.85rem', flex: 1, minWidth: 0 }}
            />
          </div>
          {monthBreakdownLoading ? (
            <div className="loadingContainer"><Spinner size={28} /></div>
          ) : !monthBreakdownData ? (
            <div className="muted">Sin datos</div>
          ) : (() => {
            const mobileItems = monthBreakdownData.items
              .filter((row) => {
                if (!mobileResumenSearch) return true
                const q = mobileResumenSearch.toLowerCase()
                return (
                  row.description.toLowerCase().includes(q) ||
                  (row.notes ?? '').toLowerCase().includes(q) ||
                  (row.category ?? '').toLowerCase().includes(q) ||
                  (row.payer_name ?? '').toLowerCase().includes(q) ||
                  (row.card_name ?? '').toLowerCase().includes(q) ||
                  (row.debtor_name ?? '').toLowerCase().includes(q) ||
                  (row.payment_method ?? '').toLowerCase().includes(q) ||
                  row.purchase_date.includes(q) ||
                  row.amount_ars.toString().includes(q) ||
                  (row.is_common ? 'común' : 'personal').includes(q)
                )
              })
              .slice()
              .sort((a, b) => b.purchase_date.localeCompare(a.purchase_date))
            if (mobileItems.length === 0) {
              return <div className="muted">{mobileResumenSearch ? 'Sin resultados' : 'Sin cuotas que venzan en este mes'}</div>
            }
            return (
              <div className="purchaseCardList" style={{ display: 'flex' }}>
                {mobileItems.map((row) => (
                  <div
                    key={`${row.purchase_id}-${row.installment_index}`}
                    className="purchaseCard"
                    onClick={() => { setMobileEditId(row.purchase_id); setMobileEditNotes(row.notes ?? ''); setMobileEditDescription(row.description) }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { setMobileEditId(row.purchase_id); setMobileEditNotes(row.notes ?? ''); setMobileEditDescription(row.description) } }}
                  >
                    <div className="purchaseCardHeader">
                      <span className="purchaseCardDescription">{row.description}</span>
                      <span className="purchaseCardAmount">{formatCurrency(row.amount_ars)}</span>
                    </div>
                    {row.notes && (
                      <div style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', marginBottom: '6px' }}>
                        {row.notes}
                      </div>
                    )}
                    <div className="purchaseCardChips">
                      <span className="purchaseChip purchaseChipNeutral">
                        {row.is_common ? 'Común' : 'Personal'}
                      </span>
                      {row.card_name && (
                        <span className="purchaseChip purchaseChipNeutral">{row.card_name}</span>
                      )}
                      {row.installments_total > 1 && (
                        <span className="purchaseChip purchaseChipInstallment">
                          {row.installment_index}/{row.installments_total}
                        </span>
                      )}
                      <span className="purchaseChip purchaseChipNeutral">{row.payer_name}</span>
                      <span className="purchaseChip purchaseChipNeutral">{row.purchase_date}</span>
                    </div>
                  </div>
                ))}
              </div>
            )
          })()}
        </div>
      </div>

      {/* Mobile edit sheet */}
      {(() => {
        const editRow = mobileEditId !== null ? monthBreakdownData?.items.find((r) => r.purchase_id === mobileEditId) ?? null : null
        if (!editRow) return null
        return (
          <div className="purchaseMobileEditOverlay" onClick={() => setMobileEditId(null)}>
            <div className="purchaseMobileEditSheet" onClick={(e) => e.stopPropagation()}>
              <div className="purchaseMobileEditHeader">
                <div>
                  <div style={{ fontWeight: 700, fontSize: '1rem' }}>{editRow.description}</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                    {formatCurrency(editRow.amount_ars)} · {editRow.purchase_date}
                  </div>
                </div>
                <button
                  type="button"
                  className="mobileMenuClose"
                  style={{ background: 'transparent', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}
                  onClick={() => setMobileEditId(null)}
                >✕</button>
              </div>
              <div className="purchaseMobileEditBody">
                <div className="formRow">
                  <label className="label">Descripción</label>
                  <input
                    type="text"
                    className="input"
                    value={mobileEditDescription}
                    placeholder="Descripción de la compra..."
                    onChange={(e) => setMobileEditDescription(e.target.value)}
                    onBlur={() => {
                      const trimmed = mobileEditDescription.trim()
                      if (trimmed && trimmed !== editRow.description) {
                        patchMutation.mutate({ id: editRow.purchase_id, payload: { description: trimmed } })
                      }
                    }}
                  />
                </div>
                <div className="formRow">
                  <label className="label">Categoría</label>
                  <select
                    className="input"
                    value={editRow.category ?? ''}
                    onChange={(e) => patchMutation.mutate({ id: editRow.purchase_id, payload: { category: e.target.value || null } })}
                  >
                    <option value="">-</option>
                    {categoriesData?.map((cat) => (
                      <option key={cat.id} value={cat.name}>{cat.name}</option>
                    ))}
                  </select>
                </div>
                <div className="formRow">
                  <label className="label" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <input
                      type="checkbox"
                      checked={editRow.is_common}
                      style={{ width: '18px', height: '18px' }}
                      onChange={(e) => patchMutation.mutate({ id: editRow.purchase_id, payload: { is_common: e.target.checked } })}
                    />
                    Gasto común
                  </label>
                </div>
                <div className="formRow">
                  <label className="label">Detalle / Notas</label>
                  <input
                    type="text"
                    className="input"
                    value={mobileEditNotes}
                    placeholder="Agregar detalle..."
                    onChange={(e) => setMobileEditNotes(e.target.value)}
                    onBlur={() => {
                      if (mobileEditNotes !== (editRow.notes ?? '')) {
                        patchMutation.mutate({ id: editRow.purchase_id, payload: { notes: mobileEditNotes || null } })
                      }
                    }}
                  />
                </div>
                <button
                  type="button"
                  className="button danger"
                  style={{ width: '100%', marginTop: '8px' }}
                  disabled={deleteMutation.isPending}
                  onClick={() => {
                    setMobileEditId(null)
                    setPendingDelete({ id: editRow.purchase_id, description: editRow.description })
                  }}
                >
                  Eliminar compra
                </button>
              </div>
            </div>
          </div>
        )
      })()}

      <ConfirmDialog
        open={pendingDelete !== null}
        message={pendingDelete ? `¿Eliminar "${pendingDelete.description}"? Esta acción no se puede deshacer.` : ''}
        confirmLabel="Eliminar"
        dangerous
        onConfirm={() => { if (pendingDelete) deleteMutation.mutate(pendingDelete.id); setPendingDelete(null) }}
        onCancel={() => setPendingDelete(null)}
      />

      <div className="dashboard-desktop-only">
      {/* Top Cards Grid */}
      <div className="dashboard-grid-2col">
        <MonthlyBalanceCard yearMonth={monthFilter} />
        <TransferCalculationCard yearMonth={monthFilter} />
      </div>

      {/* Top 5 + Resumen del mes */}
      <div className="dashboard-grid-sidebar">
        {/* Top 5 gastos */}
        <div className="panel">
          <div className="panelTitle">Top 5 Gastos</div>
          {top5.length === 0 ? (
            <div className="muted">Sin datos</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {top5.map((row, i) => (
                <div key={`${row.purchase_id}-${row.installment_index}`} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '10px 12px',
                  backgroundColor: i === 0 ? 'var(--color-primary-light)' : 'var(--color-bg)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--color-border)'
                }}>
                  <div style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '50%',
                    backgroundColor: i === 0 ? 'var(--color-primary)' : 'var(--color-border)',
                    color: i === 0 ? 'white' : 'var(--color-text-secondary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    flexShrink: 0
                  }}>
                    {i + 1}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: '0.85rem',
                      fontWeight: 600,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      {row.description}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                      {row.category || 'Sin cat.'} {row.card_name && `| ${row.card_name}`}
                    </div>
                  </div>
                  <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--color-text)', whiteSpace: 'nowrap' }}>
                    {formatCurrency(row.amount_ars)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Resumen del mes seleccionado */}
        <div className="panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
            <div className="panelTitle" style={{ marginBottom: 0 }}>Resumen del mes ({monthOptions.find((m) => m.value === monthFilter)?.label ?? monthFilter})</div>
            <input
              type="text"
              className="input"
              placeholder="Buscar en tabla..."
              value={tableSearch}
              onChange={(e) => setTableSearch(e.target.value)}
              style={{ maxWidth: '220px', fontSize: '0.85rem' }}
            />
          </div>
          {monthBreakdownLoading ? (
            <div className="loadingContainer">
              <Spinner size={28} />
            </div>
          ) : !monthBreakdownData ? (
            <div className="muted">Sin datos</div>
          ) : (
            <>
              {tableSearch && (
                <div style={{ fontSize: '0.9rem', color: 'var(--color-text-secondary)', marginBottom: '12px' }}>
                  {filteredItems.length} de {monthBreakdownData.items.length} resultados
                </div>
              )}
              {filteredItems.length === 0 ? (
                <div className="muted">
                  {tableSearch ? 'Sin resultados para la busqueda' : 'Sin cuotas que venzan en este mes'}
                </div>
              ) : (
                <div className="tableContainer">
                  <table className="table">
                    <thead>
                      <tr>
                        <th onClick={() => requestSort('purchase_date')} style={{ cursor: 'pointer', userSelect: 'none' }}>Fecha compra{getSortIcon('purchase_date')}</th>
                        <th onClick={() => requestSort('description')} style={{ cursor: 'pointer', userSelect: 'none' }}>Descripcion{getSortIcon('description')}</th>
                        <th onClick={() => requestSort('notes')} style={{ cursor: 'pointer', userSelect: 'none' }}>Detalle{getSortIcon('notes')}</th>
                        <th onClick={() => requestSort('debtor_name')} style={{ cursor: 'pointer', userSelect: 'none' }}>Deudor{getSortIcon('debtor_name')}</th>
                        <th onClick={() => requestSort('card_name')} style={{ cursor: 'pointer', userSelect: 'none' }}>Tarjeta{getSortIcon('card_name')}</th>
                        <th onClick={() => requestSort('installment_index')} style={{ cursor: 'pointer', userSelect: 'none' }}>Cuota{getSortIcon('installment_index')}</th>
                        <th onClick={() => requestSort('is_common')} style={{ cursor: 'pointer', userSelect: 'none', textAlign: 'center' }}>Comun{getSortIcon('is_common')}</th>
                        <th onClick={() => requestSort('amount_ars')} style={{ cursor: 'pointer', userSelect: 'none', textAlign: 'right' }}>Monto (ARS){getSortIcon('amount_ars')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredItems
                        .slice()
                        .sort((a, b) => {
                          if (sortConfig !== null) {
                            let aValue = a[sortConfig.key as keyof typeof a];
                            let bValue = b[sortConfig.key as keyof typeof b];
                            if (aValue === null || aValue === undefined) aValue = '';
                            if (bValue === null || bValue === undefined) bValue = '';
                            if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
                            if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
                            return 0;
                          }
                          return b.amount_ars - a.amount_ars;
                        })
                        .map((row) => (
                          <tr
                            key={`${row.purchase_id}-${row.installment_index}`}
                            onClick={() => {
                              setMobileEditId(row.purchase_id)
                              setMobileEditNotes(row.notes ?? '')
                              setMobileEditDescription(row.description)
                            }}
                            style={{ cursor: 'pointer' }}
                          >
                            <td>{row.purchase_date}</td>
                            <td>
                              <div className="tooltip-container">
                                <span style={{ borderBottom: '1px dotted var(--color-muted)', cursor: 'help' }}>
                                  {row.description}
                                </span>
                                <div className="tooltip-content">
                                  <div className="tooltip-header">
                                    <span>Detalles de Pago</span>
                                    <span style={{
                                      fontSize: '0.7rem',
                                      padding: '2px 6px',
                                      borderRadius: '4px',
                                      backgroundColor: row.is_common ? 'var(--color-primary-light)' : 'var(--color-bg)',
                                      color: row.is_common ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                                      border: '1px solid var(--color-border)'
                                    }}>
                                      {row.is_common ? 'Gasto Comun' : 'Gasto Particular'}
                                    </span>
                                  </div>
                                  <div className="tooltip-row">
                                    <span className="tooltip-label">Categoria:</span>
                                    <span className="tooltip-value">{row.category || 'Sin categoria'}</span>
                                  </div>
                                  <div className="tooltip-row">
                                    <span className="tooltip-label">Pagador:</span>
                                    <span className="tooltip-value">{row.payer_name}</span>
                                  </div>
                                  <div className="tooltip-row">
                                    <span className="tooltip-label">Metodo:</span>
                                    <span className="tooltip-value">
                                      {row.payment_method === 'card' ? 'Tarjeta' :
                                        row.payment_method === 'transfer' ? 'Transferencia' :
                                          row.payment_method === 'cash' ? 'Efectivo' : row.payment_method}
                                      {row.card_name && ` (${row.card_name})`}
                                    </span>
                                  </div>
                                  {(row.currency !== 'ARS' || row.amount_original !== row.amount_ars) && (
                                    <div className="tooltip-row">
                                      <span className="tooltip-label">Original:</span>
                                      <span className="tooltip-value">
                                        {String(row.currency).includes('.') ? String(row.currency).split('.').pop() : row.currency} {row.amount_original.toLocaleString('es-AR', { minimumFractionDigits: 2 })}
                                      </span>
                                    </div>
                                  )}
                                  {row.debtor_id && (
                                    <div className="tooltip-row" style={{ marginTop: '8px', padding: '4px', borderRadius: '4px', backgroundColor: 'var(--color-error-bg)' }}>
                                      <span className="tooltip-label" style={{ color: 'var(--color-error-text)' }}>Deudor:</span>
                                      <span className="tooltip-value" style={{ color: 'var(--color-error-text)' }}>
                                        {row.debtor_name} {row.debt_settled ? '(Saldado)' : '(Pendiente)'}
                                      </span>
                                    </div>
                                  )}
                                  <div className="tooltip-footer">
                                    Compra realizada el {row.purchase_date}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td>{row.notes ?? '-'}</td>
                            <td>
                              {row.debtor_name ? (
                                <span style={{ color: row.debt_settled ? 'var(--color-success)' : 'var(--color-error)', fontWeight: 500 }}>
                                  {row.debtor_name} {row.debt_settled ? '(Saldado)' : ''}
                                </span>
                              ) : (
                                '-'
                              )}
                            </td>
                            <td>{row.card_name ?? '-'}</td>
                            <td>
                              {row.installment_index}/{row.installments_total}
                            </td>
                            <td style={{ textAlign: 'center' }}>
                              <input
                                type="checkbox"
                                className="checkbox"
                                checked={row.is_common}
                                onChange={(e) => commonMutation.mutate({ id: row.purchase_id, is_common: e.target.checked })}
                                disabled={commonMutation.isPending}
                              />
                            </td>
                            <td style={{ textAlign: 'right', fontWeight: 500 }}>
                              ${row.amount_ars.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Charts Grid */}
      <div className="dashboard-grid-charts">
        {/* Category Chart Panel */}
        <div className="panel">
          <div className="panelTitle">Gasto por Categoria ({monthOptions.find((m) => m.value === monthFilter)?.label ?? monthFilter})</div>
          {categorySpendingLoading ? (
            <div className="loadingContainer">
              <Spinner size={28} />
            </div>
          ) : (
            <CategoryChart data={categorySpendingData ?? []} categories={categoriesData ?? []} />
          )}
        </div>

        {/* Monthly Evolution Chart */}
        <div className="panel">
          <div className="panelTitle">Evolucion Mensual de Gastos</div>
          <MonthlyEvolutionChart personId={personId} />
        </div>
      </div>

      {/* Timeline Panel */}
      <div className="panel">
        <div className="panelTitle">Cuotas Futuras (3 meses anteriores + 12 futuros)</div>
        {timelineLoading ? (
          <div className="loadingContainer">
            <Spinner size={28} />
          </div>
        ) : (
          <TimelineChart
            data={timelineData ?? []}
            commonData={isCommon === undefined ? timelineCommon : undefined}
            personalData={isCommon === undefined ? timelinePersonal : undefined}
            monthlyIncome={monthlyIncome}
          />
        )}
      </div>

      {/* Recurring Expenses */}
      <div className="panel">
        <div className="panelTitle">Gastos Recurrentes</div>
        <RecurringExpensesCard />
      </div>

      {/* Debt Report Panel */}
      <div className="panel">
        <div className="panelTitle">Deudas de Terceros</div>
        {debtLoading ? (
          <div className="loadingContainer">
            <Spinner size={28} />
          </div>
        ) : !debtData || debtData.length === 0 ? (
          <div className="muted">Sin deudas registradas</div>
        ) : (
          <div className="tableContainer">
          <table className="table">
            <thead>
              <tr>
                <th>Deudor</th>
                <th>Pendiente</th>
                <th>Pagado</th>
                <th>Compras sin saldar</th>
              </tr>
            </thead>
            <tbody>
              {debtData.map((row) => (
                <tr key={row.debtor_id}>
                  <td>{row.debtor_name}</td>
                  <td style={{ color: 'var(--color-error)' }}>
                    {row.total_owed.toLocaleString('es-AR', { maximumFractionDigits: 2 })}
                  </td>
                  <td style={{ color: 'var(--color-success)' }}>
                    {row.total_settled.toLocaleString('es-AR', { maximumFractionDigits: 2 })}
                  </td>
                  <td>{row.pending_purchases}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
      </div>{/* end dashboard-desktop-only */}

    </section>
  )
}

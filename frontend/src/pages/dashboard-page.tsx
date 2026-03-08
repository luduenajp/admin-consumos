import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import {
  fetchPeople,
  fetchMonthBreakdown,
  fetchTimeline,
  fetchDebtReport,
  updatePurchase,
  fetchCategories,
  fetchCategorySpending,
} from '../api/endpoints'
import { Spinner } from '../components/Spinner'
import { TimelineChart } from '../components/TimelineChart'
import { CategoryChart } from '../components/CategoryChart'
import { MonthlyBalanceCard } from '../components/MonthlyBalanceCard'
import { TransferCalculationCard } from '../components/TransferCalculationCard'
import { PurchaseForm } from '../components/PurchaseForm'

function getCurrentYearMonth(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

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
  const [monthFilter, setMonthFilter] = useState<string>(() => getCurrentYearMonth())
  const [expenseTypeFilter, setExpenseTypeFilter] = useState<string>('all')
  const [showAddForm, setShowAddForm] = useState(false)
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: 'asc' | 'desc' } | null>(null)
  const personId = personFilter ? Number(personFilter) : undefined
  const isCommon = expenseTypeFilter === 'all' ? undefined : expenseTypeFilter === 'common'
  const monthOptions = useMemo(() => buildMonthOptions(), [])

  const queryClient = useQueryClient()
  const { data: peopleData } = useQuery({
    queryKey: ['people'],
    queryFn: fetchPeople,
  })
  const people = peopleData ?? []


  const { data: timelineData, isLoading: timelineLoading } = useQuery({
    queryKey: ['reports', 'timeline', { personId, isCommon }],
    queryFn: () => fetchTimeline({ monthsAhead: 12, personId, isCommon }),
  })

  const { data: debtData, isLoading: debtLoading } = useQuery({
    queryKey: ['reports', 'debts'],
    queryFn: fetchDebtReport,
  })

  const { data: monthBreakdownData, isLoading: monthBreakdownLoading } = useQuery({
    queryKey: ['reports', 'month-breakdown', { yearMonth: monthFilter, personId, isCommon }],
    queryFn: () => fetchMonthBreakdown({ yearMonth: monthFilter, personId, isCommon }),
  })

  const { data: categoriesData } = useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
  })

  const { data: categorySpendingData, isLoading: categorySpendingLoading } = useQuery({
    queryKey: ['reports', 'category-spending', { personId, yearMonth: monthFilter, isCommon }],
    queryFn: () => fetchCategorySpending({ personId, yearMonth: monthFilter, isCommon }),
  })

  const commonMutation = useMutation({
    mutationFn: ({ id, is_common }: { id: number; is_common: boolean }) => updatePurchase(id, { is_common }),
    onSuccess: () => {
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

  return (
    <section className="page">
      <h2 className="pageTitle">Dashboard</h2>

      {/* Filters Container */}
      <div className="panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', gap: '32px', flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Mes a ver</label>
            <select
              className="input"
              style={{ width: '180px' }}
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
            <div className="formRow" style={{ marginBottom: 0 }}>
              <label className="label">Ver gastos de</label>
              <select
                className="input"
                style={{ width: '200px' }}
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
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Tipo de gasto</label>
            <select
              className="input"
              style={{ width: '180px' }}
              value={expenseTypeFilter}
              onChange={(e) => setExpenseTypeFilter(e.target.value)}
            >
              <option value="all">Todos</option>
              <option value="common">Comunes</option>
              <option value="personal">Personales</option>
            </select>
            <div className="hint">Filtro por tipo de gasto</div>
          </div>
          <div style={{ marginLeft: 'auto', alignSelf: 'center', display: 'flex', gap: '12px' }}>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="button"
              style={{ background: 'var(--color-primary)', color: 'white' }}
            >
              {showAddForm ? '✕ Cancelar' : '+ Nueva compra'}
            </button>
            <button
              onClick={() => {
                window.location.href = `/api/reports/export-excel?year_month=${monthFilter}`
              }}
              className="button"
              style={{ background: '#27ae60', color: 'white', borderColor: '#2ecc71', fontWeight: 600 }}
            >
              📊 Exportar Excel
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

      {/* Top Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '32px' }}>
        <MonthlyBalanceCard yearMonth={monthFilter} />
        <TransferCalculationCard yearMonth={monthFilter} />
      </div>

      {/* Resumen del mes seleccionado */}
      <div className="panel">
        <div className="panelTitle">Resumen del mes ({monthOptions.find((m) => m.value === monthFilter)?.label ?? monthFilter})</div>
        {monthBreakdownLoading ? (
          <div className="loadingContainer">
            <Spinner size={28} />
          </div>
        ) : !monthBreakdownData ? (
          <div className="muted">Sin datos</div>
        ) : (
          <>
            <div style={{ display: 'flex', gap: '24px', marginBottom: '16px', flexWrap: 'wrap' }}>
              <div style={{ fontSize: '1.25rem', fontWeight: 600 }}>
                Total del mes:{' '}
                <span style={{ color: 'var(--color-primary)' }}>
                  ${monthBreakdownData.total_ars.toLocaleString('es-AR', { maximumFractionDigits: 2 })} ARS
                </span>
              </div>
              {monthBreakdownData.items.some((i) => i.debtor_id) && (
                <div style={{ fontSize: '1.25rem', fontWeight: 600 }}>
                  Total Deudas:{' '}
                  <span style={{ color: 'var(--color-error)' }}>
                    $
                    {monthBreakdownData.items
                      .filter((i) => i.debtor_id && !i.debt_settled)
                      .reduce((sum, i) => sum + i.amount_ars, 0)
                      .toLocaleString('es-AR', { maximumFractionDigits: 2 })}{' '}
                    ARS
                  </span>
                </div>
              )}
            </div>
            {monthBreakdownData.items.length === 0 ? (
              <div className="muted">Sin cuotas que venzan en este mes</div>
            ) : (
              <div className="tableContainer">
                <table className="table">
                  <thead>
                    <tr>
                      <th onClick={() => requestSort('purchase_date')} style={{ cursor: 'pointer', userSelect: 'none' }}>Fecha compra{getSortIcon('purchase_date')}</th>
                      <th onClick={() => requestSort('description')} style={{ cursor: 'pointer', userSelect: 'none' }}>Descripción{getSortIcon('description')}</th>
                      <th onClick={() => requestSort('notes')} style={{ cursor: 'pointer', userSelect: 'none' }}>Detalle{getSortIcon('notes')}</th>
                      <th onClick={() => requestSort('debtor_name')} style={{ cursor: 'pointer', userSelect: 'none' }}>Deudor{getSortIcon('debtor_name')}</th>
                      <th onClick={() => requestSort('installment_index')} style={{ cursor: 'pointer', userSelect: 'none' }}>Cuota{getSortIcon('installment_index')}</th>
                      <th onClick={() => requestSort('is_common')} style={{ cursor: 'pointer', userSelect: 'none', textAlign: 'center' }}>Común{getSortIcon('is_common')}</th>
                      <th onClick={() => requestSort('amount_ars')} style={{ cursor: 'pointer', userSelect: 'none', textAlign: 'right' }}>Monto (ARS){getSortIcon('amount_ars')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {monthBreakdownData.items
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
                        <tr key={`${row.purchase_id}-${row.installment_index}`}>
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
                                    {row.is_common ? 'Gasto Común' : 'Gasto Particular'}
                                  </span>
                                </div>
                                <div className="tooltip-row">
                                  <span className="tooltip-label">Categoría:</span>
                                  <span className="tooltip-value">{row.category || 'Sin categoría'}</span>
                                </div>
                                <div className="tooltip-row">
                                  <span className="tooltip-label">Pagador:</span>
                                  <span className="tooltip-value">{row.payer_name}</span>
                                </div>
                                <div className="tooltip-row">
                                  <span className="tooltip-label">Método:</span>
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

      {/* Category Chart Panel */}
      <div className="panel">
        <div className="panelTitle">Gasto por Categoría ({monthOptions.find((m) => m.value === monthFilter)?.label ?? monthFilter})</div>
        {categorySpendingLoading ? (
          <div className="loadingContainer">
            <Spinner size={28} />
          </div>
        ) : (
          <CategoryChart data={categorySpendingData ?? []} categories={categoriesData ?? []} />
        )}
      </div>

      {/* Timeline Panel */}
      <div className="panel">
        <div className="panelTitle">Cuotas Futuras (3 meses anteriores + 12 futuros)</div>
        {timelineLoading ? (
          <div className="loadingContainer">
            <Spinner size={28} />
          </div>
        ) : (
          <TimelineChart data={timelineData ?? []} />
        )}
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
        )}
      </div>

    </section>
  )
}

import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import {
  fetchPeople,
  fetchMonthBreakdown,
  fetchTimeline,
  fetchDebtReport,
  updatePurchase,
} from '../api/endpoints'
import { Spinner } from '../components/Spinner'
import { TimelineChart } from '../components/TimelineChart'
import { MonthlyBalanceCard } from '../components/MonthlyBalanceCard'
import { TransferCalculationCard } from '../components/TransferCalculationCard'

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
  const personId = personFilter ? Number(personFilter) : undefined
  const monthOptions = useMemo(() => buildMonthOptions(), [])

  const queryClient = useQueryClient()
  const { data: peopleData } = useQuery({
    queryKey: ['people'],
    queryFn: fetchPeople,
  })
  const people = peopleData ?? []


  const { data: timelineData, isLoading: timelineLoading } = useQuery({
    queryKey: ['reports', 'timeline', { personId }],
    queryFn: () => fetchTimeline({ monthsAhead: 12, personId }),
  })

  const { data: debtData, isLoading: debtLoading } = useQuery({
    queryKey: ['reports', 'debts'],
    queryFn: fetchDebtReport,
  })

  const { data: monthBreakdownData, isLoading: monthBreakdownLoading } = useQuery({
    queryKey: ['reports', 'month-breakdown', { yearMonth: monthFilter, personId }],
    queryFn: () => fetchMonthBreakdown({ yearMonth: monthFilter, personId }),
  })

  const commonMutation = useMutation({
    mutationFn: ({ id, is_common }: { id: number; is_common: boolean }) => updatePurchase(id, { is_common }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      queryClient.invalidateQueries({ queryKey: ['transfer-calculation'] })
      queryClient.invalidateQueries({ queryKey: ['monthly-balance'] })
    },
  })


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
          <div style={{ marginLeft: 'auto', alignSelf: 'center' }}>
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
              <div style={{ overflowX: 'auto' }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Fecha compra</th>
                      <th>Descripción</th>
                      <th>Detalle</th>
                      <th>Deudor</th>
                      <th>Cuota</th>
                      <th style={{ textAlign: 'center' }}>Común</th>
                      <th style={{ textAlign: 'right' }}>Monto (ARS)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {monthBreakdownData.items.map((row) => (
                      <tr key={`${row.purchase_id}-${row.installment_index}`}>
                        <td>{row.purchase_date}</td>
                        <td>{row.description}</td>
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

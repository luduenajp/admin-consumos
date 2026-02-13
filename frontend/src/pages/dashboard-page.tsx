import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import {
  fetchPeople,
  fetchMonthBreakdown,
  fetchMonthlyReport,
  fetchTimeline,
  fetchCategorySpending,
  fetchDebtReport,
} from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import { CategoryChart } from '../components/CategoryChart'
import { Spinner } from '../components/Spinner'
import { TimelineChart } from '../components/TimelineChart'

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

  const { data: peopleData } = useQuery({
    queryKey: ['people'],
    queryFn: fetchPeople,
  })
  const people = peopleData ?? []

  const { data, isLoading, error } = useQuery({
    queryKey: ['reports', 'monthly', { personId }],
    queryFn: () => fetchMonthlyReport({ personId }),
  })

  const { data: timelineData, isLoading: timelineLoading } = useQuery({
    queryKey: ['reports', 'timeline', { personId }],
    queryFn: () => fetchTimeline({ monthsAhead: 12, personId }),
  })

  const { data: categoryData, isLoading: categoryLoading } = useQuery({
    queryKey: ['reports', 'category-spending', { personId }],
    queryFn: () => fetchCategorySpending({ personId }),
  })

  const { data: debtData, isLoading: debtLoading } = useQuery({
    queryKey: ['reports', 'debts'],
    queryFn: fetchDebtReport,
  })

  const { data: monthBreakdownData, isLoading: monthBreakdownLoading } = useQuery({
    queryKey: ['reports', 'month-breakdown', { yearMonth: monthFilter, personId }],
    queryFn: () => fetchMonthBreakdown({ yearMonth: monthFilter, personId }),
  })

  if (isLoading)
    return (
      <div className="loadingContainer">
        <Spinner size={32} />
      </div>
    )
  if (error) return <div className="error">Error: {extractErrorMessage(error)}</div>

  const rows = data ?? []

  return (
    <section className="page">
      <h2 className="pageTitle">Dashboard</h2>

      {/* Filters */}
      <div className="panel" style={{ marginBottom: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', alignItems: 'end' }}>
          <div className="formRow">
            <label className="label">Mes a ver</label>
            <select
              className="input"
              style={{ maxWidth: '180px' }}
              value={monthFilter}
              onChange={(e) => setMonthFilter(e.target.value)}
            >
              {monthOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <div className="hint">Cuotas que vencen en este mes</div>
          </div>
          {people.length > 0 && (
            <div className="formRow">
              <label className="label">Ver gastos de</label>
              <select
                className="input"
                style={{ maxWidth: '200px' }}
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
                {personFilter ? `Solo lo que pagó ${people.find((x) => String(x.id) === personFilter)?.name}` : 'Totales de todos'}
              </div>
            </div>
          )}
        </div>
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
            <div style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '16px' }}>
              Total del mes:{' '}
              <span style={{ color: 'var(--color-primary)' }}>
                ${monthBreakdownData.total_ars.toLocaleString('es-AR', { maximumFractionDigits: 2 })} ARS
              </span>
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
                      <th>Categoría</th>
                      <th>Cuota</th>
                      <th style={{ textAlign: 'right' }}>Monto (ARS)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {monthBreakdownData.items.map((row) => (
                      <tr key={`${row.purchase_id}-${row.installment_index}`}>
                        <td>{row.purchase_date}</td>
                        <td>{row.description}</td>
                        <td>{row.category ?? '-'}</td>
                        <td>
                          {row.installment_index}/{row.installments_total}
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
        <div className="panelTitle">Cuotas Futuras (próximos 12 meses)</div>
        {timelineLoading ? (
          <div className="loadingContainer">
            <Spinner size={28} />
          </div>
        ) : (
          <TimelineChart data={timelineData ?? []} />
        )}
      </div>

      {/* Category Distribution Panel */}
      <div className="panel">
        <div className="panelTitle">Distribución por Categoría</div>
        {categoryLoading ? (
          <div className="loadingContainer">
            <Spinner size={28} />
          </div>
        ) : (
          <CategoryChart data={categoryData ?? []} />
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

      {/* Monthly Report Panel */}
      <div className="panel">
        <div className="panelTitle">Totales mensuales (ARS)</div>
        {rows.length === 0 ? (
          <div className="muted">Sin datos</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Mes</th>
                <th>Total (ARS)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.year_month}>
                  <td>{r.year_month}</td>
                  <td>{r.total_ars.toLocaleString('es-AR', { maximumFractionDigits: 2 })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}

import { useQuery } from '@tanstack/react-query'
import {
  fetchMonthlyBalance,
  fetchTransferCalculation,
  fetchMonthBreakdown,
  fetchDebtReport,
} from '../api/endpoints'
import { formatCurrency } from '../utils/format'
import { getRelativeMonth } from '../utils/dates'
import { Spinner } from './Spinner'

interface KpiSummaryProps {
  yearMonth: string
  personId?: number
  cardId?: number
  isCommon?: boolean
}

export function KpiSummary({ yearMonth, personId, cardId, isCommon }: KpiSummaryProps) {
  const previousMonth = getRelativeMonth(
    (() => {
      const [y, m] = yearMonth.split('-').map(Number)
      const now = new Date()
      const currentOffset = (y - now.getFullYear()) * 12 + (m - now.getMonth() - 1)
      return currentOffset - 1
    })()
  )

  const { data: currentData } = useQuery({
    queryKey: ['reports', 'month-breakdown', { yearMonth, personId, cardId, isCommon }],
    queryFn: () => fetchMonthBreakdown({ yearMonth, personId, cardId, isCommon }),
  })

  const { data: prevData } = useQuery({
    queryKey: ['reports', 'month-breakdown', { yearMonth: previousMonth, personId, cardId, isCommon }],
    queryFn: () => fetchMonthBreakdown({ yearMonth: previousMonth, personId, cardId, isCommon }),
  })

  const { data: balance } = useQuery({
    queryKey: ['monthly-balance', yearMonth],
    queryFn: () => fetchMonthlyBalance(yearMonth),
  })

  const { data: transfers } = useQuery({
    queryKey: ['transfer-calculation', yearMonth],
    queryFn: () => fetchTransferCalculation(yearMonth),
  })

  const { data: debtData } = useQuery({
    queryKey: ['reports', 'debts'],
    queryFn: fetchDebtReport,
  })

  const totalSpent = currentData?.total_ars ?? 0
  const itemCount = currentData?.items.length ?? 0
  const prevTotal = prevData?.total_ars ?? 0
  const variation = prevTotal > 0 ? ((totalSpent - prevTotal) / prevTotal) * 100 : null

  const budgetPct = balance?.porcentaje_gastado ?? null
  const budgetColor =
    budgetPct === null
      ? 'var(--color-muted)'
      : budgetPct >= 100
        ? 'var(--color-error)'
        : budgetPct >= 80
          ? 'var(--color-warning)'
          : 'var(--color-success)'

  const pendingTransfer =
    transfers?.transferencias && transfers.transferencias.length > 0
      ? transfers.transferencias.reduce((sum, t) => sum + t.amount, 0)
      : null

  const pendingDebtsCount = debtData?.reduce((sum, d) => sum + d.pending_purchases, 0) ?? 0
  const pendingDebtsTotal = debtData?.reduce((sum, d) => sum + d.total_owed, 0) ?? 0

  if (!currentData) {
    return (
      <div className="kpi-grid">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="panel kpi-card" style={{ textAlign: 'center' }}>
            <Spinner size={20} />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="kpi-grid">
      {/* Total gastado */}
      <div className="panel kpi-card">
        <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '8px' }}>
          Total del mes
        </div>
        <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-text)', letterSpacing: '-0.02em' }}>
          {formatCurrency(totalSpent)}
        </div>
        {variation !== null && (
          <div style={{
            fontSize: '0.8rem',
            fontWeight: 600,
            color: variation > 0 ? 'var(--color-error)' : variation < 0 ? 'var(--color-success)' : 'var(--color-muted)',
            marginTop: '4px'
          }}>
            {variation > 0 ? '+' : ''}{variation.toFixed(1)}% vs mes anterior
          </div>
        )}
      </div>

      {/* Cuotas activas */}
      <div className="panel kpi-card">
        <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '8px' }}>
          Cuotas activas
        </div>
        <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-text)', letterSpacing: '-0.02em' }}>
          {itemCount}
        </div>
        <div style={{ fontSize: '0.8rem', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
          este mes
        </div>
      </div>

      {/* Presupuesto */}
      <div className="panel kpi-card">
        <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '8px' }}>
          Presupuesto
        </div>
        {budgetPct !== null ? (
          <>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: budgetColor, letterSpacing: '-0.02em' }}>
              {budgetPct.toFixed(1)}%
            </div>
            <div style={{
              width: '100%',
              height: '6px',
              backgroundColor: 'var(--color-primary-light)',
              borderRadius: '6px',
              overflow: 'hidden',
              marginTop: '8px'
            }}>
              <div style={{
                width: `${Math.min(budgetPct, 100)}%`,
                height: '100%',
                background: budgetColor,
                borderRadius: '6px',
                transition: 'width 0.6s ease'
              }} />
            </div>
          </>
        ) : (
          <div style={{ fontSize: '1rem', color: 'var(--color-muted)', fontStyle: 'italic' }}>
            Sin configurar
          </div>
        )}
      </div>

      {/* Transferencia pendiente + deudas */}
      <div className="panel kpi-card desktopOnly">
        <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '8px' }}>
          Transferencia
        </div>
        {pendingTransfer !== null ? (
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-warning)', letterSpacing: '-0.02em' }}>
            {formatCurrency(pendingTransfer)}
          </div>
        ) : transfers?.is_balanced ? (
          <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--color-success)' }}>
            Balanceado
          </div>
        ) : (
          <div style={{ fontSize: '1rem', color: 'var(--color-muted)', fontStyle: 'italic' }}>
            Sin datos
          </div>
        )}
        {pendingDebtsCount > 0 && (
          <div style={{
            fontSize: '0.75rem',
            fontWeight: 600,
            color: 'var(--color-error)',
            marginTop: '6px',
            padding: '3px 8px',
            backgroundColor: 'var(--color-error-bg)',
            borderRadius: 'var(--radius-sm)',
            display: 'inline-block'
          }}>
            {pendingDebtsCount} deuda{pendingDebtsCount > 1 ? 's' : ''}: {formatCurrency(pendingDebtsTotal)}
          </div>
        )}
      </div>
    </div>
  )
}

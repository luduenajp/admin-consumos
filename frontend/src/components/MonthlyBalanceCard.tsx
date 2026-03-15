import { useQuery } from '@tanstack/react-query'
import { fetchMonthlyBalance } from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import { formatCurrency } from '../utils/format'
import { getCurrentYearMonth } from '../utils/dates'
import { Spinner } from './Spinner'

export function MonthlyBalanceCard({ yearMonth }: { yearMonth?: string }) {
  const currentMonth = yearMonth ?? getCurrentYearMonth()

  const { data: balance, isLoading, error } = useQuery({
    queryKey: ['monthly-balance', currentMonth],
    queryFn: () => fetchMonthlyBalance(currentMonth),
  })

  if (isLoading) {
    return (
      <div className="panel">
        <h2 className="panelTitle">Balance del Mes</h2>
        <div className="loadingContainer">
          <Spinner />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="panel">
        <h2 className="panelTitle">Balance del Mes</h2>
        <div className="error">
          {extractErrorMessage(error)}
        </div>
        <p className="hint" style={{ marginTop: '16px' }}>
          Configura un presupuesto para ver el balance mensual
        </p>
      </div>
    )
  }

  if (!balance) {
    return (
      <div className="panel">
        <h2 className="panelTitle">Balance del Mes</h2>
        <p className="muted">
          No hay presupuesto configurado para este mes
        </p>
      </div>
    )
  }

  return (
    <div className="panel">
      <h2 className="panelTitle">Balance del Mes</h2>

      <div style={{ paddingTop: '8px' }}>
        {/* Metricas principales */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '24px',
          marginBottom: '24px'
        }}>
          <div>
            <div className="label" style={{ marginBottom: '4px' }}>Presupuesto</div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--color-text)' }}>
              {formatCurrency(balance.presupuesto)}
            </div>
          </div>

          <div>
            <div className="label" style={{ marginBottom: '4px' }}>Gastos Acumulados</div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--color-primary)' }}>
              {formatCurrency(balance.gastos_acumulados)}
            </div>
          </div>
        </div>

        {/* Sobrante personal */}
        <div style={{
          padding: '24px',
          background: balance.sobrante_total >= 0
            ? 'linear-gradient(135deg, var(--color-success-bg), #ffffff)'
            : 'linear-gradient(135deg, var(--color-error-bg), #ffffff)',
          borderRadius: 'var(--radius-md)',
          border: `1px solid ${balance.sobrante_total >= 0 ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`,
          textAlign: 'center'
        }}>
          <div style={{
            fontSize: '0.9rem',
            marginBottom: '8px',
            fontWeight: '600',
            color: 'var(--color-text-secondary)'
          }}>
            Sobrante para cada uno
          </div>
          <div style={{
            fontSize: '2rem',
            fontWeight: '800',
            color: balance.sobrante_total >= 0 ? 'var(--color-success)' : 'var(--color-error)',
            letterSpacing: '-0.02em'
          }}>
            {formatCurrency(balance.sobrante_por_persona)}
          </div>
          <div style={{
            fontSize: '0.9rem',
            color: 'var(--color-text-secondary)',
            marginTop: '8px'
          }}>
            Total restante: <strong>{formatCurrency(balance.sobrante_total)}</strong>
          </div>
        </div>
      </div>
    </div>
  )
}

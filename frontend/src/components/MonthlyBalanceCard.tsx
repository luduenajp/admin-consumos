import { useQuery } from '@tanstack/react-query'
import { fetchMonthlyBalance } from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import { formatCurrency } from '../utils/format'
import { getCurrentYearMonth } from '../utils/dates'
import { Spinner } from './Spinner'

function getBalanceStatus(percentageSpent: number): { color: string; text: string } {
  if (percentageSpent >= 100) {
    return { color: '#dc2626', text: '⚠️ Presupuesto agotado' }
  } else if (percentageSpent >= 80) {
    return { color: '#f59e0b', text: '🟡 Cuidado, casi al límite' }
  } else if (percentageSpent >= 60) {
    return { color: '#3b82f6', text: '🔵 En camino' }
  } else {
    return { color: '#10b981', text: '🟢 Bien encaminado' }
  }
}

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
          Configurá un presupuesto para ver el balance mensual
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

  const status = getBalanceStatus(balance.porcentaje_gastado)

  return (
    <div className="panel">
      <h2 className="panelTitle">Balance del Mes</h2>

      <div style={{ paddingTop: '8px' }}>
        {/* Barra de progreso */}
        <div style={{ marginBottom: '32px' }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            marginBottom: '12px'
          }}>
            <span style={{ fontSize: '1rem', fontWeight: '600', color: 'var(--color-text)' }}>
              {balance.porcentaje_gastado.toFixed(1)}% <span style={{ fontWeight: 400, fontSize: '0.9rem', color: 'var(--color-text-secondary)' }}>del presupuesto</span>
            </span>
            <span style={{
              fontSize: '0.85rem',
              color: status.color,
              fontWeight: '700',
              textTransform: 'uppercase',
              letterSpacing: '0.02em'
            }}>
              {status.text}
            </span>
          </div>

          <div style={{
            width: '100%',
            height: '10px',
            backgroundColor: 'var(--color-primary-light)',
            borderRadius: '10px',
            overflow: 'hidden'
          }}>
            <div style={{
              width: `${Math.min(balance.porcentaje_gastado, 100)}%`,
              height: '100%',
              background: `linear-gradient(90deg, ${status.color}, ${status.color}dd)`,
              borderRadius: '10px',
              transition: 'width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)'
            }} />
          </div>
        </div>

        {/* Métricas principales */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '24px',
          marginBottom: '32px'
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
            fontSize: '1rem',
            marginBottom: '8px',
            fontWeight: '600',
            color: 'var(--color-text-secondary)'
          }}>
            💰 Sobrante para cada uno
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

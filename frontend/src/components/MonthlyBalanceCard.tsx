import { useQuery } from '@tanstack/react-query'
import { fetchMonthlyBalance } from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import { Spinner } from './Spinner'

function getCurrentYearMonth(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
  }).format(amount)
}

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
        <div style={{ padding: '1rem', textAlign: 'center' }}>
          <Spinner />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="panel">
        <h2 className="panelTitle">Balance del Mes</h2>
        <div className="error" style={{ margin: '1rem' }}>
          {extractErrorMessage(error)}
        </div>
        <p className="muted" style={{ margin: '1rem' }}>
          Configurá un presupuesto para ver el balance mensual
        </p>
      </div>
    )
  }

  if (!balance) {
    return (
      <div className="panel">
        <h2 className="panelTitle">Balance del Mes</h2>
        <p className="muted" style={{ margin: '1rem' }}>
          No hay presupuesto configurado para este mes
        </p>
      </div>
    )
  }

  const status = getBalanceStatus(balance.porcentaje_gastado)

  return (
    <div className="panel">
      <h2 className="panelTitle">Balance del Mes</h2>
      
      <div style={{ padding: '1rem 0' }}>
        {/* Barra de progreso */}
        <div style={{ marginBottom: '1.5rem' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: '0.5rem'
          }}>
            <span style={{ fontSize: '0.9rem', fontWeight: '500' }}>
              {balance.porcentaje_gastado.toFixed(1)}% del presupuesto gastado
            </span>
            <span style={{ 
              fontSize: '0.8rem', 
              color: status.color,
              fontWeight: '500'
            }}>
              {status.text}
            </span>
          </div>
          
          <div style={{
            width: '100%',
            height: '8px',
            backgroundColor: '#e5e7eb',
            borderRadius: '4px',
            overflow: 'hidden'
          }}>
            <div style={{
              width: `${Math.min(balance.porcentaje_gastado, 100)}%`,
              height: '100%',
              backgroundColor: status.color,
              transition: 'width 0.3s ease'
            }} />
          </div>
        </div>

        {/* Métricas principales */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: '1fr 1fr', 
          gap: '1rem',
          marginBottom: '1.5rem'
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.8rem', color: '#6b7280', marginBottom: '0.25rem' }}>
              Presupuesto
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: '600' }}>
              {formatCurrency(balance.presupuesto)}
            </div>
          </div>
          
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '0.8rem', color: '#6b7280', marginBottom: '0.25rem' }}>
              Gastos
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: '600' }}>
              {formatCurrency(balance.gastos_acumulados)}
            </div>
          </div>
        </div>

        {/* Sobrante personal */}
        <div style={{
          padding: '1rem',
          backgroundColor: balance.sobrante_total >= 0 ? '#f0fdf4' : '#fef2f2',
          borderRadius: '8px',
          border: `1px solid ${balance.sobrante_total >= 0 ? '#bbf7d0' : '#fecaca'}`
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ 
              fontSize: '0.9rem', 
              marginBottom: '0.5rem',
              fontWeight: '500'
            }}>
              💰 Sobrante para cada uno
            </div>
            <div style={{ 
              fontSize: '1.5rem', 
              fontWeight: '700',
              color: balance.sobrante_total >= 0 ? '#166534' : '#991b1b'
            }}>
              {formatCurrency(balance.sobrante_por_persona)}
            </div>
            <div style={{ 
              fontSize: '0.8rem', 
              color: '#6b7280',
              marginTop: '0.25rem'
            }}>
              Total restante: {formatCurrency(balance.sobrante_total)}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

import { useQuery } from '@tanstack/react-query'
import { fetchRecurringExpenses } from '../api/endpoints'
import { Spinner } from './Spinner'

export function RecurringExpensesCard() {
  const { data, isLoading } = useQuery({
    queryKey: ['reports', 'recurring-expenses'],
    queryFn: () => fetchRecurringExpenses(3),
  })

  if (isLoading) {
    return (
      <div className="loadingContainer">
        <Spinner size={28} />
      </div>
    )
  }

  if (!data || data.length === 0) {
    return <div className="muted" style={{ textAlign: 'center', padding: '2rem' }}>No se detectaron gastos recurrentes (3+ meses)</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {data.map((item, i) => (
        <div
          key={i}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px 16px',
            backgroundColor: 'var(--color-bg)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--color-border)',
          }}
        >
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            backgroundColor: 'var(--color-primary-light)',
            color: 'var(--color-primary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '0.8rem',
            fontWeight: 700,
            flexShrink: 0,
          }}>
            {item.occurrences}x
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontWeight: 600,
              fontSize: '0.9rem',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              {item.description}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {item.category && (
                <span style={{
                  padding: '1px 6px',
                  backgroundColor: 'var(--color-surface)',
                  borderRadius: '4px',
                  border: '1px solid var(--color-border)',
                }}>
                  {item.category}
                </span>
              )}
              <span>Visto en {item.occurrences} meses</span>
              <span>Ultimo: {item.last_seen}</span>
            </div>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0 }}>
            <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--color-text)' }}>
              ${item.avg_amount.toLocaleString('es-AR', { maximumFractionDigits: 0 })}
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--color-text-secondary)' }}>
              prom. {item.currency}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

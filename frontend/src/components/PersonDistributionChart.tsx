import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { fetchTransferCalculation } from '../api/endpoints'
import { Spinner } from './Spinner'

interface PersonDistributionChartProps {
  yearMonth: string
}

export function PersonDistributionChart({ yearMonth }: PersonDistributionChartProps) {
  const { data: transfers, isLoading, error } = useQuery({
    queryKey: ['transfer-calculation', yearMonth],
    queryFn: () => fetchTransferCalculation(yearMonth),
  })

  if (isLoading) {
    return (
      <div className="loadingContainer">
        <Spinner size={28} />
      </div>
    )
  }

  if (error || !transfers || transfers.gastos_por_persona.length === 0) {
    return <div className="muted" style={{ textAlign: 'center', padding: '2rem' }}>Sin datos de distribucion por persona</div>
  }

  const chartData = transfers.gastos_por_persona.map((g) => ({
    name: g.person_name,
    paid: Math.round(g.paid_amount),
    should_pay: Math.round(g.should_pay),
    difference: Math.round(g.difference),
  }))

  return (
    <div>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="name"
            stroke="var(--color-text-secondary)"
            style={{ fontSize: '0.85rem' }}
          />
          <YAxis
            stroke="var(--color-text-secondary)"
            style={{ fontSize: '0.85rem' }}
            tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.9rem',
            }}
            formatter={(value, name) => [
              `$${Number(value).toLocaleString('es-AR', { maximumFractionDigits: 0 })}`,
              name === 'paid' ? 'Pago' : name === 'should_pay' ? 'Deberia pagar' : 'Diferencia',
            ]}
          />
          <Legend
            formatter={(value: string) =>
              value === 'paid' ? 'Pago' : value === 'should_pay' ? 'Deberia pagar' : value
            }
          />
          <Bar dataKey="paid" fill="var(--color-primary)" radius={[4, 4, 0, 0]} barSize={36} />
          <Bar dataKey="should_pay" fill="var(--color-accent)" radius={[4, 4, 0, 0]} barSize={36} />
        </BarChart>
      </ResponsiveContainer>

      {/* Summary cards below chart */}
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${chartData.length}, 1fr)`, gap: '12px', marginTop: '16px' }}>
        {chartData.map((person) => (
          <div
            key={person.name}
            style={{
              padding: '12px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--color-border)',
              textAlign: 'center',
              backgroundColor: person.difference > 0 ? 'var(--color-success-bg)' : person.difference < 0 ? 'var(--color-error-bg)' : 'var(--color-bg)',
            }}
          >
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: '4px' }}>
              {person.name}
            </div>
            <div style={{
              fontSize: '1.1rem',
              fontWeight: 800,
              color: person.difference > 0 ? 'var(--color-success)' : person.difference < 0 ? 'var(--color-error)' : 'var(--color-muted)',
            }}>
              {person.difference > 0 ? '+' : ''}${person.difference.toLocaleString('es-AR')}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
              {person.difference > 0 ? 'a favor' : person.difference < 0 ? 'en contra' : 'balanceado'}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface TimelineChartProps {
  data: Array<{ year_month: string; total_ars: number }>
}

export function TimelineChart({ data }: TimelineChartProps) {
  if (data.length === 0) {
    return <div className="muted">Sin cuotas futuras</div>
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
        <XAxis
          dataKey="year_month"
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
          formatter={(value) =>
            `$${Number(value).toLocaleString('es-AR', { maximumFractionDigits: 2 })}`
          }
          labelStyle={{ color: 'var(--color-text)' }}
        />
        <Bar dataKey="total_ars" fill="var(--color-primary)" radius={[8, 8, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

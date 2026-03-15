import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from 'recharts'

interface TimelineChartProps {
  data: Array<{ year_month: string; total_ars: number }>
  commonData?: Array<{ year_month: string; total_ars: number }>
  personalData?: Array<{ year_month: string; total_ars: number }>
  monthlyIncome?: number
}

export function TimelineChart({ data, commonData, personalData, monthlyIncome }: TimelineChartProps) {
  if (data.length === 0) {
    return <div className="muted">Sin cuotas futuras</div>
  }

  const hasStacked = commonData && personalData && commonData.length > 0

  const mergedData = hasStacked
    ? data.map((d) => {
        const common = commonData.find((c) => c.year_month === d.year_month)?.total_ars ?? 0
        const personal = personalData.find((p) => p.year_month === d.year_month)?.total_ars ?? 0
        return {
          year_month: d.year_month,
          total_ars: d.total_ars,
          common,
          personal,
        }
      })
    : data

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={mergedData}>
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
          formatter={(value, name) => [
            `$${Number(value).toLocaleString('es-AR', { maximumFractionDigits: 2 })}`,
            name === 'common' ? 'Comunes' : name === 'personal' ? 'Personales' : 'Total',
          ]}
          labelStyle={{ color: 'var(--color-text)' }}
        />
        {hasStacked ? (
          <>
            <Legend
              formatter={(value: string) =>
                value === 'common' ? 'Comunes' : value === 'personal' ? 'Personales' : value
              }
            />
            <Bar dataKey="common" stackId="a" fill="var(--color-primary)" radius={[0, 0, 0, 0]} />
            <Bar dataKey="personal" stackId="a" fill="var(--color-accent)" radius={[8, 8, 0, 0]} />
          </>
        ) : (
          <Bar dataKey="total_ars" fill="var(--color-primary)" radius={[8, 8, 0, 0]} />
        )}
        {monthlyIncome && monthlyIncome > 0 && (
          <ReferenceLine
            y={monthlyIncome}
            stroke="var(--color-success)"
            strokeDasharray="6 4"
            strokeWidth={2}
            label={{
              value: `Ingreso: $${(monthlyIncome / 1000).toFixed(0)}k`,
              position: 'right',
              fill: 'var(--color-success)',
              fontSize: 11,
              fontWeight: 600,
            }}
          />
        )}
      </BarChart>
    </ResponsiveContainer>
  )
}

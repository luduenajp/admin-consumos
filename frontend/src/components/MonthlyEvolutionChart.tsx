import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { fetchMonthlyReport } from '../api/endpoints'
import { Spinner } from './Spinner'

interface MonthlyEvolutionChartProps {
  personId?: number
}

export function MonthlyEvolutionChart({ personId }: MonthlyEvolutionChartProps) {
  const { data: monthlyData, isLoading } = useQuery({
    queryKey: ['reports', 'monthly', { personId }],
    queryFn: () => fetchMonthlyReport({ personId }),
  })

  if (isLoading) {
    return (
      <div className="loadingContainer">
        <Spinner size={28} />
      </div>
    )
  }

  if (!monthlyData || monthlyData.length === 0) {
    return <div className="muted" style={{ textAlign: 'center', padding: '2rem' }}>Sin datos historicos</div>
  }

  // Show last 12 months
  const recent = monthlyData.slice(-12)

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={recent} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
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
          formatter={(value) => [
            `$${Number(value).toLocaleString('es-AR', { maximumFractionDigits: 2 })}`,
            'Total',
          ]}
          labelStyle={{ color: 'var(--color-text)' }}
        />
        <Legend formatter={() => 'Gasto mensual'} />
        <Line
          type="monotone"
          dataKey="total_ars"
          stroke="var(--color-primary)"
          strokeWidth={3}
          dot={{ fill: 'var(--color-primary)', strokeWidth: 2, r: 4 }}
          activeDot={{ r: 6, strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'

interface CategoryChartProps {
  data: Array<{ category: string; total_ars: number }>
}

const COLORS = [
  'var(--color-primary)',
  'var(--color-accent)',
  '#8B7355',
  '#A67C52',
  '#C09070',
  '#D4A574',
  '#E8BA97',
  '#B89B82',
]

export function CategoryChart({ data }: CategoryChartProps) {
  if (data.length === 0) {
    return <div className="muted">Sin datos de categorías</div>
  }

  return (
    <ResponsiveContainer width="100%" height={350}>
      <PieChart>
        <Pie
          data={data}
          dataKey="total_ars"
          nameKey="category"
          cx="50%"
          cy="50%"
          outerRadius={100}
          label={({ name, percent }: { name?: string; percent?: number }) =>
            `${name ?? ''} (${((percent ?? 0) * 100).toFixed(0)}%)`
          }
        >
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.9rem',
          }}
          formatter={(value) => `$${Number(value).toLocaleString('es-AR', { maximumFractionDigits: 2 })}`}
        />
        <Legend wrapperStyle={{ fontSize: '0.85rem' }} iconType="circle" />
      </PieChart>
    </ResponsiveContainer>
  )
}

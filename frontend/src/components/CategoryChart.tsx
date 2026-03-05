import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import type { Category } from '../api/types'

interface CategoryChartProps {
  data: Array<{ category: string; total_ars: number }>
  categories?: Category[]
}

const DEFAULT_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#f97316'
]

export function CategoryChart({ data, categories = [] }: CategoryChartProps) {
  if (data.length === 0) {
    return <div className="muted" style={{ textAlign: 'center', padding: '2rem' }}>Sin datos de categorías</div>
  }

  const sortedData = [...data].sort((a, b) => b.total_ars - a.total_ars)
  const categoryColorMap = new Map(categories.map(c => [c.name, c.color]))

  return (
    <ResponsiveContainer width="100%" height={400}>
      <BarChart
        data={sortedData}
        layout="vertical"
        margin={{ top: 5, right: 30, left: 40, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="var(--color-border)" />
        <XAxis type="number" hide />
        <YAxis
          dataKey="category"
          type="category"
          width={120}
          tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.9rem',
          }}
          formatter={(value) => `$${Number(value).toLocaleString('es-AR', { maximumFractionDigits: 2 })}`}
          cursor={{ fill: 'var(--color-surface-hover)', opacity: 0.4 }}
        />
        <Bar dataKey="total_ars" radius={[0, 4, 4, 0]} barSize={24}>
          {sortedData.map((entry, index) => {
            const color = categoryColorMap.get(entry.category) || DEFAULT_COLORS[index % DEFAULT_COLORS.length]
            return <Cell key={`cell-${index}`} fill={color} />
          })}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

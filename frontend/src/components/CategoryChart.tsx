import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie } from 'recharts'
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
  const grandTotal = sortedData.reduce((sum, d) => sum + d.total_ars, 0)

  const enrichedData = sortedData.map((d, index) => ({
    ...d,
    percentage: grandTotal > 0 ? (d.total_ars / grandTotal) * 100 : 0,
    fill: categoryColorMap.get(d.category) || DEFAULT_COLORS[index % DEFAULT_COLORS.length],
  }))

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 1fr) 280px', gap: '24px', alignItems: 'start' }}>
      {/* Bar chart */}
      <ResponsiveContainer width="100%" height={400}>
        <BarChart
          data={enrichedData}
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
            formatter={(value, _name, props) => {
              const pct = (props.payload as { percentage: number }).percentage
              return [
                `$${Number(value).toLocaleString('es-AR', { maximumFractionDigits: 2 })} (${pct.toFixed(1)}%)`,
                'Monto',
              ]
            }}
            cursor={{ fill: 'var(--color-surface-hover)', opacity: 0.4 }}
          />
          <Bar dataKey="total_ars" radius={[0, 4, 4, 0]} barSize={24}>
            {enrichedData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Donut chart + legend */}
      <div>
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              data={enrichedData}
              dataKey="total_ars"
              nameKey="category"
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={80}
              strokeWidth={2}
              stroke="var(--color-surface)"
            >
              {enrichedData.map((entry, index) => (
                <Cell key={`pie-${index}`} fill={entry.fill} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.85rem',
              }}
              formatter={(value) =>
                `$${Number(value).toLocaleString('es-AR', { maximumFractionDigits: 2 })}`
              }
            />
          </PieChart>
        </ResponsiveContainer>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px' }}>
          {enrichedData.slice(0, 6).map((d, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem' }}>
              <div style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: d.fill,
                flexShrink: 0
              }} />
              <span style={{ color: 'var(--color-text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {d.category}
              </span>
              <span style={{ fontWeight: 600, color: 'var(--color-text)' }}>
                {d.percentage.toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

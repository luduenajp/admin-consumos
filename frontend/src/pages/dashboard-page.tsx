import { useQuery } from '@tanstack/react-query'

import { fetchMonthlyReport } from '../api/endpoints'

export function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['reports', 'monthly'],
    queryFn: () => fetchMonthlyReport(),
  })

  if (isLoading) return <div>Cargando...</div>
  if (error) return <div>Error cargando reporte</div>

  const rows = data ?? []

  return (
    <section className="page">
      <h2 className="pageTitle">Dashboard</h2>
      <div className="panel">
        <div className="panelTitle">Totales mensuales (ARS)</div>
        {rows.length === 0 ? (
          <div className="muted">Sin datos</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Mes</th>
                <th>Total (ARS)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.year_month}>
                  <td>{r.year_month}</td>
                  <td>{r.total_ars.toLocaleString('es-AR', { maximumFractionDigits: 2 })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}

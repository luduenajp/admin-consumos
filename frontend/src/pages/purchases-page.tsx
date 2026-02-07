import { useQuery } from '@tanstack/react-query'

import { fetchPurchases } from '../api/endpoints'

export function PurchasesPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['purchases'],
    queryFn: () => fetchPurchases(),
  })

  if (isLoading) return <div>Cargando...</div>
  if (error) return <div>Error cargando compras</div>

  const rows = data ?? []

  return (
    <section className="page">
      <h2 className="pageTitle">Compras</h2>
      <div className="panel">
        {rows.length === 0 ? (
          <div className="muted">Sin compras cargadas</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Descripción</th>
                <th>Moneda</th>
                <th>Monto</th>
                <th>Cuotas</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id}>
                  <td>{p.purchase_date}</td>
                  <td>{p.description}</td>
                  <td>{p.currency}</td>
                  <td>{p.amount_original.toLocaleString('es-AR', { maximumFractionDigits: 2 })}</td>
                  <td>{p.installments_total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}

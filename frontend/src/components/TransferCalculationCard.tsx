import { useQuery } from '@tanstack/react-query'
import { fetchTransferCalculation } from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import { Spinner } from './Spinner'

function getCurrentYearMonth(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
  }).format(amount)
}

export function TransferCalculationCard({ yearMonth }: { yearMonth?: string }) {
  const currentMonth = yearMonth ?? getCurrentYearMonth()

  const { data: transfers, isLoading, error } = useQuery({
    queryKey: ['transfer-calculation', currentMonth],
    queryFn: () => fetchTransferCalculation(currentMonth),
  })

  if (isLoading) {
    return (
      <div className="panel">
        <h2 className="panelTitle">Transferencias del Mes</h2>
        <div style={{ padding: '1rem', textAlign: 'center' }}>
          <Spinner />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="panel">
        <h2 className="panelTitle">Transferencias del Mes</h2>
        <div className="error" style={{ margin: '1rem' }}>
          {extractErrorMessage(error)}
        </div>
        <p className="muted" style={{ margin: '1rem' }}>
          Cargá los ingresos de cada persona para calcular las transferencias
        </p>
      </div>
    )
  }

  if (!transfers) {
    return (
      <div className="panel">
        <h2 className="panelTitle">Transferencias del Mes</h2>
        <p className="muted" style={{ margin: '1rem' }}>
          No hay ingresos registrados para este mes
        </p>
      </div>
    )
  }

  return (
    <div className="panel">
      <h2 className="panelTitle">Transferencias del Mes</h2>
      
      <div style={{ padding: '1rem 0' }}>
        {/* Resumen de ingresos */}
        <div style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            💰 Ingresos del Mes
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
            {transfers.ingresos.map((income) => (
              <div key={income.person_id} style={{ 
                padding: '0.5rem', 
                backgroundColor: '#f8fafc', 
                borderRadius: '4px',
                fontSize: '0.9rem'
              }}>
                <div style={{ fontWeight: 500 }}>{income.person_name}</div>
                <div style={{ color: '#059669' }}>
                  {formatCurrency(income.amount)}
                </div>
              </div>
            ))}
          </div>
          <div style={{ 
            marginTop: '0.5rem', 
            paddingTop: '0.5rem', 
            borderTop: '1px solid #e5e7eb',
            fontWeight: 600 
          }}>
            Total: {formatCurrency(transfers.total_ingresos)}
          </div>
        </div>

        {/* Gastos por persona */}
        <div style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            💳 Gastos Pagados por Persona
          </h3>
          {transfers.gastos_por_persona.map((gasto) => (
            <div key={gasto.person_id} style={{ 
              marginBottom: '0.5rem',
              padding: '0.5rem',
              backgroundColor: '#f8fafc',
              borderRadius: '4px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 500 }}>{gasto.person_name}</span>
                <span style={{ fontSize: '0.85rem', color: '#6b7280' }}>
                  Pagó: {formatCurrency(gasto.paid_amount)} | 
                  Le tocaba: {formatCurrency(gasto.should_pay)}
                </span>
              </div>
              <div style={{ 
                marginTop: '0.25rem', 
                fontWeight: 600,
                color: gasto.difference > 0 ? '#059669' : gasto.difference < 0 ? '#dc2626' : '#6b7280'
              }}>
                {gasto.difference > 0 
                  ? `Le deben: ${formatCurrency(gasto.difference)}`
                  : gasto.difference < 0 
                    ? `Debe: ${formatCurrency(Math.abs(gasto.difference))}`
                    : 'Está al día'
                }
              </div>
            </div>
          ))}
        </div>

        {/* Transferencias sugeridas */}
        <div>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            🔄 Transferencias Sugeridas
          </h3>
          {transfers.transferencias.length > 0 ? (
            <div>
              {transfers.transferencias.map((transfer, index) => (
                <div key={index} style={{
                  padding: '0.75rem',
                  backgroundColor: '#ecfdf5',
                  border: '1px solid #bbf7d0',
                  borderRadius: '6px',
                  marginBottom: '0.5rem'
                }}>
                  <div style={{ 
                    fontWeight: 600, 
                    color: '#065f46',
                    fontSize: '1rem'
                  }}>
                    💸 {transfer.from_person} → {transfer.to_person}
                  </div>
                  <div style={{ 
                    fontSize: '1.1rem', 
                    fontWeight: 700,
                    color: '#047857',
                    marginTop: '0.25rem'
                  }}>
                    {formatCurrency(transfer.amount)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ 
              padding: '0.75rem',
              backgroundColor: '#f0fdf4',
              border: '1px solid #bbf7d0',
              borderRadius: '6px',
              textAlign: 'center'
            }}>
              <div style={{ color: '#166534', fontWeight: 500 }}>
                ✅ No hay transferencias necesarias
              </div>
              <div style={{ fontSize: '0.85rem', color: '#15803d', marginTop: '0.25rem' }}>
                Los gastos están balanceados entre ustedes
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

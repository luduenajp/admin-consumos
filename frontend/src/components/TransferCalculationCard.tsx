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
        <h2 className="panelTitle">Transferencias</h2>
        <div className="loadingContainer">
          <Spinner />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="panel">
        <h2 className="panelTitle">Transferencias</h2>
        <div className="error">
          {extractErrorMessage(error)}
        </div>
        <p className="hint" style={{ marginTop: '16px' }}>
          Cargá los ingresos para calcular las transferencias
        </p>
      </div>
    )
  }

  if (!transfers) {
    return (
      <div className="panel">
        <h2 className="panelTitle">Transferencias</h2>
        <p className="muted">
          No hay ingresos registrados para este mes
        </p>
      </div>
    )
  }

  return (
    <div className="panel">
      <h2 className="panelTitle">Transferencias</h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Resumen de ingresos */}
        <div>
          <div className="label" style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>💰</span> Ingresos del Mes
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            {transfers.ingresos.map((income) => (
              <div key={income.person_id} style={{
                padding: '16px',
                backgroundColor: 'var(--color-primary-light)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid rgba(99, 102, 241, 0.1)'
              }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-primary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' }}>
                  {income.person_name}
                </div>
                <div style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-text)' }}>
                  {formatCurrency(income.amount)}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Gastos por persona */}
        <div>
          <div className="label" style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>💳</span> Gastos Comunes Pagados
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {transfers.gastos_por_persona.map((gasto) => (
              <div key={gasto.person_id} style={{
                padding: '12px 16px',
                backgroundColor: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '1rem' }}>{gasto.person_name}</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>
                    <span title="Total que esta persona pagó de su bolsillo este mes">Pagó: {formatCurrency(gasto.paid_amount)}</span>
                    <span style={{ margin: '0 8px' }}>|</span>
                    <span title="Monto que debería haber aportado para igualar el dinero sobrante (Gastos Propios + Aporte al fondo común)">Le correspondía: {formatCurrency(gasto.should_pay)}</span>
                  </div>
                  {gasto.adjustment !== 0 && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--color-success)', marginTop: '2px', fontStyle: 'italic' }}>
                      {gasto.adjustment > 0 ? '+' : ''}{formatCurrency(gasto.adjustment)} por pagos directos
                    </div>
                  )}
                </div>
                <div
                  title={gasto.difference > 0 ? "Saldo a favor: Pagó más de lo que le correspondía" : gasto.difference < 0 ? "Saldo en contra: Pagó menos de lo que le correspondía" : "Balanceado"}
                  style={{
                    fontWeight: 800,
                    fontSize: '1rem',
                    color: gasto.difference > 0 ? 'var(--color-success)' : gasto.difference < 0 ? 'var(--color-error)' : 'var(--color-muted)'
                  }}
                >
                  {gasto.difference > 0
                    ? `+ ${formatCurrency(gasto.difference)}`
                    : gasto.difference < 0
                      ? `- ${formatCurrency(Math.abs(gasto.difference))}`
                      : '0'
                  }
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Transferencias sugeridas */}
        <div>
          <div className="label" style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>🔄</span> Resolución
          </div>
          {transfers.transferencias.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {transfers.transferencias.map((transfer, index) => (
                <div key={index} style={{
                  padding: '20px',
                  background: 'linear-gradient(135deg, #10b981, #059669)',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  boxShadow: '0 4px 12px rgba(16, 185, 129, 0.2)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, opacity: 0.9, textTransform: 'uppercase' }}>
                      {transfer.from_person} debe transferir
                    </div>
                    <div style={{ fontSize: '1.75rem', fontWeight: 800 }}>
                      {formatCurrency(transfer.amount)}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, opacity: 0.9 }}>A FAVOR DE</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{transfer.to_person}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{
              padding: '24px',
              backgroundColor: 'var(--color-success-bg)',
              border: '1px solid rgba(34, 197, 94, 0.2)',
              borderRadius: 'var(--radius-md)',
              textAlign: 'center'
            }}>
              <div style={{ color: 'var(--color-success)', fontWeight: 800, fontSize: '1.1rem' }}>
                ✅ Todo Balanceado
              </div>
              <div style={{ fontSize: '0.9rem', color: 'var(--color-success-text)', marginTop: '4px', opacity: 0.8 }}>
                No se requieren transferencias este mes
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

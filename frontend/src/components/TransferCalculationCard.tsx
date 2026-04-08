import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { fetchTransferCalculation } from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import { formatCurrency } from '../utils/format'
import { getCurrentYearMonth } from '../utils/dates'
import { Spinner } from './Spinner'

function formatSignedCurrency(amount: number): string {
  if (amount > 0) {
    return `+ ${formatCurrency(amount)}`
  }
  if (amount < 0) {
    return `- ${formatCurrency(Math.abs(amount))}`
  }
  return formatCurrency(0)
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
          Carga los ingresos para calcular las transferencias
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

  const hasExpenses = transfers.total_common_expenses > 0 || transfers.total_personal_expenses > 0

  // Data for the distribution chart
  const chartData = hasExpenses
    ? transfers.gastos_por_persona.map((g) => ({
        name: g.person_name,
        paid: Math.round(g.common_paid),
        should_pay: Math.round(g.common_should_pay),
      }))
    : []

  return (
    <div className="panel">
      <h2 className="panelTitle">Transferencias</h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Resumen de ingresos */}
        <div>
          <div className="label" style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            Ingresos del Mes
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

        {/* Distribucion por persona - chart + desglose */}
        <div>
          <div className="label" style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            Balance del Fondo Comun
          </div>
          {!hasExpenses ? (
            <div style={{
              padding: '16px',
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              textAlign: 'center'
            }}>
              <div className="muted">No hay gastos cargados para este mes</div>
              <div className="hint" style={{ marginTop: '4px' }}>
                Importa un resumen o carga compras para ver el desglose
              </div>
            </div>
          ) : (
            <>
              {/* Mini chart: pago vs deberia */}
              {chartData.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                  <ResponsiveContainer width="100%" height={160}>
                    <BarChart data={chartData} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                      <XAxis dataKey="name" stroke="var(--color-text-secondary)" style={{ fontSize: '0.8rem' }} />
                      <YAxis hide />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'var(--color-surface)',
                          border: '1px solid var(--color-border)',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '0.85rem',
                        }}
                        formatter={(value, name) => [
                          `$${Number(value).toLocaleString('es-AR', { maximumFractionDigits: 0 })}`,
                          name === 'paid' ? 'Pago' : 'Deberia pagar',
                        ]}
                      />
                      <Legend formatter={(value: string) => value === 'paid' ? 'Pago' : 'Deberia pagar'} />
                      <Bar dataKey="paid" fill="var(--color-primary)" radius={[4, 4, 0, 0]} barSize={28} />
                      <Bar dataKey="should_pay" fill="var(--color-accent)" radius={[4, 4, 0, 0]} barSize={28} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Desglose por persona */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {transfers.gastos_por_persona.map((gasto) => {
                  const hasTransfers = gasto.adjustment !== 0
                  const isSettled = Math.abs(gasto.difference) < 1
                  const owes = gasto.difference < 0

                  return (
                    <div key={gasto.person_id} style={{
                      padding: '16px',
                      backgroundColor: 'var(--color-surface)',
                      border: `1px solid ${isSettled ? 'rgba(34, 197, 94, 0.3)' : 'var(--color-border)'}`,
                      borderRadius: 'var(--radius-md)',
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                        <div style={{ fontWeight: 700, fontSize: '1rem' }}>{gasto.person_name}</div>
                        {isSettled && (
                          <span style={{
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            color: 'var(--color-success)',
                            backgroundColor: 'var(--color-success-bg)',
                            padding: '2px 8px',
                            borderRadius: 'var(--radius-sm)',
                          }}>
                            Saldado
                          </span>
                        )}
                      </div>

                      {/* Flow: Pagó → Le corresponde → Transferencias → Saldo */}
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '8px' }}>
                        <div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginBottom: '2px' }}>
                            Pagó (gastos comunes)
                          </div>
                          <div style={{ fontSize: '1.05rem', fontWeight: 600 }}>
                            {formatCurrency(gasto.common_paid)}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginBottom: '2px' }}>
                            Le corresponde (comunes)
                          </div>
                          <div style={{ fontSize: '1.05rem', fontWeight: 600 }}>
                            {gasto.common_should_pay >= 0
                              ? formatCurrency(gasto.common_should_pay)
                              : `(${formatCurrency(Math.abs(gasto.common_should_pay))} a favor)`
                            }
                          </div>
                        </div>

                        {hasTransfers && (
                          <div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginBottom: '2px' }}>
                              Transferido
                            </div>
                            <div style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--color-primary)' }}>
                              {gasto.adjustment > 0 ? '+' : ''}{formatCurrency(gasto.adjustment)}
                            </div>
                          </div>
                        )}

                        {!isSettled && (
                          <div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', marginBottom: '2px' }}>
                              {owes ? 'Debe transferir' : 'Le deben'}
                            </div>
                            <div style={{
                              fontSize: '1.05rem',
                              fontWeight: 700,
                              color: owes ? 'var(--color-error)' : 'var(--color-success)',
                            }}>
                              {formatCurrency(Math.abs(gasto.difference))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>

        {/* Transferencias sugeridas */}
        <div>
          <div className="label" style={{ marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            Resolucion
          </div>
          {!hasExpenses ? (
            <div style={{
              padding: '24px',
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              textAlign: 'center'
            }}>
              <div className="muted">Sin gastos cargados, no hay transferencias que calcular</div>
            </div>
          ) : transfers.transferencias.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {transfers.transferencias.map((transfer, index) => (
                <div key={index} style={{
                  padding: '20px',
                  background: 'linear-gradient(135deg, var(--color-success), #059669)',
                  borderRadius: 'var(--radius-md)',
                  color: 'white',
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
          ) : !transfers.is_balanced ? (
            <div style={{
              padding: '24px',
              backgroundColor: 'rgba(245, 158, 11, 0.10)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              borderRadius: 'var(--radius-md)',
              textAlign: 'center'
            }}>
              <div style={{ color: 'rgba(245, 158, 11, 0.95)', fontWeight: 800, fontSize: '1.05rem' }}>
                Sin transferencias sugeridas, pero no esta balanceado
              </div>
              <div style={{ fontSize: '0.9rem', color: 'var(--color-text-secondary)', marginTop: '6px' }}>
                Delta de balance: {formatSignedCurrency(transfers.balance_delta)}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', marginTop: '8px', opacity: 0.9 }}>
                Esto suele indicar datos incompletos o una inconsistencia en el calculo.
              </div>
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
                Todo Balanceado
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

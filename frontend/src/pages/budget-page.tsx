import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchPeople, fetchIncomes, createIncome } from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import type { IncomeCreate } from '../api/types'
import { Spinner } from '../components/Spinner'

function getCurrentYearMonth(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  return `${year}-${month}`
}

function formatYearMonth(yearMonth: string): string {
  const [year, month] = yearMonth.split('-')
  const date = new Date(parseInt(year), parseInt(month) - 1)
  return date.toLocaleDateString('es-AR', { year: 'numeric', month: 'long' })
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
  }).format(amount)
}

export function BudgetPage() {
  const [yearMonth, setYearMonth] = useState(getCurrentYearMonth())
  const [selectedPersonId, setSelectedPersonId] = useState('')
  const [amount, setAmount] = useState('')
  const [notes, setNotes] = useState('')

  const queryClient = useQueryClient()

  const { data: people, isLoading: peopleLoading } = useQuery({
    queryKey: ['people'],
    queryFn: fetchPeople,
  })

  const { data: incomes, isLoading: incomesLoading } = useQuery({
    queryKey: ['incomes', yearMonth],
    queryFn: () => fetchIncomes(yearMonth),
  })

  const createIncomeMutation = useMutation({
    mutationFn: createIncome,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incomes'] })
      queryClient.invalidateQueries({ queryKey: ['monthly-balance'] })
      setSelectedPersonId('')
      setAmount('')
      setNotes('')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedPersonId || !amount || parseFloat(amount) <= 0) return

    const payload: IncomeCreate = {
      person_id: parseInt(selectedPersonId),
      year_month: yearMonth,
      amount: parseFloat(amount),
      notes: notes.trim() || null,
    }

    createIncomeMutation.mutate(payload)
  }

  if (peopleLoading || incomesLoading) {
    return (
      <div className="loadingContainer">
        <Spinner size={32} />
      </div>
    )
  }

  const currentMonthIncomes = incomes?.filter(inc => inc.year_month === yearMonth) || []
  const totalIncome = currentMonthIncomes.reduce((sum, inc) => sum + inc.amount, 0)

  return (
    <section className="page">
      <h2 className="pageTitle">Gestión de Ingresos</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '32px' }}>
        {/* Formulario y Resumen */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
          {/* Card: Selector y Total */}
          <div className="panel" style={{ background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))', color: '#fff', border: 'none' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, opacity: 0.9, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Resumen del período
              </div>
              <input
                type="month"
                className="input"
                style={{ width: '150px', background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)', color: '#fff', padding: '8px' }}
                value={yearMonth}
                onChange={(e) => setYearMonth(e.target.value)}
              />
            </div>
            <div style={{ fontSize: '2.5rem', fontWeight: 800, marginBottom: '4px' }}>
              {formatCurrency(totalIncome)}
            </div>
            <div style={{ fontSize: '1rem', opacity: 0.8 }}>
              Ingresos totales para {formatYearMonth(yearMonth)}
            </div>
          </div>

          {/* Card: Formulario */}
          <div className="panel">
            <div className="panelTitle">Cargar Nuevo Ingreso</div>
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div className="formRow">
                <label className="label">Persona</label>
                <select
                  className="input"
                  value={selectedPersonId}
                  onChange={(e) => setSelectedPersonId(e.target.value)}
                  required
                >
                  <option value="">Seleccionar responsable...</option>
                  {people?.map((person) => (
                    <option key={person.id} value={person.id}>{person.name}</option>
                  ))}
                </select>
              </div>

              <div className="formRow">
                <label className="label">Monto (ARS)</label>
                <input
                  type="number"
                  className="input"
                  placeholder="0.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  step="0.01"
                  min="0"
                  required
                />
              </div>

              <div className="formRow">
                <label className="label">Concepto (Opcional)</label>
                <input
                  type="text"
                  className="input"
                  placeholder="Ej: Sueldo, Venta, etc."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>

              {createIncomeMutation.error && (
                <div className="error">{extractErrorMessage(createIncomeMutation.error)}</div>
              )}

              <button
                type="submit"
                className="button"
                style={{ width: '100%', height: '48px', marginTop: '8px' }}
                disabled={createIncomeMutation.isPending}
              >
                {createIncomeMutation.isPending ? 'Guardando...' : 'Registrar Ingreso'}
              </button>
            </form>
          </div>
        </div>

        {/* Card: Listado */}
        <div className="panel">
          <div className="panelTitle">Detalle de Ingresos</div>
          {currentMonthIncomes.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Persona</th>
                  <th>Concepto</th>
                  <th style={{ textAlign: 'right' }}>Monto</th>
                </tr>
              </thead>
              <tbody>
                {currentMonthIncomes.map((income) => (
                  <tr key={income.id}>
                    <td style={{ fontWeight: 600 }}>{income.person_name}</td>
                    <td>{income.notes || <span className="muted">Sin especificar</span>}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--color-success)' }}>
                      {formatCurrency(income.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ textAlign: 'center', padding: '48px 0', opacity: 0.6 }}>
              <div style={{ fontSize: '2rem', marginBottom: '16px' }}>Empty</div>
              <p>No hay ingresos registrados para este período.</p>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchPeople, fetchIncomes, createIncome } from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import type { Income, IncomeCreate } from '../api/types'
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

export default function BudgetPage() {
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
      <div className="page">
        <div className="panel">
          <Spinner />
        </div>
      </div>
    )
  }

  const currentMonthIncomes = incomes?.filter(inc => inc.year_month === yearMonth) || []
  const totalIncome = currentMonthIncomes.reduce((sum, inc) => sum + inc.amount, 0)

  return (
    <div className="page">
      <div className="panel">
        <h1 className="pageTitle">Ingresos Mensuales</h1>

        {/* Resumen del mes */}
        <div className="panel" style={{ marginTop: '2rem' }}>
          <h2 className="panelTitle">Resumen {formatYearMonth(yearMonth)}</h2>
          <div style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem' }}>
            Total ingresos: {formatCurrency(totalIncome)}
          </div>
        </div>

        {/* Formulario de carga */}
        <div className="panel" style={{ marginTop: '2rem' }}>
          <h2 className="panelTitle">Cargar Ingreso</h2>
          
          <form onSubmit={handleSubmit} className="form">
            <div className="formRow">
              <label className="label">Mes</label>
              <input
                type="month"
                className="input"
                value={yearMonth}
                onChange={(e) => setYearMonth(e.target.value)}
                required
              />
            </div>

            <div className="formRow">
              <label className="label">Persona</label>
              <select
                className="input"
                value={selectedPersonId}
                onChange={(e) => setSelectedPersonId(e.target.value)}
                required
              >
                <option value="">Seleccionar persona</option>
                {people?.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="formRow">
              <label className="label">Monto</label>
              <input
                type="number"
                className="input"
                placeholder="300000"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                step="0.01"
                min="0"
                required
              />
            </div>

            <div className="formRow">
              <label className="label">Notas (opcional)</label>
              <input
                type="text"
                className="input"
                placeholder="Sueldo, bono, etc."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>

            {createIncomeMutation.error && (
              <div className="error">
                {extractErrorMessage(createIncomeMutation.error)}
              </div>
            )}

            {createIncomeMutation.isSuccess && (
              <div className="success">
                Ingreso guardado correctamente
              </div>
            )}

            <button
              type="submit"
              className="button"
              disabled={createIncomeMutation.isPending}
              style={{ marginTop: '1rem' }}
            >
              {createIncomeMutation.isPending ? <Spinner /> : 'Guardar Ingreso'}
            </button>
          </form>
        </div>

        {/* Lista de ingresos del mes */}
        <div className="panel" style={{ marginTop: '2rem' }}>
          <h2 className="panelTitle">Ingresos del Mes</h2>
          
          {currentMonthIncomes.length > 0 ? (
            <div className="table">
              <table>
                <thead>
                  <tr>
                    <th>Persona</th>
                    <th>Monto</th>
                    <th>Notas</th>
                  </tr>
                </thead>
                <tbody>
                  {currentMonthIncomes.map((income) => (
                    <tr key={income.id}>
                      <td>{income.person_name}</td>
                      <td>{formatCurrency(income.amount)}</td>
                      <td>{income.notes || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">No hay ingresos cargados para este mes</p>
          )}
        </div>
      </div>
    </div>
  )
}

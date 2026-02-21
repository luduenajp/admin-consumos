import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { fetchCards, fetchPeople, fetchPurchases, fetchDebtors, updatePurchase, deletePurchase, createPurchase } from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import type { PurchaseUpdate } from '../api/types'
import { Spinner } from '../components/Spinner'

function EditableCell({
  value,
  placeholder,
  onSave,
}: {
  value: string | null | undefined
  placeholder: string
  onSave: (val: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value ?? '')

  if (!editing) {
    return (
      <span
        className={value ? '' : 'muted'}
        style={{ cursor: 'pointer' }}
        onClick={() => {
          setDraft(value ?? '')
          setEditing(true)
        }}
      >
        {value || placeholder}
      </span>
    )
  }

  return (
    <input
      type="text"
      className="input"
      style={{ padding: '4px 8px', fontSize: '0.85rem', width: '100%' }}
      value={draft}
      autoFocus
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          onSave(draft)
          setEditing(false)
        }
        if (e.key === 'Escape') {
          setEditing(false)
        }
      }}
      onBlur={() => {
        onSave(draft)
        setEditing(false)
      }}
    />
  )
}

const PAGE_SIZE = 50

export function PurchasesPage() {
  // Filter state
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [minAmount, setMinAmount] = useState<string>('')
  const [maxAmount, setMaxAmount] = useState<string>('')
  const [descriptionSearch, setDescriptionSearch] = useState<string>('')
  const [debtorFilter, setDebtorFilter] = useState<string>('')
  const [personFilter, setPersonFilter] = useState<string>('')
  const [page, setPage] = useState(1)

  const queryClient = useQueryClient()

  // Build filters object (include pagination)
  const filters = {
    startDate: startDate || undefined,
    endDate: endDate || undefined,
    minAmount: minAmount ? parseFloat(minAmount) : undefined,
    maxAmount: maxAmount ? parseFloat(maxAmount) : undefined,
    descriptionSearch: descriptionSearch || undefined,
    personId: personFilter ? Number(personFilter) : undefined,
    page,
    pageSize: PAGE_SIZE,
  }

  // Queries
  const { data, isLoading, error } = useQuery({
    queryKey: ['purchases', filters],
    queryFn: () => fetchPurchases(filters),
  })

  const { data: debtorsData } = useQuery({
    queryKey: ['debtors'],
    queryFn: fetchDebtors,
  })

  const { data: peopleData } = useQuery({
    queryKey: ['people'],
    queryFn: fetchPeople,
  })

  const { data: cardsData } = useQuery({
    queryKey: ['cards'],
    queryFn: fetchCards,
  })

  const debtors = debtorsData ?? []
  const people = peopleData ?? []
  const cards = cardsData ?? []

  const cardNameById = new Map(cards.map((c) => [c.id, c.name]))

  const formatPayers = (payers: { person_name: string; share_type: string; share_value: number }[]) => {
    if (!payers || payers.length === 0) return '-'
    return payers
      .map((p) => {
        if (p.share_type === 'percent') return `${p.person_name} (${p.share_value}%)`
        return `${p.person_name} ($${p.share_value})`
      })
      .join(', ')
  }

  // Mutation for inline editing
  const patchMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: PurchaseUpdate }) => updatePurchase(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchases'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deletePurchase(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchases'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })

  // Manual Creation State
  const [showAddForm, setShowAddForm] = useState(false)
  const [newPurchase, setNewPurchase] = useState({
    purchase_date: new Date().toISOString().split('T')[0],
    description: '',
    payment_method: 'cash' as const,
    amount_original: '',
    currency: 'ARS' as const,
    owner_person_id: '',
    debtor_id: '',
    notes: '',
  })

  const createMutation = useMutation({
    mutationFn: (payload: any) => createPurchase(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchases'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      setShowAddForm(false)
      setNewPurchase({
        purchase_date: new Date().toISOString().split('T')[0],
        description: '',
        payment_method: 'cash' as const,
        amount_original: '',
        currency: 'ARS' as const,
        owner_person_id: '',
        debtor_id: '',
        notes: '',
      })
    },
    onError: (err) => {
      alert(`Error al crear compra: ${extractErrorMessage(err)}`)
    },
  })

  const handleAddSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newPurchase.description || !newPurchase.amount_original || !newPurchase.owner_person_id) {
      alert('Por favor completa los campos obligatorios (Descripción, Monto, Pagado por)')
      return
    }

    createMutation.mutate({
      ...newPurchase,
      amount_original: parseFloat(newPurchase.amount_original),
      owner_person_id: Number(newPurchase.owner_person_id),
      debtor_id: newPurchase.debtor_id ? Number(newPurchase.debtor_id) : null,
      installments_total: 1,
    })
  }

  const handleReset = () => {
    setStartDate('')
    setEndDate('')
    setMinAmount('')
    setMaxAmount('')
    setDescriptionSearch('')
    setDebtorFilter('')
    setPersonFilter('')
    setPage(1)
  }

  if (isLoading)
    return (
      <div className="loadingContainer">
        <Spinner size={32} />
      </div>
    )
  if (error) return <div className="error">Error: {extractErrorMessage(error)}</div>

  const items = data?.items ?? []
  // Client-side debtor filter (backend doesn't have this filter yet)
  let rows = items
  if (debtorFilter === 'none') {
    rows = rows.filter((p) => !p.debtor_id)
  } else if (debtorFilter === 'any') {
    rows = rows.filter((p) => !!p.debtor_id)
  } else if (debtorFilter) {
    rows = rows.filter((p) => p.debtor_id === Number(debtorFilter))
  }

  const total = data?.total ?? 0
  const pages = data?.pages ?? 0
  const currentPage = data?.page ?? 1

  return (
    <section className="page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h2 className="pageTitle" style={{ margin: 0 }}>
          Compras
        </h2>
        <button type="button" className="button" style={{ background: 'var(--color-primary)', color: 'white' }} onClick={() => setShowAddForm(!showAddForm)}>
          {showAddForm ? 'Cancelar' : '+ Nueva compra manual'}
        </button>
      </div>

      {showAddForm && (
        <div className="panel" style={{ marginBottom: '24px', border: '1px solid var(--color-primary)' }}>
          <div className="panelTitle">Nueva compra (Efectivo / Transferencia)</div>
          <form onSubmit={handleAddSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <div className="formRow">
                <label className="label">Fecha</label>
                <input
                  type="date"
                  className="input"
                  required
                  value={newPurchase.purchase_date}
                  onChange={(e) => setNewPurchase({ ...newPurchase, purchase_date: e.target.value })}
                />
              </div>
              <div className="formRow">
                <label className="label">Descripción</label>
                <input
                  type="text"
                  className="input"
                  required
                  placeholder="Ej: Almuerzo, Supermercado..."
                  value={newPurchase.description}
                  onChange={(e) => setNewPurchase({ ...newPurchase, description: e.target.value })}
                />
              </div>
              <div className="formRow">
                <label className="label">Monto</label>
                <input
                  type="number"
                  step="0.01"
                  className="input"
                  required
                  placeholder="0.00"
                  value={newPurchase.amount_original}
                  onChange={(e) => setNewPurchase({ ...newPurchase, amount_original: e.target.value })}
                />
              </div>
              <div className="formRow">
                <label className="label">Moneda</label>
                <select
                  className="input"
                  value={newPurchase.currency}
                  onChange={(e) => setNewPurchase({ ...newPurchase, currency: e.target.value as any })}
                >
                  <option value="ARS">ARS</option>
                  <option value="USD">USD</option>
                </select>
              </div>
              <div className="formRow">
                <label className="label">Pagado por</label>
                <select
                  className="input"
                  required
                  value={newPurchase.owner_person_id}
                  onChange={(e) => setNewPurchase({ ...newPurchase, owner_person_id: e.target.value })}
                >
                  <option value="">Seleccionar...</option>
                  {people.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="formRow">
                <label className="label">Medio de pago</label>
                <select
                  className="input"
                  value={newPurchase.payment_method}
                  onChange={(e) => setNewPurchase({ ...newPurchase, payment_method: e.target.value as any })}
                >
                  <option value="cash">Efectivo</option>
                  <option value="transfer">Transferencia</option>
                </select>
              </div>
              <div className="formRow">
                <label className="label">Deudor (Opcional)</label>
                <select
                  className="input"
                  value={newPurchase.debtor_id}
                  onChange={(e) => setNewPurchase({ ...newPurchase, debtor_id: e.target.value })}
                >
                  <option value="">Ninguno</option>
                  {debtors.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="formRow">
                <label className="label">Detalle / Notas</label>
                <input
                  type="text"
                  className="input"
                  placeholder="Opcional..."
                  value={newPurchase.notes}
                  onChange={(e) => setNewPurchase({ ...newPurchase, notes: e.target.value })}
                />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
              <button type="submit" className="button" style={{ background: 'var(--color-primary)', color: 'white' }} disabled={createMutation.isPending}>
                {createMutation.isPending ? 'Guardando...' : 'Guardar compra'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filter Panel */}
      <div className="panel">
        <div className="panelTitle">Filtros</div>
        <div style={{ display: 'grid', gap: '12px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
            <div className="formRow">
              <label className="label">Descripción</label>
              <input
                type="text"
                className="input"
                placeholder="Buscar en descripción..."
                value={descriptionSearch}
                onChange={(e) => {
                  setDescriptionSearch(e.target.value)
                  setPage(1)
                }}
              />
            </div>

            <div className="formRow">
              <label className="label">Pagado por</label>
              <select
                className="input"
                value={personFilter}
                onChange={(e) => {
                  setPersonFilter(e.target.value)
                  setPage(1)
                }}
              >
                <option value="">Todos</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <div className="hint">Gastos que pagó esta persona (según reparto)</div>
            </div>

            <div className="formRow">
              <label className="label">Deudor</label>
              <select
                className="input"
                value={debtorFilter}
                onChange={(e) => setDebtorFilter(e.target.value)}
              >
                <option value="">Todos</option>
                <option value="any">Con deudor</option>
                <option value="none">Sin deudor</option>
                {debtors.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div className="formRow">
              <label className="label">Fecha desde</label>
              <input
                type="date"
                className="input"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value)
                  setPage(1)
                }}
              />
            </div>

            <div className="formRow">
              <label className="label">Fecha hasta</label>
              <input
                type="date"
                className="input"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value)
                  setPage(1)
                }}
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div className="formRow">
              <label className="label">Monto mínimo</label>
              <input
                type="number"
                className="input"
                placeholder="0"
                value={minAmount}
                onChange={(e) => {
                  setMinAmount(e.target.value)
                  setPage(1)
                }}
              />
            </div>

            <div className="formRow">
              <label className="label">Monto máximo</label>
              <input
                type="number"
                className="input"
                placeholder="Sin límite"
                value={maxAmount}
                onChange={(e) => {
                  setMaxAmount(e.target.value)
                  setPage(1)
                }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
            <button type="button" className="button" onClick={handleReset}>
              Limpiar filtros
            </button>
          </div>
        </div>
      </div>

      {/* Results Panel */}
      <div className="panel">
        <div className="panelTitle">
          Resultados{' '}
          {debtorFilter ? `(${rows.length} en esta página)` : total > 0 ? `(${total} en total)` : ''}
        </div>
        {rows.length === 0 ? (
          <div className="muted">Sin compras que coincidan con los filtros</div>
        ) : (
          <>
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Medio de pago</th>
                    <th>Descripción</th>
                    <th>Pagó</th>
                    <th>Detalle</th>
                    <th>Moneda</th>
                    <th>Monto</th>
                    <th>Cuotas</th>
                    <th>Deudor</th>
                    <th>Saldado</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => (
                    <tr key={p.id}>
                      <td>{p.purchase_date}</td>
                      <td>
                        {p.payment_method === 'transfer' ? 'Transferencia' :
                          p.payment_method === 'cash' ? 'Efectivo' :
                            (p.card_id ? (cardNameById.get(p.card_id) ?? `#${p.card_id}`) : '-')}
                      </td>
                      <td>{p.description}</td>
                      <td>{formatPayers(p.payers)}</td>
                      <td>
                        <EditableCell
                          value={p.notes}
                          placeholder="Agregar detalle..."
                          onSave={(val) => {
                            if (val !== (p.notes ?? '')) {
                              patchMutation.mutate({ id: p.id, payload: { notes: val || null } })
                            }
                          }}
                        />
                      </td>
                      <td>{p.currency}</td>
                      <td>
                        {p.amount_original.toLocaleString('es-AR', {
                          maximumFractionDigits: 2,
                        })}
                      </td>
                      <td>{p.installments_total}</td>
                      <td>
                        <select
                          className="input"
                          style={{ padding: '4px 8px', fontSize: '0.85rem' }}
                          value={p.debtor_id ?? ''}
                          onChange={(e) => {
                            const newDebtorId = e.target.value ? Number(e.target.value) : null
                            patchMutation.mutate({
                              id: p.id,
                              payload: {
                                debtor_id: newDebtorId,
                                ...(newDebtorId === null ? { debt_settled: false } : {}),
                              },
                            })
                          }}
                        >
                          <option value="">-</option>
                          {debtors.map((d) => (
                            <option key={d.id} value={d.id}>
                              {d.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        {p.debtor_id ? (
                          <input
                            type="checkbox"
                            checked={p.debt_settled}
                            onChange={(e) => {
                              patchMutation.mutate({ id: p.id, payload: { debt_settled: e.target.checked } })
                            }}
                          />
                        ) : (
                          <span className="muted">-</span>
                        )}
                      </td>
                      <td>
                        <button
                          type="button"
                          className="button"
                          style={{ padding: '4px 8px', fontSize: '0.8rem', background: '#c0392b', border: 'none', color: '#fff', borderRadius: '4px', cursor: 'pointer' }}
                          disabled={deleteMutation.isPending}
                          onClick={() => {
                            if (window.confirm(`¿Eliminar "${p.description}"? Esta acción no se puede deshacer.`)) {
                              deleteMutation.mutate(p.id)
                            }
                          }}
                        >
                          🗑
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {pages > 1 ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  marginTop: '16px',
                  flexWrap: 'wrap',
                }}
              >
                <button
                  type="button"
                  className="button"
                  disabled={currentPage <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Anterior
                </button>
                <span className="muted" style={{ margin: 0 }}>
                  Página {currentPage} de {pages}
                </span>
                <button
                  type="button"
                  className="button"
                  disabled={currentPage >= pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Siguiente
                </button>
              </div>
            ) : null}
          </>
        )}
      </div>
    </section>
  )
}

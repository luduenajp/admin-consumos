import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import {
  fetchCards,
  fetchPeople,
  fetchPurchases,
  fetchDebtors,
  updatePurchase,
  deletePurchase,
  bulkUpdatePurchases,
  fetchCategories,
  autoCategorizePurchases
} from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import type { PurchaseUpdate, Category } from '../api/types'
import { Spinner } from '../components/Spinner'
import { PurchaseForm } from '../components/PurchaseForm'
import { ConfirmDialog } from '../components/ConfirmDialog'

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
  const [categoryFilter, setCategoryFilter] = useState<string>('')
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
    category: categoryFilter || undefined,
    page,
    pageSize: PAGE_SIZE,
  }

  // Queries
  const { data, isLoading, error } = useQuery({
    queryKey: ['purchases', filters],
    queryFn: () => fetchPurchases(filters),
  })

  const { data: categoriesData } = useQuery<Category[]>({
    queryKey: ['categories'],
    queryFn: fetchCategories,
  })

  const autoCategorizeMutation = useMutation({
    mutationFn: autoCategorizePurchases,
    onSuccess: (res) => {
      alert(`Se actualizaron ${res.updated} compras automáticamente.`)
      queryClient.invalidateQueries({ queryKey: ['purchases'] })
    },
    onError: (err) => {
      alert(`Error al auto-categorizar: ${extractErrorMessage(err)}`)
    },
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

  const bulkMutation = useMutation({
    mutationFn: ({ ids, update }: { ids: number[]; update: PurchaseUpdate }) => bulkUpdatePurchases({ purchase_ids: ids, update }),
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

  // Delete confirmation state
  const [pendingDelete, setPendingDelete] = useState<{ id: number; description: string } | null>(null)

  const handleReset = () => {
    setStartDate('')
    setEndDate('')
    setMinAmount('')
    setMaxAmount('')
    setDescriptionSearch('')
    setDebtorFilter('')
    setPersonFilter('')
    setCategoryFilter('')
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
    <>
    <section className="page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <h2 className="pageTitle" style={{ margin: 0 }}>
          Compras
        </h2>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button type="button" className="button ghost" onClick={() => autoCategorizeMutation.mutate()} disabled={autoCategorizeMutation.isPending}>
            {autoCategorizeMutation.isPending ? 'Procesando...' : '🪄 Auto-categorizar'}
          </button>
          <button type="button" className="button" onClick={() => setShowAddForm(!showAddForm)}>
            {showAddForm ? '✕ Cancelar' : '+ Nueva compra manual'}
          </button>
        </div>
      </div>

      {showAddForm && (
        <div className="panel" style={{ marginBottom: '32px', border: '1px solid var(--color-primary)', animation: 'fadeIn 0.3s ease' }}>
          <div className="panelTitle">Nueva compra</div>
          <PurchaseForm
            onSuccess={() => setShowAddForm(false)}
            onCancel={() => setShowAddForm(false)}
          />
        </div>
      )}

      {/* Filter Panel */}
      <div className="panel" style={{ padding: '24px', marginBottom: '32px' }}>
        <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: '24px' }}>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Pagado por</label>
            <select className="input" style={{ width: '160px' }} value={personFilter} onChange={(e) => { setPersonFilter(e.target.value); setPage(1); }}>
              <option value="">Todos</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Deudor</label>
            <select className="input" style={{ width: '160px' }} value={debtorFilter} onChange={(e) => { setDebtorFilter(e.target.value); setPage(1); }}>
              <option value="">Todos</option>
              <option value="any">Con deudor</option>
              <option value="none">Sin deudor</option>
              {debtors.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Categoría</label>
            <select className="input" style={{ width: '160px' }} value={categoryFilter} onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}>
              <option value="">Todas</option>
              <option value="null">Sin categoría</option>
              {categoriesData?.map((c) => (
                <option key={c.id} value={c.name}>{c.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Desde</label>
            <input type="date" className="input" style={{ width: '150px' }} value={startDate} onChange={(e) => { setStartDate(e.target.value); setPage(1); }} />
          </div>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Hasta</label>
            <input type="date" className="input" style={{ width: '150px' }} value={endDate} onChange={(e) => { setEndDate(e.target.value); setPage(1); }} />
          </div>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Mín ($)</label>
            <input type="number" className="input" style={{ width: '100px' }} placeholder="0" value={minAmount} onChange={(e) => { setMinAmount(e.target.value); setPage(1); }} />
          </div>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Máx ($)</label>
            <input type="number" className="input" style={{ width: '100px' }} placeholder="∞" value={maxAmount} onChange={(e) => { setMaxAmount(e.target.value); setPage(1); }} />
          </div>
          <div style={{ marginLeft: 'auto' }}>
            <button type="button" className="button" style={{ height: '42px' }} onClick={handleReset}>
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
        {
          rows.length === 0 ? (
            <div className="muted">Sin compras que coincidan con los filtros</div>
          ) : (
            <>
              <div className="tableContainer">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Tipo</th>
                      <th style={{ textAlign: 'center' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
                          <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', opacity: 0.8 }}>Común</span>
                          <input
                            type="checkbox"
                            title="Seleccionar todos como común/no común"
                            style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                            checked={rows.length > 0 && rows.every(r => r.is_common)}
                            ref={el => {
                              if (el) {
                                const someChecked = rows.some(r => r.is_common);
                                const allChecked = rows.every(r => r.is_common);
                                el.indeterminate = someChecked && !allChecked;
                              }
                            }}
                            onChange={(e) => {
                              const ids = rows.map(r => r.id);
                              bulkMutation.mutate({ ids, update: { is_common: e.target.checked } });
                            }}
                          />
                        </div>
                      </th>
                      <th>Descripción</th>
                      <th>Categoría</th>
                      <th>Pagó</th>
                      <th>Detalle</th>
                      <th>Moneda</th>
                      <th>Monto</th>
                      <th>Cuotas</th>
                      <th>Beneficiario</th>
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
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <span style={{ fontSize: '0.85rem' }}>
                              {p.payment_method === 'transfer' ? 'Transferencia' :
                                p.payment_method === 'cash' ? 'Efectivo' :
                                  (p.card_id ? (cardNameById.get(p.card_id) ?? `#${p.card_id}`) : '-')}
                            </span>
                          </div>
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          <input
                            type="checkbox"
                            checked={p.is_common}
                            title="Marcar como gasto común"
                            style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                            onChange={(e) => {
                              patchMutation.mutate({ id: p.id, payload: { is_common: e.target.checked } })
                            }}
                          />
                        </td>
                        <td>{p.description}</td>
                        <td>
                          <select
                            className="input"
                            style={{ padding: '4px 8px', fontSize: '0.85rem' }}
                            value={p.category ?? ''}
                            onChange={(e) => {
                              patchMutation.mutate({ id: p.id, payload: { category: e.target.value || null } })
                            }}
                          >
                            <option value="">-</option>
                            {categoriesData?.map((cat) => (
                              <option key={cat.id} value={cat.name}>
                                {cat.name}
                              </option>
                            ))}
                          </select>
                        </td>
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
                          {!p.is_common ? (
                            <select
                              className="input"
                              style={{ padding: '4px 8px', fontSize: '0.85rem' }}
                              value={p.beneficiary_person_id ?? ''}
                              onChange={(e) => {
                                const newBenId = e.target.value ? Number(e.target.value) : null
                                patchMutation.mutate({
                                  id: p.id,
                                  payload: { beneficiary_person_id: newBenId },
                                })
                              }}
                            >
                              <option value="">(Pagador)</option>
                              {people.map((person) => (
                                <option key={person.id} value={person.id}>
                                  {person.name}
                                </option>
                              ))}
                            </select>
                          ) : (
                            <span className="muted">-</span>
                          )}
                        </td>
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
                            onClick={() => setPendingDelete({ id: p.id, description: p.description })}
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
          )
        }
      </div >
    </section>

    <ConfirmDialog
      open={pendingDelete !== null}
      message={pendingDelete ? `¿Eliminar "${pendingDelete.description}"? Esta acción no se puede deshacer.` : ''}
      confirmLabel="Eliminar"
      dangerous
      onConfirm={() => {
        if (pendingDelete) deleteMutation.mutate(pendingDelete.id)
        setPendingDelete(null)
      }}
      onCancel={() => setPendingDelete(null)}
    />
    </>
  )
}

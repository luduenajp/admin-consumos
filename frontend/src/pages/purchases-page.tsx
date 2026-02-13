import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import { fetchPeople, fetchPurchases, fetchCategories, fetchDebtors, updatePurchase } from '../api/endpoints'
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
  const [category, setCategory] = useState<string>('')
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
    category: category || undefined,
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

  const { data: categoriesData } = useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
  })

  const { data: debtorsData } = useQuery({
    queryKey: ['debtors'],
    queryFn: fetchDebtors,
  })

  const { data: peopleData } = useQuery({
    queryKey: ['people'],
    queryFn: fetchPeople,
  })

  const categories = categoriesData?.categories ?? []
  const debtors = debtorsData ?? []
  const people = peopleData ?? []

  // Mutation for inline editing
  const patchMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: PurchaseUpdate }) => updatePurchase(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchases'] })
      queryClient.invalidateQueries({ queryKey: ['categories'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })

  const handleReset = () => {
    setCategory('')
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
      <h2 className="pageTitle">Compras</h2>

      {/* Filter Panel */}
      <div className="panel">
        <div className="panelTitle">Filtros</div>
        <div style={{ display: 'grid', gap: '12px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
            <div className="formRow">
              <label className="label">Categoría</label>
              <select
                className="input"
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value)
                  setPage(1)
                }}
              >
                <option value="">Todas</option>
                <option value="null">Sin categoría</option>
                {categories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

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
                  <th>Descripción</th>
                  <th>Detalle</th>
                  <th>Categoría</th>
                  <th>Moneda</th>
                  <th>Monto</th>
                  <th>Cuotas</th>
                  <th>Deudor</th>
                  <th>Saldado</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.id}>
                    <td>{p.purchase_date}</td>
                    <td>{p.description}</td>
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
                    <td>
                      <EditableCell
                        value={p.category}
                        placeholder="Sin categoría"
                        onSave={(val) => {
                          if (val !== (p.category ?? '')) {
                            patchMutation.mutate({ id: p.id, payload: { category: val || null } })
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

import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
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
  autoCategorizePurchases,
  fetchImportBatches,
  createBeneficiary,
  uploadComprobante,
} from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import type { PurchaseUpdate, Category, ComprobanteExtraction } from '../api/types'
import { Spinner } from '../components/Spinner'
import { PurchaseForm } from '../components/PurchaseForm'
import type { PurchaseFormInitialValues } from '../components/PurchaseForm'
import { ConfirmDialog } from '../components/ConfirmDialog'

function EditableCell({
  value,
  placeholder,
  onSave,
  required = false,
}: {
  value: string | null | undefined
  placeholder: string
  onSave: (val: string) => void
  required?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value ?? '')
  const [cellError, setCellError] = useState('')

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
    <div>
      <input
        type="text"
        className="input"
        style={{ padding: '4px 8px', fontSize: '0.85rem', width: '100%' }}
        value={draft}
        autoFocus
        onChange={(e) => {
          setDraft(e.target.value)
          if (cellError) setCellError('')
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            if (required && !draft.trim()) {
              setCellError('Requerido')
              return
            }
            onSave(draft)
            setEditing(false)
            setCellError('')
          }
          if (e.key === 'Escape') {
            setEditing(false)
            setCellError('')
          }
        }}
        onBlur={() => {
          if (required && !draft.trim()) {
            setCellError('Requerido')
            return
          }
          onSave(draft)
          setEditing(false)
          setCellError('')
        }}
      />
      {cellError && <span className="fieldError">{cellError}</span>}
    </div>
  )
}

const PAGE_SIZE = 50

export function PurchasesPage() {
  const [searchParams] = useSearchParams()

  // Filter state
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [minAmount, setMinAmount] = useState<string>('')
  const [maxAmount, setMaxAmount] = useState<string>('')
  const [descriptionInput, setDescriptionInput] = useState<string>('')
  const [descriptionSearch, setDescriptionSearch] = useState<string>('')
  const [debtorFilter, setDebtorFilter] = useState<string>('')
  const [personFilter, setPersonFilter] = useState<string>('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [batchFilter, setBatchFilter] = useState<string>(searchParams.get('batch') ?? '')
  const [page, setPage] = useState(1)

  const queryClient = useQueryClient()

  useEffect(() => {
    const timer = setTimeout(() => {
      setDescriptionSearch(descriptionInput)
      setPage(1)
    }, 350)
    return () => clearTimeout(timer)
  }, [descriptionInput])

  // Build filters object (include pagination)
  const filters = {
    startDate: startDate || undefined,
    endDate: endDate || undefined,
    minAmount: minAmount ? parseFloat(minAmount) : undefined,
    maxAmount: maxAmount ? parseFloat(maxAmount) : undefined,
    descriptionSearch: descriptionSearch || undefined,
    personId: personFilter ? Number(personFilter) : undefined,
    category: categoryFilter || undefined,
    importBatchId: batchFilter ? Number(batchFilter) : undefined,
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

  const { data: batchesData } = useQuery({
    queryKey: ['import-batches'],
    queryFn: fetchImportBatches,
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
  const [showFilters, setShowFilters] = useState(false)
  const [mobileEditId, setMobileEditId] = useState<number | null>(null)

  // Comprobante flow state
  const [comprobanteLoading, setComprobanteLoading] = useState(false)
  const [comprobanteError, setComprobanteError] = useState<string | null>(null)
  const [comprobanteBanner, setComprobanteBanner] = useState<{
    type: 'recognized' | 'unrecognized'
    extraction: ComprobanteExtraction
  } | null>(null)
  const [showSaveBeneficiaryModal, setShowSaveBeneficiaryModal] = useState(false)
  const [newBeneficiaryName, setNewBeneficiaryName] = useState('')
  const [newBeneficiaryCbu, setNewBeneficiaryCbu] = useState('')
  const [newBeneficiaryAlias, setNewBeneficiaryAlias] = useState('')
  const [purchaseInitialValues, setPurchaseInitialValues] = useState<PurchaseFormInitialValues | undefined>(undefined)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Delete confirmation state
  const [pendingDelete, setPendingDelete] = useState<{ id: number; description: string } | null>(null)

  const handleReset = () => {
    setStartDate('')
    setEndDate('')
    setMinAmount('')
    setMaxAmount('')
    setDescriptionInput('')
    setDescriptionSearch('')
    setDebtorFilter('')
    setPersonFilter('')
    setCategoryFilter('')
    setBatchFilter('')
    setPage(1)
  }

  const handleComprobanteFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    // Reset file input so same file can be re-selected
    e.target.value = ''

    setComprobanteError(null)
    setComprobanteBanner(null)
    setComprobanteLoading(true)

    try {
      const extraction = await uploadComprobante(file)

      const initial: PurchaseFormInitialValues = {
        amount_original: extraction.amount ?? undefined,
        purchase_date: extraction.date ?? undefined,
        currency: extraction.currency ?? 'ARS',
        description: extraction.description ?? undefined,
        payment_method: 'transfer',
        installments_total: 1,
      }
      setPurchaseInitialValues(initial)
      setShowAddForm(true)

      if (extraction.matched_beneficiary) {
        setComprobanteBanner({ type: 'recognized', extraction })
      } else if (extraction.raw_extracted?.nombre) {
        setComprobanteBanner({ type: 'unrecognized', extraction })
        setNewBeneficiaryName(extraction.raw_extracted.nombre ?? '')
        setNewBeneficiaryCbu(extraction.raw_extracted.cbu ?? '')
        setNewBeneficiaryAlias(extraction.raw_extracted.alias ?? '')
      }
    } catch (err) {
      setComprobanteError(extractErrorMessage(err))
      setPurchaseInitialValues(undefined)
      setShowAddForm(true) // open form empty for manual entry
    } finally {
      setComprobanteLoading(false)
    }
  }

  const saveBeneficiaryMutation = useMutation({
    mutationFn: () => createBeneficiary({
      name: newBeneficiaryName.trim(),
      cbu: newBeneficiaryCbu.trim() || undefined,
      alias: newBeneficiaryAlias.trim() || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['beneficiaries'] })
      setShowSaveBeneficiaryModal(false)
      setComprobanteBanner(null)
    },
  })

  if (isLoading)
    return (
      <div className="loadingContainer">
        <Spinner size={32} />
      </div>
    )
  if (error) return <div className="error">Error: {extractErrorMessage(error)}</div>

  const items = data?.items ?? []
  const mobileEditPurchase = mobileEditId !== null ? items.find((p) => p.id === mobileEditId) ?? null : null
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
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,application/pdf"
            style={{ display: 'none' }}
            onChange={handleComprobanteFileChange}
          />
          <button
            type="button"
            className="button ghost"
            onClick={() => fileInputRef.current?.click()}
            disabled={comprobanteLoading}
          >
            {comprobanteLoading ? 'Analizando...' : '📎 Desde comprobante'}
          </button>
          <button type="button" className="button" onClick={() => { setShowAddForm(!showAddForm); setPurchaseInitialValues(undefined); setComprobanteBanner(null) }}>
            {showAddForm ? '✕ Cancelar' : '+ Nueva compra manual'}
          </button>
        </div>
      </div>

      {/* Comprobante error */}
      {comprobanteError && (
        <div className="error" style={{ marginBottom: '16px', padding: '12px 16px', borderRadius: '6px', background: '#fef2f2', border: '1px solid #fca5a5' }}>
          Error al analizar comprobante: {comprobanteError}
        </div>
      )}

      {/* Recognized banner */}
      {comprobanteBanner?.type === 'recognized' && (
        <div style={{ marginBottom: '16px', padding: '12px 16px', borderRadius: '6px', background: '#f0fdf4', border: '1px solid #86efac', color: '#166534' }}>
          ✓ Destinatario reconocido: <strong>{comprobanteBanner.extraction.matched_beneficiary?.name}</strong>
        </div>
      )}

      {/* Unrecognized banner with save option */}
      {comprobanteBanner?.type === 'unrecognized' && !showSaveBeneficiaryModal && (
        <div style={{ marginBottom: '16px', padding: '12px 16px', borderRadius: '6px', background: '#fefce8', border: '1px solid #fde047', color: '#854d0e', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>¿Guardar "<strong>{comprobanteBanner.extraction.raw_extracted?.nombre}</strong>" como destinatario frecuente?</span>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button type="button" className="button" style={{ padding: '6px 12px', fontSize: '0.85rem' }} onClick={() => setShowSaveBeneficiaryModal(true)}>Guardar</button>
            <button type="button" className="button ghost" style={{ padding: '6px 12px', fontSize: '0.85rem' }} onClick={() => setComprobanteBanner(null)}>Ignorar</button>
          </div>
        </div>
      )}

      {/* Save beneficiary mini modal */}
      {showSaveBeneficiaryModal && (
        <div className="panel" style={{ marginBottom: '16px', border: '1px solid #fde047' }}>
          <div className="panelTitle">Guardar destinatario frecuente</div>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <div className="formRow" style={{ flex: 1, marginBottom: 0 }}>
              <label className="label">Nombre *</label>
              <input className="input" value={newBeneficiaryName} onChange={e => setNewBeneficiaryName(e.target.value)} placeholder="Nombre del destinatario" />
            </div>
            <div className="formRow" style={{ flex: 1, marginBottom: 0 }}>
              <label className="label">CBU</label>
              <input className="input" value={newBeneficiaryCbu} onChange={e => setNewBeneficiaryCbu(e.target.value)} placeholder="22 dígitos" />
            </div>
            <div className="formRow" style={{ flex: 1, marginBottom: 0 }}>
              <label className="label">Alias</label>
              <input className="input" value={newBeneficiaryAlias} onChange={e => setNewBeneficiaryAlias(e.target.value)} placeholder="ej: verduleria.lopez" />
            </div>
          </div>
          <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
            <button type="button" className="button" onClick={() => saveBeneficiaryMutation.mutate()} disabled={!newBeneficiaryName.trim() || saveBeneficiaryMutation.isPending}>
              {saveBeneficiaryMutation.isPending ? 'Guardando...' : 'Confirmar'}
            </button>
            <button type="button" className="button ghost" onClick={() => { setShowSaveBeneficiaryModal(false); setComprobanteBanner(null); }}>Cancelar</button>
          </div>
        </div>
      )}

      {showAddForm && (
        <div className="panel" style={{ marginBottom: '32px', border: '1px solid var(--color-primary)', animation: 'fadeIn 0.3s ease' }}>
          <div className="panelTitle">{purchaseInitialValues ? 'Nueva compra desde comprobante' : 'Nueva compra'}</div>
          <PurchaseForm
            initialValues={purchaseInitialValues}
            onSuccess={() => { setShowAddForm(false); setPurchaseInitialValues(undefined); setComprobanteBanner(null); }}
            onCancel={() => { setShowAddForm(false); setPurchaseInitialValues(undefined); setComprobanteBanner(null); }}
          />
        </div>
      )}

      {/* Mobile filter toggle — hidden on desktop via CSS */}
      <button
        type="button"
        className="button ghost purchaseMobileFilterToggle"
        onClick={() => setShowFilters((s) => !s)}
      >
        {showFilters ? '▲ Ocultar filtros' : '▼ Filtros'}
      </button>

      {/* Filter Panel */}
      <div
        className={`panel purchaseFiltersPanel${showFilters ? ' purchaseFiltersPanelOpen' : ''}`}
        style={{ padding: '24px', marginBottom: '32px' }}
      >
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
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Importación</label>
            <select className="input" style={{ width: '220px' }} value={batchFilter} onChange={(e) => { setBatchFilter(e.target.value); setPage(1); }}>
              <option value="">Todas</option>
              {batchesData?.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.source_file} ({b.imported_at.slice(0, 10)}) — {b.purchases_created} creadas
                </option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Buscar</label>
            <input type="text" className="input" style={{ width: '220px' }} placeholder="Descripción o detalle..." value={descriptionInput} onChange={(e) => setDescriptionInput(e.target.value)} />
          </div>
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
        {rows.length === 0 ? (
          <div className="muted">Sin compras que coincidan con los filtros</div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="tableContainer purchaseDesktopTable">
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

            {/* Mobile card list */}
            <div className="purchaseCardList">
              {rows.map((p) => {
                const categoryObj = categoriesData?.find((c) => c.name === p.category)
                const payerName = p.payers?.[0]?.person_name ?? '-'
                const cardName = p.card_id ? (cardNameById.get(p.card_id) ?? null) : null
                return (
                  <div
                    key={p.id}
                    className="purchaseCard"
                    onClick={() => setMobileEditId(p.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && setMobileEditId(p.id)}
                  >
                    <div className="purchaseCardHeader">
                      <span className="purchaseCardDescription">{p.description}</span>
                      <span className="purchaseCardAmount">
                        ${p.amount_original.toLocaleString('es-AR', { maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="purchaseCardChips">
                      {p.category && (
                        <span
                          className="purchaseChip"
                          style={{
                            background: categoryObj?.color ? `${categoryObj.color}22` : 'var(--color-primary-light)',
                            color: categoryObj?.color ?? 'var(--color-primary)',
                            border: `1px solid ${categoryObj?.color ? categoryObj.color + '44' : 'rgba(99,102,241,0.2)'}`,
                          }}
                        >
                          {p.category}
                        </span>
                      )}
                      <span className="purchaseChip purchaseChipNeutral">{payerName}</span>
                      {cardName && <span className="purchaseChip purchaseChipNeutral">{cardName}</span>}
                      {p.installments_total > 1 && (
                        <span className="purchaseChip purchaseChipInstallment">
                          {p.installments_total}x
                        </span>
                      )}
                      <span className="purchaseChip purchaseChipNeutral">{p.purchase_date}</span>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Pagination — shared for both views */}
            {pages > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px', flexWrap: 'wrap' }}>
                <button type="button" className="button" disabled={currentPage <= 1} onClick={() => setPage((p) => p - 1)}>
                  Anterior
                </button>
                <span className="muted" style={{ margin: 0 }}>
                  Página {currentPage} de {pages}
                </span>
                <button type="button" className="button" disabled={currentPage >= pages} onClick={() => setPage((p) => p + 1)}>
                  Siguiente
                </button>
              </div>
            )}
          </>
        )}
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

    {/* Mobile edit sheet */}
    {mobileEditPurchase && (
      <div className="purchaseMobileEditOverlay" onClick={() => setMobileEditId(null)}>
        <div className="purchaseMobileEditSheet" onClick={(e) => e.stopPropagation()}>
          <div className="purchaseMobileEditHeader">
            <div>
              <div style={{ fontWeight: 700, fontSize: '1rem' }}>{mobileEditPurchase.description}</div>
              <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                ${mobileEditPurchase.amount_original.toLocaleString('es-AR', { maximumFractionDigits: 2 })} · {mobileEditPurchase.purchase_date}
              </div>
            </div>
            <button
              type="button"
              className="mobileMenuClose"
              style={{ background: 'transparent', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}
              onClick={() => setMobileEditId(null)}
            >
              ✕
            </button>
          </div>

          <div className="purchaseMobileEditBody">
            <div className="formRow">
              <label className="label">Categoría</label>
              <select
                className="input"
                value={mobileEditPurchase.category ?? ''}
                onChange={(e) => {
                  patchMutation.mutate({ id: mobileEditPurchase.id, payload: { category: e.target.value || null } })
                }}
              >
                <option value="">-</option>
                {categoriesData?.map((cat) => (
                  <option key={cat.id} value={cat.name}>{cat.name}</option>
                ))}
              </select>
            </div>

            <div className="formRow">
              <label className="label" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <input
                  type="checkbox"
                  checked={mobileEditPurchase.is_common}
                  style={{ width: '18px', height: '18px' }}
                  onChange={(e) => {
                    patchMutation.mutate({ id: mobileEditPurchase.id, payload: { is_common: e.target.checked } })
                  }}
                />
                Gasto común
              </label>
            </div>

            <div className="formRow">
              <label className="label">Detalle / Notas</label>
              <input
                type="text"
                className="input"
                defaultValue={mobileEditPurchase.notes ?? ''}
                placeholder="Agregar detalle..."
                onBlur={(e) => {
                  const val = e.target.value
                  if (val !== (mobileEditPurchase.notes ?? '')) {
                    patchMutation.mutate({ id: mobileEditPurchase.id, payload: { notes: val || null } })
                  }
                }}
              />
            </div>

            <button
              type="button"
              className="button danger"
              style={{ width: '100%', marginTop: '8px' }}
              disabled={deleteMutation.isPending}
              onClick={() => {
                setMobileEditId(null)
                setPendingDelete({ id: mobileEditPurchase.id, description: mobileEditPurchase.description })
              }}
            >
              🗑 Eliminar compra
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  )
}

import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCurrentYearMonth } from '../utils/dates'
import { getServiceStatus, STATUS_COLORS, STATUS_LABELS } from '../utils/services'
import {
  fetchServicePayments,
  upsertServicePayment,
  updateServicePayment,
  fetchServices,
  createService,
  updateService,
} from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import type { Service, ServicePaymentWithMeta } from '../api/types'

function buildMonthOptions(): { value: string; label: string }[] {
  const months: { value: string; label: string }[] = []
  const now = new Date()
  for (let i = -2; i <= 6; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1)
    const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    const label = d.toLocaleString('es-AR', { month: 'long', year: 'numeric' })
    months.push({ value, label })
  }
  return months
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(amount)
}

function getTodayLocalDate(): Date {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

interface PaymentFormState {
  paid_date: string
  amount: string
  notes: string
  due_date: string
}

function ServiceCard({
  item,
  yearMonth,
  onPaymentSaved,
}: {
  item: ServicePaymentWithMeta
  yearMonth: string
  onPaymentSaved: () => void
}) {
  const [showForm, setShowForm] = useState(false)
  const [formError, setFormError] = useState('')
  const [form, setForm] = useState<PaymentFormState>(() => ({
    paid_date: new Date().toISOString().slice(0, 10),
    amount: '',
    notes: '',
    due_date: item.payment?.due_date ?? item.suggested_due_date ?? '',
  }))

  const today = getTodayLocalDate()
  const dueDate = item.payment?.due_date
    ? new Date(item.payment.due_date + 'T00:00:00')
    : item.suggested_due_date
    ? new Date(item.suggested_due_date + 'T00:00:00')
    : null
  const status = getServiceStatus(item.payment, dueDate, today)
  const statusColor = STATUS_COLORS[status]
  const statusLabel = STATUS_LABELS[status]

  const queryClient = useQueryClient()

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!form.amount || Number(form.amount) <= 0) throw new Error('El monto debe ser mayor a 0')
      const payload = {
        service_id: item.service.id,
        year_month: yearMonth,
        paid_date: form.paid_date || null,
        amount: Number(form.amount),
        notes: form.notes || null,
        due_date: form.due_date || null,
      }
      if (item.payment) {
        return updateServicePayment(item.payment.id, {
          paid_date: payload.paid_date,
          amount: payload.amount,
          notes: payload.notes,
          due_date: payload.due_date,
        })
      }
      return upsertServicePayment(payload)
    },
    onSuccess: () => {
      setShowForm(false)
      setFormError('')
      queryClient.invalidateQueries({ queryKey: ['service-payments'] })
      queryClient.invalidateQueries({ queryKey: ['service-payment-summary'] })
      onPaymentSaved()
    },
    onError: (e: Error) => setFormError(extractErrorMessage(e)),
  })

  const unmarkMutation = useMutation({
    mutationFn: () => {
      if (!item.payment) throw new Error('No payment to unmark')
      return updateServicePayment(item.payment.id, { paid_date: null, amount: null, notes: null })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['service-payments'] })
      queryClient.invalidateQueries({ queryKey: ['service-payment-summary'] })
      onPaymentSaved()
    },
    onError: (e: Error) => setFormError(extractErrorMessage(e)),
  })

  const diffText = useMemo(() => {
    if (!item.payment?.paid_date || !item.payment.amount || !item.service.expected_amount) return null
    const diff = item.payment.amount - item.service.expected_amount
    if (Math.abs(diff) < 1) return null
    return diff > 0
      ? `+${formatCurrency(diff)} sobre lo esperado`
      : `${formatCurrency(Math.abs(diff))} menos de lo esperado`
  }, [item])

  return (
    <div className="panel" style={{ position: 'relative' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <span
          style={{
            width: 12, height: 12, borderRadius: '50%',
            backgroundColor: statusColor, flexShrink: 0, display: 'inline-block',
          }}
          title={statusLabel}
        />
        <span className="panelTitle" style={{ margin: 0, fontSize: '1rem' }}>{item.service.name}</span>
      </div>

      <div className="muted" style={{ fontSize: '0.8rem', marginBottom: '0.4rem' }}>{statusLabel}</div>

      {dueDate && (
        <div style={{ fontSize: '0.875rem', marginBottom: '0.4rem' }}>
          Vence: {dueDate.toLocaleDateString('es-AR')}
        </div>
      )}

      {item.payment?.paid_date ? (
        <div style={{ fontSize: '0.875rem' }}>
          <div>Pagado: {new Date(item.payment.paid_date + 'T00:00:00').toLocaleDateString('es-AR')}</div>
          {item.payment.amount && <div>Monto: {formatCurrency(item.payment.amount)}</div>}
          {diffText && <div className="hint" style={{ fontSize: '0.8rem' }}>{diffText}</div>}
          {item.payment.notes && <div className="hint">{item.payment.notes}</div>}
        </div>
      ) : (
        item.service.expected_amount && (
          <div className="muted" style={{ fontSize: '0.875rem' }}>
            Referencia: {formatCurrency(item.service.expected_amount)}
          </div>
        )
      )}

      {formError && <div className="error" style={{ fontSize: '0.8rem', marginTop: '0.4rem' }}>{formError}</div>}

      {showForm && (
        <div style={{ marginTop: '0.75rem', borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem' }}>
          <div className="formRow">
            <label className="label">Fecha de pago</label>
            <input
              className="input"
              type="date"
              value={form.paid_date}
              onChange={e => setForm(f => ({ ...f, paid_date: e.target.value }))}
            />
          </div>
          <div className="formRow">
            <label className="label">Monto ($)</label>
            <input
              className="input"
              type="number"
              min="0.01"
              step="0.01"
              placeholder="0"
              value={form.amount}
              onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
            />
          </div>
          <div className="formRow">
            <label className="label">Nota (opcional)</label>
            <input
              className="input"
              type="text"
              value={form.notes}
              onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            />
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
            <button className="button" onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? 'Guardando…' : 'Guardar'}
            </button>
            <button className="button" style={{ background: 'var(--color-border)', color: 'var(--color-text)' }} onClick={() => setShowForm(false)}>
              Cancelar
            </button>
          </div>
        </div>
      )}

      {!showForm && (
        <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {item.payment?.paid_date ? (
            <button
              className="button"
              style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem' }}
              onClick={() => { setShowForm(true); setForm(f => ({ ...f, amount: String(item.payment!.amount ?? ''), paid_date: item.payment!.paid_date! })) }}
            >
              Editar pago
            </button>
          ) : (
            <button
              className="button"
              style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem' }}
              onClick={() => setShowForm(true)}
            >
              Registrar pago
            </button>
          )}
          {item.payment?.paid_date && (
            <button
              className="button"
              style={{ fontSize: '0.8rem', padding: '0.3rem 0.7rem', background: 'var(--color-border)', color: 'var(--color-text)' }}
              onClick={() => unmarkMutation.mutate()}
              disabled={unmarkMutation.isPending}
            >
              Desmarcar
            </button>
          )}
        </div>
      )}
    </div>
  )
}

interface ServiceFormState {
  name: string
  expected_amount: string
  typical_due_day: string
  sort_order: string
}

interface EditFormState {
  name: string
  expected_amount: string
  typical_due_day: string
}

function ManageServicesSection({ services }: { services: Service[] }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState<ServiceFormState>({ name: '', expected_amount: '', typical_due_day: '', sort_order: '0' })
  const [error, setError] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editForm, setEditForm] = useState<EditFormState>({ name: '', expected_amount: '', typical_due_day: '' })
  const [editError, setEditError] = useState('')

  const createMutation = useMutation({
    mutationFn: () => {
      if (!form.name.trim()) throw new Error('El nombre es requerido')
      return createService({
        name: form.name.trim(),
        expected_amount: form.expected_amount ? Number(form.expected_amount) : null,
        typical_due_day: form.typical_due_day ? Number(form.typical_due_day) : null,
        sort_order: Number(form.sort_order) || 0,
      })
    },
    onSuccess: () => {
      setForm({ name: '', expected_amount: '', typical_due_day: '', sort_order: '0' })
      setError('')
      queryClient.invalidateQueries({ queryKey: ['services'] })
      queryClient.invalidateQueries({ queryKey: ['service-payments'] })
    },
    onError: (e: Error) => setError(extractErrorMessage(e)),
  })

  const toggleActiveMutation = useMutation({
    mutationFn: (payload: { id: number; is_active: boolean }) =>
      updateService(payload.id, { is_active: payload.is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] })
      queryClient.invalidateQueries({ queryKey: ['service-payments'] })
    },
  })

  const editMutation = useMutation({
    mutationFn: (id: number) => {
      if (!editForm.name.trim()) throw new Error('El nombre es requerido')
      return updateService(id, {
        name: editForm.name.trim(),
        expected_amount: editForm.expected_amount ? Number(editForm.expected_amount) : null,
        typical_due_day: editForm.typical_due_day ? Number(editForm.typical_due_day) : null,
      })
    },
    onSuccess: () => {
      setEditingId(null)
      setEditError('')
      queryClient.invalidateQueries({ queryKey: ['services'] })
      queryClient.invalidateQueries({ queryKey: ['service-payments'] })
    },
    onError: (e: Error) => setEditError(extractErrorMessage(e)),
  })

  const startEdit = (svc: Service) => {
    setEditingId(svc.id)
    setEditForm({
      name: svc.name,
      expected_amount: svc.expected_amount != null ? String(svc.expected_amount) : '',
      typical_due_day: svc.typical_due_day != null ? String(svc.typical_due_day) : '',
    })
    setEditError('')
  }

  return (
    <div className="panel" style={{ marginTop: '2rem' }}>
      <h2 className="panelTitle">Gestionar servicios</h2>

      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '0.5rem', marginBottom: '0.5rem' }}>
          <input className="input" placeholder="Nombre *" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          <input className="input" placeholder="Monto esperado" type="number" min="0" value={form.expected_amount} onChange={e => setForm(f => ({ ...f, expected_amount: e.target.value }))} />
          <input className="input" placeholder="Día venc. (1-31)" type="number" min="1" max="31" value={form.typical_due_day} onChange={e => setForm(f => ({ ...f, typical_due_day: e.target.value }))} />
          <input className="input" placeholder="Orden" type="number" value={form.sort_order} onChange={e => setForm(f => ({ ...f, sort_order: e.target.value }))} />
        </div>
        {error && <div className="error" style={{ marginBottom: '0.5rem' }}>{error}</div>}
        <button className="button" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
          {createMutation.isPending ? 'Agregando…' : 'Agregar servicio'}
        </button>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>Nombre</th>
            <th>Monto ref.</th>
            <th>Día venc.</th>
            <th>Estado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {services.map(svc => (
            editingId === svc.id ? (
              <tr key={svc.id}>
                <td>
                  <input
                    className="input"
                    value={editForm.name}
                    onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))}
                    style={{ width: '100%' }}
                  />
                </td>
                <td>
                  <input
                    className="input"
                    type="number"
                    min="0"
                    value={editForm.expected_amount}
                    onChange={e => setEditForm(f => ({ ...f, expected_amount: e.target.value }))}
                    style={{ width: '100%' }}
                  />
                </td>
                <td>
                  <input
                    className="input"
                    type="number"
                    min="1"
                    max="31"
                    value={editForm.typical_due_day}
                    onChange={e => setEditForm(f => ({ ...f, typical_due_day: e.target.value }))}
                    style={{ width: '100%' }}
                  />
                </td>
                <td>{svc.is_active ? 'Activo' : 'Inactivo'}</td>
                <td>
                  {editError && <div className="error" style={{ fontSize: '0.8rem', marginBottom: '0.25rem' }}>{editError}</div>}
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    <button
                      className="button"
                      style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem' }}
                      onClick={() => editMutation.mutate(svc.id)}
                      disabled={editMutation.isPending}
                    >
                      {editMutation.isPending ? 'Guardando…' : 'Guardar'}
                    </button>
                    <button
                      className="button"
                      style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem', background: 'var(--color-border)', color: 'var(--color-text)' }}
                      onClick={() => { setEditingId(null); setEditError('') }}
                    >
                      Cancelar
                    </button>
                  </div>
                </td>
              </tr>
            ) : (
              <tr key={svc.id} style={{ opacity: svc.is_active ? 1 : 0.5 }}>
                <td>{svc.name}</td>
                <td>{svc.expected_amount ? formatCurrency(svc.expected_amount) : '—'}</td>
                <td>{svc.typical_due_day ?? '—'}</td>
                <td>{svc.is_active ? 'Activo' : 'Inactivo'}</td>
                <td>
                  <div style={{ display: 'flex', gap: '0.4rem' }}>
                    <button
                      className="button"
                      style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem' }}
                      onClick={() => startEdit(svc)}
                    >
                      Editar
                    </button>
                    <button
                      className="button"
                      style={{ fontSize: '0.8rem', padding: '0.2rem 0.5rem' }}
                      onClick={() => toggleActiveMutation.mutate({ id: svc.id, is_active: !svc.is_active })}
                    >
                      {svc.is_active ? 'Desactivar' : 'Activar'}
                    </button>
                  </div>
                </td>
              </tr>
            )
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ServiciosPage() {
  const [monthFilter, setMonthFilter] = useState<string>(() => getCurrentYearMonth())
  const monthOptions = useMemo(() => buildMonthOptions(), [])
  const queryClient = useQueryClient()

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['service-payments', monthFilter],
    queryFn: () => fetchServicePayments(monthFilter),
  })

  const { data: allServices = [] } = useQuery({
    queryKey: ['services'],
    queryFn: fetchServices,
  })

  const handlePaymentSaved = () => {
    queryClient.invalidateQueries({ queryKey: ['service-payments', monthFilter] })
  }

  return (
    <div className="page">
      <h1 className="pageTitle">Servicios</h1>

      <div className="formRow" style={{ marginBottom: '1.5rem' }}>
        <label className="label">Mes</label>
        <select className="input" style={{ width: 'auto' }} value={monthFilter} onChange={e => setMonthFilter(e.target.value)}>
          {monthOptions.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {isLoading && <div className="muted">Cargando…</div>}

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
        gap: '1rem',
      }}>
        {items.map(item => (
          <ServiceCard
            key={item.service.id}
            item={item}
            yearMonth={monthFilter}
            onPaymentSaved={handlePaymentSaved}
          />
        ))}
      </div>

      {!isLoading && items.length === 0 && (
        <div className="muted">No hay servicios activos. Agregá uno abajo.</div>
      )}

      <ManageServicesSection services={allServices} />
    </div>
  )
}

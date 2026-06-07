import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  createCard,
  createDebtor,
  createPerson,
  fetchCards,
  fetchCardStatements,
  upsertCardStatement,
  deleteCardStatement,
  fetchDebtors,
  fetchFxRates,
  fetchPeople,
  upsertFxRate,
  createBeneficiary,
  deleteBeneficiary,
  fetchBeneficiaries,
  updateBeneficiary,
} from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import type { CardStatementCreate, CurrencyCode, Beneficiary } from '../api/types'
import { positiveNumber } from '../utils/formValidation'

/* ------------------------------------------------------------------ */
/*  People                                                             */
/* ------------------------------------------------------------------ */

function PeopleSection() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [nameError, setNameError] = useState('')

  const peopleQuery = useQuery({
    queryKey: ['people'],
    queryFn: fetchPeople,
  })

  const createMutation = useMutation({
    mutationFn: () => createPerson({ name: name.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['people'] })
      setName('')
      setNameError('')
    },
  })

  const people = peopleQuery.data ?? []

  return (
    <div className="panel">
      <div className="panelTitle">Personas</div>
      {people.length === 0 ? (
        <div className="muted">Sin personas cargadas</div>
      ) : (
        <>
          <table className="table adminEntityTable">
            <thead>
              <tr>
                <th>ID</th>
                <th>Nombre</th>
              </tr>
            </thead>
            <tbody>
              {people.map((p) => (
                <tr key={p.id}>
                  <td>{p.id}</td>
                  <td>{p.name}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {/* Mobile card list */}
          <div className="adminCardList">
            {people.map((p) => (
              <div key={p.id} className="adminCard">
                <span className="adminCardName">{p.name}</span>
                <span className="adminCardMeta">ID: {p.id}</span>
              </div>
            ))}
          </div>
        </>
      )}
      <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid var(--color-border)' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-end' }}>
          <div className="formRow" style={{ flex: 1, marginBottom: 0 }}>
            <label className="label">Nuevo Nombre</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => setNameError(name.trim() ? '' : 'Requerido')}
              placeholder="Ej: Pablo"
            />
            {nameError && <span className="fieldError">{nameError}</span>}
          </div>
          <button
            className="button"
            style={{ height: '42px' }}
            disabled={createMutation.isPending}
            onClick={() => {
              if (!name.trim()) {
                setNameError('Requerido')
                return
              }
              setNameError('')
              createMutation.mutate()
            }}
            type="button"
          >
            {createMutation.isPending ? 'Creando...' : 'Agregar'}
          </button>
        </div>
        {createMutation.isError ? (
          <div className="error" style={{ marginTop: '12px' }}>{extractErrorMessage(createMutation.error)}</div>
        ) : null}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Cards                                                              */
/* ------------------------------------------------------------------ */

function CardsSection() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ name: '', provider: 'visa', ownerPersonId: '', last4: '' })
  const [errors, setErrors] = useState<Record<string, string>>({})

  const peopleQuery = useQuery({ queryKey: ['people'], queryFn: fetchPeople })
  const cardsQuery = useQuery({ queryKey: ['cards'], queryFn: fetchCards })

  const createMutation = useMutation({
    mutationFn: () =>
      createCard({
        name: form.name.trim(),
        provider: form.provider,
        owner_person_id: Number(form.ownerPersonId),
        last4: form.last4 || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cards'] })
      setForm({ name: '', provider: 'visa', ownerPersonId: '', last4: '' })
      setErrors({})
    },
  })

  const cards = cardsQuery.data ?? []
  const people = peopleQuery.data ?? []

  return (
    <div className="panel">
      <div className="panelTitle">Tarjetas</div>
      {cards.length === 0 ? (
        <div className="muted">Sin tarjetas cargadas</div>
      ) : (
        <>
          <table className="table adminEntityTable">
            <thead>
              <tr>
                <th>ID</th>
                <th>Nombre</th>
                <th>Proveedor</th>
                <th>Persona</th>
                <th>Últimos 4</th>
              </tr>
            </thead>
            <tbody>
              {cards.map((c) => (
                <tr key={c.id}>
                  <td>{c.id}</td>
                  <td>{c.name}</td>
                  <td>{c.provider}</td>
                  <td>{people.find((p) => p.id === c.owner_person_id)?.name ?? c.owner_person_id}</td>
                  <td>{c.last4 ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="adminCardList">
            {cards.map((c) => (
              <div key={c.id} className="adminCard">
                <span className="adminCardName">{c.name}</span>
                <span className="adminCardMeta">
                  {c.provider} · {people.find((p) => p.id === c.owner_person_id)?.name ?? '-'}
                  {c.last4 ? ` · ****${c.last4}` : ''}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
      <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid var(--color-border)' }}>
        <div className="admin-form-grid">
          <div className="formRow">
            <label className="label">Nombre</label>
            <input
              className="input"
              value={form.name}
              onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))}
              onBlur={() => setErrors(e => ({ ...e, name: form.name.trim() ? '' : 'Requerido' }))}
              placeholder="Ej: Visa Santander"
            />
            {errors.name && <span className="fieldError">{errors.name}</span>}
          </div>
          <div className="formRow">
            <label className="label">Proveedor</label>
            <select
              className="input"
              value={form.provider}
              onChange={(e) => setForm((s) => ({ ...s, provider: e.target.value }))}
            >
              <option value="visa">Visa</option>
              <option value="mastercard">Mastercard</option>
              <option value="amex">Amex</option>
            </select>
          </div>
        </div>
        <div className="admin-form-grid">
          <div className="formRow">
            <label className="label">Titular</label>
            <select
              className="input"
              value={form.ownerPersonId}
              onChange={(e) => setForm((s) => ({ ...s, ownerPersonId: e.target.value }))}
              onBlur={() => setErrors(e => ({ ...e, ownerPersonId: form.ownerPersonId ? '' : 'Seleccioná una persona' }))}
            >
              <option value="">Seleccioná...</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            {errors.ownerPersonId && <span className="fieldError">{errors.ownerPersonId}</span>}
          </div>
          <div className="formRow">
            <label className="label">Últimos 4 (opcional)</label>
            <input
              className="input"
              value={form.last4}
              onChange={(e) => setForm((s) => ({ ...s, last4: e.target.value.replace(/\D/g, '').slice(0, 4) }))}
              placeholder="1234"
              maxLength={4}
            />
          </div>
        </div>
        <button
          className="button"
          style={{ width: '100%', marginTop: '8px' }}
          disabled={createMutation.isPending}
          onClick={() => {
            const e = {
              name: form.name.trim() ? '' : 'Requerido',
              ownerPersonId: form.ownerPersonId ? '' : 'Seleccioná una persona',
            }
            setErrors(e)
            if (Object.values(e).some(Boolean)) return
            createMutation.mutate()
          }}
          type="button"
        >
          {createMutation.isPending ? 'Creando...' : 'Agregar Nueva Tarjeta'}
        </button>
        {createMutation.isError ? (
          <div className="error" style={{ marginTop: '12px' }}>{extractErrorMessage(createMutation.error)}</div>
        ) : null}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  FX Rates                                                           */
/* ------------------------------------------------------------------ */

function FxRatesSection() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ yearMonth: '', currency: 'USD' as CurrencyCode, rate: '' })
  const [errors, setErrors] = useState<Record<string, string>>({})

  const fxQuery = useQuery({ queryKey: ['fx'], queryFn: fetchFxRates })

  const upsertMutation = useMutation({
    mutationFn: () =>
      upsertFxRate({
        year_month: form.yearMonth,
        currency: form.currency,
        rate_to_ars: Number(form.rate),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['fx'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      setForm((s) => ({ ...s, rate: '' }))
      setErrors({})
    },
  })

  const rates = fxQuery.data ?? []

  return (
    <div className="panel">
      <div className="panelTitle">Tipos de cambio</div>
      {rates.length === 0 ? (
        <div className="muted">Sin tipos de cambio cargados</div>
      ) : (
        <>
          <table className="table adminEntityTable">
            <thead>
              <tr>
                <th>Mes</th>
                <th>Moneda</th>
                <th>Cotización (ARS)</th>
              </tr>
            </thead>
            <tbody>
              {rates.map((r) => (
                <tr key={r.id}>
                  <td>{r.year_month}</td>
                  <td>{r.currency}</td>
                  <td>{r.rate_to_ars.toLocaleString('es-AR', { maximumFractionDigits: 2 })}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="adminCardList">
            {rates.map((r) => (
              <div key={r.id} className="adminCard">
                <span className="adminCardName">{r.year_month}</span>
                <span className="adminCardMeta">1 {r.currency} = {r.rate_to_ars.toLocaleString('es-AR', { maximumFractionDigits: 2 })} ARS</span>
              </div>
            ))}
          </div>
        </>
      )}
      <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid var(--color-border)' }}>
        <div className="admin-form-grid">
          <div className="formRow">
            <label className="label">Mes (YYYY-MM)</label>
            <input
              className="input"
              type="month"
              value={form.yearMonth}
              onChange={(e) => setForm((s) => ({ ...s, yearMonth: e.target.value }))}
              onBlur={() => setErrors(e => ({ ...e, yearMonth: form.yearMonth ? '' : 'Requerido' }))}
            />
            {errors.yearMonth && <span className="fieldError">{errors.yearMonth}</span>}
          </div>
          <div className="formRow">
            <label className="label">Moneda</label>
            <select
              className="input"
              value={form.currency}
              onChange={(e) => setForm((s) => ({ ...s, currency: e.target.value as CurrencyCode }))}
            >
              <option value="USD">USD</option>
              <option value="ARS">ARS</option>
            </select>
          </div>
        </div>
        <div className="formRow">
          <label className="label">Cotización en ARS</label>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              <input
                className="input"
                type="number"
                step="0.01"
                min="0.01"
                value={form.rate}
                onChange={(e) => setForm((s) => ({ ...s, rate: e.target.value }))}
                onBlur={() => setErrors(e => ({ ...e, rate: positiveNumber(form.rate) }))}
                placeholder="Ej: 1150.50"
              />
              {errors.rate && <span className="fieldError">{errors.rate}</span>}
            </div>
            <button
              className="button"
              style={{ height: '42px', minWidth: '100px' }}
              disabled={upsertMutation.isPending}
              onClick={() => {
                const e = {
                  yearMonth: form.yearMonth ? '' : 'Requerido',
                  rate: positiveNumber(form.rate),
                }
                setErrors(e)
                if (Object.values(e).some(Boolean)) return
                upsertMutation.mutate()
              }}
              type="button"
            >
              {upsertMutation.isPending ? '...' : 'Guardar'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Debtors                                                            */
/* ------------------------------------------------------------------ */

function DebtorsSection() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [nameError, setNameError] = useState('')

  const debtorsQuery = useQuery({
    queryKey: ['debtors'],
    queryFn: fetchDebtors,
  })

  const createMutation = useMutation({
    mutationFn: () => createDebtor({ name: name.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['debtors'] })
      setName('')
      setNameError('')
    },
  })

  const debtors = debtorsQuery.data ?? []

  return (
    <div className="panel">
      <div className="panelTitle">Deudores</div>
      {debtors.length === 0 ? (
        <div className="muted">Sin deudores cargados</div>
      ) : (
        <>
          <table className="table adminEntityTable">
            <thead>
              <tr>
                <th>ID</th>
                <th>Nombre</th>
              </tr>
            </thead>
            <tbody>
              {debtors.map((d) => (
                <tr key={d.id}>
                  <td>{d.id}</td>
                  <td>{d.name}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="adminCardList">
            {debtors.map((d) => (
              <div key={d.id} className="adminCard">
                <span className="adminCardName">{d.name}</span>
                <span className="adminCardMeta">ID: {d.id}</span>
              </div>
            ))}
          </div>
        </>
      )}
      <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid var(--color-border)' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-end' }}>
          <div className="formRow" style={{ flex: 1, marginBottom: 0 }}>
            <label className="label">Nombre del Deudor</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => setNameError(name.trim() ? '' : 'Requerido')}
              placeholder="Ej: Marcelo"
            />
            {nameError && <span className="fieldError">{nameError}</span>}
          </div>
          <button
            className="button"
            style={{ height: '42px' }}
            disabled={createMutation.isPending}
            onClick={() => {
              if (!name.trim()) {
                setNameError('Requerido')
                return
              }
              setNameError('')
              createMutation.mutate()
            }}
            type="button"
          >
            {createMutation.isPending ? '...' : 'Agregar'}
          </button>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Beneficiaries                                                      */
/* ------------------------------------------------------------------ */

function BeneficiariesSection() {
  const queryClient = useQueryClient()
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [editCbu, setEditCbu] = useState('')
  const [editCuit, setEditCuit] = useState('')
  const [editAlias, setEditAlias] = useState('')

  const [newName, setNewName] = useState('')
  const [newCbu, setNewCbu] = useState('')
  const [newCuit, setNewCuit] = useState('')
  const [newAlias, setNewAlias] = useState('')
  const [newNameError, setNewNameError] = useState('')

  const bQuery = useQuery({
    queryKey: ['beneficiaries'],
    queryFn: fetchBeneficiaries,
  })

  const createMutation = useMutation({
    mutationFn: () => createBeneficiary({
      name: newName.trim(),
      cbu: newCbu.trim() || undefined,
      cuit: newCuit.trim() || undefined,
      alias: newAlias.trim() || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['beneficiaries'] })
      setNewName('')
      setNewCbu('')
      setNewCuit('')
      setNewAlias('')
      setNewNameError('')
    },
  })

  const updateMutation = useMutation({
    mutationFn: (id: number) => updateBeneficiary(id, {
      name: editName.trim(),
      cbu: editCbu.trim() || undefined,
      cuit: editCuit.trim() || undefined,
      alias: editAlias.trim() || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['beneficiaries'] })
      setEditingId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteBeneficiary(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['beneficiaries'] }),
  })

  const beneficiaries = bQuery.data ?? []

  const startEdit = (b: Beneficiary) => {
    setEditingId(b.id)
    setEditName(b.name)
    setEditCbu(b.cbu ?? '')
    setEditCuit(b.cuit ?? '')
    setEditAlias(b.alias ?? '')
  }

  return (
    <div className="panel">
      <div className="panelTitle">Destinatarios Frecuentes</div>
      {beneficiaries.length === 0 ? (
        <div className="muted">Sin destinatarios cargados</div>
      ) : (
        <>
          <table className="table adminEntityTable">
            <thead>
              <tr>
                <th>ID</th>
                <th>Nombre</th>
                <th>CBU</th>
                <th>CUIT</th>
                <th>Alias</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {beneficiaries.map((b) => (
                <tr key={b.id}>
                  {editingId === b.id ? (
                    <>
                      <td>{b.id}</td>
                      <td><input className="input" value={editName} onChange={e => setEditName(e.target.value)} style={{ width: '140px' }} /></td>
                      <td><input className="input" value={editCbu} onChange={e => setEditCbu(e.target.value)} placeholder="CBU" style={{ width: '120px' }} /></td>
                      <td><input className="input" value={editCuit} onChange={e => setEditCuit(e.target.value)} placeholder="CUIT" style={{ width: '120px' }} /></td>
                      <td><input className="input" value={editAlias} onChange={e => setEditAlias(e.target.value)} placeholder="Alias" style={{ width: '120px' }} /></td>
                      <td style={{ display: 'flex', gap: '6px' }}>
                        <button className="button" style={{ padding: '4px 10px', fontSize: '0.8rem' }} onClick={() => updateMutation.mutate(b.id)} disabled={!editName.trim() || updateMutation.isPending} type="button">Guardar</button>
                        <button className="button ghost" style={{ padding: '4px 10px', fontSize: '0.8rem' }} onClick={() => setEditingId(null)} type="button">Cancelar</button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td>{b.id}</td>
                      <td>{b.name}</td>
                      <td className="muted">{b.cbu ?? '—'}</td>
                      <td className="muted">{b.cuit ?? '—'}</td>
                      <td className="muted">{b.alias ?? '—'}</td>
                      <td style={{ display: 'flex', gap: '6px' }}>
                        <button className="button ghost" style={{ padding: '4px 10px', fontSize: '0.8rem' }} onClick={() => startEdit(b)} type="button">Editar</button>
                        <button className="button ghost" style={{ padding: '4px 10px', fontSize: '0.8rem', color: 'var(--color-danger, #dc2626)' }} onClick={() => deleteMutation.mutate(b.id)} disabled={deleteMutation.isPending} type="button">Eliminar</button>
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="adminCardList">
            {beneficiaries.map((b) => (
              <div key={b.id} className="adminCard">
                <span className="adminCardName">{b.name}</span>
                <span className="adminCardMeta">
                  {b.alias ? b.alias : b.cbu ? `CBU: ${b.cbu.slice(-4)}` : `ID: ${b.id}`}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
      <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid var(--color-border)' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="formRow" style={{ flex: 2, marginBottom: 0 }}>
            <label className="label">Nombre *</label>
            <input
              className="input"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onBlur={() => setNewNameError(newName.trim() ? '' : 'Requerido')}
              placeholder="Ej: Verdulería Lopez"
            />
            {newNameError && <span className="fieldError">{newNameError}</span>}
          </div>
          <div className="formRow" style={{ flex: 2, marginBottom: 0 }}>
            <label className="label">CBU</label>
            <input className="input" value={newCbu} onChange={e => setNewCbu(e.target.value)} placeholder="22 dígitos" />
          </div>
          <div className="formRow" style={{ flex: 1, marginBottom: 0 }}>
            <label className="label">CUIT</label>
            <input className="input" value={newCuit} onChange={e => setNewCuit(e.target.value)} placeholder="XX-XXXXXXXX-X" />
          </div>
          <div className="formRow" style={{ flex: 2, marginBottom: 0 }}>
            <label className="label">Alias</label>
            <input className="input" value={newAlias} onChange={e => setNewAlias(e.target.value)} placeholder="ej: verduleria.lopez" />
          </div>
          <button
            className="button"
            style={{ height: '42px' }}
            disabled={createMutation.isPending}
            onClick={() => {
              if (!newName.trim()) {
                setNewNameError('Requerido')
                return
              }
              createMutation.mutate()
            }}
            type="button"
          >
            {createMutation.isPending ? 'Guardando...' : 'Agregar'}
          </button>
        </div>
        {createMutation.isError && <div className="error" style={{ marginTop: '8px' }}>{extractErrorMessage(createMutation.error)}</div>}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Card Statements                                                    */
/* ------------------------------------------------------------------ */

function CardStatementsSection() {
  const queryClient = useQueryClient()
  const [selectedCardId, setSelectedCardId] = useState<string>('')
  const [form, setForm] = useState({ year_month: '', closing_date: '', due_date: '' })
  const [errors, setErrors] = useState<Record<string, string>>({})

  const cardsQuery = useQuery({ queryKey: ['cards'], queryFn: fetchCards })
  const cards = cardsQuery.data ?? []

  const statementsQuery = useQuery({
    queryKey: ['card-statements', selectedCardId],
    queryFn: () => fetchCardStatements(Number(selectedCardId)),
    enabled: !!selectedCardId,
  })
  const statements = statementsQuery.data ?? []

  const upsertMutation = useMutation({
    mutationFn: (payload: CardStatementCreate) => upsertCardStatement(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['card-statements', selectedCardId] })
      setForm({ year_month: '', closing_date: '', due_date: '' })
      setErrors({})
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteCardStatement(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['card-statements', selectedCardId] }),
  })

  const handleSubmit = () => {
    const e = {
      cardId: selectedCardId ? '' : 'Seleccioná una tarjeta',
      year_month: form.year_month ? '' : 'Requerido',
      closing_date: form.closing_date ? '' : 'Requerido',
    }
    setErrors(e)
    if (Object.values(e).some(Boolean)) return
    upsertMutation.mutate({
      card_id: Number(selectedCardId),
      year_month: form.year_month,
      closing_date: form.closing_date,
      due_date: form.due_date || null,
    })
  }

  return (
    <div className="panel">
      <div className="panelTitle">Fechas de Resumen por Tarjeta</div>

      <div className="formRow">
        <label className="label">Tarjeta</label>
        <select
          className="input"
          value={selectedCardId}
          onChange={(e) => {
            setSelectedCardId(e.target.value)
            setErrors(e2 => ({ ...e2, cardId: '' }))
          }}
          onBlur={() => setErrors(e => ({ ...e, cardId: selectedCardId ? '' : 'Seleccioná una tarjeta' }))}
        >
          <option value="">Seleccionar tarjeta...</option>
          {cards.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        {errors.cardId && <span className="fieldError">{errors.cardId}</span>}
      </div>

      {selectedCardId && (
        <>
          {statements.length === 0 ? (
            <div className="muted" style={{ marginBottom: '16px' }}>Sin fechas cargadas para esta tarjeta</div>
          ) : (
            <table className="table" style={{ marginBottom: '16px' }}>
              <thead>
                <tr>
                  <th>Mes</th>
                  <th>Cierre</th>
                  <th>Vencimiento</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {statements.map((s) => (
                  <tr key={s.id}>
                    <td>{s.year_month}</td>
                    <td>{s.closing_date}</td>
                    <td>{s.due_date ?? '—'}</td>
                    <td>
                      <button
                        className="button"
                        style={{ background: '#dc2626', padding: '4px 10px', fontSize: '12px' }}
                        onClick={() => deleteMutation.mutate(s.id)}
                        type="button"
                      >
                        Eliminar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div className="formRow" style={{ flex: 1, minWidth: '120px', marginBottom: 0 }}>
              <label className="label">Mes (YYYY-MM)</label>
              <input
                type="month"
                className="input"
                value={form.year_month}
                onChange={(e) => setForm({ ...form, year_month: e.target.value })}
                onBlur={() => setErrors(e => ({ ...e, year_month: form.year_month ? '' : 'Requerido' }))}
              />
              {errors.year_month && <span className="fieldError">{errors.year_month}</span>}
            </div>
            <div className="formRow" style={{ flex: 1, minWidth: '140px', marginBottom: 0 }}>
              <label className="label">Fecha de Cierre</label>
              <input
                type="date"
                className="input"
                value={form.closing_date}
                onChange={(e) => setForm({ ...form, closing_date: e.target.value })}
                onBlur={() => setErrors(e => ({ ...e, closing_date: form.closing_date ? '' : 'Requerido' }))}
              />
              {errors.closing_date && <span className="fieldError">{errors.closing_date}</span>}
            </div>
            <div className="formRow" style={{ flex: 1, minWidth: '140px', marginBottom: 0 }}>
              <label className="label">Vencimiento (opcional)</label>
              <input
                type="date"
                className="input"
                value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })}
              />
            </div>
            <button
              className="button"
              style={{ height: '42px' }}
              disabled={upsertMutation.isPending}
              onClick={handleSubmit}
              type="button"
            >
              Guardar
            </button>
          </div>
          {upsertMutation.isError && (
            <div className="error" style={{ marginTop: '12px' }}>
              {extractErrorMessage(upsertMutation.error)}
            </div>
          )}
        </>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Admin Page                                                         */
/* ------------------------------------------------------------------ */

export function AdminPage() {
  return (
    <section className="page">
      <h2 className="pageTitle">Administración del Sistema</h2>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))', gap: '32px' }}>
        <PeopleSection />
        <CardsSection />
        <CardStatementsSection />
        <DebtorsSection />
        <BeneficiariesSection />
        <FxRatesSection />
      </div>
    </section>
  )
}

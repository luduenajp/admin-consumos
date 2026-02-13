import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  createCard,
  createDebtor,
  createPerson,
  fetchCards,
  fetchDebtors,
  fetchFxRates,
  fetchPeople,
  upsertFxRate,
} from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import type { CurrencyCode } from '../api/types'

/* ------------------------------------------------------------------ */
/*  People                                                             */
/* ------------------------------------------------------------------ */

function PeopleSection() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')

  const peopleQuery = useQuery({
    queryKey: ['people'],
    queryFn: fetchPeople,
  })

  const createMutation = useMutation({
    mutationFn: () => createPerson({ name: name.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['people'] })
      setName('')
    },
  })

  const people = peopleQuery.data ?? []

  return (
    <div className="panel">
      <div className="panelTitle">Personas</div>
      {people.length === 0 ? (
        <div className="muted">Sin personas cargadas</div>
      ) : (
        <table className="table">
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
      )}
      <div style={{ marginTop: 12 }}>
        <div className="formRow">
          <label className="label">Nombre</label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Nombre de la persona"
          />
        </div>
        <div className="formRow">
          <button
            className="button"
            disabled={createMutation.isPending || !name.trim()}
            onClick={() => createMutation.mutate()}
            type="button"
          >
            {createMutation.isPending ? 'Creando...' : 'Agregar persona'}
          </button>
        </div>
        {createMutation.isError ? (
          <div className="error">Error: {extractErrorMessage(createMutation.error)}</div>
        ) : null}
        {createMutation.isSuccess ? <div className="success">Persona creada</div> : null}
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
        <table className="table">
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
      )}
      <div style={{ marginTop: 12 }}>
        <div className="formRow">
          <label className="label">Nombre de la tarjeta</label>
          <input
            className="input"
            value={form.name}
            onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))}
            placeholder="Ej: Visa Santander"
          />
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
        <div className="formRow">
          <label className="label">Persona dueña</label>
          <select
            className="input"
            value={form.ownerPersonId}
            onChange={(e) => setForm((s) => ({ ...s, ownerPersonId: e.target.value }))}
          >
            <option value="">Seleccioná...</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div className="formRow">
          <label className="label">Últimos 4 dígitos (opcional)</label>
          <input
            className="input"
            value={form.last4}
            onChange={(e) =>
              setForm((s) => ({ ...s, last4: e.target.value.replace(/\D/g, '').slice(0, 4) }))
            }
            placeholder="1234"
            maxLength={4}
            pattern="[0-9]*"
            inputMode="numeric"
          />
        </div>
        <div className="formRow">
          <button
            className="button"
            disabled={createMutation.isPending || !form.name.trim() || !form.ownerPersonId}
            onClick={() => createMutation.mutate()}
            type="button"
          >
            {createMutation.isPending ? 'Creando...' : 'Agregar tarjeta'}
          </button>
        </div>
        {createMutation.isError ? (
          <div className="error">Error: {extractErrorMessage(createMutation.error)}</div>
        ) : null}
        {createMutation.isSuccess ? <div className="success">Tarjeta creada</div> : null}
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
    },
  })

  const rates = fxQuery.data ?? []

  return (
    <div className="panel">
      <div className="panelTitle">Tipos de cambio</div>
      {rates.length === 0 ? (
        <div className="muted">Sin tipos de cambio cargados</div>
      ) : (
        <table className="table">
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
      )}
      <div style={{ marginTop: 12 }}>
        <div className="formRow">
          <label className="label">Mes (YYYY-MM)</label>
          <input
            className="input"
            type="month"
            value={form.yearMonth}
            onChange={(e) => setForm((s) => ({ ...s, yearMonth: e.target.value }))}
          />
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
        <div className="formRow">
          <label className="label">Cotización en ARS</label>
          <input
            className="input"
            type="number"
            step="0.01"
            min="0.01"
            value={form.rate}
            onChange={(e) => setForm((s) => ({ ...s, rate: e.target.value }))}
            placeholder="1150.50"
          />
          {form.rate && (Number(form.rate) <= 0 || Number.isNaN(Number(form.rate))) ? (
            <div className="hint" style={{ color: 'var(--color-error-text)' }}>
              La cotización debe ser mayor a 0
            </div>
          ) : null}
        </div>
        <div className="formRow">
          <button
            className="button"
            disabled={
              upsertMutation.isPending ||
              !form.yearMonth ||
              !form.rate ||
              Number(form.rate) <= 0 ||
              Number.isNaN(Number(form.rate))
            }
            onClick={() => upsertMutation.mutate()}
            type="button"
          >
            {upsertMutation.isPending ? 'Guardando...' : 'Guardar tipo de cambio'}
          </button>
        </div>
        {upsertMutation.isError ? (
          <div className="error">Error: {extractErrorMessage(upsertMutation.error)}</div>
        ) : null}
        {upsertMutation.isSuccess ? <div className="success">Tipo de cambio guardado</div> : null}
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

  const debtorsQuery = useQuery({
    queryKey: ['debtors'],
    queryFn: fetchDebtors,
  })

  const createMutation = useMutation({
    mutationFn: () => createDebtor({ name: name.trim() }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['debtors'] })
      setName('')
    },
  })

  const debtors = debtorsQuery.data ?? []

  return (
    <div className="panel">
      <div className="panelTitle">Deudores</div>
      {debtors.length === 0 ? (
        <div className="muted">Sin deudores cargados</div>
      ) : (
        <table className="table">
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
      )}
      <div style={{ marginTop: 12 }}>
        <div className="formRow">
          <label className="label">Nombre</label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Nombre del deudor"
          />
        </div>
        <div className="formRow">
          <button
            className="button"
            disabled={createMutation.isPending || !name.trim()}
            onClick={() => createMutation.mutate()}
            type="button"
          >
            {createMutation.isPending ? 'Creando...' : 'Agregar deudor'}
          </button>
        </div>
        {createMutation.isError ? (
          <div className="error">Error: {extractErrorMessage(createMutation.error)}</div>
        ) : null}
        {createMutation.isSuccess ? <div className="success">Deudor creado</div> : null}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Admin Page                                                         */
/* ------------------------------------------------------------------ */

export function AdminPage() {
  return (
    <section className="page">
      <h2 className="pageTitle">Administración</h2>
      <PeopleSection />
      <CardsSection />
      <DebtorsSection />
      <FxRatesSection />
    </section>
  )
}

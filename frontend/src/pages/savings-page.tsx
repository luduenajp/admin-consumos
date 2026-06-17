import { useQueries, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  CartesianGrid,
  Legend,
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  createSaving,
  createSavingSnapshot,
  createSavingsExchangeRate,
  deleteSaving,
  fetchPeople,
  fetchSavingSnapshots,
  fetchSavings,
  fetchSavingsExchangeRates,
  fetchSavingsTotalHistory,
} from '../api/endpoints'
import { extractErrorMessage } from '../api/http'
import type { CurrencyCode, Saving, SavingSnapshot, SavingsExchangeRate, SavingsTotalHistoryPoint } from '../api/types'

const LINE_COLORS = [
  'var(--color-primary)',
  '#4f86c6',
  '#5ab068',
  '#d4a843',
  '#a855f7',
  '#ec4899',
]

function formatAmount(amount: number, currency: CurrencyCode): string {
  const locale = 'es-AR'
  if (currency === 'USD') {
    return `U$S ${amount.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }
  return `$${amount.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

/* ------------------------------------------------------------------ */
/*  Inline snapshot form                                               */
/* ------------------------------------------------------------------ */

function SnapshotForm({ saving, onDone }: { saving: Saving; onDone: () => void }) {
  const queryClient = useQueryClient()
  const today = new Date().toISOString().split('T')[0]
  const [date, setDate] = useState(today)
  const [amount, setAmount] = useState('')
  const [error, setError] = useState('')

  const snapshotMutation = useMutation({
    mutationFn: () =>
      createSavingSnapshot(saving.id, {
        date,
        amount: parseFloat(amount),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savings'] })
      queryClient.invalidateQueries({ queryKey: ['saving-snapshots', saving.id] })
      onDone()
    },
    onError: (err) => setError(extractErrorMessage(err)),
  })

  return (
    <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end', flexWrap: 'wrap', marginTop: '8px' }}>
      <div className="formRow" style={{ marginBottom: 0 }}>
        <label className="label">Fecha</label>
        <input
          className="input"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          style={{ width: '140px' }}
        />
      </div>
      <div className="formRow" style={{ marginBottom: 0 }}>
        <label className="label">Monto ({saving.currency})</label>
        <input
          className="input"
          type="number"
          step="0.01"
          min="0"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="0.00"
          style={{ width: '140px' }}
        />
      </div>
      <button
        className="button"
        disabled={snapshotMutation.isPending || !amount || parseFloat(amount) <= 0}
        onClick={() => snapshotMutation.mutate()}
        type="button"
      >
        {snapshotMutation.isPending ? 'Guardando…' : 'Guardar'}
      </button>
      <button
        className="button"
        style={{ background: 'var(--color-surface)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}
        onClick={onDone}
        type="button"
      >
        Cancelar
      </button>
      {error && <span className="error">{error}</span>}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  History chart                                                      */
/* ------------------------------------------------------------------ */

function HistoryChart({
  savings,
  selectedIds,
}: {
  savings: Saving[]
  selectedIds: Set<number>
}) {
  const selectedSavings = savings.filter((s) => selectedIds.has(s.id))

  const snapshotResults = useQueries({
    queries: selectedSavings.map((s) => ({
      queryKey: ['saving-snapshots', s.id],
      queryFn: () => fetchSavingSnapshots(s.id),
    })),
  })

  // Build merged dataset: all unique dates across all selected savings
  const allDates = new Set<string>()
  const dataByLabel: Record<number, Record<string, number>> = {}

  snapshotResults.forEach((result, idx) => {
    const saving = selectedSavings[idx]
    const snapshots: SavingSnapshot[] = result.data ?? []
    dataByLabel[saving.id] = {}
    snapshots.forEach((snap) => {
      allDates.add(snap.date)
      dataByLabel[saving.id][snap.date] = snap.amount
    })
  })

  const sortedDates = Array.from(allDates).sort()
  const chartData = sortedDates.map((date) => {
    const point: Record<string, string | number> = { date }
    selectedSavings.forEach((s) => {
      if (dataByLabel[s.id]?.[date] !== undefined) {
        point[`saving_${s.id}`] = dataByLabel[s.id][date]
      }
    })
    return point
  })

  const isLoading = snapshotResults.some((r) => r.isLoading)

  if (selectedSavings.length === 0) {
    return <div className="muted">Seleccioná una o más inversiones para ver el historial</div>
  }

  if (isLoading) {
    return <div className="muted">Cargando datos…</div>
  }

  if (chartData.length === 0) {
    return <div className="muted">Sin snapshots registrados para las inversiones seleccionadas</div>
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
        <XAxis dataKey="date" stroke="var(--color-text-secondary)" style={{ fontSize: '0.85rem' }} />
        <YAxis
          stroke="var(--color-text-secondary)"
          style={{ fontSize: '0.85rem' }}
          tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: '6px',
            fontSize: '0.9rem',
          }}
          formatter={(value, name) => {
            const nameStr = String(name ?? '')
            const savingId = parseInt(nameStr.replace('saving_', ''), 10)
            const saving = savings.find((s) => s.id === savingId)
            const label = saving ? `${saving.investment_type} — ${saving.institution}` : nameStr
            const numValue = Number(value)
            return [saving ? formatAmount(numValue, saving.currency) : value, label]
          }}
        />
        <Legend
          formatter={(name: string) => {
            const savingId = parseInt(name.replace('saving_', ''), 10)
            const saving = savings.find((s) => s.id === savingId)
            return saving ? `${saving.investment_type} — ${saving.institution} (${saving.currency})` : name
          }}
        />
        {selectedSavings.map((s, idx) => (
          <Line
            key={s.id}
            type="monotone"
            dataKey={`saving_${s.id}`}
            stroke={LINE_COLORS[idx % LINE_COLORS.length]}
            strokeWidth={2}
            dot={{ r: 4 }}
            connectNulls={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

/* ------------------------------------------------------------------ */
/*  Totals panel                                                       */
/* ------------------------------------------------------------------ */

function SavingsTotalsPanel({ savings }: { savings: Saving[] }) {
  const queryClient = useQueryClient()
  const today = new Date().toISOString().split('T')[0]
  const [showRateForm, setShowRateForm] = useState(false)
  const [rateDate, setRateDate] = useState(today)
  const [usdBuy, setUsdBuy] = useState('')
  const [usdSell, setUsdSell] = useState('')
  const [rateError, setRateError] = useState('')

  const ratesQuery = useQuery({
    queryKey: ['savings-exchange-rates'],
    queryFn: fetchSavingsExchangeRates,
  })

  const rateMutation = useMutation({
    mutationFn: () =>
      createSavingsExchangeRate({
        date: rateDate,
        usd_buy: parseFloat(usdBuy),
        usd_sell: parseFloat(usdSell),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savings-exchange-rates'] })
      setShowRateForm(false)
      setUsdBuy('')
      setUsdSell('')
      setRateError('')
    },
    onError: (err) => setRateError(extractErrorMessage(err)),
  })

  const latestRate: SavingsExchangeRate | null = ratesQuery.data?.[0] ?? null

  const withAmount = savings.filter((s) => s.current_amount != null)
  const withoutAmount = savings.length - withAmount.length

  const totalARS = withAmount
    .filter((s) => s.currency === 'ARS')
    .reduce((sum, s) => sum + (s.current_amount ?? 0), 0)

  const totalUSD = withAmount
    .filter((s) => s.currency === 'USD')
    .reduce((sum, s) => sum + (s.current_amount ?? 0), 0)

  const totalInARS = latestRate != null ? totalARS + totalUSD * latestRate.usd_buy : null
  const totalInUSD = latestRate != null ? totalARS / latestRate.usd_sell + totalUSD : null

  const locale = 'es-AR'

  return (
    <div className="panel">
      <div className="panelTitle">Total ahorros</div>

      <div style={{ display: 'flex', gap: '32px', flexWrap: 'wrap', marginBottom: '16px' }}>
        <div>
          <div className="label">Total ARS</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 600, color: 'var(--color-text)' }}>
            ${totalARS.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div>
          <div className="label">Total USD</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 600, color: 'var(--color-text)' }}>
            U$S {totalUSD.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
        <div>
          <div className="label">Total en ARS (incl. USD)</div>
          {totalInARS != null ? (
            <div style={{ fontSize: '1.4rem', fontWeight: 600, color: 'var(--color-primary)' }}>
              ${totalInARS.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          ) : (
            <div style={{ fontSize: '1.1rem', color: 'var(--color-text-secondary)' }}>—</div>
          )}
        </div>
        <div>
          <div className="label">Total en USD (incl. ARS)</div>
          {totalInUSD != null ? (
            <div style={{ fontSize: '1.4rem', fontWeight: 600, color: 'var(--color-primary)' }}>
              U$S {totalInUSD.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          ) : (
            <div style={{ fontSize: '1.1rem', color: 'var(--color-text-secondary)' }}>—</div>
          )}
        </div>
      </div>

      {withoutAmount > 0 && (
        <div className="hint" style={{ marginBottom: '12px' }}>
          {withoutAmount} inversión{withoutAmount > 1 ? 'es' : ''} sin valor registrado (excluida{withoutAmount > 1 ? 's' : ''} del total)
        </div>
      )}

      <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: '12px', marginTop: '4px' }}>
        {latestRate != null ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <span className="muted" style={{ fontSize: '0.85rem' }}>
              Tipo de cambio oficial ({latestRate.date}): compra ${latestRate.usd_buy.toLocaleString(locale)} · venta ${latestRate.usd_sell.toLocaleString(locale)}
            </span>
            <button
              className="button"
              style={{ fontSize: '0.8rem', padding: '4px 10px', background: 'var(--color-surface)', color: 'var(--color-text)', border: '1px solid var(--color-border)' }}
              onClick={() => setShowRateForm((v) => !v)}
              type="button"
            >
              {showRateForm ? 'Cancelar' : 'Actualizar'}
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span className="hint">Registrá un tipo de cambio para ver el total unificado</span>
            <button
              className="button"
              style={{ fontSize: '0.8rem', padding: '4px 10px' }}
              onClick={() => setShowRateForm((v) => !v)}
              type="button"
            >
              {showRateForm ? 'Cancelar' : 'Registrar tipo de cambio'}
            </button>
          </div>
        )}

        {showRateForm && (
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap', marginTop: '12px' }}>
            <div className="formRow" style={{ marginBottom: 0 }}>
              <label className="label">Fecha</label>
              <input
                className="input"
                type="date"
                value={rateDate}
                onChange={(e) => setRateDate(e.target.value)}
                style={{ width: '140px' }}
              />
            </div>
            <div className="formRow" style={{ marginBottom: 0 }}>
              <label className="label">Compra (ARS/USD)</label>
              <input
                className="input"
                type="number"
                step="0.01"
                min="0.01"
                value={usdBuy}
                onChange={(e) => setUsdBuy(e.target.value)}
                placeholder="1150.00"
                style={{ width: '130px' }}
              />
            </div>
            <div className="formRow" style={{ marginBottom: 0 }}>
              <label className="label">Venta (ARS/USD)</label>
              <input
                className="input"
                type="number"
                step="0.01"
                min="0.01"
                value={usdSell}
                onChange={(e) => setUsdSell(e.target.value)}
                placeholder="1200.00"
                style={{ width: '130px' }}
              />
            </div>
            <button
              className="button"
              disabled={
                rateMutation.isPending ||
                !usdBuy ||
                !usdSell ||
                parseFloat(usdBuy) <= 0 ||
                parseFloat(usdSell) <= 0
              }
              onClick={() => rateMutation.mutate()}
              type="button"
            >
              {rateMutation.isPending ? 'Guardando…' : 'Guardar'}
            </button>
            {rateError && <span className="error">{rateError}</span>}
          </div>
        )}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Total history chart                                                */
/* ------------------------------------------------------------------ */

const TOTAL_LINES: Array<{ key: keyof SavingsTotalHistoryPoint; label: string; color: string }> = [
  { key: 'total_ars',    label: 'Total ARS',                 color: LINE_COLORS[0] },
  { key: 'total_usd',    label: 'Total USD',                 color: LINE_COLORS[1] },
  { key: 'total_in_ars', label: 'Total en ARS (combinado)',  color: LINE_COLORS[2] },
  { key: 'total_in_usd', label: 'Total en USD (combinado)',  color: LINE_COLORS[3] },
]

function TotalHistoryChart() {
  const [visibleLines, setVisibleLines] = useState<Set<string>>(
    new Set(['total_ars', 'total_usd'])
  )

  const query = useQuery({
    queryKey: ['savings-total-history'],
    queryFn: fetchSavingsTotalHistory,
  })

  const toggleLine = (key: string) => {
    setVisibleLines((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  if (query.isLoading) return <div className="muted">Cargando…</div>

  const data = query.data ?? []

  if (data.length === 0) {
    return <div className="muted">Sin snapshots registrados para mostrar el historial total</div>
  }

  const activeLines = TOTAL_LINES.filter(({ key }) => visibleLines.has(key))

  return (
    <>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
        {TOTAL_LINES.map(({ key, label, color }) => (
          <label
            key={key}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer', fontSize: '0.9rem', color: 'var(--color-text)' }}
          >
            <input
              type="checkbox"
              checked={visibleLines.has(key)}
              onChange={() => toggleLine(key)}
            />
            <span style={{ color }}>{label}</span>
          </label>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="date" stroke="var(--color-text-secondary)" style={{ fontSize: '0.85rem' }} />
          <YAxis
            stroke="var(--color-text-secondary)"
            style={{ fontSize: '0.85rem' }}
            tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '6px',
              fontSize: '0.9rem',
            }}
            formatter={(value, name) => {
              const line = TOTAL_LINES.find((l) => l.key === String(name))
              const isUsd = String(name).includes('usd')
              const numValue = Number(value)
              const formatted = isUsd
                ? `U$S ${numValue.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                : `$${numValue.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
              return [formatted, line?.label ?? String(name)]
            }}
          />
          {activeLines.map(({ key, color }) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={color}
              strokeWidth={2}
              dot={{ r: 4 }}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </>
  )
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */

export function SavingsPage() {
  const queryClient = useQueryClient()
  const [expandedSnapshotId, setExpandedSnapshotId] = useState<number | null>(null)
  const [selectedChartIds, setSelectedChartIds] = useState<Set<number>>(new Set())

  // New saving form state
  const [personId, setPersonId] = useState('')
  const [investmentType, setInvestmentType] = useState('')
  const [institution, setInstitution] = useState('')
  const [currency, setCurrency] = useState<CurrencyCode>('ARS')
  const [notes, setNotes] = useState('')
  const [formError, setFormError] = useState('')

  const savingsQuery = useQuery({ queryKey: ['savings'], queryFn: fetchSavings })
  const peopleQuery = useQuery({ queryKey: ['people'], queryFn: fetchPeople })

  const savings = savingsQuery.data ?? []
  const people = peopleQuery.data ?? []

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteSaving(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savings'] })
    },
  })

  const createMutation = useMutation({
    mutationFn: () =>
      createSaving({
        person_id: parseInt(personId, 10),
        investment_type: investmentType.trim(),
        institution: institution.trim(),
        currency,
        notes: notes.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['savings'] })
      setPersonId('')
      setInvestmentType('')
      setInstitution('')
      setCurrency('ARS')
      setNotes('')
      setFormError('')
    },
    onError: (err) => setFormError(extractErrorMessage(err)),
  })

  const toggleChartId = (id: number) => {
    setSelectedChartIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="page">
      <h1 className="pageTitle">Ahorros e Inversiones</h1>

      <SavingsTotalsPanel savings={savings} />

      {/* ---- Panel: Total history chart ---- */}
      <div className="panel">
        <div className="panelTitle">Evolución del total</div>
        <TotalHistoryChart />
      </div>

      {/* ---- Panel 1: Table ---- */}
      <div className="panel">
        <div className="panelTitle">Mis inversiones</div>
        {savingsQuery.isLoading && <div className="muted">Cargando…</div>}
        {savings.length === 0 && !savingsQuery.isLoading && (
          <div className="muted">Sin inversiones registradas. Creá una abajo.</div>
        )}
        {savings.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Dueño</th>
                <th>Tipo</th>
                <th>Institución</th>
                <th>Moneda</th>
                <th>Monto actual</th>
                <th>Actualizado</th>
                <th>Notas</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {savings.map((saving) => {
                const owner = people.find((p) => p.id === saving.person_id)
                return (
                  <>
                    <tr key={saving.id}>
                      <td>{owner?.name ?? `#${saving.person_id}`}</td>
                      <td>{saving.investment_type}</td>
                      <td>{saving.institution}</td>
                      <td>{saving.currency}</td>
                      <td>
                        {saving.current_amount != null
                          ? formatAmount(saving.current_amount, saving.currency)
                          : <span className="muted">Sin valor</span>}
                      </td>
                      <td>{saving.current_amount_date ?? <span className="muted">—</span>}</td>
                      <td>{saving.notes ?? <span className="muted">—</span>}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            className="button"
                            style={{ fontSize: '0.8rem', padding: '4px 10px' }}
                            onClick={() =>
                              setExpandedSnapshotId(
                                expandedSnapshotId === saving.id ? null : saving.id
                              )
                            }
                            type="button"
                          >
                            {expandedSnapshotId === saving.id ? 'Cancelar' : 'Actualizar valor'}
                          </button>
                          <button
                            className="button"
                            style={{
                              fontSize: '0.8rem',
                              padding: '4px 10px',
                              background: 'var(--color-surface)',
                              color: 'var(--color-error, #c0392b)',
                              border: '1px solid var(--color-border)',
                            }}
                            disabled={deleteMutation.isPending}
                            onClick={() => {
                              if (confirm(`¿Eliminar "${saving.investment_type} — ${saving.institution}"?`)) {
                                deleteMutation.mutate(saving.id)
                              }
                            }}
                            type="button"
                          >
                            Eliminar
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expandedSnapshotId === saving.id && (
                      <tr key={`snapshot-form-${saving.id}`}>
                        <td colSpan={8} style={{ padding: '12px 16px', background: 'var(--color-bg)' }}>
                          <SnapshotForm
                            saving={saving}
                            onDone={() => setExpandedSnapshotId(null)}
                          />
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
          </div>
        )}
      </div>

      {/* ---- Panel 2: Chart ---- */}
      <div className="panel">
        <div className="panelTitle">Historial</div>
        {savings.length === 0 ? (
          <div className="muted">Sin inversiones para mostrar</div>
        ) : (
          <>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
              {savings.map((s) => {
                const owner = people.find((p) => p.id === s.person_id)
                return (
                  <label
                    key={s.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      cursor: 'pointer',
                      fontSize: '0.9rem',
                      color: 'var(--color-text)',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedChartIds.has(s.id)}
                      onChange={() => toggleChartId(s.id)}
                    />
                    {s.investment_type} — {s.institution}
                    {owner && <span className="hint">({owner.name}, {s.currency})</span>}
                  </label>
                )
              })}
            </div>
            <HistoryChart savings={savings} selectedIds={selectedChartIds} />
          </>
        )}
      </div>

      {/* ---- Panel 3: New saving form ---- */}
      <div className="panel">
        <div className="panelTitle">Nueva inversión</div>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Dueño</label>
            <select
              className="input"
              value={personId}
              onChange={(e) => setPersonId(e.target.value)}
            >
              <option value="">Seleccioná…</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Tipo</label>
            <input
              className="input"
              value={investmentType}
              onChange={(e) => setInvestmentType(e.target.value)}
              placeholder="FCI, Bono, CDAR…"
            />
          </div>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Institución</label>
            <input
              className="input"
              value={institution}
              onChange={(e) => setInstitution(e.target.value)}
              placeholder="Banco Nación, MP…"
            />
          </div>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Moneda</label>
            <select
              className="input"
              value={currency}
              onChange={(e) => setCurrency(e.target.value as CurrencyCode)}
            >
              <option value="ARS">ARS</option>
              <option value="USD">USD</option>
            </select>
          </div>
          <div className="formRow" style={{ marginBottom: 0, flex: 1, minWidth: '200px' }}>
            <label className="label">Notas (opcional)</label>
            <input
              className="input"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Observaciones…"
            />
          </div>
          <button
            className="button"
            style={{ height: '42px' }}
            disabled={
              createMutation.isPending ||
              !personId ||
              !investmentType.trim() ||
              !institution.trim()
            }
            onClick={() => createMutation.mutate()}
            type="button"
          >
            {createMutation.isPending ? 'Creando…' : 'Crear inversión'}
          </button>
        </div>
        {formError && <div className="error" style={{ marginTop: '12px' }}>{formError}</div>}
        {createMutation.isSuccess && (
          <div className="success" style={{ marginTop: '12px' }}>Inversión creada correctamente</div>
        )}
      </div>
    </div>
  )
}

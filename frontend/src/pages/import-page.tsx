import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  detectImportCard,
  fetchCards,
  fetchPeople,
  importGSheets,
  importVisaPdf,
  importVisaXlsx,
} from '../api/endpoints'
import type { DetectImportResult } from '../api/endpoints'
import { extractErrorMessage } from '../api/http'

type ImportFormat = 'xlsx' | 'pdf' | 'gsheets'

interface ImportFormState {
  provider: string
  cardId?: number
  personId?: number
  file?: File
  format: ImportFormat
  pdfPassword: string
  gsheetsUrl: string
  isCommon: boolean
}

function formatYearMonth(ym: string | null): string {
  if (!ym) return '—'
  const [year, month] = ym.split('-')
  const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
  return `${months[parseInt(month) - 1]} ${year}`
}

export function ImportPage() {
  const queryClient = useQueryClient()
  const [formState, setFormState] = useState<ImportFormState>({
    provider: 'santander',
    format: 'xlsx',
    pdfPassword: '',
    gsheetsUrl: '',
    isCommon: true,
  })
  const [detectResult, setDetectResult] = useState<DetectImportResult | null>(null)
  const [importErrors, setImportErrors] = useState<Record<string, string>>({})

  const cardsQuery = useQuery({
    queryKey: ['cards'],
    queryFn: () => fetchCards(),
  })
  const cards = cardsQuery.data ?? []

  const peopleQuery = useQuery({
    queryKey: ['people'],
    queryFn: fetchPeople,
  })
  const people = peopleQuery.data ?? []

  const fileExtensionValid =
    !formState.file ||
    (() => {
      const name = formState.file.name.toLowerCase()
      if (formState.format === 'pdf') return name.endsWith('.pdf')
      return name.endsWith('.xlsx') || name.endsWith('.xls')
    })()

  const detectMutation = useMutation({
    mutationFn: async () => {
      if (!formState.file) throw new Error('Seleccioná un archivo')
      return detectImportCard({
        file: formState.file,
        password: formState.pdfPassword || undefined,
      })
    },
    onSuccess: (result) => {
      setDetectResult(result)
      if (result.suggested_card_id) {
        setFormState((s) => ({ ...s, cardId: result.suggested_card_id! }))
      }
    },
  })

  const importMutation = useMutation({
    mutationFn: async () => {
      if (formState.format === 'gsheets') {
        return importGSheets({
          url: formState.gsheetsUrl,
          owner_person_id: formState.personId!,
          is_common: formState.isCommon,
        })
      }

      const name = formState.file!.name.toLowerCase()
      if (formState.format === 'pdf') {
        if (!name.endsWith('.pdf')) throw new Error('El archivo debe ser .pdf')
        return importVisaPdf({
          provider: formState.provider,
          cardId: formState.cardId!,
          file: formState.file!,
          password: formState.pdfPassword || undefined,
          is_common: formState.isCommon,
        })
      }
      if (!name.endsWith('.xlsx') && !name.endsWith('.xls')) {
        throw new Error('El archivo debe ser .xlsx o .xls')
      }
      return importVisaXlsx({
        provider: formState.provider,
        cardId: formState.cardId!,
        file: formState.file!,
        is_common: formState.isCommon,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchases'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })

  function handleFileChange(file: File | undefined) {
    setFormState((s) => ({ ...s, file }))
    setDetectResult(null)
    detectMutation.reset()
    importMutation.reset()
  }

  const isFileAndFormat =
    formState.format !== 'gsheets' && !!formState.file && fileExtensionValid

  return (
    <section className="page">
      <h2 className="pageTitle">Importar Datos</h2>
      <div className="panel" style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div className="importFormatSelector" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Proveedor</label>
            <select
              className="input importFormatOption"
              onChange={(e) => setFormState((s) => ({ ...s, provider: e.target.value }))}
              value={formState.provider}
            >
              <option value="santander">Santander</option>
              <option value="nacion">Nación</option>
              <option value="mercadopago">MercadoPago</option>
            </select>
          </div>

          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Formato del Archivo</label>
            <select
              className="input importFormatOption"
              onChange={(e) => {
                setFormState((s) => ({ ...s, format: e.target.value as ImportFormat, file: undefined }))
                setImportErrors({})
              }}
              value={formState.format}
            >
              <option value="xlsx">Excel (XLSX)</option>
              <option value="pdf">PDF (resumen)</option>
              <option value="gsheets">Google Sheets / CSV link</option>
            </select>
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--color-border)', margin: '32px 0' }} />

        {formState.format === 'gsheets' ? (
          <>
            <div className="formRow">
              <label className="label">Persona Responsable (Titular)</label>
              <select
                className="input"
                onChange={(e) =>
                  setFormState((s) => ({
                    ...s,
                    personId: e.target.value ? Number(e.target.value) : undefined,
                  }))
                }
                value={formState.personId ?? ''}
              >
                <option value="">Seleccioná una persona...</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              {importErrors.personId && <span className="fieldError">{importErrors.personId}</span>}
            </div>

            <div className="formRow">
              <label className="label">URL de Google Sheets (Publicada como CSV)</label>
              <input
                className="input"
                type="url"
                placeholder="https://docs.google.com/spreadsheets/d/.../pub?output=csv"
                value={formState.gsheetsUrl}
                onChange={(e) => setFormState((s) => ({ ...s, gsheetsUrl: e.target.value }))}
              />
              {importErrors.gsheetsUrl && <span className="fieldError">{importErrors.gsheetsUrl}</span>}
              <div className="hint">Recordá que el documento debe estar configurado como "Publicado en la Web" en formato CSV.</div>
            </div>

            <div className="formRow" style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              marginTop: '32px',
              padding: '16px',
              background: 'var(--color-primary-light)',
              borderRadius: 'var(--radius-md)'
            }}>
              <input
                type="checkbox"
                id="isCommon"
                style={{ width: '20px', height: '20px' }}
                checked={formState.isCommon}
                onChange={(e) => setFormState((s) => ({ ...s, isCommon: e.target.checked }))}
              />
              <label htmlFor="isCommon" className="label" style={{ margin: 0, cursor: 'pointer', userSelect: 'none' }}>
                Marcar compras importadas como <strong>gasto común</strong> (división 50/50)
              </label>
            </div>

            <div style={{ marginTop: '32px' }}>
              <button
                className="button"
                style={{ width: '100%', height: '54px', fontSize: '1.1rem', fontWeight: 700 }}
                disabled={importMutation.isPending}
                onClick={() => {
                  const errors: Record<string, string> = {}
                  if (!formState.personId) errors.personId = 'Seleccioná un responsable'
                  if (!formState.gsheetsUrl.trim()) errors.gsheetsUrl = 'Ingresá la URL del sheet'
                  if (Object.keys(errors).length > 0) {
                    setImportErrors(errors)
                    return
                  }
                  setImportErrors({})
                  importMutation.mutate()
                }}
                type="button"
              >
                {importMutation.isPending ? 'Procesando archivo...' : 'Comenzar Importación'}
              </button>
            </div>
          </>
        ) : (
          <>
            {/* PASO 1: Selección de archivo */}
            <div className="formRow">
              <label className="label">
                Archivo {formState.format === 'pdf' ? 'PDF' : 'Excel'}
              </label>
              <div className="importDropZone" style={{
                border: '2px dashed var(--color-border)',
                padding: '32px',
                borderRadius: 'var(--radius-md)',
                textAlign: 'center',
                backgroundColor: 'var(--color-primary-light)',
                cursor: 'pointer',
                position: 'relative'
              }}>
                <input
                  style={{
                    position: 'absolute',
                    top: 0, left: 0, width: '100%', height: '100%',
                    opacity: 0, cursor: 'pointer'
                  }}
                  accept={formState.format === 'pdf' ? '.pdf' : '.xlsx,.xls'}
                  onChange={(e) => handleFileChange(e.target.files?.[0])}
                  type="file"
                />
                <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>{formState.file ? '📄' : '📤'}</div>
                <div style={{ fontWeight: 600, color: 'var(--color-text)' }}>
                  {formState.file ? formState.file.name : `Click o arrastrá tu archivo ${formState.format === 'pdf' ? 'PDF' : 'XLSX'}`}
                </div>
                <div className="hint" style={{ marginTop: '8px' }}>
                  {formState.format === 'pdf'
                    ? 'Resúmenes de Banco Nación o MercadoPago.'
                    : 'Formato Visa XLSX exportado desde el Home Banking.'}
                </div>
              </div>
              {formState.file && !fileExtensionValid ? (
                <div className="error" style={{ marginTop: 12 }}>
                  El archivo debe ser {formState.format === 'pdf' ? '.pdf' : '.xlsx o .xls'}
                </div>
              ) : null}
            </div>

            {formState.format === 'pdf' ? (
              <div className="formRow">
                <label className="label">Contraseña del PDF (si aplica)</label>
                <input
                  className="input"
                  type="password"
                  placeholder="Password del archivo..."
                  value={formState.pdfPassword}
                  onChange={(e) => setFormState((s) => ({ ...s, pdfPassword: e.target.value }))}
                  autoComplete="off"
                />
                <div className="hint">Solo necesaria si el resumen está protegido.</div>
              </div>
            ) : null}

            {/* Botón Analizar (Paso 1) */}
            {!detectResult ? (
              <div className="importSubmitRow" style={{ marginTop: '24px' }}>
                <button
                  className="button"
                  style={{ width: '100%', height: '48px', fontSize: '1rem', fontWeight: 600 }}
                  disabled={!isFileAndFormat || detectMutation.isPending}
                  onClick={() => detectMutation.mutate()}
                  type="button"
                >
                  {detectMutation.isPending ? 'Analizando archivo...' : 'Analizar archivo'}
                </button>
              </div>
            ) : null}

            {detectMutation.isError ? (
              <div className="error" style={{ marginTop: '16px' }}>
                <strong>Error al analizar:</strong> {extractErrorMessage(detectMutation.error)}
              </div>
            ) : null}

            {/* PASO 2: Resultado de detección + confirmación */}
            {detectResult ? (
              <div style={{ marginTop: '24px' }}>
                {/* Panel de info detectada */}
                <div style={{
                  background: 'var(--color-primary-light)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                  padding: '16px 20px',
                  marginBottom: '24px',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
                  gap: '12px',
                  textAlign: 'center',
                }}>
                  <div>
                    <div className="label" style={{ marginBottom: '4px' }}>Titular</div>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                      {detectResult.detected_holder
                        ? detectResult.detected_holder + (detectResult.detected_last4 ? ` ···${detectResult.detected_last4}` : '')
                        : <span className="muted">No detectado</span>}
                    </div>
                  </div>
                  <div>
                    <div className="label" style={{ marginBottom: '4px' }}>Tipo de tarjeta</div>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                      {detectResult.detected_card_type ?? <span className="muted">—</span>}
                    </div>
                  </div>
                  <div>
                    <div className="label" style={{ marginBottom: '4px' }}>Banco / Emisor</div>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                      {detectResult.detected_bank
                        ? detectResult.detected_bank.charAt(0).toUpperCase() + detectResult.detected_bank.slice(1)
                        : <span className="muted">—</span>}
                    </div>
                  </div>
                  <div>
                    <div className="label" style={{ marginBottom: '4px' }}>Mes del resumen</div>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                      {formatYearMonth(detectResult.statement_year_month)}
                    </div>
                  </div>
                  <div>
                    <div className="label" style={{ marginBottom: '4px' }}>Transacciones</div>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{detectResult.row_count}</div>
                  </div>
                  <div />
                </div>

                {/* Selector de tarjeta (pre-seleccionado si se detectó) */}
                <div className="formRow">
                  <label className="label">
                    Tarjeta Destino
                    {detectResult.suggested_card_id
                      ? <span style={{ marginLeft: '8px', color: 'var(--color-primary)', fontWeight: 400 }}>— detectada automáticamente</span>
                      : <span style={{ marginLeft: '8px', color: 'var(--color-text-secondary)', fontWeight: 400 }}>— seleccioná manualmente</span>}
                  </label>
                  <select
                    className="input"
                    onChange={(e) =>
                      setFormState((s) => ({
                        ...s,
                        cardId: e.target.value ? Number(e.target.value) : undefined,
                      }))
                    }
                    value={formState.cardId ?? ''}
                  >
                    <option value="">Seleccioná una tarjeta...</option>
                    {cards.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.provider})
                      </option>
                    ))}
                  </select>
                  {importErrors.cardId && <span className="fieldError">{importErrors.cardId}</span>}
                </div>

                <div className="formRow" style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '16px',
                  background: 'var(--color-primary-light)',
                  borderRadius: 'var(--radius-md)'
                }}>
                  <input
                    type="checkbox"
                    id="isCommon"
                    style={{ width: '20px', height: '20px' }}
                    checked={formState.isCommon}
                    onChange={(e) => setFormState((s) => ({ ...s, isCommon: e.target.checked }))}
                  />
                  <label htmlFor="isCommon" className="label" style={{ margin: 0, cursor: 'pointer', userSelect: 'none' }}>
                    Marcar compras importadas como <strong>gasto común</strong> (división 50/50)
                  </label>
                </div>

                <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                  <button
                    className="button"
                    style={{ flex: 1, height: '54px', fontSize: '1.1rem', fontWeight: 700 }}
                    disabled={importMutation.isPending}
                    onClick={() => {
                      if (!formState.cardId) {
                        setImportErrors({ cardId: 'Seleccioná una tarjeta' })
                        return
                      }
                      setImportErrors({})
                      importMutation.mutate()
                    }}
                    type="button"
                  >
                    {importMutation.isPending ? 'Importando...' : 'Confirmar e Importar'}
                  </button>
                  <button
                    style={{
                      height: '54px',
                      padding: '0 20px',
                      background: 'none',
                      border: '1px solid var(--color-border)',
                      borderRadius: 'var(--radius-md)',
                      cursor: 'pointer',
                      color: 'var(--color-text-secondary)',
                      fontWeight: 500,
                    }}
                    onClick={() => {
                      setDetectResult(null)
                      detectMutation.reset()
                      importMutation.reset()
                    }}
                    type="button"
                  >
                    Volver
                  </button>
                </div>
              </div>
            ) : null}
          </>
        )}

        {importMutation.isError ? (
          <div className="error" style={{ marginTop: '24px' }}>
            <strong>Error:</strong> {extractErrorMessage(importMutation.error)}
          </div>
        ) : null}

        {importMutation.isSuccess ? (
          <div className="success" style={{ marginTop: '24px', padding: '24px' }}>
            <div style={{ fontWeight: 800, fontSize: '1.2rem', marginBottom: '8px' }}>Importación Exitosa</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', textAlign: 'center' }}>
              <div>
                <div className="label">Creadas</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800 }}>{importMutation.data.created}</div>
              </div>
              <div>
                <div className="label">Salteadas</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-text-secondary)' }}>{importMutation.data.skipped}</div>
              </div>
              <div>
                <div className="label">Total Parseadas</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--color-primary)' }}>{importMutation.data.parsed}</div>
              </div>
            </div>
            {importMutation.data.batch_id != null && (
              <div style={{ marginTop: '16px', textAlign: 'center' }}>
                <a
                  href={`/purchases?batch=${importMutation.data.batch_id}`}
                  style={{ fontWeight: 600, color: 'var(--color-primary)' }}
                >
                  Ver compras importadas →
                </a>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </section>
  )
}

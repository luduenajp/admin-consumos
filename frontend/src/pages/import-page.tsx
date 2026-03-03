import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { fetchCards, fetchPeople, importGSheets, importVisaPdf, importVisaXlsx } from '../api/endpoints'
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

export function ImportPage() {
  const queryClient = useQueryClient()
  const [formState, setFormState] = useState<ImportFormState>({
    provider: 'santander',
    format: 'xlsx',
    pdfPassword: '',
    gsheetsUrl: '',
    isCommon: true,
  })

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

  const selectedCard = useMemo(
    function () {
      if (!formState.cardId) return undefined
      return cards.find((c) => c.id === formState.cardId)
    },
    [cards, formState.cardId],
  )

  const fileExtensionValid =
    !formState.file ||
    (() => {
      const name = formState.file.name.toLowerCase()
      if (formState.format === 'pdf') return name.endsWith('.pdf')
      return name.endsWith('.xlsx') || name.endsWith('.xls')
    })()

  const importMutation = useMutation({
    mutationFn: async () => {
      if (formState.format === 'gsheets') {
        if (!formState.personId) throw new Error('Seleccioná un responsable del gasto')
        if (!formState.gsheetsUrl) throw new Error('Ingresá la URL del archivo de Google Sheets')
        return importGSheets({
          url: formState.gsheetsUrl,
          owner_person_id: formState.personId,
          is_common: formState.isCommon,
        })
      }

      if (!formState.cardId) throw new Error('Seleccioná una tarjeta')
      if (!formState.file) throw new Error('Seleccioná un archivo')

      const name = formState.file.name.toLowerCase()
      if (formState.format === 'pdf') {
        if (!name.endsWith('.pdf')) throw new Error('El archivo debe ser .pdf')
        return importVisaPdf({
          provider: formState.provider,
          cardId: formState.cardId,
          file: formState.file,
          password: formState.pdfPassword || undefined,
          is_common: formState.isCommon,
        })
      }
      if (!name.endsWith('.xlsx') && !name.endsWith('.xls')) {
        throw new Error('El archivo debe ser .xlsx o .xls')
      }
      return importVisaXlsx({
        provider: formState.provider,
        cardId: formState.cardId,
        file: formState.file,
        is_common: formState.isCommon,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchases'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })

  return (
    <section className="page">
      <h2 className="pageTitle">Importar Datos</h2>
      <div className="panel" style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
          <div className="formRow" style={{ marginBottom: 0 }}>
            <label className="label">Proveedor</label>
            <select
              className="input"
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
              className="input"
              onChange={(e) =>
                setFormState((s) => ({
                  ...s,
                  format: e.target.value as ImportFormat,
                  file: undefined,
                }))
              }
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
          </div>
        ) : (
          <div className="formRow">
            <label className="label">Tarjeta Destino</label>
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
            {selectedCard ? <div className="hint" style={{ marginTop: '8px' }}>El gasto se registrará a nombre de: <strong>ID {selectedCard.owner_person_id}</strong></div> : null}
          </div>
        )}

        {formState.format === 'gsheets' ? (
          <div className="formRow">
            <label className="label">URL de Google Sheets (Publicada como CSV)</label>
            <input
              className="input"
              type="url"
              placeholder="https://docs.google.com/spreadsheets/d/.../pub?output=csv"
              value={formState.gsheetsUrl}
              onChange={(e) => setFormState((s) => ({ ...s, gsheetsUrl: e.target.value }))}
            />
            <div className="hint">Recordá que el documento debe estar configurado como "Publicado en la Web" en formato CSV.</div>
          </div>
        ) : (
          <>
            <div className="formRow">
              <label className="label">
                Archivo {formState.format === 'pdf' ? 'PDF' : 'Excel'} seleccionado
              </label>
              <div style={{
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
                  onChange={(e) => setFormState((s) => ({ ...s, file: e.target.files?.[0] }))}
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
                  ⚠️ El archivo debe ser {formState.format === 'pdf' ? '.pdf' : '.xlsx o .xls'}
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
          </>
        )}

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
            disabled={
              importMutation.isPending ||
              (formState.format !== 'gsheets' && !!formState.file && !fileExtensionValid) ||
              (formState.format === 'gsheets' && !formState.gsheetsUrl)
            }
            onClick={() => importMutation.mutate()}
            type="button"
          >
            {importMutation.isPending ? 'Procesando archivo...' : 'Comenzar Importación'}
          </button>
        </div>

        {importMutation.isError ? (
          <div className="error" style={{ marginTop: '24px' }}>
            <strong>Error:</strong> {extractErrorMessage(importMutation.error)}
          </div>
        ) : null}

        {importMutation.isSuccess ? (
          <div className="success" style={{ marginTop: '24px', padding: '24px' }}>
            <div style={{ fontWeight: 800, fontSize: '1.2rem', marginBottom: '8px' }}>✅ Importación Exitosa</div>
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
          </div>
        ) : null}
      </div>
    </section>
  )
}

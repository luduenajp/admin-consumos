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
}

export function ImportPage() {
  const queryClient = useQueryClient()
  const [formState, setFormState] = useState<ImportFormState>({
    provider: 'santander',
    format: 'xlsx',
    pdfPassword: '',
    gsheetsUrl: '',
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
        })
      }
      if (!name.endsWith('.xlsx') && !name.endsWith('.xls')) {
        throw new Error('El archivo debe ser .xlsx o .xls')
      }
      return importVisaXlsx({
        provider: formState.provider,
        cardId: formState.cardId,
        file: formState.file,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchases'] })
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
  })

  return (
    <section className="page">
      <h2 className="pageTitle">Importar</h2>
      <div className="panel">
        <div className="formRow">
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

        <div className="formRow">
          <label className="label">Formato</label>
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

        {formState.format === 'gsheets' ? (
          <div className="formRow">
            <label className="label">Responsable del gasto (Origen)</label>
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
              <option value="">Seleccioná...</option>
              {people.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>
        ) : (
          <div className="formRow">
            <label className="label">Tarjeta</label>
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
              <option value="">Seleccioná...</option>
              {cards.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.provider})
                </option>
              ))}
            </select>
            {selectedCard ? <div className="hint">Dueño: person_id {selectedCard.owner_person_id}</div> : null}
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
            <div className="hint">Pegá el link de "Publicar en la web" en formato Valores separados por comas (.csv) o el link a un archivo CSV.</div>
          </div>
        ) : (
          <>
            <div className="formRow">
              <label className="label">
                Archivo ({formState.format === 'pdf' ? 'PDF' : 'XLSX'})
              </label>
              <input
                className="input"
                accept={formState.format === 'pdf' ? '.pdf' : '.xlsx,.xls'}
                onChange={(e) => setFormState((s) => ({ ...s, file: e.target.files?.[0] }))}
                type="file"
              />
              <div className="hint">
                {formState.format === 'pdf'
                  ? 'Resumen en PDF (Banco Nación Visa/Mastercard, MercadoPago). Contraseña abajo si aplica.'
                  : 'Por ahora soporta el formato Visa XLSX como el ejemplo.'}
              </div>
              {formState.file && !fileExtensionValid ? (
                <div className="error" style={{ marginTop: 6 }}>
                  El archivo debe tener extensión {formState.format === 'pdf' ? '.pdf' : '.xlsx o .xls'}
                </div>
              ) : null}
            </div>

            {formState.format === 'pdf' ? (
              <div className="formRow">
                <label className="label">Contraseña del PDF (si aplica)</label>
                <input
                  className="input"
                  type="password"
                  placeholder="Dejá vacío si el PDF no tiene contraseña"
                  value={formState.pdfPassword}
                  onChange={(e) => setFormState((s) => ({ ...s, pdfPassword: e.target.value }))}
                  autoComplete="off"
                />
                <div className="hint">Solo necesaria si el resumen está protegido con contraseña.</div>
              </div>
            ) : null}
          </>
        )}

        <div className="formRow">
          <button
            className="button"
            disabled={
              importMutation.isPending ||
              (formState.format !== 'gsheets' && !!formState.file && !fileExtensionValid) ||
              (formState.format === 'gsheets' && !formState.gsheetsUrl)
            }
            onClick={() => importMutation.mutate()}
            type="button"
          >
            {importMutation.isPending ? 'Importando...' : 'Importar'}
          </button>
        </div>

        {importMutation.isError ? <div className="error">Error: {extractErrorMessage(importMutation.error)}</div> : null}
        {importMutation.isSuccess ? (
          <div className="success">
            Importación OK. Creadas: {importMutation.data.created}, Salteadas: {importMutation.data.skipped},
            Parseadas: {importMutation.data.parsed}
          </div>
        ) : null}
      </div>
    </section>
  )
}

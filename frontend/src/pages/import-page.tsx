import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { fetchCards, importVisaPdf, importVisaXlsx } from '../api/endpoints'
import { extractErrorMessage } from '../api/http'

type ImportFormat = 'xlsx' | 'pdf'

interface ImportFormState {
  provider: string
  cardId?: number
  file?: File
  format: ImportFormat
  pdfPassword: string
}

export function ImportPage() {
  const queryClient = useQueryClient()
  const [formState, setFormState] = useState<ImportFormState>({
    provider: 'santander',
    format: 'xlsx',
    pdfPassword: '',
  })

  const cardsQuery = useQuery({
    queryKey: ['cards'],
    queryFn: () => fetchCards(),
  })

  const cards = cardsQuery.data ?? []

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
          </select>
        </div>

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

        <div className="formRow">
          <button
            className="button"
            disabled={importMutation.isPending || (!!formState.file && !fileExtensionValid)}
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

import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { fetchCards, importVisaXlsx } from '../api/endpoints'

interface ImportFormState {
  provider: string
  cardId?: number
  file?: File
}

export function ImportPage() {
  const [formState, setFormState] = useState<ImportFormState>({
    provider: 'santander',
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

  const importMutation = useMutation({
    mutationFn: async () => {
      if (!formState.cardId) throw new Error('Seleccioná una tarjeta')
      if (!formState.file) throw new Error('Seleccioná un archivo XLSX')
      return importVisaXlsx({
        provider: formState.provider,
        cardId: formState.cardId,
        file: formState.file,
      })
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
          <label className="label">Archivo (XLSX)</label>
          <input
            className="input"
            onChange={(e) => setFormState((s) => ({ ...s, file: e.target.files?.[0] }))}
            type="file"
          />
          <div className="hint">Por ahora soporta el formato Visa XLSX como el ejemplo.</div>
        </div>

        <div className="formRow">
          <button
            className="button"
            disabled={importMutation.isPending}
            onClick={() => importMutation.mutate()}
            type="button"
          >
            {importMutation.isPending ? 'Importando...' : 'Importar'}
          </button>
        </div>

        {importMutation.isError ? <div className="error">Error: {String(importMutation.error)}</div> : null}
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

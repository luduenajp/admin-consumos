import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { fetchPendingSharedComprobante } from '../api/endpoints'
import { PurchaseForm } from '../components/PurchaseForm'
import { Spinner } from '../components/Spinner'
import { retrieveSharedFile } from '../utils/sharedFile'

/**
 * Destino del Web Share Target: al compartir un comprobante desde Android,
 * el service worker lo deja en Cache API y redirige acá con ?shared=1.
 * Si el SW no interceptó el POST (p. ej. lanzamiento en frío), el backend
 * lo deja pendiente y agrega ?token=... para recuperarlo por API (UC-054).
 * También funciona como deep link directo (formulario vacío).
 */
export function NuevaTransferenciaPage() {
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const isShared = searchParams.get('shared') === '1'
    const pendingToken = searchParams.get('token')
    const swDiag = searchParams.get('sw')

    const [sharedFile, setSharedFile] = useState<File | null>(null)
    const [retrieving, setRetrieving] = useState(isShared)
    const [retrieveFailed, setRetrieveFailed] = useState(false)

    useEffect(() => {
        if (!isShared) return
        let cancelled = false
        retrieveSharedFile()
            .then((file) => {
                if (file) return file
                return pendingToken ? fetchPendingSharedComprobante(pendingToken) : null
            })
            .then((file) => {
                if (cancelled) return
                if (file) {
                    setSharedFile(file)
                } else {
                    console.error('[share-target] no se encontró el comprobante compartido (ni en Cache API ni por token)')
                    setRetrieveFailed(true)
                }
            })
            .catch((err) => {
                if (cancelled) return
                console.error('[share-target] fallo al recuperar el comprobante compartido', err)
                setRetrieveFailed(true)
            })
            .finally(() => {
                if (!cancelled) setRetrieving(false)
            })
        return () => {
            cancelled = true
        }
    }, [isShared, pendingToken])

    return (
        <div className="page">
            <h1 className="pageTitle">Nueva transferencia</h1>
            <div className="panel" style={{ border: '1px solid var(--color-primary)' }}>
                <div className="panelTitle">Datos de la transferencia</div>
                {retrieving ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Spinner size={16} />
                        <span className="muted">Recuperando comprobante compartido...</span>
                    </div>
                ) : (
                    <>
                        {retrieveFailed && (
                            <p className="error">
                                No pudimos recuperar el comprobante compartido automáticamente. Subilo manualmente abajo.
                                {swDiag && <> (diagnóstico: <code>{swDiag}</code>)</>}
                            </p>
                        )}
                        <PurchaseForm
                            initialValues={{ payment_method: 'transfer' }}
                            initialFile={sharedFile ?? undefined}
                            onSuccess={() => navigate('/')}
                            onCancel={() => navigate('/')}
                        />
                    </>
                )}
            </div>
        </div>
    )
}

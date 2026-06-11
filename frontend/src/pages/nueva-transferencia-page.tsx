import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { PurchaseForm } from '../components/PurchaseForm'
import { Spinner } from '../components/Spinner'
import { retrieveSharedFile } from '../utils/sharedFile'

/**
 * Destino del Web Share Target: al compartir un comprobante desde Android,
 * el service worker lo deja en Cache API y redirige acá con ?shared=1.
 * También funciona como deep link directo (formulario vacío).
 */
export function NuevaTransferenciaPage() {
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const isShared = searchParams.get('shared') === '1'

    const [sharedFile, setSharedFile] = useState<File | null>(null)
    const [retrieving, setRetrieving] = useState(isShared)

    useEffect(() => {
        if (!isShared) return
        let cancelled = false
        retrieveSharedFile()
            .then((file) => {
                if (!cancelled && file) setSharedFile(file)
            })
            .catch(() => undefined)
            .finally(() => {
                if (!cancelled) setRetrieving(false)
            })
        return () => {
            cancelled = true
        }
    }, [isShared])

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
                    <PurchaseForm
                        initialValues={{ payment_method: 'transfer' }}
                        initialFile={sharedFile ?? undefined}
                        onSuccess={() => navigate('/')}
                        onCancel={() => navigate('/')}
                    />
                )}
            </div>
        </div>
    )
}

const SHARE_CACHE = 'shared-comprobante'
const SHARE_KEY = '/shared-comprobante'

/**
 * Recupera el comprobante que el service worker dejó en Cache API al
 * interceptar el POST del Web Share Target (ver public/sw.js).
 * Devuelve null si no hay archivo pendiente. Borra la entrada al leerla.
 */
export async function retrieveSharedFile(): Promise<File | null> {
    if (!('caches' in window)) return null
    const cache = await caches.open(SHARE_CACHE)
    const resp = await cache.match(SHARE_KEY)
    if (!resp) return null
    await cache.delete(SHARE_KEY)
    const buffer = await resp.arrayBuffer()
    const name = decodeURIComponent(resp.headers.get('X-File-Name') ?? 'comprobante')
    const type = resp.headers.get('Content-Type') ?? 'application/octet-stream'
    return new File([buffer], name, { type })
}

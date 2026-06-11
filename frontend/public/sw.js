// Service worker mínimo: su único trabajo es interceptar el POST del
// Web Share Target de Android y dejar el archivo compartido en Cache API
// para que /nueva-transferencia lo levante. No cachea ningún asset.
const SHARE_CACHE = 'shared-comprobante'

self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (event.request.method === 'POST' && url.pathname === '/share-target') {
    event.respondWith(
      (async () => {
        try {
          const formData = await event.request.formData()
          const file = formData.get('file')
          if (file && file.size > 0) {
            const cache = await caches.open(SHARE_CACHE)
            await cache.put(
              '/shared-comprobante',
              new Response(file, {
                headers: {
                  'Content-Type': file.type || 'application/octet-stream',
                  'X-File-Name': encodeURIComponent(file.name || 'comprobante'),
                },
              })
            )
          }
        } catch {
          // sin archivo: la página abre el formulario vacío igual
        }
        return Response.redirect('/nueva-transferencia?shared=1', 303)
      })()
    )
  }
  // Resto de requests: sin respondWith, pasan a la red sin tocar.
})

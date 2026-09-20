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
        // Diagnóstico temporal: el resultado (ok / no-file / error:<msg>) viaja
        // en el query param `sw` del redirect para poder verlo en los logs del
        // servidor sin depender de la consola del navegador del teléfono.
        let diag = 'no-file'
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
            diag = 'ok:' + file.size
          } else {
            // No vino nada bajo el campo "file": listamos lo que sí llegó
            // (nombres de campo, tipos y tamaños) para diagnosticar un
            // posible mismatch de MIME contra el `accept` del manifest.
            const parts = []
            for (const [key, value] of formData.entries()) {
              if (value && typeof value === 'object' && 'size' in value) {
                parts.push(`${key}=file(${value.type || '?'},${value.size}b,${value.name || '?'})`)
              } else {
                parts.push(`${key}=${String(value).slice(0, 30)}`)
              }
            }
            diag = 'no-file:[' + parts.join('|') + ']'
          }
        } catch (err) {
          diag = 'error:' + (err && err.message ? String(err.message).slice(0, 80) : String(err))
        }
        return Response.redirect(
          `/nueva-transferencia?shared=1&sw=${encodeURIComponent(diag)}`,
          303
        )
      })()
    )
  }
  // Resto de requests: sin respondWith, pasan a la red sin tocar.
})

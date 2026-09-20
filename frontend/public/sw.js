// Service worker mínimo. No cachea ningún asset.
//
// El POST del Web Share Target de Android (/share-target) NO se intercepta
// acá a propósito: en los dispositivos probados, cuando el SW intenta leer
// el body vía event.request.formData(), llega vacío (ni siquiera los
// campos de texto), un problema conocido de Chrome/Android donde el body
// de la navegación del share target no le llega al fetch handler del SW.
// Por eso esas requests pasan de largo a la red: el backend
// (POST /share-target en backend/app/main.py) las recibe y parsea el
// multipart de forma confiable, guardando el archivo con un token de un
// solo uso que /nueva-transferencia recupera vía
// GET /api/share-target/pending/{token} (ver UC-054 en SPEC.md).
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

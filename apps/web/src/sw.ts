/**
 * Service worker · el armazón de la aplicación sin red `[REQ]` §15.8.
 *
 * Hace **una sola cosa**: que la aplicación abra sin cobertura. En una visita
 * el móvil pierde señal en el sótano, y sin esto la pantalla es la del dinosaurio
 * del navegador: no se puede ni llegar a la cola de fotos que sí está guardada.
 *
 * Lo que **no** hace, y es deliberado:
 *
 * * **No cachea ninguna respuesta de `/api`.** Un CAPEX servido desde caché es
 *   un número viejo presentado como actual, y eso en un informe que se entrega
 *   es peor que un error de red. Sin conexión, la API falla y la pantalla lo
 *   dice.
 * * **No sube nada en segundo plano.** La Background Sync API no está usada:
 *   las fotos van cuando la aplicación está abierta. Prometer lo contrario
 *   sería decir que una visita se sube sola con el móvil en el bolsillo.
 *
 * `[LIM]` Sin iconos en el manifiesto todavía, así que el navegador no ofrece
 * «instalar» en todas las plataformas. El armazón sí funciona sin red.
 */

// El `self` de un service worker no es el `window` del navegador: tiene
// `skipWaiting`, `clients` y los eventos `install`/`activate`/`fetch` con sus
// métodos. Se comprueba con `tsconfig.sw.json`, que usa la biblioteca
// `WebWorker` en vez de `DOM`: darle las definiciones del DOM haría que
// TypeScript aprobara código que revienta en cuanto se ejecuta.
// `export {}` convierte el fichero en módulo: sin eso, `declare const self`
// choca con el `self` global en vez de precisarlo, y TypeScript trata cada
// evento como un `Event` genérico sin `respondWith`.
export {}

declare const self: ServiceWorkerGlobalScope & typeof globalThis

// Vite reemplaza esto en la compilación: la lista real de ficheros con su hash.
// Sin el hash, una versión nueva serviría el JavaScript viejo desde la caché.
declare const __ARMAZON__: string[]

const CACHE = 'tdd-armazon-v1'

/**
 * `ignoreVary` no es opcional aquí.
 *
 * Las entradas del armazón las guarda `addAll`, que pide sin cabecera `Origin`.
 * El `<script crossorigin>` que genera Vite **sí** la manda, y el servidor
 * responde con `Vary: Origin`. Sin `ignoreVary`, la búsqueda en la caché no
 * encuentra nunca ese fichero: con red no se nota —se descarga y ya— y sin red
 * la aplicación abre en blanco. Cualquier proxy que añada
 * `Vary: Accept-Encoding` rompería lo mismo.
 *
 * Se encontró abriendo la aplicación sin conexión en un navegador de verdad.
 * No hay forma de verlo de otra manera.
 */
const BUSCAR = { ignoreVary: true } as const

self.addEventListener('install', (evento) => {
  evento.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(__ARMAZON__))
      // `skipWaiting` para que una versión nueva entre en el siguiente arranque
      // y no cuando al usuario le dé por cerrar todas las pestañas, que en un
      // móvil puede no pasar en semanas.
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (evento) => {
  evento.waitUntil(
    caches
      .keys()
      .then((claves) => Promise.all(claves.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (evento) => {
  const peticion = evento.request
  const url = new URL(peticion.url)

  // Solo GET del propio origen. Una subida de foto o un login nunca pasan por
  // aquí: reintentarlos desde el worker duplicaría escrituras.
  if (peticion.method !== 'GET' || url.origin !== self.location.origin) return

  // `[REQ]` La API nunca se sirve desde caché. Un dato viejo presentado como
  // actual es peor que un error visible.
  if (url.pathname.startsWith('/api/')) return

  // Navegación: red primero, y el armazón guardado si no hay. Al revés —caché
  // primero— la aplicación se quedaría en una versión antigua hasta que alguien
  // limpiara el navegador.
  if (peticion.mode === 'navigate') {
    evento.respondWith(
      fetch(peticion).catch(() =>
        caches.match('/index.html', BUSCAR).then((r) => r ?? Response.error()),
      ),
    )
    return
  }

  // Estáticos con hash en el nombre: caché primero, porque su contenido no
  // cambia nunca. Si cambiara, cambiaría el nombre.
  evento.respondWith(
    caches.match(peticion, BUSCAR).then(
      (guardada) =>
        guardada ??
        fetch(peticion).then((respuesta) => {
          if (respuesta.ok && respuesta.type === 'basic') {
            const copia = respuesta.clone()
            void caches.open(CACHE).then((c) => c.put(peticion, copia))
          }
          return respuesta
        }),
    ),
  )
})

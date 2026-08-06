/**
 * ¿Abre la aplicación sin red? `[REQ]` §15.8
 *
 * Es la única forma de comprobarlo. Un service worker no se puede probar con
 * vitest —no hay `caches`, ni ciclo de instalación, ni control de la página— y
 * afirmar «funciona sin conexión» sin haberlo visto es justo lo que no se puede
 * hacer. Así que se abre un navegador de verdad, se le corta la red y se mira.
 *
 * No es teatro: **encontró un fallo que ninguna otra comprobación veía.** El
 * servidor responde con `Vary: Origin`, las entradas del armazón se guardan sin
 * esa cabecera y el `<script crossorigin>` la manda, así que la búsqueda en la
 * caché no encontraba nunca el JavaScript. Con red no se nota —se descarga y
 * ya—; sin red la aplicación abría en blanco. Se arregló con `ignoreVary`.
 *
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-sin-red.mjs
 */
import { chromium } from 'playwright'

const BASE = process.env.URL_BASE ?? 'http://localhost:4173'
const fallos = []

// Sin ruta fija al navegador: Playwright usa el que tenga instalado. La
// variable existe para los entornos que traen Chromium en otro sitio; escribir
// una ruta concreta aquí habría hecho que esto solo funcionara en una máquina.
const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
)
const contexto = await navegador.newContext()
const pagina = await contexto.newPage()

console.log('· Primera visita, con red')
await pagina.goto(BASE, { waitUntil: 'networkidle' })
const titulo = await pagina.title()
console.log('  título:', titulo)
if (!titulo.includes('due diligence') && !titulo.includes('Due diligence')) {
  fallos.push('La página no carga el título esperado')
}

console.log('· El service worker se registra y activa')
const activo = await pagina.evaluate(async () => {
  const reg = await navigator.serviceWorker.ready
  return { alcance: reg.scope, estado: reg.active?.state ?? 'ninguno' }
})
console.log('  ', activo)
if (activo.estado !== 'activated') fallos.push('El service worker no llega a activarse')

console.log('· El armazón está en la caché, con sus hashes')
const cacheado = await pagina.evaluate(async () => {
  const nombres = await caches.keys()
  const c = await caches.open(nombres[0])
  return (await c.keys()).map((r) => new URL(r.url).pathname).sort()
})
console.log('  ', cacheado)
if (!cacheado.some((p) => p.endsWith('.js'))) fallos.push('El JavaScript no está precacheado')
if (!cacheado.some((p) => p.endsWith('.css'))) fallos.push('El CSS no está precacheado')

console.log('· Ahora sin red: la aplicación tiene que abrir igual')
await contexto.setOffline(true)
const respuesta = await pagina.goto(BASE, { waitUntil: 'domcontentloaded' })
console.log('  estado de la navegación:', respuesta?.status())
// Con la aplicación cargada, sin sesión, debe verse la pantalla de entrar.
await pagina.waitForTimeout(800)
const texto = await pagina.evaluate(() => document.body.innerText)
console.log('  texto visible:', JSON.stringify(texto.slice(0, 120)))
if (texto.trim().length === 0) {
  fallos.push('Sin red la aplicación no pinta nada: el armazón no sirve')
}

console.log('· El manifiesto es instalable')
const manifiesto = await pagina.evaluate(async () => {
  const r = await fetch('/manifest.webmanifest')
  return r.ok ? await r.json() : null
})
if (!manifiesto) {
  fallos.push('No se ha podido leer el manifiesto')
} else {
  const tamanos = (manifiesto.icons ?? []).map((i) => i.sizes)
  const enmascarables = (manifiesto.icons ?? []).filter((i) =>
    (i.purpose ?? '').includes('maskable'),
  )
  console.log('   iconos:', tamanos.join(', '), '· maskable:', enmascarables.length)
  // Los dos tamaños que exigen Chrome y Android para ofrecer «instalar».
  for (const requerido of ['192x192', '512x512']) {
    if (!tamanos.includes(requerido)) {
      fallos.push(`El manifiesto no declara un icono de ${requerido}: no será instalable`)
    }
  }
  if (enmascarables.length === 0) {
    fallos.push('Sin icono «maskable», Android recorta el dibujo en el círculo')
  }
  // Y los ficheros existen de verdad: un manifiesto que apunta a un 404 se
  // acepta igual y el icono sale en blanco.
  for (const icono of manifiesto.icons ?? []) {
    const estado = await pagina.evaluate(
      async (src) => (await fetch(src)).status,
      icono.src,
    )
    if (estado !== 200) fallos.push(`El icono ${icono.src} devuelve ${estado}`)
  }
}

console.log('· La API NO se sirve desde caché')
// Se pide con red y luego sin ella: si el worker la hubiera cacheado, la
// segunda respondería 200 con un dato viejo, que es peor que un error visible.
await contexto.setOffline(false)
await pagina.evaluate(async () => {
  await fetch('/api/v1/catalogs/zones').catch(() => undefined)
})
await contexto.setOffline(true)
const apiSinRed = await pagina.evaluate(async () => {
  try {
    const r = await fetch('/api/v1/catalogs/zones')
    return { ok: true, status: r.status }
  } catch {
    return { ok: false }
  }
})
console.log('  ', apiSinRed)
if (apiSinRed.ok) {
  fallos.push('La API se está sirviendo desde la caché: un dato viejo se presentaría como actual')
}

console.log('· IndexedDB guarda una foto y sobrevive a la recarga')
await contexto.setOffline(false)
const guardado = await pagina.evaluate(async () => {
  const db = await new Promise((res, rej) => {
    const p = indexedDB.open('tdd-fotos', 1)
    p.onupgradeneeded = () => {
      const d = p.result
      if (!d.objectStoreNames.contains('pendientes')) {
        d.createObjectStore('pendientes', { keyPath: 'id' }).createIndex('projectId', 'projectId')
      }
    }
    p.onsuccess = () => res(p.result)
    p.onerror = () => rej(p.error)
  })
  await new Promise((res, rej) => {
    const tx = db.transaction('pendientes', 'readwrite')
    tx.objectStore('pendientes').put({
      id: 'e1',
      projectId: 'p1',
      bytes: new Uint8Array([9, 8, 7]).buffer,
      nombre: 'IMG_0001.jpg',
      tipo: 'image/jpeg',
      modificado: 0,
      origen: 'CAMARA',
      estado: 'PENDIENTE',
      intentos: 0,
      encolada: 1,
    })
    tx.oncomplete = () => res()
    tx.onerror = () => rej(tx.error)
  })
  db.close()
  return true
})
await pagina.reload({ waitUntil: 'domcontentloaded' })
const recuperado = await pagina.evaluate(async () => {
  const db = await new Promise((res, rej) => {
    const p = indexedDB.open('tdd-fotos', 1)
    p.onsuccess = () => res(p.result)
    p.onerror = () => rej(p.error)
  })
  const filas = await new Promise((res, rej) => {
    const tx = db.transaction('pendientes', 'readonly')
    const q = tx.objectStore('pendientes').index('projectId').getAll('p1')
    tx.oncomplete = () => res(q.result)
    tx.onerror = () => rej(tx.error)
  })
  db.close()
  return filas.map((f) => ({ id: f.id, bytes: [...new Uint8Array(f.bytes)], nombre: f.nombre }))
})
console.log('  ', recuperado)
if (guardado && recuperado.length !== 1) {
  fallos.push('La foto encolada no sobrevive a la recarga')
} else if (recuperado[0] && recuperado[0].bytes.join() !== '9,8,7') {
  fallos.push('Los bytes de la foto no sobreviven intactos')
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log('El armazón abre sin red y la cola sobrevive a la recarga.')

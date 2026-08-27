/** La vista de campo, en el motor y el tamaño de un teléfono.
 *
 *  Es la comprobación que faltaba. Todo lo demás se ha comprobado en Chromium
 *  a 1280×900, y **el uso real de esta aplicación es un consultor en una nave,
 *  con una mano, con un teléfono**.
 *
 *      # iPhone: el motor es WebKit
 *      TDD_NAVEGADOR=webkit TDD_DISPOSITIVO="iPhone 14" \
 *        TDD_PROYECTO=<uuid> node herramientas/comprobar-safari.mjs
 *
 *      # Android: el motor es Blink, y lo que cambia es el ANCHO
 *      TDD_DISPOSITIVO="Galaxy S9+" \
 *        TDD_PROYECTO=<uuid> node herramientas/comprobar-safari.mjs
 *
 *  Los dos ejes son independientes y hay que recorrerlos los dos. Un iPhone 14
 *  mide 390 puntos; un Android de gama media, 360, y uno estrecho, 320. Una
 *  tabla que cabe a 390 puede desbordarse a 320, y eso no lo dice el motor.
 *
 *  `[LIM]` WebKit de Playwright **no es Safari de iOS**. Lo que aquí no se
 *  puede comprobar y sigue sin comprobarse en ningún sitio: la cámara, un HEIC
 *  de verdad, el desalojo de IndexedDB a los siete días sin abrir la
 *  aplicación, la presión de memoria que hace que Safari recargue la pestaña, y
 *  «Añadir a pantalla de inicio». Eso pide un teléfono.
 */
import { abrir } from './navegador.mjs'

const BASE = process.env.TDD_WEB ?? 'http://localhost:4173'
const CORREO = process.env.TDD_EMAIL ?? 'admin@ejemplo.example'
const CLAVE = process.env.TDD_PASSWORD ?? 'cubierta invertida 2026'
const PID = process.env.TDD_PROYECTO

if (!PID) {
  console.error('Falta TDD_PROYECTO')
  process.exit(1)
}

const fallos = []
const comprobar = (ok, que) => {
  if (!ok) fallos.push(que)
  console.log(`${ok ? '  ok' : '  FALLA'}  ${que}`)
}

const { navegador, contexto, motorUsado, dispositivo } = await abrir()
console.log(`Motor: ${motorUsado} · Dispositivo: ${dispositivo}`)
if (motorUsado !== 'webkit') {
  console.log('  ! No es WebKit: esto comprueba la maquetación, no el motor de Safari.')
}

const pg = await contexto.newPage()
const errores = []
pg.on('pageerror', (e) => errores.push(e.message))

// ── 1 · La pantalla de acceso cabe en el alto del teléfono ─────────────────
//
// Se mide ANTES de entrar, y no después: con la sesión abierta `/entrar`
// redirige a la lista de encargos, así que volver aquí más tarde no mide la
// pantalla de acceso, mide otra cosa. La primera versión de esta comprobación
// entraba dos veces y se colgaba esperando un campo que ya no estaba.
//
// `min-height: 100vh` en Safari de iOS mide la pantalla CON la barra de
// direcciones retraída, así que el formulario centrado se va por debajo del
// borde visible y la página aparece con scroll sin motivo. `100dvh` mide lo
// que de verdad se ve.
await pg.goto(`${BASE}/entrar`)
const desbordeVertical = await pg.evaluate(
  () => document.documentElement.scrollHeight > window.innerHeight + 2,
)
comprobar(!desbordeVertical, 'la pantalla de acceso cabe sin scroll en el alto del teléfono')

// ── 2 · Se puede entrar con una mano ────────────────────────────────────────
await pg.fill('input[type="email"]', CORREO)
await pg.fill('input[type="password"]', CLAVE)
await pg.click('button[type="submit"]')
await pg.waitForURL('**/proyectos', { timeout: 20000 })
comprobar(true, 'se inicia sesión desde el teléfono')

// ── 3 · Nada se sale por los lados ──────────────────────────────────────────
// El ancho real, no uno escrito a mano: esta comprobación corre en teléfonos de
// 320, 360 y 390 puntos, y un mensaje que miente sobre cuál se estaba midiendo
// es peor que no dar el dato.
const ancho = await pg.evaluate(() => window.innerWidth)
for (const [nombre, ruta] of [
  ['proyectos', '/proyectos'],
  ['fotografías', `/proyectos/${PID}/fotos`],
  ['hallazgos y CAPEX', `/proyectos/${PID}/capex`],
  ['inventario', `/proyectos/${PID}/equipo`],
]) {
  await pg.goto(`${BASE}${ruta}`)
  await pg.waitForTimeout(1500)
  const desborda = await pg.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  )
  comprobar(!desborda, `«${nombre}» no se sale por los lados a ${ancho} px`)
}

// ── 4 · Los controles se pueden pulsar con el pulgar ────────────────────────
// 44×44 puntos es el mínimo que pide la guía de interfaz de Apple, y no es
// cosmético: por debajo de eso se falla el objetivo con el dedo y en una nave,
// con guantes, mucho más.
await pg.goto(`${BASE}/proyectos/${PID}/fotos`)
await pg.waitForTimeout(2000)
const pequenos = await pg.evaluate(() => {
  const chicos = []
  for (const el of document.querySelectorAll('button, a[href], input[type="checkbox"], select')) {
    const r = el.getBoundingClientRect()
    if (r.width === 0 || r.height === 0) continue // oculto: no cuenta
    if (r.height < 32 || r.width < 32) {
      chicos.push(`${el.tagName.toLowerCase()}«${(el.textContent || '').trim().slice(0, 24)}»`)
    }
  }
  return chicos
})
comprobar(
  pequenos.length === 0,
  `todos los controles llegan a 32 px (${pequenos.length} pequeños: ${pequenos.slice(0, 4).join(', ')})`,
)

// ── 5 · El texto no se lee con lupa ─────────────────────────────────────────
// Y además: Safari de iOS **hace zoom solo** al enfocar un campo cuyo texto
// mida menos de 16 px, y luego no lo deshace. La página se queda ampliada y hay
// que pellizcar para volver, en cada campo del formulario.
const camposChicos = await pg.evaluate(() => {
  const chicos = []
  for (const el of document.querySelectorAll('input, select, textarea')) {
    const px = parseFloat(getComputedStyle(el).fontSize)
    if (px < 16) chicos.push(`${el.tagName.toLowerCase()}[${el.type || ''}]=${px}px`)
  }
  return [...new Set(chicos)]
})
comprobar(
  camposChicos.length === 0,
  `ningún campo baja de 16 px, que es lo que dispara el zoom automático (${camposChicos.slice(0, 3).join(', ')})`,
)

// ── 6 · La cola de subida sobrevive sin red ─────────────────────────────────
// Es lo que sostiene el trabajo en una nave sin cobertura: si IndexedDB no
// funciona en este motor, las fotos de una visita se pierden al cerrar.
const almacenamiento = await pg.evaluate(async () => {
  try {
    const abierta = await new Promise((res, rej) => {
      const p = indexedDB.open('tdd-comprobacion-safari', 1)
      p.onupgradeneeded = () => p.result.createObjectStore('x')
      p.onsuccess = () => res(p.result)
      p.onerror = () => rej(p.error)
    })
    // Se guarda un ArrayBuffer, que es exactamente lo que guarda la cola: el
    // `File` no se serializa a propósito porque Safari ha tenido fallos con
    // blobs en IndexedDB durante años.
    await new Promise((res, rej) => {
      const tx = abierta.transaction('x', 'readwrite')
      tx.objectStore('x').put(new Uint8Array([1, 2, 3]).buffer, 'k')
      tx.oncomplete = res
      tx.onerror = () => rej(tx.error)
    })
    const leido = await new Promise((res, rej) => {
      const tx = abierta.transaction('x', 'readonly')
      const p = tx.objectStore('x').get('k')
      p.onsuccess = () => res(p.result)
      p.onerror = () => rej(p.error)
    })
    abierta.close()
    indexedDB.deleteDatabase('tdd-comprobacion-safari')
    return { ok: leido && leido.byteLength === 3, persistencia: typeof navigator.storage?.persist }
  } catch (e) {
    return { ok: false, error: String(e) }
  }
})
comprobar(almacenamiento.ok, `IndexedDB guarda y devuelve bytes (${almacenamiento.error ?? 'ok'})`)

// ── 7 · Sin errores de página ───────────────────────────────────────────────
comprobar(errores.length === 0, `sin errores de página (${errores.slice(0, 2).join(' · ')})`)

await navegador.close()

if (fallos.length) {
  console.error(`\n${fallos.length} comprobaciones fallan en ${motorUsado}/${dispositivo}`)
  process.exit(1)
}
console.log(`\nTodo correcto en ${motorUsado}/${dispositivo}.`)

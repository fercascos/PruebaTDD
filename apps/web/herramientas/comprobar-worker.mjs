/** Generar un informe con el worker de por medio, en un navegador de verdad.
 *
 *  Las pruebas de la API ya cubren la cola y el manejador. Lo que **solo** se
 *  ve aquí es lo que le pasa a la persona que pulsa el botón:
 *
 *   1. Que la pantalla no se queda colgada: el botón vuelve enseguida y
 *      aparece una versión en GENERANDO. Es la promesa de §17.
 *   2. Que **no se le ofrece descargar algo que todavía no existe**. Un botón
 *      PPTX sobre una versión en curso daría un 404 y parecería un fallo
 *      cuando lo único que pasa es que aún se está generando.
 *   3. Que la fila se actualiza **sola**, sin recargar la página.
 *
 *  Necesita el worker en marcha (`python -m tdd.cola --cola heavy`).
 */
import { chromium } from 'playwright'

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

const nav = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH })
const pg = await nav.newPage()
const errores = []
pg.on('pageerror', (e) => errores.push(e.message))

await pg.goto(`${BASE}/entrar`)
await pg.fill('input[type="email"]', CORREO)
await pg.fill('input[type="password"]', CLAVE)
await pg.click('button[type="submit"]')
await pg.waitForURL('**/proyectos', { timeout: 15000 })

await pg.goto(`${BASE}/proyectos/${PID}/informes`)
await pg.waitForSelector('button:has-text("Comprobar antes de generar")', { timeout: 20000 })

const versionesAntes = await pg.locator('.tabla tbody tr').count()

await pg.click('button:has-text("Comprobar antes de generar")')
await pg.waitForSelector('button:has-text("Generar informe")', { timeout: 20000 })

// ── 1 · La pantalla no se queda colgada ─────────────────────────────────────
const arranque = Date.now()
await pg.click('button:has-text("Generar informe")')
await pg
  .locator('.tabla tbody tr')
  .nth(versionesAntes)
  .waitFor({ state: 'visible', timeout: 20000 })
const tardanza = Date.now() - arranque
comprobar(tardanza < 3000, `la petición vuelve en menos de 3 s (${tardanza} ms) · §17`)

const fila = pg.locator('.tabla tbody tr').filter({ hasText: 'GENERANDO' }).first()

// ── 2 · No se ofrece descargar lo que no existe ─────────────────────────────
if ((await fila.count()) > 0) {
  comprobar(
    (await fila.locator('button:has-text("PPTX")').count()) === 0,
    'mientras genera no se ofrece descargar el PPTX',
  )
  comprobar(
    (await fila.locator('.generando').count()) === 1,
    'la fila dice que se está generando y que se actualiza sola',
  )
} else {
  // El worker fue más rápido que el navegador. No es un fallo, pero conviene
  // que se lea en la salida en vez de dar por probado algo que no se vio.
  comprobar(true, 'el worker terminó antes de poder mirar el estado intermedio')
}

// ── 3 · Se actualiza sola ───────────────────────────────────────────────────
await pg
  .locator('.tabla tbody tr')
  .nth(versionesAntes)
  .locator('button:has-text("PPTX")')
  .waitFor({ state: 'visible', timeout: 60000 })
comprobar(true, 'la fila pasa a GENERADO sola, sin recargar la página')

comprobar(
  (await pg.locator('.tabla tbody tr').filter({ hasText: 'ERROR' }).count()) === 0,
  'ninguna versión quedó en ERROR',
)

comprobar(errores.length === 0, `sin errores de página (${errores.slice(0, 2).join(' · ')})`)
await nav.close()

if (fallos.length) {
  console.error(`\n${fallos.length} comprobaciones fallan`)
  process.exit(1)
}
console.log('\nTodo correcto.')

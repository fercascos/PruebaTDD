/** Comprueba en un navegador de verdad las tres garantías del módulo de
 *  revisión documental con IA.
 *
 *  Las pruebas de la API ya cubren la base y el servicio. Lo que **solo** se ve
 *  aquí es lo que ve una persona:
 *
 *   1. Que sin autorizar no aparece ningún botón de revisar. Un requisito que
 *      solo vive en el backend no protege de una interfaz que ofrece el botón
 *      igualmente y luego enseña un 403.
 *   2. Que el aviso de «revisión simulada» está donde no se puede ignorar.
 *      Si el usuario no lo ve, la simulación se convierte en un engaño.
 *   3. Que aceptar una propuesta exige pulsar, y que después ya no se puede
 *      volver a decidir. */
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

await pg.goto(`${BASE}/proyectos/${PID}/documentacion`)
await pg.waitForSelector('.autorizacion-ia')

// ── 0 · Punto de partida conocido ───────────────────────────────────────────
// El encargo de pruebas sobrevive entre ejecuciones, así que la autorización
// puede venir encendida de la anterior. Se apaga antes de empezar: una
// comprobación que depende del estado que dejó la ejecución previa no prueba
// nada, y la primera versión de este fichero pasaba por casualidad.
if ((await pg.locator('.autorizacion-ia.activa').count()) > 0) {
  await pg.click('.autorizacion-ia button')
  await pg.waitForSelector('.autorizacion-ia.inactiva', { timeout: 15000 })
}

// ── 1 · Apagado de fábrica, y sin botón de revisar ──────────────────────────
const apagada = await pg.locator('.autorizacion-ia.inactiva').count()
comprobar(apagada === 1, 'la revisión con IA aparece apagada')
comprobar(
  (await pg.locator('.revisar-ia').count()) === 0,
  'apagada, no se ofrece ningún botón de revisar',
)

// ── 2 · Se añade una línea y un documento ───────────────────────────────────
const titulo = `Licencia de actividad ${Date.now()}`
await pg.fill('.nueva-linea input[aria-label="Documento solicitado"]', titulo)
await pg.click('.nueva-linea button[type="submit"]')
await pg.waitForSelector(`.checklist .linea:has-text("${titulo}")`)
comprobar(true, 'se puede añadir una línea a la checklist')

const linea = pg.locator(`.checklist .linea:has-text("${titulo}")`)
await linea.locator('input[type="file"]').setInputFiles({
  name: 'licencia.pdf',
  mimeType: 'application/pdf',
  buffer: Buffer.from(`%PDF-1.7\n% ${Date.now()}\ntrailer\n%%EOF\n`),
})
await pg.waitForSelector(`.checklist .linea:has-text("${titulo}") .documento`, { timeout: 15000 })
comprobar(true, 'el documento se adjunta a su línea')

// ── 3 · Se autoriza, y entonces sí aparece el botón ─────────────────────────
await pg.click('.autorizacion-ia button')
await pg.waitForSelector('.autorizacion-ia.activa')
comprobar(true, 'autorizar cambia el estado a la vista')

const revisar = linea.locator('.revisar-ia')
await revisar.waitFor({ state: 'visible', timeout: 15000 })
comprobar(true, 'autorizada, aparece el botón de revisar')

await revisar.scrollIntoViewIfNeeded()
await revisar.click({ timeout: 15000 })
// Se espera a las observaciones DE ESTA LÍNEA, no a las de cualquiera: con un
// `waitForSelector` global la cuenta se tomaba antes de que se pintara esta
// revisión y salía cero.
await linea.locator('.observacion').first().waitFor({ state: 'visible', timeout: 20000 })

// ── 4 · El aviso de simulación tiene que verse ──────────────────────────────
const aviso = await linea.locator('.revision [class*="aviso"]').first().innerText()
comprobar(/simulada/i.test(aviso), 'el aviso dice en claro que la revisión es simulada')
comprobar(
  /nadie ha leído/i.test(aviso),
  'el aviso dice que nadie ha leído el documento',
)

// ── 5 · La IA propone; decide una persona ───────────────────────────────────
// Acotado a la línea recién creada: contar en toda la página dejaría que la
// prueba pasara con observaciones de una ejecución anterior.
const propuestas = await linea.locator('.observacion.d-propuesta').count()
comprobar(
  propuestas === (await linea.locator('.observacion').count()),
  `todas las observaciones de esta línea nacen como propuesta (${propuestas})`,
)
comprobar(propuestas > 0, `hay observaciones que decidir (${propuestas})`)

await linea.locator('.observacion.d-propuesta').first().locator('button:has-text("Aceptar")').click()
await linea.locator('.observacion.d-aceptada').first().waitFor({ timeout: 15000 })
comprobar(true, 'aceptar una propuesta la marca como decidida por una persona')

comprobar(
  (await linea.locator('.observacion.d-aceptada button:has-text("Aceptar")').count()) === 0,
  'una vez decidida, ya no se ofrece decidir otra vez',
)
comprobar(
  (await linea.locator('.observacion.d-propuesta').count()) === propuestas - 1,
  'solo se decide la que se pulsa: las demás siguen siendo propuestas',
)

// ── 6 · Contraste de las etiquetas de veredicto ─────────────────────────────
// Salió blanco sobre blanco en «Dudoso» la primera vez que se miró la pantalla
// de verdad: la cabecera es oscura y la etiqueta no traía color propio.
const ilegibles = await pg.locator('.observacion .veredicto').evaluateAll((nodos) =>
  nodos
    .map((n) => {
      const e = getComputedStyle(n)
      return { texto: n.textContent, color: e.color, fondo: e.backgroundColor }
    })
    .filter((v) => v.color === v.fondo || v.color === 'rgb(255, 255, 255)'),
)
comprobar(
  ilegibles.length === 0,
  `ninguna etiqueta de veredicto queda ilegible (${ilegibles.map((v) => v.texto).join(', ')})`,
)

comprobar(errores.length === 0, `sin errores de página (${errores.slice(0, 2).join(' · ')})`)
await nav.close()

if (fallos.length) {
  console.error(`\n${fallos.length} comprobaciones fallan`)
  process.exit(1)
}
console.log('\nTodo correcto.')

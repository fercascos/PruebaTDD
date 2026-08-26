/** El árbol de ubicaciones en un navegador de verdad, hasta el nombre del fichero.
 *
 *  Las pruebas de la API ya cubren el árbol, los ciclos y el movimiento de
 *  ramas. Lo que **solo** se ve aquí es la cadena completa que da sentido a la
 *  tabla:
 *
 *    crear la sala → clasificar la foto en ella → que `[Espacio]` aparezca en
 *    el nombre propuesto al renombrar en lote.
 *
 *  Si cualquier eslabón se rompe, el token vuelve a omitirse en silencio y el
 *  nombre sale plausible pero con un campo menos. Es exactamente el fallo que
 *  tuvo `[Sistema]` durante meses.
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
const pg = await nav.newPage({ viewport: { width: 1280, height: 900 } })
const errores = []
pg.on('pageerror', (e) => errores.push(e.message))

await pg.goto(`${BASE}/entrar`)
await pg.fill('input[type="email"]', CORREO)
await pg.fill('input[type="password"]', CLAVE)
await pg.click('button[type="submit"]')
await pg.waitForURL('**/proyectos', { timeout: 15000 })

// ── 1 · Se abre la ficha del activo y aparece el árbol ──────────────────────
await pg.goto(`${BASE}/proyectos/${PID}/activos`)
await pg.waitForSelector('.tabla tbody tr, .vacio', { timeout: 20000 })
await pg.locator('.tabla tbody tr button').first().click()
await pg.waitForSelector('.ubicaciones', { timeout: 15000 })
comprobar(true, 'la ficha del activo lleva el árbol de ubicaciones')

// La ficha tiene que ENSEÑAR lo que la API guarda. Cinco superficies
// arrancaban en blanco aunque el activo las tuviera, y con el año de reforma
// eso llegaba a borrarlo: `guardar()` manda `null` cuando el campo está vacío,
// así que abrir y pulsar Guardar perdía el dato en silencio.
const rellenos = await pg.locator('input[type="number"]').evaluateAll((inputs) =>
  inputs.filter((i) => i.value.trim() !== '').length,
)
comprobar(
  rellenos >= 4,
  `la ficha carga las superficies que la API guarda (${rellenos} campos con valor)`,
)

// ── 2 · Se crean una planta y una sala dentro ──────────────────────────────
const sufijo = Date.now().toString().slice(-6)
const planta = `Planta ${sufijo}`
const sala = `Sala Maquinas ${sufijo}`

await pg.selectOption('.nueva-ubicacion select:first-of-type', 'PLANTA')
await pg.fill('.nueva-ubicacion input', planta)
await pg.click('.nueva-ubicacion button[type="submit"]')
await pg.waitForSelector(`.arbol li:has-text("${planta}")`, { timeout: 15000 })

await pg.selectOption('.nueva-ubicacion select:first-of-type', 'ESPACIO')
await pg.selectOption('.nueva-ubicacion select[aria-label="Dentro de"]', { label: planta })
await pg.fill('.nueva-ubicacion input', sala)
await pg.click('.nueva-ubicacion button[type="submit"]')
await pg.waitForSelector(`.arbol li:has-text("${sala}")`, { timeout: 15000 })
comprobar(true, 'se crean una planta y una sala dentro de ella')

// Las filas se localizan por su `<strong>`, no por el texto de la fila: cada
// una lleva un `<select>` cuyas opciones entran en el `innerText`, así que
// buscar por texto encontraba la fila equivocada y acusaba a la aplicación de
// un fallo que no tenía.
const filaDe = (nombre) => pg.locator(`.arbol li:has(strong:text-is("${nombre}"))`)
const sangriaDe = async (nombre) =>
  filaDe(nombre).evaluate((n) => parseFloat(getComputedStyle(n).paddingLeft))

// La sangría es lo que hace legible el árbol: la sala va más adentro.
comprobar(
  (await sangriaDe(sala)) > (await sangriaDe(planta)),
  'la sala se pinta sangrada respecto de su planta',
)

// Un nodo no puede ofrecerse como su propio padre: sería ofrecer un error.
const opcionesDeLaPlanta = await filaDe(planta).locator('select option').allInnerTexts()
comprobar(
  !opcionesDeLaPlanta.some((o) => o.includes(sala)),
  'no se ofrece meter una planta dentro de su propia sala',
)

// ── 3 · La foto se clasifica en esa sala ────────────────────────────────────
await pg.goto(`${BASE}/proyectos/${PID}/fotos`)
await pg.waitForSelector('.rejilla img, .vacio', { timeout: 25000 })
const hayFotos = await pg.locator('.rejilla img').count()
if (hayFotos === 0) {
  console.error('El encargo de pruebas no tiene fotografías. Suba una antes.')
  process.exit(1)
}
await pg.locator('.rejilla .miniatura').first().click()
await pg.waitForSelector('select', { timeout: 15000 })

const selectorDeEspacio = pg.locator('label:has-text("Espacio") select')
comprobar((await selectorDeEspacio.count()) === 1, 'el detalle de la foto ofrece elegir espacio')
// El árbol se pide al abrir la ficha: hay que esperar a que llegue. Sin esto
// la comprobación de abajo miraba un desplegable con la única opción vacía y
// acusaba a la aplicación de un fallo que era de la prueba.
await selectorDeEspacio
  .locator('option')
  .nth(1)
  .waitFor({ state: 'attached', timeout: 15000 })
// Se selecciona por VALOR, no por etiqueta: el texto de cada opción lleva
// los espacios duros de la sangría, así que una coincidencia exacta por
// etiqueta no encaja y `selectOption` no admite expresiones regulares ahí.
const valorDeLaSala = await selectorDeEspacio.evaluate(
  (sel, nombre) =>
    Array.from(sel.options).find((o) => o.textContent.includes(nombre))?.value ?? '',
  sala,
)
comprobar(valorDeLaSala !== '', 'la sala recién creada aparece en el desplegable de la foto')
await selectorDeEspacio.selectOption(valorDeLaSala)
await pg.locator('button:has-text("Guardar")').first().click()
await pg.waitForTimeout(2000)
comprobar(true, 'la foto se guarda con su ubicación')

// ── 4 · Y `[Espacio]` aparece en el nombre propuesto ────────────────────────
await pg.waitForSelector('.rejilla .miniatura', { timeout: 20000 })
await pg.locator('.rejilla li input[type="checkbox"]').first().check()
await pg.locator('button:has-text("Renombrar en lote")').first().click()
await pg.waitForSelector('.dialogo', { timeout: 20000 })

await pg.locator('.dialogo label:has-text("Plantilla") input').fill('[Activo]_[Espacio]_[Numero]')
// La previsualización es un botón explícito y no automática: el renombrado en
// lote es la operación con más capacidad de destrozo del bloque, y calcular el
// plan solo al pedirlo es deliberado.
await pg.locator('.dialogo button:has-text("Previsualizar")').click()
await pg.waitForSelector('.dialogo table tbody tr', { timeout: 20000 })

const propuesto = await pg.locator('.dialogo table tbody tr').first().innerText()
const esperado = `SalaMaquinas${sufijo}`
comprobar(
  propuesto.includes(esperado),
  `el token [Espacio] llega al nombre propuesto (${esperado} en «${propuesto.replace(/\s+/g, ' ').slice(0, 90)}»)`,
)

comprobar(errores.length === 0, `sin errores de página (${errores.slice(0, 2).join(' · ')})`)
await nav.close()

if (fallos.length) {
  console.error(`\n${fallos.length} comprobaciones fallan`)
  process.exit(1)
}
console.log('\nTodo correcto.')

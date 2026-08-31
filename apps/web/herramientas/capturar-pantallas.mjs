/** Captura las pantallas de un encargo de DEMOSTRACIÓN, para enseñar la
 *  aplicación sin tener que montarla.
 *
 *  No es una comprobación: no afirma nada y no falla si algo está mal. Para eso
 *  están las `comprobar-*.mjs` de esta misma carpeta.
 *
 *  `[REQ]` Apúntelo **solo** a una base de datos de demostración con datos
 *  ficticios. Genera un informe de verdad en el encargo indicado, así que
 *  ejecutarlo contra datos reales de un cliente crearía una versión que no
 *  pidió nadie.
 *
 *      TDD_PROYECTO=<uuid> node apps/web/herramientas/_capturar.mjs
 */
import { chromium } from 'playwright'
const BASE = process.env.TDD_WEB ?? 'http://localhost:4173'
const CORREO = process.env.TDD_EMAIL ?? 'admin@ejemplo.example'
const CLAVE = process.env.TDD_PASSWORD ?? 'cubierta invertida 2026'
const PID = process.env.TDD_PROYECTO
const SALIDA = process.env.TDD_CAPTURAS ?? '/tmp/capturas'

if (!PID) {
  console.error('Falta TDD_PROYECTO: el identificador del encargo de demostración.')
  process.exit(1)
}

const nav = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH })
const ctx = await nav.newContext({ viewport:{width:1440,height:900}, deviceScaleFactor:1 })
const pg = await ctx.newPage()
const errores = []
pg.on('pageerror', e => errores.push(e.message))

async function foto(nombre, opciones={}) {
  await pg.waitForTimeout(opciones.espera ?? 350)
  await pg.screenshot({ path:`${SALIDA}/${nombre}.png`, fullPage: opciones.completa ?? false })
  console.log('·', nombre)
}

// 1 · Entrar
await pg.goto(`${BASE}/entrar`)
await foto('01-entrar')

// 2 · Recuperar
await pg.click('a:has-text("He olvidado mi contraseña")')
await pg.waitForURL('**/recuperar')
await foto('02-recuperar')

await pg.goto(`${BASE}/entrar`)
await pg.fill('input[type="email"]', CORREO)
await pg.fill('input[type="password"]', CLAVE)
await pg.click('button[type="submit"]')
await pg.waitForURL('**/proyectos',{timeout:15000})
await foto('03-proyectos')

const pantallas = [
  ['04-fases', ``, '.pestanas'],
  ['05-activos', `/activos`, '.tabla, .vacio'],
  ['05b-documentacion', `/documentacion`, '.autorizacion-ia'],
  ['06-fotos', `/fotos`, '.rejilla li'],
  ['07-mapa', `/mapa`, '.leaflet-container'],
  ['08-inventario', `/equipo`, '.tabla.inventario'],
  ['09-capex', `/capex`, '.tabla.capex'],
  ['10-riesgos', `/riesgos`, '.tabla.matriz'],
  ['11-informes', `/informes`, 'button, .vacio'],
]
for (const [nombre, sufijo, espera] of pantallas) {
  await pg.goto(`${BASE}/proyectos/${PID}${sufijo}`)
  try { await pg.waitForSelector(espera, { timeout: 12000 }) } catch { /* se captura igual */ }
  await foto(nombre, { completa: true, espera: 900 })
}

// 11b · El árbol de ubicaciones, dentro de la ficha del activo (§8.4)
// Se abre el activo que TIENE árbol, no «el primero de la tabla»: el encargo de
// demostración es de cartera y la tabla ordena por nombre, así que el primero
// puede ser el que no tiene ubicaciones y la lámina saldría vacía.
// El nombre sale de `tools/sembrar_demo.py`, que es quien crea las ubicaciones;
// esta herramienta ya es solo para la base de demostración, así que el
// acoplamiento es el que hay. Si el nombre cambia, se cae al primer activo y la
// captura sale igual, quizá con el árbol vacío.
await pg.goto(`${BASE}/proyectos/${PID}/activos`)
await pg.waitForSelector('.tabla tbody tr')
const conArbol = pg.locator('.tabla tbody tr', { hasText: 'Nave A' })
await ((await conArbol.count()) ? conArbol : pg.locator('.tabla tbody tr'))
  .locator('button')
  .first()
  .click()
await pg.waitForSelector('.ubicaciones')
await foto('11b-ubicaciones', { completa:true, espera:600 })

// 12 · Ficha de hallazgo con el comparador abierto
await pg.goto(`${BASE}/proyectos/${PID}/capex`)
await pg.waitForSelector('.tabla.capex')
// `:not(.cabecera-grupo)` porque en un encargo de cartera la tabla va separada
// por activo, y la fila de cabecera de cada grupo lleva su propio
// `button.enlace` —«Exportar este activo»—: sin excluirla se pulsaba ése y la
// ficha del hallazgo no llegaba a abrirse.
await pg.locator('.tabla.capex tbody tr:not(.cabecera-grupo) button.enlace').first().click()
await pg.waitForSelector('.linea-capex')
await foto('12-ficha-hallazgo', { completa:true })
await pg.click('button:has-text("Ver referencias y validar el precio")')
await pg.waitForSelector('.comparador')
await pg.locator('.comparador').screenshot({ path:`${SALIDA}/13-comparador.png` })
console.log('· 13-comparador')

// 14 · Importar inventario
await pg.goto(`${BASE}/proyectos/${PID}/equipo`)
await pg.waitForSelector('.tabla.inventario')
await pg.click('button:has-text("Importar desde Excel")')
await pg.waitForSelector('.importar')
await foto('14-importar', { completa:true })

// 15 · Plantillas y sugerencias
for (const [n, ruta] of [['15-plantillas','/plantillas'],['16-sugerencias','/sugerencias'],['17-personas','/personas']]) {
  await pg.goto(BASE+ruta)
  await pg.waitForTimeout(900)
  await foto(n, { completa:true })
}

// 19 · La comprobación previa del informe, que es lo que decide si se genera
await pg.goto(`${BASE}/proyectos/${PID}/informes`)
await pg.waitForSelector('button:has-text("Comprobar antes de generar")')
await pg.click('button:has-text("Comprobar antes de generar")')
await pg.waitForSelector('.previo')
await foto('19-previo-del-informe', { completa:true, espera:600 })

// 20 · Y el informe ya generado, con sus avisos congelados en la versión
await pg.click('button:has-text("Generar informe")')
await pg.waitForSelector('table.tabla tbody tr', { timeout: 30000 })
await foto('20-informe-generado', { completa:true, espera:900 })

// 18 · Móvil: la pestaña de fotos, que es la que se usa en campo
const movil = await nav.newContext({ viewport:{width:390,height:844}, isMobile:true, hasTouch:true })
const pm = await movil.newPage()
await pm.goto(`${BASE}/entrar`)
await pm.fill('input[type="email"]', CORREO)
await pm.fill('input[type="password"]', CLAVE)
await pm.click('button[type="submit"]')
await pm.waitForURL('**/proyectos',{timeout:15000})
await pm.goto(`${BASE}/proyectos/${PID}/fotos`)
await pm.waitForTimeout(1500)
await pm.screenshot({ path:`${SALIDA}/18-movil-fotos.png`, fullPage:true })
console.log('· 18-movil-fotos')

await nav.close()
if (errores.length) console.log('ERRORES EN PÁGINA:', errores.slice(0,5))

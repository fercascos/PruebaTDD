/** Ninguna pantalla puede desbordar horizontalmente en un móvil.
 *
 *  El `body` con barra de desplazamiento lateral no es un defecto cosmético:
 *  deja inservible el resto de la pantalla, porque el contenido se va hacia la
 *  derecha y hay que arrastrar para leer cada línea. En campo la aplicación se
 *  usa en un móvil, y 320 px es el ancho de un iPhone SE, que sigue vivo.
 *
 *  Lo que se mide **no** es que nada sobresalga: una tabla de doce columnas
 *  sobresale a propósito y se desplaza ella sola dentro de `.desbordable`. Lo
 *  que se mide es que no lo haga **la página**, y para cada desbordamiento se
 *  nombra el elemento culpable: el que sobresale sin que ningún antepasado
 *  suyo esté ya recortando. Sin esa distinción, el aviso señala a la tabla y no
 *  al `<select>` que la empuja, y se arregla lo que no era.
 *
 *  Uso:
 *    TDD_PROYECTO=<id> node herramientas/comprobar-ancho.mjs
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

/** 320 es el suelo real (iPhone SE); 360 es el Android más común. */
const ANCHOS = [320, 360]

/** Las rutas REALES, no las etiquetas de las pestañas: la de Inventario apunta
 *  a `equipo` y la de Fotografías a `fotos`. Escribirlas por su etiqueta manda
 *  al comodín del enrutador, que redirige a `/proyectos`, y la comprobación
 *  mide dos veces la misma pantalla y pasa sin haber visitado nada. */
const PANTALLAS = [
  ['proyectos', '/proyectos'],
  ['plantillas', '/plantillas'],
  ['personas', '/personas'],
  ['sugerencias', '/sugerencias'],
  ['fases', `/proyectos/${PID}`],
  ['documentacion', `/proyectos/${PID}/documentacion`],
  ['activos', `/proyectos/${PID}/activos`],
  ['fotos', `/proyectos/${PID}/fotos`],
  ['mapa', `/proyectos/${PID}/mapa`],
  ['equipo', `/proyectos/${PID}/equipo`],
  ['capex', `/proyectos/${PID}/capex`],
  ['riesgos', `/proyectos/${PID}/riesgos`],
  ['informes', `/proyectos/${PID}/informes`],
]

const fallos = []
const comprobar = (ok, que) => {
  if (!ok) fallos.push(que)
  console.log(`${ok ? '  ok' : '  FALLA'}  ${que}`)
}

/** Cuánto desborda la página, y quién lo provoca de verdad. */
function medir() {
  const doc = document.documentElement
  const ancho = doc.clientWidth
  const culpables = []
  for (const e of document.querySelectorAll('body *')) {
    const caja = e.getBoundingClientRect()
    if (caja.right <= ancho + 0.5) continue
    // Si un antepasado ya recorta o desplaza, este elemento no empuja la
    // página: sobresale DENTRO de su contenedor, que es lo que se quiere.
    let recortado = false
    for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
      const ov = getComputedStyle(p).overflowX
      if (ov === 'auto' || ov === 'scroll' || ov === 'hidden') {
        recortado = true
        break
      }
    }
    if (recortado) continue
    const clases = String(e.className || '').trim().split(/\s+/).filter(Boolean).join('.')
    culpables.push(`${e.tagName.toLowerCase()}${clases ? '.' + clases : ''}`)
  }
  return { sobra: doc.scrollWidth - ancho, culpables: [...new Set(culpables)].slice(0, 4) }
}

const nav = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH })

for (const ancho of ANCHOS) {
  console.log(`\n${ancho} px`)
  const pg = await nav.newPage({
    viewport: { width: ancho, height: 780 },
    isMobile: true,
    hasTouch: true,
  })
  await pg.goto(`${BASE}/entrar`)
  await pg.fill('input[type="email"]', CORREO)
  await pg.fill('input[type="password"]', CLAVE)
  await pg.click('button[type="submit"]')
  await pg.waitForURL('**/proyectos', { timeout: 15000 })

  for (const [nombre, ruta] of PANTALLAS) {
    await pg.goto(`${BASE}${ruta}`)
    await pg.waitForTimeout(700)

    // Que se haya llegado a la pantalla, antes de medirla. El enrutador manda
    // lo que no reconoce a `/proyectos`, así que una ruta mal escrita mediría
    // la lista de encargos y pasaría sin haber visitado nada. Es exactamente lo
    // que dejó pasar este defecto durante semanas.
    const llegada = new URL(pg.url()).pathname
    if (llegada !== ruta) {
      comprobar(false, `${nombre}: la ruta ${ruta} redirige a ${llegada}`)
      continue
    }

    const { sobra, culpables } = await pg.evaluate(medir)
    comprobar(
      sobra <= 0,
      sobra <= 0
        ? `${nombre} cabe`
        : `${nombre} desborda ${sobra}px — ${culpables.join(', ') || 'sin culpable directo'}`,
    )

    // Un botón que cambia de texto cambia de ancho, y la pantalla puede caber
    // en un estado y no en el otro. El de la autorización de IA pasa de
    // «Autorizar» a «Retirar la autorización» y se salía 59 px a 320: no lo
    // enseñaba una pantalla recién sembrada, solo una ya autorizada. Se mide
    // el otro estado y se deja como estaba.
    if (nombre === 'documentacion') {
      const boton = pg.locator('.autorizacion-ia button')
      const antes = (await boton.textContent())?.trim()
      await boton.click()
      await pg.waitForTimeout(1500)
      const otro = await pg.evaluate(medir)
      const ahora = (await boton.textContent())?.trim()
      comprobar(
        otro.sobra <= 0,
        otro.sobra <= 0
          ? `documentacion cabe también con «${ahora}»`
          : `documentacion desborda ${otro.sobra}px con «${ahora}» — ${otro.culpables.join(', ')}`,
      )
      await boton.click() // se deja el encargo como estaba
      await pg.waitForTimeout(1200)
      if ((await boton.textContent())?.trim() !== antes) {
        comprobar(false, 'la autorización de IA no ha vuelto a su estado inicial')
      }
    }
  }
  await pg.close()
}

// ── Y en un escritorio, la cifra que se busca a la vista ────────────────────
// La otra mitad de «que quepa»: en un móvil vale con que la tabla se desplace
// ella, pero en un escritorio el TOTAL del CAPEX no puede exigir arrastrar. No
// se veía a ningún ancho —el contenido medía 1232 px contra los 1160 que deja
// `main`— y nadie lo notaba porque la tabla sí se desplazaba: el dato no se
// perdía, solo había que ir a buscarlo.
console.log('\n1280 px · escritorio')
const esc = await nav.newPage({ viewport: { width: 1280, height: 900 } })
await esc.goto(`${BASE}/entrar`)
await esc.fill('input[type="email"]', CORREO)
await esc.fill('input[type="password"]', CLAVE)
await esc.click('button[type="submit"]')
await esc.waitForURL('**/proyectos', { timeout: 15000 })
await esc.goto(`${BASE}/proyectos/${PID}/capex`)
await esc.waitForSelector('.tabla.capex tbody tr', { timeout: 20000 })

const totalDelCapex = await esc.evaluate(() => {
  const tabla = document.querySelector('.tabla.capex')
  const celda = [...tabla.querySelectorAll('tfoot td')].pop()
  if (!celda) return null
  return {
    dentro: celda.getBoundingClientRect().right <= tabla.getBoundingClientRect().right + 0.5,
    sobra: tabla.scrollWidth - tabla.clientWidth,
    texto: celda.textContent.trim(),
  }
})
comprobar(
  totalDelCapex !== null && totalDelCapex.dentro,
  totalDelCapex === null
    ? 'la tabla de CAPEX no tiene fila de totales'
    : totalDelCapex.dentro
      ? `el total del CAPEX se lee entero sin arrastrar (${totalDelCapex.texto})`
      : `el total del CAPEX queda fuera por ${totalDelCapex.sobra}px`,
)
await esc.close()

await nav.close()

if (fallos.length) {
  console.error(`\n${fallos.length} comprobaciones fallan`)
  process.exit(1)
}
console.log('\nTodo cabe.')

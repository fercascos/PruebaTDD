/**
 * ¿Dice el dashboard lo que tiene que decir? `[REQ]` §3.3 de `docs/23`.
 *
 * Cuatro cosas que no se ven en una prueba unitaria:
 *
 * 1. **Que los cinco cortes cuadren entre sí en la pantalla.** Cinco gráficos
 *    uno debajo de otro que no suman lo mismo destruyen la confianza en los
 *    cinco, y el descuadre lo encuentra el cliente con la calculadora.
 * 2. **Que el selector de varios activos filtre de verdad los cinco.** Es lo
 *    nuevo: si un corte se quedara sin filtrar, saldría más grande que los
 *    demás y nadie sabría cuál creer.
 * 3. **Que la barra apilada sume su categoría.** Los tramos son los objetos; si
 *    no dieran la barra, el gráfico mentiría en la misma pantalla que lo
 *    desmiente.
 * 4. **Que nada se identifique solo por color.** Los grados de riesgo con su
 *    código escrito, y los objetos de cada apilada listados en su tabla.
 *
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-dashboard.mjs
 */
import { chromium } from 'playwright'

const BASE = process.env.URL_BASE ?? 'http://localhost:4173'
const API = process.env.URL_API ?? 'http://localhost:8000/api/v1'
const CORREO = process.env.TDD_EMAIL ?? 'admin@ejemplo.example'
const CLAVE = process.env.TDD_PASSWORD ?? 'cubierta invertida 2026'

const fallos = []

async function api(metodo, ruta, cuerpo, token) {
  const r = await fetch(API + ruta, {
    method: metodo,
    headers: {
      ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  })
  const texto = await r.text()
  if (!r.ok) throw new Error(`${metodo} ${ruta} -> ${r.status}: ${texto.slice(0, 300)}`)
  return texto ? JSON.parse(texto) : null
}

/** Los euros de un texto de pantalla: «1.234.567 €» → 1234567. */
function importes(texto) {
  return [...texto.matchAll(/([\d.]+)(?:,\d+)?\s*€/g)].map((m) => Number(m[1].replace(/\./g, '')))
}

const { access_token: tk } = await api('POST', '/auth/login', {
  email: CORREO,
  password: CLAVE,
})
const cli = await api('POST', '/clients', { name: 'Inversora Ficticia S.L.' }, tk)
const proyecto = await api(
  'POST',
  '/projects',
  { client_id: cli.id, name: 'Cartera para el dashboard' },
  tk,
)
const tipologias = await api('GET', '/catalogs/asset-typologies', null, tk)
const riesgos = await api('GET', '/catalogs/risk-levels', null, tk)
const conceptos = await api('GET', '/catalogs/capex-concepts', null, tk)
const codigos = await api('GET', '/catalogs/capex-codes', null, tk)
const porRiesgo = Object.fromEntries(riesgos.map((r) => [r.code, r.id]))
const porConcepto = Object.fromEntries(conceptos.map((c) => [c.code, c.id]))
const porCodigo = Object.fromEntries(codigos.map((c) => [c.code, c.id]))

/** Tres naves: dos que se van a mirar juntas y una que hace de ruido. */
const NAVES = ['Nave Norte', 'Nave Sur', 'Nave Este']
const activos = []
for (const name of NAVES) {
  activos.push(await api('POST', `/projects/${proyecto.id}/assets`, {
    name,
    typology_id: tipologias[0].id,
  }, tk))
}
const zonas = await api('GET', `/assets/${activos[0].id}/allowed-zones`, null, tk)

/**
 * El reparto. Los dos primeros activos llevan objetos del MISMO capítulo, que
 * es lo que hace que la barra apilada tenga varios tramos que comprobar.
 */
const REPARTO = [
  { nave: 0, codigo: 'HC.H09.01', riesgo: '04', concepto: 'NORMATIVA', plazo: 'CORTO', importe: 500000 },
  { nave: 0, codigo: 'HC.H09.02', riesgo: '03', concepto: 'NORMATIVA', plazo: 'CORTO', importe: 300000 },
  { nave: 0, codigo: 'HC.H09', riesgo: '02', concepto: 'MEJORA', plazo: 'MEDIO', importe: 100000 },
  { nave: 1, codigo: 'HC.H02.01', riesgo: '01', concepto: 'MEJORA', plazo: 'LARGO', importe: 120000 },
  // Ruido fuera de la selección: si un corte no se filtrara, se vería.
  { nave: 2, codigo: 'HC.H03.01', riesgo: '04', concepto: 'SEGURIDAD', plazo: 'CORTO', importe: 999000 },
]
for (const [i, caso] of REPARTO.entries()) {
  await api('POST', `/projects/${proyecto.id}/findings`, {
    asset_id: activos[caso.nave].id,
    capex_code_id: porCodigo[caso.codigo],
    zone_id: zonas[0].id,
    risk_level_id: porRiesgo[caso.riesgo],
    capex_concept_id: porConcepto[caso.concepto],
    title: `Anomalía ${i + 1}`,
    description: 'Observada en visita.',
    capex_lines: [{ time_horizon_code: caso.plazo, amount: String(caso.importe) }],
  }, tk)
}
const TOTAL = REPARTO.reduce((a, c) => a + c.importe, 0)
const DOS_NAVES = REPARTO.filter((c) => c.nave < 2).reduce((a, c) => a + c.importe, 0)
console.log(`· ${REPARTO.length} hallazgos · ${TOTAL} € en total · ${DOS_NAVES} € en dos naves`)

// ── La pantalla ──────────────────────────────────────────────────────────────
const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
)
const contexto = await navegador.newContext({ viewport: { width: 1280, height: 1100 } })
const pagina = await contexto.newPage()
pagina.on('pageerror', (e) => fallos.push(`Error en la página: ${e.message}`))

await pagina.goto(BASE)
await pagina.fill('input[type="email"]', CORREO)
await pagina.fill('input[type="password"]', CLAVE)
await pagina.click('button[type="submit"]')
await pagina.waitForURL('**/proyectos', { timeout: 10000 })

await pagina.goto(`${BASE}/proyectos/${proyecto.id}/dashboard`)
await pagina.waitForSelector('.barras.apiladas', { timeout: 10000 })
console.log('· Dashboard abierto')

// 1 · El titular es el CAPEX del proyecto entero.
const titular = importes(await pagina.locator('.cifras-clave li').first().innerText())[0]
console.log(`  titular: ${titular} · esperado ${TOTAL}`)
if (titular !== TOTAL) fallos.push(`El titular dice ${titular} y el CAPEX es ${TOTAL}`)

// 2 · Los cinco cortes suman lo mismo en la pantalla.
const bloques = await pagina.locator('.bloque').all()
const titulos = []
for (const b of bloques) titulos.push((await b.locator('h3').innerText()).trim())
console.log('  bloques:', titulos.join(' · '))
for (const esperado of [
  'Distribución por concepto de gasto',
  'Perfil temporal de la inversión',
  'Exposición por grado de riesgo',
  'Desglose por categoría y objeto',
  'Distribución por activo',
]) {
  if (!titulos.includes(esperado)) fallos.push(`Falta el bloque «${esperado}»`)
}

/** Los cuatro bloques de barras, por su título en pantalla. El último —el de
 *  activo— es el que NO se filtra. */
const BARRAS = [
  'Perfil temporal de la inversión',
  'Exposición por grado de riesgo',
  'Desglose por categoría y objeto',
  'Distribución por activo',
]

/** El total de un bloque de barras: la suma de sus importes de fila. */
async function totalDelBloque(titulo) {
  const bloque = pagina.locator('.bloque').filter({ has: pagina.getByText(titulo, { exact: true }) })
  const cifras = await bloque.locator('.barras > li .cifra.importe').allInnerTexts()
  return cifras.reduce((a, t) => a + (importes(t)[0] ?? 0), 0)
}
for (const titulo of BARRAS) {
  const suma = await totalDelBloque(titulo)
  console.log(`  «${titulo}» suma ${suma}`)
  if (suma !== TOTAL) fallos.push(`«${titulo}» suma ${suma} y el CAPEX es ${TOTAL}`)
}

// 3 · El grado de riesgo va escrito, no solo en color.
const riesgo = await pagina
  .locator('.bloque')
  .filter({ has: pagina.getByText('Exposición por grado de riesgo', { exact: true }) })
  .innerText()
for (const codigo of ['01', '02', '03', '04']) {
  if (!riesgo.includes(codigo)) fallos.push(`El grado «${codigo}» no aparece escrito`)
}

// 4 · La barra apilada: sus tramos suman la categoría, y los objetos se leen.
const apiladas = await pagina.locator('.barras.apiladas > li').all()
console.log(`  ${apiladas.length} categorías apiladas`)
// La de electricidad, que es la que lleva tres objetos: 500 000 + 300 000 y
// 100 000 codificados en la propia categoría, sin bajar al objeto.
const electricidad = pagina.locator('.barras.apiladas > li').filter({ hasText: 'HC.H09' })
const tramos = await electricidad.locator('.tramo').count()
const importeCategoria = importes(await electricidad.locator('.cifra.importe').innerText())[0]
console.log(`  HC.H09: ${tramos} tramos · ${importeCategoria} €`)
if (tramos !== 3) fallos.push(`HC.H09 debería traer 3 objetos apilados y trae ${tramos}`)
if (importeCategoria !== 900000) {
  fallos.push(`HC.H09 suma ${importeCategoria} y debería sumar 900000`)
}
// Y los anchos de los tramos son la proporción de cada objeto dentro de ella:
// si no lo fueran, la barra no diría lo que dice su cifra.
const anchos = await electricidad.locator('.tramo').evaluateAll((ns) =>
  ns.map((n) => Number(n.style.width.replace('%', '')).toFixed(1)),
)
console.log('  anchos:', anchos.join(' / '))
if (anchos.join('/') !== '55.6/33.3/11.1') {
  fallos.push(`Los tramos de HC.H09 miden ${anchos.join('/')} y deberían medir 55.6/33.3/11.1`)
}
// El tramo pequeño no cabe rotulado, y por eso hace falta la tabla.
const rotulos = await electricidad.locator('.rotulo-de-tramo').count()
console.log(`  ${rotulos} de ${tramos} tramos llevan el nombre dentro`)
if (rotulos !== 2) {
  fallos.push(`Deberían rotularse los 2 tramos anchos y se rotulan ${rotulos}`)
}

// Los objetos, escritos en la tabla: el color no los identifica.
await pagina
  .locator('.bloque')
  .filter({ has: pagina.getByText('Desglose por categoría y objeto', { exact: true }) })
  .locator('summary')
  .click()
const tabla = await pagina
  .locator('.bloque')
  .filter({ has: pagina.getByText('Desglose por categoría y objeto', { exact: true }) })
  .locator('table')
  .innerText()
for (const nombre of ['Acometida-Centro de transformación', 'CGBT', 'Sin detallar']) {
  if (!tabla.includes(nombre)) fallos.push(`El objeto «${nombre}» no aparece escrito en la tabla`)
}

// 5 · El selector de varios activos filtra los cinco cortes.
await pagina.locator('.filtro-de-activos > summary').click()
for (const nombre of ['Nave Norte', 'Nave Sur']) {
  await pagina.locator('.filtro-de-activos label').filter({ hasText: nombre }).locator('input').check()
}
await pagina.waitForFunction(
  (esperado) => {
    const t = document.querySelector('.cifras-clave li .valor')?.textContent ?? ''
    return Number(t.replace(/[^\d]/g, '').slice(0, -2)) === esperado
  },
  DOS_NAVES,
  { timeout: 10000 },
)
const alcance = (await pagina.locator('.alcance').innerText()).replace(/\s+/g, ' ').trim()
console.log('  alcance:', alcance)
if (!alcance.includes('Nave Norte') || !alcance.includes('Nave Sur')) {
  fallos.push(`El alcance no nombra los dos activos elegidos: ${alcance}`)
}
for (const titulo of BARRAS.slice(0, -1)) {
  const suma = await totalDelBloque(titulo)
  console.log(`  filtrado, «${titulo}» suma ${suma}`)
  if (suma !== DOS_NAVES) fallos.push(`Filtrado, «${titulo}» suma ${suma} y debería ser ${DOS_NAVES}`)
}
// La distribución por activo NO se filtra: es la referencia del resto.
const edificios = await totalDelBloque('Distribución por activo')
console.log(`  filtrado, la distribución por activo sigue sumando ${edificios}`)
if (edificios !== TOTAL) {
  fallos.push(`«Distribución por activo» debería seguir enseñando la cartera entera (${TOTAL}), y suma ${edificios}`)
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log('Los cinco cortes cuadran, el filtro alcanza a cuatro y la distribución por activo se queda.')

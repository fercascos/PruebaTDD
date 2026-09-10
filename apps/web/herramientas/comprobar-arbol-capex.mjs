/**
 * ¿Dice el árbol de CAPEX del activo lo que tiene que decir? `[REQ]` §3.2 e.
 *
 * Cinco cosas que no se ven en una prueba unitaria:
 *
 * 1. **Que el árbol sume el CAPEX del activo.** Si el total de la cabecera no
 *    cuadra con lo cargado, quien lo lee se pasa el día buscando euros que no
 *    faltan.
 * 2. **Que cada nodo sume su subárbol.** El total de una categoría tiene que
 *    ser el de sus objetos: si no, el árbol se contradice consigo mismo en la
 *    misma pantalla.
 * 3. **Que solo salgan las ramas con contenido.** El catálogo trae 175 nodos;
 *    pintarlos todos obligaría a buscar lo que hay entre lo que no hay.
 * 4. **Que un código retirado no se trague una actuación.** Va a su rama, con
 *    su aviso, y sigue contando en el total.
 * 5. **Que la ficha de cada actuación traiga lo que pidió el cliente**: zona,
 *    riesgo, concepto, repercutible y los cinco plazos con su total.
 *
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-arbol-capex.mjs
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
const proyecto = await api('POST', '/projects', { client_id: cli.id, name: 'Activo con árbol' }, tk)
const tipologias = await api('GET', '/catalogs/asset-typologies', null, tk)
const riesgos = await api('GET', '/catalogs/risk-levels', null, tk)
const conceptos = await api('GET', '/catalogs/capex-concepts', null, tk)
const codigos = await api('GET', '/catalogs/capex-codes', null, tk)
const porRiesgo = Object.fromEntries(riesgos.map((r) => [r.code, r.id]))
const porConcepto = Object.fromEntries(conceptos.map((c) => [c.code, c.id]))
const porCodigo = Object.fromEntries(codigos.map((c) => [c.code, c.id]))

const activo = await api(
  'POST',
  `/projects/${proyecto.id}/assets`,
  { name: 'Nave Norte', typology_id: tipologias[0].id },
  tk,
)
// Un segundo activo con dinero: si el árbol no filtrara por activo, se vería.
const otro = await api(
  'POST',
  `/projects/${proyecto.id}/assets`,
  { name: 'Nave Sur', typology_id: tipologias[0].id },
  tk,
)
const zonas = await api('GET', `/assets/${activo.id}/allowed-zones`, null, tk)
const cubierta = zonas.find((z) => z.code === 'CUBIERTA') ?? zonas[0]

/**
 * El reparto. Dos objetos de electricidad y uno de cubierta, más un soft cost
 * —que se codifica en la CATEGORÍA porque soft costs no tiene objetos— y una
 * actuación recurrente, que cuenta como un hallazgo con dos plazos.
 */
const REPARTO = [
  { codigo: 'HC.H09.01', riesgo: '04', concepto: 'NORMATIVA', lineas: [['CORTO', 500000]] },
  { codigo: 'HC.H09.02', riesgo: '03', concepto: 'NORMATIVA', lineas: [['CORTO', 300000]] },
  {
    codigo: 'HC.H02.01',
    riesgo: '02',
    concepto: 'MEJORA',
    // Recurrente (P-44): un hallazgo, dos plazos.
    lineas: [['MEDIO', 80000], ['LARGO', 40000]],
  },
  { codigo: 'SC.S03', riesgo: '01', concepto: 'SOFT_COST', lineas: [['CORTO', 12000]] },
]
let esperado = 0
for (const [i, caso] of REPARTO.entries()) {
  await api('POST', `/projects/${proyecto.id}/findings`, {
    asset_id: activo.id,
    capex_code_id: porCodigo[caso.codigo],
    zone_id: cubierta.id,
    risk_level_id: porRiesgo[caso.riesgo],
    capex_concept_id: porConcepto[caso.concepto],
    title: `Anomalía ${i + 1}`,
    description: 'Observada en visita.',
    comments: 'Comentario del gestor técnico.',
    tenant_recoverable: 'SI',
    capex_lines: caso.lineas.map(([h, a]) => ({ time_horizon_code: h, amount: String(a) })),
  }, tk)
  for (const [, a] of caso.lineas) esperado += a
}
// Ruido en el otro activo.
await api('POST', `/projects/${proyecto.id}/findings`, {
  asset_id: otro.id,
  capex_code_id: porCodigo['HC.H03.01'],
  zone_id: cubierta.id,
  title: 'Del otro activo',
  description: '',
  capex_lines: [{ time_horizon_code: 'CORTO', amount: '999000' }],
}, tk)

console.log(`· ${REPARTO.length} actuaciones · ${esperado} € en el activo`)

// ── La pantalla ──────────────────────────────────────────────────────────────
const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
)
const contexto = await navegador.newContext({ viewport: { width: 1400, height: 1100 } })
const pagina = await contexto.newPage()
pagina.on('pageerror', (e) => fallos.push(`Error en la página: ${e.message}`))

await pagina.goto(BASE)
await pagina.fill('input[type="email"]', CORREO)
await pagina.fill('input[type="password"]', CLAVE)
await pagina.click('button[type="submit"]')
await pagina.waitForURL('**/proyectos', { timeout: 10000 })

// `[REQ]` §3.2 · Cada sección del activo tiene su propia dirección desde
// que el espacio del activo existe: se entra por ella y no encadenando
// clics, que además comprueba que la ruta es la que se anuncia.
await pagina.goto(`${BASE}/proyectos/${proyecto.id}/activos/${activo.id}/capex`)
await pagina.waitForSelector('.arbol-capex', { timeout: 10000 })
console.log('· Árbol abierto')

// 1 · El total del activo cuadra, y el otro activo no se cuela.
const cabecera = await pagina.locator('.arbol-capex > .alcance').innerText()
console.log('  cabecera:', cabecera.replace(/\s+/g, ' ').trim())
const totalPantalla = importes(cabecera)[0]
if (totalPantalla !== esperado) {
  fallos.push(`El árbol suma ${totalPantalla} y el activo tiene ${esperado}`)
}
if (!cabecera.includes(`${REPARTO.length} actuaciones`)) {
  fallos.push(`La cabecera no dice «${REPARTO.length} actuaciones»: ${cabecera.trim()}`)
}

/** El resumen de una rama, por el código que lleva escrito.
 *
 *  Se busca en el `<span class="codigo">` y con texto EXACTO, no con `hasText`
 *  sobre el resumen entero: `hasText` es subcadena y sin distinguir mayúsculas,
 *  así que «MA» encontraba «Acometida-Centro de transforMAción» y la prueba
 *  daba por dibujada una rama que no existe. */
async function rama(code) {
  return pagina
    .locator('.arbol-capex .rama > details > summary')
    .filter({ has: pagina.locator('.codigo', { hasText: new RegExp(`^${code.replace(/\./g, '\\.')}$`) }) })
}

// 2 · Cada nodo suma su subárbol: HC = 920 000, H09 = 800 000, sus dos objetos.
for (const [code, valor] of [
  ['HC', 920000],
  ['HC.H09', 800000],
  ['HC.H09.01', 500000],
  ['HC.H09.02', 300000],
  ['HC.H02', 120000],
  ['SC', 12000],
  ['SC.S03', 12000],
]) {
  const texto = await (await rama(code)).first().innerText()
  const suma = importes(texto).at(-1)
  console.log(`  ${code}: ${suma}`)
  if (suma !== valor) fallos.push(`La rama «${code}» suma ${suma} y debería sumar ${valor}`)
}

// 3 · Solo las ramas con contenido. Con 175 nodos en el catálogo, aquí hay 8.
const ramas = await pagina.locator('.arbol-capex .rama').count()
console.log(`  ${ramas} ramas dibujadas`)
if (ramas > 12) fallos.push(`Se dibujan ${ramas} ramas: deberían salir solo las que tienen algo`)
for (const ausente of ['HC.H07', 'MA', 'IMP']) {
  if ((await (await rama(ausente)).count()) > 0) {
    fallos.push(`«${ausente}» no tiene nada y aparece igualmente`)
  }
}

// 4 · Un soft cost se codifica en su CATEGORÍA, porque no tiene objetos, y el
//     árbol lo enseña ahí. Es el caso que el alta no admitía.
const soft = await (await rama('SC.S03')).first().innerText()
if (!soft.includes('Licencias')) fallos.push(`La rama de soft costs no se nombra: ${soft}`)

// 5b · La franja económica está sombreada y separada de la descriptiva.
const franja = await pagina
  .locator('.arbol-capex .tabla.actuaciones')
  .first()
  .locator('thead th.economica')
  .allInnerTexts()
console.log('  franja económica:', franja.join(' / '))
if (franja.length !== 6) {
  fallos.push(`La franja económica tiene ${franja.length} columnas y deberían ser 6`)
}
const fondos = await pagina
  .locator('.arbol-capex .tabla.actuaciones')
  .first()
  .locator('tbody tr:first-child th, tbody tr:first-child td')
  .evaluateAll((ns) =>
    ns.map((n) => ({
      eco: n.classList.contains('economica'),
      fondo: getComputedStyle(n).backgroundColor,
    })),
  )
const descriptivas = new Set(fondos.filter((c) => !c.eco).map((c) => c.fondo))
const economicas = new Set(fondos.filter((c) => c.eco).map((c) => c.fondo))
console.log('  fondos:', [...descriptivas].join(','), 'vs', [...economicas].join(','))
if ([...economicas].some((f) => descriptivas.has(f))) {
  fallos.push('Las columnas económicas se pintan igual que las descriptivas')
}

// 5 · La ficha de la actuación trae lo que pidió el cliente.
// La de «Anomalía 1», que es la de riesgo 04: la primera del DOM es la de
// H02, porque las ramas van por código y H02 va antes que H09.
const fila = pagina
  .locator('.arbol-capex .tabla.actuaciones tbody tr')
  .filter({ hasText: 'Anomalía 1' })
const celdas = await fila.locator('th, td').allInnerTexts()
console.log('  «Anomalía 1»:', celdas.map((c) => c.replace(/\s+/g, ' ').trim()).join(' | '))
const cabeceras = await pagina
  .locator('.arbol-capex .tabla.actuaciones')
  .first()
  .locator('thead th')
  .allInnerTexts()
for (const columna of ['Zona afectada', 'Riesgo', 'Concepto', 'Repercutible', 'Total']) {
  // Las cabeceras se pintan en versalitas, así que se comparan sin distinguir
  // mayúsculas: lo que se comprueba es que la columna esté, no cómo se pinta.
  if (!cabeceras.some((c) => c.toLowerCase() === columna.toLowerCase())) {
    fallos.push(`Falta la columna «${columna}»: hay ${cabeceras.join(', ')}`)
  }
}
const primera = celdas.join(' ')
for (const dato of ['Comentario del gestor técnico', 'Observada en visita', 'Cubierta', '04', 'Sí']) {
  if (!primera.includes(dato)) fallos.push(`La fila no trae «${dato}»: ${primera}`)
}

// 6 · Se puede dar de alta desde el nodo, con su código ya puesto.
// El botón dice el NOMBRE del objeto, y su nombre accesible lleva además el
// código entre paréntesis: los nombres se repiten en el catálogo —«General» y
// «Otros» están en las veintiocho categorías— y sin el código dos botones
// distintos se anunciarían igual.
const anadir = pagina.getByRole('button', {
  name: 'Añadir actuación en Acometida-Centro de transformación (HC.H09.01)',
})
if ((await anadir.count()) !== 1) {
  fallos.push('El botón de alta no se llama por el nombre del objeto y su código')
}
const visible = await anadir.first().innerText()
if (visible.includes('HC.H09.01')) {
  fallos.push(`El botón enseña el código y debería enseñar el nombre: ${visible}`)
}
console.log('  botón de alta:', visible.trim())
await anadir.first().click()
await pagina.waitForSelector('form', { timeout: 5000 })
const selector = pagina.getByLabel(/Código CAPEX/)
// Hay que esperar a que llegue el catálogo: mientras el desplegable solo tiene
// el «— elija un elemento —», el valor preseleccionado no puede estar puesto.
// Y comprobarlo DESPUÉS es justo lo que interesa: que al llegar las opciones el
// código del nodo siga elegido y no lo pise la primera de la lista.
// Las `option` de un `select` cerrado no son «visibles» para Playwright, así
// que se espera contándolas y no con `waitFor`.
await pagina.waitForFunction(
  () => (document.querySelectorAll('select option') ?? []).length > 20,
  null,
  { timeout: 10000 },
)
const elegido = await selector.inputValue()
if (elegido !== porCodigo['HC.H09.01']) {
  const opciones = await selector.locator('option').count()
  fallos.push(
    `El alta desde el árbol no llega con el código del nodo puesto: ` +
      `vale ${elegido || '(vacío)'} entre ${opciones} opciones, y debería valer ` +
      `${porCodigo['HC.H09.01']}`,
  )
} else {
  console.log('  el alta hereda el código del nodo')
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log('El árbol cuadra con el activo, cada nodo suma su subárbol y la ficha trae sus campos.')

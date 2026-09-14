/**
 * ¿Dice la matriz de riesgos lo que tiene que decir? `[REQ]` §12
 *
 * Tres cosas que no se ven en una prueba unitaria:
 *
 * 1. **Que los números de la pantalla cuadren con el CAPEX del proyecto.** Es lo
 *    que sostiene la utilidad de la matriz: si el total no coincide, quien la
 *    lee se pasa el resto del día buscando euros que no faltan.
 * 2. **Que el grado no se identifique solo por color.** Uno de cada doce
 *    hombres es daltónico, y esta pantalla se imprime en blanco y negro para
 *    reuniones. Se comprueba leyendo el texto: los códigos y los nombres tienen
 *    que estar escritos.
 * 3. **Que el filtro de activos admita uno, varios y todos** `[REQ]` §3.3, con
 *    las palabras del cliente. Aquí había un desplegable de uno solo, y eso
 *    dejaba fuera la única comparación que se hace en una cartera: «las dos
 *    naves del polígono frente al resto».
 *
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-riesgos.mjs
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

const { access_token: tk } = await api('POST', '/auth/login', {
  email: CORREO,
  password: CLAVE,
})
const cli = await api('POST', '/clients', { name: 'Inversora Ficticia S.L.' }, tk)
const proyecto = await api(
  'POST',
  '/projects',
  {
    client_id: cli.id,
    internal_code: `2026-${Math.random().toString(16).slice(2, 8)}`,
    name: 'Proyecto con riesgos',
  },
  tk,
)
const tipologias = await api('GET', '/catalogs/asset-typologies', null, tk)
const activo = await api(
  'POST',
  `/projects/${proyecto.id}/assets`,
  { name: 'Edificio Norte', typology_id: tipologias[0].id },
  tk,
)
const zonas = await api('GET', `/assets/${activo.id}/allowed-zones`, null, tk)
const codigos = await api('GET', '/catalogs/capex-codes?level=3', null, tk)
const riesgos = await api('GET', '/catalogs/risk-levels', null, tk)
const porCodigo = Object.fromEntries(riesgos.map((r) => [r.code, r.id]))

/** Un proyecto con los cuatro grados y una actuación recurrente. */
const REPARTO = [
  { riesgo: '04', lineas: [['CORTO', '412500.00']] },
  { riesgo: '03', lineas: [['CORTO', '271700.00']] },
  // Recurrente (P-44): un hallazgo, dos plazos.
  { riesgo: '03', lineas: [['MEDIO', '200000.00'], ['LARGO', '212500.00']] },
  { riesgo: '02', lineas: [['MEJORAS', '114500.00']] },
  { riesgo: '01', lineas: [] }, // sin importe: cuenta como hallazgo y suma cero
  { riesgo: null, lineas: [['OTRO', '142500.00']] }, // sin grado
]
let esperado = 0
for (const [i, caso] of REPARTO.entries()) {
  const cuerpo = {
    asset_id: activo.id,
    capex_code_id: codigos[i % codigos.length].id,
    zone_id: zonas[0].id,
    title: `Anomalía ${i + 1}`,
    description: 'Observada en visita.',
    capex_lines: caso.lineas.map(([h, a]) => ({ time_horizon_code: h, amount: a })),
  }
  if (caso.riesgo) cuerpo.risk_level_id = porCodigo[caso.riesgo]
  await api('POST', `/projects/${proyecto.id}/findings`, cuerpo, tk)
  for (const [, a] of caso.lineas) esperado += Number(a)
}
console.log(`· ${REPARTO.length} hallazgos, ${esperado.toLocaleString('es-ES')} € en total`)

// `[REQ]` §3.3 · Un segundo activo, que es lo que hace que el filtro exista:
// con uno solo no se pinta, porque un desplegable de una casilla no filtra.
const segundo = await api(
  'POST',
  `/projects/${proyecto.id}/assets`,
  { name: 'Edificio Sur', typology_id: tipologias[0].id },
  tk,
)
const zonasSur = await api('GET', `/assets/${segundo.id}/allowed-zones`, null, tk)
const SUR = 77000
await api(
  'POST',
  `/projects/${proyecto.id}/findings`,
  {
    asset_id: segundo.id,
    capex_code_id: codigos[0].id,
    zone_id: zonasSur[0].id,
    risk_level_id: porCodigo['02'],
    title: 'Anomalía del sur',
    description: 'Observada en visita.',
    capex_lines: [{ time_horizon_code: 'CORTO', amount: String(SUR) }],
  },
  tk,
)
const TODO = esperado + SUR
console.log(`· Segundo activo con ${SUR} € · ${TODO} € en la cartera`)

// El CAPEX del proyecto por la otra vía: si los dos no coinciden, es que la
// matriz está contando mal, no que la prueba esté mal escrita.
const resumen = await api('GET', `/projects/${proyecto.id}/capex/summary/by-horizon`, null, tk)
const capex = resumen.reduce((a, f) => a + Number(f.amount), 0)
if (Math.abs(capex - TODO) > 0.01) {
  fallos.push(`El CAPEX del proyecto (${capex}) no es el que se ha cargado (${TODO})`)
}

// ── La pantalla ──────────────────────────────────────────────────────────────
const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
)
const contexto = await navegador.newContext({ viewport: { width: 1280, height: 1000 } })
const pagina = await contexto.newPage()
pagina.on('pageerror', (e) => fallos.push(`Error en la página: ${e.message}`))

await pagina.goto(BASE)
await pagina.fill('input[type="email"]', CORREO)
await pagina.fill('input[type="password"]', CLAVE)
await pagina.click('button[type="submit"]')
await pagina.waitForURL('**/proyectos', { timeout: 10000 })

await pagina.goto(`${BASE}/proyectos/${proyecto.id}/riesgos`)
await pagina.waitForSelector('.tabla.matriz', { timeout: 10000 })
console.log('· Matriz abierta')

// 1 · Los números de la pantalla cuadran con el CAPEX.
const pie = await pagina.locator('.tabla.matriz tfoot tr').textContent()
console.log('  fila de totales:', pie.replace(/\s+/g, ' ').trim())
const enPantalla = [...pie.matchAll(/([\d.]+)\s*€/g)].map((m) =>
  Number(m[1].replace(/\./g, '')),
)
const totalPantalla = enPantalla.at(-1)
console.log(`  total en pantalla: ${totalPantalla} · esperado: ${Math.round(TODO)}`)
if (Math.abs(totalPantalla - TODO) > 1) {
  fallos.push(`El total de la matriz (${totalPantalla}) no cuadra con el CAPEX (${TODO})`)
}
// Y las columnas suman el total.
const columnas = enPantalla.slice(0, -1)
const sumaColumnas = columnas.reduce((a, b) => a + b, 0)
if (Math.abs(sumaColumnas - totalPantalla) > 1) {
  fallos.push(`Las columnas suman ${sumaColumnas} y el total dice ${totalPantalla}`)
}

// 2 · El grado no se identifica solo por color: los códigos están escritos.
const texto = await pagina.locator('.tabla.matriz').innerText()
for (const codigo of ['01', '02', '03', '04']) {
  if (!texto.includes(codigo)) fallos.push(`El código «${codigo}» no aparece escrito en la matriz`)
}
for (const nombre of ['Extremo', 'Alto', 'Moderado', 'Bajo']) {
  if (!texto.includes(nombre)) fallos.push(`El nombre «${nombre}» no aparece escrito`)
}
console.log('  los cuatro grados salen con código y nombre:', !fallos.length)

// 3 · Una actuación recurrente cuenta una vez y reparte su dinero.
const filaAlto = await pagina
  .locator('.tabla.matriz tbody tr')
  .filter({ hasText: 'Alto' })
  .innerText()
console.log('  fila «Alto»:', filaAlto.replace(/\s+/g, ' ').trim())
const alto = [...filaAlto.matchAll(/([\d.]+)\s*€/g)].map((m) => Number(m[1].replace(/\./g, '')))
if (alto.at(-1) !== 271700 + 200000 + 212500) {
  fallos.push(`La fila «Alto» totaliza ${alto.at(-1)} y debería ser 684200`)
}

// 4 · Los hallazgos sin grado no desaparecen.
const cuerpoTabla = await pagina.locator('.tabla.matriz tbody').innerText()
if (!cuerpoTabla.includes('Sin clasificar')) {
  fallos.push('La fila de hallazgos sin grado no aparece: los totales dejarían de cuadrar')
}

// 5 · El recuento de hallazgos cuenta la recurrente una vez: 6 + el del sur.
// `> .ayuda` y no `.ayuda` a secas: el `<legend>` del filtro de activos lleva
// la misma clase y está dentro de `.filtro`, así que el selector suelto
// devuelve dos elementos.
const cabecera = await pagina.locator('.filtro > .ayuda').textContent()
console.log('  cabecera:', cabecera.trim())
if (!cabecera.includes(`${REPARTO.length + 1} hallazgos`)) {
  fallos.push(`La cabecera no dice «${REPARTO.length + 1} hallazgos»: ${cabecera.trim()}`)
}

// 6 · `[REQ]` §3.3 · El filtro: uno, varios y todos.
/**
 * El total de la matriz **cuando llegue a valerlo**, o el que haya al agotarse
 * la espera.
 *
 * Espera por el valor exacto y no por «que cambie del anterior», que es lo que
 * hacía y estaba mal: marcar y desmarcar casillas produce estados intermedios
 * —tras soltar la primera de dos, la matriz enseña un momento solo la segunda—
 * y «ha cambiado» se cumple ahí, así que la comprobación leía un total real
 * pero de un paso que no era el suyo.
 */
async function totalDeLaMatriz(esperadoAqui) {
  const leer = () =>
    pagina.locator('.tabla.matriz tfoot tr').textContent().then((fila) => {
      const cifras = [...fila.matchAll(/([\d.]+)\s*€/g)].map((m) => Number(m[1].replace(/\./g, '')))
      return cifras.at(-1)
    })
  try {
    await pagina.waitForFunction(
      (valor) => {
        const fila = document.querySelector('.tabla.matriz tfoot tr')?.textContent ?? ''
        const ultima = [...fila.matchAll(/([\d.]+)\s*€/g)].at(-1)
        return ultima !== undefined && Number(ultima[1].replace(/\./g, '')) === valor
      },
      Math.round(esperadoAqui),
      { timeout: 10000 },
    )
  } catch {
    // Se deja caer: quien llama compara y dice qué salió, que informa más que
    // un tiempo de espera agotado sin cifra.
  }
  return leer()
}

if ((await pagina.locator('.filtro .filtro-de-activos').count()) !== 1) {
  fallos.push('Con dos activos, la matriz no ofrece el filtro de varios')
} else {
  await pagina.locator('.filtro-de-activos > summary').click()
  const casilla = (nombre) =>
    pagina.locator('.filtro-de-activos label').filter({ hasText: nombre }).locator('input')

  // Uno solo.
  await casilla('Edificio Norte').check()
  const soloNorte = await totalDeLaMatriz(esperado)
  console.log(`  solo Edificio Norte: ${soloNorte} · esperado ${Math.round(esperado)}`)
  if (Math.abs(soloNorte - esperado) > 1) {
    fallos.push(`Filtrando a un activo la matriz suma ${soloNorte} y debería sumar ${esperado}`)
  }

  // Varios: el segundo se SUMA al primero, no lo sustituye.
  await casilla('Edificio Sur').check()
  const losDos = await totalDeLaMatriz(TODO)
  console.log(`  los dos: ${losDos} · esperado ${Math.round(TODO)}`)
  if (Math.abs(losDos - TODO) > 1) {
    fallos.push(`Con los dos marcados la matriz suma ${losDos} y debería sumar ${TODO}`)
  }

  // Y soltarlos todos vuelve a la cartera entera, no a cero.
  await casilla('Edificio Norte').uncheck()
  await casilla('Edificio Sur').uncheck()
  const sinFiltro = await totalDeLaMatriz(TODO)
  console.log(`  sin ninguna casilla: ${sinFiltro}`)
  if (Math.abs(sinFiltro - TODO) > 1) {
    fallos.push(`Sin casillas marcadas la matriz suma ${sinFiltro} y debería ser la cartera entera`)
  }
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log(
  'Los totales cuadran con el CAPEX, el grado se lee sin depender del color y el filtro ' +
    'admite uno, varios y todos.',
)

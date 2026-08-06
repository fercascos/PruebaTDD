/**
 * ¿Dice el inventario de equipo lo que tiene que decir? `[REQ]` §7 / P-15
 *
 * Lo que se comprueba con el navegador delante y no en una unitaria:
 *
 * 1. **P-15 · «La vida residual se calcula, no se teclea.»** No puede existir
 *    ningún campo donde introducirla, y la cifra tiene que salir sola mientras
 *    se rellena el año de instalación. Es el requisito entero de esta pantalla.
 * 2. **El equipo vencido no se identifica solo por color.** La misma regla que
 *    en la matriz de riesgos: uno de cada doce hombres es daltónico y esto se
 *    imprime en blanco y negro para las reuniones.
 * 3. **Estado y obsolescencia son columnas distintas.** Una caldera bien
 *    conservada puede estar sin repuestos, y eso decide la sustitución.
 *
 *     make run &
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-inventario.mjs
 */
import { chromium } from 'playwright'

const BASE = process.env.URL_BASE ?? 'http://localhost:4173'
const API = process.env.URL_API ?? 'http://localhost:8000/api/v1'
const CORREO = process.env.TDD_EMAIL ?? 'admin@ejemplo.example'
const CLAVE = process.env.TDD_PASSWORD ?? 'cubierta invertida 2026'

const fallos = []
const ANIO = new Date().getFullYear()

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

const sufijo = Math.random().toString(16).slice(2, 8)
const { access_token: tk } = await api('POST', '/auth/login', { email: CORREO, password: CLAVE })
const cli = await api('POST', '/clients', { name: 'Inversora Ficticia S.L.' }, tk)
const proyecto = await api(
  'POST',
  '/projects',
  { client_id: cli.id, internal_code: `2026-${sufijo}`, name: 'Encargo con inventario' },
  tk,
)
const tipologias = await api('GET', '/catalogs/asset-typologies', null, tk)
const activo = await api(
  'POST',
  `/projects/${proyecto.id}/assets`,
  { name: 'Edificio Norte', typology_id: tipologias[0].id },
  tk,
)
const sistemas = await api('GET', '/catalogs/technical-systems', null, tk)
if (sistemas.length !== 14) {
  fallos.push(`Se esperaban 14 sistemas técnicos sembrados, hay ${sistemas.length}`)
}
const clima = sistemas.find((s) => s.code === 'CLIMATIZACION')

// Una enfriadora con la vida agotada y un ascensor recién puesto: la lista
// tiene que distinguirlos sin que nadie mire el color.
await api(
  'POST',
  `/projects/${proyecto.id}/equipment`,
  {
    asset_id: activo.id,
    tag: 'CL-01',
    equipment_type: 'Enfriadora',
    technical_system_id: clima.id,
    manufacturer: 'Fabricante Ficticio',
    model: 'XR-300',
    serial_number: '4J-00219',
    install_year: 1995,
    expected_life_years: 20,
    condition: 'BUENO',
    obsolescence: 'SIN_REPUESTOS',
    criticality: 'ALTA',
  },
  tk,
)
await api(
  'POST',
  `/projects/${proyecto.id}/equipment`,
  {
    asset_id: activo.id,
    tag: 'AS-01',
    equipment_type: 'Ascensor',
    install_year: ANIO,
    expected_life_years: 25,
    condition: 'BUENO',
    obsolescence: 'ACTUAL',
  },
  tk,
)
console.log(`· Encargo ${proyecto.internal_code}: una enfriadora vencida y un ascensor nuevo`)

// ── La pantalla ──────────────────────────────────────────────────────────────
const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
)
const contexto = await navegador.newContext({ viewport: { width: 1500, height: 1100 } })
const pagina = await contexto.newPage()
pagina.on('pageerror', (e) => fallos.push(`Error en la página: ${e.message}`))

await pagina.goto(BASE)
await pagina.fill('input[type="email"]', CORREO)
await pagina.fill('input[type="password"]', CLAVE)
await pagina.click('button[type="submit"]')
await pagina.waitForURL('**/proyectos', { timeout: 10000 })

await pagina.goto(`${BASE}/proyectos/${proyecto.id}/equipo`)
await pagina.waitForSelector('.tabla.inventario', { timeout: 10000 })
console.log('· Inventario abierto')

// 1 · La vida residual está escrita, no insinuada con color.
const enfriadora = pagina.locator('.tabla.inventario tbody tr').filter({ hasText: 'CL-01' })
const textoEnfriadora = await enfriadora.innerText()
console.log('  fila CL-01:', textoEnfriadora.replace(/\s+/g, ' ').trim())
const vencidaHace = ANIO - (1995 + 20)
if (!textoEnfriadora.includes(`vencida hace ${vencidaHace} años`)) {
  fallos.push(`La fila no dice cuántos años lleva vencida (esperado ${vencidaHace}): ${textoEnfriadora}`)
}
if (!textoEnfriadora.includes('Corto plazo')) {
  fallos.push('La reposición de un equipo vencido no se sitúa en el plazo más inmediato')
}

// 2 · Y el ascensor nuevo no aparece como vencido.
const ascensor = await pagina
  .locator('.tabla.inventario tbody tr')
  .filter({ hasText: 'AS-01' })
  .innerText()
console.log('  fila AS-01:', ascensor.replace(/\s+/g, ' ').trim())
if (!ascensor.includes('25 años')) {
  fallos.push(`El ascensor recién instalado no dice que le quedan 25 años: ${ascensor}`)
}

// 3 · Estado y obsolescencia son columnas distintas: la enfriadora está en
//     BUEN estado Y sin repuestos a la vez. Fundirlas perdería este caso.
if (!textoEnfriadora.includes('Bueno') || !textoEnfriadora.includes('Sin repuestos')) {
  fallos.push('Estado y obsolescencia no se leen por separado en la misma fila')
}

// 4 · El filtro de vencidos deja fuera al que no lo está.
await pagina.check('.inventario .filtro input[type="checkbox"]')
await pagina.waitForFunction(
  () => document.querySelectorAll('.tabla.inventario tbody tr').length === 1,
  null,
  { timeout: 5000 },
)
const filtrado = await pagina.locator('.tabla.inventario tbody').innerText()
if (filtrado.includes('AS-01')) fallos.push('El filtro de vencidos deja pasar un equipo vigente')
await pagina.uncheck('.inventario .filtro input[type="checkbox"]')

// 5 · **P-15** · No hay ningún campo donde teclear la vida residual, y la cifra
//     sale sola mientras se rellenan los dos datos de los que depende.
await pagina.click('button:has-text("Añadir equipo")')
await pagina.waitForSelector('.ficha-equipo')
const etiquetas = await pagina.locator('.ficha-equipo label').allInnerTexts()
const sospechosas = etiquetas.filter((e) => /vida residual|años restantes|remaining/i.test(e))
if (sospechosas.length) {
  fallos.push(`Hay un campo para teclear la vida residual: ${sospechosas.join(' / ')}`)
}
console.log(`  campos del formulario: ${etiquetas.length}, ninguno de vida residual`)

await pagina.fill('.ficha-equipo input[placeholder*="Enfriadora"]', 'Caldera')
const anios = pagina.locator('.ficha-equipo section:has-text("Vida útil") input[type="number"]')
await anios.nth(0).fill('2000')
// Con solo la mitad del dato no se calcula nada y se avisa, porque la base lo
// rechaza con un CHECK y un 500 no explicaría por qué.
const aviso = await pagina.locator('.ficha-equipo .mensaje.aviso').innerText()
if (!/juntos o no van/i.test(aviso)) {
  fallos.push(`Media vida útil no avisa de que faltan los dos datos: «${aviso}»`)
}
if (!(await pagina.locator('.ficha-equipo .acciones button').first().isDisabled())) {
  fallos.push('Se puede guardar con media vida útil: la base lo rechazaría con un CHECK')
}

await anios.nth(1).fill('30')
await pagina.waitForSelector('.ficha-equipo .vida-calculada strong')
const calculada = await pagina.locator('.vida-calculada').innerText()
console.log('  vida calculada al teclear:', calculada.replace(/\s+/g, ' ').trim())
if (!calculada.includes('2030')) {
  fallos.push(`La vida residual no se calcula sola al teclear: «${calculada}»`)
}
if (!/no se guarda/i.test(calculada)) {
  fallos.push('No se dice que la vida residual se recalcula y no se almacena')
}

// 6 · Y guardarlo devuelve la misma cifra que calcula el servidor.
await pagina.click('.ficha-equipo .acciones button:has-text("Guardar equipo")')
await pagina.waitForSelector('.tabla.inventario', { timeout: 10000 })
const caldera = await pagina
  .locator('.tabla.inventario tbody tr')
  .filter({ hasText: 'Caldera' })
  .innerText()
console.log('  fila Caldera:', caldera.replace(/\s+/g, ' ').trim())
const restan = 2030 - ANIO
const esperado = restan < 0 ? `vencida hace ${-restan} años` : `${restan} años`
if (!caldera.includes(esperado)) {
  fallos.push(`La cifra guardada no coincide con la calculada («${esperado}»): ${caldera}`)
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log('La vida residual se calcula y no se teclea, y lo vencido se lee sin depender del color.')

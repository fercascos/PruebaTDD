/**
 * ¿Hace la visita del activo lo que pidió el cliente? `[REQ]` §3.2 c.
 *
 * Seis cosas que no se ven en una prueba de API:
 *
 * 1. **Que la visita viva dentro del activo**, con sus tres bloques: datos,
 *    equipo implicado y fotos.
 * 2. **Que el punto de encuentro llegue relleno con la dirección del activo** y
 *    se pueda corregir. Pedirlo en blanco significa que casi siempre queda
 *    vacío, y el día de la visita nadie sabe por dónde se entra.
 * 3. **Que marcar «Realizada» feche la visita sola.** La fecha real es la que
 *    fecha el informe.
 * 4. **Que el equipo implicado mezcle personas de la aplicación y acompañantes
 *    escritos a mano**, y que cuatro no sea un tope.
 * 5. **Que la pantalla diga que el coste NO entra en el CAPEX**: quien lo
 *    teclea tiene que saber dónde acaba antes de teclearlo.
 * 6. **Que el coste no llegue de verdad al CAPEX del activo**, comprobado
 *    contra la API después de guardarlo por la pantalla.
 *
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-visita-del-activo.mjs
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

/**
 * Pulsa un botón y espera a que **la petición termine**, no a que la pantalla
 * parezca haber cambiado.
 *
 * La primera versión de esta comprobación esperaba por el DOM —«que haya una
 * línea de equipo», «que salga el mensaje de guardado»— y las dos condiciones
 * ya eran ciertas **antes** de pulsar: la línea se añade en local al elegir la
 * persona, y el mensaje de guardado seguía en pantalla de la vez anterior. Así
 * que leía la API antes de que llegara nada y daba por rotas dos cosas que
 * funcionaban. Esperar por la respuesta es lo único que de verdad ordena las
 * dos mitades.
 */
async function pulsarYEsperar(pagina, nombre, metodo, fragmento) {
  const respuesta = pagina.waitForResponse(
    (r) => r.url().includes(fragmento) && r.request().method() === metodo,
    { timeout: 15000 },
  )
  await pagina.getByRole('button', { name: nombre }).click()
  const r = await respuesta
  if (!r.ok()) fallos.push(`${metodo} ${fragmento} respondió ${r.status()}`)
  return r
}

const { access_token: tk } = await api('POST', '/auth/login', { email: CORREO, password: CLAVE })
const cli = await api('POST', '/clients', { name: 'Inversora Ficticia S.L.' }, tk)
const proyecto = await api(
  'POST',
  '/projects',
  { client_id: cli.id, name: 'Activo con visita', applicable_phases: [{ code: 'VISITA' }] },
  tk,
)
const tipologias = await api('GET', '/catalogs/asset-typologies', null, tk)
const activo = await api(
  'POST',
  `/projects/${proyecto.id}/assets`,
  {
    name: 'Nave Norte',
    typology_id: tipologias.find((t) => t.code === 'INDUSTRIAL').id,
    address_line: 'Polígono Ficticio, parcela 12',
    city: 'Ciudad Ficticia',
  },
  tk,
)
console.log('· Proyecto y activo creados')

// ── La pantalla ──────────────────────────────────────────────────────────────
const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
)
const contexto = await navegador.newContext({ viewport: { width: 1400, height: 1200 } })
const pagina = await contexto.newPage()
pagina.on('pageerror', (e) => fallos.push(`Error en la página: ${e.message}`))

await pagina.goto(BASE)
await pagina.fill('input[type="email"]', CORREO)
await pagina.fill('input[type="password"]', CLAVE)
await pagina.click('button[type="submit"]')
await pagina.waitForURL('**/proyectos', { timeout: 10000 })

await pagina.goto(`${BASE}/proyectos/${proyecto.id}/activos`)
await pagina.getByRole('button', { name: 'Editar' }).first().click()
await pagina.waitForSelector('.visita-activo', { timeout: 10000 })
console.log('· Sección de visita abierta')

// 1 · Los tres bloques de la hoja del cliente están.
await pagina.getByRole('button', { name: 'Programar una visita' }).click()
await pagina.waitForSelector('.visita-activo .visita', { timeout: 10000 })
const bloques = await pagina.locator('.visita-activo h4').allInnerTexts()
console.log('  bloques:', bloques.join(' / '))
for (const esperado of ['Datos de la visita', 'Equipo implicado', 'Fotografías']) {
  if (!bloques.some((b) => b.trim() === esperado)) {
    fallos.push(`Falta el bloque «${esperado}»: hay ${bloques.join(', ')}`)
  }
}

// 2 · El punto de encuentro llega propuesto desde la ficha del activo.
const encuentro = pagina.getByLabel(/Ubicación y punto de encuentro/)
const propuesto = await encuentro.inputValue()
console.log('  punto de encuentro propuesto:', propuesto)
if (!propuesto.includes('Polígono Ficticio')) {
  fallos.push(`El punto de encuentro no se propone de la ficha del activo: «${propuesto}»`)
}
await encuentro.fill('Entrada por el muelle 4; preguntar por el jefe de mantenimiento.')

// 3 · Marcar «Realizada» y guardar: se fecha sola.
await pagina.getByLabel('Estado de la visita').selectOption('VISITADO')
await pulsarYEsperar(pagina, 'Guardar la visita', 'PATCH', '/visits/')
const [guardada] = await api('GET', `/assets/${activo.id}/visits`, null, tk)
console.log('  estado:', guardada.status, '· fecha real:', guardada.actual_date)
if (guardada.status !== 'VISITADO' || !guardada.actual_date) {
  fallos.push(`«Realizada» no ha fechado la visita: ${JSON.stringify(guardada)}`)
}
if (!guardada.meeting_point.includes('muelle 4')) {
  fallos.push(`El punto de encuentro corregido no se ha guardado: «${guardada.meeting_point}»`)
}
// La fila se marca como realizada, y además lo dice con letras.
const pastilla = await pagina.locator('.visita summary .pastilla').first().innerText()
if (!/realizada/i.test(pastilla)) {
  fallos.push(`El estado no se lee en la cabecera de la visita: «${pastilla}»`)
}

// 4 · Equipo implicado: personas de la aplicación y acompañantes de fuera.
await pagina.getByLabel('Añadir una persona del equipo').selectOption({ index: 1 })
for (let i = 0; i < 4; i++) {
  await pagina.getByRole('button', { name: 'Añadir acompañante' }).click()
}
const acompanantes = ['Nombre Ficticio', 'Otro Nombre', 'Tercer Nombre', 'Cuarto Nombre']
for (const [i, nombre] of acompanantes.entries()) {
  await pagina.getByLabel(`Nombre del acompañante ${i + 2}`).fill(nombre)
}
await pulsarYEsperar(pagina, 'Guardar el equipo', 'PUT', '/attendees')
const [conEquipo] = await api('GET', `/assets/${activo.id}/visits`, null, tk)
console.log(`  asistentes: ${conEquipo.asistentes.length}`)
// `[REQ]` Cuatro «Responsable» era lo que cabía en la hoja, no un tope.
if (conEquipo.asistentes.length !== 5) {
  fallos.push(
    `Se esperaban 5 asistentes —1 del equipo y 4 de fuera— y hay ${conEquipo.asistentes.length}`,
  )
}
const delEquipo = conEquipo.asistentes.filter((a) => a.es_del_equipo)
if (delEquipo.length !== 1 || !delEquipo[0].app_user_id) {
  fallos.push('La persona del equipo no ha quedado atada a su cuenta')
} else {
  console.log(`  del equipo: ${delEquipo[0].nombre} (con cuenta)`)
}
if (!conEquipo.asistentes.some((a) => a.nombre === 'Cuarto Nombre' && !a.es_del_equipo)) {
  fallos.push('El cuarto acompañante no se ha guardado')
}

// 5 · La pantalla advierte de dónde NO acaba el coste, antes de teclearlo.
const ayudaDelCoste = await pagina
  .locator('label', { hasText: 'Coste de la visita' })
  .locator('.ayuda')
  .innerText()
console.log('  aviso del coste:', ayudaDelCoste)
if (!/CAPEX/.test(ayudaDelCoste) || !/informe/.test(ayudaDelCoste)) {
  fallos.push(`La pantalla no dice que el coste queda fuera del CAPEX: «${ayudaDelCoste}»`)
}

// 6 · Y no acaba ahí de verdad.
await pagina.getByLabel(/Coste de la visita/).fill('1250')
await pulsarYEsperar(pagina, 'Guardar la visita', 'PATCH', '/visits/')
const [conCoste] = await api('GET', `/assets/${activo.id}/visits`, null, tk)
if (Number(conCoste.cost_amount) !== 1250) {
  fallos.push(`El coste no se ha guardado: ${conCoste.cost_amount}`)
}
const porActivo = await api('GET', `/projects/${proyecto.id}/capex/summary/by-asset`, null, tk)
const enCapex = porActivo.reduce((s, f) => s + Number(f.amount), 0)
console.log(`  coste guardado: ${conCoste.cost_amount} · CAPEX del proyecto: ${enCapex}`)
if (enCapex !== 0) {
  fallos.push(`El coste de la visita ha llegado al CAPEX del edificio: ${enCapex}`)
}

// 7 · Varias visitas por activo, y la última arriba.
await pulsarYEsperar(pagina, 'Programar una visita', 'POST', '/visits')
await pagina.waitForFunction(
  () => document.querySelectorAll('.visita-activo .visita').length === 2,
  null,
  { timeout: 10000 },
)
const cabeceras = await pagina.locator('.visita summary strong').allInnerTexts()
console.log('  visitas:', cabeceras.join(' / '))
if (cabeceras[0] !== 'Sin fecha') {
  fallos.push(`La visita recién creada no sale la primera: ${cabeceras.join(', ')}`)
}

// 8 · La página no se ensancha en móvil.
const movil = await contexto.newPage()
await movil.setViewportSize({ width: 390, height: 900 })
await movil.goto(`${BASE}/proyectos/${proyecto.id}/activos`)
await movil.getByRole('button', { name: 'Editar' }).first().click()
await movil.waitForSelector('.visita-activo .visita', { timeout: 10000 })
const ancho = await movil.evaluate(() => ({
  doc: document.documentElement.scrollWidth,
  ventana: window.innerWidth,
}))
console.log(`  móvil: ${ancho.doc} sobre ${ancho.ventana}`)
if (ancho.doc > ancho.ventana) {
  fallos.push(`En móvil la página se ensancha ${ancho.doc - ancho.ventana} px`)
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log(
  'La visita vive en el activo, se fecha sola al marcarla, el equipo mezcla cuentas y ' +
    'acompañantes, y el coste se queda fuera del CAPEX.',
)

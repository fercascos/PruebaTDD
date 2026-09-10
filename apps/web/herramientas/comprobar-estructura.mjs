/**
 * ¿Está la aplicación estructurada como la pidió el cliente? `[REQ]` §3.1-§3.2.
 *
 * Lo confirmó al revisar el prototipo, y es el cambio de fondo del rediseño:
 *
 * 1. **Cinco pestañas de proyecto y en su orden**: Resumen, Activos, y después
 *    lo general —Dashboard, Riesgos, Informe final—. Eran diez.
 * 2. **Documentación, fotografías, mapa, inventario y CAPEX ya no son pestañas
 *    del proyecto**: se han mudado dentro del activo. Que sigan existiendo por
 *    su ruta vieja sería tener las dos cosas.
 * 3. **Un espacio por activo** con sus cinco secciones, y cada una con su
 *    propia dirección: sin eso no se puede mandar «mira la visita de la Nave A».
 * 4. **El Resumen lleva la introducción y el mapa de TODOS los activos**, que
 *    es lo que pidió: el mapa de fotografías contesta otra pregunta.
 * 5. **El detalle del activo lleva su propio mapa.**
 * 6. **La introducción se guarda y vuelve.**
 * 7. **La aplicación no dice «encargo» en ninguna pantalla**: se llama proyecto.
 *
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-estructura.mjs
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

const { access_token: tk } = await api('POST', '/auth/login', { email: CORREO, password: CLAVE })
const cli = await api('POST', '/clients', { name: 'Inversora Ficticia S.L.' }, tk)
const proyecto = await api('POST', '/projects', { client_id: cli.id, name: 'Cartera Ficticia' }, tk)
const tipologias = await api('GET', '/catalogs/asset-typologies', null, tk)
const industrial = tipologias.find((t) => t.code === 'INDUSTRIAL').id
const activo = await api(
  'POST',
  `/projects/${proyecto.id}/assets`,
  {
    name: 'Nave Norte',
    asset_code: 'NN-1',
    typology_id: industrial,
    address_line: 'Polígono Ficticio, parcela 12',
    city: 'Ciudad Ficticia',
    latitude: '40.3081',
    longitude: '-3.7326',
  },
  tk,
)
// Un segundo activo, situado lejos: el mapa del Resumen tiene que encuadrar los
// dos, y con uno solo no se vería la diferencia con el del detalle.
await api(
  'POST',
  `/projects/${proyecto.id}/assets`,
  {
    name: 'Nave Sur',
    typology_id: industrial,
    city: 'Otra Ciudad Ficticia',
    latitude: '39.9864',
    longitude: '-3.6100',
  },
  tk,
)
console.log('· Proyecto con dos activos situados')

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

// 1 · Cinco pestañas, en su orden.
await pagina.goto(`${BASE}/proyectos/${proyecto.id}`)
await pagina.waitForSelector('.pestanas', { timeout: 10000 })
const pestanas = (await pagina.locator('.pestanas > a').allInnerTexts()).map((t) => t.trim())
console.log('  pestañas:', pestanas.join(' · '))
const ESPERADAS = ['Resumen', 'Activos', 'Dashboard', 'Riesgos', 'Informe final']
if (JSON.stringify(pestanas) !== JSON.stringify(ESPERADAS)) {
  fallos.push(`Las pestañas son ${pestanas.join(', ')} y deberían ser ${ESPERADAS.join(', ')}`)
}

// 2 · Las cinco que se han mudado ya no responden en el proyecto.
for (const vieja of ['documentacion', 'fotos', 'mapa', 'equipo', 'capex']) {
  await pagina.goto(`${BASE}/proyectos/${proyecto.id}/${vieja}`)
  await pagina.waitForTimeout(500)
  const hay = await pagina.locator('.pestanas > a.active').count()
  if (hay > 0) {
    fallos.push(`«${vieja}» sigue siendo una pestaña del proyecto: debería vivir en el activo`)
  }
}
console.log('  las cinco pestañas mudadas ya no están en el proyecto')

// 3 · Un espacio por activo, con dirección propia por sección.
await pagina.goto(`${BASE}/proyectos/${proyecto.id}/activos`)
await pagina.getByRole('button', { name: 'Abrir' }).first().click()
await pagina.waitForSelector('.pestanas.secundarias', { timeout: 10000 })
const secciones = (await pagina.locator('.pestanas.secundarias a').allInnerTexts()).map((t) =>
  t.trim(),
)
console.log('  secciones:', secciones.join(' · '))
const SECCIONES = ['Detalle', 'Documentación', 'Visita', 'Inventario', 'CAPEX']
if (JSON.stringify(secciones) !== JSON.stringify(SECCIONES)) {
  fallos.push(`Las secciones son ${secciones.join(', ')} y deberían ser ${SECCIONES.join(', ')}`)
}
for (const [nombre, cola] of [
  ['Documentación', 'documentacion'],
  ['Visita', 'visita'],
  ['Inventario', 'inventario'],
  ['CAPEX', 'capex'],
]) {
  await pagina.getByRole('link', { name: nombre, exact: true }).click()
  await pagina.waitForTimeout(700)
  const ruta = new URL(pagina.url()).pathname
  if (!ruta.endsWith(`/${cola}`)) {
    fallos.push(`«${nombre}» no tiene dirección propia: la ruta es ${ruta}`)
  }
}
console.log('  cada sección tiene su dirección')

// 4 · El Resumen: introducción + mapa de TODOS los activos.
await pagina.goto(`${BASE}/proyectos/${proyecto.id}`)
await pagina.waitForSelector('.texto-introduccion', { timeout: 10000 })
await pagina.waitForTimeout(1800)
const situadosCartera = await pagina.locator('.mapa-de-la-cartera .mapa-activos .ayuda').innerText()
console.log('  mapa de la cartera:', situadosCartera.replace(/\s+/g, ' ').trim())
if (!situadosCartera.includes('2')) {
  fallos.push(`El mapa del Resumen no sitúa los dos activos: «${situadosCartera.trim()}»`)
}
const chinchetas = await pagina.locator('.mapa-de-la-cartera .leaflet-marker-icon').count()
if (chinchetas !== 2) fallos.push(`El mapa del Resumen pinta ${chinchetas} chinchetas y hay 2 activos`)

// 5 · El detalle del activo, con SU mapa y una sola chincheta.
await pagina.goto(`${BASE}/proyectos/${proyecto.id}/activos/${activo.id}`)
await pagina.waitForSelector('.mapa-del-activo', { timeout: 10000 })
await pagina.waitForTimeout(1800)
const unaSola = await pagina.locator('.mapa-del-activo .leaflet-marker-icon').count()
console.log(`  mapa del activo: ${unaSola} chincheta`)
if (unaSola !== 1) fallos.push(`El mapa del detalle pinta ${unaSola} chinchetas y debería pintar 1`)

// 6 · La introducción se guarda y vuelve.
const TEXTO = 'Due diligence técnica de dos naves logísticas en polígono ficticio.'
await pagina.goto(`${BASE}/proyectos/${proyecto.id}`)
await pagina.waitForSelector('.texto-introduccion', { timeout: 10000 })
await pagina.getByLabel('Introducción del proyecto').fill(TEXTO)
const respuesta = pagina.waitForResponse(
  (r) => r.url().includes(`/projects/${proyecto.id}`) && r.request().method() === 'PATCH',
  { timeout: 15000 },
)
await pagina.getByRole('button', { name: 'Guardar la introducción' }).click()
const r = await respuesta
if (!r.ok()) fallos.push(`Guardar la introducción respondió ${r.status()}`)
const guardado = await api('GET', `/projects/${proyecto.id}`, null, tk)
if (guardado.summary_text !== TEXTO) {
  fallos.push(`La introducción no ha llegado a la base: «${guardado.summary_text}»`)
} else {
  console.log('  la introducción se guarda')
}
await pagina.reload()
await pagina.waitForSelector('.texto-introduccion', { timeout: 10000 })
if ((await pagina.getByLabel('Introducción del proyecto').inputValue()) !== TEXTO) {
  fallos.push('La introducción no vuelve al recargar')
}

// 7 · La palabra «encargo» no aparece en ninguna de las pantallas del recorrido.
for (const ruta of [
  `/proyectos/${proyecto.id}`,
  `/proyectos/${proyecto.id}/activos`,
  `/proyectos/${proyecto.id}/activos/${activo.id}`,
  `/proyectos/${proyecto.id}/activos/${activo.id}/visita`,
  `/proyectos/${proyecto.id}/dashboard`,
]) {
  await pagina.goto(BASE + ruta)
  await pagina.waitForTimeout(900)
  const texto = await pagina.locator('body').innerText()
  if (/\bencargos?\b/i.test(texto)) {
    fallos.push(`«encargo» sigue en pantalla en ${ruta}: se llama proyecto`)
  }
}
console.log('  ninguna pantalla dice «encargo»')

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log(
  'Cinco pestañas de proyecto, un espacio por activo con sus cinco secciones, ' +
    'la introducción se guarda y los dos mapas sitúan activos.',
)

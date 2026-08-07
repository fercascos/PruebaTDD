/**
 * ¿Sale ya el sistema técnico en el nombre del fichero? `[REQ]` §3.2 · §15.4
 *
 * Este defecto llevaba tiempo delante y nadie lo vio, porque el nombre que
 * producía era plausible: la plantilla por defecto es
 * `[Proyecto]_[Activo]_[Sistema]_[Zona]_[Numero]` y la fotografía no guardaba
 * el sistema en ninguna parte, así que **todo renombrado en lote escribía
 * «SinSistema»**. `2026-014_NaveA_SinSistema_Cubierta_001` no parece roto.
 *
 * Lo que se comprueba aquí y no en una unitaria:
 *
 * 1. Que clasificar desde la pantalla llega al nombre propuesto.
 * 2. Que la previsualización del renombrado lo enseña **antes** de aplicar.
 * 3. Que una foto sin clasificar se distingue en la rejilla, porque es la que
 *    va a salir «SinSistema».
 *
 *     make run &
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-sistema-de-fotos.mjs
 */
import { readFile } from 'node:fs/promises'
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

const sufijo = Math.random().toString(16).slice(2, 8)
const { access_token: tk } = await api('POST', '/auth/login', { email: CORREO, password: CLAVE })
const cli = await api('POST', '/clients', { name: 'Inversora Ficticia S.L.' }, tk)
const proyecto = await api(
  'POST',
  '/projects',
  { client_id: cli.id, internal_code: `2026-${sufijo}`, name: 'Encargo con fotos' },
  tk,
)
const tipologias = await api('GET', '/catalogs/asset-typologies', null, tk)
const activo = await api(
  'POST',
  `/projects/${proyecto.id}/assets`,
  { name: 'Nave Norte', typology_id: tipologias[0].id, asset_code: 'NN' },
  tk,
)
const sistemas = await api('GET', '/catalogs/technical-systems', null, tk)
const clima = sistemas.find((s) => s.code === 'CLIMA')

// Dos fotografías sintéticas —un degradado, no material de cliente— para poder
// distinguir la clasificada de la que no lo está.
const jpeg = await readFile(new URL('./foto-de-prueba.jpg', import.meta.url))
async function subir(nombre, extra = {}) {
  const f = new FormData()
  // Un byte distinto por foto: el índice único por `sha256` del proyecto es real.
  const variado = Buffer.concat([jpeg, Buffer.from(nombre)])
  f.append('file', new Blob([variado], { type: 'image/jpeg' }), nombre)
  f.append('asset_id', activo.id)
  for (const [k, v] of Object.entries(extra)) f.append(k, v)
  const r = await fetch(`${API}/projects/${proyecto.id}/photos`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${tk}` },
    body: f,
  })
  if (!r.ok) throw new Error(`subida -> ${r.status}: ${(await r.text()).slice(0, 300)}`)
  return r.json()
}
const clasificada = await subir('IMG_0001.jpg', { technical_system_id: clima.id })
await subir('IMG_0002.jpg')
console.log('· Dos fotos: una de climatización y otra sin clasificar')

if (clasificada.technical_system_id !== clima.id) {
  fallos.push('La subida no ha guardado el sistema técnico')
}

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

await pagina.goto(`${BASE}/proyectos/${proyecto.id}/fotos`)
await pagina.waitForSelector('.rejilla li', { timeout: 10000 })
console.log('· Pestaña de fotografías abierta')

// 1 · La que no está clasificada se distingue: es la que saldrá «SinSistema».
const marcas = await pagina.locator('.rejilla li').allInnerTexts()
const sinSistema = marcas.filter((m) => m.includes('sin sistema')).length
console.log(`  fotos marcadas «sin sistema»: ${sinSistema} de ${marcas.length}`)
if (sinSistema !== 1) {
  fallos.push(`Se esperaba 1 foto marcada «sin sistema», hay ${sinSistema}`)
}

// 2 · El filtro por sistema deja solo la clasificada.
await pagina.selectOption('.filtro label:has-text("y del sistema") select', { label: 'Climatización' })
await pagina.waitForFunction(
  () => document.querySelectorAll('.rejilla li').length === 1,
  null,
  { timeout: 5000 },
)
console.log('  el filtro por sistema deja 1')
await pagina.selectOption('.filtro label:has-text("y del sistema") select', '')
await pagina.waitForFunction(() => document.querySelectorAll('.rejilla li').length === 2, null, {
  timeout: 5000,
})

// 3 · **El defecto.** Se selecciona la clasificada y se previsualiza el
//     renombrado con la plantilla por defecto.
await pagina.locator('.rejilla li').first().locator('input[type="checkbox"]').check()
await pagina.click('.barra-seleccion button:has-text("Renombrar")')
await pagina.waitForSelector('.dialogo', { timeout: 10000 })
await pagina.click('.dialogo button:has-text("Previsualizar")')
await pagina.waitForSelector('.dialogo table tbody tr', { timeout: 10000 })
const propuesto = await pagina.locator('.dialogo table tbody tr').first().innerText()
console.log('  nombre propuesto:', propuesto.replace(/\s+/g, ' ').trim())

if (propuesto.includes('SinSistema')) {
  fallos.push('Una foto CLASIFICADA sigue produciendo «SinSistema» en el nombre')
}
if (!propuesto.includes(clima.code)) {
  fallos.push(`El código del sistema (${clima.code}) no aparece en el nombre propuesto`)
}
// Y el activo sale por su código, no por su nombre largo: §15.4 dice
// «asset_code o name», y la consulta usaba solo el nombre.
if (!propuesto.includes('NN')) {
  fallos.push('El código del activo no llega al nombre: sale el nombre largo')
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log('El sistema técnico llega al nombre del fichero y lo sin clasificar se ve.')

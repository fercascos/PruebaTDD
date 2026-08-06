/**
 * ¿Se puede anotar una fotografía de verdad? `[REQ]` §15.2
 *
 * Un lienzo no se prueba con vitest: no hay `getBoundingClientRect` real, ni
 * puntero, ni imagen que cargar. Lo único que demuestra que la herramienta
 * funciona es arrastrar el ratón sobre ella y ver qué se guarda.
 *
 * Se comprueban las tres cosas que pueden salir mal y no se ven leyendo código:
 * que el arrastre produce una forma, que las coordenadas salen **en fracción
 * del lado** —el fallo clásico de las anotaciones— y que un clic sin arrastrar
 * no crea una forma invisible.
 *
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-anotador.mjs
 *
 * Necesita la API en :8000 con el administrador de `make db-admin`.
 */
import { readFile } from 'node:fs/promises'
import { chromium } from 'playwright'

const BASE = process.env.URL_BASE ?? 'http://localhost:4173'
const API = process.env.URL_API ?? 'http://localhost:8000/api/v1'
const CORREO = process.env.TDD_EMAIL ?? 'admin@ejemplo.example'
const CLAVE = process.env.TDD_PASSWORD ?? 'cubierta invertida 2026'

const fallos = []

// ── Preparar un encargo con una foto, por API ────────────────────────────────
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

const sesion = await api('POST', '/auth/login', { email: CORREO, password: CLAVE })
const tk = sesion.access_token
const cliente = await api('POST', '/clients', { name: 'Inversora Ficticia S.L.' }, tk)
const proyecto = await api(
  'POST',
  '/projects',
  {
    client_id: cliente.id,
    internal_code: `2026-${Math.random().toString(16).slice(2, 8)}`,
    name: 'Encargo para anotar',
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

// Una fotografía sintética: un degradado, no material de cliente. `[REQ]` No
// se versionan fotos reales de activos identificables.
const jpeg = await readFile(new URL('./foto-de-prueba.jpg', import.meta.url))
const formulario = new FormData()
formulario.append('file', new Blob([jpeg], { type: 'image/jpeg' }), 'IMG_0001.jpg')
formulario.append('asset_id', activo.id)
const subida = await fetch(`${API}/projects/${proyecto.id}/photos`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${tk}` },
  body: formulario,
})
if (!subida.ok) throw new Error(`subida -> ${subida.status}: ${(await subida.text()).slice(0, 300)}`)
const foto = await subida.json()
console.log('· Encargo y fotografía preparados')

// ── Entrar y llegar al lienzo ────────────────────────────────────────────────
const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
)
const contexto = await navegador.newContext()
const pagina = await contexto.newPage()
pagina.on('pageerror', (e) => fallos.push(`Error en la página: ${e.message}`))

await pagina.goto(BASE)
await pagina.fill('input[type="email"]', CORREO)
await pagina.fill('input[type="password"]', CLAVE)
await pagina.click('button[type="submit"]')
await pagina.waitForURL('**/proyectos', { timeout: 10000 })
console.log('· Sesión iniciada')

await pagina.goto(`${BASE}/proyectos/${proyecto.id}/fotos`)
await pagina.getByRole('button', { name: /miniatura|IMG_0001/i }).first().click({ timeout: 10000 })
  .catch(async () => {
    // La miniatura es un botón sin texto: se pincha por clase.
    await pagina.locator('.miniatura').first().click({ timeout: 10000 })
  })
await pagina.getByRole('button', { name: 'Anotar' }).click({ timeout: 10000 })
await pagina.waitForSelector('.anotador canvas', { timeout: 10000 })
console.log('· Lienzo abierto')

// ── Dibujar arrastrando ──────────────────────────────────────────────────────
const caja = await pagina.locator('.anotador canvas').boundingBox()
async function arrastrar(x1, y1, x2, y2) {
  await pagina.mouse.move(caja.x + caja.width * x1, caja.y + caja.height * y1)
  await pagina.mouse.down()
  await pagina.mouse.move(caja.x + caja.width * x2, caja.y + caja.height * y2, { steps: 8 })
  await pagina.mouse.up()
}

await arrastrar(0.2, 0.2, 0.7, 0.6)
let etiqueta = await pagina.getByRole('button', { name: /Guardar \d+ anotaciones/ }).textContent()
console.log('  tras arrastrar:', etiqueta.trim())
if (!/Guardar 1 anotaciones/.test(etiqueta)) {
  fallos.push('Arrastrar sobre el lienzo no ha creado ninguna forma')
}

// Un clic sin arrastrar no debe crear una forma invisible.
await pagina.mouse.click(caja.x + caja.width * 0.5, caja.y + caja.height * 0.5)
etiqueta = await pagina.getByRole('button', { name: /Guardar \d+ anotaciones/ }).textContent()
console.log('  tras un clic suelto:', etiqueta.trim())
if (!/Guardar 1 anotaciones/.test(etiqueta)) {
  fallos.push('Un clic sin arrastrar ha creado una forma de tamaño cero')
}

// ── Guardar y comprobar lo que llegó al servidor ─────────────────────────────
await pagina.getByRole('button', { name: /Guardar 1 anotaciones/ }).click()
await pagina.waitForTimeout(1200)

const versiones = await api('GET', `/photos/${foto.id}/versions`, null, tk)
const anotada = versiones.find((v) => v.version_type === 'ANOTADA')
console.log('· Versión guardada:', anotada ? anotada.version_type : 'ninguna')
if (!anotada) {
  fallos.push('No se ha creado la versión anotada')
} else {
  const forma = anotada.annotations.shapes[0]
  console.log('  forma:', JSON.stringify(forma))
  if (!forma) {
    fallos.push('La capa guardada no lleva ninguna forma')
  } else {
    // Lo que de verdad importa: fracción del lado, no píxeles del lienzo.
    for (const clave of ['x1', 'y1', 'x2', 'y2']) {
      if (!(forma[clave] >= 0 && forma[clave] <= 1)) {
        fallos.push(`«${clave}» vale ${forma[clave]}: no está en fracción del lado`)
      }
    }
    // Y que apunte donde se arrastró, con holgura por el redondeo del ratón.
    if (Math.abs(forma.x1 - 0.2) > 0.05 || Math.abs(forma.y2 - 0.6) > 0.05) {
      fallos.push(
        `La forma no coincide con el arrastre: ${JSON.stringify(forma)} para (0.2,0.2)-(0.7,0.6)`,
      )
    }
  }
  if (anotada.stored_object_id !== null) {
    fallos.push('Se ha duplicado el binario: la capa debe ser vectorial')
  }
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log('Se dibuja sobre la foto y la capa se guarda en fracción del lado.')

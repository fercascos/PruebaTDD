/**
 * ¿Se ven las fotografías sobre el mapa? `[REQ]` §15.9
 *
 * Leaflet mide el contenedor, calcula el encuadre y coloca las chinchetas en
 * píxeles: nada de eso ocurre en vitest, donde no hay layout. La única forma de
 * saber si el mapa funciona es abrirlo y contar las chinchetas.
 *
 * Se comprueban las tres cosas que pueden fallar sin que se note leyendo código:
 * que las chinchetas aparecen, que el encuadre las deja **todas dentro** del
 * recuadro visible —un `fitBounds` mal hecho abre sobre el Atlántico— y que el
 * recuento de fotos sin coordenadas se enseña en vez de callarse.
 *
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-mapa.mjs
 *
 * Necesita la API con el administrador de `make db-admin`.
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

const { access_token: tk } = await api('POST', '/auth/login', {
  email: CORREO,
  password: CLAVE,
})
const cliente = await api('POST', '/clients', { name: 'Inversora Ficticia S.L.' }, tk)
const proyecto = await api(
  'POST',
  '/projects',
  {
    client_id: cliente.id,
    internal_code: `2026-${Math.random().toString(16).slice(2, 8)}`,
    name: 'Encargo con mapa',
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

// Fotografías sintéticas ya geolocalizadas por la API de pruebas: aquí se
// suben las tres que trae el repositorio, con EXIF puesto por el backend.
// `[REQ]` No hay material de cliente: son degradados con GPS inventado.
const jpeg = await readFile(new URL('./foto-de-prueba.jpg', import.meta.url))

/**
 * Cada subida lleva unos bytes distintos al final del fichero.
 *
 * Sin eso, la segunda copia de la misma imagen choca con el detector de
 * duplicados exactos (`UNIQUE (project_id, sha256)`) y devuelve un 409: la
 * comprobación se quedaba con una sola chincheta y parecía que el mapa no
 * pintaba las demás. Un comentario JPEG al final no altera la imagen.
 */
let variante = 0
async function subir(nombre) {
  const sufijo = Buffer.from(`\u0000variante-${variante++}`)
  const unica = Buffer.concat([jpeg, sufijo])
  const fd = new FormData()
  fd.append('file', new Blob([unica], { type: 'image/jpeg' }), nombre)
  fd.append('asset_id', activo.id)
  const r = await fetch(`${API}/projects/${proyecto.id}/photos`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${tk}` },
    body: fd,
  })
  const texto = await r.text()
  // Un duplicado exacto (409) es esperable: la misma imagen dos veces.
  return r.ok ? JSON.parse(texto) : null
}

const foto = await subir('IMG_MAPA.jpg')
if (!foto) throw new Error('no se ha podido subir la fotografía de prueba')

// El EXIF de la imagen del repositorio no lleva GPS, así que se ponen las
// coordenadas por la vía que usaría cualquier corrección manual: la base. Aquí
// no hay endpoint para escribirlas a propósito —§15.6, no se inventa una
// posición—, así que se usa el propio SQL de administración.
const { execSync } = await import('node:child_process')
const COORDS = [
  [40.4153, -3.6844],
  [40.472, -3.6828],
  [40.4262, -3.6903],
]
const ids = [foto.id]
for (let i = 1; i < COORDS.length; i++) {
  const otra = await subir(`IMG_MAPA_${i}.jpg`)
  if (otra) ids.push(otra.id)
}
// Una foto más SIN coordenadas: es la que debe salir en el recuento.
await subir('IMG_SIN_GPS.jpg')

for (const [i, id] of ids.entries()) {
  const [lat, lon] = COORDS[i % COORDS.length]
  execSync(
    `psql -h /tmp -p 55432 -U postgres -q -d tdd -c ` +
      `"UPDATE photo SET gps_latitude=${lat}, gps_longitude=${lon} WHERE id='${id}'"`,
  )
}
const situadas = ids.length
console.log(`· ${situadas} fotografías situadas y alguna sin coordenadas`)

// ── El mapa en el navegador ──────────────────────────────────────────────────
const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
)
const contexto = await navegador.newContext({ viewport: { width: 1280, height: 900 } })
const pagina = await contexto.newPage()
pagina.on('pageerror', (e) => fallos.push(`Error en la página: ${e.message}`))

await pagina.goto(BASE)
await pagina.fill('input[type="email"]', CORREO)
await pagina.fill('input[type="password"]', CLAVE)
await pagina.click('button[type="submit"]')
await pagina.waitForURL('**/proyectos', { timeout: 10000 })

await pagina.goto(`${BASE}/proyectos/${proyecto.id}/mapa`)
await pagina.waitForSelector('.leaflet-container', { timeout: 15000 })
await pagina.waitForTimeout(1200)
console.log('· Mapa abierto')

const chinchetas = await pagina.locator('.chincheta').count()
console.log('  chinchetas:', chinchetas)
if (chinchetas !== situadas) {
  fallos.push(`Se esperaban ${situadas} chinchetas y hay ${chinchetas}`)
}

// El encuadre tiene que dejarlas TODAS dentro del recuadro visible. Un
// `fitBounds` mal hecho abre el mapa sobre el Atlántico y hay que buscarlas.
const mapa = await pagina.locator('.leaflet-container').boundingBox()
for (let i = 0; i < chinchetas; i++) {
  const c = await pagina.locator('.chincheta').nth(i).boundingBox()
  const dentro =
    c && c.x >= mapa.x - 2 && c.y >= mapa.y - 2 &&
    c.x + c.width <= mapa.x + mapa.width + 2 &&
    c.y + c.height <= mapa.y + mapa.height + 2
  if (!dentro) fallos.push(`La chincheta ${i} queda fuera del recuadro visible`)
}
console.log('  todas dentro del encuadre:', !fallos.length)

// El recuento de las que no tienen coordenadas se enseña, no se calla.
const aviso = await pagina.locator('.mensaje.aviso').allTextContents()
const habla = aviso.some((t) => t.includes('sin coordenadas') || t.includes('no llevan coordenadas'))
console.log('  avisa de las fotos sin coordenadas:', habla)
if (!habla) fallos.push('El mapa no dice cuántas fotografías se quedan fuera')

// Y no se contacta con ningún servidor externo sin proveedor configurado.
const externas = []
pagina.on('request', (r) => {
  const url = new URL(r.url())
  if (url.origin !== new URL(BASE).origin) externas.push(r.url())
})
await pagina.reload({ waitUntil: 'networkidle' })
await pagina.waitForTimeout(1500)
console.log('  peticiones a servidores externos:', externas.length)
if (externas.length) {
  fallos.push(`Sin proveedor configurado no debería salir nada fuera: ${externas.join(', ')}`)
}

// Pinchar una chincheta abre su globo con el nombre del activo.
if (chinchetas > 0) {
  await pagina.locator('.chincheta').first().click()
  await pagina.waitForSelector('.leaflet-popup-content', { timeout: 5000 })
  const globo = await pagina.locator('.leaflet-popup-content').first().textContent()
  console.log('  globo:', JSON.stringify(globo.slice(0, 60)))
  if (!globo.includes('Edificio Norte')) {
    fallos.push('El globo no dice a qué activo pertenece la fotografía')
  }
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log('Las fotografías se ven situadas, encuadradas y sin salir a ningún servidor externo.')

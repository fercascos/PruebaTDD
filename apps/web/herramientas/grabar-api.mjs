/** Graba lo que la API contesta mientras se recorre la aplicación.
 *
 *  Es la mitad de datos del **prototipo navegable**: la otra mitad es la
 *  aplicación de verdad compilada a un solo fichero (`prototipo/`). En vez de
 *  escribir a mano un servidor de mentira —que envejece en cuanto la API
 *  cambia—, se recorre la aplicación con el navegador y se guarda cada
 *  respuesta tal cual sale. El prototipo la vuelve a servir desde dentro del
 *  navegador.
 *
 *  `[REQ]` Apúntelo **solo a una base de demostración con datos ficticios**: lo
 *  que grabe acaba dentro de un fichero que se puede compartir. Con datos de un
 *  cliente sería publicar su proyecto.
 *
 *      TDD_PROYECTO=<uuid> node apps/web/herramientas/grabar-api.mjs
 *
 *  `[LIM]` Graba **respuestas, no comportamiento**: el prototipo navega y filtra
 *  con lo grabado, pero no escribe. Lo que no se visite aquí, allí sale vacío.
 */
import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'
import { EN } from '../src/i18n/textos.ts'

const BASE = process.env.TDD_WEB ?? 'http://localhost:5173'
const CORREO = process.env.TDD_EMAIL ?? 'admin@ejemplo.example'
const CLAVE = process.env.TDD_PASSWORD ?? 'cubierta invertida 2026'
const PID = process.env.TDD_PROYECTO
const SALIDA = process.env.TDD_GRABACION ?? 'prototipo/grabacion.json'

/** El idioma en el que se graba. `[REQ]` S-05 · 0030 */
const IDIOMA = process.env.TDD_IDIOMA ?? 'es'
if (IDIOMA !== 'es' && IDIOMA !== 'en') {
  console.error(`TDD_IDIOMA tiene que ser «es» o «en», no «${IDIOMA}».`)
  process.exit(1)
}

/** El texto de un selector, en el idioma de la grabación.
 *
 *  `[REQ]` Este recorrido busca por **texto visible** —«Resumen», «Comprobar
 *  antes de generar»—, así que en inglés no encontraría nada y grabaría media
 *  aplicación sin que nada fallara: el fichero saldría más pequeño y el
 *  prototipo tendría pantallas vacías.
 *
 *  Se traduce con **el mismo diccionario que la aplicación**, no con una copia:
 *  el día que alguien cambie una traducción, este recorrido la sigue. Si
 *  faltara la entrada sale el castellano, el selector no encuentra nada y se
 *  ve en el recuento final.
 */
const t = (clave) => (IDIOMA === 'en' ? (EN[clave] ?? clave) : clave)

if (!PID) {
  console.error('Falta TDD_PROYECTO: el identificador del proyecto de demostración.')
  process.exit(1)
}

const nav = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH })
const ctx = await nav.newContext({
  viewport: { width: 1440, height: 950 },
  // `[REQ]` La aplicación elige su idioma inicial de lo guardado y, si no hay
  // nada, de `navigator.language`. Fijarlo aquí hace dos cosas de una: la
  // interfaz arranca en el idioma pedido Y las peticiones salen con el
  // `Accept-Language` que hace que la API devuelva los catálogos traducidos.
  locale: IDIOMA === 'en' ? 'en-GB' : 'es-ES',
})
// Y por si acaso, lo guardado: es lo primero que mira la aplicación, y así la
// grabación no depende de que el navegador respete `locale`. **Antes de abrir
// la página**: un `addInitScript` puesto después no corre en las páginas que ya
// existen, así que la primera —la única que se usa— arrancaría sin él.
await ctx.addInitScript(
  (idioma) => {
    try {
      localStorage.setItem('tdd.idioma', idioma)
    } catch {
      // Almacenamiento bloqueado: queda el `locale` del contexto.
    }
  },
  IDIOMA,
)

const pg = await ctx.newPage()

/** clave `MÉTODO ruta?consulta` → respuesta. */
const grabacion = {}
const binarios = new Set()

pg.on('response', async (res) => {
  const url = new URL(res.url())
  if (!url.pathname.startsWith('/api/v1')) return
  const clave = `${res.request().method()} ${url.pathname}${url.search}`
  if (grabacion[clave]) return
  const tipo = res.headers()['content-type'] ?? 'application/json'
  try {
    if (tipo.startsWith('image/')) {
      const buf = await res.body()
      grabacion[clave] = { estado: res.status(), tipo, base64: buf.toString('base64') }
      binarios.add(clave)
    } else {
      grabacion[clave] = { estado: res.status(), tipo, texto: await res.text() }
    }
  } catch {
    // Una respuesta que ya no se puede leer no se graba: mejor un hueco
    // declarado que un cuerpo vacío que parece una respuesta válida.
  }
})

async function ver(ruta, espera = 1200) {
  await pg.goto(`${BASE}${ruta}`)
  await pg.waitForTimeout(espera)
}

// ── El recorrido ────────────────────────────────────────────────────────────
await ver('/entrar', 500)
await pg.fill('input[type="email"]', CORREO)
await pg.fill('input[type="password"]', CLAVE)
await pg.click('button[type="submit"]')
await pg.waitForURL('**/proyectos', { timeout: 15000 })
await pg.waitForTimeout(1200)

/** Las pestañas del proyecto, **tal como están hoy**.
 *
 *  `[REQ]` Esta lista estaba desfasada: nombraba `/documentacion`, `/fotos`,
 *  `/mapa`, `/equipo` y `/capex` como pestañas del proyecto, y hace tiempo que
 *  cuelgan **del activo** (`/activos/:id/...`). El efecto no era un error: era
 *  una grabación de 16 respuestas en vez de doscientas, y un prototipo con la
 *  mitad de las pantallas en blanco. Un recorrido que busca rutas que ya no
 *  existen no falla, simplemente no graba.
 *
 *  Se comprueba abajo: si una pestaña no deja ni una petición, se avisa.
 */
const PESTANAS = ['', '/activos', '/dashboard', '/riesgos', '/informes']

/** Y las del activo, que son las que llevan el grueso del trabajo. */
const SECCIONES_DEL_ACTIVO = ['', '/documentacion', '/visita', '/inventario', '/capex']

const vacias = []
for (const p of PESTANAS) {
  const antes = Object.keys(grabacion).length
  await ver(`/proyectos/${PID}${p}`)
  if (Object.keys(grabacion).length === antes) vacias.push(`/proyectos/${PID}${p}`)
}
for (const r of ['/plantillas', '/sugerencias', '/personas', '/proyectos']) await ver(r)

// El resumen del CAPEX y su filtro: viven detrás de un botón y de un
// desplegable, así que sus peticiones no salen solas. Está en `/dashboard`;
// la ruta `/capex` del proyecto dejó de existir y aquí seguía escrita.
await ver(`/proyectos/${PID}/dashboard`)
const resumen = pg.getByRole('tab', { name: t('Resumen') })
if (await resumen.count()) {
  await resumen.click()
  await pg.waitForTimeout(1500)
  const barras = pg.locator('.barras.elegibles .fila')
  for (let i = 0; i < (await barras.count()); i++) {
    await barras.nth(i).click()
    await pg.waitForTimeout(1200)
    await pg.locator('.fila.marcada').click() // vuelve al conjunto
    await pg.waitForTimeout(900)
  }
}

// Las fichas: hallazgo con su comparador, activo con su árbol, foto.
await ver(`/proyectos/${PID}/dashboard`)
const filas = pg.locator('.tabla.capex tbody tr:not(.cabecera-grupo) button.enlace')
for (let i = 0; i < Math.min(await filas.count(), 4); i++) {
  await ver(`/proyectos/${PID}/dashboard`)
  await filas.nth(i).click()
  await pg.waitForTimeout(1100)
  const precios = pg.locator(`button:has-text("${t('Ver referencias y validar el precio')}")`)
  if (await precios.count()) {
    await precios.first().click()
    await pg.waitForTimeout(900)
  }
}

// Los activos, y **las cinco secciones de cada uno**: ahí vive el trabajo de
// verdad —la documentación pedida, la visita, el inventario y el CAPEX del
// activo—, y es lo que el prototipo tiene que poder enseñar.
await ver(`/proyectos/${PID}/activos`)
const idsDeActivos = JSON.parse(
  grabacion[`GET /api/v1/projects/${PID}/assets`]?.texto ?? '[]',
).map((a) => a.id)
for (const idActivo of idsDeActivos) {
  for (const seccion of SECCIONES_DEL_ACTIVO) {
    await ver(`/proyectos/${PID}/activos/${idActivo}${seccion}`)
  }
}
console.log(`· ${idsDeActivos.length} activos × ${SECCIONES_DEL_ACTIVO.length} secciones`)

// Las fotografías: cuelgan de la visita del activo, no del proyecto.
for (const idActivo of idsDeActivos) {
  const ruta = `/proyectos/${PID}/activos/${idActivo}/visita`
  await ver(ruta)
  const fotos = pg.locator('.rejilla li button, .rejilla li a')
  for (let i = 0; i < Math.min(await fotos.count(), 4); i++) {
    await ver(ruta)
    await fotos.nth(i).click()
    await pg.waitForTimeout(1100)
  }
}

// La comprobación previa del informe, que es lo que decide si se genera.
await ver(`/proyectos/${PID}/informes`)
const previo = pg.locator(`button:has-text("${t('Comprobar antes de generar')}")`)
if (await previo.count()) {
  await previo.click()
  await pg.waitForTimeout(1500)
}

// ── Rellenar los cuerpos que el navegador no dejó leer ──────────────────────
// Las imágenes salían con el cuerpo VACÍO, y en el prototipo se veían como
// iconos rotos. La causa: la aplicación aborta la descarga al desmontar el
// componente —y en modo estricto React monta dos veces—, así que cuando se
// pedía el cuerpo ya no había nada que leer. Se vuelven a pedir aquí, contra la
// API y con su token, que es donde sí están enteras.
const API = process.env.TDD_API ?? 'http://127.0.0.1:8000/api/v1'
const entrada = await fetch(`${API}/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: CORREO, password: CLAVE }),
})
if (!entrada.ok) throw new Error(`No se pudo entrar en la API para rellenar: ${entrada.status}`)
const { access_token: token } = await entrada.json()

let rellenados = 0
for (const [clave, r] of Object.entries(grabacion)) {
  const vacio = r.base64 === '' || (r.texto === '' && r.estado === 200)
  if (!vacio || !clave.startsWith('GET ')) continue
  const res = await fetch(`${API.replace(/\/api\/v1$/, '')}${clave.slice(4)}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) continue
  const buf = Buffer.from(await res.arrayBuffer())
  if (r.base64 !== undefined) r.base64 = buf.toString('base64')
  else r.texto = buf.toString('utf-8')
  rellenados++
}
if (rellenados) console.log(`· rellenados ${rellenados} cuerpos que el navegador dejó vacíos`)

// ── La lista de proyectos se queda en el que sí se ha grabado ────────────────
// La base de demostración arrastra 45 proyectos de pruebas antiguas. En el
// prototipo salían todos y **pulsar cualquiera llevaba a una pantalla rota**,
// porque de ésos no hay nada grabado. Un prototipo en el que la mayoría de los
// clics no lleva a ninguna parte no es un prototipo: es una trampa.
const listado = grabacion['GET /api/v1/projects']
if (listado?.texto) {
  const todos = JSON.parse(listado.texto)
  const lista = Array.isArray(todos) ? todos : (todos.items ?? [])
  const solo = lista.filter((p) => p.id === PID)
  listado.texto = JSON.stringify(Array.isArray(todos) ? solo : { ...todos, items: solo })
  console.log(`· la lista de proyectos pasa de ${lista.length} a ${solo.length}`)
}

if (vacias.length) {
  console.log(
    `\n${vacias.length} rutas no han dejado NINGUNA peticion nueva. Si la pantalla pide ` +
      `datos, la ruta ya no existe y este recorrido esta desfasado —paso una vez, y el ` +
      `prototipo salio con la mitad de las pantallas en blanco—. Si solo reusa lo que ya ` +
      `trajo la pantalla de arriba, es normal:\n  ${vacias.join('\n  ')}`,
  )
}

await mkdir(dirname(SALIDA), { recursive: true })
await writeFile(SALIDA, JSON.stringify(grabacion, null, 1))
const bytes = (await import('node:fs')).statSync(SALIDA).size
console.log(
  `${Object.keys(grabacion).length} respuestas (${binarios.size} imágenes) · ` +
    `${(bytes / 1024 / 1024).toFixed(2)} MB · idioma ${IDIOMA} · ${SALIDA}`,
)
await nav.close()

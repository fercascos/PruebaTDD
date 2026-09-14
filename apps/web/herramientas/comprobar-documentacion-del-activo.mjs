/**
 * ¿Es el árbol documental del activo el que pidió el cliente? `[REQ]` §3.2 b.
 *
 * Siete cosas que no se ven en una prueba de API:
 *
 * 1. **Que sea el árbol de la hoja v2**: 73 nodos y 60 casillas, en el orden
 *    del cliente y no en el alfabético.
 * 2. **Que nazca plegado.** Son nodos con nombres de hasta trescientos
 *    caracteres: abiertos de golpe es una pantalla de varios metros.
 * 3. **Que un nodo que agrupa no ofrezca estado**, porque marcarlo no diría
 *    nada de lo que cuelga de él.
 * 4. **Que poner un estado se guarde** y que la casilla cambie de color: el
 *    borde de la izquierda es lo que se recorre con la vista.
 * 5. **Que «no disponible» pida el motivo antes de enviarlo**, y no después con
 *    un error rojo del servidor.
 * 6. **Que adjuntar cuelgue el documento de su casilla** y la dé por recibida
 *    sin pedir dos gestos para una sola cosa.
 * 7. **Que se reabra solo lo que ya tiene trabajo hecho** al volver a entrar.
 *
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-documentacion-del-activo.mjs
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
// `[REQ]` La fase documental **se elige a la carta** al dar de alta el proyecto,
// y el árbol vive en ella: sin marcarla aquí la pantalla dice que falta.
const proyecto = await api(
  'POST',
  '/projects',
  {
    client_id: cli.id,
    name: 'Activo con documentación',
    applicable_phases: [{ code: 'SOLICITUD_DOCUMENTACION' }],
  },
  tk,
)
const tipologias = await api('GET', '/catalogs/asset-typologies', null, tk)
const activo = await api(
  'POST',
  `/projects/${proyecto.id}/assets`,
  { name: 'Nave Norte', typology_id: tipologias.find((t) => t.code === 'INDUSTRIAL').id },
  tk,
)
console.log('· Proyecto con fase documental y un activo sin nada pedido')

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

await pagina.goto(`${BASE}/proyectos/${proyecto.id}/activos/${activo.id}/documentacion`)
await pagina.waitForSelector('.arbol-documental .cabecera-doc', { timeout: 10000 })
console.log('· Árbol documental abierto')

/** La cabecera de una rama, por su código. */
function rama(code) {
  return pagina.locator('.cabecera-doc').filter({
    has: pagina.locator('.codigo', { hasText: new RegExp(`^${code.replace(/\./g, '\\.')}$`) }),
  })
}

/** La ficha de una casilla. El id lleva guiones: `S1.2.1` no vale en CSS.
 *
 * Se filtra por **visible**: una casilla dentro de una rama plegada sigue en el
 * DOM, así que contar nodos sin más dice que está abierta cuando no lo está.
 */
function casilla(code) {
  return pagina.locator(`#doc-${code.replace(/\./g, '-')}:visible`)
}

/** Espera a que la pantalla termine de guardar.
 *
 * `aria-busy` y no `.mensaje.ok`: el aviso de la operación anterior sigue ahí,
 * así que esperarlo vuelve al instante y lo siguiente pisa una petición en
 * vuelo. Es el mismo fallo que apareció en el inventario.
 */
async function reposo() {
  await pagina.waitForSelector('.arbol-documental[aria-busy="false"]', { timeout: 15000 })
}

async function abrir(code) {
  const cabecera = rama(code)
  if ((await cabecera.getAttribute('aria-expanded')) === 'false') await cabecera.click()
}

// 1 · Es el árbol del cliente, con sus cuatro raíces.
const raices = await pagina.locator('.cabecera-doc.n1').count()
console.log(`  ${raices} raíces del árbol`)
// S1, S2 y S3 agrupan; S4 «Q&A» no tiene hijos y por eso es casilla, no rama.
if (raices !== 3) fallos.push(`El árbol enseña ${raices} raíces con hijos, se esperaban 3`)
if ((await casilla('S4').count()) !== 1) {
  fallos.push('«S4 · Q&A» no sale como casilla, y es un nodo de nivel 1 sin hijos')
}
const resumen = await pagina.locator('.arbol-documental .ayuda').innerText()
if (!resumen.includes('73 nodos') || !resumen.includes('60 casillas')) {
  fallos.push(`El resumen no dice 73 nodos y 60 casillas: «${resumen.slice(0, 120)}»`)
}

// 2 · Nace plegado: ninguna casilla a la vista antes de tocar nada.
const visiblesDeEntrada = await pagina.locator('.ficha-doc:visible').count()
console.log(`  ${visiblesDeEntrada} casilla(s) visibles al entrar`)
// Solo `S4`, que cuelga de la raíz y no de ninguna rama plegable.
if (visiblesDeEntrada > 1) {
  fallos.push(
    `El árbol nace con ${visiblesDeEntrada} casillas abiertas y tenía que nacer plegado`,
  )
}

// 3 · Un nodo que agrupa no ofrece estado.
await abrir('S1')
if ((await rama('S1.1').count()) !== 1) fallos.push('Abrir S1 no enseña sus categorías')
if ((await casilla('S1.1').count()) !== 0) {
  fallos.push('«S1.1 Licencias urbanísticas» ofrece estado, y agrupa a cuatro licencias')
}
await abrir('S1.1')
if ((await casilla('S1.1.1').count()) !== 1) fallos.push('Abrir S1.1 no enseña sus licencias')

// 4 · Poner un estado se guarda y se ve.
await casilla('S1.1.1').getByLabel('Estado de S1.1.1').selectOption('RECIBIDA')
await reposo()
if (!(await casilla('S1.1.1').getAttribute('class')).includes('e-recibida')) {
  fallos.push('Marcar «recibida» no cambia el color de la casilla')
} else {
  console.log('  la casilla marcada como recibida se distingue por su borde')
}
// Y la rama de arriba lo cuenta sin abrirla.
const marca = await rama('S1.1').locator('.marca-doc').innerText()
if (!marca.startsWith('1/4')) {
  fallos.push(`La rama S1.1 dice «${marca}» y tenía que decir 1 de 4`)
}

// 5 · «No disponible» pide el motivo antes de enviarlo.
await casilla('S1.1.2').getByLabel('Estado de S1.1.2').selectOption('NO_DISPONIBLE')
await reposo()
const aviso = await pagina.locator('.mensaje.error').first().innerText()
if (!aviso.toLowerCase().includes('por qué')) {
  fallos.push(`Marcar «no disponible» sin motivo no lo pide: «${aviso.slice(0, 120)}»`)
} else {
  console.log('  «no disponible» sin motivo se para en la pantalla, no en el servidor')
}
if ((await casilla('S1.1.2').getAttribute('class')).includes('e-no_disponible')) {
  fallos.push('La casilla se ha marcado «no disponible» sin motivo')
}

// 6 · Adjuntar cuelga el documento de su casilla y la da por recibida.
const PDF = Buffer.from(
  '%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n',
)
await casilla('S1.1.3')
  .getByLabel('Adjuntar documentos a S1.1.3')
  .setInputFiles({ name: 'licencia.pdf', mimeType: 'application/pdf', buffer: PDF })
await reposo()
const adjuntos = await casilla('S1.1.3').locator('.adjuntos-doc li').count()
if (adjuntos !== 1) {
  fallos.push(`La casilla S1.1.3 enseña ${adjuntos} adjuntos y se ha subido uno`)
} else if (!(await casilla('S1.1.3').getAttribute('class')).includes('e-recibida')) {
  fallos.push('Adjuntar un documento no da la casilla por recibida')
} else {
  console.log('  adjuntar cuelga el documento y da la casilla por recibida de una vez')
}

// 7 · Al volver a entrar se reabre lo que ya tiene trabajo hecho.
await pagina.reload()
await pagina.waitForSelector('.arbol-documental .cabecera-doc', { timeout: 10000 })
await reposo()
if ((await casilla('S1.1.1').count()) !== 1) {
  fallos.push('Al volver a entrar, la rama con trabajo hecho vuelve a estar plegada')
} else {
  console.log('  la rama con trabajo hecho se abre sola al volver')
}
// Y S2, que sigue sin tocar, no: si se abriera todo no se distinguiría nada.
if ((await casilla('S2.1').count()) !== 0) {
  fallos.push('Se abre también una rama sin tocar, y eso es abrir el árbol entero')
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log(
  'La documentación del activo es el árbol de la hoja del cliente: 73 nodos, 60 casillas, ' +
    'estado por casilla, motivo obligatorio cuando falta y documentos colgando de cada una.',
)

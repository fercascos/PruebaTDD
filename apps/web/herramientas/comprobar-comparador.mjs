/**
 * ¿Hace el comparador de precios lo que promete? `[REQ]` §14
 *
 * Esta pantalla existe para cumplir tres frases que el cliente escribió, y las
 * tres se comprueban aquí **con el navegador delante**, no con una unitaria:
 *
 * 1. **«No inventes APIs ni fuentes de precios.»** Se registran todas las
 *    peticiones que sale de la página. Si alguna va a un tercero, esto falla.
 *    Es la única forma de comprobarlo de verdad: un `grep` por `fetch` no ve
 *    una imagen remota ni una fuente web.
 * 2. **«Nunca selecciones automáticamente un precio como definitivo sin
 *    revisión humana.»** Al abrir, ninguna fila viene marcada y el botón de
 *    validar está deshabilitado.
 * 3. **Decir lo que NO se ha mirado.** El bloque de fuentes no consultadas
 *    tiene que estar, con el motivo escrito.
 *
 * Y una cuarta que no es una frase del cliente sino sentido común: después de
 * validar, la línea tiene que decir **contra qué** se validó.
 *
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-comparador.mjs
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

const sufijo = Math.random().toString(16).slice(2, 8)

const { access_token: tk } = await api('POST', '/auth/login', { email: CORREO, password: CLAVE })
const cli = await api('POST', '/clients', { name: 'Inversora Ficticia S.L.' }, tk)
const proyecto = await api(
  'POST',
  '/projects',
  { client_id: cli.id, internal_code: `2026-${sufijo}`, name: 'Encargo con precios' },
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
const hallazgo = await api(
  'POST',
  `/projects/${proyecto.id}/findings`,
  {
    asset_id: activo.id,
    capex_code_id: codigos[0].id,
    zone_id: zonas[0].id,
    title: 'Enfriadora al final de su vida útil',
    description: 'Observada en visita.',
    capex_lines: [{ time_horizon_code: 'CORTO', amount: '40000.00' }],
  },
  tk,
)

// Una fuente manual con una referencia, y otra que NO se ha consultado: sin la
// segunda no hay nada que comprobar del bloque que da nombre a la pantalla.
const manual = await api(
  'POST',
  '/price-sources',
  { code: `MAN-${sufijo}`, name: 'Introducido a mano', source_type: 'MANUAL' },
  tk,
)
const externa = await api(
  'POST',
  '/price-sources',
  {
    code: `EXT-${sufijo}`,
    name: 'Base de precios licenciada',
    source_type: 'BASE_PRECIOS_LICENCIADA',
  },
  tk,
)
await api(
  'POST',
  '/price-references',
  {
    price_source_id: manual.id,
    description: 'Sustitución de enfriadora 300 kW',
    unit: 'ud',
    unit_price: '48500.00',
    price_date: '2025-11-01',
    geo_scope: 'ES-MAD',
    scope_included: 'Equipo, transporte y puesta en marcha',
    scope_excluded: 'Obra civil',
    provenance_note: 'Oferta adjunta del industrial',
  },
  tk,
)
console.log(`· Encargo ${proyecto.internal_code} con 1 referencia y 1 fuente no consultada`)

// ── La pantalla ──────────────────────────────────────────────────────────────
const navegador = await chromium.launch(
  process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {},
)
const contexto = await navegador.newContext({ viewport: { width: 1400, height: 1100 } })
const pagina = await contexto.newPage()
pagina.on('pageerror', (e) => fallos.push(`Error en la página: ${e.message}`))

// `[REQ]` «No inventes APIs ni fuentes de precios»: se anota TODO lo que sale.
const permitidos = new Set([new URL(BASE).host, new URL(API).host])
const ajenas = []
pagina.on('request', (p) => {
  const host = new URL(p.url()).host
  if (host && !permitidos.has(host)) ajenas.push(`${p.method()} ${p.url()}`)
})

await pagina.goto(BASE)
await pagina.fill('input[type="email"]', CORREO)
await pagina.fill('input[type="password"]', CLAVE)
await pagina.click('button[type="submit"]')
await pagina.waitForURL('**/proyectos', { timeout: 10000 })

await pagina.goto(`${BASE}/proyectos/${proyecto.id}/capex`)
await pagina.click(`button.enlace:has-text("${hallazgo.title}")`)
await pagina.waitForSelector('.linea-capex', { timeout: 10000 })

// La línea todavía no tiene procedencia y lo dice.
const antes = await pagina.locator('.linea-capex .procedencia').first().innerText()
console.log('· procedencia antes:', antes.replace(/\s+/g, ' ').trim())
if (!/sin procedencia/i.test(antes)) {
  fallos.push(`Una línea sin validar no avisa de que no tiene procedencia: «${antes}»`)
}

await pagina.click('button:has-text("Ver referencias y validar el precio")')
await pagina.waitForSelector('.comparador', { timeout: 10000 })
console.log('· Comparador abierto')

// 1 · Nada viene elegido y no se puede validar todavía.
const marcados = await pagina.locator('.comparador input[type="radio"]:checked').count()
if (marcados !== 0) fallos.push(`${marcados} referencia(s) vienen marcadas: nada debe elegirse solo`)
const validar = pagina.locator('.comparador .aplicar button:has-text("Validar precio")')
if (!(await validar.isDisabled())) {
  fallos.push('Se puede validar sin haber elegido referencia: un precio sin procedencia');
}
const aviso = await pagina.locator('.comparador .mensaje.aviso').first().innerText()
if (!/ninguna referencia se selecciona autom/i.test(aviso)) {
  fallos.push(`El aviso de que nada se elige solo no está el primero: «${aviso}»`)
}

// 2 · Lo que NO se ha consultado, con su motivo.
const noConsultadas = await pagina.locator('.no-consultadas').innerText()
console.log('· no consultadas:', noConsultadas.replace(/\s+/g, ' ').trim().slice(0, 160))
if (!noConsultadas.includes(externa.name)) {
  fallos.push('La fuente no habilitada no aparece en el bloque de no consultadas')
}
if (!/ninguna consulta automatizada/i.test(noConsultadas)) {
  fallos.push('El motivo de no consulta no dice que no se ha llamado a nadie')
}

// 3 · Elegir rellena el importe pero no lo cierra.
await pagina.locator('.tabla.referencias tbody tr').first().locator('input[type="radio"]').check()
const importe = pagina.locator('.comparador .aplicar input[type="number"]')
if (Number(await importe.inputValue()) !== 48500) {
  fallos.push(`Elegir la referencia no lleva su precio al importe: ${await importe.inputValue()}`)
}
if (await importe.isDisabled()) fallos.push('El importe queda bloqueado al elegir referencia')

// 4 · Un importe distinto exige explicación, y el servidor lo rechaza si falta.
await importe.fill('52000')
await pagina.waitForSelector('.comparador .aplicar .mensaje.aviso')
await validar.click()
await pagina.waitForSelector('.comparador .mensaje.error', { timeout: 10000 })
const rechazo = await pagina.locator('.comparador .mensaje.error').innerText()
console.log('· rechazo:', rechazo.replace(/\s+/g, ' ').trim().slice(0, 140))
if (!rechazo.includes('48500') || !rechazo.includes('52000')) {
  fallos.push(`El rechazo no enseña las dos cifras: «${rechazo}»`)
}

// 5 · Con explicación pasa, y la línea dice contra qué se validó.
await pagina.fill('.comparador textarea', 'Oferta en firme del industrial, incluye puesta en marcha.')
await validar.click()
await pagina.waitForSelector('.linea-capex .procedencia.p-validado', { timeout: 10000 })
const despues = await pagina.locator('.linea-capex .procedencia').first().innerText()
console.log('· procedencia después:', despues.replace(/\s+/g, ' ').trim())
for (const trozo of ['Validado', manual.name, 'Oferta en firme']) {
  if (!despues.includes(trozo)) fallos.push(`La procedencia no menciona «${trozo}»: «${despues}»`)
}
// El recuadro de la línea sigue al servidor. Fue un fallo real en su día: la
// pantalla enseñaba dos cifras distintas a la vez, la vieja en el campo y la
// nueva en el total.
const enLinea = pagina.locator('.linea-capex label:has-text("Importe") input').first()
if (Number(await enLinea.inputValue()) !== 52000) {
  fallos.push(`El campo de la línea no ha seguido al importe validado: ${await enLinea.inputValue()}`)
}

// 6 · La actualización por índice calcula, enseña la fórmula y NO aplica sola.
await pagina.click('button:has-text("Ver referencias y validar el precio")')
await pagina.waitForSelector('.comparador')
await pagina.click('button.enlace:has-text("Actualizar el precio por un índice")')
const indices = pagina.locator('.por-indice input[type="number"]')
await indices.nth(0).fill('112.7')
await indices.nth(1).fill('118.4')
await pagina.click('.por-indice button:has-text("Calcular")')
await pagina.waitForSelector('.por-indice .formula')
const formula = await pagina.locator('.por-indice .formula').innerText()
console.log('· fórmula:', formula)
// 52.000 × (118,4 / 112,7) × 1 = 54.629,99. Se comprueba la cuenta, no el
// texto: una fórmula bien escrita con el resultado mal es peor que ninguna.
const esperado = (52000 * 118.4) / 112.7
if (!formula.includes(esperado.toFixed(2))) {
  fallos.push(`La fórmula no da ${esperado.toFixed(2)}: «${formula}»`)
}
const importe2 = pagina.locator('.comparador .aplicar input[type="number"]')
if (Number(await importe2.inputValue()) !== 52000) {
  fallos.push(`Calcular por índice ha cambiado el importe solo: ${await importe2.inputValue()}`)
}

// 7 · Nadie ha salido a internet.
if (ajenas.length) {
  fallos.push(`La pantalla ha llamado a ${ajenas.length} destino(s) ajeno(s): ${ajenas[0]}`)
}
console.log(`· peticiones a terceros: ${ajenas.length}`)

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log('Nada se elige solo, se dice lo que no se ha mirado y no sale una petición a terceros.')

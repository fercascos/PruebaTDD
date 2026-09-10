/**
 * ¿Hace el inventario del activo lo que pidió el cliente? `[REQ]` §3.2 d.
 *
 * Seis cosas que no se ven en una prueba de API:
 *
 * 1. **Que el descriptivo se traiga de la documentación** y salga en la rejilla
 *    con el texto que dice la memoria, no con el nombre del catálogo.
 * 2. **Que nazca diciendo que está pendiente de validar por el gestor
 *    técnico.** Escrito, no insinuado con un color: esto se imprime.
 * 3. **Que el cuadro sea editable y se guarde.** Es literalmente lo que se
 *    pidió, y una rejilla que parece editable y no persiste es peor que una de
 *    solo lectura.
 * 4. **Que la casilla valide, y que no deje validar un descriptivo vacío**:
 *    sería firmar una casilla en blanco.
 * 5. **Que «pasa a CAPEX» no cree nada al marcarla** y que el botón genere las
 *    actuaciones de golpe, avisando del equipo cuyo capítulo no resuelve.
 * 6. **Que una fotografía se ate al equipo que retrata.**
 *
 *     npm run build && npx vite preview --port 4173 &
 *     node herramientas/comprobar-inventario-del-activo.mjs
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
const proyecto = await api(
  'POST',
  '/projects',
  { client_id: cli.id, name: 'Activo con inventario' },
  tk,
)
const tipologias = await api('GET', '/catalogs/asset-typologies', null, tk)
const codigos = await api('GET', '/catalogs/capex-codes', null, tk)
const sistemas = await api('GET', '/catalogs/technical-systems', null, tk)
const porCodigo = Object.fromEntries(codigos.map((c) => [c.code, c.id]))
const porSistema = Object.fromEntries(sistemas.map((s) => [s.code, s]))

const activo = await api(
  'POST',
  `/projects/${proyecto.id}/assets`,
  { name: 'Nave Norte', typology_id: tipologias.find((t) => t.code === 'INDUSTRIAL').id },
  tk,
)

// La memoria técnica, que es de donde salen hoy los descriptivos. Dos objetos
// codificados a nivel 3 y uno sin código, que tiene que salir en los avisos.
await api(
  'PUT',
  `/assets/${activo.id}/memoria`,
  {
    origen: 'MANUAL',
    es_simulada: false,
    categorias: [
      {
        capex_code_id: porCodigo['HC.H08'],
        objetos: [
          {
            capex_code_id: porCodigo['HC.H08.01'],
            nombre: 'Enfriadora de la cubierta',
            cantidad: '2',
            unidad: 'ud',
            notes: 'Refrigerante R-410A.',
          },
          { nombre: 'Climatizadora de oficinas' },
        ],
      },
      {
        capex_code_id: porCodigo['HC.H02'],
        objetos: [{ capex_code_id: porCodigo['HC.H02.01'], nombre: 'Lámina impermeabilizante' }],
      },
    ],
  },
  tk,
)

// El inventario: uno con sistema que resuelve a capítulo y otro cuyo sistema
// apunta a dos —«H06 + H10»—, que es el que tiene que salir en los avisos.
const enfriadora = await api(
  'POST',
  `/projects/${proyecto.id}/equipment`,
  {
    asset_id: activo.id,
    tag: 'CL-01',
    equipment_type: 'Enfriadora',
    manufacturer: 'Fabricante Ficticio',
    technical_system_id: porSistema.CLIMA.id,
    install_year: 1998,
    expected_life_years: 20,
  },
  tk,
)
await api(
  'POST',
  `/projects/${proyecto.id}/equipment`,
  {
    asset_id: activo.id,
    tag: 'BIE-01',
    equipment_type: 'BIE',
    technical_system_id: porSistema.PCI.id,
  },
  tk,
)

// Una fotografía de la visita, generada aquí: ni una foto real. `[REQ]`
const PIXEL = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
)
const formulario = new FormData()
formulario.append('file', new Blob([PIXEL], { type: 'image/png' }), 'IMG_0001.png')
formulario.append('asset_id', activo.id)
const subida = await fetch(`${API}/projects/${proyecto.id}/photos`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${tk}` },
  body: formulario,
})
if (!subida.ok) throw new Error(`No se ha podido subir la foto: ${await subida.text()}`)
const foto = await subida.json()

console.log('· Memoria, dos equipos y una fotografía cargados')

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

// `[REQ]` §3.2 · Cada sección del activo tiene su propia dirección desde
// que el espacio del activo existe: se entra por ella y no encadenando
// clics, que además comprueba que la ruta es la que se anuncia.
await pagina.goto(`${BASE}/proyectos/${proyecto.id}/activos/${activo.id}/inventario`)
await pagina.waitForSelector('.inventario-activo', { timeout: 10000 })
console.log('· Inventario abierto')

// 1 · Traer de la documentación.
await pagina.getByRole('button', { name: 'Traer de la documentación' }).click()
await pagina.waitForSelector('.tabla.descriptivos tbody tr', { timeout: 10000 })
const filas = pagina.locator('.tabla.descriptivos tbody tr')
const cuantas = await filas.count()
console.log(`  ${cuantas} descriptivos traídos`)
if (cuantas !== 2) {
  fallos.push(`Se han traído ${cuantas} descriptivos y la memoria codifica 2 objetos`)
}

/** La fila de un objeto, por su código. */
function fila(code) {
  return filas.filter({
    has: pagina.locator('.codigo', { hasText: new RegExp(`^${code.replace(/\./g, '\\.')}$`) }),
  })
}

const texto = await fila('HC.H08.01')
  .locator('textarea')
  .inputValue()
console.log('  descriptivo:', texto)
// Las palabras de la memoria, no el nombre del catálogo: «Producción de
// climatización» ya está en la columna de al lado.
if (!texto.includes('Enfriadora de la cubierta') || !texto.includes('R-410A')) {
  fallos.push(`El descriptivo no trae lo que dice la memoria: «${texto}»`)
}
if (texto.includes('2,00')) {
  fallos.push(`La cantidad se escribe con la escala de la columna: «${texto}»`)
}

// 1b · El objeto sin código sale avisado y no se inventa un descriptivo.
const avisos = await pagina.locator('.inventario-activo .mensaje.aviso').allInnerTexts()
console.log('  avisos:', avisos.length)
if (!avisos.some((a) => a.includes('no están codificados'))) {
  fallos.push('El objeto sin código del catálogo no se avisa')
}

// 2 · Nace pendiente de validar, y lo dice con letras.
const estado = await fila('HC.H08.01').locator('td.validacion').innerText()
console.log('  estado:', estado.replace(/\s+/g, ' ').trim())
if (!/pendiente de validar/i.test(estado)) {
  fallos.push(`La fila no dice que está pendiente de validar: «${estado}»`)
}
if (!/gestor técnico/i.test(estado)) {
  fallos.push(`No dice quién tiene que validarlo: «${estado}»`)
}

// 3 · El cuadro es editable y se guarda.
const CORRECCION = 'Dos enfriadoras aire-agua de 2004; el compresor de la nº2 está sustituido.'
await fila('HC.H08.01').locator('textarea').fill(CORRECCION)
await pagina.getByRole('button', { name: /^Guardar descriptivos/ }).click()
await pagina.waitForSelector('.inventario-activo .mensaje.ok', { timeout: 10000 })
const guardados = await api('GET', `/assets/${activo.id}/descriptivos`, null, tk)
const enBase = guardados.find((d) => d.capex_code === 'HC.H08.01')
if (enBase.texto !== CORRECCION) {
  fallos.push(`Lo editado no llega a la base: «${enBase.texto}»`)
} else {
  console.log('  la corrección se ha guardado')
}

// 4 · La casilla valida. Y sobre un descriptivo vacío no se puede marcar.
await fila('HC.H08.01')
  .getByRole('checkbox', { name: /Marcar como validado/ })
  .check()
await pagina.getByRole('button', { name: /^Guardar descriptivos/ }).click()
await pagina.waitForSelector('.tabla.descriptivos tr.validado', { timeout: 10000 })
const firmado = (await api('GET', `/assets/${activo.id}/descriptivos`, null, tk)).find(
  (d) => d.capex_code === 'HC.H08.01',
)
if (!firmado.validado_at || !firmado.validado_por) {
  fallos.push('La casilla marca validado sin dejar constancia de quién y cuándo')
} else {
  console.log(`  validado por ${firmado.validado_por_nombre}`)
}
const conFirma = await fila('HC.H08.01').locator('td.validacion').innerText()
if (!/Validado/.test(conFirma) || !/\d{4}-\d{2}-\d{2}/.test(conFirma)) {
  fallos.push(`La fila validada no enseña la firma: «${conFirma.replace(/\s+/g, ' ')}»`)
}

// La otra fila se vacía: su casilla tiene que quedar deshabilitada.
await fila('HC.H02.01').locator('textarea').fill('   ')
const casillaVacia = fila('HC.H02.01').getByRole('checkbox', { name: /Marcar como validado/ })
if (await casillaVacia.isEnabled()) {
  fallos.push('Se puede marcar como validado un descriptivo vacío: sería firmar en blanco')
} else {
  console.log('  un descriptivo vacío no se puede validar')
}

// 5 · «Pasa a CAPEX»: marcar no crea nada, el botón genera de golpe.
// `click()` y no `check()`: la casilla es controlada y solo se marca cuando
// vuelve el PATCH, así que `check()` —que verifica el estado nada más pulsar—
// da por fallado un guardado que sí está en camino. Se espera por la clase de
// la fila, que es lo que de verdad dice que el servidor lo aceptó.
for (const etiqueta of ['CL-01', 'BIE-01']) {
  await pagina
    .locator('.tabla.equipo-capex tbody tr')
    .filter({ hasText: etiqueta })
    .getByRole('checkbox')
    .click()
}
await pagina.waitForFunction(
  () => document.querySelectorAll('.tabla.equipo-capex tbody tr.marcado').length === 2,
  null,
  { timeout: 10000 },
)
const sinGenerar = await api('GET', `/projects/${proyecto.id}/findings?asset_id=${activo.id}`, null, tk)
if (sinGenerar.length !== 0) {
  fallos.push(`Marcar la casilla ya ha creado ${sinGenerar.length} actuación(es): no debería`)
} else {
  console.log('  marcar no crea nada')
}

await pagina.getByRole('button', { name: /Generar actuaciones de los marcados/ }).click()
await pagina.waitForSelector('.inventario-activo .mensaje.ok', { timeout: 10000 })
const generadas = await api('GET', `/projects/${proyecto.id}/findings?asset_id=${activo.id}`, null, tk)
console.log(`  ${generadas.length} actuación(es) generada(s)`)
// Solo la enfriadora: la BIE va a «H06 + H10» y elegir uno sería codificarla mal.
if (generadas.length !== 1 || !generadas[0].title.includes('CL-01')) {
  fallos.push(
    `Se esperaba una sola actuación, la de CL-01: ${generadas.map((h) => h.title).join(' / ')}`,
  )
}
const avisosCapex = await pagina.locator('.inventario-activo .mensaje.aviso').allInnerTexts()
if (!avisosCapex.some((a) => a.includes('BIE-01'))) {
  fallos.push('El equipo cuyo capítulo no resuelve no sale en los avisos')
} else {
  console.log('  el equipo sin capítulo único se avisa en vez de codificarse a ciegas')
}

// 6 · La fotografía se ata al equipo.
await pagina
  .locator('.tabla.fotos-equipo tbody tr')
  .first()
  .locator('select')
  .selectOption(enfriadora.id)
await pagina.waitForFunction(
  (id) => {
    const celda = document.querySelector('.tabla.equipo-capex tbody tr td:last-child')
    return celda && celda.textContent.trim() !== '0' && id
  },
  enfriadora.id,
  { timeout: 10000 },
)
const atada = await api('GET', `/photos/${foto.id}`, null, tk)
if (atada.equipment_id !== enfriadora.id) {
  fallos.push(`La fotografía no ha quedado atada al equipo: ${atada.equipment_id}`)
} else {
  console.log('  la fotografía queda atada a CL-01')
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log(
  'Los descriptivos se traen pendientes, se editan y se validan; «pasa a CAPEX» genera de una vez '
    + 'y la fotografía se ata al equipo.',
)

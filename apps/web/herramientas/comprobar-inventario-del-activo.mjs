/**
 * ¿Hace el inventario del activo lo que pidió el cliente? `[REQ]` §3.2 d.
 *
 * Ocho cosas que no se ven en una prueba de API:
 *
 * 1. **Que el inventario sea el árbol**: categorías, y dentro de cada categoría
 *    sus objetos. Es lo que se pidió al revisar el prototipo.
 * 2. **Que se abra solo lo que ya tiene trabajo hecho.** Ciento cuarenta y un
 *    objetos abiertos de golpe es una pantalla donde no se encuentra nada.
 * 3. **Que el descriptivo se traiga de la documentación** con el texto que dice
 *    la memoria, no con el nombre del catálogo.
 * 4. **Que la valoración sea otro cuadro y no se toque al traer.** Es la razón
 *    de que sean dos: refrescar el documento no puede borrar el juicio de una
 *    persona.
 * 5. **Que la casilla valide, y que no deje validar un objeto vacío**: sería
 *    firmar una casilla en blanco.
 * 6. **Que «pasa a CAPEX» no cree nada al marcarla** y que el botón genere las
 *    actuaciones de golpe.
 * 7. **Que un equipo de PCI YA se genere.** Su sistema vale «H06 + H10» y antes
 *    no se podía codificar; con el objeto puesto al inventariarlo, sí.
 * 8. **Que un equipo sin objeto salga aparte** y se pueda colocar desde ahí.
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

const { access_token: tk } = await api('POST', '/auth/login', {
  email: CORREO,
  password: CLAVE,
})
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
        objetos: [
          { capex_code_id: porCodigo['HC.H02.01'], nombre: 'Lámina impermeabilizante' },
        ],
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
    capex_code_id: porCodigo['HC.H08.01'],
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
    // `[REQ]` El objeto, que es lo que resuelve la ambigüedad: el sistema de
    // este equipo vale «H06 + H10» y de ahí no sale un capítulo único.
    capex_code_id: porCodigo['HC.H10.05'],
  },
  tk,
)
// Y uno sin objeto ni sistema: tiene que salir aparte, en «sin clasificar».
const suelto = await api(
  'POST',
  `/projects/${proyecto.id}/equipment`,
  { asset_id: activo.id, tag: 'XX-01', equipment_type: 'Equipo sin clasificar' },
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

// `[REQ]` §3.2 · Cada sección del activo tiene su propia dirección: se entra por
// ella y no encadenando clics, que además comprueba que la ruta es la que se
// anuncia.
await pagina.goto(`${BASE}/proyectos/${proyecto.id}/activos/${activo.id}/inventario`)
await pagina.waitForSelector('.inventario-activo .cabecera-inv', { timeout: 10000 })
console.log('· Inventario abierto')

/** La cabecera de un nodo del árbol, por su código. */
function nodo(code) {
  return pagina.locator('.cabecera-inv').filter({
    has: pagina.locator('.codigo', { hasText: new RegExp(`^${code.replace(/\./g, '\\.')}$`) }),
  })
}

/** La ficha abierta de un objeto: el `<li>` que lo contiene. */
function ficha(code) {
  return pagina
    .locator('li')
    .filter({ has: nodo(code) })
    .locator('.ficha-objeto')
    .first()
}

/** Pulsa y **espera a que la pantalla termine**.
 *
 * Esperar a `.mensaje.ok` no vale: el de la operación anterior sigue ahí, así
 * que `waitForSelector` vuelve al instante y lo siguiente que haga la prueba
 * pisa una petición en vuelo. `aria-busy` es el estado de verdad.
 */
async function pulsar(nombre) {
  await pagina.getByRole('button', { name: nombre }).click()
  await pagina.waitForSelector('.inventario-activo[aria-busy="false"]', { timeout: 15000 })
}

async function abrir(code) {
  const cabecera = nodo(code)
  if ((await cabecera.getAttribute('aria-expanded')) === 'false') await cabecera.click()
}

// 1 · Es un árbol: raíces, categorías y objetos.
const raices = await pagina.locator('.cabecera-inv.n1').count()
console.log(`  ${raices} raíces del árbol`)
if (raices < 1) fallos.push('El inventario no enseña las raíces del árbol')
// Hard Cost tiene que estar, y con sus capítulos dentro.
if ((await nodo('HC').count()) !== 1) fallos.push('No está la raíz Hard Cost')
await abrir('HC')
if ((await nodo('HC.H08').count()) !== 1) {
  fallos.push('Abrir Hard Cost no enseña sus capítulos')
}

// 2 · Los equipos ya colocan su objeto, así que su categoría se abre sola.
await pagina.waitForSelector('.cabecera-inv.con-algo', { timeout: 10000 })
const conAlgo = await pagina.locator('.cabecera-inv.con-algo').count()
console.log(`  ${conAlgo} objeto(s) marcados como «con contenido»`)
// Dos: los objetos de los dos equipos que se han inventariado con su objeto.
if (conAlgo !== 2) {
  fallos.push(`${conAlgo} objeto(s) se distinguen por tener trabajo hecho, se esperaban 2`)
}

// 3 · Traer de la documentación.
await pulsar(/Traer descriptivos/)
await abrir('HC.H08')
await abrir('HC.H08.01')
const texto = await ficha('HC.H08.01')
  .getByRole('textbox', { name: /^Descriptivo de/ })
  .inputValue()
console.log('  descriptivo:', texto)
// Las palabras de la memoria, no el nombre del catálogo.
if (!texto.includes('Enfriadora de la cubierta') || !texto.includes('R-410A')) {
  fallos.push(`El descriptivo no trae lo que dice la memoria: «${texto}»`)
}
if (texto.includes('2,00')) {
  fallos.push(`La cantidad se escribe con la escala de la columna: «${texto}»`)
}
const avisos = await pagina.locator('.inventario-activo .mensaje.aviso').allInnerTexts()
if (!avisos.some((a) => a.includes('no están codificados'))) {
  fallos.push('El objeto sin código del catálogo no se avisa')
}

// 4 · La valoración es otro cuadro, y traer no la toca.
const VALORACION = 'Refrigerante en calendario de retirada. Sustitución a medio plazo.'
await ficha('HC.H08.01')
  .getByRole('textbox', { name: /^Valoración de/ })
  .fill(VALORACION)
await pulsar(/^Guardar el inventario/)
let enBase = (await api('GET', `/assets/${activo.id}/descriptivos`, null, tk)).find(
  (d) => d.capex_code === 'HC.H08.01',
)
if (enBase.valoracion !== VALORACION) {
  fallos.push(`La valoración no llega a la base: «${enBase.valoracion}»`)
} else {
  console.log('  la valoración se guarda aparte del descriptivo')
}

await pulsar(/Traer descriptivos/)
enBase = (await api('GET', `/assets/${activo.id}/descriptivos`, null, tk)).find(
  (d) => d.capex_code === 'HC.H08.01',
)
if (enBase.valoracion !== VALORACION) {
  fallos.push('Volver a traer la documentación ha pisado la valoración')
} else {
  console.log('  y volver a traer no la toca')
}

// 5 · La casilla valida; un objeto vacío no se puede firmar.
await abrir('HC.H08.01')
await ficha('HC.H08.01')
  .getByRole('checkbox', { name: /Validado por un técnico/ })
  .check()
await pulsar(/^Guardar el inventario/)
const firmado = (await api('GET', `/assets/${activo.id}/descriptivos`, null, tk)).find(
  (d) => d.capex_code === 'HC.H08.01',
)
if (!firmado.validado_at || !firmado.validado_por) {
  fallos.push('La casilla marca validado sin dejar constancia de quién y cuándo')
} else {
  console.log(`  validado por ${firmado.validado_por_nombre}`)
}

await abrir('HC.H02')
await abrir('HC.H02.01')
await ficha('HC.H02.01')
  .getByRole('textbox', { name: /^Descriptivo de/ })
  .fill('   ')
const casillaVacia = ficha('HC.H02.01').getByRole('checkbox', {
  name: /Validado por un técnico/,
})
if (await casillaVacia.isEnabled()) {
  fallos.push('Se puede validar un objeto vacío: sería firmar en blanco')
} else {
  console.log('  un objeto vacío no se puede validar')
}

// 6 · «Pasa a CAPEX»: marcar no crea nada.
// `click()` y no `check()`: la casilla es controlada y solo se marca cuando
// vuelve el PATCH, así que `check()` daría por fallado un guardado en camino.
await abrir('HC.H10')
await abrir('HC.H10.05')
for (const [code, etiqueta] of [
  ['HC.H08.01', 'CL-01'],
  ['HC.H10.05', 'BIE-01'],
]) {
  await ficha(code)
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
const sinGenerar = await api(
  'GET',
  `/projects/${proyecto.id}/findings?asset_id=${activo.id}`,
  null,
  tk,
)
if (sinGenerar.length !== 0) {
  fallos.push(`Marcar la casilla ya ha creado ${sinGenerar.length} actuación(es): no debería`)
} else {
  console.log('  marcar no crea nada')
}

// 7 · Generar: ahora el de PCI también, porque tiene objeto.
await pulsar(/Generar actuaciones de los marcados/)
const generadas = await api(
  'GET',
  `/projects/${proyecto.id}/findings?asset_id=${activo.id}`,
  null,
  tk,
)
console.log(`  ${generadas.length} actuación(es) generada(s)`)
if (generadas.length !== 2) {
  fallos.push(
    `Se esperaban dos actuaciones —CL-01 y BIE-01—: ${generadas.map((h) => h.title).join(' / ')}`,
  )
}
const bie = generadas.find((h) => h.title.includes('BIE-01'))
if (!bie) {
  fallos.push('El equipo de PCI sigue sin generarse pese a tener objeto')
} else if (bie.capex_code_id !== porCodigo['HC.H10.05']) {
  fallos.push('La actuación del equipo de PCI no cuelga del objeto que se le puso')
} else {
  console.log('  el de PCI se genera y cuelga de su objeto: «H06 + H10» ya no bloquea')
}

// 8 · El equipo sin objeto sale aparte y se coloca desde ahí.
const sinClasificar = pagina.locator('.sin-clasificar')
if ((await sinClasificar.count()) !== 1) {
  fallos.push('El equipo sin objeto no sale agrupado aparte')
} else {
  await sinClasificar
    .locator('tbody tr')
    .filter({ hasText: 'XX-01' })
    .locator('select')
    .selectOption(porCodigo['HC.H02.01'])
  await pagina.waitForFunction(() => !document.querySelector('.sin-clasificar'), null, {
    timeout: 10000,
  })
  const colocado = await api('GET', `/equipment/${suelto.id}`, null, tk)
  if (colocado.capex_code !== 'HC.H02.01') {
    fallos.push(`Colocar el equipo no ha guardado su objeto: ${colocado.capex_code}`)
  } else {
    console.log('  un equipo sin objeto se coloca desde «sin clasificar»')
  }
}

// La fotografía sigue atándose al equipo desde la visita: es donde vive la
// galería. Aquí se comprueba que, atada, aparece en el objeto de su equipo.
await api('PATCH', `/photos/${foto.id}`, { equipment_id: enfriadora.id }, tk)
await pagina.reload()
await pagina.waitForSelector('.inventario-activo .cabecera-inv', { timeout: 10000 })
await abrir('HC.H08')
await abrir('HC.H08.01')
const fotosDelObjeto = await ficha('HC.H08.01').locator('.fotos-del-objeto li').count()
if (fotosDelObjeto !== 1) {
  fallos.push(`El objeto enseña ${fotosDelObjeto} fotografías y su equipo tiene una`)
} else {
  console.log('  la foto atada al equipo aparece en su objeto sin clasificarla dos veces')
}

await navegador.close()

console.log()
if (fallos.length) {
  console.log(`${fallos.length} problema(s):`)
  for (const f of fallos) console.log(' -', f)
  process.exit(1)
}
console.log(
  'El inventario es el árbol del cliente; cada objeto lleva su descriptivo y su valoración, ' +
    'sus equipos y sus fotos; y «pasa a CAPEX» genera sabiendo dónde cuelga cada actuación.',
)

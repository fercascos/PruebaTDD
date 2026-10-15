/** Recorre el prototipo **ya compilado** y busca texto del otro idioma.
 *
 *  `[REQ]` Es la única comprobación que mira lo que de verdad se entrega. El
 *  extractor de `extraer-textos.mjs` vigila el código; la tabla de la API
 *  vigila sus claves; pero el prototipo junta las dos mitades —los rótulos y
 *  **la grabación**— y es donde se ve si encajan. Las tres veces que esta capa
 *  salió mal, lo que lo delató fue mirar la pantalla.
 *
 *  Abre el fichero con `file://`, como quien lo recibe por correo: así también
 *  se comprueba que funciona sin servidor y sin red.
 *
 *      node herramientas/comprobar-prototipo.mjs
 *      TDD_PROTOTIPO=prototipo/entregable/prototipo-en.html TDD_IDIOMA=en node ...
 */
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { abrir } from './navegador.mjs'

const IDIOMA = process.env.TDD_IDIOMA ?? 'en'
const FICHERO = resolve(
  process.env.TDD_PROTOTIPO ??
    `prototipo/entregable/${IDIOMA === 'es' ? 'prototipo.html' : `prototipo-${IDIOMA}.html`}`,
)
if (!existsSync(FICHERO)) {
  console.error(`No existe ${FICHERO}. Compílelo con \`npm run prototipo\`.`)
  process.exit(1)
}

/** Palabras que **solo** existen en castellano, con tilde o con ñ, y que no son
 *  nombres propios ni del cliente. Una sola en una pantalla inglesa basta. */
const DELATORAS = [
  'Guardar', 'Cerrar', 'Volver', 'Buscar', 'Añadir', 'Cargando', 'Ninguno',
  'ningún', 'ninguna', 'Hallazgo', 'hallazgos', 'Activo', 'activos',
  'Informe', 'informes', 'Plantilla', 'plantillas', 'Fotografía', 'fotografías',
  'Zona', 'zonas', 'Visita', 'visitas', 'Equipo', 'Riesgo', 'riesgos',
  'Capítulo', 'capítulos', 'Objeto', 'Fase', 'fases', 'Proyecto', 'proyectos',
  'Resumen', 'Estado', 'Acciones', 'Versión', 'Sugerencias', 'Personas',
  'Quedan', 'quedan', 'Reposición', 'Vida útil', 'sin generar', 'Sin clasificar',
  // Añadidas al encontrarlas en pantalla con todo lo demás en verde. Las tres
  // venían de **plantillas de JavaScript** —`` `${n}/${m} objetos` ``—, que no
  // ve ningún extractor porque no hay una cadena que leer. Son el aviso de que
  // esta lista se queda corta por definición: lo que la amplía es mirar.
  // «eq.» NO entra: abrevia «equipos» y «equipment», y se escribe igual en
  // los dos idiomas. Es de la familia de las unidades.
  'objetos', 'objeto', 'situado', 'situados',
  // El conector suelto entre dos expresiones: «0 de 141». Con espacios a los
  // lados para no cazar «Inventada» ni «Avenida».
  ' de ',
]

const { navegador, contexto } = await abrir()
const pg = await contexto.newPage()
const errores = []
pg.on('pageerror', (e) => errores.push(e.message))
pg.on('console', (m) => m.type() === 'error' && errores.push(m.text()))

await pg.goto(`file://${FICHERO}`)
await pg.waitForTimeout(1500)

// El prototipo arranca ya dentro: la grabación trae la sesión. El proyecto que
// hay que recorrer sale de la grabación, leyéndola del disco: el fichero
// compilado no la expone, y pedírsela a la página obligaría a tocar el
// prototipo para poder comprobarlo, que es al revés de como debe ser.
const GRABACION = resolve(
  process.env.TDD_GRABACION ??
    `prototipo/${IDIOMA === 'es' ? 'grabacion.json' : `grabacion-${IDIOMA}.json`}`,
)
const idProyecto = (() => {
  if (!existsSync(GRABACION)) return null
  const g = JSON.parse(readFileSync(GRABACION, 'utf-8'))
  const clave = Object.keys(g).find((k) => k === 'GET /api/v1/projects' || k.startsWith('GET /api/v1/projects?'))
  if (!clave) return null
  const lista = JSON.parse(g[clave].texto)
  return (Array.isArray(lista) ? lista : (lista.items ?? []))[0]?.id ?? null
})()
if (!idProyecto) console.log('· sin proyecto en la grabación: solo se miran las pantallas sueltas')

/** Lo que va **entre paréntesis** no cuenta.
 *
 *  `[REQ]` El catálogo inglés conserva a propósito el término legal español
 *  dentro del nombre: «Concept design (Proyecto Básico)». No es un descuido de
 *  la traducción, es la decisión correcta —«Proyecto Básico» es el nombre del
 *  documento que hay que pedirle al cliente, y traducirlo dejaría a quien lo
 *  pide sin saber qué nombrar—. Está en `data/catalogos/traducciones_en.csv`
 *  marcado como traducción propia.
 *
 *  Un escape de verdad no viene entre paréntesis, así que quitarlos no afloja
 *  la comprobación: la ajusta a lo que de verdad se busca.
 */
const sinParentesis = (texto) => texto.replace(/\([^)]*\)/g, '')

const sospechas = []
async function mirar(nombre, ir) {
  await ir()
  await pg.waitForTimeout(900)
  const texto = sinParentesis(await pg.locator('body').innerText())
  const vistas = DELATORAS.filter((p) => texto.includes(p))
  const marca = vistas.length ? `✗ ${vistas.join(', ')}` : '✓'
  console.log(`  ${marca.padEnd(40)} ${nombre}`)
  if (vistas.length) sospechas.push({ nombre, vistas })
}

/** Los activos del encargo, que salen de la misma grabación.
 *
 *  `[REQ]` Sus cinco secciones son **la mitad de las pantallas** del prototipo
 *  —la documentación pedida, la visita, el inventario, el CAPEX— y es donde
 *  vive el trabajo de verdad. Mirar solo las pestañas de arriba daría una
 *  comprobación que pasa sin haber visto lo que importa.
 */
const idsDeActivos = (() => {
  if (!existsSync(GRABACION) || !idProyecto) return []
  const g = JSON.parse(readFileSync(GRABACION, 'utf-8'))
  const r = g[`GET /api/v1/projects/${idProyecto}/assets`]
  return r ? JSON.parse(r.texto).map((a) => a.id) : []
})()

const base = idProyecto ? `#/proyectos/${idProyecto}` : null
const SECCIONES = [
  ['', 'ficha'],
  ['/documentacion', 'documentación'],
  ['/visita', 'visita'],
  ['/inventario', 'inventario'],
  ['/capex', 'CAPEX'],
]
const pantallas = [
  ['lista de proyectos', '#/proyectos'],
  ...(base
    ? [
        ['resumen del proyecto', base],
        ['activos', `${base}/activos`],
        ['cuadro de mando', `${base}/dashboard`],
        ['riesgos', `${base}/riesgos`],
        ['informe final', `${base}/informes`],
      ]
    : []),
  ...idsDeActivos.flatMap((id, i) =>
    SECCIONES.map(([ruta, nombre]) => [`activo ${i + 1} · ${nombre}`, `${base}/activos/${id}${ruta}`]),
  ),
  ['plantillas', '#/plantillas'],
  ['sugerencias', '#/sugerencias'],
  ['personas', '#/personas'],
]
console.log(`\n${FICHERO}\nbuscando castellano en pantalla:\n`)
for (const [nombre, hash] of pantallas) {
  await mirar(nombre, () => pg.goto(`file://${FICHERO}${hash}`))
}

console.log(`\nerrores de pagina: ${errores.length ? errores.slice(0, 5).join(' | ') : 'ninguno'}`)
if (sospechas.length) {
  console.log(`\n${sospechas.length} pantallas con texto castellano.`)
  process.exitCode = 1
} else {
  console.log('\nNinguna pantalla con texto castellano.')
}
await navegador.close()

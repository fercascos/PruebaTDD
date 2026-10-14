/** Envuelve en `traducir()` el texto de la interfaz `[REQ]` S-05.
 *
 *      node herramientas/cablear-i18n.mjs --ver     # qué tocaría, sin tocar
 *      node herramientas/cablear-i18n.mjs
 *
 *  Son ~600 sitios en 50 ficheros. A mano es media jornada y un puñado de
 *  despistes; a lo bruto con una expresión regular es romper la aplicación. La
 *  línea que separa las dos cosas es ésta: **solo se sustituye lo que está en
 *  el diccionario**. El diccionario lo construyó el extractor a partir de este
 *  mismo código y lo revisó una persona, así que es una lista blanca, no una
 *  heurística.
 *
 *  Lo que toca, y nada más:
 *
 *  1. **Texto suelto dentro de JSX**: `<h1>Proyectos</h1>`.
 *  2. **Atributos de texto** de una lista corta y explícita: `placeholder`,
 *     `title`, `aria-label`, `alt`.
 *
 *  `[LIM]` Lo que **no** toca, a propósito, porque distinguirlo exige entender
 *  el programa y no solo leerlo: las cadenas sueltas en la lógica —un `const`
 *  con una lista de rótulos, un `throw new Error(...)`—. Las cuenta y las
 *  enumera al terminar para que se repasen a mano.
 *
 *  ## Las cinco que quedan, y por qué quedan
 *
 *  Se repasaron todas, una por una. Cinco siguen en la lista y **están bien
 *  así**; se dejan dichas para que nadie las «arregle»:
 *
 *  - `ArbolDeCapex.tsx` «Código retirado» y `DocumentacionDelActivo.tsx`
 *    «Pendiente de pedir» son rótulos que viajan dentro de un dato —el nombre
 *    de un nodo del árbol, el de una opción— y los traduce quien los pinta. El
 *    informe de arriba las ve porque son argumentos de una llamada, no valores
 *    de una tabla, y esa diferencia no se lee en el renglón.
 *  - `PestanaEquipo.tsx` «vencido» es una **clase CSS** que se llama igual que
 *    un rótulo del catálogo. Traducirla rompería la hoja de estilos.
 *  - `Plantillas.tsx` «Estándar» es **dato**: el nombre con el que se da de
 *    alta una plantilla viaja al servidor y se guarda. Traducirlo crearía
 *    plantillas distintas según el idioma de quien las creó.
 *  - `Sugerencias.tsx` «Sugerencias» está **dentro de un comentario**, en una
 *    cita literal de lo que pidió el cliente.
 */
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { EN } from '../src/i18n/textos.ts'

const RAIZ = new URL('..', import.meta.url).pathname.replace(/^\/@fs/, '')
const FUENTE = join(RAIZ, 'src')
const VER = process.argv.includes('--ver')

/** Atributos y props cuyo valor lee una persona. El resto son nombres y rutas.
 *
 *  `etiqueta`, `ayuda` y `titulo` no son del HTML: son las props de los
 *  componentes de formulario de esta aplicación (`ui/Formulario.tsx`), y entre
 *  las tres son 140 textos. Sin ellas el cableado automático se dejaba fuera
 *  casi todas las etiquetas de los formularios, que es donde más texto hay.
 */
const ATRIBUTOS = ['placeholder', 'title', 'aria-label', 'alt', 'etiqueta', 'ayuda', 'titulo']

function ficheros(dir) {
  const salida = []
  for (const nombre of readdirSync(dir)) {
    const ruta = join(dir, nombre)
    if (statSync(ruta).isDirectory()) salida.push(...ficheros(ruta))
    else if (/\.tsx$/.test(nombre) && !nombre.includes('.test.')) salida.push(ruta)
  }
  return salida
}

/** Escapa una cadena para meterla entre comillas simples en el código. */
function comillas(s) {
  return `'${s.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}'`
}

let tocados = 0
let sustituciones = 0
const sinTocar = new Map()

for (const fichero of ficheros(FUENTE)) {
  if (fichero.includes(join('src', 'i18n'))) continue
  const original = readFileSync(fichero, 'utf8')
  let codigo = original
  let n = 0

  // 1 · Texto suelto dentro de JSX. El `(?<!=)` descarta la flecha de una
  //     función, que con el genérico de al lado parece una etiqueta.
  codigo = codigo.replace(/(?<!=)(>)(\s*)([^<>{}\n][^<>{}\n]*?)(\s*)(<)/g, (todo, ab, e1, texto, e2, ce) => {
    const clave = texto.trim().replace(/\s+/g, ' ')
    if (!(clave in EN)) return todo
    n += 1
    return `${ab}${e1}{traducir(${comillas(clave)})}${e2}${ce}`
  })

  // 1b · Texto JSX que ocupa **varias líneas**: los párrafos de ayuda.
  //
  //      <p className="ayuda">
  //        Tipo de coste → categoría → objeto. Solo se dibujan las ramas
  //        que tienen algo.
  //      </p>
  //
  //  Se reescribe en una sola llamada y en un solo renglón, aunque quede
  //  largo: partir el literal exigiría `+` entre trozos y la clave del
  //  diccionario es la frase entera, así que cualquier corte la rompería.
  //  Como el único linter del frontend es `tsc`, un renglón largo no es un
  //  problema; una clave partida sí.
  codigo = codigo.replace(
    /(?<!=)(>)[ \t]*\n((?:[ \t]*[^<>{}\n][^<>{}\n]*\n)+)([ \t]*)(<)/g,
    (todo, ab, cuerpo, sangria, ce) => {
      const clave = cuerpo.replace(/\s+/g, ' ').trim()
      if (!(clave in EN)) return todo
      n += 1
      return `${ab}\n${sangria}  {traducir(${comillas(clave)})}\n${sangria}${ce}`
    },
  )

  // 2 · Atributos de texto.
  for (const attr of ATRIBUTOS) {
    const re = new RegExp(`(\\s${attr}=)"([^"\\n]+)"`, 'g')
    codigo = codigo.replace(re, (todo, izq, texto) => {
      const clave = texto.trim().replace(/\s+/g, ' ')
      if (!(clave in EN)) return todo
      n += 1
      return `${izq}{traducir(${comillas(clave)})}`
    })
  }

  if (n === 0) continue

  // El import, una sola vez y después del último `import` que ya haya.
  if (!codigo.includes("from '../i18n/idioma'") && !codigo.includes("from './i18n/idioma'")) {
    const profundidad = relative(FUENTE, fichero).split('/').length - 1
    const ruta = profundidad === 0 ? './i18n/idioma' : `${'../'.repeat(profundidad)}i18n/idioma`
    // **Antes del primer import, no después del último.** Después del último
    // parece lo natural y rompe: `^import .*$` casa con la primera línea de un
    // `import {` multilínea, y el import nuevo se cuela dentro de la llave.
    // Pasó con `Anotador.tsx` y lo cantó el compilador. Delante no puede
    // partir nada, y si no hay ningún import va detrás del comentario de
    // cabecera, que en este repositorio lo lleva todo.
    const linea = `import { traducir } from '${ruta}'\n`
    const primero = codigo.search(/^import /m)
    if (primero >= 0) {
      codigo = codigo.slice(0, primero) + linea + codigo.slice(primero)
    } else {
      const fin = codigo.startsWith('/*') ? codigo.indexOf('*/') + 2 : 0
      codigo = `${codigo.slice(0, fin)}\n${linea}${codigo.slice(fin)}`
    }
  }

  tocados += 1
  sustituciones += n
  if (!VER) writeFileSync(fichero, codigo)
  console.log(`${String(n).padStart(3)}  ${relative(RAIZ, fichero)}`)
}

/** Dónde está la cadena, para saber si hay algo que hacer con ella.
 *
 *  `[LIM]` Esto mira el renglón, no el programa, y por eso se equivoca en dos
 *  direcciones conocidas. Hacia el silencio: una cadena dentro de un
 *  `traducir(` que abrió en el renglón anterior se da por hecha sin
 *  comprobarlo. Y hacia el ruido: `className={e.vencido ? 'vencido' : ''}` es
 *  una clase CSS que se llama igual que un rótulo del catálogo, y sale en la
 *  lista. Sirve para repasar, no para aprobar.
 */
function situacion(codigo, indice) {
  const renglon = codigo.lastIndexOf('\n', indice) + 1
  const izquierda = codigo.slice(renglon, indice)
  // Ya traducida, en la misma línea o en la de arriba.
  if (/\b(traducir|t)\(\s*$/.test(izquierda)) return 'hecha'
  if (!izquierda.trim() && /\b(traducir|t)\(\s*$/.test(codigo.slice(0, renglon).trimEnd()))
    return 'hecha'
  // **Valor de una tabla de rótulos**: `NA: 'N. A.'`, `['tag', 'Etiqueta']`,
  // `{ code: 'CORTO', nombre: 'Corto plazo' }`. Estas se dejan en castellano a
  // propósito —una constante de módulo se evalúa al importar y congelaría el
  // idioma— y traduce quien las pinta. Ver `i18n/idioma.tsx`.
  if (/(\w+|\]):\s*$/.test(izquierda) || /\[\s*'[^']*',\s*$/.test(izquierda)) return 'tabla'
  return 'suelta'
}

// Lo que queda suelto en la lógica, para repasarlo a mano.
let enTablas = 0
for (const fichero of ficheros(FUENTE)) {
  if (fichero.includes(join('src', 'i18n'))) continue
  const codigo = readFileSync(fichero, 'utf8')
  for (const m of codigo.matchAll(/'([^'\\\n]{3,})'|"([^"\\\n]{3,})"/g)) {
    const clave = (m[1] ?? m[2]).trim().replace(/\s+/g, ' ')
    if (!(clave in EN)) continue
    const donde = situacion(codigo, m.index)
    if (donde === 'hecha') continue
    if (donde === 'tabla') {
      enTablas += 1
      continue
    }
    if (!sinTocar.has(relative(RAIZ, fichero))) sinTocar.set(relative(RAIZ, fichero), [])
    sinTocar.get(relative(RAIZ, fichero)).push(clave)
  }
}

console.log(`\n${sustituciones} sustituciones en ${tocados} ficheros${VER ? ' (no se ha escrito nada)' : ''}`)
if (enTablas) {
  console.log(
    `\n${enTablas} valores de tablas de rótulos, en castellano a propósito:` +
      ` los traduce quien los pinta, no su declaración.`,
  )
}
if (sinTocar.size) {
  const total = [...sinTocar.values()].reduce((a, b) => a + b.length, 0)
  console.log(`\n${total} cadenas sueltas en la lógica, para repasar a mano:`)
  for (const [f, cs] of sinTocar) console.log(`  ${f}: ${cs.map((c) => `«${c}»`).join(', ')}`)
} else {
  console.log('\nNada suelto en la lógica.')
}

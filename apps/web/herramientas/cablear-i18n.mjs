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
 */
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { EN } from '../src/i18n/textos.ts'

const RAIZ = new URL('..', import.meta.url).pathname.replace(/^\/@fs/, '')
const FUENTE = join(RAIZ, 'src')
const VER = process.argv.includes('--ver')

/** Atributos cuyo valor lee una persona. El resto son nombres y rutas. */
const ATRIBUTOS = ['placeholder', 'title', 'aria-label', 'alt']

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

// Lo que queda suelto en la lógica, para repasarlo a mano.
for (const fichero of ficheros(FUENTE)) {
  if (fichero.includes(join('src', 'i18n'))) continue
  const codigo = readFileSync(fichero, 'utf8')
  for (const m of codigo.matchAll(/'([^'\\\n]{3,})'|"([^"\\\n]{3,})"/g)) {
    const clave = (m[1] ?? m[2]).trim().replace(/\s+/g, ' ')
    if (!(clave in EN)) continue
    // Si ya va dentro de `traducir(` o `t(`, está hecho.
    const antes = codigo.slice(Math.max(0, m.index - 12), m.index)
    if (/\b(traducir|t)\(\s*$/.test(antes)) continue
    if (!sinTocar.has(relative(RAIZ, fichero))) sinTocar.set(relative(RAIZ, fichero), [])
    sinTocar.get(relative(RAIZ, fichero)).push(clave)
  }
}

console.log(`\n${sustituciones} sustituciones en ${tocados} ficheros${VER ? ' (no se ha escrito nada)' : ''}`)
if (sinTocar.size) {
  const total = [...sinTocar.values()].reduce((a, b) => a + b.length, 0)
  console.log(`\n${total} cadenas en la lógica, para repasar a mano:`)
  for (const [f, cs] of sinTocar) console.log(`  ${f}: ${cs.length}`)
}

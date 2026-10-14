/** Saca el catálogo de textos traducibles del código de la interfaz.
 *
 *  `[REQ]` S-05. Existe porque son ~730 cadenas repartidas por 54 ficheros y
 *  revisarlas a ojo garantiza dejarse algunas. Esto las junta, las ordena y
 *  dice cuáles ya tienen traducción y cuáles no.
 *
 *      node herramientas/extraer-textos.mjs            # resumen
 *      node herramientas/extraer-textos.mjs --faltan   # solo lo que falta
 *      node herramientas/extraer-textos.mjs --json     # para volcarlo
 *
 *  `[LIM]` Es un extractor por **expresión regular**, no un analizador de
 *  TypeScript. Acierta con el texto suelto dentro de JSX y con las cadenas
 *  entrecomilladas que parecen una frase, y se le escapa el texto construido
 *  con plantillas (`` `${n} activos` ``). Por eso la prueba que lo usa compara
 *  conjuntos en vez de contar: un fallo suyo deja una cadena sin traducir a la
 *  vista en la pantalla, no un error silencioso.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

/**
 * La raíz de `apps/web`.
 *
 * `[LIM]` Se limpia el prefijo `/@fs` porque este módulo lo importa también la
 * prueba, y Vite sirve los ficheros del disco bajo esa ruta: sin esto el
 * extractor funciona por línea de órdenes y falla dentro de `vitest`, que es
 * justo donde tiene que funcionar.
 */
const RAIZ = new URL('..', import.meta.url).pathname.replace(/^\/@fs/, '')
const FUENTE = join(RAIZ, 'src')

/** Lo que NO es texto para una persona aunque lo parezca. */
const NO_ES_TEXTO = [
  /^[a-z-]+$/, // clases CSS, nombres de ruta
  /^[A-Z_]+$/, // constantes y códigos de catálogo
  /^\d/, // cifras
  /^https?:/,
  /^\//, // rutas
  /^[.#]/, // selectores
  /^[A-Z]{2,4}\.[A-Z]?\d/, // códigos del árbol: HC.H02, S1.1.3
]

const ACENTOS = /[áéíóúüñÁÉÍÓÚÑ¿¡]/

/**
 * ¿Es texto para una persona?
 *
 * `suelto` distingue de dónde salió, y la diferencia importa. Una palabra
 * suelta dentro de JSX —`<button>Salir</button>`— **es** una etiqueta de la
 * interfaz; la misma palabra entre comillas puede ser el nombre de un
 * componente, una ruta o un valor de enumerado.
 *
 * Esto estaba mal al escribirlo: solo aceptaba lo que llevara acentos o varias
 * palabras, así que se dejaba fuera «Proyectos», «Salir», «Cliente», «Estado»…
 * —media interfaz—. Lo descubrió la prueba del catálogo, que dio por muertas
 * las traducciones que sí estaban en uso.
 */
function esTexto(s, suelto = false) {
  const t = s.trim()
  if (t.length < 3) return false
  if (NO_ES_TEXTO.some((r) => r.test(t))) return false
  if (ACENTOS.test(t)) return true
  if (/\s/.test(t) && /^[A-ZÁÉÍÓÚÑ¿¡]/.test(t)) return true
  // Palabra suelta dentro de JSX: etiqueta de la interfaz.
  return suelto && /^[A-ZÁÉÍÓÚÑ][a-záéíóúüñ]+$/.test(t)
}

function ficheros(dir) {
  const salida = []
  for (const nombre of readdirSync(dir)) {
    const ruta = join(dir, nombre)
    if (statSync(ruta).isDirectory()) {
      salida.push(...ficheros(ruta))
    } else if (/\.tsx?$/.test(nombre) && !nombre.includes('.test.')) {
      salida.push(ruta)
    }
  }
  return salida
}

/** `{texto: [ficheros donde sale]}`. */
export function extraer() {
  const encontrados = new Map()
  const apuntar = (texto, fichero, suelto = false) => {
    const t = texto.trim().replace(/\s+/g, ' ')
    if (!esTexto(t, suelto)) return
    if (!encontrados.has(t)) encontrados.set(t, new Set())
    encontrados.get(t).add(relative(RAIZ, fichero))
  }

  for (const fichero of ficheros(FUENTE)) {
    if (fichero.includes(`${join('src', 'i18n')}`)) continue // el propio catálogo
    const codigo = readFileSync(fichero, 'utf8')
    // Texto suelto entre etiquetas JSX. **Solo en `.tsx`**: en un `.ts` no hay
    // JSX, y esta misma regla recogía los genéricos de TypeScript —de
    // `Map<string, Promise<void>>` sacaba «Promise»— y los daba por etiquetas
    // de la interfaz.
    if (fichero.endsWith('.tsx')) {
      // `(?<!=)` descarta la flecha de una función: en `=> Promise<void>` el
      // `>` del `=>` y el `<` del genérico encierran «Promise», que no es una
      // etiqueta de nada.
      for (const m of codigo.matchAll(/(?<!=)>\s*([^<>{}\n][^<>{}\n]*?)\s*</g)) {
        apuntar(m[1], fichero, true)
      }
    }
    // Cadenas entrecomilladas.
    for (const m of codigo.matchAll(/'([^'\\\n]{3,})'|"([^"\\\n]{3,})"/g)) {
      apuntar(m[1] ?? m[2], fichero)
    }
    // Y lo ya traducido: `t('Proyectos')`. Es la señal más fiable de todas
    // —alguien ha dicho explícitamente que eso es texto— y hace falta porque
    // al envolver una etiqueta deja de ser texto suelto de JSX y, si es una
    // sola palabra, las reglas de arriba ya no la reconocen. Sin esto, cada
    // cadena traducida desaparecía del catálogo en cuanto se traducía.
    for (const m of codigo.matchAll(/\bt\(\s*'([^'\\\n]+)'|\bt\(\s*"([^"\\\n]+)"/g)) {
      const t = (m[1] ?? m[2]).trim().replace(/\s+/g, ' ')
      if (!encontrados.has(t)) encontrados.set(t, new Set())
      encontrados.get(t).add(relative(RAIZ, fichero))
    }
  }
  return encontrados
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { EN } = await import('../src/i18n/textos.ts').catch(() => ({ EN: {} }))
  const encontrados = extraer()
  const claves = [...encontrados.keys()].sort((a, b) => a.localeCompare(b, 'es'))
  const faltan = claves.filter((c) => !(c in EN))

  if (process.argv.includes('--json')) {
    console.log(JSON.stringify(Object.fromEntries(faltan.map((c) => [c, ''])), null, 2))
  } else if (process.argv.includes('--faltan')) {
    for (const c of faltan) console.log(`${[...encontrados.get(c)][0]}\t${c}`)
  } else {
    console.log(`${claves.length} textos · ${claves.length - faltan.length} traducidos · ${faltan.length} sin traducir`)
  }
}

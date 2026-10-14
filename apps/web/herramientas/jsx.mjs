/** El texto visible de un fichero `.tsx`, **leído con el parser de TypeScript**.
 *
 *  `[REQ]` Esto empezó siendo una expresión regular y ha costado dos agujeros
 *  silenciosos encontrar que no puede serlo:
 *
 *  1. El primero: un párrafo que el formateador parte en cuatro renglones. La
 *     regla excluía el salto de línea —para no cruzar etiquetas— y dejaba
 *     invisibles **67 nodos** de texto de ayuda. El extractor decía «0 sin
 *     traducir» mientras el prototipo en inglés enseñaba los párrafos en
 *     castellano.
 *  2. El segundo, al arreglar el primero: el texto que convive con una
 *     etiqueta dentro del mismo párrafo —`…lo que se sabe de él:
 *     <strong>Descriptivo</strong>, que sale de la memoria…`— son **tres**
 *     nodos de texto, y una regla que exige el párrafo entero limpio no ve
 *     ninguno.
 *
 *  Y la expresión regular que sí los veía —«todo lo que hay entre `>` y `<`»—
 *  recogía además el código: en `useState<Foo>()` el `>` del genérico y el `<`
 *  siguiente encierran código, no texto. Trescientos falsos positivos.
 *
 *  `typescript` ya es dependencia del proyecto —es lo que ejecuta `npm run
 *  lint`—, así que esto no añade ninguna. Y a diferencia de la expresión
 *  regular, **no se equivoca**: un `JsxText` es texto de la interfaz por
 *  definición del lenguaje, no por parecerlo.
 */
import ts from 'typescript'

/** Props cuyo valor lee una persona. El resto son nombres, rutas y códigos.
 *
 *  Las tres últimas no son del HTML: son las props de los componentes de
 *  formulario de esta aplicación (`ui/Formulario.tsx`).
 */
export const ATRIBUTOS = new Set([
  'placeholder',
  'title',
  'aria-label',
  'alt',
  'etiqueta',
  'ayuda',
  'titulo',
  'textoDeEnvio',
  'columna',
  'plural',
])

/** Las entidades que aparecen en el texto JSX de esta aplicación. */
const ENTIDADES = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&nbsp;': '\u00a0' }

/** Normaliza como lo hace el navegador: los espacios colapsan y la entidad se
 *  resuelve.
 *
 *  `[REQ]` Resolver la entidad **no es cosmético**: el parser devuelve el
 *  texto del fichero, así que `Q&A` escrito en JSX llega como `Q&amp;A`. Si la
 *  clave del diccionario llevara la entidad, el día que se envuelva en
 *  `traducir('… Q&amp;A …')` eso ya es una cadena de JavaScript y React la
 *  pintaría literalmente: el usuario vería «Q&amp;A» en la pantalla.
 */
export function normalizar(texto) {
  let salida = texto.replace(/\s+/g, ' ').trim()
  for (const [entidad, caracter] of Object.entries(ENTIDADES)) {
    salida = salida.replaceAll(entidad, caracter)
  }
  return salida
}

/**
 * ¿Es texto para una persona, o un signo de puntuación suelto?
 *
 * Un `JsxText` puede ser `·`, `,` o `{' '}`-vecino: separadores que el
 * formateador deja entre elementos y que no se traducen. Se pide **una letra**
 * y al menos tres caracteres.
 */
export function esVisible(texto) {
  return texto.length >= 3 && /\p{L}/u.test(texto)
}

/**
 * Los trozos de texto visible de un fichero, con su posición exacta.
 *
 * Devuelve `{texto, inicio, fin, tipo}` ordenados por posición, donde `tipo`
 * es `'jsx'` para un nodo de texto y `'attr'` para el valor de un atributo. La
 * posición es la del fichero sin tocar, así que quien reescriba tiene que ir
 * **de atrás hacia delante** para no invalidar las de los siguientes.
 */
export function textoVisible(codigo, fichero = 'x.tsx') {
  const fuente = ts.createSourceFile(fichero, codigo, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const trozos = []

  const visitar = (nodo) => {
    if (ts.isJsxText(nodo)) {
      const texto = normalizar(nodo.getText(fuente))
      if (esVisible(texto)) {
        trozos.push({ texto, inicio: nodo.getStart(fuente), fin: nodo.getEnd(), tipo: 'jsx' })
      }
    } else if (ts.isJsxAttribute(nodo) && nodo.initializer) {
      const nombre = nodo.name.getText(fuente)
      // Solo el literal directo: `etiqueta="Zona"`. Un `etiqueta={algo}` ya es
      // una expresión y la decide quien la escribió.
      if (ATRIBUTOS.has(nombre) && ts.isStringLiteral(nodo.initializer)) {
        const texto = normalizar(nodo.initializer.text)
        if (esVisible(texto)) {
          trozos.push({
            texto,
            inicio: nodo.initializer.getStart(fuente),
            fin: nodo.initializer.getEnd(),
            tipo: 'attr',
          })
        }
      }
    }
    ts.forEachChild(nodo, visitar)
  }

  visitar(fuente)
  return trozos.sort((a, b) => a.inicio - b.inicio)
}

/**
 * El traductor, sin React `[REQ]` S-05.
 *
 * Está separado de `idioma.tsx` por una razón concreta, no por orden: hay
 * módulos de esta aplicación que son **lógica pura y lo dicen en su cabecera**
 * —`fotos/cola.ts`, «sin React ni red»—, y que sin embargo producen texto que
 * una persona lee («Fallo de red»). Si el traductor viviera en el fichero del
 * contexto, importarlo desde ahí arrastraría React dentro de un módulo que
 * presume de no tenerlo, y esa frase de la cabecera dejaría de ser verdad sin
 * que nada fallase.
 *
 * Así que aquí está lo que no necesita React —el idioma en vivo y la
 * sustitución de huecos— y en `idioma.tsx` lo que sí: el contexto, el
 * proveedor, los `hooks` y los formatos de `Intl`. `idioma.tsx` reexporta
 * `traducir`, de modo que el resto del código sigue importándolo del sitio de
 * siempre y no hay dos caminos que mantener.
 */
import { EN } from './textos'

export type Idioma = 'es' | 'en'

/**
 * El idioma en vivo, fuera de React.
 *
 * `[REQ]` Existe para que `traducir()` se pueda llamar **desde cualquier
 * sitio**: una constante de módulo, un ayudante que no es componente, el
 * cuerpo de un `catch`. Con un `hook` eso no se puede, y la alternativa era
 * reestructurar cincuenta ficheros para meter el texto dentro de un componente.
 *
 * `[LIM]` Es estado fuera de React, con lo que eso implica: **no dispara el
 * repintado por sí solo**. Lo dispara `ProveedorDeIdioma`, que llama a
 * `fijarIdioma()` y acto seguido cambia su `useState`, y como está en la raíz
 * del árbol repinta todo lo que hay debajo. Funciona porque **ningún
 * componente de esta aplicación está memoizado**; comprobado, no supuesto. El
 * día que alguien envuelva uno en `memo`, ese componente se quedará en el
 * idioma anterior, y por eso está escrito aquí.
 */
let idiomaActual: Idioma = 'es'

/** Lo llama `ProveedorDeIdioma`, y nadie más. */
export function fijarIdioma(a: Idioma): void {
  idiomaActual = a
}

export function idiomaEnVivo(): Idioma {
  return idiomaActual
}

/**
 * Traduce. En castellano devuelve la clave tal cual, que **es** el texto.
 *
 * `valores` sustituye `{nombre}` por su valor. Se resuelve después de
 * traducir, para que la frase inglesa pueda colocar los huecos en otro orden.
 */
export function traducir(clave: string, valores?: Record<string, string | number>): string {
  const texto = idiomaActual === 'en' ? (EN[clave] ?? clave) : clave
  if (!valores) return texto
  return texto.replace(/\{(\w+)\}/g, (entero, nombre) =>
    nombre in valores ? String(valores[nombre]) : entero,
  )
}

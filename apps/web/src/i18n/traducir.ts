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

/** Lo que `Intl` necesita para el idioma en vivo. La moneda la fija el proyecto. */
const LOCALE: Record<Idioma, string> = { es: 'es-ES', en: 'en-GB' }

export function localeEnVivo(): string {
  return LOCALE[idiomaActual]
}

/**
 * Un formateador de `Intl` que **sigue al idioma**.
 *
 * `[REQ]` Existe por un error concreto y silencioso: había trece
 * `new Intl.NumberFormat('es-ES', …)` como constantes de módulo repartidas por
 * el frontend. Una constante de módulo se evalúa **al importar**, así que la
 * pantalla en inglés seguía escribiendo «250.157,50 €» —punto de millares,
 * coma decimal, símbolo detrás— a alguien que espera «€250,157.50». Se vio en
 * el prototipo en inglés, con la cifra de CAPEX del proyecto en la cabecera.
 *
 * Devuelve algo con `.format()` para no tocar los cincuenta sitios que lo
 * llaman así, y crea el formateador de verdad **en la llamada**, cacheado por
 * idioma: construir un `Intl.NumberFormat` no es gratis y estas funciones se
 * llaman una vez por celda de una tabla.
 */
export function formateador(opciones: Intl.NumberFormatOptions): { format: (n: number) => string } {
  const cache = new Map<string, Intl.NumberFormat>()
  return {
    format(n: number): string {
      const l = localeEnVivo()
      let f = cache.get(l)
      if (!f) {
        f = new Intl.NumberFormat(l, opciones)
        cache.set(l, f)
      }
      return f.format(n)
    },
  }
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

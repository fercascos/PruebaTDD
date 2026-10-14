/**
 * El estado de un proyecto, escrito para una persona.
 *
 * `[REQ]` La pantalla enseñaba **el código del enumerado**: «BORRADOR»,
 * «VISITA_PROGRAMADA». En castellano se entiende a medias —se lee el guion
 * bajo— y en inglés no se entiende en absoluto, que es como se vio: el
 * prototipo en inglés ponía «BORRADOR» en la cabecera del proyecto.
 *
 * Así que aquí está el rótulo, y el código se queda donde tiene que estar: en
 * la base, en la API y en la clase CSS de la etiqueta.
 *
 * `[LIM]` Un estado que se añada al enumerado y no aquí sale con su código
 * crudo, que es exactamente lo que había antes y por tanto no empeora nada. No
 * se puede comprobar en tiempo de compilación sin duplicar el enumerado en
 * TypeScript, y duplicarlo es la otra forma de que divergan.
 */
import { traducir } from '../i18n/traducir'

/** Código del enumerado `project_status` → rótulo en castellano. */
const PROYECTO: Record<string, string> = {
  BORRADOR: 'Borrador',
  EN_PREPARACION: 'En preparación',
  VISITA_PROGRAMADA: 'Visita programada',
  VISITA_REALIZADA: 'Visita realizada',
  EN_ANALISIS: 'En análisis',
  EN_REVISION: 'En revisión',
  INFORME_EMITIDO: 'Informe emitido',
  CERRADO: 'Cerrado',
  ARCHIVADO: 'Archivado',
}

/**
 * El rótulo del estado de un proyecto, en el idioma de la interfaz.
 *
 * Se traduce **aquí y no en la tabla de arriba**: una constante de módulo se
 * evalúa al importar y congelaría el idioma. Ver `i18n/idioma.tsx`.
 */
export function estadoDeProyecto(code: string): string {
  return traducir(PROYECTO[code] ?? code)
}

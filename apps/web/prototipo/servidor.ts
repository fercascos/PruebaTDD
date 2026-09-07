/**
 * La API, servida desde dentro del navegador.
 *
 * El prototipo **es la aplicación de verdad**: el mismo React, las mismas
 * pantallas, el mismo `cliente.ts`. Lo único que cambia es que sus `fetch` no
 * salen a ninguna parte: los contesta esto, con respuestas **grabadas de la API
 * real** recorriendo un encargo de demostración (`herramientas/grabar-api.mjs`).
 *
 * Se hace así y no con un servidor de mentira escrito a mano por una razón: un
 * servidor a mano envejece en cuanto la API cambia, y entonces el prototipo
 * enseña una aplicación que ya no existe. Esto se vuelve a grabar en un minuto.
 *
 * `[LIM]` **Es de solo lectura.** Se navega, se cambia de pestaña, se filtra y
 * se abren las fichas; lo que escribe —crear un hallazgo, aceptar una
 * propuesta, generar un informe— responde `501` y la aplicación lo enseña como
 * el error que es. No se simula un éxito: un prototipo que finge guardar es
 * peor que uno que dice que no guarda.
 */

type Grabada = { estado: number; tipo: string; texto?: string; base64?: string }

/** `MÉTODO /api/v1/ruta?consulta` → lo que contestó la API aquel día. */
export type Grabacion = Record<string, Grabada>

const PREFIJO = '/api/v1'

function cuerpo(r: Grabada): BodyInit | null {
  if (r.base64 === undefined) return r.texto ?? null
  const bruto = atob(r.base64)
  const bytes = new Uint8Array(bruto.length)
  for (let i = 0; i < bruto.length; i++) bytes[i] = bruto.charCodeAt(i)
  return bytes
}

function respuesta(r: Grabada): Response {
  return new Response(cuerpo(r), {
    status: r.estado,
    headers: { 'Content-Type': r.tipo },
  })
}

function problema(status: number, titulo: string, detalle: string): Response {
  // El mismo formato que usa la API (RFC 7807), para que la pantalla lo pinte
  // como pinta cualquier otro error y no haya que tocar nada.
  return new Response(JSON.stringify({ title: titulo, status, detail: detalle }), {
    status,
    headers: { 'Content-Type': 'application/problem+json' },
  })
}

/** Lo que el prototipo no puede contestar, dicho en pantalla y no en la consola. */
const SIN_GRABAR =
  'Este recorrido no llegó a esta pantalla al grabarse, así que el prototipo no ' +
  'tiene su respuesta. En la aplicación de verdad esto funciona.'

const SOLO_LECTURA =
  'El prototipo es de solo lectura: navega con datos grabados y no guarda nada. ' +
  'Escribir esto sí funciona en la aplicación.'

export function instalar(grabacion: Grabacion): void {
  const original = window.fetch.bind(window)
  const fallos = new Set<string>()

  window.fetch = async (entrada, opciones) => {
    const url = new URL(
      typeof entrada === 'string' ? entrada : entrada instanceof URL ? entrada.href : entrada.url,
      window.location.origin,
    )
    if (!url.pathname.startsWith(PREFIJO)) return original(entrada, opciones)

    const metodo = (
      opciones?.method ??
      (entrada instanceof Request ? entrada.method : 'GET')
    ).toUpperCase()

    // 1 · La respuesta exacta, con su consulta: es lo que hace que los filtros
    //     del resumen del CAPEX se muevan de verdad y no siempre igual.
    const exacta = grabacion[`${metodo} ${url.pathname}${url.search}`]
    if (exacta) return respuesta(exacta)

    // 2 · La misma ruta sin consulta. Un filtro que no se grabó enseña el
    //     conjunto entero, que es lo razonable: la pantalla sigue viva.
    const sinConsulta = grabacion[`${metodo} ${url.pathname}`]
    if (sinConsulta) return respuesta(sinConsulta)

    if (metodo !== 'GET') return problema(501, 'Prototipo de solo lectura', SOLO_LECTURA)

    const clave = `${metodo} ${url.pathname}`
    if (!fallos.has(clave)) {
      fallos.add(clave)
      console.warn('[prototipo] sin grabar:', clave)
    }
    return problema(501, 'Fuera del recorrido grabado', SIN_GRABAR)
  }
}

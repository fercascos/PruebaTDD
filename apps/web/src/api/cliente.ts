/**
 * Cliente HTTP de la API.
 *
 * Dos decisiones que se notan al usar la aplicación:
 *
 * 1. **El token de acceso vive en memoria, no en `localStorage`.** Un token en
 *    `localStorage` lo lee cualquier script que llegue a ejecutarse en la
 *    página; en memoria desaparece al cerrar la pestaña. El de refresco sí se
 *    guarda —si no, habría que iniciar sesión en cada recarga— y es el
 *    compromiso consciente de este diseño.
 *
 * 2. **El refresco es automático y se hace UNA sola vez.** Si dos peticiones
 *    caducan a la vez, comparten la misma promesa de refresco: sin eso, las
 *    dos rotarían el token, la segunda presentaría uno ya rotado y el servidor
 *    revocaría la familia entera por reutilización, echando al usuario.
 */

const BASE = '/api/v1'
const CLAVE_REFRESCO = 'tdd.refresh'

export class ErrorDeApi extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly detalle?: unknown,
  ) {
    super(message)
    this.name = 'ErrorDeApi'
  }

  /** El servidor rechazó la petición por el estado del recurso, no por su forma. */
  get esConflicto(): boolean {
    return this.status === 409
  }

  get esNoAutorizado(): boolean {
    return this.status === 401
  }
}

let tokenDeAcceso: string | null = null
let refrescoEnCurso: Promise<boolean> | null = null
const oyentes = new Set<(autenticado: boolean) => void>()

export function tokenActual(): string | null {
  return tokenDeAcceso
}

export function haySesion(): boolean {
  return tokenDeAcceso !== null || localStorage.getItem(CLAVE_REFRESCO) !== null
}

export function alCambiarSesion(oyente: (autenticado: boolean) => void): () => void {
  oyentes.add(oyente)
  return () => oyentes.delete(oyente)
}

function anunciar(autenticado: boolean): void {
  oyentes.forEach((o) => o(autenticado))
}

export function guardarSesion(acceso: string, refresco: string): void {
  tokenDeAcceso = acceso
  localStorage.setItem(CLAVE_REFRESCO, refresco)
  anunciar(true)
}

export function olvidarSesion(): void {
  tokenDeAcceso = null
  localStorage.removeItem(CLAVE_REFRESCO)
  anunciar(false)
}

async function refrescar(): Promise<boolean> {
  const refresco = localStorage.getItem(CLAVE_REFRESCO)
  if (!refresco) return false

  // Una sola promesa compartida: si dos peticiones caducan a la vez y ambas
  // refrescan, la segunda presentaría un token ya rotado y el servidor
  // revocaría la familia entera dando por robado el token.
  refrescoEnCurso ??= (async () => {
    try {
      const respuesta = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresco }),
      })
      if (!respuesta.ok) {
        olvidarSesion()
        return false
      }
      const datos = (await respuesta.json()) as { access_token: string; refresh_token: string }
      guardarSesion(datos.access_token, datos.refresh_token)
      return true
    } finally {
      refrescoEnCurso = null
    }
  })()
  return refrescoEnCurso
}

type Opciones = {
  method?: string
  body?: unknown
  cuerpoCrudo?: BodyInit
  signal?: AbortSignal
  /** Interno: evita reintentar el refresco en bucle. */
  reintentado?: boolean
}

async function peticion(ruta: string, opciones: Opciones = {}): Promise<Response> {
  const cabeceras: Record<string, string> = {}
  if (tokenDeAcceso) cabeceras.Authorization = `Bearer ${tokenDeAcceso}`

  let cuerpo = opciones.cuerpoCrudo
  if (opciones.body !== undefined) {
    cabeceras['Content-Type'] = 'application/json'
    cuerpo = JSON.stringify(opciones.body)
  }

  const respuesta = await fetch(`${BASE}${ruta}`, {
    method: opciones.method ?? 'GET',
    headers: cabeceras,
    body: cuerpo,
    signal: opciones.signal,
  })

  if (respuesta.status === 401 && !opciones.reintentado && (await refrescar())) {
    return peticion(ruta, { ...opciones, reintentado: true })
  }
  return respuesta
}

async function lanzarSiFalla(respuesta: Response): Promise<void> {
  if (respuesta.ok) return
  let detalle: unknown
  let mensaje = `Error ${respuesta.status}`
  try {
    detalle = await respuesta.json()
    const d = detalle as { detail?: unknown; title?: string }
    if (typeof d.detail === 'string') mensaje = d.detail
    else if (Array.isArray(d.detail)) {
      // Los errores de validación de FastAPI vienen como lista de campos. Se
      // resumen en una frase: el usuario no tiene que leer un JSON.
      mensaje = d.detail
        .map((e) => {
          const item = e as { loc?: unknown[]; msg?: string }
          const campo = (item.loc ?? []).slice(1).join('.')
          return campo ? `${campo}: ${item.msg}` : item.msg
        })
        .join('; ')
    } else if (d.title) mensaje = d.title
  } catch {
    /* La respuesta no traía JSON: se queda el mensaje genérico. */
  }
  if (respuesta.status === 401) olvidarSesion()
  throw new ErrorDeApi(respuesta.status, mensaje, detalle)
}

export async function obtener<T>(ruta: string, signal?: AbortSignal): Promise<T> {
  const r = await peticion(ruta, { signal })
  await lanzarSiFalla(r)
  return (await r.json()) as T
}

export async function enviar<T>(ruta: string, body: unknown, method = 'POST'): Promise<T> {
  const r = await peticion(ruta, { method, body })
  await lanzarSiFalla(r)
  return r.status === 204 ? (undefined as T) : ((await r.json()) as T)
}

/**
 * `DELETE`. Devuelve el cuerpo si lo hay: varios endpoints responden con la
 * entidad padre y sus totales ya recalculados —borrar una línea de CAPEX
 * devuelve el hallazgo—, y descartarlo obligaría a la interfaz a rehacer la
 * suma por su cuenta, que es donde aparecen los descuadres.
 */
export async function borrar<T = void>(ruta: string): Promise<T> {
  const r = await peticion(ruta, { method: 'DELETE' })
  await lanzarSiFalla(r)
  return r.status === 204 ? (undefined as T) : ((await r.json()) as T)
}

export async function subirFichero<T>(
  ruta: string,
  archivo: File,
  campos: Record<string, string | undefined> = {},
): Promise<T> {
  const formulario = new FormData()
  formulario.append('file', archivo)
  for (const [clave, valor] of Object.entries(campos)) {
    if (valor !== undefined && valor !== '') formulario.append(clave, valor)
  }
  // Sin `Content-Type`: el navegador tiene que poner el `boundary` del
  // multipart, y fijarlo a mano rompe la subida de forma difícil de depurar.
  const r = await peticion(ruta, { method: 'POST', cuerpoCrudo: formulario })
  await lanzarSiFalla(r)
  return (await r.json()) as T
}

/**
 * El binario de una ruta protegida, con la credencial y el reintento de
 * refresco que lleva cualquier otra petición.
 *
 * Existe porque un `<img src>` no puede llevar cabecera `Authorization`: el
 * token vive en memoria, no en una cookie, así que las imágenes hay que
 * traerlas con `fetch` y pintarlas desde un `blob:`. Lo usa `<Imagen>`.
 */
export async function peticionAutenticada(ruta: string, signal?: AbortSignal): Promise<Blob> {
  const r = await peticion(ruta, { signal })
  await lanzarSiFalla(r)
  return await r.blob()
}

export async function descargar(ruta: string, nombre: string): Promise<void> {
  const r = await peticion(ruta)
  await lanzarSiFalla(r)
  const blob = await r.blob()
  const url = URL.createObjectURL(blob)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombre
  enlace.click()
  URL.revokeObjectURL(url)
}

export async function iniciarSesion(email: string, password: string): Promise<void> {
  const r = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  await lanzarSiFalla(r)
  const datos = (await r.json()) as { access_token: string; refresh_token: string }
  guardarSesion(datos.access_token, datos.refresh_token)
}

export async function cerrarSesion(): Promise<void> {
  const refresco = localStorage.getItem(CLAVE_REFRESCO)
  if (refresco) {
    await peticion('/auth/logout', { method: 'POST', body: { refresh_token: refresco } }).catch(
      () => undefined,
    )
  }
  olvidarSesion()
}

/** Recupera la sesión al recargar la página, si el token de refresco sigue vivo. */
export async function restaurarSesion(): Promise<boolean> {
  if (tokenDeAcceso) return true
  return refrescar()
}

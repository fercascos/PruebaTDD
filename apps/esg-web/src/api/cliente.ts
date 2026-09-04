/**
 * Cliente de la API.
 *
 * El token no se guarda aquí: lo pide a quien sepa dárselo (`ponerProveedorDeToken`),
 * que en producción es MSAL —que lo renueva solo— y en desarrollo el token que
 * firma la propia API. Guardar aquí una copia caducaría a los cinco minutos y
 * el usuario vería «credencial no válida» sin haber hecho nada.
 */
export class ErrorDeApi extends Error {
  constructor(
    readonly estado: number,
    mensaje: string,
  ) {
    super(mensaje)
  }
}

type ProveedorDeToken = () => Promise<string | null>

let proveedor: ProveedorDeToken = async () => null

export function ponerProveedorDeToken(nuevo: ProveedorDeToken): void {
  proveedor = nuevo
}

export const BASE = import.meta.env.VITE_API_URL ?? ''

async function cabeceras(extra: Record<string, string> = {}): Promise<Record<string, string>> {
  const token = await proveedor()
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra
}

async function comprobar(respuesta: Response): Promise<never | Response> {
  if (respuesta.ok) return respuesta
  let detalle = respuesta.statusText
  try {
    const cuerpo = await respuesta.json()
    // FastAPI manda `detail`; con un error de validación es una lista.
    detalle = Array.isArray(cuerpo?.detail)
      ? cuerpo.detail.map((d: { msg?: string }) => d.msg ?? '').join('; ')
      : (cuerpo?.detail ?? detalle)
  } catch {
    /* la respuesta no era JSON: se queda el texto del estado */
  }
  throw new ErrorDeApi(respuesta.status, detalle)
}

export async function pedir<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  const respuesta = await fetch(`${BASE}${ruta}`, {
    ...opciones,
    headers: await cabeceras({
      ...(opciones.body && !(opciones.body instanceof FormData)
        ? { 'Content-Type': 'application/json' }
        : {}),
      ...((opciones.headers as Record<string, string>) ?? {}),
    }),
  })
  await comprobar(respuesta)
  if (respuesta.status === 204) return undefined as T
  return (await respuesta.json()) as T
}

/** Construye `?a=1&a=2` para los filtros de valores repetidos. */
export function consulta(parametros: Record<string, string | string[] | undefined>): string {
  const busqueda = new URLSearchParams()
  for (const [clave, valor] of Object.entries(parametros)) {
    if (valor === undefined) continue
    if (Array.isArray(valor)) valor.forEach((v) => busqueda.append(clave, v))
    else busqueda.append(clave, valor)
  }
  return busqueda.toString() ? `?${busqueda}` : ''
}

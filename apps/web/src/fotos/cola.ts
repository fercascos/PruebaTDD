/**
 * Cola de subida de fotografías · **lógica pura, sin React ni red**.
 *
 * Es la pieza que hace usable una visita de campo, y la que más se nota cuando
 * falla. El problema real: alguien selecciona 180 fotos desde el carrete con
 * cobertura irregular. Sin cola, el navegador abre 180 peticiones a la vez,
 * el móvil se queda sin memoria y las que fallan se pierden en silencio.
 *
 * Tres decisiones:
 *
 * 1. **Concurrencia limitada** (4 por defecto). Más no va más rápido con datos
 *    móviles y sí multiplica los tiempos de espera y los fallos.
 * 2. **Reintento con espera creciente**, pero solo ante fallos de red o del
 *    servidor. Un `409` de duplicado o un `415` de formato no mejoran por
 *    reintentarlos: se marcan y se sigue.
 * 3. **Nada se pierde en silencio.** Cada elemento acaba en un estado visible,
 *    y el recuento de pendientes está siempre a la vista.
 */

export type EstadoDeElemento = 'PENDIENTE' | 'SUBIENDO' | 'HECHO' | 'DUPLICADO' | 'FALLIDO'

export type Origen = 'ORDENADOR' | 'CARRETE' | 'CAMARA'

export type ElementoDeCola = {
  id: string
  archivo: File
  origen: Origen
  estado: EstadoDeElemento
  intentos: number
  error?: string
  /** Identificador de la foto ya subida, o de la que la duplica. */
  photoId?: string
  mensajeDeDuplicado?: string
}

export const CONCURRENCIA_POR_DEFECTO = 4
export const MAX_INTENTOS = 4

/** Códigos que no mejoran por reintentarse: es el fichero, no la red. */
const DEFINITIVOS = new Set([400, 409, 413, 415, 422])

export function esReintentable(status: number | undefined): boolean {
  if (status === undefined) return true // Fallo de red: reintentar tiene sentido.
  if (DEFINITIVOS.has(status)) return false
  return status >= 500 || status === 429 || status === 408
}

/**
 * Espera creciente con dispersión.
 *
 * La dispersión no es un adorno: sin ella, 180 fotos que fallan por un corte
 * de cobertura reintentan todas en el mismo instante y vuelven a tumbar la
 * conexión justo cuando se recupera.
 */
export function esperaMs(intento: number, aleatorio: () => number = Math.random): number {
  const base = Math.min(1000 * 2 ** (intento - 1), 16000)
  return Math.round(base * (0.5 + aleatorio() * 0.5))
}

export type Resumen = {
  total: number
  pendientes: number
  subiendo: number
  hechas: number
  duplicadas: number
  fallidas: number
  porcentaje: number
}

export function resumir(elementos: readonly ElementoDeCola[]): Resumen {
  const cuenta = (estado: EstadoDeElemento) => elementos.filter((e) => e.estado === estado).length
  const total = elementos.length
  const terminadas = cuenta('HECHO') + cuenta('DUPLICADO') + cuenta('FALLIDO')
  return {
    total,
    pendientes: cuenta('PENDIENTE'),
    subiendo: cuenta('SUBIENDO'),
    hechas: cuenta('HECHO'),
    duplicadas: cuenta('DUPLICADO'),
    fallidas: cuenta('FALLIDO'),
    porcentaje: total === 0 ? 0 : Math.round((terminadas / total) * 100),
  }
}

let contador = 0

export function crearElementos(archivos: readonly File[], origen: Origen): ElementoDeCola[] {
  return archivos.map((archivo) => ({
    id: `e${++contador}`,
    archivo,
    origen,
    estado: 'PENDIENTE' as const,
    intentos: 0,
  }))
}

/** Tipos que el servidor acepta. Filtrar aquí evita 180 rechazos remotos. */
const TIPOS_ADMITIDOS = /^image\/(jpeg|png|webp|heic|heif|tiff)$/i
const EXTENSIONES_ADMITIDAS = /\.(jpe?g|png|webp|heic|heif|tiff?)$/i

export function esImagenAdmitida(archivo: File): boolean {
  // Se mira el tipo Y la extensión: algunos navegadores no dan `type` para
  // HEIC, y descartar por eso las fotos de un iPhone sería el peor filtro
  // posible en la aplicación que más las va a recibir.
  return TIPOS_ADMITIDOS.test(archivo.type) || EXTENSIONES_ADMITIDAS.test(archivo.name)
}

export type ResultadoDeSubida =
  | { tipo: 'ok'; photoId: string }
  | { tipo: 'duplicado'; mensaje: string }
  | { tipo: 'error'; mensaje: string; status?: number }

export type Subidor = (elemento: ElementoDeCola) => Promise<ResultadoDeSubida>

type Opciones = {
  concurrencia?: number
  alCambiar?: (elementos: ElementoDeCola[]) => void
  dormir?: (ms: number) => Promise<void>
  aleatorio?: () => number
  senal?: AbortSignal
}

const dormirDeVerdad = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

/**
 * Procesa la cola entera. Devuelve los elementos con su estado final.
 *
 * Es una función y no un hook a propósito: así se puede probar sin montar
 * React ni un servidor, que es donde de verdad se comprueban el reintento y la
 * concurrencia.
 */
export async function procesar(
  elementos: ElementoDeCola[],
  subir: Subidor,
  opciones: Opciones = {},
): Promise<ElementoDeCola[]> {
  const {
    concurrencia = CONCURRENCIA_POR_DEFECTO,
    alCambiar,
    dormir = dormirDeVerdad,
    aleatorio = Math.random,
    senal,
  } = opciones

  let siguiente = 0
  const avisar = () => alCambiar?.([...elementos])

  async function trabajador(): Promise<void> {
    for (;;) {
      if (senal?.aborted) return
      const indice = siguiente++
      const elemento = elementos[indice]
      if (elemento === undefined) return
      if (elemento.estado !== 'PENDIENTE') continue

      for (;;) {
        elemento.estado = 'SUBIENDO'
        elemento.intentos += 1
        avisar()

        // Una excepción inesperada se trata como fallo de red: sin `status`,
        // `esReintentable` decide que merece otro intento. Lo que no puede
        // pasar es que la foto desaparezca sin dejar rastro.
        const resultado: ResultadoDeSubida = await subir(elemento).catch(
          (e: unknown): ResultadoDeSubida => ({
            tipo: 'error',
            mensaje: e instanceof Error ? e.message : 'Fallo de red',
          }),
        )

        if (resultado.tipo === 'ok') {
          elemento.estado = 'HECHO'
          elemento.photoId = resultado.photoId
          break
        }
        if (resultado.tipo === 'duplicado') {
          // No es un fallo: la foto ya está en el proyecto. Se marca aparte
          // para que el recuento de errores no se llene de falsos positivos.
          elemento.estado = 'DUPLICADO'
          elemento.mensajeDeDuplicado = resultado.mensaje
          break
        }
        if (!esReintentable(resultado.status) || elemento.intentos >= MAX_INTENTOS) {
          elemento.estado = 'FALLIDO'
          elemento.error = resultado.mensaje
          break
        }
        elemento.estado = 'PENDIENTE'
        avisar()
        await dormir(esperaMs(elemento.intentos, aleatorio))
        if (senal?.aborted) return
      }
      avisar()
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(concurrencia, elementos.length) }, () => trabajador()),
  )
  return elementos
}

/** Vuelve a poner en cola lo que falló, conservando lo que ya subió. */
export function reencolarFallidas(elementos: readonly ElementoDeCola[]): ElementoDeCola[] {
  return elementos.map((e) =>
    e.estado === 'FALLIDO' ? { ...e, estado: 'PENDIENTE' as const, intentos: 0, error: undefined } : e,
  )
}

import { describe, expect, it, vi } from 'vitest'
import {
  type ElementoDeCola,
  type ResultadoDeSubida,
  MAX_INTENTOS,
  crearElementos,
  esImagenAdmitida,
  esReintentable,
  esperaMs,
  procesar,
  reencolarFallidas,
  resumir,
} from './cola'

function archivo(nombre: string, tipo = 'image/jpeg'): File {
  return new File([new Uint8Array([1, 2, 3])], nombre, { type: tipo })
}

/** Sin espera real: probar el reintento no puede costar 30 segundos. */
const sinDormir = () => Promise.resolve()

describe('qué se acepta antes de subir', () => {
  it('acepta los formatos que el servidor admite', () => {
    for (const tipo of ['image/jpeg', 'image/png', 'image/webp', 'image/heic']) {
      expect(esImagenAdmitida(archivo('f', tipo))).toBe(true)
    }
  })

  it('acepta un HEIC aunque el navegador no le dé tipo', () => {
    // Algunos navegadores dejan `type` vacío para HEIC. Descartarlo por eso
    // sería el peor filtro posible en la aplicación que más los va a recibir.
    expect(esImagenAdmitida(archivo('IMG_0042.HEIC', ''))).toBe(true)
  })

  it('rechaza lo que no es una imagen', () => {
    expect(esImagenAdmitida(archivo('contrato.pdf', 'application/pdf'))).toBe(false)
  })
})

describe('qué merece reintentarse', () => {
  it('un fallo de red sí', () => {
    expect(esReintentable(undefined)).toBe(true)
  })

  it('un error del servidor sí', () => {
    expect(esReintentable(503)).toBe(true)
    expect(esReintentable(429)).toBe(true)
  })

  it('un duplicado o un formato inválido no mejoran por reintentarse', () => {
    for (const status of [409, 415, 422, 413]) {
      expect(esReintentable(status)).toBe(false)
    }
  })
})

describe('espera creciente', () => {
  it('crece con cada intento', () => {
    const fijo = () => 1
    expect(esperaMs(1, fijo)).toBeLessThan(esperaMs(2, fijo))
    expect(esperaMs(2, fijo)).toBeLessThan(esperaMs(3, fijo))
  })

  it('tiene techo: no espera minutos', () => {
    expect(esperaMs(20, () => 1)).toBeLessThanOrEqual(16000)
  })

  it('dispersa, para que 180 fotos no reintenten todas a la vez', () => {
    // Sin dispersión, un corte de cobertura hace que las 180 reintenten en el
    // mismo instante y vuelvan a tumbar la conexión al recuperarse.
    expect(esperaMs(3, () => 0)).not.toBe(esperaMs(3, () => 1))
  })
})

describe('proceso de la cola', () => {
  it('sube todas las fotos', async () => {
    const elementos = crearElementos([archivo('a.jpg'), archivo('b.jpg')], 'CARRETE')
    const subir = vi.fn(
      async (): Promise<ResultadoDeSubida> => ({ tipo: 'ok', photoId: 'p1' }),
    )

    await procesar(elementos, subir, { dormir: sinDormir })

    expect(subir).toHaveBeenCalledTimes(2)
    expect(elementos.every((e) => e.estado === 'HECHO')).toBe(true)
  })

  it('no abre más peticiones a la vez que la concurrencia', async () => {
    // Es la razón de existir de la cola: 180 peticiones simultáneas dejan sin
    // memoria a un móvil de gama media.
    const elementos = crearElementos(
      Array.from({ length: 12 }, (_, i) => archivo(`f${i}.jpg`)),
      'ORDENADOR',
    )
    let enVuelo = 0
    let maximo = 0
    const subir = async (): Promise<ResultadoDeSubida> => {
      enVuelo += 1
      maximo = Math.max(maximo, enVuelo)
      await Promise.resolve()
      enVuelo -= 1
      return { tipo: 'ok', photoId: 'p' }
    }

    await procesar(elementos, subir, { concurrencia: 3, dormir: sinDormir })

    expect(maximo).toBeLessThanOrEqual(3)
  })

  it('reintenta un fallo de red y acaba subiendo', async () => {
    const elementos = crearElementos([archivo('a.jpg')], 'CAMARA')
    let llamadas = 0
    const subir = async (): Promise<ResultadoDeSubida> => {
      llamadas += 1
      return llamadas < 3
        ? { tipo: 'error', mensaje: 'Fallo de red' }
        : { tipo: 'ok', photoId: 'p9' }
    }

    await procesar(elementos, subir, { dormir: sinDormir })

    expect(llamadas).toBe(3)
    expect(elementos[0]?.estado).toBe('HECHO')
  })

  it('no reintenta un duplicado: la foto ya está', async () => {
    const elementos = crearElementos([archivo('a.jpg')], 'ORDENADOR')
    const subir = vi.fn(
      async (): Promise<ResultadoDeSubida> => ({ tipo: 'duplicado', mensaje: 'Ya está' }),
    )

    await procesar(elementos, subir, { dormir: sinDormir })

    expect(subir).toHaveBeenCalledTimes(1)
    expect(elementos[0]?.estado).toBe('DUPLICADO')
  })

  it('se rinde tras el máximo de intentos y deja el motivo a la vista', async () => {
    // Nada se pierde en silencio: acaba en un estado visible con su error.
    const elementos = crearElementos([archivo('a.jpg')], 'ORDENADOR')
    const subir = async (): Promise<ResultadoDeSubida> => ({
      tipo: 'error',
      mensaje: 'El servidor no responde',
      status: 503,
    })

    await procesar(elementos, subir, { dormir: sinDormir })

    expect(elementos[0]?.estado).toBe('FALLIDO')
    expect(elementos[0]?.intentos).toBe(MAX_INTENTOS)
    expect(elementos[0]?.error).toBe('El servidor no responde')
  })

  it('una excepción inesperada tampoco pierde la foto', async () => {
    const elementos = crearElementos([archivo('a.jpg')], 'ORDENADOR')
    const subir = async (): Promise<ResultadoDeSubida> => {
      throw new Error('boom')
    }

    await procesar(elementos, subir, { dormir: sinDormir })

    expect(elementos[0]?.estado).toBe('FALLIDO')
    expect(elementos[0]?.error).toBe('boom')
  })

  it('avisa del progreso mientras trabaja', async () => {
    const elementos = crearElementos([archivo('a.jpg'), archivo('b.jpg')], 'CARRETE')
    const avisos: number[] = []

    await procesar(elementos, async () => ({ tipo: 'ok', photoId: 'p' }), {
      dormir: sinDormir,
      alCambiar: (e) => avisos.push(resumir(e).hechas),
    })

    expect(avisos.length).toBeGreaterThan(0)
    expect(avisos.at(-1)).toBe(2)
  })
})

describe('resumen y reencolado', () => {
  const elementos: ElementoDeCola[] = [
    { id: '1', archivo: archivo('a'), origen: 'ORDENADOR', estado: 'HECHO', intentos: 1 },
    { id: '2', archivo: archivo('b'), origen: 'ORDENADOR', estado: 'DUPLICADO', intentos: 1 },
    { id: '3', archivo: archivo('c'), origen: 'ORDENADOR', estado: 'FALLIDO', intentos: 4 },
    { id: '4', archivo: archivo('d'), origen: 'ORDENADOR', estado: 'PENDIENTE', intentos: 0 },
  ]

  it('cuenta cada estado por separado', () => {
    const r = resumir(elementos)
    expect(r).toMatchObject({ total: 4, hechas: 1, duplicadas: 1, fallidas: 1, pendientes: 1 })
  })

  it('el duplicado no cuenta como error', () => {
    // Si contara, el resumen asustaría sin motivo: la foto está en el proyecto.
    expect(resumir(elementos).fallidas).toBe(1)
  })

  it('el porcentaje cuenta lo terminado, no solo lo subido', () => {
    expect(resumir(elementos).porcentaje).toBe(75)
  })

  it('reencolar solo toca lo fallido', () => {
    const nuevos = reencolarFallidas(elementos)
    expect(nuevos.map((e) => e.estado)).toEqual([
      'HECHO',
      'DUPLICADO',
      'PENDIENTE',
      'PENDIENTE',
    ])
    expect(nuevos[2]?.intentos).toBe(0)
  })
})

// @vitest-environment node
//
// Node y no jsdom: el `File` de jsdom no implementa `arrayBuffer()`, que los
// navegadores tienen desde Safari 14. Es una carencia del entorno de pruebas,
// no del código, y correr aquí con el `File` nativo de Node prueba justo lo que
// interesa —que los bytes sobreviven— sin escribir un apaño en la aplicación.

/**
 * La cola persistida.
 *
 * Corre contra una IndexedDB de verdad (`fake-indexeddb`), no contra un doble:
 * lo que se quiere comprobar es que el binario sobrevive, y un doble que
 * devuelve lo que se le metió no demuestra nada de eso.
 */

import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import { comoCola, guardar, guardarVarias, olvidar, pendientesDe, vaciar } from './almacen'
import type { ElementoDeCola } from './cola'

const PROYECTO = 'proyecto-1'
const OTRO = 'proyecto-2'

function elemento(id: string, extra: Partial<ElementoDeCola> = {}): ElementoDeCola {
  return {
    id,
    archivo: new File([new Uint8Array([1, 2, 3, 4])], `${id}.jpg`, { type: 'image/jpeg' }),
    origen: 'CAMARA',
    estado: 'PENDIENTE',
    intentos: 0,
    ...extra,
  }
}

/** La única fila esperada. Falla con un mensaje útil si no hay exactamente una. */
function unica<T>(filas: readonly T[]): T {
  expect(filas).toHaveLength(1)
  const fila = filas[0]
  if (fila === undefined) throw new Error('sin filas')
  return fila
}

beforeEach(async () => {
  await vaciar(PROYECTO)
  await vaciar(OTRO)
})

describe('persistencia de la cola', () => {
  it('guarda el binario entero, no una referencia al fichero', async () => {
    // Un `File` de un `<input>` deja de ser legible en cuanto el navegador
    // olvida la página que lo abrió. Guardar solo la ruta habría dado una cola
    // llena de elementos que no se pueden subir.
    await guardar(PROYECTO, elemento('e1'))

    const fila = unica(await pendientesDe(PROYECTO))
    const bytes = new Uint8Array(await fila.archivo.arrayBuffer())
    expect([...bytes]).toEqual([1, 2, 3, 4])
    expect(fila.archivo.name).toBe('e1.jpg')
    expect(fila.archivo.type).toBe('image/jpeg')
  })

  it('conserva el orden en que se encolaron', async () => {
    await guardarVarias(PROYECTO, [elemento('a'), elemento('b'), elemento('c')])
    const ids = (await pendientesDe(PROYECTO)).map((f) => f.id)
    expect(ids).toEqual(['a', 'b', 'c'])
  })

  it('no mezcla las fotos de dos encargos', async () => {
    await guardar(PROYECTO, elemento('mia'))
    await guardar(OTRO, elemento('ajena'))

    expect((await pendientesDe(PROYECTO)).map((f) => f.id)).toEqual(['mia'])
    expect((await pendientesDe(OTRO)).map((f) => f.id)).toEqual(['ajena'])
  })

  it('guardar dos veces el mismo elemento lo actualiza, no lo duplica', async () => {
    await guardar(PROYECTO, elemento('e1'))
    await guardar(PROYECTO, elemento('e1', { estado: 'FALLIDO', intentos: 3, error: 'sin red' }))

    const fila = unica(await pendientesDe(PROYECTO))
    expect(fila.estado).toBe('FALLIDO')
    expect(fila.intentos).toBe(3)
  })

  it('olvida lo que ya está en el servidor', async () => {
    await guardarVarias(PROYECTO, [elemento('subida'), elemento('pendiente')])
    await olvidar('subida')
    expect((await pendientesDe(PROYECTO)).map((f) => f.id)).toEqual(['pendiente'])
  })

  it('sobrevive a que se cierre y se vuelva a abrir la base', async () => {
    await guardar(PROYECTO, elemento('e1'))
    // Cada operación abre y cierra su propia conexión: si el dato solo viviera
    // en la conexión anterior, esta segunda lectura no lo vería.
    expect(await pendientesDe(PROYECTO)).toHaveLength(1)
    expect(await pendientesDe(PROYECTO)).toHaveLength(1)
  })

  it('un proyecto sin nada devuelve una lista vacía, no un error', async () => {
    expect(await pendientesDe('proyecto-que-no-existe')).toEqual([])
  })
})

describe('volver a la cola', () => {
  it('lo que se quedó subiendo vuelve a pendiente', async () => {
    // Si la aplicación se cerró a mitad de una subida, esa foto no está en el
    // servidor. Dejarla en «subiendo» para siempre la mete en un limbo del que
    // nadie la saca.
    await guardar(PROYECTO, elemento('e1', { estado: 'SUBIENDO', intentos: 2 }))

    const vuelto = unica(comoCola(await pendientesDe(PROYECTO)))
    expect(vuelto.estado).toBe('PENDIENTE')
    // El corte de ayer no dice nada de la cobertura de hoy.
    expect(vuelto.intentos).toBe(0)
  })

  it('lo fallido sigue fallido, con su motivo, para poder reintentarlo a mano', async () => {
    await guardar(PROYECTO, elemento('e1', { estado: 'FALLIDO', intentos: 4, error: 'sin red' }))
    const vuelto = unica(comoCola(await pendientesDe(PROYECTO)))
    expect(vuelto.estado).toBe('FALLIDO')
    expect(vuelto.error).toBe('sin red')
    expect(vuelto.intentos).toBe(4)
  })

  it('el archivo recuperado sigue siendo subible', async () => {
    await guardar(PROYECTO, elemento('e1'))
    const vuelto = unica(comoCola(await pendientesDe(PROYECTO)))
    expect(vuelto.archivo).toBeInstanceOf(File)
    expect(vuelto.archivo.size).toBe(4)
  })

  it('mantiene el origen: una foto de cámara no se convierte en una del carrete', async () => {
    await guardarVarias(PROYECTO, [
      elemento('a', { origen: 'CAMARA' }),
      elemento('b', { origen: 'ORDENADOR' }),
    ])
    const vueltos = comoCola(await pendientesDe(PROYECTO))
    expect(vueltos.map((v) => v.origen)).toEqual(['CAMARA', 'ORDENADOR'])
  })
})

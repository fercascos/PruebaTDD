import { afterEach, describe, expect, it } from 'vitest'
import { leerEstado } from './red'

/**
 * La lectura del estado de red.
 *
 * Se prueba la función pura y no el hook: lo que importa aquí es la **decisión
 * en caso de duda**, y esa es la parte que no se ve montando un componente.
 */

function fingir(valor: unknown) {
  Object.defineProperty(navigator, 'onLine', { value: valor, configurable: true })
}

afterEach(() => fingir(true))

describe('leerEstado', () => {
  it('con conexión declarada, hay red', () => {
    fingir(true)
    expect(leerEstado()).toBe(true)
  })

  it('con `false` explícito, no hay red', () => {
    // Es el único caso en que `navigator.onLine` es de fiar: dice `true`
    // estando conectado a un wifi sin salida, pero no dice `false` teniéndola.
    fingir(false)
    expect(leerEstado()).toBe(false)
  })

  it('si el navegador no lo sabe, se asume que hay red', () => {
    // Un aviso falso de «sin conexión» asusta y hace desconfiar del resto de la
    // pantalla. Callarse cuando no se sabe es la opción menos dañina.
    fingir(undefined)
    expect(leerEstado()).toBe(true)
    fingir(null)
    expect(leerEstado()).toBe(true)
  })
})

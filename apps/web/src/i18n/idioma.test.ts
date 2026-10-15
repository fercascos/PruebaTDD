/** El traductor y el formato, probados de verdad `[REQ]` S-05. */
import { beforeEach, describe, expect, it } from 'vitest'
import { traducir } from './idioma'
import { EN } from './textos'

describe('traducir()', () => {
  beforeEach(() => localStorage.clear())

  it('en castellano devuelve la clave, que ES el texto', () => {
    expect(traducir('Proyectos')).toBe('Proyectos')
  })

  it('una clave que no existe sale tal cual, no como clave cruda', () => {
    // Es el respaldo que hace que un texto nuevo sin traducir se lea en
    // castellano en vez de salir como «nav.proyectos» delante de un cliente.
    expect(traducir('Un texto que nadie ha traducido')).toBe('Un texto que nadie ha traducido')
  })

  it('interpola después de traducir, no antes', () => {
    // El orden importa: la frase inglesa puede colocar los huecos en otro
    // sitio que la castellana.
    expect(traducir('Quedaron {n}', { n: 3 })).toContain('3')
  })

  it('deja el hueco si falta el valor, en vez de escribir «undefined»', () => {
    expect(traducir('Quedaron {n}')).toBe('Quedaron {n}')
  })
})

describe('el diccionario', () => {
  it('traduce al inglés y no deja el castellano puesto', () => {
    // Un descuido típico al traducir a mano: copiar la clave en el valor.
    const sinTraducir = Object.entries(EN).filter(([es, ingles]) => es === ingles)
    // Palabras que se escriben igual en los dos idiomas. «Error» entró con los
    // rótulos de una palabra: es el estado de una fila al importar una hoja, y
    // en inglés se llama igual.
    const iguales = ['Dashboard', 'English', 'Total', 'Red Flag / CAPEX', 'Error']
    expect(sinTraducir.map(([es]) => es).filter((es) => !iguales.includes(es))).toEqual([])
  })
})

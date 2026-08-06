import { describe, expect, it } from 'vitest'
import { COLORES, type Forma, grosorEnPixeles, nueva, relativa, tieneTamano } from './formas'

/**
 * La lógica de las anotaciones.
 *
 * Lo que se prueba es lo que de verdad puede salir mal: la conversión a
 * coordenadas relativas —el fallo clásico de las anotaciones— y el descarte de
 * las formas de tamaño cero. El pintado en sí se ve mirando la pantalla.
 */

function forma(extra: Partial<Forma> = {}): Forma {
  return {
    tipo: 'FLECHA',
    x1: 0.1,
    y1: 0.1,
    x2: 0.5,
    y2: 0.5,
    color: '#DC2626',
    grosor: 3,
    texto: '',
    ...extra,
  }
}

describe('coordenadas relativas', () => {
  it('convierte un punto del lienzo a fracción del lado', () => {
    expect(relativa(320, 120, 640, 480)).toEqual({ x: 0.5, y: 0.25 })
  })

  it('usa el tamaño mostrado, no el del canvas', () => {
    // El canvas se escala con CSS para caber en la pantalla. La misma posición
    // del dedo sobre un lienzo mostrado a la mitad debe dar la misma fracción.
    expect(relativa(160, 60, 320, 240)).toEqual(relativa(320, 120, 640, 480))
  })

  it('acota lo que se sale del lienzo', () => {
    // El puntero puede salirse mientras se arrastra. Sin acotar, el servidor
    // rechazaría la capa entera por una coordenada de 1,03.
    expect(relativa(700, -20, 640, 480)).toEqual({ x: 1, y: 0 })
  })

  it('un lienzo de tamaño cero no produce NaN', () => {
    // Pasa de verdad: el primer render, antes de que la imagen tenga medidas.
    // Un `NaN` en la capa se guardaría como `null` y rompería el informe.
    expect(relativa(10, 10, 0, 0)).toEqual({ x: 0, y: 0 })
  })
})

describe('formas nuevas', () => {
  it('nacen con el origen y el final en el mismo punto', () => {
    const f = nueva('RECTANGULO', 0.3, 0.4, '#059669', 5, '')
    expect([f.x1, f.y1, f.x2, f.y2]).toEqual([0.3, 0.4, 0.3, 0.4])
  })

  it('solo el texto lleva texto', () => {
    expect(nueva('FLECHA', 0, 0, '#000000', 3, 'Fisura').texto).toBe('')
    expect(nueva('TEXTO', 0, 0, '#000000', 3, 'Fisura').texto).toBe('Fisura')
  })
})

describe('formas de tamaño cero', () => {
  it('un clic sin arrastrar no cuenta como anotación', () => {
    // Sería invisible en el informe y estaría en la capa: el usuario creería
    // haber anotado algo.
    expect(tieneTamano(forma({ x2: 0.1, y2: 0.1 }))).toBe(false)
  })

  it('un arrastre mínimo tampoco', () => {
    expect(tieneTamano(forma({ x1: 0.5, y1: 0.5, x2: 0.502, y2: 0.501 }))).toBe(false)
  })

  it('un arrastre de verdad sí', () => {
    expect(tieneTamano(forma({ x1: 0.2, y1: 0.2, x2: 0.6, y2: 0.6 }))).toBe(true)
  })

  it('basta con moverse en un eje', () => {
    // Una línea horizontal es una anotación perfectamente legítima.
    expect(tieneTamano(forma({ x1: 0.2, y1: 0.5, x2: 0.8, y2: 0.5 }))).toBe(true)
  })
})

describe('grosor', () => {
  it('escala con el tamaño de la imagen', () => {
    // Un trazo fijo de 3 px no se ve sobre una foto de 4000, y tapa entera una
    // miniatura de 320. Es la misma regla que aplica el servidor al rasterizar.
    expect(grosorEnPixeles(3, 1000, 750)).toBe(3)
    expect(grosorEnPixeles(3, 4000, 3000)).toBe(12)
  })

  it('nunca baja de un píxel', () => {
    expect(grosorEnPixeles(1, 100, 75)).toBe(1)
  })
})

describe('paleta', () => {
  it('todos los colores son #RRGGBB, que es lo que el servidor acepta', () => {
    for (const c of COLORES) expect(c.valor).toMatch(/^#[0-9A-F]{6}$/)
  })
})

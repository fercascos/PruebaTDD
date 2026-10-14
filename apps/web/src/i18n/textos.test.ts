/**
 * La traducción, vigilada `[REQ]` S-05.
 *
 * Dos cosas que una tabla de textos hace mal si nadie mira:
 *
 * 1. **Se llena de entradas muertas.** Alguien reescribe una frase de la
 *    pantalla y la traducción vieja se queda ahí, sin que nada la use y sin
 *    que nadie lo note. La siguiente persona la lee y cree que está traducida.
 * 2. **Se queda a medias en silencio.** El respaldo al castellano —que existe
 *    a propósito, para no enseñar una clave cruda— también sirve para no
 *    enterarse de que faltan trescientas.
 *
 * Contra lo primero, la prueba es estricta: una entrada que no corresponda a
 * ningún texto del código **falla**. Contra lo segundo hay un trinquete: el
 * número de traducidas no puede bajar, y el mensaje dice cuántas quedan.
 */
import { describe, expect, it } from 'vitest'
import { extraer } from '../../herramientas/extraer-textos.mjs'
import { EN } from './textos'

/**
 * Cuántas había traducidas la última vez. **Solo puede subir.**
 *
 * `[LIM]` No es 516 todavía: la traducción se hizo por pantallas, empezando
 * por el camino que recorre quien abre la aplicación. Cuando llegue al total,
 * esta constante desaparece y la prueba pasa a exigirlas todas.
 */
const TRADUCIDAS_AL_MENOS = 204

const EN_EL_CODIGO = new Set(extraer().keys())

describe('el catálogo de textos', () => {
  it('no tiene entradas que ya no use nadie', () => {
    const muertas = Object.keys(EN).filter((c: string) => !EN_EL_CODIGO.has(c))
    expect(
      muertas,
      `Estas traducciones no corresponden a ningún texto de la interfaz. ` +
        `O la frase cambió en la pantalla y hay que actualizar la clave, o sobra:\n  ` +
        muertas.join('\n  '),
    ).toEqual([])
  })

  it('no retrocede: lo traducido sigue traducido', () => {
    const traducidas = [...EN_EL_CODIGO].filter((c) => c in EN).length
    const faltan = EN_EL_CODIGO.size - traducidas
    expect(
      traducidas,
      `Había ${TRADUCIDAS_AL_MENOS} textos traducidos y ahora hay ${traducidas}. ` +
        `Si ha añadido texto nuevo a una pantalla, tradúzcalo; si ha retirado una ` +
        `pantalla, baje el trinquete a conciencia. Quedan ${faltan} sin traducir.`,
    ).toBeGreaterThanOrEqual(TRADUCIDAS_AL_MENOS)
  })

  it('no deja una traducción vacía, que es peor que no tenerla', () => {
    const vacias = Object.entries(EN)
      .filter(([, v]) => !v.trim())
      .map(([k]) => k)
    expect(vacias).toEqual([])
  })

  it('respeta el inglés que el cliente ya usa en sus plantillas', () => {
    // No es una comprobación de estilo: traducir «Objeto» por «Object» sería
    // correcto y estaría mal, porque en su informe pone «Item». Si alguien
    // «mejora» esto, el informe y la pantalla dejan de llamar igual a lo mismo.
    expect(EN['Objeto']).toBe('Item')
    expect(EN['Zona afectada']).toBe('Affected area')
    expect(EN['Concepto']).toBe('Purpose')
    expect(EN['Corto plazo']).toBe('Short term')
    expect(EN['Riesgo']).toBe('Risk')
  })
})

/**
 * La paleta de los gráficos, **medida y no elegida a ojo**.
 *
 * Un consultor imprime estas pantallas en blanco y negro para una reunión, y
 * uno de cada doce hombres es daltónico. Que dos porciones de una tarta se
 * distingan no es una cuestión de gusto: es comprobable, y aquí está
 * comprobado con el validador de la guía de visualización
 * (`scripts/validate_palette.js`), no razonado.
 *
 * ## Qué se midió, y qué salió
 *
 * Una tarta es una forma **de todos contra todos**: el lector compara cualquier
 * porción con cualquier otra, no solo con la de al lado. Es el criterio
 * exigente, y con él:
 *
 * | Tonos | Resultado |
 * |---|---|
 * | 3 (azul, naranja, agua) | pasa · peor par ΔE 9,2 CVD · 24,0 visión normal |
 * | 4 (+ violeta) | **pasa** · peor par ΔE 9,2 CVD · 16,3 visión normal |
 * | 5 (+ magenta) | **falla**: magenta ↔ naranja ΔE 12,9 con visión normal, por debajo del suelo de 15 |
 *
 * Por eso la tarta admite **cuatro conceptos y el resto agrupado**, y no diez.
 * El quinto tono no se «añade con cuidado»: no existe uno que pase, y generar
 * un tono nuevo es exactamente lo que rompe todas las comprobaciones.
 *
 * ## Las dos excepciones, declaradas
 *
 * 1. **`OTROS` es gris a propósito.** No es un quinto concepto: es la cola
 *    agrupada, y va en gris de segundo plano. El validador lo marca como
 *    «lee gris» —que es justo lo que se busca—; se eligió `#6b6a66` y no un
 *    gris más claro porque con `#8a8880` la separación contra el agua caía a
 *    ΔE 14,3, por debajo del suelo. Se midió.
 * 2. **El agua queda en 2,74:1 contra el fondo**, por debajo de 3:1. La guía
 *    dice que eso obliga a texto visible o a tabla, y **no es descartable**:
 *    por eso cada porción lleva su nombre y su cifra escritos y hay una tabla
 *    con los mismos datos debajo. El color acompaña; no informa por sí solo.
 *
 * `[LIM]` Solo hay paleta clara. La aplicación no tiene modo oscuro —no hay una
 * sola regla `prefers-color-scheme` en la hoja de estilos—, así que no se
 * inventa una segunda paleta que nadie ha medido contra un fondo oscuro. Si
 * algún día lo hay, estos tonos **no valen invertidos**: en oscuro el violeta y
 * el azul caen a ΔE 9,8 y hay que volver a medir.
 */

/** Los cuatro tonos que pasan todos los pares, en orden fijo. */
export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#4a3aa7'] as const

/**
 * El gris de la cola agrupada. No es un tono de serie más.
 *
 * Va **siempre en último lugar**: el orden de los tonos es fijo y no se cicla,
 * porque el color tiene que seguir a la categoría y no a su puesto en el
 * ranking. Si mañana «Normativa» baja del segundo al cuarto sitio, cambia de
 * color —eso es inevitable en un reparto ordenado por importe— pero **la
 * leyenda y las etiquetas van al lado**, que es lo que impide leerlo mal.
 */
export const OTROS = '#6b6a66'

/** Cuántas categorías propias caben antes de agrupar el resto. Medido, no elegido. */
export const MAXIMO_DE_PORCIONES = SERIES.length

/**
 * Reparte una lista ordenada de mayor a menor en, como mucho, cuatro categorías
 * más «Otros».
 *
 * `[REQ]` Agrupar no es esconder: la porción agrupada dice **cuántas** hay
 * dentro, y la tabla de debajo las lista todas con su importe. Lo que se evita
 * es una tarta de diez porciones donde las seis últimas son rayas sin nombre.
 */
export function agrupar<T>(
  filas: readonly T[],
  importe: (fila: T) => number,
): { propias: T[]; resto: T[] } {
  // Ya vienen ordenadas de la API, pero no se da por hecho: si alguien cambia
  // el `ORDER BY`, agrupar la cola equivocada sería un error silencioso.
  const ordenadas = [...filas].sort((a, b) => importe(b) - importe(a))
  if (ordenadas.length <= MAXIMO_DE_PORCIONES + 1) {
    // Con cinco o menos caben todas: agrupar una sola en «Otros» esconde su
    // nombre sin ahorrar ninguna porción.
    return { propias: ordenadas, resto: [] }
  }
  return {
    propias: ordenadas.slice(0, MAXIMO_DE_PORCIONES),
    resto: ordenadas.slice(MAXIMO_DE_PORCIONES),
  }
}

/** El color de la porción `n`, con el gris para la cola.
 *
 * Un índice fuera de la paleta cae en el gris en vez de ciclar. Ciclar los
 * tonos es lo que hace que dos porciones distintas salgan del mismo color sin
 * que nadie se entere; caer en el gris es visible y `agrupar()` lo impide antes
 * de llegar aquí.
 */
export function colorDePorcion(indice: number, esOtros: boolean): string {
  return esOtros ? OTROS : (SERIES[indice] ?? OTROS)
}

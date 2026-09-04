/**
 * Paleta de los cuatro vectores.
 *
 * Los colores NO se asignan por tamaño ni por orden de aparición: van pegados
 * al vector. Si un filtro deja fuera el gas, la electricidad no cambia de
 * color; cuando el color se reparte por ranking, dos capturas de pantalla del
 * mismo panel con distinto filtro parecen dos edificios distintos.
 *
 * Los cuatro tonos son los cuatro primeros de la paleta categórica de
 * referencia, en su orden, y están comprobados con el validador en los dos
 * modos: separación para daltonismo ΔE 9,1 (claro) y 8,4 (oscuro), y ΔE de
 * visión normal 22,9 y 19,8, por encima del suelo de 15.
 *
 * En modo claro, el agua y los residuos quedan por debajo de 3:1 contra el
 * fondo: por eso los gráficos llevan SIEMPRE etiqueta directa y hay una tabla
 * con los mismos números. El color no es el único que dice qué es cada cosa.
 */
export const VECTORES = ['AGUA', 'ELECTRICIDAD', 'GAS', 'RESIDUOS'] as const
export type Vector = (typeof VECTORES)[number]

export const COLOR: Record<Vector, string> = {
  AGUA: 'var(--serie-1)',
  ELECTRICIDAD: 'var(--serie-2)',
  GAS: 'var(--serie-3)',
  RESIDUOS: 'var(--serie-4)',
}

export const ETIQUETA: Record<Vector, string> = {
  AGUA: 'Agua',
  ELECTRICIDAD: 'Electricidad',
  GAS: 'Gas',
  RESIDUOS: 'Residuos',
}

export const UNIDAD: Record<Vector, string> = {
  AGUA: 'm³',
  ELECTRICIDAD: 'kWh',
  GAS: 'kWh',
  RESIDUOS: 'kg',
}

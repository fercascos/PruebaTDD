/**
 * Cómo se escriben los números de los gráficos.
 *
 * En un sitio y no en cada componente porque el fallo que arregla es
 * exactamente el de repetirlo: `toFixed(1)` devuelve **siempre** un punto
 * decimal —«83.4 %»— y en castellano el separador decimal es la coma. Estaba
 * en la leyenda de la tarta, en su tabla y en una tarjeta de titular, tres
 * sitios distintos escritos el mismo día.
 */

/** Un porcentaje con un decimal: «83,4 %». */
const UN_DECIMAL = new Intl.NumberFormat('es-ES', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

export function porcentaje(parte: number, total: number): string {
  // Un total de cero no da un porcentaje: da una división por cero, que en
  // JavaScript es `Infinity` o `NaN` y se pinta tal cual en la pantalla.
  if (total <= 0) return '—'
  return `${UN_DECIMAL.format((parte / total) * 100)} %`
}

/**
 * `useGrouping` no es un capricho.
 *
 * En español, `Intl` omite el separador de millares en los números de cuatro
 * cifras —«4300,00 €»—, que es correcto en prosa y **malo en una columna de
 * importes**: al lado de «22.400,00 €» se lee peor y rompe la alineación de las
 * cifras. En una tabla de dinero manda la comparación, no la tipografía de un
 * párrafo.
 */
export const euros = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
  useGrouping: true,
})

export const eurosExactos = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  useGrouping: true,
})

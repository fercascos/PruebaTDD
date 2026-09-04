const ES = 'es-ES'

/** Cantidades: sin decimales por encima de mil, dos por debajo. Un consumo de
 *  12.480,3271 kWh en una tarjeta no informa: ocupa. */
export function cantidad(valor: number | string | null | undefined): string {
  if (valor === null || valor === undefined) return '—'
  const n = typeof valor === 'string' ? Number(valor) : valor
  if (Number.isNaN(n)) return '—'
  const decimales = Math.abs(n) >= 1000 ? 0 : 2
  return n.toLocaleString(ES, {
    minimumFractionDigits: decimales,
    maximumFractionDigits: decimales,
  })
}

export function porcentaje(valor: number | string | null | undefined): string {
  if (valor === null || valor === undefined) return '—'
  const n = typeof valor === 'string' ? Number(valor) : valor
  if (Number.isNaN(n)) return '—'
  return `${n > 0 ? '+' : ''}${n.toLocaleString(ES, { maximumFractionDigits: 1 })} %`
}

const MESES = [
  'ene', 'feb', 'mar', 'abr', 'may', 'jun',
  'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
]

/** «2025-03-01» → «mar 25». La etiqueta del eje no puede ocupar más que la barra. */
export function mesCorto(iso: string): string {
  const [anio, mes] = iso.split('-')
  return `${MESES[Number(mes) - 1]} ${anio.slice(2)}`
}

export function mesLargo(iso: string): string {
  const [anio, mes] = iso.split('-')
  return `${MESES[Number(mes) - 1]} de ${anio}`
}

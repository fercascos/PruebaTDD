import { useCallback, useEffect, useState } from 'react'
import { obtener } from '../api/cliente'
import type { Hallazgo } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

const PLAZOS = ['CORTO', 'MEDIO', 'LARGO', 'MEJORAS', 'OTRO'] as const

const euros = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
})

/**
 * Hallazgos y CAPEX.
 *
 * La tabla replica la del informe a propósito: **una fila por actuación**, con
 * una columna por plazo. Una actuación recurrente (P-44) tiene varias líneas y
 * aquí se ve como una sola fila con dos columnas rellenas, que es como aparece
 * en el Excel del cliente. Enseñarla de otra forma obligaría al consultor a
 * traducir mentalmente entre la pantalla y lo que va a entregar.
 */
export function PestanaCapex({ projectId }: { projectId: string }) {
  const [hallazgos, setHallazgos] = useState<Hallazgo[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(() => {
    obtener<Hallazgo[]>(`/projects/${projectId}/findings`)
      .then(setHallazgos)
      .catch((e: Error) => setError(e.message))
  }, [projectId])

  useEffect(recargar, [recargar])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!hallazgos) return <p className="cargando">Cargando hallazgos…</p>
  if (hallazgos.length === 0) {
    return (
      <Vacio>
        Todavía no hay hallazgos. En campo se crean desde la propia fotografía, que hereda el activo
        y la zona.
      </Vacio>
    )
  }

  const totales = new Map<string, number>()
  for (const h of hallazgos) {
    for (const l of h.capex_lines) {
      totales.set(
        l.time_horizon_code,
        (totales.get(l.time_horizon_code) ?? 0) + Number(l.amount),
      )
    }
  }
  const totalGeneral = [...totales.values()].reduce((a, b) => a + b, 0)
  const sinValidar = hallazgos
    .flatMap((h) => h.capex_lines)
    .filter((l) => l.price_status !== 'VALIDADO' && Number(l.amount) > 0)

  return (
    <>
      {sinValidar.length > 0 && (
        <Mensaje tipo="aviso">
          {sinValidar.length} líneas con precio sin validar, por{' '}
          {euros.format(sinValidar.reduce((a, l) => a + Number(l.amount), 0))}. Generar así es
          legítimo para un borrador interno; enviarlo al cliente sin revisarlo, no.
        </Mensaje>
      )}

      <table className="tabla capex">
        <thead>
          <tr>
            <th>Actuación</th>
            <th>Estado</th>
            {PLAZOS.map((p) => (
              <th key={p} className="numerica">
                {p}
              </th>
            ))}
            <th className="numerica">Total</th>
          </tr>
        </thead>
        <tbody>
          {hallazgos.map((h) => {
            const porPlazo = new Map(h.capex_lines.map((l) => [l.time_horizon_code, l]))
            return (
              <tr key={h.id}>
                <td>
                  <strong>{h.title}</strong>
                  {h.capex_lines.length > 1 && (
                    <em className="ayuda"> · actuación recurrente</em>
                  )}
                </td>
                <td>
                  <span className={`estado e-${h.status.toLowerCase()}`}>{h.status}</span>
                </td>
                {PLAZOS.map((p) => {
                  const linea = porPlazo.get(p)
                  return (
                    <td key={p} className="numerica">
                      {linea ? euros.format(Number(linea.amount)) : '—'}
                    </td>
                  )
                })}
                <td className="numerica">
                  <strong>{euros.format(Number(h.total_amount))}</strong>
                </td>
              </tr>
            )
          })}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={2}>Total</td>
            {PLAZOS.map((p) => (
              <td key={p} className="numerica">
                {totales.has(p) ? euros.format(totales.get(p) ?? 0) : '—'}
              </td>
            ))}
            <td className="numerica">
              <strong>{euros.format(totalGeneral)}</strong>
            </td>
          </tr>
        </tfoot>
      </table>
    </>
  )
}

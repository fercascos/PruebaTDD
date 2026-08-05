import { useEffect, useState } from 'react'
import { obtener } from '../api/cliente'
import type { Activo } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

export function PestanaActivos({ projectId }: { projectId: string }) {
  const [activos, setActivos] = useState<Activo[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    obtener<Activo[]>(`/projects/${projectId}/assets`)
      .then(setActivos)
      .catch((e: Error) => setError(e.message))
  }, [projectId])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!activos) return <p className="cargando">Cargando activos…</p>
  if (activos.length === 0) {
    return (
      <Vacio>
        Este encargo todavía no tiene activos. Un proyecto sin activos no sale de borrador.
      </Vacio>
    )
  }

  return (
    <table className="tabla">
      <thead>
        <tr>
          <th>Nombre</th>
          <th>Código</th>
          <th>Ciudad</th>
          <th>Año</th>
          <th className="numerica">Superficie construida</th>
        </tr>
      </thead>
      <tbody>
        {activos.map((a) => (
          <tr key={a.id}>
            <td>{a.name}</td>
            <td>{a.asset_code ?? '—'}</td>
            <td>{a.city ?? '—'}</td>
            <td>{a.year_built ?? '—'}</td>
            <td className="numerica">
              {a.total_built_sqm ? `${Number(a.total_built_sqm).toLocaleString('es-ES')} m²` : '—'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

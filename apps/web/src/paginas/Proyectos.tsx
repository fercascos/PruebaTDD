import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { obtener } from '../api/cliente'
import type { Proyecto } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

export function Proyectos() {
  const [proyectos, setProyectos] = useState<Proyecto[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    obtener<Proyecto[]>('/projects')
      .then(setProyectos)
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!proyectos) return <p className="cargando">Cargando proyectos…</p>
  if (proyectos.length === 0) {
    return <Vacio>Todavía no hay ningún encargo dado de alta en esta organización.</Vacio>
  }

  return (
    <>
      <h1>Proyectos</h1>
      <table className="tabla">
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Estado</th>
            <th>Moneda</th>
          </tr>
        </thead>
        <tbody>
          {proyectos.map((p) => (
            <tr key={p.id}>
              <td>
                <Link to={`/proyectos/${p.id}`}>{p.internal_code}</Link>
              </td>
              <td>{p.name}</td>
              <td>
                <span className={`estado e-${p.status.toLowerCase()}`}>{p.status}</span>
              </td>
              <td>{p.currency}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

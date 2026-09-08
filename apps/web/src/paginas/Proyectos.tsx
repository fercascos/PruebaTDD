import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { obtener } from '../api/cliente'
import type { Proyecto } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

/**
 * La lista de proyectos.
 *
 * `[REQ]` Las columnas son las de la revisión del prototipo, **en este orden**:
 * código, nombre, cliente, arranque, cierre y estado. Se lee de izquierda a
 * derecha como se pregunta —«el 2026-107, el de Getafe, ¿de quién era y cuándo
 * cierra?»— y por eso el cliente va tercero y no al final.
 *
 * La moneda se ha ido: era una columna repetida en todas las filas que nadie
 * mira, y el sitio lo ocupan ahora las fechas.
 */

/** Una fecha ISO como la escribe la gente aquí. Vacía si no hay. */
function fecha(iso: string | null): string {
  if (!iso) return '—'
  const [a, m, d] = iso.split('-')
  return `${d}/${m}/${a}`
}

export function Proyectos() {
  const [proyectos, setProyectos] = useState<Proyecto[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const navegar = useNavigate()

  const cabecera = (
    <header className="ficha">
      <h1>Proyectos</h1>
      <button type="button" onClick={() => navegar('/proyectos/nuevo')}>
        Nuevo proyecto
      </button>
    </header>
  )

  useEffect(() => {
    obtener<Proyecto[]>('/projects')
      .then(setProyectos)
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!proyectos) return <p className="cargando">Cargando proyectos…</p>
  if (proyectos.length === 0) {
    return (
      <>
        {cabecera}
        <Vacio>Todavía no hay ningún proyecto dado de alta en esta organización.</Vacio>
      </>
    )
  }

  return (
    <>
      {cabecera}
      <div className="desbordable">
        <table className="tabla">
          <thead>
            <tr>
              <th scope="col">Código</th>
              <th scope="col">Proyecto</th>
              <th scope="col">Cliente</th>
              <th scope="col">Arranque</th>
              <th scope="col">Cierre</th>
              <th scope="col">Estado</th>
            </tr>
          </thead>
          <tbody>
            {proyectos.map((p) => (
              <tr key={p.id}>
                <td className="codigo">
                  <Link to={`/proyectos/${p.id}`}>{p.internal_code}</Link>
                </td>
                <td>{p.name}</td>
                <td>
                  {p.client_name ?? '—'}
                  {/* `[REQ]` Un proyecto colgando de un cliente que nadie ha
                      revisado tiene que verse desde la lista: si no, el aviso
                      se queda en el buzón del administrador y aquí parece un
                      cliente como los demás. */}
                  {p.client_pending_validation && (
                    <span className="pastilla aviso" title="Escrito al dar de alta; falta validarlo">
                      sin validar
                    </span>
                  )}
                </td>
                <td className="fecha">{fecha(p.start_date)}</td>
                <td className="fecha">{fecha(p.close_date)}</td>
                <td>
                  <span className={`estado e-${p.status.toLowerCase()}`}>{p.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

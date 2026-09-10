import { useCallback, useEffect, useState } from 'react'
import { NavLink, Route, Routes, useParams } from 'react-router-dom'
import { obtener } from '../api/cliente'
import type { Proyecto } from '../api/tipos'
import { Mensaje } from '../ui/Marco'
import { PestanaActivos } from './PestanaActivos'
import { EspacioDelActivo } from './EspacioDelActivo'
import { PestanaInformes } from './PestanaInformes'
import { PestanaRiesgos } from './PestanaRiesgos'
import { ResumenDelProyecto } from './ResumenDelProyecto'
import { Dashboard } from './Dashboard'

export function FichaDeProyecto() {
  const { id = '' } = useParams()
  const [proyecto, setProyecto] = useState<Proyecto | null>(null)
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(() => {
    obtener<Proyecto>(`/projects/${id}`)
      .then(setProyecto)
      .catch((e: Error) => setError(e.message))
  }, [id])

  useEffect(recargar, [recargar])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!proyecto) return <p className="cargando">Cargando el proyecto…</p>

  return (
    <>
      <header className="ficha">
        <div>
          <h1>
            {proyecto.internal_code} · {proyecto.name}
          </h1>
          {/* `[REQ]` El cliente, en la cabecera. Quien abre un proyecto a media
              mañana necesita saber de quién es sin bajar a ninguna pestaña: es
              lo que decide el tono de un correo y lo que se pregunta primero. */}
          {proyecto.client_name && (
            <p className="cliente-del-proyecto">
              {proyecto.client_name}
              {proyecto.client_pending_validation && (
                <span className="pastilla aviso">cliente sin validar</span>
              )}
            </p>
          )}
        </div>
        <span className={`estado e-${proyecto.status.toLowerCase()}`}>{proyecto.status}</span>
      </header>

      {/* `[REQ]` §3.1-§3.2 · **Cinco pestañas, y el orden es el que pidió el
          cliente**: primero el Resumen, después los activos —cada uno con su
          espacio—, y al final lo general, que es Dashboard, Riesgos e Informe.

          Eran diez. Documentación, Fotografías, Mapa, Inventario y Hallazgos y
          CAPEX **se han mudado dentro del activo**, que es donde ocurre el
          trabajo; el mapa del proyecto entero es ahora un bloque del Resumen.
          Tenerlas aquí obligaba a filtrar por activo en cinco sitios distintos
          para reconstruir a mano lo que se sabe de un edificio. */}
      <nav className="pestanas">
        <NavLink to={`/proyectos/${id}`} end>
          Resumen
        </NavLink>
        <NavLink to={`/proyectos/${id}/activos`}>Activos</NavLink>
        <NavLink to={`/proyectos/${id}/dashboard`}>Dashboard</NavLink>
        <NavLink to={`/proyectos/${id}/riesgos`}>Riesgos</NavLink>
        <NavLink to={`/proyectos/${id}/informes`}>Informe final</NavLink>
      </nav>

      <Routes>
        <Route
          index
          element={
            <ResumenDelProyecto projectId={id} proyecto={proyecto} alGuardar={recargar} />
          }
        />
        <Route path="activos" element={<PestanaActivos projectId={id} />} />
        <Route path="activos/:assetId/*" element={<EspacioDelActivo projectId={id} />} />
        <Route path="dashboard" element={<Dashboard projectId={id} />} />
        <Route path="riesgos" element={<PestanaRiesgos projectId={id} />} />
        <Route path="informes" element={<PestanaInformes projectId={id} />} />
      </Routes>
    </>
  )
}

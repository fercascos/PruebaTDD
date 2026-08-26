import { Suspense, lazy, useEffect, useState } from 'react'
import { NavLink, Route, Routes, useParams } from 'react-router-dom'
import { obtener } from '../api/cliente'
import type { Proyecto } from '../api/tipos'
import { Mensaje } from '../ui/Marco'
import { PestanaFases } from './PestanaFases'
import { PestanaDocumentacion } from './PestanaDocumentacion'
import { PestanaActivos } from './PestanaActivos'
import { PestanaFotos } from './PestanaFotos'
import { PestanaCapex } from './PestanaCapex'
import { PestanaEquipo } from './PestanaEquipo'
import { PestanaInformes } from './PestanaInformes'
import { PestanaRiesgos } from './PestanaRiesgos'

/**
 * El mapa se carga aparte, solo al abrir su pestaña.
 *
 * Leaflet pesa ~150 KB y esta es una aplicación que se usa en obra, con datos
 * móviles y a veces con una barra de cobertura. Meterlo en el paquete inicial
 * haría más lenta la entrada a todo el mundo por una pantalla que muchos no
 * van a abrir. El trozo aparte sigue precacheándose para funcionar sin red: el
 * plugin del service worker recorre todos los `.js` del empaquetado.
 */
const PestanaMapa = lazy(() =>
  import('./PestanaMapa').then((m) => ({ default: m.PestanaMapa })),
)

export function FichaDeProyecto() {
  const { id = '' } = useParams()
  const [proyecto, setProyecto] = useState<Proyecto | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    obtener<Proyecto>(`/projects/${id}`)
      .then(setProyecto)
      .catch((e: Error) => setError(e.message))
  }, [id])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!proyecto) return <p className="cargando">Cargando el encargo…</p>

  return (
    <>
      <header className="ficha">
        <h1>
          {proyecto.internal_code} · {proyecto.name}
        </h1>
        <span className={`estado e-${proyecto.status.toLowerCase()}`}>{proyecto.status}</span>
      </header>

      {/* Las pestañas siguen los dos ejes del proyecto: el estado va arriba, y
          las fases —el trabajo real, que avanza en paralelo— tienen la suya. */}
      <nav className="pestanas">
        <NavLink to={`/proyectos/${id}`} end>
          Fases
        </NavLink>
        <NavLink to={`/proyectos/${id}/documentacion`}>Documentación</NavLink>
        <NavLink to={`/proyectos/${id}/activos`}>Activos</NavLink>
        <NavLink to={`/proyectos/${id}/fotos`}>Fotografías</NavLink>
        <NavLink to={`/proyectos/${id}/mapa`}>Mapa</NavLink>
        <NavLink to={`/proyectos/${id}/equipo`}>Inventario</NavLink>
        <NavLink to={`/proyectos/${id}/capex`}>Hallazgos y CAPEX</NavLink>
        <NavLink to={`/proyectos/${id}/riesgos`}>Riesgos</NavLink>
        <NavLink to={`/proyectos/${id}/informes`}>Informes</NavLink>
      </nav>

      <Routes>
        <Route index element={<PestanaFases projectId={id} />} />
        <Route path="documentacion" element={<PestanaDocumentacion projectId={id} />} />
        <Route path="activos" element={<PestanaActivos projectId={id} />} />
        <Route path="fotos" element={<PestanaFotos projectId={id} />} />
        <Route
          path="mapa"
          element={
            <Suspense fallback={<p className="cargando">Cargando el mapa…</p>}>
              <PestanaMapa projectId={id} />
            </Suspense>
          }
        />
        <Route path="equipo" element={<PestanaEquipo projectId={id} />} />
        <Route path="capex" element={<PestanaCapex projectId={id} />} />
        <Route path="riesgos" element={<PestanaRiesgos projectId={id} />} />
        <Route path="informes" element={<PestanaInformes projectId={id} />} />
      </Routes>
    </>
  )
}

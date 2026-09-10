import { Suspense, lazy, useCallback, useEffect, useState } from 'react'
import { NavLink, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { obtener } from '../api/cliente'
import type { Activo } from '../api/tipos'
import { Mensaje } from '../ui/Marco'
import { ArbolDeCapex } from './ArbolDeCapex'
import { ArbolDeUbicaciones } from './ArbolDeUbicaciones'
import { DocumentacionDelActivo } from './DocumentacionDelActivo'
import { FichaDeActivo } from './FichaDeActivo'
import { InventarioDelActivo } from './InventarioDelActivo'
import { PestanaEquipo } from './PestanaEquipo'
import { PestanaFotos } from './PestanaFotos'
import { VisitaDelActivo } from './VisitaDelActivo'

/** Leaflet pesa ~150 KB: se carga solo al abrir la sección que lo usa. */
const MapaDeActivos = lazy(() =>
  import('./MapaDeActivos').then((m) => ({ default: m.MapaDeActivos })),
)
/** El mapa de FOTOGRAFÍAS (§15.9), que es otra cosa: ver si la visita cubrió el
 *  edificio o se quedó en la fachada. Por eso vive en la Visita y no en Detalle. */
const MapaDeFotos = lazy(() =>
  import('./PestanaMapa').then((m) => ({ default: m.PestanaMapa })),
)

/**
 * El **espacio de un activo** `[REQ]` §3.2 de `docs/23`.
 *
 * Es el cambio de fondo del rediseño, y lo confirmó el cliente al revisar el
 * prototipo: *«la parte de activo con la apertura de un espacio por cada activo
 * que contenga Detalle, Documentación, Visita, Inventario y CAPEX»*.
 *
 * ## Por qué un espacio y no un formulario largo
 *
 * La primera versión de esto apilaba las secciones una debajo de otra dentro de
 * la ficha: siete mil píxeles de alto, y llegar al CAPEX exigía pasar por
 * delante de todo lo demás. Cinco pestañas dentro del activo hacen que cada
 * sección se abra sola y que la dirección web diga en cuál se está, que es lo
 * que permite mandarle a alguien «mira la visita de la Nave A».
 *
 * ## Cinco secciones, y las cuatro que se mudan aquí
 *
 * Documentación, fotografías, inventario y CAPEX **dejan de ser pestañas del
 * proyecto**. No se reescriben: las mismas pantallas reciben ahora el activo
 * fijado y esconden su desplegable, porque dentro de un edificio elegir otro
 * edificio es salirse de la pantalla en la que se está.
 *
 * - **Detalle** lleva la ficha, el mapa de este activo y su árbol de ubicaciones.
 * - **Visita** lleva los datos, el equipo implicado y **las fotografías**, que
 *   es donde el cliente las puso: su bloque V3 dice «aquí incluye la sección de
 *   fotos que hay actualmente desarrollado».
 * - **Inventario** lleva los descriptivos, «pasa a CAPEX» y la ficha de equipo.
 *
 * `[LIM]` **Documentación está por construir.** El diseño está cerrado —el árbol
 * de 73 nodos de la hoja v2— y la sección lo dice con letras en vez de fingir.
 */

const SECCIONES = [
  ['', 'Detalle'],
  ['documentacion', 'Documentación'],
  ['visita', 'Visita'],
  ['inventario', 'Inventario'],
  ['capex', 'CAPEX'],
] as const

export function EspacioDelActivo({ projectId }: { projectId: string }) {
  const { assetId = '' } = useParams()
  const navegar = useNavigate()
  const [activo, setActivo] = useState<Activo | null>(null)
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(() => {
    obtener<Activo>(`/assets/${assetId}`)
      .then(setActivo)
      .catch((e: Error) => setError(e.message))
  }, [assetId])

  useEffect(recargar, [recargar])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!activo) return <p className="cargando">Cargando el activo…</p>

  const base = `/proyectos/${projectId}/activos/${assetId}`

  return (
    <section className="espacio-activo">
      <header className="cabecera-activo">
        <button
          type="button"
          className="enlace volver"
          onClick={() => navegar(`/proyectos/${projectId}/activos`)}
        >
          ← Todos los activos
        </button>
        <h2>
          {activo.name}
          {activo.asset_code && <span className="codigo"> · {activo.asset_code}</span>}
        </h2>
        {(activo.address_line || activo.city) && (
          <p className="ayuda">
            {[activo.address_line, activo.city].filter(Boolean).join(', ')}
          </p>
        )}
      </header>

      <nav className="pestanas secundarias">
        {SECCIONES.map(([ruta, nombre]) => (
          <NavLink key={ruta} to={ruta ? `${base}/${ruta}` : base} end={ruta === ''}>
            {nombre}
          </NavLink>
        ))}
      </nav>

      <Routes>
        <Route
          index
          element={
            <>
              <FichaDeActivo
                projectId={projectId}
                activo={activo}
                alGuardar={recargar}
                alCancelar={() => navegar(`/proyectos/${projectId}/activos`)}
              />
              {/* `[REQ]` §3.2 a · «Detalle, incluyendo un mapa con la
                  localización del activo concreto». Va debajo de la ficha
                  porque primero se identifica el edificio y después se sitúa. */}
              <section className="mapa-del-activo">
                <h3>Dónde está</h3>
                <Suspense fallback={<p className="cargando">Cargando el mapa…</p>}>
                  <MapaDeActivos projectId={projectId} assetId={assetId} />
                </Suspense>
              </section>
              <ArbolDeUbicaciones assetId={assetId} />
            </>
          }
        />
        <Route
          path="documentacion"
          element={<DocumentacionDelActivo projectId={projectId} assetId={assetId} />}
        />
        <Route
          path="visita"
          element={
            <>
              <VisitaDelActivo activo={activo} />
              <section className="fotos-del-activo">
                <h3>Fotografías de la visita</h3>
                <PestanaFotos projectId={projectId} assetId={assetId} />
              </section>
              {/* `[REQ]` §15.9 · El mapa de fotografías responde a una pregunta
                  de la visita —¿se cubrió el edificio o se quedó en la
                  fachada?—, así que su sitio es este y no el Detalle. */}
              <section className="mapa-de-fotos">
                <h3>Dónde se hizo cada fotografía</h3>
                <Suspense fallback={<p className="cargando">Cargando el mapa…</p>}>
                  <MapaDeFotos projectId={projectId} assetId={assetId} />
                </Suspense>
              </section>
            </>
          }
        />
        <Route
          path="inventario"
          element={
            <>
              <InventarioDelActivo projectId={projectId} assetId={assetId} />
              <section className="equipo-del-activo">
                <h3>Ficha de cada equipo</h3>
                <p className="ayuda">
                  El detalle completo: fabricante, número de serie, mantenimiento preventivo y
                  vida residual, que se calcula al leer y nunca se teclea.
                </p>
                <PestanaEquipo projectId={projectId} assetId={assetId} />
              </section>
            </>
          }
        />
        <Route
          path="capex"
          element={<ArbolDeCapex projectId={projectId} assetId={assetId} />}
        />
      </Routes>
    </section>
  )
}

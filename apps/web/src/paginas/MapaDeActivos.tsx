import L from 'leaflet'
// Sin esto los controles de Leaflet salen sin estilo: el zoom se solapa con
// la escala y las chinchetas se descolocan. Lo importa cada componente que
// monta un mapa; Vite lo deduplica en la hoja del trozo cargado en diferido.
import 'leaflet/dist/leaflet.css'
import { useCallback, useEffect, useRef, useState } from 'react'
import { obtener } from '../api/cliente'
import type { Activo } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

/**
 * Dónde están los **activos** `[REQ]` §3.1 y §3.2 a de `docs/23`.
 *
 * El cliente lo pidió dos veces al revisar el prototipo: en el Resumen, *«todas
 * las ubicaciones de todos los activos del proyecto en un mismo mapa»*; y en el
 * detalle de cada activo, *«un mapa con la localización del activo concreto»*.
 *
 * ## No es el mapa de fotografías, y por eso es otro componente
 *
 * `PestanaMapa` existe desde §15.9 y pinta **fotografías**: sirve para ver si la
 * visita cubrió el edificio o se quedó en la fachada. Reutilizarlo aquí producía
 * una pantalla que decía «0 situadas · 4 sin coordenadas» sobre un proyecto con
 * dos activos perfectamente localizados: contestaba otra pregunta.
 *
 * Un activo tiene sus propias coordenadas en la ficha, puestas a mano o
 * propuestas por el geocodificador y **aceptadas por una persona**. Eso es lo
 * que se pinta aquí.
 *
 * ## Sin cartografía de fondo por omisión
 *
 * La misma decisión que en el mapa de fotografías, y por el mismo motivo: la
 * biblioteca es libre, las teselas no. Sin `VITE_MAP_TILE_URL` la aplicación
 * **no contacta con nadie** y el mapa sigue situando y midiendo. Una due
 * diligence no debería filtrar a un tercero qué edificio se está comprando.
 */

const TESELAS: string = import.meta.env.VITE_MAP_TILE_URL ?? ''
const ATRIBUCION: string = import.meta.env.VITE_MAP_ATTRIBUTION ?? ''

/** Chincheta propia: los iconos por defecto de Leaflet se sirven por URL. */
function chincheta(resaltada: boolean): L.DivIcon {
  return L.divIcon({
    className: 'chincheta',
    html: `<span class="punto ${resaltada ? 'resaltado' : ''}"></span>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  })
}

function escapar(texto: string): string {
  return texto.replace(
    /[&<>"']/g,
    (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string,
  )
}

export function MapaDeActivos({
  projectId,
  assetId,
}: {
  projectId: string
  /** Con él, el mapa es de un solo activo y se acerca a él. */
  assetId?: string
}) {
  const mapaRef = useRef<L.Map | null>(null)
  const capaRef = useRef<L.LayerGroup | null>(null)
  const [activos, setActivos] = useState<Activo[] | null>(null)
  const [listo, setListo] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    obtener<Activo[]>(`/projects/${projectId}/assets`)
      .then((todos) => setActivos(assetId ? todos.filter((a) => a.id === assetId) : todos))
      .catch((e: Error) => setError(e.message))
  }, [projectId, assetId])

  /**
   * El mapa se crea **cuando el nodo aparece**, con una referencia por
   * callback y no en un efecto de dependencias vacías: mientras los datos
   * cargan el `div` todavía no existe, así que en el montaje la referencia
   * valdría `null` y el efecto no volvería a ejecutarse nunca. Es el mismo
   * defecto que cazó `comprobar-mapa.mjs` en el mapa de fotografías.
   */
  const montarMapa = useCallback((nodo: HTMLDivElement | null) => {
    if (nodo === null) {
      mapaRef.current?.remove()
      mapaRef.current = null
      capaRef.current = null
      setListo(false)
      return
    }
    if (mapaRef.current) return
    const mapa = L.map(nodo, { attributionControl: Boolean(ATRIBUCION) })
    if (TESELAS) L.tileLayer(TESELAS, { attribution: ATRIBUCION, maxZoom: 19 }).addTo(mapa)
    // Escala siempre: sin cartografía de fondo es lo único que da idea de la
    // distancia entre dos chinchetas, y con ella tampoco sobra.
    L.control.scale({ imperial: false }).addTo(mapa)
    mapa.setView([40.4168, -3.7038], 5)
    capaRef.current = L.layerGroup().addTo(mapa)
    mapaRef.current = mapa
    setListo(true)
  }, [])

  const situados = (activos ?? []).filter((a) => a.latitude && a.longitude)

  useEffect(() => {
    const mapa = mapaRef.current
    const capa = capaRef.current
    if (!mapa || !capa || !listo) return
    capa.clearLayers()
    if (situados.length === 0) return

    for (const a of situados) {
      const punto: [number, number] = [Number(a.latitude), Number(a.longitude)]
      L.marker(punto, { icon: chincheta(Boolean(assetId)), title: a.name })
        .bindPopup(
          `<strong>${escapar(a.name)}</strong><br>` +
            (a.asset_code ? `${escapar(a.asset_code)}<br>` : '') +
            escapar([a.address_line, a.city].filter(Boolean).join(', ') || 'Sin dirección'),
        )
        .addTo(capa)
    }
    const encuadre = L.latLngBounds(
      situados.map((a) => [Number(a.latitude), Number(a.longitude)] as [number, number]),
    )
    // Con un solo activo, `fitBounds` sobre un punto se va al zoom máximo y se
    // ve una calle sin contexto. Se fija un acercamiento razonable de barrio.
    if (situados.length === 1) mapa.setView(encuadre.getCenter(), 16)
    else mapa.fitBounds(encuadre, { padding: [40, 40], maxZoom: 15 })
  }, [situados, listo, assetId])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!activos) return <p className="cargando">Cargando los activos…</p>

  const sinSituar = activos.length - situados.length

  return (
    <div className="mapa-activos">
      <p className="ayuda">
        <strong>{situados.length}</strong> {situados.length === 1 ? 'situado' : 'situados'}
        {sinSituar > 0 && ` · ${sinSituar} sin coordenadas`}
      </p>

      {!TESELAS && (
        <Mensaje tipo="aviso">
          Sin cartografía de fondo: no hay proveedor de teselas configurado, así que la
          aplicación no contacta con ningún servidor externo. Las posiciones y las distancias
          son correctas —use la escala—. Para ver el mapa, defina <code>VITE_MAP_TILE_URL</code>{' '}
          con un proveedor cuyas condiciones de uso permitan este caso.
        </Mensaje>
      )}

      {activos.length === 0 ? (
        <Vacio>Este proyecto todavía no tiene activos.</Vacio>
      ) : situados.length === 0 ? (
        <Vacio>
          {activos.length === 1
            ? 'Este activo no tiene coordenadas. Se ponen en su ficha, a mano o proponiéndolas desde la dirección.'
            : 'Ningún activo tiene coordenadas todavía. Se ponen en la ficha de cada uno.'}
        </Vacio>
      ) : (
        <div className="mapa" ref={montarMapa} />
      )}
    </div>
  )
}

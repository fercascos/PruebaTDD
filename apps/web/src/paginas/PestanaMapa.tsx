import { useCallback, useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { obtener } from '../api/cliente'
import type { Activo } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

type Punto = {
  id: string
  latitude: number
  longitude: number
  display_name: string
  caption: string | null
  taken_at: string | null
  asset_id: string | null
  asset_name: string | null
  zone_name: string | null
}

type Mapa = {
  puntos: Punto[]
  sin_coordenadas: number
  encuadre: { sur: number; norte: number; oeste: number; este: number } | null
}

/**
 * El proveedor de teselas, **por configuración y sin valor por defecto**.
 *
 * La biblioteca (Leaflet, BSD-2) es libre sin condiciones; las teselas no. El
 * servidor al que todo el mundo apunta por costumbre, `tile.openstreetmap.org`,
 * tiene una *Tile Usage Policy* que lo limita a uso ligero y no comercial y
 * pide expresamente que el uso intensivo se autoaloje o vaya a un proveedor de
 * pago. Una consultora usándolo a diario estaría fuera de esas condiciones.
 *
 * Así que aquí no hay ninguna URL escrita: sin `VITE_MAP_TILE_URL` la
 * aplicación **no contacta con nadie** y el mapa funciona igual, solo que sin
 * cartografía de fondo. Poner un proveedor es una decisión explícita de quien
 * despliega, que es quien puede aceptar sus términos. Ver `.env.example`.
 */
const TESELAS: string = import.meta.env.VITE_MAP_TILE_URL ?? ''
const ATRIBUCION: string = import.meta.env.VITE_MAP_ATTRIBUTION ?? ''

/** Chincheta propia: los iconos por defecto de Leaflet se sirven por URL. */
function chincheta(resaltada: boolean): L.DivIcon {
  return L.divIcon({
    className: 'chincheta',
    html: `<span class="punto ${resaltada ? 'resaltado' : ''}"></span>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  })
}

/**
 * Mapa de fotografías `[REQ]` §15.9.
 *
 * Sirve para lo que un listado no puede: ver de un vistazo si la visita cubrió
 * todo el activo o se quedó en la fachada, y detectar la foto que se coló de
 * otro edificio.
 *
 * `[LIM]` **El mapa nunca es la visita completa.** Muchas fotografías llegan
 * sin coordenadas —en un sótano no hay señal, y muchos móviles van con la
 * localización apagada—, así que el recuento de las que faltan está siempre a
 * la vista. La fecha y las coordenadas no se infieren jamás: si no vinieron en
 * el EXIF, no están.
 */
export function PestanaMapa({ projectId }: { projectId: string }) {
  const mapaRef = useRef<L.Map | null>(null)
  const capaRef = useRef<L.LayerGroup | null>(null)
  const [datos, setDatos] = useState<Mapa | null>(null)
  const [activos, setActivos] = useState<Activo[]>([])
  const [filtro, setFiltro] = useState('')
  const [elegida, setElegida] = useState<string | null>(null)
  //: Fuerza el repintado de las chinchetas en cuanto el mapa existe: si no, la
  //: primera tanda de datos podía llegar antes que el mapa y no pintarse.
  const [listo, setListo] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(() => {
    const consulta = filtro ? `?asset_id=${filtro}` : ''
    obtener<Mapa>(`/projects/${projectId}/photos/map${consulta}`)
      .then(setDatos)
      .catch((e: Error) => setError(e.message))
  }, [projectId, filtro])

  useEffect(recargar, [recargar])

  useEffect(() => {
    obtener<Activo[]>(`/projects/${projectId}/assets`)
      .then(setActivos)
      .catch(() => setActivos([]))
  }, [projectId])

  /**
   * Se crea el mapa **cuando el nodo aparece**, con una referencia por
   * callback, y no en un efecto con dependencias vacías.
   *
   * Con el efecto no funcionaba: mientras los datos están cargando el
   * componente devuelve «Cargando el mapa…» y el `div` todavía no existe, así
   * que en el montaje la referencia valía `null`, el efecto se rendía y —al
   * depender de `[]`— no se volvía a ejecutar nunca. El mapa no aparecía
   * jamás. La referencia por callback se dispara justo cuando React engancha
   * el nodo, sin importar en qué render ocurra.
   *
   * Lo cazó `comprobar-mapa.mjs` abriendo la pestaña en un navegador. Leyendo
   * el código no se ve.
   */
  const montarMapa = useCallback((nodo: HTMLDivElement | null) => {
    if (nodo === null) {
      mapaRef.current?.remove()
      mapaRef.current = null
      capaRef.current = null
      return
    }
    if (mapaRef.current) return
    const mapa = L.map(nodo, { attributionControl: Boolean(ATRIBUCION) })
    if (TESELAS) {
      L.tileLayer(TESELAS, { attribution: ATRIBUCION, maxZoom: 19 }).addTo(mapa)
    }
    // Escala siempre: sin cartografía de fondo es lo único que da idea de la
    // distancia entre dos chinchetas, y con ella tampoco sobra.
    L.control.scale({ imperial: false }).addTo(mapa)
    mapa.setView([40.4168, -3.7038], 5)
    capaRef.current = L.layerGroup().addTo(mapa)
    mapaRef.current = mapa
    setListo(true)
  }, [])

  // Pintar las chinchetas cuando cambian los datos o la selección.
  useEffect(() => {
    const mapa = mapaRef.current
    const capa = capaRef.current
    if (!mapa || !capa || !datos) return
    capa.clearLayers()

    for (const punto of datos.puntos) {
      const marca = L.marker([punto.latitude, punto.longitude], {
        icon: chincheta(punto.id === elegida),
        title: punto.display_name,
      })
      marca.bindPopup(
        `<strong>${escapar(punto.display_name)}</strong><br>` +
          (punto.asset_name ? `${escapar(punto.asset_name)}<br>` : '') +
          (punto.zone_name ? `<em>${escapar(punto.zone_name)}</em><br>` : '') +
          (punto.caption ? `${escapar(punto.caption)}<br>` : '') +
          (punto.taken_at
            ? new Date(punto.taken_at).toLocaleString('es-ES')
            : '<em>sin fecha EXIF</em>'),
      )
      marca.on('click', () => setElegida(punto.id))
      marca.addTo(capa)
    }

    if (datos.encuadre) {
      const { sur, norte, oeste, este } = datos.encuadre
      // `pad` para que las chinchetas del borde no queden pegadas al marco.
      mapa.fitBounds(
        L.latLngBounds([sur, oeste], [norte, este]).pad(0.15),
        { maxZoom: 18 },
      )
    }
  }, [datos, elegida, listo])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!datos) return <p className="cargando">Cargando el mapa…</p>

  return (
    <>
      <div className="filtro">
        <label>
          Activo
          <select value={filtro} onChange={(e) => setFiltro(e.target.value)}>
            <option value="">Todos</option>
            {activos.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <span className="ayuda">
          {datos.puntos.length} situadas
          {datos.sin_coordenadas > 0 && ` · ${datos.sin_coordenadas} sin coordenadas`}
        </span>
      </div>

      {/* `[REQ]` §15.6 · El mapa nunca es la visita completa, y decirlo evita
          que cuatro chinchetas se lean como «se hicieron cuatro fotos». */}
      {datos.sin_coordenadas > 0 && (
        <Mensaje tipo="aviso">
          {datos.sin_coordenadas} fotografías no llevan coordenadas y no salen aquí. En un sótano no
          hay señal, y muchos móviles van con la localización apagada. No se infiere ninguna
          posición: si no vino en el EXIF, no está.
        </Mensaje>
      )}

      {!TESELAS && (
        <Mensaje tipo="aviso">
          Sin cartografía de fondo: no hay proveedor de teselas configurado, así que la aplicación no
          contacta con ningún servidor externo. Las posiciones y las distancias son correctas —use la
          escala—. Para ver el mapa, defina <code>VITE_MAP_TILE_URL</code> con un proveedor cuyas
          condiciones de uso permitan este caso. Ver <code>.env.example</code>.
        </Mensaje>
      )}

      {datos.puntos.length === 0 && (
        <Vacio>
          Ninguna fotografía de esta selección trae coordenadas. Se registran solas si el móvil
          tiene la localización activada al hacer la foto.
        </Vacio>
      )}

      {/* El contenedor está SIEMPRE montado, aunque no haya puntos. Ocultarlo
          dejaba el mapa creado sobre un nodo que ya no existe: al volver a un
          filtro con fotos, el efecto de creación no se repite —depende de `[]`—
          y el mapa no aparecía nunca más. */}
      <div className={`mapa ${datos.puntos.length === 0 ? 'vacio' : ''}`} ref={montarMapa} />
    </>
  )
}

/** El contenido del globo se inserta como HTML: hay que escaparlo. */
function escapar(texto: string): string {
  const escape: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }
  return texto.replace(/[&<>"']/g, (c) => escape[c] ?? c)
}

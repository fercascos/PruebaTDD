import { useEffect, useState } from 'react'
import { enviar, obtener } from '../api/cliente'
import type { Activo, ElementoCatalogo, Foto, NodoDeUbicacion } from '../api/tipos'
import { Campo, Rejilla } from '../ui/Formulario'
import { Mensaje } from '../ui/Marco'
import { Anotador } from './Anotador'
import { Imagen } from './Imagen'

/**
 * Ficha de una fotografía: clasificarla y decidir si sale en el informe.
 *
 * Lo que esta pantalla enseña y una rejilla de miniaturas no puede: **de dónde
 * viene el dato**. La fecha y las coordenadas salen del EXIF y no se pueden
 * teclear; si la foto no las trae, se dice que están vacías en vez de dejar un
 * hueco que parezca un descuido. `[REQ]` §15.6 · No se infiere ninguna de las
 * dos.
 */
export function DetalleDeFoto({
  foto,
  projectId,
  alGuardar,
  alCerrar,
  alCrearHallazgo,
}: {
  foto: Foto
  projectId: string
  alGuardar: () => void
  alCerrar: () => void
  alCrearHallazgo: (foto: Foto) => void
}) {
  const [activos, setActivos] = useState<Activo[]>([])
  const [zonas, setZonas] = useState<ElementoCatalogo[]>([])
  const [espacios, setEspacios] = useState<NodoDeUbicacion[]>([])
  const [activo, setActivo] = useState(foto.asset_id ?? '')
  const [zona, setZona] = useState(foto.zone_id ?? '')
  const [espacio, setEspacio] = useState(foto.location_node_id ?? '')
  const [nombre, setNombre] = useState(foto.display_name)
  const [pie, setPie] = useState(foto.caption ?? '')
  const [etiquetas, setEtiquetas] = useState(foto.tags.join(', '))
  const [enInforme, setEnInforme] = useState(foto.include_in_report)
  const [orden, setOrden] = useState(foto.report_order?.toString() ?? '')
  const [error, setError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [anotando, setAnotando] = useState(false)

  useEffect(() => {
    obtener<Activo[]>(`/projects/${projectId}/assets`)
      .then(setActivos)
      .catch(() => setActivos([]))
  }, [projectId])

  useEffect(() => {
    if (!activo) {
      setZonas([])
      return
    }
    obtener<ElementoCatalogo[]>(`/assets/${activo}/allowed-zones`)
      .then(setZonas)
      .catch(() => setZonas([]))
    // El árbol es de ESTE activo: cambiar de activo cambia los espacios, y
    // dejar el anterior seleccionado guardaría una foto en una sala de otro
    // edificio.
    obtener<NodoDeUbicacion[]>(`/assets/${activo}/locations`)
      .then(setEspacios)
      .catch(() => setEspacios([]))
  }, [activo])

  async function guardar() {
    setError(null)
    setGuardando(true)
    try {
      await enviar(
        `/photos/${foto.id}`,
        {
          asset_id: activo || null,
          zone_id: zona || null,
          location_node_id: espacio || null,
          // El nombre visible va sin extensión: la fija el servidor desde el
          // tipo real del archivo, y mandarla aquí produciría un 422.
          display_name: nombre.trim(),
          caption: pie.trim() || null,
          tags: etiquetas
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean),
          include_in_report: enInforme,
          report_order: orden ? Number(orden) : null,
        },
        'PATCH',
      )
      alGuardar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se ha podido guardar')
    } finally {
      setGuardando(false)
    }
  }

  if (anotando) {
    return (
      <Anotador
        photoId={foto.id}
        alGuardar={() => {
          setAnotando(false)
          alGuardar()
        }}
        alCerrar={() => setAnotando(false)}
      />
    )
  }

  return (
    <div className="dialogo detalle-foto">
      <div className="vista">
        {/* La vista de 1600 px, no el original: para mirarla en pantalla no
            hace falta traerse los 4 MB de la cámara. */}
        <Imagen
          ruta={`/photos/${foto.id}/download?variante=VISTA_1600`}
          alt={foto.caption ?? foto.display_name}
        />
      </div>

      <div className="datos">
        <h3>{foto.display_name}.{foto.file_extension}</h3>

        {/* Procedencia: no editable, porque no se inventa. */}
        <dl className="procedencia">
          <dt>Llegó como</dt>
          <dd>{foto.original_filename}</dd>
          <dt>Origen</dt>
          <dd>{foto.origin}</dd>
          <dt>Fecha de captura</dt>
          <dd>
            {foto.taken_at ? (
              new Date(foto.taken_at).toLocaleString('es-ES')
            ) : (
              <em>sin EXIF · no se infiere</em>
            )}
          </dd>
          <dt>Coordenadas</dt>
          <dd>
            {foto.gps_latitude !== null ? (
              `${foto.gps_latitude.toFixed(6)}, ${foto.gps_longitude?.toFixed(6)}`
            ) : (
              <em>sin GPS</em>
            )}
          </dd>
          <dt>Dimensiones</dt>
          <dd>
            {foto.width_px} × {foto.height_px} px · {Math.round(foto.byte_size / 1024)} KB
          </dd>
          <dt>Huella</dt>
          <dd>
            <code title={foto.sha256}>{foto.sha256.slice(0, 16)}…</code>
          </dd>
        </dl>

        <Rejilla>
          <Campo etiqueta="Activo">
            <select value={activo} onChange={(e) => setActivo(e.target.value)}>
              <option value="">— sin asignar —</option>
              {activos.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Zona" ayuda="Clasificación del catálogo: es lo que agrega el informe">
            <select value={zona} onChange={(e) => setZona(e.target.value)} disabled={!activo}>
              <option value="">— sin zona —</option>
              {zonas.map((z) => (
                <option key={z.id} value={z.id}>
                  {z.name_es}
                </option>
              ))}
            </select>
          </Campo>
          <Campo
            etiqueta="Espacio"
            ayuda={
              espacios.length === 0
                ? 'Este activo no tiene árbol de ubicaciones todavía'
                : 'Dónde está exactamente. Alimenta el token [Espacio] al renombrar'
            }
          >
            {/* La sangría se calcula con `profundidad`, que ya viene de la API:
                la lista llega en orden de recorrido, así que basta con
                anteponer espacios. `&nbsp;` porque el navegador colapsa los
                espacios normales dentro de un `<option>`. */}
            <select
              value={espacio}
              onChange={(e) => setEspacio(e.target.value)}
              disabled={!activo || espacios.length === 0}
            >
              <option value="">— sin espacio —</option>
              {espacios.map((n) => (
                <option key={n.id} value={n.id}>
                  {'\u00a0\u00a0'.repeat(n.profundidad)}
                  {n.name}
                </option>
              ))}
            </select>
          </Campo>
        </Rejilla>

        <Campo etiqueta="Nombre visible" ayuda="Sin extensión: la fija el servidor">
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={200} />
        </Campo>
        <Campo etiqueta="Pie de foto" ayuda="Es el texto que se inserta bajo la imagen en el PPTX">
          <input value={pie} onChange={(e) => setPie(e.target.value)} />
        </Campo>
        <Campo etiqueta="Etiquetas" ayuda="Separadas por comas">
          <input value={etiquetas} onChange={(e) => setEtiquetas(e.target.value)} />
        </Campo>

        <Rejilla>
          <label className="casilla">
            <input
              type="checkbox"
              checked={enInforme}
              onChange={(e) => setEnInforme(e.target.checked)}
            />
            Incluir en el informe
          </label>
          <Campo etiqueta="Orden de aparición">
            <input
              type="number"
              min={1}
              value={orden}
              onChange={(e) => setOrden(e.target.value)}
              disabled={!enInforme}
            />
          </Campo>
        </Rejilla>

        {enInforme && !activo && (
          <Mensaje tipo="aviso">
            Seleccionada para el informe pero sin activo: no se sabría en qué diapositiva colocarla.
          </Mensaje>
        )}
        {enInforme && !pie.trim() && (
          <Mensaje tipo="aviso">Sin pie de foto: saldrá en el informe sin texto debajo.</Mensaje>
        )}
        {error && <Mensaje tipo="error">{error}</Mensaje>}

        <div className="acciones">
          <button type="button" onClick={() => void guardar()} disabled={guardando}>
            {guardando ? 'Guardando…' : 'Guardar'}
          </button>
          <button type="button" className="secundario" onClick={() => setAnotando(true)}>
            Anotar
          </button>
          <button
            type="button"
            className="secundario"
            onClick={() => alCrearHallazgo(foto)}
            disabled={!activo}
            title={activo ? '' : 'Asigne primero un activo'}
          >
            Crear hallazgo desde esta foto
          </button>
          <button type="button" className="secundario" onClick={alCerrar}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  )
}

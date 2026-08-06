import { useEffect, useState } from 'react'
import { enviar, obtener } from '../api/cliente'
import type { Activo, ElementoCatalogo } from '../api/tipos'
import { Campo, Formulario, Rejilla } from '../ui/Formulario'
import { Mensaje } from '../ui/Marco'

type CodigoCapex = ElementoCatalogo & { level: number; parent_id: string | null }
type GradoDeRiesgo = ElementoCatalogo & { score: number; definition_es: string }

/** `[REQ]` P-05 · Los cinco destinos posibles del importe. Mutuamente excluyentes. */
const PLAZOS = [
  { code: 'CORTO', nombre: 'Corto plazo (1-2 años)' },
  { code: 'MEDIO', nombre: 'Medio plazo' },
  { code: 'LARGO', nombre: 'Largo plazo' },
  { code: 'MEJORAS', nombre: 'Mejora potencial' },
  { code: 'OTRO', nombre: 'Otro tipo de petición' },
] as const

type LineaEnEdicion = { plazo: string; importe: string }

/**
 * Alta de un hallazgo **con su línea de CAPEX en la misma pantalla**.
 *
 * `[REC]` No es un atajo: en la tabla real del cliente son la misma fila.
 * Partirlo en dos pantallas multiplicaría por dos los pasos de la operación que
 * más se repite en todo el proyecto —sesenta o setenta veces por encargo— y
 * dejaría hallazgos huérfanos cada vez que alguien se distrajera a mitad.
 *
 * `[REQ]` P-44 · Se pueden añadir varias líneas, **una por plazo**. Es la
 * actuación recurrente: la limpieza de lucernarios hace falta ahora y otra vez
 * dentro de diez años.
 */
export function NuevoHallazgo({
  projectId,
  photoId,
  activoInicial,
  zonaInicial,
  alGuardar,
  alCancelar,
}: {
  projectId: string
  /** Si viene de una foto, el hallazgo hereda su activo y su zona. */
  photoId?: string
  activoInicial?: string
  zonaInicial?: string
  alGuardar: () => void
  alCancelar: () => void
}) {
  const [activos, setActivos] = useState<Activo[]>([])
  const [zonas, setZonas] = useState<ElementoCatalogo[]>([])
  const [codigos, setCodigos] = useState<CodigoCapex[]>([])
  const [riesgos, setRiesgos] = useState<GradoDeRiesgo[]>([])

  const [activo, setActivo] = useState(activoInicial ?? '')
  const [zona, setZona] = useState(zonaInicial ?? '')
  const [codigo, setCodigo] = useState('')
  const [riesgo, setRiesgo] = useState('')
  const [titulo, setTitulo] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [comentarios, setComentarios] = useState('')
  const [recomendacion, setRecomendacion] = useState('')
  const [lineas, setLineas] = useState<LineaEnEdicion[]>([{ plazo: 'CORTO', importe: '' }])

  useEffect(() => {
    obtener<Activo[]>(`/projects/${projectId}/assets`)
      .then((lista) => {
        setActivos(lista)
        if (!activoInicial && lista[0]) setActivo(lista[0].id)
      })
      .catch(() => setActivos([]))
    obtener<CodigoCapex[]>('/catalogs/capex-codes?level=3')
      .then(setCodigos)
      .catch(() => setCodigos([]))
    obtener<GradoDeRiesgo[]>('/catalogs/risk-levels')
      .then(setRiesgos)
      .catch(() => setRiesgos([]))
  }, [projectId, activoInicial])

  // Las zonas dependen de la tipología del activo. Se recargan al cambiarlo
  // para no ofrecer una que el servidor va a rechazar.
  useEffect(() => {
    if (!activo) return
    obtener<ElementoCatalogo[]>(`/assets/${activo}/allowed-zones`)
      .then((lista) => {
        setZonas(lista)
        setZona((actual) =>
          lista.some((z) => z.id === actual) ? actual : (lista[0]?.id ?? ''),
        )
      })
      .catch(() => setZonas([]))
  }, [activo])

  const plazosUsados = new Set(lineas.map((l) => l.plazo))
  const definicion = riesgos.find((r) => r.id === riesgo)?.definition_es

  async function guardar() {
    const capex = lineas
      .filter((l) => l.importe.trim() !== '')
      .map((l) => ({ time_horizon_code: l.plazo, amount: l.importe.trim() }))

    const cuerpo = {
      capex_code_id: codigo,
      title: titulo.trim(),
      description: descripcion.trim(),
      risk_level_id: riesgo || null,
    }

    if (photoId) {
      // El atajo de campo: hereda activo y zona de la foto y la enlaza como
      // evidencia. La línea de CAPEX se añade después, porque el endorso de
      // «desde foto» crea el hallazgo mínimo.
      const hallazgo = await enviar<{ id: string }>('/findings/from-photo', {
        photo_id: photoId,
        capex_code_id: codigo,
        title: titulo.trim(),
        description: descripcion.trim(),
        risk_level_id: riesgo || null,
        zone_id: zona || null,
      })
      for (const linea of capex) {
        await enviar(`/findings/${hallazgo.id}/capex-items`, linea)
      }
    } else {
      await enviar(`/projects/${projectId}/findings`, {
        ...cuerpo,
        asset_id: activo,
        zone_id: zona,
        comments: comentarios.trim() || null,
        recommendation: recomendacion.trim() || null,
        capex_lines: capex,
      })
    }
    alGuardar()
  }

  return (
    <Formulario
      titulo={photoId ? 'Nuevo hallazgo desde la fotografía' : 'Nuevo hallazgo'}
      enviar={guardar}
      textoDeEnvio="Crear hallazgo"
      alCancelar={alCancelar}
    >
      {photoId && (
        <Mensaje tipo="ok">
          Hereda el activo y la zona de la fotografía, y la deja enlazada como evidencia.
        </Mensaje>
      )}

      <Rejilla>
        <Campo etiqueta="Activo">
          <select
            required
            value={activo}
            onChange={(e) => setActivo(e.target.value)}
            disabled={Boolean(photoId)}
          >
            {activos.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </Campo>
        <Campo etiqueta="Zona" ayuda="Solo las que admite la tipología del activo">
          <select required value={zona} onChange={(e) => setZona(e.target.value)}>
            {zonas.map((z) => (
              <option key={z.id} value={z.id}>
                {z.name_es}
              </option>
            ))}
          </select>
        </Campo>
        <Campo etiqueta="Código CAPEX">
          <select required value={codigo} onChange={(e) => setCodigo(e.target.value)}>
            <option value="">— elija un elemento —</option>
            {codigos.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} · {c.name_es}
              </option>
            ))}
          </select>
        </Campo>
        <Campo etiqueta="Grado de riesgo">
          <select value={riesgo} onChange={(e) => setRiesgo(e.target.value)}>
            <option value="">— sin clasificar —</option>
            {riesgos.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name_es}
              </option>
            ))}
          </select>
        </Campo>
      </Rejilla>

      {/* La definición íntegra del grado, para que «Alto» no sea una palabra
          sin criterio detrás. Viene del catálogo, no del frontend. */}
      {definicion && <p className="ayuda definicion">{definicion}</p>}

      <Campo etiqueta="Título de la actuación">
        <input
          required
          maxLength={240}
          value={titulo}
          onChange={(e) => setTitulo(e.target.value)}
          placeholder="Renovación de impermeabilización"
        />
      </Campo>
      <Campo etiqueta="Descripción" ayuda="Es lo que lee el revisor y lo que sale en el informe">
        <textarea rows={3} value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
      </Campo>

      {!photoId && (
        <>
          <Campo etiqueta="Comentarios">
            <textarea
              rows={2}
              value={comentarios}
              onChange={(e) => setComentarios(e.target.value)}
            />
          </Campo>
          <Campo etiqueta="Actuación recomendada">
            <textarea
              rows={2}
              value={recomendacion}
              onChange={(e) => setRecomendacion(e.target.value)}
            />
          </Campo>
        </>
      )}

      <h3>Importe</h3>
      <p className="ayuda">
        Una línea por plazo. El importe que teclee <strong>lo incluye todo</strong>: indirectos,
        honorarios y contingencia ya dentro. La aplicación nunca aplica la cascada por encima.
        Añada otra línea solo si la actuación es <em>recurrente</em> —hace falta ahora y otra vez
        más adelante—, que es lo que P-44 permite.
      </p>

      {lineas.map((linea, indice) => (
        <Rejilla key={indice}>
          <Campo etiqueta="Plazo">
            <select
              value={linea.plazo}
              onChange={(e) =>
                setLineas((previas) =>
                  previas.map((l, i) => (i === indice ? { ...l, plazo: e.target.value } : l)),
                )
              }
            >
              {PLAZOS.map((p) => (
                <option
                  key={p.code}
                  value={p.code}
                  // Dos líneas en el mismo plazo sí son un duplicado, y el
                  // servidor lo rechaza con un 409. Mejor no ofrecerlo.
                  disabled={p.code !== linea.plazo && plazosUsados.has(p.code)}
                >
                  {p.nombre}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Importe (€)">
            <input
              type="number"
              step="0.01"
              min={0}
              value={linea.importe}
              onChange={(e) =>
                setLineas((previas) =>
                  previas.map((l, i) => (i === indice ? { ...l, importe: e.target.value } : l)),
                )
              }
            />
          </Campo>
          {lineas.length > 1 && (
            <button
              type="button"
              className="secundario"
              onClick={() => setLineas((previas) => previas.filter((_, i) => i !== indice))}
            >
              Quitar
            </button>
          )}
        </Rejilla>
      ))}

      {lineas.length < PLAZOS.length && (
        <button
          type="button"
          className="secundario"
          onClick={() =>
            setLineas((previas) => [
              ...previas,
              {
                plazo: PLAZOS.find((p) => !plazosUsados.has(p.code))?.code ?? 'MEDIO',
                importe: '',
              },
            ])
          }
        >
          Añadir otro plazo (actuación recurrente)
        </button>
      )}
    </Formulario>
  )
}

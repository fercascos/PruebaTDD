import { useCallback, useEffect, useState } from 'react'
import { enviar, obtener } from '../api/cliente'
import type { AsistenteDeVisita, Activo, Foto, Persona, Visita } from '../api/tipos'
import { Campo, Rejilla } from '../ui/Formulario'
import { Mensaje, Vacio } from '../ui/Marco'

/**
 * La visita **de un activo** `[REQ]` §3.2 c de `docs/23`.
 *
 * Los tres bloques de la hoja del cliente: datos de la visita, equipo implicado
 * y fotos.
 *
 * ## Casi nada de esto es nuevo
 *
 * `asset_visit` ya tenía estado, fecha prevista, fecha real, quién la dirigió,
 * limitaciones de acceso y resumen, y ya admitía **varias visitas por activo**.
 * Esta pantalla no inventa un modelo: lo enseña dentro del activo, que es donde
 * el cliente lo quiere, y añade lo que faltaba —punto de encuentro, coste y la
 * lista de asistentes—.
 *
 * ## «Check visita» es el estado, no una casilla aparte
 *
 * La hoja pide *«marcar si la visita ha sido realizada»*. Eso ya existe: es el
 * estado `VISITADO`, y la base **exige fecha real** para aceptarlo. Una casilla
 * booleana al lado del estado habría creado dos verdades sobre lo mismo, y la
 * pregunta «¿cuál manda?» no tiene buena respuesta.
 *
 * ## El equipo implicado son dos listas en una
 *
 * Los cuatro «Responsable» de la hoja son cuatro porque es lo que cabía en una
 * hoja de cálculo. Aquí la lista no tiene tope, y mezcla **personas de la
 * aplicación** —con las que se puede preguntar «qué visitó cada uno»— y
 * **acompañantes** de la propiedad o del mantenedor, que no tienen cuenta y
 * nunca la van a tener. Perderlos sería perder a quien abrió el cuarto de
 * máquinas.
 *
 * ## El coste no sale del encargo
 *
 * `[REQ]` Lo decidió el cliente: es **coste interno**. No entra en el CAPEX ni
 * en el informe, y la pantalla lo dice para que nadie lo teclee esperando otra
 * cosa. Que no salga lo fija una prueba sobre el snapshot, no este comentario.
 */

const ESTADOS = [
  { code: 'PENDIENTE_DEFINIR', nombre: 'Pendiente de definir' },
  { code: 'AGENDADO', nombre: 'Agendada' },
  { code: 'VISITADO', nombre: 'Realizada' },
] as const

/** Los campos de una visita mientras se teclean. */
type Borrador = {
  scheduled_date: string
  actual_date: string
  meeting_point: string
  access_limitations: string
  summary: string
  cost_amount: string
}

function desde(v: Visita): Borrador {
  return {
    scheduled_date: v.scheduled_date ?? '',
    actual_date: v.actual_date ?? '',
    meeting_point: v.meeting_point ?? '',
    access_limitations: v.access_limitations ?? '',
    summary: v.summary ?? '',
    cost_amount: v.cost_amount ?? '',
  }
}

export function VisitaDelActivo({ activo }: { activo: Activo }) {
  const [visitas, setVisitas] = useState<Visita[] | null>(null)
  const [personas, setPersonas] = useState<Persona[]>([])
  const [fotos, setFotos] = useState<Foto[]>([])
  const [error, setError] = useState<string | null>(null)
  const [hecho, setHecho] = useState<string | null>(null)
  const [trabajando, setTrabajando] = useState(false)

  const recargar = useCallback(() => {
    obtener<Visita[]>(`/assets/${activo.id}/visits`)
      .then(setVisitas)
      .catch((e: Error) => setError(e.message))
  }, [activo.id])

  useEffect(recargar, [recargar])

  useEffect(() => {
    obtener<Persona[]>('/users')
      .then((lista) => setPersonas(lista.filter((p) => p.is_active)))
      .catch(() => setPersonas([]))
    obtener<Foto[]>(`/projects/${activo.project_id}/photos?asset_id=${activo.id}`)
      .then(setFotos)
      .catch(() => setFotos([]))
  }, [activo.id, activo.project_id])

  async function conAviso(hacer: () => Promise<void>) {
    setError(null)
    setHecho(null)
    setTrabajando(true)
    try {
      await hacer()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se ha podido completar')
    } finally {
      setTrabajando(false)
    }
  }

  function programar() {
    return conAviso(async () => {
      await enviar<Visita>(`/projects/${activo.project_id}/visits`, {
        asset_id: activo.id,
        // La dirección del activo se propone como punto de partida: es lo que
        // se sabe, y quien programa la corrige con por dónde se entra de
        // verdad. Pedirla en blanco significa que casi siempre queda vacía.
        meeting_point: [activo.address_line, activo.city].filter(Boolean).join(', ') || null,
      })
      setHecho('Visita creada. Ponga la fecha y quién va.')
      recargar()
    })
  }

  function guardar(visita: Visita, borrador: Borrador, estado: Visita['status']) {
    return conAviso(async () => {
      const cuerpo: Record<string, unknown> = {
        status: estado,
        scheduled_date: borrador.scheduled_date || null,
        meeting_point: borrador.meeting_point.trim() || null,
        access_limitations: borrador.access_limitations.trim() || null,
        summary: borrador.summary.trim() || null,
        cost_amount: borrador.cost_amount.trim() || null,
      }
      // La fecha real solo viaja si la hay: mandar `null` con estado VISITADO
      // pisaría la que el servidor pone solo al marcar la visita como hecha.
      if (borrador.actual_date) cuerpo.actual_date = borrador.actual_date
      const actualizada = await enviar<Visita>(`/visits/${visita.id}`, cuerpo, 'PATCH')
      setVisitas((previas) =>
        (previas ?? []).map((v) => (v.id === visita.id ? actualizada : v)),
      )
      setHecho('Visita guardada.')
    })
  }

  function guardarAsistentes(visita: Visita, lineas: AsistenteDeVisita[]) {
    return conAviso(async () => {
      const actualizada = await enviar<Visita>(
        `/visits/${visita.id}/attendees`,
        {
          asistentes: lineas.map((a) => ({
            app_user_id: a.es_del_equipo ? a.app_user_id : null,
            external_name: a.es_del_equipo ? null : a.nombre.trim(),
            role_note: a.role_note?.trim() || null,
          })),
        },
        'PUT',
      )
      setVisitas((previas) =>
        (previas ?? []).map((v) => (v.id === visita.id ? actualizada : v)),
      )
      setHecho('Equipo implicado guardado.')
    })
  }

  return (
    <section className="visita-activo">
      <h3>Visita al activo</h3>

      {error && <Mensaje tipo="error">{error}</Mensaje>}
      {hecho && <Mensaje tipo="ok">{hecho}</Mensaje>}

      <div className="filtro">
        <button type="button" disabled={trabajando} onClick={() => void programar()}>
          Programar una visita
        </button>
        {visitas && visitas.length > 1 && (
          <span className="recuento">
            <strong>{visitas.length}</strong> visitas a este activo
          </span>
        )}
      </div>

      {!visitas ? (
        <p className="cargando">Cargando las visitas…</p>
      ) : visitas.length === 0 ? (
        <Vacio>
          Este activo no tiene ninguna visita registrada. Se puede programar antes de tener
          fecha: la visita nace «pendiente de definir» y no obliga a inventarse un día.
        </Vacio>
      ) : (
        <ul className="visitas">
          {visitas.map((v, i) => (
            <FichaDeVisita
              key={v.id}
              visita={v}
              personas={personas}
              fotos={fotos}
              abierta={i === 0}
              trabajando={trabajando}
              alGuardar={guardar}
              alGuardarAsistentes={guardarAsistentes}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

function FichaDeVisita({
  visita,
  personas,
  fotos,
  abierta,
  trabajando,
  alGuardar,
  alGuardarAsistentes,
}: {
  visita: Visita
  personas: Persona[]
  fotos: Foto[]
  abierta: boolean
  trabajando: boolean
  alGuardar: (v: Visita, b: Borrador, e: Visita['status']) => Promise<void>
  alGuardarAsistentes: (v: Visita, lineas: AsistenteDeVisita[]) => Promise<void>
}) {
  const [borrador, setBorrador] = useState<Borrador>(() => desde(visita))
  const [estado, setEstado] = useState<Visita['status']>(visita.status)
  const [lineas, setLineas] = useState<AsistenteDeVisita[]>(visita.asistentes)

  // Cuando el servidor devuelve la visita guardada, la pantalla vuelve a lo que
  // hay en la base: es la única forma de ver la fecha real que pone el servidor
  // solo al marcar la visita como realizada.
  useEffect(() => {
    setBorrador(desde(visita))
    setEstado(visita.status)
    setLineas(visita.asistentes)
  }, [visita])

  function campo(clave: keyof Borrador) {
    return {
      value: borrador[clave],
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
        setBorrador((previo) => ({ ...previo, [clave]: e.target.value })),
    }
  }

  const cuando = visita.actual_date ?? visita.scheduled_date
  const libres = personas.filter(
    (p) => !lineas.some((a) => a.es_del_equipo && a.app_user_id === p.id),
  )
  const deLasFotos = fotos.filter(
    (f) => !visita.actual_date || f.taken_at?.slice(0, 10) === visita.actual_date,
  )

  return (
    <li className={`visita ${estado === 'VISITADO' ? 'realizada' : ''}`}>
      <details open={abierta}>
        <summary>
          <strong>{cuando ?? 'Sin fecha'}</strong>
          <span className="pastilla">
            {ESTADOS.find((e) => e.code === visita.status)?.nombre ?? visita.status}
          </span>
          <span className="cifra">
            {visita.asistentes.length}{' '}
            {visita.asistentes.length === 1 ? 'asistente' : 'asistentes'}
          </span>
        </summary>

        {/* ── V1 · Datos de la visita ────────────────────────────────────── */}
        <h4>Datos de la visita</h4>
        <Rejilla>
          <Campo etiqueta="Estado">
            <select
              value={estado}
              onChange={(e) => setEstado(e.target.value as Visita['status'])}
              aria-label="Estado de la visita"
            >
              {ESTADOS.map((e) => (
                <option key={e.code} value={e.code}>
                  {e.nombre}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Fecha prevista">
            <input type="date" {...campo('scheduled_date')} />
          </Campo>
          {/* Solo cuando ya se ha ido: pedir la fecha real de una visita que no
              se ha hecho invita a rellenarla con la prevista, y esa es la fecha
              que acaba fechando el informe. */}
          {estado === 'VISITADO' && (
            <Campo
              etiqueta="Fecha real"
              ayuda="La que fecha el informe. Si la deja en blanco, se pone la de hoy al guardar"
            >
              <input type="date" {...campo('actual_date')} />
            </Campo>
          )}
        </Rejilla>

        <Campo
          etiqueta="Ubicación y punto de encuentro"
          ayuda="Por dónde se entra y con quién se queda. La dirección del edificio está en su ficha"
        >
          <textarea rows={2} {...campo('meeting_point')} />
        </Campo>

        <Campo
          etiqueta="Limitaciones de acceso"
          ayuda="Lo que no se pudo ver. Sale en el informe: «no se accedió a la cubierta» cambia lo que se puede afirmar sobre ella"
        >
          <textarea rows={2} {...campo('access_limitations')} />
        </Campo>

        <Campo etiqueta="Resumen de la visita">
          <textarea rows={3} {...campo('summary')} />
        </Campo>

        <Campo
          etiqueta="Coste de la visita"
          ayuda="Coste interno del encargo: NO entra en el CAPEX del edificio ni sale en el informe del cliente"
        >
          <input type="number" step="0.01" min={0} {...campo('cost_amount')} />
        </Campo>

        <div className="filtro">
          <button
            type="button"
            disabled={trabajando}
            onClick={() => void alGuardar(visita, borrador, estado)}
          >
            Guardar la visita
          </button>
        </div>

        {/* ── V2 · Equipo implicado ──────────────────────────────────────── */}
        <h4>Equipo implicado</h4>
        <p className="ayuda">
          Quién fue. Del equipo se elige de la lista de personas; quien acompaña —el jefe de
          mantenimiento, el mantenedor de PCI— se escribe, porque no tiene cuenta en la
          aplicación.
        </p>

        {lineas.length === 0 ? (
          <Vacio>Todavía no hay nadie apuntado a esta visita.</Vacio>
        ) : (
          <ul className="asistentes">
            {lineas.map((a, i) => (
              <li key={a.id || `nuevo-${i}`} className={a.es_del_equipo ? 'equipo' : 'externo'}>
                <span className="quien">
                  {a.es_del_equipo ? (
                    a.nombre
                  ) : (
                    <input
                      value={a.nombre}
                      maxLength={200}
                      placeholder="Nombre y apellidos"
                      aria-label={`Nombre del acompañante ${i + 1}`}
                      onChange={(e) =>
                        setLineas((previas) =>
                          previas.map((x, j) =>
                            j === i ? { ...x, nombre: e.target.value } : x,
                          ),
                        )
                      }
                    />
                  )}
                </span>
                <input
                  className="calidad"
                  value={a.role_note ?? ''}
                  maxLength={200}
                  placeholder="En calidad de…"
                  aria-label={`En calidad de qué vino ${a.nombre || `el asistente ${i + 1}`}`}
                  onChange={(e) =>
                    setLineas((previas) =>
                      previas.map((x, j) =>
                        j === i ? { ...x, role_note: e.target.value } : x,
                      ),
                    )
                  }
                />
                <button
                  type="button"
                  className="enlace"
                  aria-label={`Quitar a ${a.nombre || `el asistente ${i + 1}`}`}
                  onClick={() => setLineas((previas) => previas.filter((_, j) => j !== i))}
                >
                  Quitar
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="filtro">
          <Campo etiqueta="Añadir del equipo">
            <select
              value=""
              disabled={libres.length === 0}
              aria-label="Añadir una persona del equipo"
              onChange={(e) => {
                const p = personas.find((x) => x.id === e.target.value)
                if (!p) return
                setLineas((previas) => [
                  ...previas,
                  {
                    id: '',
                    app_user_id: p.id,
                    nombre: p.full_name,
                    es_del_equipo: true,
                    role_note: null,
                  },
                ])
              }}
            >
              <option value="">— elija una persona —</option>
              {libres.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.full_name}
                </option>
              ))}
            </select>
          </Campo>
          <button
            type="button"
            className="secundario"
            onClick={() =>
              setLineas((previas) => [
                ...previas,
                {
                  id: '',
                  app_user_id: null,
                  nombre: '',
                  es_del_equipo: false,
                  role_note: null,
                },
              ])
            }
          >
            Añadir acompañante
          </button>
          <button
            type="button"
            disabled={trabajando || lineas.some((a) => !a.es_del_equipo && !a.nombre.trim())}
            onClick={() => void alGuardarAsistentes(visita, lineas)}
          >
            Guardar el equipo
          </button>
        </div>

        {/* ── V3 · Fotos ─────────────────────────────────────────────────── */}
        <h4>Fotografías</h4>
        <p className="ayuda">
          Las de este activo. Se suben desde «Fotografías», también desde el móvil durante la
          visita, y se atan a cada equipo desde el inventario.
        </p>
        {fotos.length === 0 ? (
          <Vacio>Este activo todavía no tiene fotografías.</Vacio>
        ) : (
          <p className="recuento">
            <strong>{fotos.length}</strong> {fotos.length === 1 ? 'fotografía' : 'fotografías'}{' '}
            del activo
            {visita.actual_date && (
              <>
                {' · '}
                <strong>{deLasFotos.length}</strong> con fecha de esta visita
              </>
            )}
          </p>
        )}
      </details>
    </li>
  )
}

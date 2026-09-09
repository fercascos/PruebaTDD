import { useCallback, useEffect, useMemo, useState } from 'react'
import { enviar, obtener } from '../api/cliente'
import type {
  Descriptivo,
  DescriptivosTraidos,
  Equipo,
  EsqueletoDeEquipos,
  Foto,
} from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

/**
 * El inventario **de un activo** `[REQ]` §3.2 d de `docs/23`.
 *
 * Tres cosas que el cliente pidió juntas, y que juntas tienen sentido: lo que
 * la documentación dice que hay, lo que se vio en la visita, y la foto que lo
 * demuestra.
 *
 * ## a) El descriptivo de cada objeto, pendiente de validar
 *
 * `[REQ]` Literal: *«deberá traer el descriptivo de cada objeto de Hard Cost que
 * encuentre en la documentación, que indique que está pendiente de validar por
 * el Gestor Técnico, que sea un cuadro editable y que tenga una casilla de check
 * para marcar como validado»*.
 *
 * La rejilla es exactamente eso. Se trae con un botón —no al abrir la pantalla:
 * escribir en la base al mirar una página es la clase de efecto que nadie
 * espera—, nace **pendiente**, se edita, y la casilla la firma. Lo que la
 * pantalla enseña como sí o no, la base lo guarda como quién y cuándo, que es lo
 * que hace que la validación valga algo seis meses después.
 *
 * **Traerlo otra vez no pisa trabajo hecho.** Ampliar la memoria y volver a
 * traer es lo normal; que eso borrara lo que alguien corrigió o firmó sería
 * indefendible. Lo respeta el servidor, y lo dice al terminar.
 *
 * ## b) La casilla «pasa a CAPEX»
 *
 * Marcarla **no crea nada**. Se recorre el inventario marcando lo que hay que
 * sustituir y las actuaciones se generan después, todas de una vez, con el botón
 * de abajo. Crear el hallazgo al pulsar habría llenado el CAPEX de filas vacías
 * cada vez que alguien se equivoca de casilla, y borrarlas después es peor que
 * no haberlas creado.
 *
 * `[LIM]` El capítulo sale del sistema técnico del equipo, y **no siempre
 * resuelve**: «Protección contra incendios» apunta a `H06 + H10`. Cuando no
 * resuelve a uno solo, el equipo no se genera y sale en los avisos con su
 * nombre. Elegir uno de los dos sería codificar mal una actuación, y eso no se
 * ve hasta que alguien suma el capítulo equivocado.
 *
 * ## c) Vincular las fotos de la visita a cada equipo
 *
 * Es lo que justifica, medio año después, por qué se propone sustituir **esa**
 * máquina y no otra. El vínculo es una clasificación: borrar el equipo no se
 * lleva la fotografía, que vale por sí sola como evidencia de la visita.
 */

/** Lo que la pantalla guarda de una fila mientras se teclea. */
type Borrador = { texto: string; validado: boolean }

export function InventarioDelActivo({
  projectId,
  assetId,
}: {
  projectId: string
  assetId: string
}) {
  const [descriptivos, setDescriptivos] = useState<Descriptivo[] | null>(null)
  const [equipos, setEquipos] = useState<Equipo[] | null>(null)
  const [fotos, setFotos] = useState<Foto[]>([])
  const [borradores, setBorradores] = useState<Record<string, Borrador>>({})
  const [error, setError] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string[] | null>(null)
  const [hecho, setHecho] = useState<string | null>(null)
  const [trabajando, setTrabajando] = useState(false)

  const recargar = useCallback(() => {
    obtener<Descriptivo[]>(`/assets/${assetId}/descriptivos`)
      .then((lista) => {
        setDescriptivos(lista)
        // Los borradores se rehacen desde lo guardado: dejar los de antes
        // enseñaría texto que el servidor no tiene, que es la peor forma de
        // creerse que algo está guardado.
        setBorradores(
          Object.fromEntries(
            lista.map((d) => [d.capex_code_id, { texto: d.texto, validado: d.validado }]),
          ),
        )
      })
      .catch((e: Error) => setError(e.message))
    obtener<Equipo[]>(`/projects/${projectId}/equipment?asset_id=${assetId}`)
      .then(setEquipos)
      .catch((e: Error) => setError(e.message))
    obtener<Foto[]>(`/projects/${projectId}/photos?asset_id=${assetId}`)
      .then(setFotos)
      .catch(() => setFotos([]))
  }, [projectId, assetId])

  useEffect(recargar, [recargar])

  /** Las filas cuyo texto o casilla difieren de lo guardado. */
  const sucias = useMemo(() => {
    if (!descriptivos) return []
    return descriptivos.filter((d) => {
      const b = borradores[d.capex_code_id]
      return b && (b.texto !== d.texto || b.validado !== d.validado)
    })
  }, [descriptivos, borradores])

  const pendientes = descriptivos?.filter((d) => !d.validado).length ?? 0

  async function conAviso(hacer: () => Promise<void>) {
    setError(null)
    setAviso(null)
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

  function traer() {
    return conAviso(async () => {
      const r = await enviar<DescriptivosTraidos>(
        `/assets/${assetId}/descriptivos/desde-documentacion`,
        {},
      )
      setHecho(
        `${r.creados} descriptivo(s) nuevo(s), ${r.completados} completado(s) y ` +
          `${r.respetados} respetado(s) porque ya tenían texto o estaban validados.`,
      )
      if (r.avisos.length) setAviso(r.avisos)
      recargar()
    })
  }

  function guardar() {
    return conAviso(async () => {
      const lineas = sucias.map((d) => ({
        capex_code_id: d.capex_code_id,
        ...borradores[d.capex_code_id],
      }))
      const actualizados = await enviar<Descriptivo[]>(
        `/assets/${assetId}/descriptivos`,
        { lineas },
        'PUT',
      )
      setDescriptivos(actualizados)
      setBorradores(
        Object.fromEntries(
          actualizados.map((d) => [d.capex_code_id, { texto: d.texto, validado: d.validado }]),
        ),
      )
      setHecho(`${lineas.length} descriptivo(s) guardado(s).`)
    })
  }

  function marcar(equipo: Equipo, pasa: boolean) {
    return conAviso(async () => {
      await enviar<Equipo>(`/equipment/${equipo.id}`, { pasa_a_capex: pasa }, 'PATCH')
      setEquipos((previos) =>
        (previos ?? []).map((e) => (e.id === equipo.id ? { ...e, pasa_a_capex: pasa } : e)),
      )
    })
  }

  function generar() {
    return conAviso(async () => {
      const r = await enviar<EsqueletoDeEquipos>(
        `/assets/${assetId}/equipment/generar-capex`,
        {},
      )
      setHecho(
        `${r.creadas} actuación(es) creada(s) de ${r.marcados} equipo(s) marcado(s). ` +
          `${r.omitidas} ya existían y no se han duplicado.`,
      )
      if (r.avisos.length) setAviso(r.avisos)
    })
  }

  function atar(foto: Foto, equipmentId: string) {
    return conAviso(async () => {
      const actualizada = await enviar<Foto>(
        `/photos/${foto.id}`,
        { equipment_id: equipmentId || null },
        'PATCH',
      )
      setFotos((previas) => previas.map((f) => (f.id === foto.id ? actualizada : f)))
    })
  }

  const marcados = equipos?.filter((e) => e.pasa_a_capex).length ?? 0

  return (
    <section className="inventario-activo">
      <h3>Inventario del activo</h3>

      {error && <Mensaje tipo="error">{error}</Mensaje>}
      {hecho && <Mensaje tipo="ok">{hecho}</Mensaje>}
      {aviso?.map((a) => (
        <Mensaje key={a} tipo="aviso">
          {a}
        </Mensaje>
      ))}

      {/* ── a) Los descriptivos ─────────────────────────────────────────── */}
      <h4>Descriptivo de cada objeto</h4>
      <p className="ayuda">
        Sale de la documentación del activo y <strong>nace pendiente de validar</strong>: lo ha
        leído una máquina, no un técnico. Corrija el texto y marque la casilla cuando lo dé por
        bueno. Volver a traerlo no pisa lo que ya haya escrito o validado.
      </p>

      <div className="filtro">
        <button
          type="button"
          className="secundario"
          disabled={trabajando}
          onClick={() => void traer()}
        >
          Traer de la documentación
        </button>
        <button
          type="button"
          disabled={trabajando || sucias.length === 0}
          onClick={() => void guardar()}
        >
          {/* «Guardar descriptivos» y no «Guardar» a secas: la ficha del activo
              está en la misma pantalla con su propio botón de guardar, y dos
              botones que dicen lo mismo sobre cosas distintas es la mejor forma
              de que alguien crea que ha guardado lo que no. */}
          Guardar descriptivos {sucias.length > 0 ? `(${sucias.length})` : ''}
        </button>
        {descriptivos && descriptivos.length > 0 && (
          <span className="recuento">
            <strong>{pendientes}</strong> de {descriptivos.length} pendientes de validar
          </span>
        )}
      </div>

      {!descriptivos ? (
        <p className="cargando">Cargando los descriptivos…</p>
      ) : descriptivos.length === 0 ? (
        <Vacio>
          Todavía no hay descriptivos. Se traen de la memoria técnica del edificio con el botón
          de arriba; si el activo no tiene memoria cargada, no hay nada que traer y la
          aplicación no se lo va a inventar.
        </Vacio>
      ) : (
        <div className="desbordable">
          <table className="tabla descriptivos">
            <thead>
              <tr>
                <th scope="col">Capítulo</th>
                <th scope="col">Objeto</th>
                <th scope="col">Descriptivo</th>
                <th scope="col">Estado</th>
                <th scope="col">Validado</th>
              </tr>
            </thead>
            <tbody>
              {descriptivos.map((d) => {
                const b = borradores[d.capex_code_id] ?? {
                  texto: d.texto,
                  validado: d.validado,
                }
                const cambiado = b.texto !== d.texto || b.validado !== d.validado
                return (
                  <tr key={d.id} className={d.validado ? 'validado' : 'pendiente'}>
                    <td className="capitulo">
                      <span className="codigo">{d.chapter_code}</span>
                      <div className="ayuda">{d.chapter_name}</div>
                    </td>
                    <td>
                      <span className="codigo">{d.capex_code}</span>
                      <div className="ayuda">{d.capex_name}</div>
                    </td>
                    <td className="editable">
                      <textarea
                        rows={2}
                        maxLength={4000}
                        aria-label={`Descriptivo de ${d.capex_name} (${d.capex_code})`}
                        value={b.texto}
                        onChange={(e) =>
                          setBorradores((previos) => ({
                            ...previos,
                            [d.capex_code_id]: { ...b, texto: e.target.value },
                          }))
                        }
                      />
                      {cambiado && <span className="ayuda">sin guardar</span>}
                    </td>
                    <td className="validacion">
                      {/* El estado se ESCRIBE, no se pinta: el color acompaña y
                          no informa por sí solo. */}
                      {d.validado ? (
                        <>
                          <strong>Validado</strong>
                          <div className="ayuda">
                            {d.validado_por_nombre ?? 'alguien'} · {d.validado_at?.slice(0, 10)}
                          </div>
                        </>
                      ) : (
                        <>
                          <strong>Pendiente de validar</strong>
                          <div className="ayuda">por el gestor técnico</div>
                        </>
                      )}
                      {d.es_simulada && (
                        <div className="ayuda simulada">
                          extracción SIMULADA: léalo en el documento antes de validarlo
                        </div>
                      )}
                    </td>
                    {/* La casilla va suelta, sin `<label>` ni texto oculto: la
                        cabecera de la columna ya dice «Validado» y el
                        `aria-label` nombra la fila entera. Un `.oculto-visual`
                        aquí sería además un elemento posicionado dentro de una
                        tabla que se desplaza en horizontal, y eso ensancha la
                        página en móvil aunque no se vea. */}
                    <td className="casilla-validado">
                      <input
                        type="checkbox"
                        checked={b.validado}
                        // Sin texto no hay nada que firmar, y el servidor lo
                        // rechaza igualmente: deshabilitarla lo explica antes
                        // de que alguien se lleve un 422.
                        disabled={!b.texto.trim()}
                        aria-label={`Marcar como validado ${d.capex_name} (${d.capex_code})`}
                        onChange={(e) =>
                          setBorradores((previos) => ({
                            ...previos,
                            [d.capex_code_id]: { ...b, validado: e.target.checked },
                          }))
                        }
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── b) «Pasa a CAPEX» ───────────────────────────────────────────── */}
      <h4>Equipo del activo</h4>
      <p className="ayuda">
        Marque lo que hay que sustituir o intervenir. <strong>Marcar no crea nada</strong>: las
        actuaciones se generan todas de una vez con el botón, en borrador y sin importe, para
        valorarlas después desde el árbol del CAPEX.
      </p>

      {!equipos ? (
        <p className="cargando">Cargando el inventario de equipo…</p>
      ) : equipos.length === 0 ? (
        <Vacio>
          Este activo no tiene equipos en el inventario. Se dan de alta desde «Inventario de
          equipo», uno a uno o importando la hoja de la visita.
        </Vacio>
      ) : (
        <>
          <div className="filtro">
            <button
              type="button"
              disabled={trabajando || marcados === 0}
              onClick={() => void generar()}
            >
              Generar actuaciones de los marcados ({marcados})
            </button>
          </div>
          <div className="desbordable">
            <table className="tabla equipo-capex">
              <thead>
                <tr>
                  <th scope="col">Pasa a CAPEX</th>
                  <th scope="col">Etiqueta</th>
                  <th scope="col">Equipo</th>
                  <th scope="col">Sistema</th>
                  <th scope="col">Vida residual</th>
                  <th scope="col" className="numerica">
                    Fotos
                  </th>
                </tr>
              </thead>
              <tbody>
                {equipos.map((e) => (
                  <tr key={e.id} className={e.pasa_a_capex ? 'marcado' : ''}>
                    <td className="casilla-marcado">
                      <input
                        type="checkbox"
                        checked={e.pasa_a_capex}
                        disabled={trabajando}
                        aria-label={`Pasa a CAPEX: ${e.tag ?? e.equipment_type}`}
                        onChange={(ev) => void marcar(e, ev.target.checked)}
                      />
                    </td>
                    <td>{e.tag ?? '—'}</td>
                    <td>
                      {e.equipment_type}
                      {e.manufacturer && (
                        <div className="ayuda">
                          {e.manufacturer} {e.model ?? ''}
                        </div>
                      )}
                    </td>
                    <td>
                      {e.technical_system_name ?? (
                        <span className="ayuda">sin sistema: no se sabe a qué capítulo va</span>
                      )}
                    </td>
                    <td title={e.vida_resumen}>
                      {e.remaining_life_years === null ? (
                        <span className="ayuda">sin datos</span>
                      ) : e.remaining_life_years < 0 ? (
                        <strong>vencida hace {Math.abs(e.remaining_life_years)} años</strong>
                      ) : (
                        `${e.remaining_life_years} años`
                      )}
                    </td>
                    <td className="numerica">
                      {fotos.filter((f) => f.equipment_id === e.id).length}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ── c) Fotos de la visita ───────────────────────────────────────── */}
      <h4>Fotografías de la visita</h4>
      <p className="ayuda">
        Ate cada fotografía al equipo que retrata. Es lo que justifica medio año después por qué
        se propone sustituir esa máquina y no otra. Desatarla no borra la foto, y borrar el
        equipo tampoco: la fotografía es evidencia de la visita y vale por sí sola.
      </p>

      {fotos.length === 0 ? (
        <Vacio>
          Este activo no tiene fotografías todavía. Se suben desde «Fotografías», también desde
          el móvil durante la visita.
        </Vacio>
      ) : !equipos || equipos.length === 0 ? (
        <Mensaje tipo="aviso">
          Hay {fotos.length} fotografía(s), pero ningún equipo al que atarlas. Dé de alta el
          inventario primero.
        </Mensaje>
      ) : (
        <div className="desbordable">
          <table className="tabla fotos-equipo">
            <thead>
              <tr>
                <th scope="col">Fotografía</th>
                <th scope="col">Tomada</th>
                <th scope="col">Equipo que retrata</th>
              </tr>
            </thead>
            <tbody>
              {fotos.map((f) => (
                <tr key={f.id}>
                  <td>{f.display_name}</td>
                  <td>
                    {f.taken_at?.slice(0, 10) ?? <span className="ayuda">sin fecha</span>}
                  </td>
                  <td>
                    <select
                      value={f.equipment_id ?? ''}
                      disabled={trabajando}
                      aria-label={`Equipo que retrata ${f.display_name}`}
                      onChange={(e) => void atar(f, e.target.value)}
                    >
                      <option value="">— ninguno —</option>
                      {equipos.map((e) => (
                        <option key={e.id} value={e.id}>
                          {e.tag ? `${e.tag} · ${e.equipment_type}` : e.equipment_type}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

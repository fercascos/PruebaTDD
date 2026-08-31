import { useCallback, useEffect, useState } from 'react'
import { ErrorDeApi, descargar, enviar, obtener } from '../api/cliente'
import type { Mapeo, Plantilla, Previo, VersionDeInforme } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

const ORDEN_DE_SEVERIDAD = ['BLOQUEANTE', 'ALTA', 'MEDIA', 'BAJA'] as const

export function PestanaInformes({ projectId }: { projectId: string }) {
  const [plantillas, setPlantillas] = useState<Plantilla[]>([])
  const [plantillaElegida, setPlantillaElegida] = useState('')
  const [mapeos, setMapeos] = useState<Mapeo[]>([])
  const [mapeoElegido, setMapeoElegido] = useState('')
  const [previo, setPrevio] = useState<Previo | null>(null)
  const [versiones, setVersiones] = useState<VersionDeInforme[]>([])
  const [error, setError] = useState<string | null>(null)
  const [trabajando, setTrabajando] = useState(false)

  const recargarVersiones = useCallback(() => {
    obtener<VersionDeInforme[]>(`/projects/${projectId}/reports`)
      .then(setVersiones)
      .catch(() => setVersiones([]))
  }, [projectId])

  useEffect(() => {
    obtener<Plantilla[]>('/report-templates')
      .then((lista) => {
        setPlantillas(lista)
        if (lista[0]) setPlantillaElegida(lista[0].id)
      })
      .catch((e: Error) => setError(e.message))
    recargarVersiones()
  }, [recargarVersiones])

  /**
   * `[REQ]` §17 · Generar ya no bloquea: la petición encola y el worker
   * produce el fichero. Mientras haya alguna versión en GENERANDO se vuelve a
   * preguntar cada dos segundos.
   *
   * Se sondea en vez de abrir una conexión permanente porque es una espera de
   * segundos y ocurre unas pocas veces por encargo: montar WebSockets para eso
   * añadiría un canal que mantener a cambio de nada.
   */
  const generando = versiones.some((v) => v.status === 'GENERANDO')
  useEffect(() => {
    if (!generando) return
    const t = setInterval(() => void recargarVersiones(), 2000)
    return () => clearInterval(t)
  }, [generando, recargarVersiones])

  useEffect(() => {
    if (!plantillaElegida) return
    obtener<Mapeo[]>(`/report-templates/${plantillaElegida}/mappings`)
      .then((lista) => {
        setMapeos(lista)
        const porDefecto = lista.find((m) => m.is_default) ?? lista[0]
        setMapeoElegido(porDefecto?.id ?? '')
      })
      .catch(() => setMapeos([]))
    setPrevio(null)
  }, [plantillaElegida])

  async function comprobar() {
    setTrabajando(true)
    setError(null)
    try {
      setPrevio(
        await enviar<Previo>(`/projects/${projectId}/reports/preflight`, {
          template_id: plantillaElegida,
          mapping_id: mapeoElegido || null,
        }),
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se ha podido comprobar')
    } finally {
      setTrabajando(false)
    }
  }

  async function generar() {
    setTrabajando(true)
    setError(null)
    try {
      // La respuesta trae la versión en GENERANDO. No se espera aquí: se
      // recarga la lista y el sondeo de arriba se encarga del resto.
      await enviar<VersionDeInforme>(`/projects/${projectId}/reports`, {
        template_id: plantillaElegida,
        mapping_id: mapeoElegido || null,
      })
      await recargarVersiones()
    } catch (e) {
      setError(
        e instanceof ErrorDeApi && e.esConflicto
          ? e.message
          : e instanceof Error
            ? e.message
            : 'No se ha podido generar',
      )
    } finally {
      setTrabajando(false)
    }
  }

  async function cambiarEstado(version: VersionDeInforme, destino: string) {
    setError(null)
    try {
      await enviar(`/reports/${version.id}/transitions`, { to: destino })
      recargarVersiones()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se ha podido cambiar el estado')
    }
  }

  if (plantillas.length === 0) {
    return (
      <Vacio>
        No hay ninguna plantilla registrada. Súbala en «Plantillas» antes de generar un informe.
      </Vacio>
    )
  }

  return (
    <>
      {error && <Mensaje tipo="error">{error}</Mensaje>}

      <div className="filtro">
        <label>
          Plantilla
          <select value={plantillaElegida} onChange={(e) => setPlantillaElegida(e.target.value)}>
            {plantillas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.language})
              </option>
            ))}
          </select>
        </label>
        <label>
          Mapeo
          <select value={mapeoElegido} onChange={(e) => setMapeoElegido(e.target.value)}>
            <option value="">— sin mapeo —</option>
            {mapeos.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
                {m.is_default ? ' (por defecto)' : ''}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => void comprobar()} disabled={trabajando}>
          Comprobar antes de generar
        </button>
      </div>

      {previo && (
        <section className="previo">
          <h3>
            {previo.summary.total} avisos · {previo.summary.blocking} bloquean la generación
          </h3>
          {ORDEN_DE_SEVERIDAD.map((severidad) => {
            const lista = previo.warnings.filter((w) => w.severidad === severidad)
            if (lista.length === 0) return null
            return (
              <ul key={severidad} className={`avisos s-${severidad.toLowerCase()}`}>
                {lista.map((w, i) => (
                  <li key={`${w.codigo}-${i}`}>
                    <code>{w.codigo}</code> {w.mensaje}
                  </li>
                ))}
              </ul>
            )
          })}
          <button
            type="button"
            className="destacado"
            onClick={() => void generar()}
            // El servidor lo rechazaría igualmente; deshabilitarlo aquí ahorra
            // el viaje y deja claro qué hay que arreglar antes.
            disabled={!previo.can_generate || trabajando}
          >
            {previo.can_generate ? 'Generar informe' : 'Corrija lo bloqueante para generar'}
          </button>
        </section>
      )}

      <h3>Versiones</h3>
      {versiones.length === 0 ? (
        <Vacio>Todavía no se ha generado ningún informe de este encargo.</Vacio>
      ) : (
        <div className="desbordable">
          <table className="tabla">
            <thead>
              <tr>
                <th>Versión</th>
                <th>Estado</th>
                <th>Huella del PPTX</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {versiones.map((v) => (
                <tr key={v.id}>
                  <td>v{v.version_number}</td>
                  <td>
                    <span className={`estado e-${v.status.toLowerCase()}`}>{v.status}</span>
                    {v.is_locked && <span className="candado"> inmutable</span>}
                  </td>
                  <td>
                    <code title={v.pptx_sha256 ?? ''}>{v.pptx_sha256?.slice(0, 12) ?? '—'}…</code>
                  </td>
                  <td className="acciones">
                    {/* Mientras el worker no ha terminado no hay ningún fichero
                        que descargar: ofrecer el botón daría un 404 y parecería
                        un fallo cuando lo único que pasa es que aún se está
                        generando. */}
                    {v.status === 'GENERANDO' && (
                      <span className="generando">Generando… se actualiza solo</span>
                    )}
                    {v.status === 'ERROR' && (
                      <span className="fallo">
                        No se pudo generar. Vuelva a pedirlo; si se repite, avise a soporte.
                      </span>
                    )}
                    {v.status !== 'GENERANDO' && v.status !== 'ERROR' && (
                      <>
                        <button
                          type="button"
                          className="secundario"
                          onClick={() =>
                            void descargar(
                              `/reports/${v.id}/download`,
                              `informe-v${v.version_number}.pptx`,
                            )
                          }
                        >
                          PPTX
                        </button>
                        <button
                          type="button"
                          className="secundario"
                          onClick={() =>
                            void descargar(
                              `/reports/${v.id}/download?formato=xlsx`,
                              `capex-v${v.version_number}.xlsx`,
                            )
                          }
                        >
                          XLSX
                        </button>
                      </>
                    )}
                    {!v.is_locked && v.status !== 'GENERANDO' && v.status !== 'ERROR' && (
                      <select
                        value=""
                        onChange={(e) => e.target.value && void cambiarEstado(v, e.target.value)}
                      >
                        <option value="">Cambiar estado…</option>
                        <option value="EN_REVISION">A revisión</option>
                        <option value="APROBADO">Aprobar</option>
                        <option value="EMITIDO">Emitir (bloquea para siempre)</option>
                      </select>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

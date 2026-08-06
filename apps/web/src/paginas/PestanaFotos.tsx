import { useCallback, useEffect, useState } from 'react'
import { enviar, obtener } from '../api/cliente'
import type { Activo, Foto } from '../api/tipos'
import { DetalleDeFoto } from '../fotos/DetalleDeFoto'
import { Imagen } from '../fotos/Imagen'
import { RenombradoEnLote } from '../fotos/RenombradoEnLote'
import { Subida } from '../fotos/Subida'
import { Mensaje, Vacio } from '../ui/Marco'
import { NuevoHallazgo } from './NuevoHallazgo'

export function PestanaFotos({ projectId }: { projectId: string }) {
  const [fotos, setFotos] = useState<Foto[] | null>(null)
  const [activos, setActivos] = useState<Activo[]>([])
  const [activoElegido, setActivoElegido] = useState('')
  const [filtroActivo, setFiltroActivo] = useState('')
  const [soloInforme, setSoloInforme] = useState(false)
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set())
  const [abierta, setAbierta] = useState<Foto | null>(null)
  const [hallazgoDesde, setHallazgoDesde] = useState<Foto | null>(null)
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(() => {
    const filtros = new URLSearchParams()
    if (filtroActivo) filtros.set('asset_id', filtroActivo)
    if (soloInforme) filtros.set('include_in_report', 'true')
    obtener<Foto[]>(`/projects/${projectId}/photos?${filtros}`)
      .then((lista) => {
        setFotos(lista)
        // Si la foto abierta sigue en la lista, se refresca con lo recién
        // guardado; si ya no está, se cierra el panel en vez de dejarlo
        // enseñando un estado que ya no existe.
        setAbierta((actual) => (actual ? (lista.find((f) => f.id === actual.id) ?? null) : null))
      })
      .catch((e: Error) => setError(e.message))
  }, [projectId, filtroActivo, soloInforme])

  useEffect(() => {
    recargar()
    obtener<Activo[]>(`/projects/${projectId}/assets`)
      .then(setActivos)
      .catch(() => setActivos([]))
  }, [projectId, recargar])

  function alternar(id: string) {
    setSeleccion((previa) => {
      const nueva = new Set(previa)
      if (nueva.has(id)) nueva.delete(id)
      else nueva.add(id)
      return nueva
    })
  }

  async function enLote(cambios: Record<string, unknown>) {
    await enviar('/photos/bulk-update', { photo_ids: [...seleccion], ...cambios })
    setSeleccion(new Set())
    recargar()
  }

  if (error) return <Mensaje tipo="error">{error}</Mensaje>

  if (hallazgoDesde) {
    return (
      <NuevoHallazgo
        projectId={projectId}
        photoId={hallazgoDesde.id}
        activoInicial={hallazgoDesde.asset_id ?? undefined}
        zonaInicial={hallazgoDesde.zone_id ?? undefined}
        alGuardar={() => {
          setHallazgoDesde(null)
          setAbierta(null)
          recargar()
        }}
        alCancelar={() => setHallazgoDesde(null)}
      />
    )
  }

  return (
    <>
      <div className="filtro">
        <label>
          Activo al que asignar lo que se suba
          <select value={activoElegido} onChange={(e) => setActivoElegido(e.target.value)}>
            <option value="">Sin asignar (se avisa, no se bloquea)</option>
            {activos.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Ver solo las de
          <select value={filtroActivo} onChange={(e) => setFiltroActivo(e.target.value)}>
            <option value="">Todos los activos</option>
            {activos.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label className="casilla">
          <input
            type="checkbox"
            checked={soloInforme}
            onChange={(e) => setSoloInforme(e.target.checked)}
          />
          Solo las seleccionadas para el informe
        </label>
      </div>

      <Subida projectId={projectId} assetId={activoElegido || undefined} alTerminar={recargar} />

      {seleccion.size > 0 && (
        <div className="barra-seleccion">
          <span>{seleccion.size} seleccionadas</span>
          <button type="button" onClick={() => void enLote({ include_in_report: true })}>
            Incluir en el informe
          </button>
          <button
            type="button"
            className="secundario"
            onClick={() => void enLote({ include_in_report: false })}
          >
            Quitar del informe
          </button>
          {activoElegido && (
            <button
              type="button"
              className="secundario"
              onClick={() => void enLote({ asset_id: activoElegido })}
            >
              Asignar al activo elegido
            </button>
          )}
          <RenombradoEnLote
            photoIds={[...seleccion]}
            alAplicar={() => {
              setSeleccion(new Set())
              recargar()
            }}
          />
        </div>
      )}

      {abierta && (
        <DetalleDeFoto
          foto={abierta}
          projectId={projectId}
          alGuardar={recargar}
          alCerrar={() => setAbierta(null)}
          alCrearHallazgo={setHallazgoDesde}
        />
      )}

      {!fotos ? (
        <p className="cargando">Cargando fotografías…</p>
      ) : fotos.length === 0 ? (
        <Vacio>
          {filtroActivo || soloInforme
            ? 'Ninguna fotografía cumple el filtro.'
            : 'Todavía no hay fotografías. Use los botones de arriba para añadirlas.'}
        </Vacio>
      ) : (
        <ul className="rejilla">
          {fotos.map((f) => (
            <li key={f.id} className={seleccion.has(f.id) ? 'elegida' : ''}>
              <button type="button" className="miniatura" onClick={() => setAbierta(f)}>
                {/* La miniatura, no el original: una visita de 400 fotos son
                    400 archivos de 4 MB para pintar recuadros de 320 píxeles.
                    Y con `<Imagen>` porque un `src` a secas no lleva la
                    credencial y devolvía un 401 por cada foto. */}
                <Imagen
                  ruta={`/photos/${f.id}/download?variante=MINIATURA_320`}
                  alt={f.caption ?? f.display_name}
                />
              </button>
              <p className="nombre" title={f.original_filename}>
                {f.display_name}
              </p>
              <p className="meta">
                <label className="casilla">
                  <input
                    type="checkbox"
                    checked={seleccion.has(f.id)}
                    onChange={() => alternar(f.id)}
                  />
                  elegir
                </label>
                {f.include_in_report && <span className="marca">en el informe</span>}
                {f.gps_latitude !== null && <span className="marca">con GPS</span>}
                {f.taken_at === null && <span className="marca aviso">sin fecha</span>}
                {f.asset_id === null && <span className="marca aviso">sin activo</span>}
              </p>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

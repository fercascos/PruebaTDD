import { useCallback, useEffect, useState } from 'react'
import { enviar, obtener } from '../api/cliente'
import type { Activo, Foto } from '../api/tipos'
import { Subida } from '../fotos/Subida'
import { Mensaje, Vacio } from '../ui/Marco'
import { RenombradoEnLote } from '../fotos/RenombradoEnLote'

export function PestanaFotos({ projectId }: { projectId: string }) {
  const [fotos, setFotos] = useState<Foto[] | null>(null)
  const [activos, setActivos] = useState<Activo[]>([])
  const [activoElegido, setActivoElegido] = useState('')
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(() => {
    obtener<Foto[]>(`/projects/${projectId}/photos`)
      .then(setFotos)
      .catch((e: Error) => setError(e.message))
  }, [projectId])

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

  async function marcarParaInforme(incluir: boolean) {
    await enviar('/photos/bulk-update', {
      photo_ids: [...seleccion],
      include_in_report: incluir,
    })
    setSeleccion(new Set())
    recargar()
  }

  if (error) return <Mensaje tipo="error">{error}</Mensaje>

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
      </div>

      <Subida
        projectId={projectId}
        assetId={activoElegido || undefined}
        alTerminar={recargar}
      />

      {seleccion.size > 0 && (
        <div className="barra-seleccion">
          <span>{seleccion.size} seleccionadas</span>
          <button type="button" onClick={() => void marcarParaInforme(true)}>
            Incluir en el informe
          </button>
          <button type="button" className="secundario" onClick={() => void marcarParaInforme(false)}>
            Quitar del informe
          </button>
          <RenombradoEnLote
            photoIds={[...seleccion]}
            alAplicar={() => {
              setSeleccion(new Set())
              recargar()
            }}
          />
        </div>
      )}

      {!fotos ? (
        <p className="cargando">Cargando fotografías…</p>
      ) : fotos.length === 0 ? (
        <Vacio>Todavía no hay fotografías. Use los botones de arriba para añadirlas.</Vacio>
      ) : (
        <ul className="rejilla">
          {fotos.map((f) => (
            <li key={f.id} className={seleccion.has(f.id) ? 'elegida' : ''}>
              <button type="button" className="miniatura" onClick={() => alternar(f.id)}>
                {/* `loading="lazy"` importa de verdad: una rejilla con 400
                    miniaturas sin él descarga las 400 al abrir la pestaña. */}
                <img
                  src={`/api/v1/photos/${f.id}/download`}
                  alt={f.caption ?? f.display_name}
                  loading="lazy"
                />
              </button>
              <p className="nombre" title={f.original_filename}>
                {f.display_name}
              </p>
              <p className="meta">
                {f.include_in_report && <span className="marca">en el informe</span>}
                {f.gps_latitude !== null && <span className="marca">con GPS</span>}
                {f.taken_at === null && <span className="marca aviso">sin fecha</span>}
              </p>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

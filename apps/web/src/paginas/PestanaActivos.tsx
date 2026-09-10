import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { borrar, obtener } from '../api/cliente'
import type { Activo } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'
import { FichaDeActivo } from './FichaDeActivo'

/**
 * La **lista** de activos del proyecto, y solo la lista.
 *
 * `[REQ]` §3.2 · Antes esta pantalla apilaba, al abrir un activo, la ficha y
 * las cuatro secciones una debajo de otra: siete mil píxeles de alto, y para
 * llegar al CAPEX había que pasar por delante de todo lo demás. Ahora abrir un
 * activo **entra en su espacio** —`/activos/:assetId`—, que tiene sus propias
 * cinco pestañas y una dirección web por sección.
 *
 * Aquí solo queda dar de alta, que sí es una ficha suelta: un activo que aún no
 * existe no tiene visita, ni inventario, ni actuaciones que enseñar.
 */

export function PestanaActivos({ projectId }: { projectId: string }) {
  const [activos, setActivos] = useState<Activo[] | null>(null)
  const [creando, setCreando] = useState(false)
  const navegar = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(() => {
    obtener<Activo[]>(`/projects/${projectId}/assets`)
      .then(setActivos)
      .catch((e: Error) => setError(e.message))
  }, [projectId])

  useEffect(recargar, [recargar])

  async function borrarActivo(activo: Activo) {
    setError(null)
    try {
      await borrar(`/assets/${activo.id}`)
      recargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se ha podido borrar')
    }
  }

  if (error) return <Mensaje tipo="error">{error}</Mensaje>

  // Solo el alta usa la ficha suelta. Editar uno que existe entra en su
  // espacio, que es donde está todo lo suyo.
  if (creando) {
    return (
      <FichaDeActivo
        projectId={projectId}
        alGuardar={() => {
          setCreando(false)
          recargar()
        }}
        alCancelar={() => setCreando(false)}
      />
    )
  }

  return (
    <>
      <div className="filtro">
        <button type="button" onClick={() => setCreando(true)}>
          Añadir activo
        </button>
      </div>

      {!activos ? (
        <p className="cargando">Cargando activos…</p>
      ) : activos.length === 0 ? (
        <Vacio>
          Este proyecto todavía no tiene activos. Un proyecto sin activos no sale de borrador.
        </Vacio>
      ) : (
        <div className="desbordable">
          <table className="tabla">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Código</th>
                <th>Ciudad</th>
                <th>Año</th>
                <th className="numerica">Superficie construida</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {activos.map((a) => (
                <tr key={a.id}>
                  <td>{a.name}</td>
                  <td>{a.asset_code ?? '—'}</td>
                  <td>{a.city ?? '—'}</td>
                  <td>{a.year_built ?? '—'}</td>
                  <td className="numerica">
                    {a.total_built_sqm
                      ? `${Number(a.total_built_sqm).toLocaleString('es-ES')} m²`
                      : '—'}
                  </td>
                  <td className="acciones">
                    <button
                      type="button"
                      className="secundario"
                      onClick={() => navegar(`/proyectos/${projectId}/activos/${a.id}`)}
                    >
                      Abrir
                    </button>
                    <button
                      type="button"
                      className="secundario"
                      onClick={() => void borrarActivo(a)}
                      // El borrado es lógico: los hallazgos ya redactados siguen
                      // referenciando este activo y el informe emitido también.
                      title="Borrado lógico: los hallazgos ya redactados lo conservan"
                    >
                      Borrar
                    </button>
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

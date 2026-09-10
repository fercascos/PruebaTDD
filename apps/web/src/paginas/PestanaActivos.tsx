import { useCallback, useEffect, useState } from 'react'
import { borrar, obtener } from '../api/cliente'
import type { Activo } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'
import { FichaDeActivo } from './FichaDeActivo'
import { ArbolDeUbicaciones } from './ArbolDeUbicaciones'
import { ArbolDeCapex } from './ArbolDeCapex'
import { InventarioDelActivo } from './InventarioDelActivo'
import { VisitaDelActivo } from './VisitaDelActivo'

export function PestanaActivos({ projectId }: { projectId: string }) {
  const [activos, setActivos] = useState<Activo[] | null>(null)
  const [editando, setEditando] = useState<Activo | 'nuevo' | null>(null)
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

  if (editando) {
    return (
      <>
        <FichaDeActivo
          projectId={projectId}
          activo={editando === 'nuevo' ? undefined : editando}
          alGuardar={() => {
            setEditando(null)
            recargar()
          }}
          alCancelar={() => setEditando(null)}
        />
        {/* Los dos árboles solo tienen sentido sobre un activo que ya existe:
            sus nodos y sus actuaciones cuelgan de un `asset_id`. En el alta no
            se muestran.
            `[REQ]` §3.2 de `docs/23` · El de CAPEX vive **dentro del activo**,
            que es donde va a acabar todo. Es el primer trozo de esa mudanza:
            está aquí, y no en una pestaña del proyecto, desde el primer día. */}
        {editando !== 'nuevo' && (
          <>
            <ArbolDeUbicaciones assetId={editando.id} />
            {/* `[REQ]` §3.2 c · La visita va antes que el inventario porque es
                de donde sale: se recorre el edificio y se apunta lo que hay.
                Y sus limitaciones de acceso explican por qué el inventario de
                más abajo puede estar incompleto. */}
            <VisitaDelActivo activo={editando} />
            {/* `[REQ]` §3.2 d · El inventario va **antes** que el árbol del
                CAPEX y no después: describe lo que hay y marca lo que hay que
                sustituir, y de ahí salen actuaciones que aparecen en el árbol.
                Al revés se leería como un apéndice de algo que ya está hecho. */}
            <InventarioDelActivo projectId={projectId} assetId={editando.id} />
            <ArbolDeCapex projectId={projectId} assetId={editando.id} />
          </>
        )}
      </>
    )
  }

  return (
    <>
      <div className="filtro">
        <button type="button" onClick={() => setEditando('nuevo')}>
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
                    <button type="button" className="secundario" onClick={() => setEditando(a)}>
                      Editar
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

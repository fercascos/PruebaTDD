import { useCallback, useEffect, useState } from 'react'
import { borrar, enviar, obtener } from '../api/cliente'
import type { NodoDeUbicacion, TipoDeNodo } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

/**
 * El árbol físico de un activo: zonas, plantas y espacios.
 *
 * `[REC]` §8.4 · No sustituye a la zona del catálogo, la complementa. La zona
 * clasifica —«Cubierta»— y es lo que agrega el informe; esto localiza
 * —«Cubierta › Sala Máquinas 2»— y es lo que permite volver a encontrar una
 * fotografía seis meses después.
 *
 * La lista llega **en orden de recorrido** desde la API, con la profundidad de
 * cada nodo ya calculada, así que pintarla es sangrar y nada más: no hay que
 * armar la jerarquía aquí.
 */

const TIPOS: { valor: TipoDeNodo; etiqueta: string }[] = [
  { valor: 'ZONA', etiqueta: 'Zona' },
  { valor: 'PLANTA', etiqueta: 'Planta' },
  { valor: 'ESPACIO', etiqueta: 'Espacio' },
]

export function ArbolDeUbicaciones({ assetId }: { assetId: string }) {
  const [nodos, setNodos] = useState<NodoDeUbicacion[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [nombre, setNombre] = useState('')
  const [tipo, setTipo] = useState<TipoDeNodo>('ZONA')
  const [padre, setPadre] = useState('')
  const [ocupado, setOcupado] = useState(false)

  const recargar = useCallback(async () => {
    try {
      setNodos(await obtener<NodoDeUbicacion[]>(`/assets/${assetId}/locations`))
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [assetId])

  useEffect(() => {
    void recargar()
  }, [recargar])

  async function crear(e: React.FormEvent) {
    e.preventDefault()
    if (!nombre.trim()) return
    setOcupado(true)
    try {
      await enviar(`/assets/${assetId}/locations`, {
        node_type: tipo,
        name: nombre.trim(),
        parent_id: padre || null,
      })
      setNombre('')
      await recargar()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setOcupado(false)
    }
  }

  async function mover(nodo: NodoDeUbicacion, nuevoPadre: string) {
    try {
      await enviar(`/locations/${nodo.id}`, { parent_id: nuevoPadre || null }, 'PATCH')
      await recargar()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function eliminar(nodo: NodoDeUbicacion) {
    try {
      await borrar(`/locations/${nodo.id}`)
      await recargar()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  if (!nodos) return <p className="cargando">Cargando ubicaciones…</p>

  return (
    <section className="ubicaciones">
      <h3>Ubicaciones del edificio</h3>
      <p className="ayuda">
        Dónde está cada cosa dentro de este activo. Es distinto de la zona: la zona clasifica para el
        informe («Cubierta»), esto localiza para volver a encontrarlo («Cubierta › Sala Máquinas 2»).
        Lo que se elija aquí alimenta el token <code>[Espacio]</code> al renombrar fotografías.
      </p>

      {error && <Mensaje tipo="error">{error}</Mensaje>}

      <form className="nueva-ubicacion" onSubmit={(e) => void crear(e)}>
        <select value={tipo} onChange={(e) => setTipo(e.target.value as TipoDeNodo)}>
          {TIPOS.map((t) => (
            <option key={t.valor} value={t.valor}>
              {t.etiqueta}
            </option>
          ))}
        </select>
        <select value={padre} onChange={(e) => setPadre(e.target.value)} aria-label="Dentro de">
          <option value="">— en la raíz —</option>
          {nodos.map((n) => (
            <option key={n.id} value={n.id}>
              {n.ruta_legible}
            </option>
          ))}
        </select>
        <input
          value={nombre}
          onChange={(e) => setNombre(e.target.value)}
          placeholder="Nombre (p. ej. «Sala Máquinas 2»)"
          aria-label="Nombre de la ubicación"
          maxLength={160}
        />
        <button type="submit" disabled={!nombre.trim() || ocupado}>
          Añadir
        </button>
      </form>

      {nodos.length === 0 ? (
        <Vacio>
          Este activo no tiene ubicaciones. Sin ellas las fotografías se pueden clasificar por zona,
          pero no se puede decir en qué sala estaban.
        </Vacio>
      ) : (
        <ul className="arbol">
          {nodos.map((n) => (
            <li key={n.id} style={{ paddingLeft: `${n.profundidad * 1.4}rem` }}>
              <span className={`tipo t-${n.node_type.toLowerCase()}`}>{n.node_type}</span>
              <strong>{n.name}</strong>
              {n.zone_name && <span className="zona-ligada">zona: {n.zone_name}</span>}
              <select
                value={n.parent_id ?? ''}
                onChange={(e) => void mover(n, e.target.value)}
                aria-label={`Mover ${n.name}`}
              >
                <option value="">— en la raíz —</option>
                {/* Un nodo no puede colgar de sí mismo ni de su descendencia: la
                    API lo rechaza, pero ofrecerlo en la lista sería ofrecer un
                    error. Se filtra por la ruta, que ya trae el prefijo. */}
                {nodos
                  .filter((o) => o.id !== n.id && !o.ruta_legible.startsWith(`${n.ruta_legible} ›`))
                  .map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.ruta_legible}
                    </option>
                  ))}
              </select>
              <button type="button" className="secundario peligro" onClick={() => void eliminar(n)}>
                Eliminar
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

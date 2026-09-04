/**
 * La fila de filtros, encima de los gráficos.
 *
 * Los filtros viven en el estado de la página y viajan en la consulta a la API:
 * no se filtra en el navegador. Filtrar aquí lo que el servidor ya ha mandado
 * significaría que el navegador ha recibido datos que quizá no debía ver, y ese
 * es justo el error que el ámbito de visibilidad viene a evitar.
 */
import type { Cartera, Activo, Vector } from '../api/tipos'
import { ETIQUETA, VECTORES } from '../graficos/paleta'

export interface Seleccion {
  desde: string
  hasta: string
  cartera: string
  activo: string
  vectores: Vector[]
}

interface Props {
  carteras: Cartera[]
  activos: Activo[]
  seleccion: Seleccion
  cambiar: (nueva: Seleccion) => void
}

/** Atajos de periodo. El de doce meses es el que se usa el 90 % de las veces. */
export function ultimosMeses(cuantos: number): { desde: string; hasta: string } {
  const hoy = new Date()
  // El día 1 del mes que viene: `hasta` es EXCLUSIVA, igual que en la API.
  const hasta = new Date(Date.UTC(hoy.getUTCFullYear(), hoy.getUTCMonth() + 1, 1))
  const desde = new Date(Date.UTC(hoy.getUTCFullYear(), hoy.getUTCMonth() + 1 - cuantos, 1))
  return { desde: iso(desde), hasta: iso(hasta) }
}

export function anio(cual: number): { desde: string; hasta: string } {
  return { desde: `${cual}-01-01`, hasta: `${cual + 1}-01-01` }
}

function iso(fecha: Date): string {
  return fecha.toISOString().slice(0, 10)
}

export function Filtros({ carteras, activos, seleccion, cambiar }: Props) {
  const activosVisibles = seleccion.cartera
    ? activos.filter((a) => a.cartera_id === seleccion.cartera)
    : activos

  return (
    <div className="filtros">
      <label>
        Cartera
        <select
          value={seleccion.cartera}
          onChange={(e) =>
            // Al cambiar de cartera se suelta el activo: dejarlo puesto
            // enseñaría un panel vacío sin decir por qué.
            cambiar({ ...seleccion, cartera: e.target.value, activo: '' })
          }
        >
          <option value="">Todas</option>
          {carteras.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre}
            </option>
          ))}
        </select>
      </label>

      <label>
        Activo
        <select
          value={seleccion.activo}
          onChange={(e) => cambiar({ ...seleccion, activo: e.target.value })}
        >
          <option value="">Todos</option>
          {activosVisibles.map((a) => (
            <option key={a.id} value={a.id}>
              {a.codigo} · {a.nombre}
            </option>
          ))}
        </select>
      </label>

      <label>
        Desde
        <input
          type="date"
          value={seleccion.desde}
          onChange={(e) => cambiar({ ...seleccion, desde: e.target.value })}
        />
      </label>
      <label>
        Hasta <span className="pista" title="Exclusiva: un trimestre acaba el día 1 del siguiente">(excl.)</span>
        <input
          type="date"
          value={seleccion.hasta}
          onChange={(e) => cambiar({ ...seleccion, hasta: e.target.value })}
        />
      </label>

      <div className="atajos">
        <button type="button" onClick={() => cambiar({ ...seleccion, ...ultimosMeses(12) })}>
          12 meses
        </button>
        <button type="button" onClick={() => cambiar({ ...seleccion, ...ultimosMeses(3) })}>
          3 meses
        </button>
        <button
          type="button"
          onClick={() => cambiar({ ...seleccion, ...anio(new Date().getUTCFullYear() - 1) })}
        >
          {new Date().getUTCFullYear() - 1}
        </button>
      </div>

      <fieldset className="vectores">
        <legend>Vectores</legend>
        {VECTORES.map((v) => (
          <label key={v} className="casilla">
            <input
              type="checkbox"
              checked={seleccion.vectores.includes(v)}
              onChange={(e) =>
                cambiar({
                  ...seleccion,
                  vectores: e.target.checked
                    ? [...seleccion.vectores, v]
                    : seleccion.vectores.filter((x) => x !== v),
                })
              }
            />
            {ETIQUETA[v]}
          </label>
        ))}
      </fieldset>
    </div>
  )
}

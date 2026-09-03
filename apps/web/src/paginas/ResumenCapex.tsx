import { useCallback, useEffect, useState } from 'react'
import { obtener } from '../api/cliente'
import type {
  ResumenPorActivo,
  ResumenPorCapitulo,
  ResumenPorConcepto,
  ResumenPorHorizonte,
} from '../api/tipos'
import { Tarta, type Porcion } from '../graficos/Tarta'
import { agrupar } from '../graficos/paleta'
import { Mensaje, Vacio } from '../ui/Marco'

/**
 * El resumen del CAPEX: cuatro preguntas y sus cuatro respuestas.
 *
 * La rejilla de hallazgos contesta «qué hay que hacer». Esta vista contesta las
 * cuatro que se hacen en la reunión, y que hoy se contestaban sumando a mano:
 *
 * | Pregunta | Corte | Forma |
 * |---|---|---|
 * | ¿En qué se va el dinero? | concepto | **tarta** — es un reparto parte-todo |
 * | ¿Cuándo hay que pagarlo? | horizonte | barras, en orden de plazo |
 * | ¿Qué parte del edificio? | capítulo | barras, de mayor a menor |
 * | ¿Qué edificio? | activo | barras, solo si hay más de uno |
 *
 * ## Por qué solo una es una tarta
 *
 * Una tarta sirve para ver **una proporción de un vistazo** y es mala para
 * comparar dos trozos parecidos: el ojo humano compara longitudes mucho mejor
 * que ángulos. El concepto es un reparto —«esto es normativa, esto es mejora»—
 * y ahí la tarta acierta. Los otros tres son comparaciones de magnitud, y ahí
 * una barra se lee mejor y no obliga a inventar colores.
 *
 * Las barras van todas **del mismo tono**, no de colores distintos. El color
 * distinto se usa para decir «esto es otra cosa», y en una comparación de
 * magnitudes todas las barras son la misma cosa medida en sitios distintos:
 * pintarlas de siete colores añade un significado que no existe.
 *
 * `[REQ]` Ningún gráfico se identifica solo por color. Cada barra lleva su
 * nombre y su cifra escritos, la tarta lleva leyenda con importes y
 * porcentajes, y debajo hay una tabla con los mismos números. Se imprime en
 * blanco y negro en cada reunión, y uno de cada doce hombres es daltónico.
 */

const euros = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

const eurosExactos = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
})

type Datos = {
  concepto: ResumenPorConcepto[]
  horizonte: ResumenPorHorizonte[]
  capitulo: ResumenPorCapitulo[]
  activo: ResumenPorActivo[]
}

export function ResumenCapex({ projectId }: { projectId: string }) {
  const [datos, setDatos] = useState<Datos | null>(null)
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(async () => {
    try {
      const [concepto, horizonte, capitulo, activo] = await Promise.all([
        obtener<ResumenPorConcepto[]>(`/projects/${projectId}/capex/summary/by-concept`),
        obtener<ResumenPorHorizonte[]>(`/projects/${projectId}/capex/summary/by-horizon`),
        obtener<ResumenPorCapitulo[]>(`/projects/${projectId}/capex/summary/by-chapter`),
        obtener<ResumenPorActivo[]>(`/projects/${projectId}/capex/summary/by-asset`),
      ])
      setDatos({ concepto, horizonte, capitulo, activo })
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [projectId])

  useEffect(() => {
    void recargar()
  }, [recargar])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!datos) return <p className="cargando">Cargando el resumen…</p>

  const total = datos.concepto.reduce((s, c) => s + Number(c.amount), 0)
  if (total <= 0) {
    return (
      <Vacio>
        Todavía no hay ninguna línea de CAPEX valorada. Este resumen se rellena solo a medida que
        se registran hallazgos con su importe.
      </Vacio>
    )
  }

  const hallazgos = datos.activo.reduce((s, a) => s + a.findings, 0)
  const lineas = datos.concepto.reduce((s, c) => s + c.lines, 0)
  const conActuaciones = datos.activo.filter((a) => a.findings > 0).length

  // `[REQ]` Cuatro conceptos y el resto agrupado: es lo que la paleta admite
  // medido, no una preferencia. Ver `graficos/paleta.ts`.
  const { propias, resto } = agrupar(datos.concepto, (c) => Number(c.amount))
  const porciones: Porcion[] = [
    ...propias.map((c) => ({
      clave: c.capex_concept_code,
      nombre: c.capex_concept_name,
      valor: Number(c.amount),
    })),
    ...(resto.length > 0
      ? [
          {
            clave: 'OTROS',
            nombre: 'Otros',
            valor: resto.reduce((s, c) => s + Number(c.amount), 0),
            agrupa: resto.length,
          },
        ]
      : []),
  ]

  return (
    <div className="resumen-capex">
      {/* `[REC]` Los titulares primero, y como cifras y no como gráficos. Un
          número solo no es un gráfico de una barra: es un número. */}
      <ul className="cifras-clave">
        <li>
          <span className="valor">{eurosExactos.format(total)}</span>
          <span className="rotulo">CAPEX del encargo</span>
        </li>
        <li>
          <span className="valor">{hallazgos}</span>
          <span className="rotulo">{hallazgos === 1 ? 'hallazgo' : 'hallazgos'}</span>
        </li>
        <li>
          <span className="valor">{lineas}</span>
          <span className="rotulo">
            {lineas === 1 ? 'línea de CAPEX' : 'líneas de CAPEX'}
          </span>
        </li>
        <li>
          <span className="valor">
            {conActuaciones}
            <span className="ayuda"> / {datos.activo.length}</span>
          </span>
          <span className="rotulo">activos con actuaciones</span>
        </li>
      </ul>

      <section className="bloque">
        <h3>En qué se va el dinero</h3>
        <p className="ayuda">
          Por concepto de gasto. Es la distinción que separa un edificio caro de uno mal
          mantenido: <strong>«Normativa» hay que pagarlo y «Mejora» se puede decidir</strong>,
          y en el total valen lo mismo.
        </p>
        <Tarta
          porciones={porciones}
          titulo="Reparto del CAPEX por concepto de gasto"
          formatear={(v) => eurosExactos.format(v)}
        />
        <Tabla
          columna="Concepto"
          filas={datos.concepto.map((c) => ({
            clave: c.capex_concept_code,
            nombre: c.capex_concept_name,
            importe: Number(c.amount),
            detalle: `${c.findings} ${c.findings === 1 ? 'hallazgo' : 'hallazgos'}`,
          }))}
          total={total}
        />
      </section>

      <section className="bloque">
        <h3>Cuándo hay que pagarlo</h3>
        <p className="ayuda">
          En orden de plazo, no de importe: aquí lo que se lee es el perfil temporal del gasto,
          y reordenarlo por cuantía lo destruiría.
        </p>
        <Barras
          filas={datos.horizonte.map((h) => ({
            clave: h.time_horizon_code,
            nombre: h.time_horizon_name,
            importe: Number(h.amount),
            detalle: `${h.lines} ${h.lines === 1 ? 'línea' : 'líneas'}`,
          }))}
        />
      </section>

      <section className="bloque">
        <h3>Qué parte del edificio</h3>
        <p className="ayuda">
          Por capítulo del árbol de CAPEX. Un hallazgo codificado en un objeto suma en su
          capítulo: si no, el reparto saldría partido en trozos que no suman nada reconocible.
        </p>
        <Barras
          filas={datos.capitulo.map((c) => ({
            clave: c.chapter_code,
            nombre: `${c.chapter_code} · ${c.chapter_name}`,
            importe: Number(c.amount),
            detalle: `${c.findings} ${c.findings === 1 ? 'hallazgo' : 'hallazgos'}`,
          }))}
        />
      </section>

      {/* Con un solo activo, un gráfico de una barra es el total otra vez. */}
      {datos.activo.length > 1 && (
        <section className="bloque">
          <h3>Qué edificio</h3>
          <p className="ayuda">
            En un encargo de cartera es el número que entra en la negociación de cada edificio.
            Los activos sin actuaciones salen con cero: un activo que desaparece de la lista se
            confunde con uno que se visitó y no tenía nada.
          </p>
          {/* De mayor a menor: es una comparación de magnitudes y la API los
              devuelve por nombre, que aquí no significa nada. En «cuándo hay
              que pagarlo» es al revés y por eso allí NO se reordena. */}
          <Barras
            filas={[...datos.activo]
              .sort((a, b) => Number(b.amount) - Number(a.amount))
              .map((a) => ({
                clave: a.asset_id,
                nombre: a.asset_name,
                importe: Number(a.amount),
                detalle: `${a.findings} ${a.findings === 1 ? 'hallazgo' : 'hallazgos'}`,
              }))}
          />
        </section>
      )}
    </div>
  )
}

type Fila = { clave: string; nombre: string; importe: number; detalle: string }

/**
 * Barras horizontales de un solo tono.
 *
 * `[REQ]` La escala la marca **la barra más larga**, no el total del encargo:
 * con el total, un reparto dominado por una categoría deja las demás como
 * rayas invisibles y el gráfico deja de decir nada de ellas.
 */
function Barras({ filas }: { filas: Fila[] }) {
  const mayor = Math.max(...filas.map((f) => f.importe), 1)
  return (
    <ul className="barras">
      {filas.map((f) => (
        <li key={f.clave}>
          <span className="etiqueta">{f.nombre}</span>
          <span className="barra" aria-hidden="true">
            {/* `[REQ]` Cero no pinta nada. El estilo compartido da un mínimo de
                2 px para que un importe pequeño no se confunda con «nada»; con
                un cero hace lo contrario y convierte «nada» en «poco». Los dos
                casos existen —un plazo sin actuaciones y un plazo con una
                actuación barata— y tienen que verse distintos. */}
            {f.importe > 0 && (
              <span className="relleno" style={{ width: `${(f.importe / mayor) * 100}%` }} />
            )}
          </span>
          <span className="cifra">{f.detalle}</span>
          <span className="cifra importe">{euros.format(f.importe)}</span>
        </li>
      ))}
    </ul>
  )
}

/**
 * Los mismos números de la tarta, en tabla.
 *
 * No es una redundancia: la guía de visualización obliga a una vista en tabla
 * cuando algún tono no llega a 3:1 de contraste contra el fondo, y aquí el agua
 * se queda en 2,74:1. Además es lo que permite leer los conceptos que la tarta
 * agrupa en «Otros», y copiar una cifra exacta.
 */
function Tabla({
  columna,
  filas,
  total,
}: {
  columna: string
  filas: Fila[]
  total: number
}) {
  return (
    <details className="detalle-tabla">
      <summary>Ver los {filas.length} conceptos en tabla</summary>
      <div className="desbordable">
        <table className="tabla">
          <thead>
            <tr>
              <th scope="col">{columna}</th>
              <th scope="col">Hallazgos</th>
              <th scope="col" className="numerica">
                Importe
              </th>
              <th scope="col" className="numerica">
                % del total
              </th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => (
              <tr key={f.clave}>
                <th scope="row">{f.nombre}</th>
                <td>{f.detalle}</td>
                <td className="numerica">{eurosExactos.format(f.importe)}</td>
                <td className="numerica">{((f.importe / total) * 100).toFixed(1)} %</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td>Total</td>
              <td />
              <td className="numerica">{eurosExactos.format(total)}</td>
              <td className="numerica">100,0 %</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </details>
  )
}

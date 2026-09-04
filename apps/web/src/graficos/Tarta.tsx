import { useId, useState } from 'react'
import { porcentaje } from './formato'
import { colorDePorcion } from './paleta'

/**
 * Un gráfico de tarta para un reparto parte-todo.
 *
 * Se usa **solo** donde la pregunta es «de qué se compone el total», y con
 * cinco porciones como mucho. Comparar dos porciones parecidas en una tarta es
 * difícil para cualquiera: para eso están las barras y la tabla, que van al
 * lado. Aquí lo que se lee de un vistazo es la proporción, no el orden.
 *
 * `[REQ]` **El color no informa por sí solo.** Cada porción sale además con su
 * nombre, su importe y su porcentaje escritos en la leyenda, y la misma
 * información está en una tabla debajo. Es lo que hace que la pantalla siga
 * sirviendo impresa en blanco y negro —cosa que pasa en cada reunión— y para
 * quien no distingue el verde del naranja.
 */

export type Porcion = {
  /** La clave estable. El color sigue a la categoría, no a su puesto. */
  clave: string
  nombre: string
  valor: number
  /** Cuántas categorías van dentro, si es la porción agrupada. */
  agrupa?: number
}

/** Radio del círculo en el sistema de coordenadas del SVG. */
const RADIO = 100

/**
 * Separación entre porciones, en grados.
 *
 * La guía pide un hueco del color del fondo entre rellenos contiguos: sin él,
 * dos porciones de tonos parecidos se leen como una sola. En grados y no en
 * píxeles porque el SVG se escala, y un hueco en píxeles se estrecharía al
 * agrandar el gráfico justo cuando más se nota.
 */
const HUECO = 1.2

function punto(grados: number): [number, number] {
  // −90 para que la primera porción empiece arriba: es donde el ojo empieza a
  // leer un reloj, y de un reparto se lee primero la mayor.
  const radianes = ((grados - 90) * Math.PI) / 180
  return [RADIO * Math.cos(radianes), RADIO * Math.sin(radianes)]
}

function sector(desde: number, hasta: number): string {
  const barrido = hasta - desde
  // Una porción de más de media vuelta necesita el indicador de arco largo, o
  // el navegador dibuja el complementario: una porción del 70 % saldría del
  // 30 %. Es el fallo clásico de una tarta hecha a mano.
  const arcoLargo = barrido > 180 ? 1 : 0
  const [x1, y1] = punto(desde)
  const [x2, y2] = punto(hasta)
  return `M 0 0 L ${x1} ${y1} A ${RADIO} ${RADIO} 0 ${arcoLargo} 1 ${x2} ${y2} Z`
}

export function Tarta({
  porciones,
  titulo,
  formatear,
}: {
  porciones: Porcion[]
  /** Describe el gráfico para quien lo lee con un lector de pantalla. */
  titulo: string
  formatear: (valor: number) => string
}) {
  const [encima, setEncima] = useState<string | null>(null)
  const idTitulo = useId()

  const total = porciones.reduce((suma, p) => suma + p.valor, 0)
  if (total <= 0) return null

  let acumulado = 0
  const trozos = porciones.map((p, i) => {
    const desde = acumulado
    const barrido = (p.valor / total) * 360
    acumulado += barrido
    return {
      ...p,
      desde,
      hasta: desde + barrido,
      parte: porcentaje(p.valor, total),
      color: colorDePorcion(i, p.agrupa !== undefined),
    }
  })

  return (
    <div className="tarta">
      <svg
        viewBox="-110 -110 220 220"
        role="img"
        aria-labelledby={idTitulo}
        className="lienzo"
      >
        <title id={idTitulo}>{titulo}</title>
        {trozos.map((t) => {
          // Una porción tan fina que el hueco se la comería se dibuja entera:
          // más vale una raya sin separar que una porción que desaparece.
          const cabeHueco = t.hasta - t.desde > HUECO * 3
          return (
            <path
              key={t.clave}
              d={sector(t.desde + (cabeHueco ? HUECO / 2 : 0), t.hasta - (cabeHueco ? HUECO / 2 : 0))}
              fill={t.color}
              className={encima && encima !== t.clave ? 'apagada' : ''}
              onMouseEnter={() => setEncima(t.clave)}
              onMouseLeave={() => setEncima(null)}
            >
              {/* El navegador lo enseña al pasar por encima. No sustituye a la
                  leyenda: la complementa para quien usa ratón. */}
              <title>
                {t.nombre}: {formatear(t.valor)} ({t.parte})
              </title>
            </path>
          )
        })}
      </svg>

      {/* `[REQ]` La leyenda no es opcional ni decorativa: es donde vive la
          identidad de cada porción. Lleva el nombre, el importe y el
          porcentaje, así que la tarta se puede leer entera sin distinguir un
          solo color. */}
      <ul className="leyenda">
        {trozos.map((t) => (
          <li
            key={t.clave}
            className={encima && encima !== t.clave ? 'apagada' : ''}
            onMouseEnter={() => setEncima(t.clave)}
            onMouseLeave={() => setEncima(null)}
          >
            <span className="marca" style={{ background: t.color }} aria-hidden="true" />
            <span className="nombre">
              {t.nombre}
              {t.agrupa !== undefined && (
                <span className="ayuda"> · {t.agrupa} conceptos</span>
              )}
            </span>
            <span className="porcentaje">{t.parte}</span>
            <span className="importe">{formatear(t.valor)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

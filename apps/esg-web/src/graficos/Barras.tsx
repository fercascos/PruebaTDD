/**
 * Serie mensual de UN vector.
 *
 * Un gráfico por vector, y no todos juntos: el agua se mide en m³ y la
 * electricidad en kWh. Ponerlos en el mismo eje —o peor, en dos ejes— es
 * comparar cosas que no se comparan, y lo que se lee es la escala, no el
 * consumo. Cuatro paneles pequeños, cada uno con su unidad, dicen lo que hay.
 */
import { useState } from 'react'

import { cantidad, mesCorto, mesLargo } from './formato'

export interface Barra {
  mes: string
  valor: number
}

interface Props {
  barras: Barra[]
  color: string
  unidad: string
  titulo: string
}

const ALTO = 150
const HUECO = 2 // el separador de 2 px entre barras contiguas

export function Barras({ barras, color, unidad, titulo }: Props) {
  const [encima, setEncima] = useState<number | null>(null)
  if (barras.length === 0) return <p className="vacio">Sin datos en el periodo.</p>

  const maximo = Math.max(...barras.map((b) => b.valor), 1)
  const ancho = 100 / barras.length

  return (
    <figure className="grafico">
      <figcaption>
        {titulo} <span className="unidad">{unidad}</span>
      </figcaption>
      <div className="lienzo">
        <svg
          viewBox={`0 0 100 ${ALTO}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`${titulo} por mes, en ${unidad}`}
        >
          {barras.map((b, i) => {
            const alto = (b.valor / maximo) * (ALTO - 12)
            return (
              <rect
                key={b.mes}
                x={i * ancho + HUECO / 2}
                y={ALTO - alto}
                width={ancho - HUECO}
                height={Math.max(alto, 1)}
                rx={1}
                fill={color}
                opacity={encima === null || encima === i ? 1 : 0.45}
                onMouseEnter={() => setEncima(i)}
                onMouseLeave={() => setEncima(null)}
              />
            )
          })}
        </svg>
        {encima !== null && (
          <div className="soplo" style={{ left: `${(encima + 0.5) * ancho}%` }}>
            <strong>{cantidad(barras[encima].valor)}</strong> {unidad}
            <br />
            <span>{mesLargo(barras[encima].mes)}</span>
          </div>
        )}
      </div>
      {/* El eje son los meses, y solo se etiquetan los que caben: con doce
          barras y una etiqueta en cada una, no se lee ninguna. */}
      <div className="eje">
        {barras.map((b, i) => (
          <span key={b.mes} className={i % Math.ceil(barras.length / 6) ? 'oculto' : ''}>
            {mesCorto(b.mes)}
          </span>
        ))}
      </div>
    </figure>
  )
}

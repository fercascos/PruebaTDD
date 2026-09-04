/**
 * Reparto de UN vector entre los activos.
 *
 * No hay ninguna tarta que mezcle vectores: sumar kWh con m³ y con kg da un
 * número que no existe. Lo que sí tiene sentido es «de los 340.000 kWh de la
 * cartera, cuánto es de cada edificio», que es esta.
 *
 * Cada porción lleva su etiqueta al lado: en modo claro dos de los cuatro tonos
 * no llegan a 3:1 contra el fondo, así que el color no puede ser lo único que
 * distinga una porción de otra.
 */
import { useState } from 'react'

import { cantidad } from './formato'

export interface Porcion {
  etiqueta: string
  valor: number
}

interface Props {
  porciones: Porcion[]
  color: string
  unidad: string
  titulo: string
}

const RADIO = 42
const GROSOR = 16

export function Donut({ porciones, color, unidad, titulo }: Props) {
  const [encima, setEncima] = useState<number | null>(null)
  const total = porciones.reduce((s, p) => s + p.valor, 0)
  if (total <= 0) return <p className="vacio">Sin datos en el periodo.</p>

  // Con muchos activos, las porciones se vuelven líneas: se enseñan los seis
  // mayores y el resto va a «Otros». Un anillo de treinta porciones no se lee.
  const ordenadas = [...porciones].sort((a, b) => b.valor - a.valor)
  const visibles = ordenadas.slice(0, 6)
  const resto = ordenadas.slice(6).reduce((s, p) => s + p.valor, 0)
  const lista = resto > 0 ? [...visibles, { etiqueta: 'Otros', valor: resto }] : visibles

  let acumulado = 0
  const arcos = lista.map((p, i) => {
    const desde = (acumulado / total) * 360
    acumulado += p.valor
    const hasta = (acumulado / total) * 360
    return { ...p, desde, hasta, indice: i }
  })

  return (
    <figure className="grafico donut">
      <figcaption>
        {titulo} <span className="unidad">{unidad}</span>
      </figcaption>
      <div className="donut-cuerpo">
        <svg viewBox="0 0 100 100" role="img" aria-label={`${titulo}, reparto por activo`}>
          {arcos.map((a) => (
            <path
              key={a.etiqueta}
              d={sector(a.desde, a.hasta)}
              fill={color}
              // La identidad de cada porción la da la etiqueta; el degradado de
              // opacidad solo ayuda a seguirla con la vista.
              opacity={1 - a.indice * 0.13}
              stroke="var(--fondo)"
              strokeWidth={2}
              onMouseEnter={() => setEncima(a.indice)}
              onMouseLeave={() => setEncima(null)}
            />
          ))}
        </svg>
        <ul className="leyenda">
          {arcos.map((a) => (
            <li key={a.etiqueta} className={encima === a.indice ? 'destacada' : ''}>
              <span className="muestra" style={{ background: color, opacity: 1 - a.indice * 0.13 }} />
              <span className="nombre">{a.etiqueta}</span>
              <span className="valor">
                {cantidad(a.valor)} <em>{Math.round((a.valor / total) * 100)} %</em>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </figure>
  )
}

function sector(desde: number, hasta: number): string {
  const externo = RADIO
  const interno = RADIO - GROSOR
  const a1 = polar(externo, desde)
  const a2 = polar(externo, hasta)
  const b1 = polar(interno, hasta)
  const b2 = polar(interno, desde)
  const largo = hasta - desde > 180 ? 1 : 0
  return [
    `M ${a1.x} ${a1.y}`,
    `A ${externo} ${externo} 0 ${largo} 1 ${a2.x} ${a2.y}`,
    `L ${b1.x} ${b1.y}`,
    `A ${interno} ${interno} 0 ${largo} 0 ${b2.x} ${b2.y}`,
    'Z',
  ].join(' ')
}

function polar(radio: number, grados: number) {
  const radianes = ((grados - 90) * Math.PI) / 180
  return { x: 50 + radio * Math.cos(radianes), y: 50 + radio * Math.sin(radianes) }
}

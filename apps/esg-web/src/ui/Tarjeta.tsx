/**
 * La tarjeta de un vector: consumo del periodo, variación y cobertura.
 *
 * La cobertura va en la misma tarjeta que el número, y no escondida en una
 * pestaña de calidad del dato. Un consumo con el 40 % de cobertura no es un
 * consumo bajo: es un consumo que falta, y quien lea la cifra tiene que verlo
 * sin buscarlo.
 */
import type { Total } from '../api/tipos'
import { cantidad, porcentaje } from '../graficos/formato'
import { COLOR, ETIQUETA, UNIDAD } from '../graficos/paleta'
import type { Vector } from '../graficos/paleta'

export function Tarjeta({ total }: { total: Total }) {
  // La unidad se escribe aquí, no se copia de la API: allí es `m3`, que es
  // como se guarda y como viaja, y en pantalla se lee «m³».
  const unidad = UNIDAD[total.vector as Vector]
  const cobertura = total.cobertura.porcentaje ? Number(total.cobertura.porcentaje) : null
  const variacion = total.variacion_porcentual ? Number(total.variacion_porcentual) : null
  const floja = cobertura !== null && cobertura < 90

  return (
    <article className="tarjeta">
      <header>
        <span className="marca" style={{ background: COLOR[total.vector as Vector] }} />
        {ETIQUETA[total.vector as Vector]}
      </header>
      <p className="cifra">
        {cantidad(total.medido)} <span className="unidad">{unidad}</span>
      </p>
      <p className="linea">
        {variacion === null ? (
          <span className="apagado">Sin periodo anterior con el que comparar</span>
        ) : (
          <span className={variacion > 0 ? 'sube' : 'baja'}>
            {porcentaje(variacion)} frente al periodo anterior
          </span>
        )}
      </p>
      <p className={`linea cobertura ${floja ? 'aviso' : ''}`}>
        Cobertura {cobertura === null ? '—' : `${cobertura} %`}
        <span className="apagado">
          {' '}
          ({total.cobertura.dias_con_dato} de {total.cobertura.dias_esperados} días)
        </span>
      </p>
      {Number(total.estimado) > 0 && (
        <p className="linea apagado">
          Además, {cantidad(total.estimado)} {unidad} estimados, fuera del total
        </p>
      )}
      {total.cobertura.lecturas_sin_normalizar > 0 && (
        <p className="linea aviso">
          {total.cobertura.lecturas_sin_normalizar} lectura(s) sin convertir: no suman
        </p>
      )}
    </article>
  )
}

import { useState } from 'react'
import { enviar } from '../api/cliente'
import { Campo, Rejilla } from '../ui/Formulario'
import { Mensaje } from '../ui/Marco'

/**
 * La cascada de CAPEX, con la fórmula a la vista `[REQ]` P-16.
 *
 * > *«No ocultes las fórmulas.»*
 *
 * El endpoint `POST /capex/preview-calculation` existía y estaba probado desde
 * el principio, pero **ninguna pantalla lo llamaba**: el requisito de enseñar
 * el cálculo estaba construido y era invisible. Cada peldaño sale con su base y
 * su porcentaje, no solo con el resultado, para que el consultor pueda
 * comprobar de dónde viene cada euro delante del cliente.
 *
 * Dos cosas que no hace, y son deliberadas:
 *
 * * **No guarda nada.** El cálculo es una función pura expuesta por HTTP; se
 *   puede jugar con los porcentajes sin consecuencias.
 * * **No sustituye el importe por su cuenta.** `[REQ]` P-05b · Aplicarlo es un
 *   clic aparte. Quien tecleó el importe puede tener un presupuesto real
 *   delante, y la fórmula no sabe nada de eso.
 *
 * `[SUP]` Los porcentajes de partida son los de la convención española que usa
 * el ejemplo de `docs/11-capex-precios.md`. **Son editables**: P-06 quedó sin
 * fuente de precios externa y el acuerdo fue que cada uno ajuste esta parte a
 * mano hasta que la haya.
 */

const POR_DEFECTO = {
  indirect_pct: '0.08',
  overhead_pct: '0.13',
  profit_pct: '0.06',
  fees_pct: '0.06',
  contingency_pct: '0.10',
}

const ETIQUETAS: Record<string, string> = {
  indirect_pct: 'Costes indirectos',
  overhead_pct: 'Gastos generales (GG)',
  profit_pct: 'Beneficio industrial (BI)',
  fees_pct: 'Honorarios técnicos',
  contingency_pct: 'Contingencia',
}

type Peldano = {
  key: string
  label: string
  base_amount: string
  pct: string
  amount: string
}

type Resultado = {
  direct_cost: string
  steps: Peldano[]
  pem: string | null
  pec: string | null
  computed_base: string
  tax_amount: string
  total_with_tax: string
  nota: string
}

const euros = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' })
const porciento = new Intl.NumberFormat('es-ES', { style: 'percent', maximumFractionDigits: 2 })

export function Calculadora({ alAplicar }: { alAplicar: (base: string) => void }) {
  const [abierta, setAbierta] = useState(false)
  const [cantidad, setCantidad] = useState('1')
  const [precio, setPrecio] = useState('')
  const [impuesto, setImpuesto] = useState('0.21')
  const [pcts, setPcts] = useState(POR_DEFECTO)
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function calcular() {
    setError(null)
    try {
      setResultado(
        await enviar<Resultado>('/capex/preview-calculation', {
          quantity: cantidad || '0',
          unit_price: precio || '0',
          percentages: pcts,
          tax_pct: impuesto || '0',
        }),
      )
    } catch (e) {
      setError((e as Error).message)
    }
  }

  if (!abierta) {
    return (
      <button type="button" className="enlace" onClick={() => setAbierta(true)}>
        Cómo se calcula · abrir la cascada
      </button>
    )
  }

  return (
    <div className="calculadora">
      <div className="cabecera">
        <h4>Cómo se calcula</h4>
        <button type="button" className="enlace" onClick={() => setAbierta(false)}>
          Cerrar
        </button>
      </div>

      <Rejilla>
        <Campo etiqueta="Medición">
          <input
            type="number"
            step="0.01"
            min={0}
            value={cantidad}
            onChange={(e) => setCantidad(e.target.value)}
          />
        </Campo>
        <Campo etiqueta="Precio unitario (€)">
          <input
            type="number"
            step="0.01"
            min={0}
            value={precio}
            onChange={(e) => setPrecio(e.target.value)}
          />
        </Campo>
        <Campo etiqueta="Impuesto" ayuda="Fracción: 0,21 para el 21 %">
          <input
            type="number"
            step="0.01"
            min={0}
            max={1}
            value={impuesto}
            onChange={(e) => setImpuesto(e.target.value)}
          />
        </Campo>
      </Rejilla>

      <p className="ayuda">
        `[SUP]` Porcentajes de la convención española. <strong>Editables</strong>: P-06 quedó sin
        fuente de precios externa y el acuerdo fue ajustar esta parte a mano hasta que la haya.
      </p>
      <Rejilla>
        {Object.entries(pcts).map(([clave, valor]) => (
          <Campo key={clave} etiqueta={ETIQUETAS[clave] ?? clave}>
            <input
              type="number"
              step="0.01"
              min={0}
              value={valor}
              onChange={(e) => setPcts((previos) => ({ ...previos, [clave]: e.target.value }))}
            />
          </Campo>
        ))}
      </Rejilla>

      <button type="button" onClick={() => void calcular()}>
        Calcular
      </button>
      {error && <Mensaje tipo="error">{error}</Mensaje>}

      {resultado && (
        <>
          <table className="tabla cascada">
            <thead>
              <tr>
                <th>Concepto</th>
                <th className="numerica">Sobre</th>
                <th className="numerica">%</th>
                <th className="numerica">Importe</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Coste directo</td>
                <td className="numerica">—</td>
                <td className="numerica">—</td>
                <td className="numerica">{euros.format(Number(resultado.direct_cost))}</td>
              </tr>
              {resultado.steps.map((p) => (
                <tr key={p.key}>
                  <td>{p.label}</td>
                  {/* La base de cada peldaño, no solo el resultado: es lo que
                      permite comprobar que GG y BI van sobre el PEM y los
                      honorarios sobre el PEC, y no todos sobre el directo. */}
                  <td className="numerica">{euros.format(Number(p.base_amount))}</td>
                  <td className="numerica">{porciento.format(Number(p.pct))}</td>
                  <td className="numerica">{euros.format(Number(p.amount))}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              {resultado.pem && (
                <tr>
                  <td colSpan={3}>PEM · directo + indirectos</td>
                  <td className="numerica">{euros.format(Number(resultado.pem))}</td>
                </tr>
              )}
              {resultado.pec && (
                <tr>
                  <td colSpan={3}>PEC · PEM + GG + BI</td>
                  <td className="numerica">{euros.format(Number(resultado.pec))}</td>
                </tr>
              )}
              <tr>
                <td colSpan={3}>
                  <strong>Base imponible</strong>
                </td>
                <td className="numerica">
                  <strong>{euros.format(Number(resultado.computed_base))}</strong>
                </td>
              </tr>
              <tr>
                <td colSpan={3}>Impuesto</td>
                <td className="numerica">{euros.format(Number(resultado.tax_amount))}</td>
              </tr>
              <tr>
                <td colSpan={3}>Total con impuesto</td>
                <td className="numerica">{euros.format(Number(resultado.total_with_tax))}</td>
              </tr>
            </tfoot>
          </table>

          <p className="ayuda">{resultado.nota}</p>
          {/* `[REQ]` P-05b · Aplicarlo es un clic aparte, y solo rellena el
              campo: sigue haciendo falta guardar la línea. */}
          <button
            type="button"
            className="secundario"
            onClick={() => alAplicar(resultado.computed_base)}
          >
            Usar la base imponible como importe
          </button>
        </>
      )}
    </div>
  )
}

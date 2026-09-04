/**
 * Carga de un fichero de consumos.
 *
 * El orden de la pantalla es el del trabajo: elegir fichero → ver qué columna
 * ha entendido que es qué → **simular** → leer las incidencias → aplicar. El
 * botón de aplicar no aparece hasta que hay una simulación: aplicar a ciegas un
 * Excel de mil filas es lo que produce las cargas duplicadas que luego hay que
 * deshacer a mano.
 */
import { useState } from 'react'

import { ErrorDeApi, pedir } from '../api/cliente'
import type { ResultadoDeCarga } from '../api/tipos'
import { VECTORES } from '../graficos/paleta'

const CAMPOS: Record<string, string> = {
  suministro: 'Suministro (CUPS/contador)',
  vector: 'Vector',
  inicio: 'Inicio del periodo',
  fin: 'Fin del periodo',
  cantidad: 'Cantidad',
  unidad: 'Unidad',
  calidad: 'Calidad (medido/estimado)',
  activo: 'Activo',
  importe: 'Importe',
  moneda: 'Moneda',
  factor_gas: 'Poder calorífico (gas)',
  fraccion: 'Fracción de residuo',
  referencia: 'Nº de factura',
}

export function Cargar() {
  const [fichero, setFichero] = useState<File | null>(null)
  const [vectorPorDefecto, setVectorPorDefecto] = useState('')
  const [resultado, setResultado] = useState<ResultadoDeCarga | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [trabajando, setTrabajando] = useState(false)

  async function enviar(aplicar: boolean) {
    if (!fichero) return
    setTrabajando(true)
    setError(null)
    const formulario = new FormData()
    formulario.append('fichero', fichero)
    formulario.append('aplicar', String(aplicar))
    if (vectorPorDefecto) formulario.append('vector_por_defecto', vectorPorDefecto)
    try {
      setResultado(
        await pedir<ResultadoDeCarga>('/api/v1/cargas', { method: 'POST', body: formulario }),
      )
    } catch (e) {
      setError(e instanceof ErrorDeApi ? e.message : 'No se pudo procesar el fichero')
    } finally {
      setTrabajando(false)
    }
  }

  const simulada = resultado && !resultado.aplicada

  return (
    <section className="cargar">
      <h2>Cargar consumos desde un fichero</h2>
      <p className="apagado">
        CSV o Excel. La fecha de fin se entiende <strong>inclusiva</strong> («del 1 al 31 de
        marzo»), como en una factura: por dentro se guarda el día siguiente, para que dos meses
        seguidos no se solapen.
      </p>

      <div className="formulario">
        <label>
          Fichero
          <input
            type="file"
            accept=".csv,.xlsx,.xlsm,.txt"
            onChange={(e) => {
              setFichero(e.target.files?.[0] ?? null)
              setResultado(null)
            }}
          />
        </label>
        <label>
          Vector, si el fichero no trae columna
          <select
            value={vectorPorDefecto}
            onChange={(e) => setVectorPorDefecto(e.target.value)}
          >
            <option value="">— lo trae el fichero —</option>
            {VECTORES.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <div className="botones">
          <button type="button" disabled={!fichero || trabajando} onClick={() => enviar(false)}>
            Simular
          </button>
          <button
            type="button"
            className="principal"
            disabled={!simulada || trabajando}
            onClick={() => enviar(true)}
            title={simulada ? '' : 'Primero simule la carga'}
          >
            Aplicar
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {resultado && (
        <div className="resultado">
          <h3>
            {resultado.aplicada ? 'Carga aplicada' : 'Simulación'} · {resultado.filas_totales}{' '}
            filas
          </h3>
          {resultado.ya_cargado_antes && (
            <p className="aviso">
              Este mismo fichero ya se aplicó antes (coincide su huella). Si lo aplica otra vez,
              los periodos repetidos los rechazará la base de datos.
            </p>
          )}
          <ul className="recuento">
            <li>
              <strong>{resultado.filas_aceptadas}</strong> aceptadas
            </li>
            <li>
              <strong>{resultado.filas_rechazadas}</strong> rechazadas
            </li>
            {resultado.filas_sin_normalizar > 0 && (
              <li className="aviso">
                <strong>{resultado.filas_sin_normalizar}</strong> guardadas sin poder convertir
              </li>
            )}
          </ul>

          {resultado.mapeo && (
            <details open={resultado.mapeo.faltan.length > 0}>
              <summary>Columnas emparejadas</summary>
              <ul className="mapeo">
                {Object.entries(resultado.mapeo.columnas).map(([campo, columna]) => (
                  <li key={campo}>
                    <span className="campo">{CAMPOS[campo] ?? campo}</span>
                    <span className="columna">{columna}</span>
                  </li>
                ))}
                {resultado.mapeo.faltan.map((campo) => (
                  <li key={campo} className="falta">
                    <span className="campo">{CAMPOS[campo] ?? campo}</span>
                    <span className="columna">sin emparejar</span>
                  </li>
                ))}
              </ul>
            </details>
          )}

          {resultado.incidencias.length > 0 && (
            <table className="incidencias">
              <caption>Incidencias · la fila es la del fichero, con su cabecera contada</caption>
              <thead>
                <tr>
                  <th>Fila</th>
                  <th>Columna</th>
                  <th>Qué pasa</th>
                  <th>Valor</th>
                </tr>
              </thead>
              <tbody>
                {resultado.incidencias.slice(0, 200).map((i, n) => (
                  <tr key={n}>
                    <td>{i.fila ?? '—'}</td>
                    <td>{i.columna ?? '—'}</td>
                    <td>{i.mensaje}</td>
                    <td className="valor">{i.valor ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  )
}

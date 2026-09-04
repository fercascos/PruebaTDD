/**
 * Cola de revisión de lo que ha leído la IA.
 *
 * Lo que está aquí **no suma en ningún panel**. Esa es la promesa: la IA
 * acierta mucho, pero una factura mal leída no se distingue de una buena una
 * vez está dentro de la suma, así que lo dudoso espera a que una persona lo
 * mire.
 */
import { useCallback, useEffect, useState } from 'react'

import { pedir } from '../api/cliente'
import type { LecturaPendiente, ResultadoImportacion } from '../api/tipos'
import { cantidad } from '../graficos/formato'
import { ETIQUETA } from '../graficos/paleta'
import { ultimosMeses } from '../ui/Filtros'

export function Revision({ puedeEscribir }: { puedeEscribir: boolean }) {
  const [pendientes, setPendientes] = useState<LecturaPendiente[]>([])
  const [importacion, setImportacion] = useState<ResultadoImportacion | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [periodo, setPeriodo] = useState(ultimosMeses(3))

  const cargar = useCallback(async () => {
    setPendientes(await pedir<LecturaPendiente[]>('/api/v1/lecturas/pendientes'))
  }, [])

  useEffect(() => {
    void cargar()
  }, [cargar])

  async function importar() {
    setError(null)
    try {
      setImportacion(
        await pedir<ResultadoImportacion>(
          `/api/v1/conector/importar?desde=${periodo.desde}&hasta=${periodo.hasta}`,
          { method: 'POST' },
        ),
      )
      await cargar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo importar')
    }
  }

  async function resolver(id: string, estado: 'CONFIRMADA' | 'DESCARTADA') {
    await pedir(`/api/v1/lecturas/${id}/resolver`, {
      method: 'POST',
      body: JSON.stringify({ estado }),
    })
    await cargar()
  }

  return (
    <section className="revision">
      <h2>Facturas leídas por IA</h2>
      <div className="formulario">
        <label>
          Desde
          <input
            type="date"
            value={periodo.desde}
            onChange={(e) => setPeriodo({ ...periodo, desde: e.target.value })}
          />
        </label>
        <label>
          Hasta (excl.)
          <input
            type="date"
            value={periodo.hasta}
            onChange={(e) => setPeriodo({ ...periodo, hasta: e.target.value })}
          />
        </label>
        <button type="button" onClick={importar} disabled={!puedeEscribir}>
          Importar del lector
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {importacion && (
        <p className="recuento-linea">
          {importacion.facturas_leidas} leídas · {importacion.confirmadas} confirmadas ·{' '}
          {importacion.pendientes_de_revision} a revisar · {importacion.rechazadas} rechazadas
        </p>
      )}

      {pendientes.length === 0 ? (
        <p className="vacio">No hay nada esperando revisión.</p>
      ) : (
        <table className="pendientes">
          <caption>Estas lecturas no suman en ningún panel hasta que se confirmen</caption>
          <thead>
            <tr>
              <th>Activo</th>
              <th>Suministro</th>
              <th>Vector</th>
              <th>Periodo</th>
              <th>Cantidad</th>
              <th>Confianza</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {pendientes.map((p) => (
              <tr key={p.id}>
                <td>{p.activo}</td>
                <td className="codigo">{p.suministro}</td>
                <td>{ETIQUETA[p.vector]}</td>
                <td>
                  {p.inicio} → {p.fin}
                </td>
                <td>
                  {cantidad(p.cantidad)} {p.unidad}
                </td>
                <td className={Number(p.confianza) < 0.6 ? 'aviso' : ''}>
                  {p.confianza ? `${Math.round(Number(p.confianza) * 100)} %` : '—'}
                </td>
                <td className="acciones">
                  <button
                    type="button"
                    disabled={!puedeEscribir}
                    onClick={() => resolver(p.id, 'CONFIRMADA')}
                  >
                    Confirmar
                  </button>
                  <button
                    type="button"
                    disabled={!puedeEscribir}
                    onClick={() => resolver(p.id, 'DESCARTADA')}
                  >
                    Descartar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

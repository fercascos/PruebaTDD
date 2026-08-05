import { useState } from 'react'
import { enviar } from '../api/cliente'

type Cambio = {
  photo_id: string
  antes: string
  despues: string
  cambia: boolean
  omitidos: string[]
}

type Plan = {
  dry_run: boolean
  cambios: Cambio[]
  colisiones_resueltas: string[]
  aplicados: number
  fallidos: { photo_id: string; motivo: string }[]
}

const PLANTILLA_POR_DEFECTO = '[Proyecto]_[Activo]_[Sistema]_[Zona]_[Numero]'

/**
 * Renombrado en lote con **previsualización obligatoria** `[REQ]` §15.4.
 *
 * Es la operación con más capacidad de destrozo de todo el bloque: cuatrocientos
 * nombres cambiados a la vez y ninguna forma cómoda de recordar cómo se
 * llamaban. Por eso el botón de aplicar **no existe** hasta que se ha visto la
 * tabla antes/después, y el servidor tiene `dry_run: true` por defecto para
 * que ni siquiera un cliente mal escrito pueda saltárselo.
 */
export function RenombradoEnLote({
  photoIds,
  alAplicar,
}: {
  photoIds: string[]
  alAplicar: () => void
}) {
  const [abierto, setAbierto] = useState(false)
  const [plantilla, setPlantilla] = useState(PLANTILLA_POR_DEFECTO)
  const [numerar, setNumerar] = useState(true)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [trabajando, setTrabajando] = useState(false)

  async function previsualizar() {
    setTrabajando(true)
    try {
      setPlan(
        await enviar<Plan>('/photos/bulk-rename', {
          photo_ids: photoIds,
          template: plantilla,
          dry_run: true,
          numerar_desde: numerar ? 1 : null,
        }),
      )
    } finally {
      setTrabajando(false)
    }
  }

  async function aplicar() {
    setTrabajando(true)
    try {
      const resultado = await enviar<Plan>('/photos/bulk-rename', {
        photo_ids: photoIds,
        template: plantilla,
        dry_run: false,
        numerar_desde: numerar ? 1 : null,
      })
      setPlan(resultado)
      alAplicar()
    } finally {
      setTrabajando(false)
    }
  }

  if (!abierto) {
    return (
      <button type="button" className="secundario" onClick={() => setAbierto(true)}>
        Renombrar en lote…
      </button>
    )
  }

  const cambian = plan?.cambios.filter((c) => c.cambia) ?? []

  return (
    <div className="dialogo">
      <h3>Renombrar {photoIds.length} fotografías</h3>

      <label>
        Plantilla
        <input value={plantilla} onChange={(e) => setPlantilla(e.target.value)} />
      </label>
      <p className="ayuda">
        Marcadores disponibles: [Proyecto] [ProyectoNombre] [Activo] [Sistema] [Zona] [Espacio]
        [Capitulo] [Categoria] [Fecha] [Hora] [Numero] [Autor] [Etiqueta]. La extensión no forma
        parte de la plantilla: la fija el servidor desde el tipo real del archivo.
      </p>

      <label className="casilla">
        <input type="checkbox" checked={numerar} onChange={(e) => setNumerar(e.target.checked)} />
        Numerar correlativamente desde 001
      </label>

      <div className="acciones">
        <button type="button" onClick={() => void previsualizar()} disabled={trabajando}>
          Previsualizar
        </button>
        <button
          type="button"
          className="peligro"
          onClick={() => void aplicar()}
          // Sin haber visto la tabla no hay botón: la previsualización es
          // obligatoria y no es un consejo.
          disabled={trabajando || plan === null || cambian.length === 0}
        >
          Aplicar a {cambian.length}
        </button>
        <button type="button" className="secundario" onClick={() => setAbierto(false)}>
          Cerrar
        </button>
      </div>

      {plan && (
        <>
          {plan.colisiones_resueltas.length > 0 && (
            <p className="mensaje aviso">
              {plan.colisiones_resueltas.length} nombres coincidían y han recibido un sufijo
              alfabético (_b, _c…) para no pisarse.
            </p>
          )}
          {plan.aplicados > 0 && (
            <p className="mensaje ok">
              {plan.aplicados} renombradas
              {plan.fallidos.length > 0 && ` · ${plan.fallidos.length} fallidas`}
            </p>
          )}
          <table className="tabla compacta">
            <thead>
              <tr>
                <th>Antes</th>
                <th>Después</th>
              </tr>
            </thead>
            <tbody>
              {plan.cambios.map((c) => (
                <tr key={c.photo_id} className={c.cambia ? '' : 'sin-cambio'}>
                  <td>{c.antes}</td>
                  <td>
                    {c.despues}
                    {c.omitidos.length > 0 && (
                      <em className="ayuda"> · sin valor: {c.omitidos.join(' ')}</em>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}

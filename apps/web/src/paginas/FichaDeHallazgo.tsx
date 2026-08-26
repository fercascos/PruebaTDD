import { useCallback, useEffect, useRef, useState } from 'react'
import { borrar, enviar, obtener } from '../api/cliente'
import { esConflictoDeVersion, mensajeDeConflicto } from '../ui/conflictos'
import type { Destino, ElementoCatalogo, Hallazgo, LineaCapex } from '../api/tipos'
import { Campo, Rejilla } from '../ui/Formulario'
import { Mensaje } from '../ui/Marco'
import { sinCerosSobrantes } from '../ui/numeros'
import { Calculadora } from './CalculadoraDeCapex'
import { ComparadorDePrecios } from './ComparadorDePrecios'

const PLAZOS = [
  { code: 'CORTO', nombre: 'Corto plazo' },
  { code: 'MEDIO', nombre: 'Medio plazo' },
  { code: 'LARGO', nombre: 'Largo plazo' },
  { code: 'MEJORAS', nombre: 'Mejoras potenciales' },
  { code: 'OTRO', nombre: 'Otro' },
] as const

const euros = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' })

/**
 * Edición de un hallazgo y de sus líneas de CAPEX.
 *
 * Faltaba lo más cotidiano de todo: **corregir**. Se podía crear una actuación
 * desde la interfaz, pero arreglar un importe mal tecleado —que pasa en cada
 * visita— exigía un `PATCH` por API.
 *
 * `[REQ]` P-44 · Una actuación puede tener **varias líneas, una por plazo**.
 * Repetir plazo no es un caso a evitar con cuidado: la base de datos lo impide
 * con un `UNIQUE`, y aquí el plazo ya usado sale deshabilitado en la lista.
 */
export function FichaDeHallazgo({
  hallazgo: inicial,
  alGuardar,
  alCerrar,
}: {
  hallazgo: Hallazgo
  alGuardar: () => void
  alCerrar: () => void
}) {
  const [hallazgo, setHallazgo] = useState(inicial)
  const [riesgos, setRiesgos] = useState<(ElementoCatalogo & { definition_es?: string })[]>([])
  const [destinos, setDestinos] = useState<Destino[]>([])
  const [titulo, setTitulo] = useState(inicial.title)
  const [descripcion, setDescripcion] = useState(inicial.description)
  const [comentarios, setComentarios] = useState(inicial.comments ?? '')
  const [recomendacion, setRecomendacion] = useState(inicial.recommendation ?? '')
  const [riesgo, setRiesgo] = useState(inicial.risk_level_id ?? '')
  const [error, setError] = useState<string | null>(null)
  //  Se distingue del error corriente: un choque de versión no se arregla
  //  volviendo a pulsar Guardar, que es lo que hace cualquiera ante un error.
  //  Lo que hay que ofrecer es recargar y mirar qué cambió.
  const [choque, setChoque] = useState(false)
  const [guardando, setGuardando] = useState(false)
  //  El aviso se pinta arriba y el botón de guardar está al final de una ficha
  //  larga: quien guarda desde abajo no lo vería. Se descubrió mirando una
  //  captura de la pantalla real, no en las pruebas, que solo comprobaban que
  //  el aviso existiera.
  const avisoRef = useRef<HTMLDivElement>(null)

  const recargarDestinos = useCallback(() => {
    obtener<Destino[]>(`/findings/${inicial.id}/transitions`)
      .then(setDestinos)
      .catch(() => setDestinos([]))
  }, [inicial.id])

  useEffect(() => {
    if (choque) avisoRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [choque])

  useEffect(() => {
    obtener<(ElementoCatalogo & { definition_es?: string })[]>('/catalogs/risk-levels')
      .then(setRiesgos)
      .catch(() => setRiesgos([]))
    recargarDestinos()
  }, [recargarDestinos])

  /** Cada respuesta trae los totales recalculados: no se suman aquí. */
  function refrescar(nuevo: Hallazgo) {
    setHallazgo(nuevo)
    recargarDestinos()
    alGuardar()
  }

  async function guardarCabecera() {
    setError(null)
    setGuardando(true)
    try {
      refrescar(
        await enviar<Hallazgo>(
          `/findings/${hallazgo.id}`,
          {
            title: titulo.trim(),
            description: descripcion.trim(),
            comments: comentarios.trim() || null,
            recommendation: recomendacion.trim() || null,
            risk_level_id: riesgo || null,
          },
          'PATCH',
          hallazgo.row_version,
        ),
      )
    } catch (e) {
      setError(mensajeDeConflicto(e))
      setChoque(esConflictoDeVersion(e))
    } finally {
      setGuardando(false)
    }
  }

  /** Trae la versión de la base y repuebla el formulario con ella.
   *
   *  Descarta lo que hubiera escrito quien ve el conflicto, y es lo correcto:
   *  el texto que se guardó es el del compañero, y editar sobre una copia vieja
   *  volvería a producir el mismo choque.
   */
  async function recargar() {
    try {
      const fresco = await obtener<Hallazgo>(`/findings/${hallazgo.id}`)
      setHallazgo(fresco)
      setTitulo(fresco.title)
      setDescripcion(fresco.description)
      setComentarios(fresco.comments ?? '')
      setRecomendacion(fresco.recommendation ?? '')
      setRiesgo(fresco.risk_level_id ?? '')
      setError(null)
      setChoque(false)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function transicionar(destino: string) {
    setError(null)
    try {
      refrescar(await enviar<Hallazgo>(`/findings/${hallazgo.id}/transitions`, { to: destino }))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const usados = new Set(hallazgo.capex_lines.map((l) => l.time_horizon_code))
  const libres = PLAZOS.filter((p) => !usados.has(p.code))
  const definicion = riesgos.find((r) => r.id === riesgo)?.definition_es

  return (
    <div className="ficha-hallazgo">
      <div className="cabecera">
        <h2>{hallazgo.title}</h2>
        <span className={`estado e-${hallazgo.status.toLowerCase()}`}>{hallazgo.status}</span>
        <button type="button" className="secundario" onClick={alCerrar}>
          Cerrar
        </button>
      </div>

      {error && (
        <div ref={avisoRef}>
          <Mensaje tipo={choque ? 'aviso' : 'error'}>
            {error}
            {choque && (
              <p className="acciones-conflicto">
                <button type="button" className="secundario" onClick={() => void recargar()}>
                  Recargar con los cambios de la otra persona
                </button>
              </p>
            )}
          </Mensaje>
        </div>
      )}

      <section>
        <h3>Descripción</h3>
        <Campo etiqueta="Título">
          <input maxLength={240} value={titulo} onChange={(e) => setTitulo(e.target.value)} />
        </Campo>
        <Campo etiqueta="Descripción" ayuda="Lo que se observa. Es lo que va al informe">
          <textarea
            rows={3}
            value={descripcion}
            onChange={(e) => setDescripcion(e.target.value)}
          />
        </Campo>
        <Campo etiqueta="Comentarios" ayuda="Notas internas del equipo">
          <textarea
            rows={2}
            value={comentarios}
            onChange={(e) => setComentarios(e.target.value)}
          />
        </Campo>
        <Campo etiqueta="Recomendación">
          <textarea
            rows={2}
            value={recomendacion}
            onChange={(e) => setRecomendacion(e.target.value)}
          />
        </Campo>
        <Campo etiqueta="Grado de riesgo">
          <select value={riesgo} onChange={(e) => setRiesgo(e.target.value)}>
            <option value="">— sin clasificar —</option>
            {riesgos.map((r) => (
              <option key={r.id} value={r.id}>
                {r.code} · {r.name_es}
              </option>
            ))}
          </select>
        </Campo>
        {/* La definición íntegra, no solo la etiqueta: «Alto» sin el criterio
            detrás es una palabra, y dos consultores la aplicarían distinto. */}
        {definicion && <p className="definicion-riesgo">{definicion}</p>}

        <button type="button" onClick={() => void guardarCabecera()} disabled={guardando}>
          {guardando ? 'Guardando…' : 'Guardar cambios'}
        </button>
      </section>

      <section>
        <h3>Líneas de CAPEX</h3>
        <p className="ayuda">
          `[REQ]` P-44 · Una actuación recurrente lleva <strong>una línea por plazo</strong>, no dos
          en el mismo. El plazo ya usado no aparece en la lista.
        </p>

        {hallazgo.capex_lines.length === 0 && (
          <p className="ayuda">
            Todavía sin importe. Es válido: en campo se anota lo que se ve antes de saber cuánto
            cuesta.
          </p>
        )}

        {hallazgo.capex_lines.map((linea) => (
          <Linea
            key={linea.id}
            linea={linea}
            descripcion={hallazgo.title}
            alCambiar={refrescar}
            alFallar={setError}
          />
        ))}

        {libres.length > 0 && (
          <NuevaLinea
            findingId={hallazgo.id}
            libres={libres}
            alCrear={refrescar}
            alFallar={setError}
          />
        )}
      </section>

      <section>
        <h3>Estado</h3>
        <p className="ayuda">
          Los botones que no se pueden pulsar salen deshabilitados <strong>con su motivo</strong>.
          Un botón que no está no se puede preguntar por qué no está.
        </p>
        <div className="acciones">
          {destinos.length === 0 && <em className="ayuda">Sin transiciones desde este estado.</em>}
          {destinos.map((d) => (
            <span key={d.to} className="destino">
              <button
                type="button"
                className="secundario"
                disabled={!d.allowed}
                onClick={() => void transicionar(d.to)}
                title={d.blockers.join('; ')}
              >
                {d.to}
              </button>
              {!d.allowed && <em className="ayuda">{d.blockers.join('; ')}</em>}
            </span>
          ))}
        </div>
      </section>
    </div>
  )
}

const PRECIO: Record<string, string> = {
  SIN_PRECIO: 'Sin precio',
  PENDIENTE_VALIDACION: 'Pendiente de validación',
  VALIDADO: 'Validado',
}

/** Una línea: importe, impuesto, medición y el traslado explícito. */
function Linea({
  linea,
  descripcion,
  alCambiar,
  alFallar,
}: {
  linea: LineaCapex
  descripcion: string
  alCambiar: (h: Hallazgo) => void
  alFallar: (m: string | null) => void
}) {
  const [importe, setImporte] = useState(sinCerosSobrantes(linea.amount))
  const [impuesto, setImpuesto] = useState(sinCerosSobrantes(linea.tax_pct))
  const [ocupado, setOcupado] = useState(false)
  const [comparando, setComparando] = useState(false)

  // Cuando el servidor cambia el importe por su cuenta —«trasladar la base
  // calculada» lo hace— el campo tiene que seguirlo. Sin esto el total de
  // arriba se actualizaba y el recuadro seguía enseñando el número viejo, que
  // es la peor combinación posible: dos cifras distintas a la vez en pantalla.
  useEffect(() => {
    setImporte(sinCerosSobrantes(linea.amount))
    setImpuesto(sinCerosSobrantes(linea.tax_pct))
  }, [linea.amount, linea.tax_pct])

  async function guardar() {
    alFallar(null)
    setOcupado(true)
    try {
      alCambiar(
        await enviar<Hallazgo>(
          `/capex-items/${linea.id}`,
          { amount: importe, tax_pct: impuesto },
          'PATCH',
          linea.row_version,
        ),
      )
    } catch (e) {
      alFallar(mensajeDeConflicto(e))
    } finally {
      setOcupado(false)
    }
  }

  // `DELETE` y `carry-measurement` devuelven el hallazgo completo, igual que
  // el resto: la interfaz nunca recalcula el total por su cuenta, que es donde
  // aparecen los descuadres entre lo que se ve y lo que se entrega.
  async function operar(hacer: () => Promise<Hallazgo>) {
    alFallar(null)
    setOcupado(true)
    try {
      alCambiar(await hacer())
    } catch (e) {
      alFallar((e as Error).message)
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div className="linea-capex">
      <Rejilla>
        <Campo etiqueta="Plazo">
          <input value={linea.time_horizon_code} readOnly />
        </Campo>
        <Campo
          etiqueta="Importe (€)"
          ayuda={`Precio: ${PRECIO[linea.price_status] ?? linea.price_status}`}
        >
          <input
            type="number"
            step="0.01"
            min={0}
            value={importe}
            onChange={(e) => setImporte(e.target.value)}
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
      <p className="totales">
        Con impuesto: <strong>{euros.format(Number(linea.total_cost))}</strong>
        {linea.computed_base && (
          <>
            {' · '}base calculada por medición: {euros.format(Number(linea.computed_base))}
          </>
        )}
      </p>

      {/* `[REQ]` §14 · La procedencia se lee aquí, sin abrir la auditoría. Un
          importe validado del que no se ve contra qué se validó vale lo mismo
          que uno sin validar el día que el cliente pregunta de dónde sale. */}
      <p className={`procedencia p-${linea.price_status.toLowerCase()}`}>
        {linea.price_reference_label ? (
          <>
            <strong>{PRECIO[linea.price_status] ?? linea.price_status}</strong> contra{' '}
            {linea.price_reference_label}
            {linea.price_validation_note && <> — «{linea.price_validation_note}»</>}
          </>
        ) : (
          <>
            <strong>Sin procedencia registrada.</strong> El importe se ha tecleado; no está
            respaldado por ninguna referencia.
          </>
        )}
      </p>

      <div className="acciones">
        <button type="button" onClick={() => void guardar()} disabled={ocupado}>
          Guardar línea
        </button>
        {/* `[REQ]` P-05b · El traslado es una acción EXPLÍCITA. La cascada nunca
            sustituye sola un importe tecleado: quien lo escribió puede tener un
            presupuesto real delante y la fórmula no sabe nada de eso. */}
        {linea.computed_base && (
          <button
            type="button"
            className="secundario"
            disabled={ocupado}
            title="Sustituye el importe por la base calculada. No ocurre solo"
            onClick={() =>
              void operar(() =>
                enviar<Hallazgo>(
                  `/capex-items/${linea.id}/carry-measurement`,
                  { confirmar: true },
                  'POST',
                  linea.row_version,
                ),
              )
            }
          >
            Trasladar la base calculada al importe
          </button>
        )}
        <button
          type="button"
          className="secundario"
          onClick={() => setComparando(true)}
          disabled={ocupado}
        >
          Ver referencias y validar el precio
        </button>
        <button
          type="button"
          className="secundario peligro"
          onClick={() =>
            void operar(() => borrar<Hallazgo>(`/capex-items/${linea.id}`, linea.row_version))
          }
          disabled={ocupado}
        >
          Eliminar
        </button>
      </div>
      <Calculadora alAplicar={(base) => setImporte(base)} />

      {/* Se abre en línea, como la calculadora, y no en una capa por encima:
          un modal sobre una tabla de doce columnas obliga a decidir con el
          contexto tapado, y aquí lo que se compara es justo el contexto. */}
      {comparando && (
        <ComparadorDePrecios
          itemId={linea.id}
          version={linea.row_version}
          descripcion={descripcion}
          importeActual={linea.amount}
          alValidar={(h) => {
            setComparando(false)
            alCambiar(h)
          }}
          alCerrar={() => setComparando(false)}
        />
      )}
    </div>
  )
}

function NuevaLinea({
  findingId,
  libres,
  alCrear,
  alFallar,
}: {
  findingId: string
  libres: readonly { code: string; nombre: string }[]
  alCrear: (h: Hallazgo) => void
  alFallar: (m: string | null) => void
}) {
  const [plazo, setPlazo] = useState(libres[0]?.code ?? '')
  const [importe, setImporte] = useState('')
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => {
    if (!libres.some((l) => l.code === plazo)) setPlazo(libres[0]?.code ?? '')
  }, [libres, plazo])

  async function crear() {
    alFallar(null)
    setOcupado(true)
    try {
      alCrear(
        await enviar<Hallazgo>(`/findings/${findingId}/capex-items`, {
          time_horizon_code: plazo,
          amount: importe.trim() || '0',
        }),
      )
      setImporte('')
    } catch (e) {
      alFallar((e as Error).message)
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div className="linea-capex nueva">
      <Rejilla>
        <Campo etiqueta="Añadir plazo">
          <select value={plazo} onChange={(e) => setPlazo(e.target.value)}>
            {libres.map((l) => (
              <option key={l.code} value={l.code}>
                {l.nombre}
              </option>
            ))}
          </select>
        </Campo>
        <Campo etiqueta="Importe (€)" ayuda="Puede quedar en blanco y rellenarse después">
          <input
            type="number"
            step="0.01"
            min={0}
            value={importe}
            onChange={(e) => setImporte(e.target.value)}
          />
        </Campo>
      </Rejilla>
      <button type="button" onClick={() => void crear()} disabled={ocupado || !plazo}>
        Añadir línea
      </button>
    </div>
  )
}

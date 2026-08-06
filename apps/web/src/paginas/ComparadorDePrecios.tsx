import { useCallback, useEffect, useState } from 'react'
import { enviar, obtener } from '../api/cliente'
import type { Hallazgo } from '../api/tipos'
import { Campo, Rejilla } from '../ui/Formulario'
import { Mensaje, Vacio } from '../ui/Marco'
import { sinCerosSobrantes } from '../ui/numeros'

type Referencia = {
  id: string
  source_code: string
  source_name: string
  source_type: string
  description: string
  unit: string
  unit_price: string
  currency: string
  price_date: string | null
  retrieved_at: string | null
  geo_scope: string | null
  includes_tax: boolean | null
  includes_installation: boolean | null
  scope_included: string | null
  scope_excluded: string | null
  provenance_note: string | null
  source_url: string | null
}

type NoConsultada = { code: string; name: string; motivo: string }

type Comparacion = {
  referencias: Referencia[]
  no_consultadas: NoConsultada[]
  aviso: string
}

type Fuente = {
  id: string
  code: string
  name: string
  source_type: string
  is_enabled: boolean
  motivo_de_no_consulta: string | null
}

const euros = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' })

function fecha(valor: string | null): string {
  return valor ? new Date(valor).toLocaleDateString('es-ES') : '—'
}

function siNo(valor: boolean | null): string {
  if (valor === null) return '—'
  return valor ? 'Sí' : 'No'
}

/**
 * Comparador de referencias de precio `[REQ]` §14.
 *
 * Tres cosas que esta pantalla hace y conviene no perder de vista:
 *
 * **No consulta nada.** No hay botón de «buscar en internet» porque no hay
 * ninguna fuente externa habilitada y porque consultar a un proveedor sin
 * licencia ni revisión de sus condiciones de uso es lo que el cliente prohibió.
 * Lo que se ve es lo que alguien registró.
 *
 * **Dice lo que NO ha mirado.** El bloque de fuentes no consultadas, con su
 * motivo, es deliberado: una lista de tres referencias sin esa columna sugiere
 * que se ha buscado en todas partes.
 *
 * **No elige.** Ninguna columna viene marcada. El importe que se aplica es un
 * campo editable, y validarlo exige una persona —y una explicación cuando el
 * número no es el de la referencia—.
 */
export function ComparadorDePrecios({
  itemId,
  descripcion,
  importeActual,
  alValidar,
  alCerrar,
}: {
  itemId: string
  descripcion: string
  importeActual: string
  alValidar: (hallazgo: Hallazgo) => void
  alCerrar: () => void
}) {
  const [datos, setDatos] = useState<Comparacion | null>(null)
  const [fuentes, setFuentes] = useState<Fuente[]>([])
  const [busqueda, setBusqueda] = useState('')
  const [elegida, setElegida] = useState<string | null>(null)
  const [importe, setImporte] = useState(sinCerosSobrantes(importeActual))
  const [justificacion, setJustificacion] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [alta, setAlta] = useState(false)

  const recargar = useCallback(() => {
    const consulta = busqueda.trim() ? `?q=${encodeURIComponent(busqueda.trim())}` : ''
    obtener<Comparacion>(`/price-references${consulta}`)
      .then(setDatos)
      .catch((e: Error) => setError(e.message))
  }, [busqueda])

  useEffect(recargar, [recargar])

  useEffect(() => {
    obtener<Fuente[]>('/price-sources')
      .then(setFuentes)
      .catch(() => setFuentes([]))
  }, [])

  const referencia = datos?.referencias.find((r) => r.id === elegida) ?? null
  const difiere = referencia !== null && Number(importe) !== Number(referencia.unit_price)

  async function validar() {
    setError(null)
    setGuardando(true)
    try {
      alValidar(
        await enviar<Hallazgo>(`/capex-items/${itemId}/validate-price`, {
          amount: importe,
          price_reference_id: elegida,
          justificacion: justificacion.trim() || null,
        }),
      )
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setGuardando(false)
    }
  }

  if (!datos) return <p className="cargando">Cargando referencias…</p>

  return (
    <div className="comparador">
      <div className="titular">
        <div>
          <h2>Referencias de precio</h2>
          <p className="ayuda">{descripcion}</p>
        </div>
        <button type="button" className="secundario" onClick={alCerrar}>
          Cerrar
        </button>
      </div>

      {error && <Mensaje tipo="error">{error}</Mensaje>}

      {/* `[REQ]` §14 · Nada se selecciona solo. Es lo primero que se lee. */}
      <Mensaje tipo="aviso">{datos.aviso}</Mensaje>

      <div className="filtro">
        <label>
          Buscar entre las registradas
          <input
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="enfriadora, lámina, ascensor…"
          />
        </label>
        <button type="button" className="secundario" onClick={() => setAlta(true)}>
          Introducir precio manual
        </button>
        <span className="ayuda">
          No hay búsqueda en proveedores externos: la aplicación no consulta ninguno.
        </span>
      </div>

      {alta && (
        <NuevaReferencia
          fuentes={fuentes}
          descripcionSugerida={descripcion}
          alCrear={() => {
            setAlta(false)
            recargar()
          }}
          alCancelar={() => setAlta(false)}
        />
      )}

      {datos.referencias.length === 0 ? (
        <Vacio>
          No hay ninguna referencia registrada que encaje. Introduzca el precio a mano indicando de
          dónde sale.
        </Vacio>
      ) : (
        <div className="desbordable">
          <table className="tabla referencias">
            <thead>
              <tr>
                <th scope="col">Elegir</th>
                <th scope="col">Fuente</th>
                <th scope="col">Descripción</th>
                <th scope="col" className="numerica">
                  Precio unitario
                </th>
                <th scope="col">Unidad</th>
                <th scope="col">Fecha del precio</th>
                <th scope="col">Registrada</th>
                <th scope="col">Ámbito</th>
                <th scope="col">Impuestos</th>
                <th scope="col">Instalación</th>
                <th scope="col">Incluye</th>
                <th scope="col">Excluye</th>
              </tr>
            </thead>
            <tbody>
              {datos.referencias.map((r) => (
                <tr key={r.id} className={r.id === elegida ? 'elegida' : ''}>
                  <td>
                    <label className="casilla">
                      <input
                        type="radio"
                        name="referencia"
                        checked={r.id === elegida}
                        onChange={() => {
                          setElegida(r.id)
                          // Elegir una referencia rellena el importe, pero no
                          // lo cierra: sigue siendo editable, que es lo que
                          // distingue «propuesto» de «decidido».
                          setImporte(sinCerosSobrantes(r.unit_price))
                        }}
                      />
                      <span className="oculto-visual">Elegir {r.source_name}</span>
                    </label>
                  </td>
                  <td>
                    <strong>{r.source_name}</strong>
                    <br />
                    <span className="ayuda">{r.source_type}</span>
                  </td>
                  <td>{r.description}</td>
                  <td className="numerica">{euros.format(Number(r.unit_price))}</td>
                  <td>{r.unit}</td>
                  <td>{fecha(r.price_date)}</td>
                  <td>{fecha(r.retrieved_at)}</td>
                  <td>{r.geo_scope ?? '—'}</td>
                  <td>{siNo(r.includes_tax)}</td>
                  <td>{siNo(r.includes_installation)}</td>
                  <td className="alcance">{r.scope_included ?? '—'}</td>
                  <td className="alcance">{r.scope_excluded ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* `[REQ]` §14 · La columna de lo no consultado, con su motivo. Sin ella
          una lista de resultados sugiere que se ha buscado en todas partes. */}
      {datos.no_consultadas.length > 0 && (
        <section className="no-consultadas">
          <h3>Fuentes no consultadas</h3>
          <ul>
            {datos.no_consultadas.map((f) => (
              <li key={f.code}>
                <strong>{f.name}</strong> — {f.motivo}
              </li>
            ))}
          </ul>
          <p className="ayuda">
            Habilitar una fuente exige registrar la revisión de sus condiciones de uso y requiere
            rol de administrador.
          </p>
        </section>
      )}

      <ActualizacionPorIndice base={importe} alAplicar={setImporte} />

      <section className="aplicar">
        <h3>Precio que se aplicará</h3>
        <Rejilla>
          <Campo etiqueta="Importe (€)" ayuda="Editable: puede no ser el de ninguna referencia">
            <input
              type="number"
              step="0.01"
              min={0}
              value={importe}
              onChange={(e) => setImporte(e.target.value)}
            />
          </Campo>
        </Rejilla>

        {difiere && referencia && (
          <Mensaje tipo="aviso">
            El importe no coincide con la referencia elegida (
            {euros.format(Number(referencia.unit_price))}). Explique por qué.
          </Mensaje>
        )}

        <Campo
          etiqueta="Justificación"
          ayuda={
            difiere
              ? 'Obligatoria: el importe difiere de la referencia'
              : 'Opcional cuando el importe es el de la referencia'
          }
        >
          <textarea
            rows={2}
            value={justificacion}
            onChange={(e) => setJustificacion(e.target.value)}
            placeholder="Oferta en firme del proveedor, incluye puesta en marcha…"
          />
        </Campo>

        {elegida === null && (
          <Mensaje tipo="aviso">
            Elija una referencia. Un precio conserva siempre su procedencia: si el importe no sale de
            ninguna de las registradas, dé de alta una manual con su origen.
          </Mensaje>
        )}

        <div className="acciones">
          <button
            type="button"
            onClick={() => void validar()}
            disabled={guardando || elegida === null}
          >
            {guardando ? 'Validando…' : 'Validar precio'}
          </button>
          <button type="button" className="secundario" onClick={alCerrar}>
            Cancelar
          </button>
        </div>
      </section>
    </div>
  )
}

/** `[REQ]` P-06 · Los dos valores del índice los introduce el usuario. */
function ActualizacionPorIndice({
  base,
  alAplicar,
}: {
  base: string
  alAplicar: (valor: string) => void
}) {
  const [abierto, setAbierto] = useState(false)
  const [origen, setOrigen] = useState('')
  const [destino, setDestino] = useState('')
  const [geo, setGeo] = useState('1')
  const [resultado, setResultado] = useState<{ resultado: string; formula: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!abierto) {
    return (
      <button type="button" className="enlace" onClick={() => setAbierto(true)}>
        Actualizar el precio por un índice
      </button>
    )
  }

  async function calcular() {
    setError(null)
    try {
      setResultado(
        await enviar<{ resultado: string; formula: string }>('/prices/index-update', {
          base,
          indice_origen: origen,
          indice_destino: destino,
          factor_geografico: geo || '1',
        }),
      )
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <section className="por-indice">
      <div className="titular">
        <h3>Actualización por índice</h3>
        <button type="button" className="enlace" onClick={() => setAbierto(false)}>
          Cerrar
        </button>
      </div>
      <p className="ayuda">
        `[LIM]` No hay catálogo de índices en la aplicación: los dos valores los introduce usted.
        Publicar una cifra que nadie ha verificado sería inventar una fuente de precios.
      </p>
      <Rejilla>
        <Campo etiqueta="Índice en la fecha del precio">
          <input
            type="number"
            step="0.01"
            value={origen}
            onChange={(e) => setOrigen(e.target.value)}
            placeholder="112,7"
          />
        </Campo>
        <Campo etiqueta="Índice hoy">
          <input
            type="number"
            step="0.01"
            value={destino}
            onChange={(e) => setDestino(e.target.value)}
            placeholder="118,4"
          />
        </Campo>
        <Campo etiqueta="Factor geográfico" ayuda="1 si no aplica">
          <input type="number" step="0.01" value={geo} onChange={(e) => setGeo(e.target.value)} />
        </Campo>
      </Rejilla>
      <button type="button" className="secundario" onClick={() => void calcular()}>
        Calcular
      </button>
      {error && <Mensaje tipo="error">{error}</Mensaje>}
      {resultado && (
        <>
          <p className="formula">{resultado.formula}</p>
          <button type="button" className="secundario" onClick={() => alAplicar(resultado.resultado)}>
            Llevar {euros.format(Number(resultado.resultado))} al importe
          </button>
          <p className="ayuda">
            No se ha aplicado nada todavía, y aplicarlo solo rellena el campo: sigue haciendo falta
            validar el precio.
          </p>
        </>
      )}
    </section>
  )
}

function NuevaReferencia({
  fuentes,
  descripcionSugerida,
  alCrear,
  alCancelar,
}: {
  fuentes: Fuente[]
  descripcionSugerida: string
  alCrear: () => void
  alCancelar: () => void
}) {
  const [fuente, setFuente] = useState(fuentes[0]?.id ?? '')
  const [descripcion, setDescripcion] = useState(descripcionSugerida)
  const [unidad, setUnidad] = useState('ud')
  const [precio, setPrecio] = useState('')
  const [fechaPrecio, setFechaPrecio] = useState('')
  const [ambito, setAmbito] = useState('')
  const [incluye, setIncluye] = useState('')
  const [excluye, setExcluye] = useState('')
  const [origen, setOrigen] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!fuente && fuentes[0]) setFuente(fuentes[0].id)
  }, [fuentes, fuente])

  async function crear() {
    setError(null)
    try {
      await enviar('/price-references', {
        price_source_id: fuente,
        description: descripcion.trim(),
        unit: unidad.trim(),
        unit_price: precio,
        price_date: fechaPrecio || null,
        geo_scope: ambito.trim() || null,
        scope_included: incluye.trim() || null,
        scope_excluded: excluye.trim() || null,
        provenance_note: origen.trim() || null,
      })
      alCrear()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <section className="nueva-referencia">
      <h3>Introducir un precio a mano</h3>
      <p className="ayuda">
        Queda firmado con su usuario y con la fecha. Es lo que permite preguntar de dónde salió
        dentro de seis meses.
      </p>
      <Rejilla>
        <Campo etiqueta="Fuente">
          <select value={fuente} onChange={(e) => setFuente(e.target.value)}>
            {fuentes.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
        </Campo>
        <Campo etiqueta="Unidad">
          <input value={unidad} onChange={(e) => setUnidad(e.target.value)} maxLength={20} />
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
        <Campo etiqueta="Fecha del precio">
          <input
            type="date"
            value={fechaPrecio}
            onChange={(e) => setFechaPrecio(e.target.value)}
          />
        </Campo>
        <Campo etiqueta="Ámbito" ayuda="ES-MAD, nacional…">
          <input value={ambito} onChange={(e) => setAmbito(e.target.value)} maxLength={40} />
        </Campo>
      </Rejilla>
      <Campo etiqueta="Descripción">
        <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
      </Campo>
      <Rejilla>
        <Campo etiqueta="Incluye">
          <input value={incluye} onChange={(e) => setIncluye(e.target.value)} />
        </Campo>
        <Campo etiqueta="Excluye">
          <input value={excluye} onChange={(e) => setExcluye(e.target.value)} />
        </Campo>
      </Rejilla>
      <Campo etiqueta="De dónde sale" ayuda="Oferta adjunta, catálogo, llamada al fabricante…">
        <input value={origen} onChange={(e) => setOrigen(e.target.value)} />
      </Campo>
      {error && <Mensaje tipo="error">{error}</Mensaje>}
      <div className="acciones">
        <button type="button" onClick={() => void crear()} disabled={!fuente || !precio}>
          Registrar referencia
        </button>
        <button type="button" className="secundario" onClick={alCancelar}>
          Cancelar
        </button>
      </div>
    </section>
  )
}

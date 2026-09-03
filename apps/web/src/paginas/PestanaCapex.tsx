import { useCallback, useEffect, useState } from 'react'
import { descargar, obtener } from '../api/cliente'
import type { Activo, Hallazgo } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'
import { FichaDeHallazgo } from './FichaDeHallazgo'
import { NuevoHallazgo } from './NuevoHallazgo'
import { ResumenCapex } from './ResumenCapex'

const PLAZOS = ['CORTO', 'MEDIO', 'LARGO', 'MEJORAS', 'OTRO'] as const

const euros = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
})

/**
 * Hallazgos y CAPEX.
 *
 * La tabla replica la del informe a propósito: **una fila por actuación**, con
 * una columna por plazo. Una actuación recurrente (P-44) tiene varias líneas y
 * aquí se ve como una sola fila con dos columnas rellenas, que es como aparece
 * en el Excel del cliente. Enseñarla de otra forma obligaría al consultor a
 * traducir mentalmente entre la pantalla y lo que va a entregar.
 */
/** Los idiomas para los que hay plantilla CAPEX. */
type Idioma = 'es' | 'en'

/**
 * Qué se descarga cuando el encargo tiene más de un activo.
 *
 * `[REQ]` La plantilla del cliente describe **un** edificio: un nombre, unas
 * superficies y un tipo que decide qué zonas ofrece el desplegable. En un
 * encargo de cartera, `conjunto` deja a los demás activos sin identificar y
 * `por-activo` da un libro a cada uno. Por eso la opción está aquí y no
 * escondida en la API: es una decisión sobre lo que se le manda al cliente.
 */
type Alcance = 'conjunto' | 'por-activo'

/**
 * Las dos vistas del CAPEX.
 *
 * `[REC]` Van aquí dentro y **no como una décima pestaña de proyecto**. Son dos
 * lecturas del mismo dato —lo que hay que hacer y cuánto suma—, y separarlas al
 * primer nivel de navegación las alejaría entre sí justo cuando se consultan
 * una detrás de otra: se mira el reparto, se ve que «Normativa» pesa demasiado
 * y se va a la rejilla a comprobar de qué hallazgos sale.
 */
type Vista = 'hallazgos' | 'resumen'

export function PestanaCapex({ projectId }: { projectId: string }) {
  const [hallazgos, setHallazgos] = useState<Hallazgo[] | null>(null)
  const [activos, setActivos] = useState<Activo[]>([])
  const [error, setError] = useState<string | null>(null)
  const [creando, setCreando] = useState(false)
  const [abierto, setAbierto] = useState<Hallazgo | null>(null)
  const [exportando, setExportando] = useState(false)
  const [idioma, setIdioma] = useState<Idioma>('es')
  const [alcance, setAlcance] = useState<Alcance>('por-activo')
  const [vista, setVista] = useState<Vista>('hallazgos')
  // Aparte del error de carga: que falle la exportación no debe dejar la
  // pestaña en blanco y hacer perder de vista la tabla.
  const [errorExport, setErrorExport] = useState<string | null>(null)

  const recargar = useCallback(() => {
    obtener<Hallazgo[]>(`/projects/${projectId}/findings`)
      .then(setHallazgos)
      .catch((e: Error) => setError(e.message))
    // Los activos son para agrupar la tabla y nombrar cada libro. Si fallan, la
    // pestaña sigue siendo útil sin agrupar: no se tumba la pantalla por eso.
    obtener<Activo[]>(`/projects/${projectId}/assets`)
      .then(setActivos)
      .catch(() => setActivos([]))
  }, [projectId])

  useEffect(recargar, [recargar])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>

  if (abierto) {
    return (
      <FichaDeHallazgo
        hallazgo={abierto}
        alGuardar={recargar}
        alCerrar={() => {
          setAbierto(null)
          recargar()
        }}
      />
    )
  }

  if (creando) {
    return (
      <NuevoHallazgo
        projectId={projectId}
        alGuardar={() => {
          setCreando(false)
          recargar()
        }}
        alCancelar={() => setCreando(false)}
      />
    )
  }

  /**
   * `[REQ]` P-31 · Exportar el CAPEX a XLSX para adjuntarlo en el envío que el
   * equipo hace fuera de la plataforma. **Sale la plantilla CAPEX del cliente
   * rellenada**, con sus gráficos, sus tablas dinámicas y sus fórmulas, no un
   * libro construido a mano.
   */
  const cartera = activos.length > 1
  const separado = cartera && alcance === 'por-activo'

  async function exportar() {
    setExportando(true)
    setErrorExport(null)
    try {
      if (separado) {
        await descargar(
          `/projects/${projectId}/capex/export.zip?idioma=${idioma}`,
          `CAPEX_${idioma.toUpperCase()}_por_activo.zip`,
        )
      } else {
        await descargar(
          `/projects/${projectId}/capex/export.xlsx?idioma=${idioma}`,
          `CAPEX_${idioma.toUpperCase()}.xlsx`,
        )
      }
    } catch (e) {
      setErrorExport((e as Error).message)
    } finally {
      setExportando(false)
    }
  }

  /** El CAPEX de un solo activo, desde su propia sección de la tabla. */
  async function exportarActivo(a: Activo) {
    setExportando(true)
    setErrorExport(null)
    try {
      await descargar(
        `/projects/${projectId}/capex/export.xlsx?idioma=${idioma}&asset_id=${a.id}`,
        `CAPEX_${idioma.toUpperCase()}_${a.asset_code ?? a.name}.xlsx`,
      )
    } catch (e) {
      setErrorExport((e as Error).message)
    } finally {
      setExportando(false)
    }
  }

  const alta = (
    <div className="filtro">
      <button type="button" onClick={() => setCreando(true)}>
        Registrar hallazgo
      </button>
      <button
        type="button"
        className="secundario"
        onClick={exportar}
        disabled={exportando || !hallazgos?.length}
        title={
          separado
            ? 'Un libro por activo, cada uno con su cabecera y sus zonas, en un ZIP'
            : 'Rellena la plantilla CAPEX del cliente y la descarga'
        }
      >
        {exportando ? 'Preparando…' : separado ? 'Exportar por activo (ZIP)' : 'Exportar a XLSX'}
      </button>
      {/* `[REQ]` Hay una plantilla por idioma, y no es solo la cabecera: las
          etiquetas de zona, riesgo y concepto salen de listas cerradas de la
          propia plantilla, así que el idioma se elige ANTES de descargar. */}
      <label className="idioma">
        Idioma
        <select
          value={idioma}
          onChange={(e) => setIdioma(e.target.value as Idioma)}
          disabled={exportando}
        >
          <option value="es">Español</option>
          <option value="en">English</option>
        </select>
      </label>
      {/* Solo aparece si hay más de un activo: en un encargo de un edificio la
          elección no existe y el control sobraría. */}
      {cartera && (
        <label className="alcance">
          Alcance
          <select
            value={alcance}
            onChange={(e) => setAlcance(e.target.value as Alcance)}
            disabled={exportando}
          >
            <option value="por-activo">Un libro por activo</option>
            <option value="conjunto">Un libro para todo el encargo</option>
          </select>
        </label>
      )}
    </div>
  )

  const avisoExport = errorExport ? <Mensaje tipo="error">{errorExport}</Mensaje> : null

  /* Dos botones y no un desplegable: son dos, se alternan constantemente, y un
     desplegable esconde la mitad de la pantalla detrás de un clic. */
  const conmutador = (
    <div className="vistas" role="tablist" aria-label="Vista del CAPEX">
      <button
        type="button"
        role="tab"
        aria-selected={vista === 'hallazgos'}
        className={vista === 'hallazgos' ? 'activa' : ''}
        onClick={() => setVista('hallazgos')}
      >
        Hallazgos
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={vista === 'resumen'}
        className={vista === 'resumen' ? 'activa' : ''}
        onClick={() => setVista('resumen')}
      >
        Resumen
      </button>
    </div>
  )

  if (vista === 'resumen') {
    return (
      <>
        {conmutador}
        <ResumenCapex projectId={projectId} />
      </>
    )
  }

  if (!hallazgos) return <p className="cargando">Cargando hallazgos…</p>
  if (hallazgos.length === 0) {
    return (
      <>
        {conmutador}
        {alta}
        {avisoExport}
        <Vacio>
          Todavía no hay hallazgos. En campo también se crean desde la propia fotografía, que hereda
          el activo y la zona.
        </Vacio>
      </>
    )
  }

  const totales = new Map<string, number>()
  for (const h of hallazgos) {
    for (const l of h.capex_lines) {
      totales.set(
        l.time_horizon_code,
        (totales.get(l.time_horizon_code) ?? 0) + Number(l.amount),
      )
    }
  }
  const totalGeneral = [...totales.values()].reduce((a, b) => a + b, 0)
  const sinValidar = hallazgos
    .flatMap((h) => h.capex_lines)
    .filter((l) => l.price_status !== 'VALIDADO' && Number(l.amount) > 0)

  /**
   * `[REQ]` La rejilla, **separada por activo**.
   *
   * En una cartera la pregunta que se hace el cliente no es cuánto suma el
   * encargo, sino cuánto cuesta cada edificio: es el número que entra en la
   * negociación de cada uno. Sin agrupar había que sumarlo a mano desde una
   * lista corrida, y ahí es donde aparecen los descuadres.
   *
   * Los activos **sin ningún hallazgo salen igual**, con su sección vacía: uno
   * sin visitar y otro visitado sin hallazgos no son lo mismo, y si el que no
   * tiene nada desapareciera de la tabla se verían idénticos.
   */
  const grupos = cartera
    ? activos.map((a) => ({ activo: a, suyos: hallazgos.filter((h) => h.asset_id === a.id) }))
    : [{ activo: null, suyos: hallazgos }]

  // Un hallazgo cuyo activo ya no está en la lista no puede desaparecer de la
  // pantalla sin más: el total de arriba lo sigue contando y no cuadraría.
  const conocidos = new Set(activos.map((a) => a.id))
  const sueltos = cartera ? hallazgos.filter((h) => !conocidos.has(h.asset_id)) : []

  const suma = (hs: Hallazgo[], plazo?: string) =>
    hs
      .flatMap((h) => h.capex_lines)
      .filter((l) => !plazo || l.time_horizon_code === plazo)
      .reduce((a, l) => a + Number(l.amount), 0)

  const filaDeHallazgo = (h: Hallazgo) => {
    const porPlazo = new Map(h.capex_lines.map((l) => [l.time_horizon_code, l]))
    return (
      <tr key={h.id}>
        <td>
          {/* Abre la ficha: corregir un importe mal tecleado es lo más
              cotidiano que hay, y hasta ahora exigía un PATCH por API. */}
          <button type="button" className="enlace" onClick={() => setAbierto(h)}>
            {h.title}
          </button>
          {h.capex_lines.length > 1 && <em className="ayuda"> · actuación recurrente</em>}
        </td>
        <td>
          <span className={`estado e-${h.status.toLowerCase()}`}>{h.status}</span>
        </td>
        {PLAZOS.map((p) => {
          const linea = porPlazo.get(p)
          return (
            <td key={p} className="numerica">
              {linea ? euros.format(Number(linea.amount)) : '—'}
            </td>
          )
        })}
        <td className="numerica">
          <strong>{euros.format(Number(h.total_amount))}</strong>
        </td>
      </tr>
    )
  }

  return (
    <>
      {conmutador}
      {alta}
      {avisoExport}
      {sinValidar.length > 0 && (
        <Mensaje tipo="aviso">
          {sinValidar.length} líneas con precio sin validar, por{' '}
          {euros.format(sinValidar.reduce((a, l) => a + Number(l.amount), 0))}. Generar así es
          legítimo para un borrador interno; enviarlo al cliente sin revisarlo, no.
        </Mensaje>
      )}

      <table className="tabla capex">
        <thead>
          <tr>
            <th>Actuación</th>
            <th>Estado</th>
            {PLAZOS.map((p) => (
              <th key={p} className="numerica">
                {p}
              </th>
            ))}
            <th className="numerica">Total</th>
          </tr>
        </thead>
        {grupos.map(({ activo, suyos }) => (
          <tbody key={activo?.id ?? 'todo'} className={activo ? 'grupo-activo' : undefined}>
            {activo && (
              <tr className="cabecera-grupo">
                <th colSpan={2} scope="colgroup">
                  {activo.name}
                  {activo.asset_code && <em className="ayuda"> · {activo.asset_code}</em>}
                  <button
                    type="button"
                    className="enlace"
                    onClick={() => exportarActivo(activo)}
                    disabled={exportando || suyos.length === 0}
                    title="Descarga la plantilla CAPEX rellena solo con este activo"
                  >
                    Exportar este activo
                  </button>
                </th>
                {PLAZOS.map((p) => (
                  <td key={p} className="numerica">
                    {suma(suyos, p) ? euros.format(suma(suyos, p)) : '—'}
                  </td>
                ))}
                <td className="numerica">
                  <strong>{euros.format(suma(suyos))}</strong>
                </td>
              </tr>
            )}
            {suyos.length === 0 ? (
              <tr>
                <td colSpan={2 + PLAZOS.length + 1} className="ayuda">
                  Sin hallazgos registrados todavía. No es lo mismo que no tener CAPEX: puede que
                  aún no se haya visitado.
                </td>
              </tr>
            ) : (
              suyos.map(filaDeHallazgo)
            )}
          </tbody>
        ))}
        {sueltos.length > 0 && (
          <tbody className="grupo-activo">
            <tr className="cabecera-grupo">
              <th colSpan={2 + PLAZOS.length + 1} scope="colgroup">
                Sin activo en el encargo
                <em className="ayuda">
                  {' '}
                  · su activo se borró después de registrarlos. Siguen contando en el total.
                </em>
              </th>
            </tr>
            {sueltos.map(filaDeHallazgo)}
          </tbody>
        )}
        <tfoot>
          <tr>
            <td colSpan={2}>Total</td>
            {PLAZOS.map((p) => (
              <td key={p} className="numerica">
                {totales.has(p) ? euros.format(totales.get(p) ?? 0) : '—'}
              </td>
            ))}
            <td className="numerica">
              <strong>{euros.format(totalGeneral)}</strong>
            </td>
          </tr>
        </tfoot>
      </table>
    </>
  )
}

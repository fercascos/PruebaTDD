import { useCallback, useEffect, useState } from 'react'
import { enviar, obtener, subirFichero } from '../api/cliente'
import type {
  CategoriaDeSolicitud,
  Documento,
  EstadoSolicitud,
  ObservacionIa,
  PermisoDeRevision,
  PropuestaDeDato,
  ResultadoDeExtraccion,
  RevisionIa,
  Solicitud,
} from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

/**
 * La fase «Solicitud de documentación»: la checklist, lo que ha llegado y su
 * revisión asistida.
 *
 * Dos cosas que esta pantalla hace explícitas porque son requisitos del
 * cliente y no detalles de interfaz:
 *
 * 1. **La revisión con IA está apagada hasta que alguien la autoriza**, y el
 *    interruptor dice quién lo hizo. No es una preferencia: es una
 *    autorización sobre documentación de un cliente.
 * 2. **Lo que la IA devuelve son propuestas.** Se pintan como tales, con su
 *    evidencia al lado, y no cambian el estado de ninguna línea hasta que una
 *    persona las acepta. Aceptar tampoco lo cambia: dice que la observación es
 *    cierta, y qué hacer con ella lo decide quien lleva el encargo.
 */

const ESTADOS: EstadoSolicitud[] = [
  'SOLICITADA',
  'RECIBIDA',
  'PARCIAL',
  'NO_DISPONIBLE',
  'NO_APLICA',
]

const VEREDICTO: Record<string, string> = {
  CONFORME: 'Conforme',
  NO_CONFORME: 'No conforme',
  FALTA: 'Falta',
  DUDOSO: 'Dudoso',
}

/**
 * El nombre en castellano de cada campo del activo que un documento puede
 * proponer.
 *
 * Las etiquetas son **las mismas que en la ficha del activo**, a propósito. Si
 * aquí pusiera «Superficie ocupada» y allí «Ocupación», quien valida no sabría
 * a qué casilla va a parar lo que acepta. Cuando falta una entrada se enseña el
 * nombre técnico en vez de ocultar la fila: una propuesta sin etiqueta sigue
 * siendo una propuesta que hay que decidir.
 */
const CAMPO: Record<string, string> = {
  main_use: 'Uso principal',
  secondary_use: 'Uso secundario',
  address_line: 'Dirección',
  city: 'Ciudad',
  province: 'Provincia',
  postal_code: 'Código postal',
  cadastral_reference: 'Referencia catastral',
  developer: 'Promotor',
  project_date: 'Fecha del proyecto',
  year_built: 'Año de construcción',
  year_last_refurb: 'Año de última reforma',
  plot_area_sqm: 'Superficie de parcela (m²)',
  total_built_sqm: 'Superficie construida total (m²)',
  lettable_area_sqm: 'Superficie alquilable (m²)',
  usable_area_sqm: 'Superficie útil total (m²)',
  occupied_area_sqm: 'Ocupación (m²)',
  urbanised_area_sqm: 'Superficie urbanizada (m²)',
  warehouse_area_sqm: 'Superficie de almacén (m²)',
  office_area_sqm: 'Superficie de oficinas (m²)',
  warehouse_height_m: 'Altura libre de almacén (m)',
  max_height_m: 'Altura máxima del edificio (m)',
  floors_above: 'Plantas sobre rasante',
  floors_below: 'Plantas bajo rasante',
  loading_docks: 'Muelles de carga',
  parking_spaces: 'Plazas de aparcamiento',
}

export function PestanaDocumentacion({ projectId }: { projectId: string }) {
  const [lineas, setLineas] = useState<Solicitud[] | null>(null)
  const [categorias, setCategorias] = useState<CategoriaDeSolicitud[]>([])
  const [documentos, setDocumentos] = useState<Documento[]>([])
  const [permiso, setPermiso] = useState<PermisoDeRevision | null>(null)
  const [error, setError] = useState<string | null>(null)
  /**
   * Los tipos de documento que la aplicación sabe leer hoy.
   *
   * `[REQ]` Se piden para ofrecer el botón de extraer **solo** donde va a
   * funcionar. Ofrecerlo en todos y que falle en la mayoría enseña a la gente a
   * no pulsarlo, y entonces la extracción no sirve de nada aunque funcione.
   */
  const [extraibles, setExtraibles] = useState<string[]>([])

  const recargar = useCallback(async () => {
    try {
      const [l, d, p] = await Promise.all([
        obtener<Solicitud[]>(`/projects/${projectId}/doc-requests`),
        obtener<Documento[]>(`/projects/${projectId}/documents`),
        obtener<PermisoDeRevision>(`/projects/${projectId}/ai-doc-review`),
      ])
      setLineas(l)
      setDocumentos(d)
      setPermiso(p)
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [projectId])

  useEffect(() => {
    void recargar()
    // Sin categorías no se puede dar de alta ninguna línea, así que un fallo
    // aquí se enseña. Tragárselo dejaba un desplegable vacío y un formulario
    // que no hacía nada al pulsar, sin decir por qué.
    obtener<CategoriaDeSolicitud[]>('/catalogs/doc-request-categories')
      .then(setCategorias)
      .catch((e: Error) => setError(e.message))
    // Que esto falle no rompe la pantalla: sin la lista no se ofrece extraer,
    // que es lo mismo que pasaba antes de que la extracción existiera. Por eso
    // no se enseña como error, a diferencia de las categorías.
    obtener<string[]>('/extraccion/tipos-soportados')
      .then(setExtraibles)
      .catch(() => setExtraibles([]))
  }, [recargar])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!lineas || !permiso) return <p className="cargando">Cargando la documentación…</p>

  const sinLinea = documentos.filter((d) => d.doc_request_item_id === null)

  return (
    <section className="documentacion">
      <Autorizacion
        projectId={projectId}
        permiso={permiso}
        alCambiar={setPermiso}
        alFallar={setError}
      />

      <NuevaLinea projectId={projectId} categorias={categorias} alCrear={recargar} />

      {lineas.length === 0 ? (
        <Vacio>
          La checklist está vacía. Añade arriba lo que hay que pedir: cada línea que quede sin
          recibir se convierte sola en una limitación del informe.
        </Vacio>
      ) : (
        <ul className="checklist">
          {lineas.map((l) => (
            <Linea
              key={l.id}
              linea={l}
              documentos={documentos.filter((d) => d.doc_request_item_id === l.id)}
              projectId={projectId}
              revisionActiva={permiso.activo}
              extraibles={extraibles}
              alCambiar={recargar}
              alFallar={setError}
            />
          ))}
        </ul>
      )}

      {sinLinea.length > 0 && (
        <details className="sueltos">
          <summary>{sinLinea.length} documento(s) sin línea de checklist</summary>
          <p className="detalle">
            Llegaron al encargo sin decir qué solicitud cubren. Se pueden revisar igual, pero no
            cuentan para la checklist ni para las limitaciones del informe.
          </p>
          <ul>
            {sinLinea.map((d) => (
              <FichaDocumento
                key={d.id}
                documento={d}
                revisionActiva={permiso.activo}
                extraibles={extraibles}
                alFallar={setError}
              />
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

/** `[REQ]` El interruptor de la revisión con IA, con su autoría a la vista. */
function Autorizacion({
  projectId,
  permiso,
  alCambiar,
  alFallar,
}: {
  projectId: string
  permiso: PermisoDeRevision
  alCambiar: (p: PermisoDeRevision) => void
  alFallar: (m: string) => void
}) {
  const [ocupado, setOcupado] = useState(false)

  async function cambiar() {
    setOcupado(true)
    try {
      alCambiar(
        await enviar<PermisoDeRevision>(
          `/projects/${projectId}/ai-doc-review`,
          { activo: !permiso.activo },
          'PUT',
        ),
      )
    } catch (e) {
      alFallar((e as Error).message)
    } finally {
      setOcupado(false)
    }
  }

  return (
    <div className={`autorizacion-ia ${permiso.activo ? 'activa' : 'inactiva'}`}>
      <div>
        <strong>Revisión de documentación con IA</strong>
        {permiso.activo ? (
          <p className="detalle">
            Autorizada para este encargo{permiso.desde ? ` el ${permiso.desde.slice(0, 10)}` : ''}.
            Los documentos que se suban podrán analizarse a petición.
          </p>
        ) : (
          <p className="detalle">
            Apagada. Ningún documento de este encargo se analiza mientras lo esté. La autoriza quien
            dirige el proyecto, y queda constancia de quién lo hizo.
          </p>
        )}
      </div>
      <button type="button" onClick={() => void cambiar()} disabled={ocupado}>
        {permiso.activo ? 'Retirar la autorización' : 'Autorizar'}
      </button>
    </div>
  )
}

function NuevaLinea({
  projectId,
  categorias,
  alCrear,
}: {
  projectId: string
  categorias: CategoriaDeSolicitud[]
  alCrear: () => Promise<void>
}) {
  const [titulo, setTitulo] = useState('')
  const [categoria, setCategoria] = useState('')
  const [fallo, setFallo] = useState<string | null>(null)

  useEffect(() => {
    const primera = categorias[0]
    if (!categoria && primera) setCategoria(primera.id)
  }, [categorias, categoria])

  async function crear(e: React.FormEvent) {
    e.preventDefault()
    if (!titulo.trim() || !categoria) return
    try {
      await enviar(`/projects/${projectId}/doc-requests`, {
        category_id: categoria,
        title: titulo.trim(),
      })
      setTitulo('')
      setFallo(null)
      await alCrear()
    } catch (err) {
      setFallo((err as Error).message)
    }
  }

  return (
    <form className="nueva-linea" onSubmit={(e) => void crear(e)}>
      <select
        value={categoria}
        onChange={(e) => setCategoria(e.target.value)}
        aria-label="Categoría"
      >
        {categorias.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name_es}
          </option>
        ))}
      </select>
      <input
        value={titulo}
        onChange={(e) => setTitulo(e.target.value)}
        placeholder="Qué hay que pedir (p. ej. «Licencia de actividad»)"
        aria-label="Documento solicitado"
      />
      <button type="submit" disabled={!titulo.trim()}>
        Añadir a la checklist
      </button>
      {fallo && <Mensaje tipo="error">{fallo}</Mensaje>}
    </form>
  )
}

function Linea({
  linea,
  documentos,
  projectId,
  revisionActiva,
  extraibles,
  alCambiar,
  alFallar,
}: {
  linea: Solicitud
  documentos: Documento[]
  projectId: string
  revisionActiva: boolean
  extraibles: string[]
  alCambiar: () => Promise<void>
  alFallar: (m: string) => void
}) {
  const [subiendo, setSubiendo] = useState(false)
  const [motivo, setMotivo] = useState(linea.unavailable_reason ?? '')

  async function cambiarEstado(status: EstadoSolicitud) {
    // `NO_DISPONIBLE` sin motivo lo rechaza la base: se pide antes de enviarlo
    // para que el error llegue como una pregunta y no como un 500.
    if (status === 'NO_DISPONIBLE' && !motivo.trim()) {
      alFallar('Para marcar «no disponible» hace falta decir por qué: es lo que explica la limitación en el informe.')
      return
    }
    try {
      await enviar(
        `/doc-requests/${linea.id}`,
        { status, unavailable_reason: motivo.trim() || null },
        'PATCH',
      )
      await alCambiar()
    } catch (e) {
      alFallar((e as Error).message)
    }
  }

  async function subir(archivo: File) {
    setSubiendo(true)
    try {
      await subirFichero(`/projects/${projectId}/documents`, archivo, {
        doc_request_item_id: linea.id,
      })
      await alCambiar()
    } catch (e) {
      alFallar((e as Error).message)
    } finally {
      setSubiendo(false)
    }
  }

  return (
    <li className={`linea l-${linea.status.toLowerCase()}`}>
      <div className="cabecera">
        <div>
          <strong>{linea.title}</strong>
          <span className="categoria">{linea.category_name}</span>
        </div>
        <select
          value={linea.status}
          onChange={(e) => void cambiarEstado(e.target.value as EstadoSolicitud)}
          aria-label={`Estado de ${linea.title}`}
        >
          {ESTADOS.map((e) => (
            <option key={e} value={e}>
              {e.replace('_', ' ')}
            </option>
          ))}
        </select>
      </div>

      {linea.affects_report_limitations && (
        <p className="limitacion">
          Esta línea entra en las limitaciones del informe: declarar lo que no se ha podido revisar
          es una obligación profesional en una TDD.
        </p>
      )}

      {linea.status === 'NO_DISPONIBLE' && (
        <input
          className="motivo"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          onBlur={() => void cambiarEstado('NO_DISPONIBLE')}
          placeholder="Por qué no está disponible"
          aria-label="Motivo"
        />
      )}

      <ul className="documentos">
        {documentos.map((d) => (
          <FichaDocumento
            key={d.id}
            documento={d}
            revisionActiva={revisionActiva}
            extraibles={extraibles}
            alFallar={alFallar}
          />
        ))}
      </ul>

      <label className="subir">
        <input
          type="file"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) void subir(f)
            e.target.value = ''
          }}
        />
        <span>{subiendo ? 'Subiendo…' : 'Adjuntar documento'}</span>
      </label>
    </li>
  )
}

function FichaDocumento({
  documento,
  revisionActiva,
  extraibles,
  alFallar,
}: {
  documento: Documento
  revisionActiva: boolean
  extraibles: string[]
  alFallar: (m: string) => void
}) {
  const [revisiones, setRevisiones] = useState<RevisionIa[] | null>(null)
  const [revisando, setRevisando] = useState(false)

  const cargar = useCallback(async () => {
    try {
      setRevisiones(await obtener<RevisionIa[]>(`/documents/${documento.id}/ai-reviews`))
    } catch (e) {
      alFallar((e as Error).message)
    }
  }, [documento.id, alFallar])

  useEffect(() => {
    if (revisionActiva) void cargar()
  }, [revisionActiva, cargar])

  async function revisar() {
    setRevisando(true)
    try {
      await enviar(`/documents/${documento.id}/ai-review`, {})
      await cargar()
    } catch (e) {
      alFallar((e as Error).message)
    } finally {
      setRevisando(false)
    }
  }

  const ultima = revisiones?.[0]

  // Solo donde va a funcionar: un tipo que no se lee, o un documento que no se
  // asignó a ningún activo, no tienen a quién proponerle nada.
  const puedeExtraerse = extraibles.includes(documento.doc_type) && documento.asset_id !== null

  return (
    <li className="documento">
      <div className="cabecera">
        <span className="nombre">
          {documento.display_name}.{documento.file_extension}
        </span>
        <span className="peso">{Math.round(documento.byte_size / 1024)} kB</span>
        {revisionActiva && (
          <button
            type="button"
            className="revisar-ia"
            onClick={() => void revisar()}
            disabled={revisando}
          >
            {revisando ? 'Revisando…' : ultima ? 'Revisar otra vez' : 'Revisar con IA'}
          </button>
        )}
      </div>

      {ultima && <Revision revision={ultima} alDecidir={cargar} alFallar={alFallar} />}
      {revisiones && revisiones.length > 1 && (
        <p className="detalle">
          Hay {revisiones.length} revisiones de este documento. Se muestra la más reciente.
        </p>
      )}

      {puedeExtraerse && <Extraccion documento={documento} alFallar={alFallar} />}
    </li>
  )
}

/**
 * `[REQ]` De lo que dice el documento a lo que dice el activo, con un botón
 * en medio.
 *
 * Lo que hace explícito, y por lo que existe la pantalla:
 *
 * * **Nada se aplica solo.** Extraer deja propuestas; aplicarlas es otro clic.
 * * **Cada propuesta trae la celda literal del PDF** y **lo que el activo tiene
 *   hoy** en ese campo. Con las dos delante se distingue «esto completa un
 *   hueco» de «esto contradice lo que había», que son decisiones distintas.
 * * **Se decide una a una.** Un botón de «aceptar todo» invita a aceptar sin
 *   mirar, que es exactamente lo que la validación viene a evitar.
 */
function Extraccion({
  documento,
  alFallar,
}: {
  documento: Documento
  alFallar: (m: string) => void
}) {
  const [propuestas, setPropuestas] = useState<PropuestaDeDato[] | null>(null)
  const [resultado, setResultado] = useState<ResultadoDeExtraccion | null>(null)
  const [extrayendo, setExtrayendo] = useState(false)

  const cargar = useCallback(async () => {
    if (!documento.asset_id) return
    try {
      const todas = await obtener<PropuestaDeDato[]>(`/assets/${documento.asset_id}/propuestas`)
      setPropuestas(todas.filter((p) => p.document_id === documento.id))
    } catch (e) {
      alFallar((e as Error).message)
    }
  }, [documento.asset_id, documento.id, alFallar])

  useEffect(() => {
    void cargar()
  }, [cargar])

  async function extraer() {
    setExtrayendo(true)
    try {
      setResultado(await enviar<ResultadoDeExtraccion>(`/documents/${documento.id}/extraer`, {}))
      await cargar()
    } catch (e) {
      alFallar((e as Error).message)
    } finally {
      setExtrayendo(false)
    }
  }

  const pendientes = propuestas?.filter((p) => p.estado === 'PENDIENTE') ?? []
  const decididas = (propuestas?.length ?? 0) - pendientes.length

  return (
    <div className="extraccion">
      <div className="cabecera">
        <button type="button" onClick={() => void extraer()} disabled={extrayendo}>
          {extrayendo ? 'Leyendo…' : propuestas?.length ? 'Volver a extraer' : 'Extraer datos'}
        </button>
        {/* Volver a extraer no reabre lo ya resuelto. Decirlo antes de pulsar
            evita la duda de si se va a perder lo decidido. */}
        {decididas > 0 && (
          <span className="detalle">
            {decididas} ya decidida(s): volver a extraer no las reabre
          </span>
        )}
      </div>

      {resultado?.es_simulada && (
        <Mensaje tipo="aviso">
          Lectura <strong>simulada</strong>: nadie ha leído este documento. Lo de abajo ocupa el
          sitio de lo que vendrá y no dice nada sobre su contenido.
        </Mensaje>
      )}

      {resultado?.avisos.map((a) => (
        <Mensaje key={a} tipo="aviso">
          {a}
        </Mensaje>
      ))}

      {resultado && Object.keys(resultado.desconocidos).length > 0 && (
        <details className="desconocidos">
          <summary>
            {Object.keys(resultado.desconocidos).length} etiqueta(s) leídas que no se han sabido
            encajar
          </summary>
          {/* No se pierden. Es como se descubre el sinónimo que falta, y es lo
              que separa «no venía el dato» de «no lo supe leer». */}
          <ul>
            {Object.entries(resultado.desconocidos).map(([etiqueta, valor]) => (
              <li key={etiqueta}>
                <strong>{etiqueta}</strong>: {valor}
              </li>
            ))}
          </ul>
        </details>
      )}

      {propuestas !== null && propuestas.length === 0 && resultado && (
        <p className="detalle">
          El documento no ha propuesto ningún dato del edificio. Los avisos de arriba dicen por qué.
        </p>
      )}

      {pendientes.length > 0 && (
        <ul className="propuestas">
          {pendientes.map((p) => (
            <Propuesta
              key={p.id}
              propuesta={p}
              assetId={documento.asset_id!}
              alDecidir={cargar}
              alFallar={alFallar}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function Propuesta({
  propuesta,
  assetId,
  alDecidir,
  alFallar,
}: {
  propuesta: PropuestaDeDato
  assetId: string
  alDecidir: () => Promise<void>
  alFallar: (m: string) => void
}) {
  const [ocupado, setOcupado] = useState(false)

  async function decidir(aceptar: boolean) {
    setOcupado(true)
    try {
      await enviar(`/assets/${assetId}/propuestas/decidir`, {
        [aceptar ? 'aceptar' : 'descartar']: [propuesta.id],
      })
      await alDecidir()
    } catch (e) {
      alFallar((e as Error).message)
    } finally {
      setOcupado(false)
    }
  }

  // Que el campo ya tenga valor no lo convierte en un error, pero sí en otra
  // decisión: aceptar aquí sustituye algo, no rellena un hueco.
  const contradice = propuesta.valor_actual !== null && propuesta.valor_actual !== propuesta.valor

  return (
    <li className={`propuesta${contradice ? ' contradice' : ''}`}>
      <div className="cabecera">
        <span className="criterio">{CAMPO[propuesta.campo] ?? propuesta.campo}</span>
        <span className="valor">{propuesta.valor}</span>
      </div>

      <p className="resumen">
        {propuesta.valor_actual === null ? (
          <>Hoy está vacío: aceptarlo lo rellena.</>
        ) : contradice ? (
          <>
            Hoy pone <strong>{propuesta.valor_actual}</strong>. Aceptarlo lo{' '}
            <strong>sustituye</strong>.
          </>
        ) : (
          <>Coincide con lo que ya hay. Aceptarlo no cambia nada.</>
        )}
      </p>

      {propuesta.evidencia && (
        <blockquote className="evidencia">
          {propuesta.evidencia}
          {propuesta.seccion && <cite>{propuesta.seccion}</cite>}
        </blockquote>
      )}

      <div className="decidir">
        <button type="button" onClick={() => void decidir(true)} disabled={ocupado}>
          Aceptar
        </button>
        <button type="button" onClick={() => void decidir(false)} disabled={ocupado}>
          Descartar
        </button>
      </div>
    </li>
  )
}

function Revision({
  revision,
  alDecidir,
  alFallar,
}: {
  revision: RevisionIa
  alDecidir: () => Promise<void>
  alFallar: (m: string) => void
}) {
  if (revision.status === 'FALLIDA') {
    return <Mensaje tipo="error">No se pudo revisar: {revision.error_message}</Mensaje>
  }

  return (
    <div className="revision">
      {/* [LIM] Lo más importante de toda la pantalla: mientras no haya
          proveedor, que nadie confunda esto con una revisión de verdad. */}
      {revision.is_simulated && (
        <Mensaje tipo="aviso">
          Revisión <strong>simulada</strong>. Todavía no hay proveedor de IA elegido, así que nadie
          ha leído este documento: las observaciones de abajo ocupan el sitio de las que vendrán y
          no dicen nada sobre su contenido.
        </Mensaje>
      )}
      <ul className="observaciones">
        {revision.observaciones.map((o) => (
          <Observacion key={o.id} obs={o} alDecidir={alDecidir} alFallar={alFallar} />
        ))}
      </ul>
    </div>
  )
}

function Observacion({
  obs,
  alDecidir,
  alFallar,
}: {
  obs: ObservacionIa
  alDecidir: () => Promise<void>
  alFallar: (m: string) => void
}) {
  const [ocupado, setOcupado] = useState(false)

  async function decidir(aceptar: boolean) {
    setOcupado(true)
    try {
      await enviar(`/ai-review-findings/${obs.id}/decision`, { aceptar })
      await alDecidir()
    } catch (e) {
      alFallar((e as Error).message)
    } finally {
      setOcupado(false)
    }
  }

  return (
    <li className={`observacion v-${obs.verdict.toLowerCase()} d-${obs.decision.toLowerCase()}`}>
      <div className="cabecera">
        <span className="criterio">{obs.check_name}</span>
        <span className="veredicto">{VEREDICTO[obs.verdict] ?? obs.verdict}</span>
      </div>
      <p className="resumen">{obs.summary}</p>

      {obs.evidence_text && (
        <blockquote className="evidencia">
          {obs.evidence_text}
          {obs.evidence_page !== null && <cite>página {obs.evidence_page}</cite>}
        </blockquote>
      )}

      {obs.decision === 'PROPUESTA' ? (
        <div className="decidir">
          {/* La IA propone; aquí decide una persona. No hay forma de que una
              propuesta se acepte sola. */}
          <button type="button" onClick={() => void decidir(true)} disabled={ocupado}>
            Aceptar
          </button>
          <button type="button" onClick={() => void decidir(false)} disabled={ocupado}>
            Rechazar
          </button>
        </div>
      ) : (
        <p className="decidida">
          {obs.decision === 'ACEPTADA' ? 'Aceptada' : 'Rechazada'} por una persona
          {obs.decision_note ? `: ${obs.decision_note}` : '.'}
        </p>
      )}
    </li>
  )
}

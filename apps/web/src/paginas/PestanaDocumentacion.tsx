import { useCallback, useEffect, useState } from 'react'
import { enviar, obtener, subirFichero } from '../api/cliente'
import type {
  Activo,
  CategoriaDeSolicitud,
  Documento,
  EstadoSolicitud,
  LimitacionDocumental,
  MotivoDeLimitacion,
  ObservacionIa,
  PermisoDeRevision,
  PropuestaDeDato,
  PropuestaDeEquipo,
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
  /**
   * Cuántas extracciones se han hecho en esta sesión de pantalla.
   *
   * No se usa el número: se usa que **cambie**. Extraer un documento puede
   * aportar limitaciones al encargo, y el panel de limitaciones está fuera de
   * la ficha de ese documento, así que necesita saber que hay algo nuevo. Un
   * contador es la forma más simple de decírselo sin subir su estado aquí.
   */
  const [extraccionesHechas, setExtraccionesHechas] = useState(0)
  const alExtraer = useCallback(() => setExtraccionesHechas((n) => n + 1), [])

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
              alExtraer={alExtraer}
              alFallar={setError}
            />
          ))}
        </ul>
      )}

      {/* `[REQ]` Va al final y no dentro de cada documento a propósito: una
          limitación es del ENCARGO, no del fichero. Un plan de autoprotección
          cubre un complejo de seis naves y sus reservas afectan al informe
          entero; enterrarlas en la ficha del PDF las dejaría fuera de la vista
          de quien redacta el apartado de limitaciones. */}
      <Limitaciones projectId={projectId} clave={extraccionesHechas} alFallar={setError} />

      {/* Igual que las limitaciones: los medios son del ENCARGO hasta que
          alguien dice de qué activo son, así que van fuera de la ficha del
          documento que los declaró. */}
      <EquiposPropuestos
        projectId={projectId}
        clave={extraccionesHechas}
        alFallar={setError}
      />

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
                alExtraer={alExtraer}
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
  alExtraer,
  alFallar,
}: {
  linea: Solicitud
  documentos: Documento[]
  projectId: string
  revisionActiva: boolean
  extraibles: string[]
  alCambiar: () => Promise<void>
  alExtraer: () => void
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
            alExtraer={alExtraer}
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
  alExtraer,
  alFallar,
}: {
  documento: Documento
  revisionActiva: boolean
  extraibles: string[]
  alExtraer: () => void
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

      {puedeExtraerse && (
        <Extraccion documento={documento} alExtraer={alExtraer} alFallar={alFallar} />
      )}
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
  alExtraer,
  alFallar,
}: {
  documento: Documento
  alExtraer: () => void
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
      // Puede haber aportado limitaciones al encargo, y ésas se pintan fuera
      // de esta ficha.
      alExtraer()
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

/**
 * `[REQ]` Lo que la documentación dice sobre su propia fiabilidad.
 *
 * La **tercera clase** de limitación del informe, y la que faltaba. Las dos que
 * ya había salen de lo que *no* llegó —una línea del checklist sin recibir, una
 * pregunta sin respuesta— y se calculan solas. Ésta es lo contrario: el
 * documento llegó, la casilla está marcada, el expediente parece completo, y el
 * documento dice que no se puede confiar en él.
 *
 * El caso que lo hizo evidente, leyendo uno de verdad: un plan de
 * autoprotección redactado con las naves vacías define los recorridos de
 * evacuación suponiendo espacios diáfanos. En cuanto entra un inquilino con
 * estanterías, esas longitudes dejan de ser las que dice el plan. Sin esta
 * pantalla, la limitación solo la ve quien se lo lea entero.
 *
 * **Solo las aceptadas van al informe.** Es lo que separa una salvedad
 * profesional de un párrafo que puso una máquina y nadie leyó.
 */
const MOTIVO: Record<MotivoDeLimitacion, { etiqueta: string; explica: string }> = {
  CADUCADO: {
    etiqueta: 'Fuera de plazo',
    explica: 'El documento existe pero está fuera de su plazo de vigencia o de revisión.',
  },
  INCOMPLETO: {
    etiqueta: 'Incompleto',
    explica: 'Le faltan datos que el propio documento reserva un sitio para llevar.',
  },
  NO_VIGENTE: {
    etiqueta: 'No vigente',
    explica: 'El documento se declara borrador, resumen o copia sin valor.',
  },
  DECLARADA: {
    etiqueta: 'La declara el documento',
    explica: 'La escribió quien redactó el documento. Se recoge literal, sin reescribirla.',
  },
  INCONSISTENTE: {
    etiqueta: 'Se contradice',
    explica: 'El documento no concuerda consigo mismo.',
  },
}

function Limitaciones({
  projectId,
  clave,
  alFallar,
}: {
  projectId: string
  /** Cambia cuando se extrae algo. No se lee: solo dispara la recarga. */
  clave: number
  alFallar: (m: string) => void
}) {
  const [todas, setTodas] = useState<LimitacionDocumental[] | null>(null)
  const [ocupado, setOcupado] = useState(false)

  const cargar = useCallback(async () => {
    try {
      setTodas(
        await obtener<LimitacionDocumental[]>(`/projects/${projectId}/limitaciones-documentales`),
      )
    } catch (e) {
      alFallar((e as Error).message)
    }
  }, [projectId, alFallar])

  useEffect(() => {
    void cargar()
  }, [cargar, clave])

  async function decidir(id: string, aceptar: boolean) {
    setOcupado(true)
    try {
      await enviar(`/projects/${projectId}/limitaciones-documentales/decidir`, {
        [aceptar ? 'aceptar' : 'descartar']: [id],
      })
      await cargar()
    } catch (e) {
      alFallar((e as Error).message)
    } finally {
      setOcupado(false)
    }
  }

  // Nada extraído todavía: la sección no aparece. Una caja vacía en cada
  // encargo enseña a no mirarla.
  if (!todas || todas.length === 0) return null

  const pendientes = todas.filter((l) => l.estado === 'PENDIENTE')
  const aceptadas = todas.filter((l) => l.estado === 'ACEPTADA')
  const descartadas = todas.filter((l) => l.estado === 'DESCARTADA')

  return (
    <section className="limitaciones-doc">
      <h3>Lo que la documentación dice sobre sí misma</h3>
      <p className="ayuda">
        Salen de leer los documentos, no de lo que falta. <strong>Solo las aceptadas entran en
        el apartado de limitaciones del informe</strong>: entre la propuesta y el entregable hay
        una persona decidiendo.
      </p>

      {pendientes.length > 0 && (
        <ul className="propuestas">
          {pendientes.map((l) => (
            <li key={l.id} className={`propuesta limitacion m-${l.motivo.toLowerCase()}`}>
              <div className="cabecera">
                <span className="criterio">{MOTIVO[l.motivo].etiqueta}</span>
                {l.es_simulada && <span className="veredicto">simulada</span>}
              </div>
              <p className="resumen">{l.texto}</p>
              <p className="detalle">
                {MOTIVO[l.motivo].explica}
                {l.documento && <> · Sale de «{l.documento}»</>}
                {l.seccion && <> · {l.seccion}</>}
              </p>
              {l.evidencia && <blockquote className="evidencia">{l.evidencia}</blockquote>}
              <div className="decidir">
                <button type="button" onClick={() => void decidir(l.id, true)} disabled={ocupado}>
                  Incluir en el informe
                </button>
                <button type="button" onClick={() => void decidir(l.id, false)} disabled={ocupado}>
                  Descartar
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {aceptadas.length > 0 && (
        <details className="decididas" open>
          <summary>{aceptadas.length} van al informe</summary>
          <ul>
            {aceptadas.map((l) => (
              <li key={l.id}>
                <strong>{MOTIVO[l.motivo].etiqueta}</strong> · {l.texto}
              </li>
            ))}
          </ul>
        </details>
      )}

      {descartadas.length > 0 && (
        <details className="decididas">
          {/* Descartar no es borrar: si el cliente pregunta por qué el informe
              no menciona algo, la respuesta tiene que estar aquí y no en la
              memoria de nadie. */}
          <summary>{descartadas.length} descartada(s), con constancia de quién fue</summary>
          <ul>
            {descartadas.map((l) => (
              <li key={l.id}>
                <strong>{MOTIVO[l.motivo].etiqueta}</strong> · {l.texto}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

/**
 * `[REQ]` Los medios que la documentación dice que existen, al inventario.
 *
 * El capítulo 4 de la Norma Básica de Autoprotección enumera los medios de
 * protección contra incendios del edificio: hidrantes, rociadores, BIE,
 * detección, exutorios. Teclearlos a mano después de que un documento los liste
 * es el trabajo repetido que esta aplicación viene a evitar.
 *
 * Es la **única** de las tres decisiones que crea una ficha nueva en vez de
 * actualizar una que ya existía, y por eso pide el activo: el documento no lo
 * dice. Un plan cubre un complejo de seis naves y habla de «dieciséis hidrantes
 * distribuidos por el perímetro»; adivinar la nave lo haría pasar por sabido, y
 * un equipo en la nave equivocada es una visita perdida.
 */
function EquiposPropuestos({
  projectId,
  clave,
  alFallar,
}: {
  projectId: string
  clave: number
  alFallar: (m: string) => void
}) {
  const [todos, setTodos] = useState<PropuestaDeEquipo[] | null>(null)
  const [activos, setActivos] = useState<Activo[]>([])
  const [destino, setDestino] = useState<Record<string, string>>({})
  const [meses, setMeses] = useState<Record<string, string>>({})
  const [ocupado, setOcupado] = useState(false)

  const cargar = useCallback(async () => {
    try {
      setTodos(
        await obtener<PropuestaDeEquipo[]>(`/projects/${projectId}/propuestas-de-equipo`),
      )
    } catch (e) {
      alFallar((e as Error).message)
    }
  }, [projectId, alFallar])

  useEffect(() => {
    void cargar()
    obtener<Activo[]>(`/projects/${projectId}/assets`)
      .then(setActivos)
      .catch(() => setActivos([]))
  }, [cargar, clave, projectId])

  async function decidir(propuesta: PropuestaDeEquipo, aceptar: boolean) {
    setOcupado(true)
    try {
      const cuerpo = aceptar
        ? {
            aceptar: [
              {
                id: propuesta.id,
                asset_id: destino[propuesta.id] ?? activos[0]?.id,
                ...(meses[propuesta.id]
                  ? { maintenance_months: Number(meses[propuesta.id]) }
                  : {}),
              },
            ],
          }
        : { descartar: [propuesta.id] }
      await enviar(`/projects/${projectId}/propuestas-de-equipo/decidir`, cuerpo)
      await cargar()
    } catch (e) {
      alFallar((e as Error).message)
    } finally {
      setOcupado(false)
    }
  }

  if (!todos || todos.length === 0) return null

  const pendientes = todos.filter((e) => e.estado === 'PENDIENTE')
  const aceptados = todos.filter((e) => e.estado === 'ACEPTADA')

  return (
    <section className="equipos-propuestos">
      <h3>Medios que declara la documentación</h3>
      <p className="ayuda">
        Salen del capítulo de medios de autoprotección. <strong>Aceptar crea la ficha de
        equipo</strong>, así que hay que decir en qué activo va: el documento no lo dice.
      </p>

      {activos.length === 0 && pendientes.length > 0 && (
        <Mensaje tipo="aviso">
          Este encargo no tiene ningún activo dado de alta todavía, y un equipo tiene que nacer
          en alguno. Créalo antes de aceptar estas propuestas.
        </Mensaje>
      )}

      {pendientes.length > 0 && (
        <ul className="propuestas">
          {pendientes.map((e) => (
            <li key={e.id} className="propuesta equipo">
              <div className="cabecera">
                <span className="criterio">{e.equipment_type}</span>
                <span className="valor">
                  {/* Sin cantidad se dice «sin cantidad», no «1». Un uno en un
                      inventario se lee después como cierto. */}
                  {e.quantity === null ? (
                    <span className="ayuda">sin cantidad</span>
                  ) : (
                    `${Number(e.quantity)} ${e.unit}`
                  )}
                </span>
              </div>
              <p className="detalle">
                {e.technical_system_name ?? 'sin sistema técnico'}
                {e.documento && <> · Sale de «{e.documento}»</>}
                {e.seccion && <> · {e.seccion}</>}
              </p>
              {e.evidencia && <blockquote className="evidencia">{e.evidencia}</blockquote>}

              <div className="destino">
                <label>
                  Activo
                  <select
                    value={destino[e.id] ?? activos[0]?.id ?? ''}
                    onChange={(ev) => setDestino((d) => ({ ...d, [e.id]: ev.target.value }))}
                  >
                    {activos.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Revisión cada (meses)
                  <input
                    type="number"
                    min={1}
                    max={600}
                    placeholder="opcional"
                    value={meses[e.id] ?? ''}
                    onChange={(ev) => setMeses((m) => ({ ...m, [e.id]: ev.target.value }))}
                  />
                </label>
              </div>

              <div className="decidir">
                <button
                  type="button"
                  onClick={() => void decidir(e, true)}
                  disabled={ocupado || activos.length === 0}
                >
                  Añadir al inventario
                </button>
                <button type="button" onClick={() => void decidir(e, false)} disabled={ocupado}>
                  Descartar
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {aceptados.length > 0 && (
        <details className="decididas" open>
          <summary>{aceptados.length} añadido(s) al inventario</summary>
          <ul>
            {aceptados.map((e) => (
              <li key={e.id}>
                <strong>{e.equipment_type}</strong>
                {e.quantity !== null && ` × ${Number(e.quantity)} ${e.unit}`}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

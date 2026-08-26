import { useCallback, useEffect, useState } from 'react'
import { enviar, obtener, subirFichero } from '../api/cliente'
import type {
  CategoriaDeSolicitud,
  Documento,
  EstadoSolicitud,
  ObservacionIa,
  PermisoDeRevision,
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

export function PestanaDocumentacion({ projectId }: { projectId: string }) {
  const [lineas, setLineas] = useState<Solicitud[] | null>(null)
  const [categorias, setCategorias] = useState<CategoriaDeSolicitud[]>([])
  const [documentos, setDocumentos] = useState<Documento[]>([])
  const [permiso, setPermiso] = useState<PermisoDeRevision | null>(null)
  const [error, setError] = useState<string | null>(null)

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
  alCambiar,
  alFallar,
}: {
  linea: Solicitud
  documentos: Documento[]
  projectId: string
  revisionActiva: boolean
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
  alFallar,
}: {
  documento: Documento
  revisionActiva: boolean
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

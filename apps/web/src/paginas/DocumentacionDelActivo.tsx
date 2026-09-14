import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { descargar, enviar, obtener, subirFichero } from '../api/cliente'
import type { DocumentoDeCasilla, EstadoSolicitud, NodoDocumental } from '../api/tipos'
import { Mensaje } from '../ui/Marco'

/**
 * La documentación **de un activo** `[REQ]` §3.2 b de `docs/23`.
 *
 * Es el árbol de la hoja v2 del cliente: **73 nodos en tres niveles**, de los
 * que 60 no tienen hijos. Un nodo sin hijos es una **casilla** y lleva estado,
 * motivo cuando no hay documento, y los ficheros colgando. Los otros 13 solo
 * agrupan, y por eso no ofrecen estado: marcar «Licencias urbanísticas» como
 * recibida cuando cuelgan cuatro licencias no dice nada de ninguna de las
 * cuatro.
 *
 * ## Seis situaciones, no cinco
 *
 * Una casilla sin tocar **no tiene fila en la base**, y eso es lo normal: el
 * árbol empieza entero sin pedir. Crear sesenta filas vacías por activo habría
 * llenado la tabla de ruido para no decir nada.
 *
 * | En pantalla | En la base |
 * |---|---|
 * | Pendiente de pedir | no hay fila |
 * | Solicitada | `SOLICITADA` |
 * | Recibida | `RECIBIDA` |
 * | Recibida en parte | `PARCIAL` |
 * | No disponible | `NO_DISPONIBLE` |
 * | No aplica | `NO_APLICA` |
 *
 * `[REC]` **«Recibida en parte» no estaba en la hoja del cliente**, que define
 * cuatro estados. Se mantiene porque cuenta como limitación del informe igual
 * que «no disponible»: recibir tres de los ocho boletines eléctricos no es
 * haberlos recibido. `[PDV]` Sin validar con el cliente.
 *
 * ## Qué se abre y qué no
 *
 * Las ramas nacen **plegadas** y se abren solas las que ya tienen algo. Son 73
 * nodos con nombres de hasta trescientos caracteres: abiertos de golpe es una
 * pantalla de varios metros donde no se encuentra nada.
 *
 * `[LIM]` La checklist **del proyecto** sigue en su pestaña y no se ha
 * fusionado con esto. Son dos cosas distintas aunque compartan tabla: allí se
 * piden documentos sueltos con su propio título al inicio del encargo; aquí se
 * repasa activo por activo el árbol completo. Unificarlas es una decisión de
 * producto que no se ha tomado.
 */

/** Los estados que se pueden elegir, con la palabra que se lee en pantalla. */
const ESTADOS: ReadonlyArray<readonly [EstadoSolicitud, string]> = [
  ['SOLICITADA', 'Solicitada'],
  ['RECIBIDA', 'Recibida'],
  ['PARCIAL', 'Recibida en parte'],
  ['NO_DISPONIBLE', 'No disponible'],
  ['NO_APLICA', 'No aplica'],
]

/** Lo que se lee mientras la casilla no tiene fila en la base. */
const SIN_PEDIR = 'Pendiente de pedir'

/** El código como identificador de CSS y de `aria-controls`: `S1.2.1` no vale.
 *
 * Las ramas y las casillas llevan **prefijos distintos**. Con uno solo, el
 * `<ul>` de la rama `S1.1` y la ficha de la casilla `S1.1` —que nunca existen a
 * la vez, pero el selector no lo sabe— se llamaban igual, y buscar la casilla
 * `S1.1` encontraba la lista de sus hijos. */
function ancla(code: string): string {
  return `doc-${code.replace(/\./g, '-')}`
}

function anclaDeRama(code: string): string {
  return `hijos-${ancla(code)}`
}

export function DocumentacionDelActivo({
  projectId,
  assetId,
}: {
  projectId: string
  assetId: string
}) {
  const [nodos, setNodos] = useState<NodoDocumental[] | null>(null)
  const [abiertos, setAbiertos] = useState<Set<string> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [trabajando, setTrabajando] = useState(false)

  const recargar = useCallback(
    () => obtener<NodoDocumental[]>(`/assets/${assetId}/doc-tree`).then(setNodos),
    [assetId],
  )

  useEffect(() => {
    setNodos(null)
    setAbiertos(null)
    recargar().catch((e: Error) => setError(e.message))
  }, [recargar])

  /** Los hijos de cada nodo, una sola vez, para no recorrer 73 por cada rama. */
  const hijos = useMemo(() => {
    const mapa = new Map<string | null, NodoDocumental[]>()
    for (const n of nodos ?? []) {
      const lista = mapa.get(n.parent_code) ?? []
      lista.push(n)
      mapa.set(n.parent_code, lista)
    }
    return mapa
  }, [nodos])

  /** Qué hay debajo de un nodo: cuántas casillas y cuántas están resueltas. */
  const resumen = useCallback(
    (n: NodoDocumental): { casillas: number; hechas: number; limita: number; docs: number } => {
      if (n.es_casilla) {
        return {
          casillas: 1,
          hechas: n.status === 'RECIBIDA' || n.status === 'NO_APLICA' ? 1 : 0,
          limita: n.limita_el_informe ? 1 : 0,
          docs: n.documentos.length,
        }
      }
      const total = { casillas: 0, hechas: 0, limita: 0, docs: 0 }
      for (const h of hijos.get(n.code) ?? []) {
        const r = resumen(h)
        total.casillas += r.casillas
        total.hechas += r.hechas
        total.limita += r.limita
        total.docs += r.docs
      }
      return total
    },
    [hijos],
  )

  // Se abre lo que ya tiene trabajo hecho, y **una sola vez**: reabrirlo en cada
  // recarga cerraría de golpe la rama que alguien acaba de desplegar a mano.
  useEffect(() => {
    if (abiertos !== null || !nodos?.length) return
    const abrir = new Set<string>()
    for (const n of nodos) {
      if (n.es_casilla && (n.status !== null || n.documentos.length > 0)) {
        let padre = n.parent_code
        while (padre) {
          abrir.add(padre)
          padre = nodos.find((x) => x.code === padre)?.parent_code ?? null
        }
      }
    }
    setAbiertos(abrir)
  }, [abiertos, nodos])

  function alternar(code: string) {
    setAbiertos((previos) => {
      const siguiente = new Set(previos ?? [])
      if (siguiente.has(code)) siguiente.delete(code)
      else siguiente.add(code)
      return siguiente
    })
  }

  const fijar = useCallback(
    async (nodo: NodoDocumental, status: EstadoSolicitud, motivo: string) => {
      // `NO_DISPONIBLE` sin motivo lo rechaza la base. Se pregunta antes de
      // enviarlo para que llegue como una petición y no como un error.
      if (status === 'NO_DISPONIBLE' && !motivo.trim()) {
        setError(
          'Marcar «no disponible» exige decir por qué: es lo que explica la limitación en el informe.',
        )
        return
      }
      setTrabajando(true)
      try {
        await enviar(
          `/assets/${assetId}/doc-tree/${nodo.code}`,
          { status, unavailable_reason: motivo.trim() || null },
          'PUT',
          nodo.row_version ?? undefined,
        )
        await recargar()
        setError(null)
        setAviso(`${nodo.code} · ${ESTADOS.find(([e]) => e === status)?.[1] ?? status}`)
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setTrabajando(false)
      }
    },
    [assetId, recargar],
  )

  const adjuntar = useCallback(
    async (nodo: NodoDocumental, ficheros: File[]) => {
      setTrabajando(true)
      try {
        // Si la casilla no tiene fila todavía, adjuntar la crea: subir un
        // documento a una casilla ES recibirlo, y obligar a marcar el estado
        // antes sería pedir dos gestos para una sola cosa.
        let item = nodo.item_id
        if (item === null) {
          const creada = await enviar<NodoDocumental>(
            `/assets/${assetId}/doc-tree/${nodo.code}`,
            { status: 'RECIBIDA', unavailable_reason: null },
            'PUT',
          )
          item = creada.item_id
        }
        for (const archivo of ficheros) {
          await subirFichero(`/projects/${projectId}/documents`, archivo, {
            asset_id: assetId,
            doc_request_item_id: item ?? undefined,
          })
        }
        await recargar()
        setError(null)
        setAviso(
          `${ficheros.length} documento${ficheros.length === 1 ? '' : 's'} en ${nodo.code}`,
        )
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setTrabajando(false)
      }
    },
    [assetId, projectId, recargar],
  )

  if (error && nodos === null) return <Mensaje tipo="error">{error}</Mensaje>
  if (nodos === null) return <p className="cargando">Cargando el árbol documental…</p>

  const casillas = nodos.filter((n) => n.es_casilla)
  const pedidas = casillas.filter((n) => n.status !== null).length
  const limitan = casillas.filter((n) => n.limita_el_informe).length

  return (
    <section className="arbol-documental" aria-busy={trabajando}>
      {error && <Mensaje tipo="error">{error}</Mensaje>}
      {/* `role="status"` y no un `<p>` suelto: sin él, un lector de pantalla no
          se entera de que la casilla se ha guardado. Y el párrafo está SIEMPRE
          en el árbol, vacío o no, porque una región viva que aparece al mismo
          tiempo que su texto no se anuncia. Lo que cambia es la clase: sin
          aviso no pinta la franja verde, que si no queda de adorno permanente
          encima del árbol. */}
      <p className={aviso ? 'mensaje ok' : 'aviso-vacio'} role="status">
        {aviso ?? ''}
      </p>

      <p className="ayuda">
        El árbol acordado con el cliente: <strong>{nodos.length} nodos</strong> y{' '}
        <strong>{casillas.length} casillas</strong>. Van tocadas {pedidas}, y{' '}
        {limitan === 0
          ? 'ninguna entra hoy en las limitaciones del informe'
          : `${limitan} ${limitan === 1 ? 'entra' : 'entran'} en las limitaciones del informe`}
        . Las que no tienen estado están pendientes de pedir.
      </p>

      <ul className="ramas-doc">
        {(hijos.get(null) ?? []).map((raiz) => (
          <Rama
            key={raiz.code}
            nodo={raiz}
            hijos={hijos}
            abiertos={abiertos ?? new Set()}
            resumen={resumen}
            trabajando={trabajando}
            alAlternar={alternar}
            alFijar={fijar}
            alAdjuntar={adjuntar}
          />
        ))}
      </ul>
    </section>
  )
}

function Rama({
  nodo,
  hijos,
  abiertos,
  resumen,
  trabajando,
  alAlternar,
  alFijar,
  alAdjuntar,
}: {
  nodo: NodoDocumental
  hijos: Map<string | null, NodoDocumental[]>
  abiertos: Set<string>
  resumen: (n: NodoDocumental) => {
    casillas: number
    hechas: number
    limita: number
    docs: number
  }
  trabajando: boolean
  alAlternar: (code: string) => void
  alFijar: (n: NodoDocumental, e: EstadoSolicitud, motivo: string) => Promise<void>
  alAdjuntar: (n: NodoDocumental, ficheros: File[]) => Promise<void>
}) {
  if (nodo.es_casilla) {
    return (
      <li className="casilla-doc">
        <Casilla
          nodo={nodo}
          trabajando={trabajando}
          alFijar={alFijar}
          alAdjuntar={alAdjuntar}
        />
      </li>
    )
  }

  const abierto = abiertos.has(nodo.code)
  const r = resumen(nodo)
  return (
    <li className="rama-doc">
      <button
        type="button"
        className={`cabecera-doc n${nodo.level} ${r.hechas > 0 ? 'con-algo' : ''}`}
        aria-expanded={abierto}
        aria-controls={anclaDeRama(nodo.code)}
        onClick={() => alAlternar(nodo.code)}
      >
        <span aria-hidden="true" className="flecha">
          {abierto ? '▾' : '▸'}
        </span>
        <span className="codigo">{nodo.code}</span>
        <span className="nombre-doc">{nodo.name_es}</span>
        <span className="marca-doc">
          {r.hechas}/{r.casillas}
          {r.docs > 0 && ` · ${r.docs} doc${r.docs === 1 ? '' : 's'}`}
          {r.limita > 0 && ` · ${r.limita} limita`}
        </span>
      </button>
      <ul id={anclaDeRama(nodo.code)} hidden={!abierto}>
        {(hijos.get(nodo.code) ?? []).map((h) => (
          <Rama
            key={h.code}
            nodo={h}
            hijos={hijos}
            abiertos={abiertos}
            resumen={resumen}
            trabajando={trabajando}
            alAlternar={alAlternar}
            alFijar={alFijar}
            alAdjuntar={alAdjuntar}
          />
        ))}
      </ul>
    </li>
  )
}

function Casilla({
  nodo,
  trabajando,
  alFijar,
  alAdjuntar,
}: {
  nodo: NodoDocumental
  trabajando: boolean
  alFijar: (n: NodoDocumental, e: EstadoSolicitud, motivo: string) => Promise<void>
  alAdjuntar: (n: NodoDocumental, ficheros: File[]) => Promise<void>
}) {
  const [motivo, setMotivo] = useState(nodo.unavailable_reason ?? '')
  const entrada = useRef<HTMLInputElement | null>(null)

  // El motivo que viene del servidor gana cuando cambia por fuera —otra
  // pestaña, otra persona—, pero no mientras se teclea: el efecto solo mira el
  // valor guardado, así que un guardado propio no borra lo escrito después.
  useEffect(() => {
    setMotivo(nodo.unavailable_reason ?? '')
  }, [nodo.unavailable_reason])

  function elegir(valor: string) {
    if (valor === '') return
    void alFijar(nodo, valor as EstadoSolicitud, motivo)
  }

  function soltar(lista: FileList | null) {
    // La `FileList` de un `<input>` es **viva**: se copia antes de limpiar el
    // campo, o al llegar a la subida ya no queda ningún fichero dentro.
    const ficheros = [...(lista ?? [])]
    if (entrada.current) entrada.current.value = ''
    if (ficheros.length) void alAdjuntar(nodo, ficheros)
  }

  const estado = nodo.status
  return (
    <div
      className={`ficha-doc e-${(estado ?? 'sin-pedir').toLowerCase()}`}
      id={ancla(nodo.code)}
    >
      <div className="cabecera-casilla">
        <span className="codigo">{nodo.code}</span>
        <span className="nombre-doc">{nodo.name_es}</span>
      </div>

      <div className="mandos-casilla">
        <label className="campo-linea">
          Estado
          <select
            value={estado ?? ''}
            disabled={trabajando}
            onChange={(e) => elegir(e.target.value)}
            aria-label={`Estado de ${nodo.code}`}
          >
            {/* La opción vacía solo existe mientras no hay estado: una vez
                puesto no se puede volver a «sin pedir», porque la fila ya
                existe y fingir que no sería mentirle a quien mire después. */}
            {estado === null && <option value="">{SIN_PEDIR}</option>}
            {ESTADOS.map(([valor, texto]) => (
              <option key={valor} value={valor}>
                {texto}
              </option>
            ))}
          </select>
        </label>

        {/* El `<input type=file>` nativo y a la vista, como en la checklist del
            proyecto: un botón bonito que esconde el campo real cuesta un trozo
            de CSS frágil y una trampa de accesibilidad a cambio de nada. */}
        <label className="subir-casilla">
          Adjuntar
          <input
            ref={entrada}
            type="file"
            multiple
            disabled={trabajando}
            onChange={(e) => soltar(e.target.files)}
            aria-label={`Adjuntar documentos a ${nodo.code}`}
          />
        </label>

        {nodo.received_at && (
          <span className="pastilla">Recibida el {nodo.received_at.slice(0, 10)}</span>
        )}
      </div>

      {estado === 'NO_DISPONIBLE' && (
        <label className="campo">
          Por qué no está disponible
          <textarea
            rows={2}
            value={motivo}
            disabled={trabajando}
            onChange={(e) => setMotivo(e.target.value)}
            onBlur={() => {
              if (motivo.trim() !== (nodo.unavailable_reason ?? '')) {
                void alFijar(nodo, 'NO_DISPONIBLE', motivo)
              }
            }}
          />
        </label>
      )}

      {nodo.limita_el_informe && (
        <p className="limitacion">
          Esta casilla entra en las limitaciones del informe: declarar lo que no se ha podido
          revisar es una obligación profesional en una TDD.
        </p>
      )}

      {nodo.documentos.length > 0 && (
        <ul className="adjuntos-doc">
          {nodo.documentos.map((d) => (
            <Adjunto key={d.id} documento={d} />
          ))}
        </ul>
      )}
    </div>
  )
}

function Adjunto({ documento }: { documento: DocumentoDeCasilla }) {
  const [bajando, setBajando] = useState(false)
  return (
    <li>
      <button
        type="button"
        className="enlace"
        disabled={bajando}
        onClick={() => {
          setBajando(true)
          void descargar(`/documents/${documento.id}/download`, documento.display_name).finally(
            () => setBajando(false),
          )
        }}
      >
        {documento.display_name}
      </button>
      <span className="pastilla">v{documento.version_number}</span>
      {/* `[REQ]` §15.6 · Un RESTRINGIDO no va a ninguna IA, y quien mira la
          lista tiene que poder verlo sin abrir la ficha. */}
      <span
        className={`pastilla ${documento.confidentiality === 'RESTRINGIDO' ? 'aviso' : ''}`}
      >
        {documento.confidentiality.toLowerCase()}
      </span>
      <span className="fecha">{documento.uploaded_at.slice(0, 10)}</span>
    </li>
  )
}

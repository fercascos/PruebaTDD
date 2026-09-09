import { useCallback, useEffect, useMemo, useState } from 'react'
import { obtener } from '../api/cliente'
import type { CodigoCapex, ElementoCatalogo, Hallazgo } from '../api/tipos'
import { euros } from '../graficos/formato'
import { Mensaje, Vacio } from '../ui/Marco'
import { FichaDeHallazgo } from './FichaDeHallazgo'
import { NuevoHallazgo } from './NuevoHallazgo'

/**
 * El CAPEX de **un activo**, como árbol `[REQ]` §3.2 e de `docs/23`.
 *
 * Tipo de coste → categoría → objeto, y colgando de cada objeto las actuaciones
 * que se le han codificado. Es lo que pidió el cliente: *«separar cada actuación
 * en función de las distintas categorías, como un diagrama de árbol»*.
 *
 * ## Qué añade sobre la rejilla de Hallazgos y CAPEX
 *
 * La rejilla es una lista corrida por proyecto y contesta «qué hay que hacer».
 * Esta pantalla contesta **«qué le pasa a este edificio, y por dónde»**, que es
 * la pregunta con la que se recorre un activo: se mira Electricidad, se ve que
 * pesa, se abre y se comprueba de qué objetos sale. Con la lista corrida eso
 * exige filtrar dos veces y sumar a mano.
 *
 * ## Solo salen las ramas con contenido
 *
 * El catálogo tiene 175 nodos y un activo normal toca diez o quince. Pintar el
 * árbol entero obligaría a buscar lo que hay entre lo que no hay, que es
 * exactamente el trabajo que esta pantalla ahorra. Las ramas se construyen
 * **desde las actuaciones hacia arriba**, así que un tipo de coste sin nada no
 * aparece.
 *
 * `[REC]` Es la decisión contraria a la de los cortes del dashboard, donde los
 * cinco plazos y los cuatro grados de riesgo **sí** salen con cero. No es una
 * incoherencia: allí la lista es corta y cerrada, y un plazo que desaparece se
 * confunde con uno que no toca; aquí la lista tiene 175 entradas y enseñarlas
 * todas no informa de nada.
 *
 * ## Los códigos retirados no se tragan
 *
 * `[LIM]` `/catalogs/capex-codes` no devuelve los códigos con `deprecated_at`, y
 * hay actuaciones que apuntan a ellos: la migración `0020` deprecó siete objetos
 * «General» al adoptar el árbol del cliente, y un informe emitido tiene que
 * seguir resolviéndolos. Una actuación así **no encuentra su nodo**, y dejarla
 * fuera del árbol en silencio descuadraría el total del activo contra el
 * dashboard. Van a una rama propia, **«Código retirado»**, con su aviso.
 *
 * ## Escribir desde el árbol
 *
 * Cada objeto lleva su «Añadir actuación», que abre el alta **con ese código ya
 * puesto**. Sin eso, quien está mirando «Electricidad › CGBT» y quiere anotar
 * algo tiene que volver a buscar ese código en una lista de 141, que es la mejor
 * forma de que acabe en el nodo de al lado. Y el título de cada actuación abre
 * su ficha: el árbol es una forma de entrar al dato, no un segundo editor.
 */

/** Los cinco plazos, en el orden de la plantilla. */
const PLAZOS = [
  ['CORTO', 'Corto'],
  ['MEDIO', 'Medio'],
  ['LARGO', 'Largo'],
  ['MEJORAS', 'Mejoras'],
  ['OTRO', 'Otro'],
] as const

/**
 * `[SUP]` El orden de los tipos de coste, que es el de la hoja del cliente.
 *
 * `capex_code` **no tiene columna de orden** y la API los devuelve por código,
 * que alfabéticamente pone ESG delante de Hard Cost. Añadir la columna sería una
 * migración por un asunto de presentación; los que no estén aquí van al final,
 * por código, así que un tipo nuevo no desaparece.
 */
const ORDEN_DE_TIPO = ['HC', 'SC', 'OP', 'MA', 'ESG', 'IMP']

/** La rama de los códigos que ya no están en el catálogo. Ver la cabecera. */
const RETIRADO = 'RETIRADO'

type Nodo = {
  /** El `id` del código, o `RETIRADO`. */
  clave: string
  code: string
  nombre: string
  nivel: number
  hijos: Nodo[]
  /** Las actuaciones codificadas **en este nodo**, no en sus hijos. */
  actuaciones: Hallazgo[]
  /** Importe del subárbol, por plazo y en total. */
  porPlazo: Record<string, number>
  total: number
  /** Cuántas actuaciones cuelgan del subárbol. */
  cuantas: number
}

export function ArbolDeCapex({ projectId, assetId }: { projectId: string; assetId: string }) {
  const [hallazgos, setHallazgos] = useState<Hallazgo[] | null>(null)
  const [codigos, setCodigos] = useState<CodigoCapex[]>([])
  const [zonas, setZonas] = useState<ElementoCatalogo[]>([])
  const [riesgos, setRiesgos] = useState<ElementoCatalogo[]>([])
  const [conceptos, setConceptos] = useState<ElementoCatalogo[]>([])
  const [error, setError] = useState<string | null>(null)
  const [abierto, setAbierto] = useState<Hallazgo | null>(null)
  /** El código bajo el que se está dando de alta una actuación, si es que sí. */
  const [creandoEn, setCreandoEn] = useState<string | null>(null)

  const recargar = useCallback(() => {
    obtener<Hallazgo[]>(`/projects/${projectId}/findings?asset_id=${assetId}`)
      .then(setHallazgos)
      .catch((e: Error) => setError(e.message))
  }, [projectId, assetId])

  useEffect(recargar, [recargar])

  useEffect(() => {
    // Los catálogos son la otra mitad: la API devuelve identificadores y aquí
    // hacen falta nombres. Si alguno falla, el árbol sigue siendo útil con el
    // identificador a la vista, así que no se tumba la pantalla por eso.
    obtener<CodigoCapex[]>('/catalogs/capex-codes')
      .then(setCodigos)
      .catch(() => setCodigos([]))
    obtener<ElementoCatalogo[]>('/catalogs/zones')
      .then(setZonas)
      .catch(() => setZonas([]))
    obtener<ElementoCatalogo[]>('/catalogs/risk-levels')
      .then(setRiesgos)
      .catch(() => setRiesgos([]))
    obtener<ElementoCatalogo[]>('/catalogs/capex-concepts')
      .then(setConceptos)
      .catch(() => setConceptos([]))
  }, [])

  const nombreDe = useMemo(() => {
    const de = (lista: ElementoCatalogo[]) => new Map(lista.map((e) => [e.id, e]))
    return { zona: de(zonas), riesgo: de(riesgos), concepto: de(conceptos) }
  }, [zonas, riesgos, conceptos])

  const raices = useMemo(
    () => (hallazgos ? construir(hallazgos, codigos) : []),
    [hallazgos, codigos],
  )

  /**
   * Dónde se puede codificar: **una hoja del catálogo**, no del árbol dibujado.
   *
   * Son cosas distintas y confundirlas ofrecería el alta en el sitio
   * equivocado: aquí solo se dibujan las ramas con contenido, así que una
   * categoría con quince objetos de los que solo uno tiene actuaciones parece
   * tener un único hijo. Se pregunta al catálogo, que es quien sabe si ese nodo
   * tiene objetos por debajo.
   *
   * Es la misma regla que aplica el alta: en soft costs, operativos e
   * imprevistos la categoría **es** la hoja, porque no tienen objetos.
   */
  const esHoja = useMemo(() => {
    const conHijos = new Set(codigos.map((c) => c.parent_id).filter(Boolean))
    return (clave: string) => !conHijos.has(clave)
  }, [codigos])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!hallazgos) return <p className="cargando">Cargando el CAPEX del activo…</p>

  if (abierto) {
    return (
      <FichaDeHallazgo
        hallazgo={abierto}
        alGuardar={() => {
          setAbierto(null)
          recargar()
        }}
        alCerrar={() => setAbierto(null)}
      />
    )
  }

  if (creandoEn) {
    return (
      <NuevoHallazgo
        projectId={projectId}
        activoInicial={assetId}
        codigoInicial={creandoEn}
        alGuardar={() => {
          setCreandoEn(null)
          recargar()
        }}
        alCancelar={() => setCreandoEn(null)}
      />
    )
  }

  const total = raices.reduce((s, n) => s + n.total, 0)

  return (
    <section className="arbol-capex">
      <h3>CAPEX del activo</h3>
      <p className="ayuda">
        Tipo de coste → categoría → objeto. Solo se dibujan las ramas que tienen algo: el
        catálogo trae 175 nodos y un activo toca unos pocos.
      </p>

      {hallazgos.length === 0 ? (
        <Vacio>
          Este activo todavía no tiene actuaciones. Se registran desde «Hallazgos y CAPEX»,
          desde una fotografía de la visita, o aquí mismo cuando el árbol tenga ramas.
        </Vacio>
      ) : (
        <>
          <p className="alcance">
            <strong>{hallazgos.length}</strong>{' '}
            {hallazgos.length === 1 ? 'actuación' : 'actuaciones'} ·{' '}
            <strong>{euros.format(total)}</strong>
          </p>
          <ul className="ramas">
            {raices.map((n) => (
              <Rama
                key={n.clave}
                nodo={n}
                nombreDe={nombreDe}
                esHoja={esHoja}
                alAbrir={setAbierto}
                alCrear={setCreandoEn}
              />
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

type Nombres = {
  zona: Map<string, ElementoCatalogo>
  riesgo: Map<string, ElementoCatalogo>
  concepto: Map<string, ElementoCatalogo>
}

/**
 * Una rama del árbol, con sus hijos y sus actuaciones.
 *
 * `<details open>` y no un desplegable propio: trae el teclado, el foco y el
 * anuncio del estado hechos, y además el navegador lo imprime abierto. Un `div`
 * con un `onClick` habría que enseñarle las tres cosas.
 */
function Rama({
  nodo,
  nombreDe,
  esHoja,
  alAbrir,
  alCrear,
}: {
  nodo: Nodo
  nombreDe: Nombres
  esHoja: (clave: string) => boolean
  alAbrir: (h: Hallazgo) => void
  alCrear: (codigoId: string) => void
}) {
  const retirado = nodo.clave === RETIRADO
  return (
    <li className={`rama nivel-${nodo.nivel}`}>
      <details open>
        <summary>
          <span className="nodo">
            {!retirado && <span className="codigo">{nodo.code}</span>}
            <span className="nombre">{nodo.nombre}</span>
          </span>
          <span className="cifra">
            {nodo.cuantas} {nodo.cuantas === 1 ? 'actuación' : 'actuaciones'}
          </span>
          <span className="cifra importe">{euros.format(nodo.total)}</span>
        </summary>

        {retirado && (
          <Mensaje tipo="aviso">
            Estas actuaciones están codificadas en códigos que ya no se ofrecen. Siguen contando
            en los totales —por eso salen aquí y no desaparecen—, pero conviene recodificarlas:
            al exportar, la plantilla no sabe en qué bloque ponerlas.
          </Mensaje>
        )}

        {nodo.hijos.length > 0 && (
          <ul className="ramas">
            {nodo.hijos.map((h) => (
              <Rama
                key={h.clave}
                nodo={h}
                nombreDe={nombreDe}
                esHoja={esHoja}
                alAbrir={alAbrir}
                alCrear={alCrear}
              />
            ))}
          </ul>
        )}

        {nodo.actuaciones.length > 0 && (
          <TablaDeActuaciones
            actuaciones={nodo.actuaciones}
            nombreDe={nombreDe}
            alAbrir={alAbrir}
          />
        )}

        {/* El alta cuelga de donde se puede codificar: una hoja del catálogo.
            De `HC` no, que no es un sitio; y de `HC.H09` tampoco, porque tiene
            objetos y codificar en la categoría teniendo el objeto delante es
            perder el detalle que el desglose del dashboard iba a enseñar. */}
        {!retirado && nodo.nivel >= 2 && esHoja(nodo.clave) && (
          <p className="anadir-aqui">
            <button type="button" className="enlace" onClick={() => alCrear(nodo.clave)}>
              Añadir actuación en {nodo.code}
            </button>
          </p>
        )}
      </details>
    </li>
  )
}

/**
 * Las actuaciones de un nodo, con **los campos que pidió el cliente**:
 * descripción, zona afectada, riesgo, comentarios del gestor técnico, CAPEX por
 * plazo con su total, el concepto y si es repercutible a inquilinos.
 *
 * `[REC]` La descripción y los comentarios van **bajo el título** y no en dos
 * columnas más. Son texto libre de longitud imprevisible: en columna estirarían
 * la fila hasta que las cifras, que es lo que se compara, dejaran de estar una
 * debajo de otra. La tabla ya tiene once columnas.
 */
function TablaDeActuaciones({
  actuaciones,
  nombreDe,
  alAbrir,
}: {
  actuaciones: Hallazgo[]
  nombreDe: Nombres
  alAbrir: (h: Hallazgo) => void
}) {
  const suma = (plazo?: string) =>
    actuaciones
      .flatMap((h) => h.capex_lines)
      .filter((l) => !plazo || l.time_horizon_code === plazo)
      .reduce((a, l) => a + Number(l.amount), 0)

  return (
    <div className="desbordable">
      <table className="tabla actuaciones">
        <thead>
          <tr>
            <th scope="col">Actuación</th>
            <th scope="col">Zona afectada</th>
            <th scope="col">Riesgo</th>
            <th scope="col">Concepto</th>
            <th scope="col">Repercutible</th>
            {PLAZOS.map(([codigo, etiqueta]) => (
              <th key={codigo} scope="col" className="numerica">
                {etiqueta}
              </th>
            ))}
            <th scope="col" className="numerica">
              Total
            </th>
          </tr>
        </thead>
        <tbody>
          {actuaciones.map((h) => {
            const porPlazo = new Map(h.capex_lines.map((l) => [l.time_horizon_code, l]))
            const riesgo = h.risk_level_id ? nombreDe.riesgo.get(h.risk_level_id) : undefined
            return (
              <tr key={h.id}>
                <th scope="row">
                  <button type="button" className="enlace" onClick={() => alAbrir(h)}>
                    {h.title}
                  </button>
                  {h.capex_lines.length > 1 && <em className="ayuda"> · recurrente</em>}
                  {h.description && <span className="ayuda descripcion">{h.description}</span>}
                  {h.comments && (
                    <span className="ayuda descripcion">
                      <strong>Comentarios:</strong> {h.comments}
                    </span>
                  )}
                </th>
                <td>{nombreDe.zona.get(h.zone_id)?.name_es ?? '—'}</td>
                <td>
                  {riesgo ? (
                    /* `[REQ]` El grado va escrito, con su código. El color solo
                       acompaña: esto se imprime en blanco y negro. */
                    <span className={`marca-grado grado-${riesgo.code.toLowerCase()}`} />
                  ) : null}
                  {riesgo ? `${riesgo.code} · ${riesgo.name_es}` : '—'}
                </td>
                <td>
                  {h.capex_concept_id
                    ? (nombreDe.concepto.get(h.capex_concept_id)?.name_es ?? '—')
                    : '—'}
                </td>
                <td>{REPERCUTIBLE[h.tenant_recoverable] ?? h.tenant_recoverable}</td>
                {PLAZOS.map(([codigo]) => {
                  const linea = porPlazo.get(codigo)
                  return (
                    <td key={codigo} className="numerica">
                      {linea ? euros.format(Number(linea.amount)) : '—'}
                    </td>
                  )
                })}
                <td className="numerica">
                  <strong>{euros.format(Number(h.total_amount))}</strong>
                </td>
              </tr>
            )
          })}
        </tbody>
        {/* Con una sola actuación el pie repetiría su fila palabra por palabra.
            Un total que solo puede coincidir con lo de arriba no es un total:
            es ruido en una tabla que ya tiene once columnas. */}
        {actuaciones.length > 1 && (
          <tfoot>
            <tr>
              <td colSpan={5}>Total del nodo</td>
              {PLAZOS.map(([codigo]) => (
                <td key={codigo} className="numerica">
                  {suma(codigo) ? euros.format(suma(codigo)) : '—'}
                </td>
              ))}
              <td className="numerica">
                <strong>{euros.format(suma())}</strong>
              </td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}

/** Cómo se lee `tenant_recoverable` en pantalla. */
const REPERCUTIBLE: Record<string, string> = {
  SI: 'Sí',
  NO: 'No',
  NA: 'N. A.',
}

/**
 * Monta el árbol **desde las actuaciones hacia arriba**.
 *
 * Se recorre cada actuación, se busca su código y se sube por `parent_id`
 * creando los nodos que falten. Así solo existen las ramas con contenido, y los
 * importes se acumulan por el camino: el total de una categoría **es** la suma
 * de lo que cuelga de ella, no un número calculado aparte que pueda discrepar.
 */
export function construir(hallazgos: Hallazgo[], codigos: CodigoCapex[]): Nodo[] {
  const porId = new Map(codigos.map((c) => [c.id, c]))
  const nodos = new Map<string, Nodo>()
  const raices: Nodo[] = []

  const crear = (clave: string, code: string, nombre: string, nivel: number): Nodo => ({
    clave,
    code,
    nombre,
    nivel,
    hijos: [],
    actuaciones: [],
    porPlazo: {},
    total: 0,
    cuantas: 0,
  })

  /** El nodo de un código, creándolo —y a sus padres— si hace falta. */
  const nodoDe = (id: string): Nodo => {
    const existente = nodos.get(id)
    if (existente) return existente
    const codigo = porId.get(id)
    if (!codigo) {
      // Código retirado, o de otra organización: una rama propia. Ver la
      // cabecera del módulo; lo que no puede es desaparecer.
      const retirado = nodos.get(RETIRADO) ?? crear(RETIRADO, '', 'Código retirado', 1)
      if (!nodos.has(RETIRADO)) {
        nodos.set(RETIRADO, retirado)
        raices.push(retirado)
      }
      return retirado
    }
    const nodo = crear(codigo.id, codigo.code, codigo.name_es, codigo.level)
    nodos.set(codigo.id, nodo)
    if (codigo.parent_id) {
      nodoDe(codigo.parent_id).hijos.push(nodo)
    } else {
      raices.push(nodo)
    }
    return nodo
  }

  for (const h of hallazgos) {
    const nodo = nodoDe(h.capex_code_id)
    nodo.actuaciones.push(h)
    // El importe sube por toda la rama: el total de un nodo es el de su
    // subárbol, que es lo que se lee en el resumen de la línea.
    const porPlazo: Record<string, number> = {}
    let total = 0
    for (const l of h.capex_lines) {
      const importe = Number(l.amount)
      porPlazo[l.time_horizon_code] = (porPlazo[l.time_horizon_code] ?? 0) + importe
      total += importe
    }
    for (let n: Nodo | undefined = nodo; n; n = padreDe(n, nodos, porId)) {
      n.cuantas += 1
      n.total += total
      for (const [plazo, importe] of Object.entries(porPlazo)) {
        n.porPlazo[plazo] = (n.porPlazo[plazo] ?? 0) + importe
      }
    }
  }

  ordenar(raices)
  return raices
}

/** El nodo del padre, si lo hay y si ya se ha creado. */
function padreDe(
  nodo: Nodo,
  nodos: Map<string, Nodo>,
  porId: Map<string, CodigoCapex>,
): Nodo | undefined {
  const codigo = porId.get(nodo.clave)
  return codigo?.parent_id ? nodos.get(codigo.parent_id) : undefined
}

/**
 * Ordena el árbol en su sitio: los tipos por el orden de la hoja del cliente y
 * el resto **por código**, que es como se lee una taxonomía y como está en su
 * Excel. Por importe ya ordena el dashboard, que es donde se pregunta cuál pesa
 * más; aquí se pregunta qué hay en H09.
 */
function ordenar(nodos: Nodo[]): void {
  nodos.sort((a, b) => {
    if (a.nivel === 1) {
      const ia = ORDEN_DE_TIPO.indexOf(a.code)
      const ib = ORDEN_DE_TIPO.indexOf(b.code)
      // Los que no están en la lista —un tipo nuevo, la rama de retirados— al
      // final, y entre ellos por código.
      if (ia !== ib)
        return (ia < 0 ? ORDEN_DE_TIPO.length : ia) - (ib < 0 ? ORDEN_DE_TIPO.length : ib)
    }
    return a.code.localeCompare(b.code, 'es')
  })
  for (const n of nodos) ordenar(n.hijos)
}

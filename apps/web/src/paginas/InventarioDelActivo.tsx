import { useCallback, useEffect, useMemo, useState } from 'react'
import { enviar, obtener } from '../api/cliente'
import { porTipoDeCoste } from '../api/tipos'
import type {
  CodigoCapex,
  Descriptivo,
  DescriptivosTraidos,
  Equipo,
  EsqueletoDeEquipos,
  Foto,
} from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

/**
 * El inventario **de un activo**, por categorías y objetos `[REQ]` §3.2 d.
 *
 * ## Por qué es un árbol y no una rejilla
 *
 * Lo pidió el cliente al revisar el prototipo: *«que aparezca todo el inventario
 * dividido por las distintas categorías y dentro de cada categoría incluir todos
 * sus objetos»*. Antes esto eran tres listas planas —descriptivos por un lado,
 * equipos por otro, fotos por otro— y nada ataba una cosa con la otra: había que
 * saberse de memoria que la enfriadora de la tabla de equipos era el objeto
 * `HC.H08.01` de la rejilla de descriptivos.
 *
 * Ahora **el árbol es el índice del trabajo**. Se recorre categoría a categoría
 * y dentro de cada objeto está todo lo que se sabe de él.
 *
 * ## Dos textos, y por qué no son uno
 *
 * * **Descriptivo** — *qué hay*. Sale de la memoria técnica, así que se trae con
 *   un botón: es dato leído de un documento.
 * * **Valoración** — *en qué estado está*. Eso no lo dice ningún documento: lo
 *   escribe quien ha ido a verlo.
 *
 * En el mismo párrafo nadie sabría medio año después qué se observó y qué se
 * copió, y traer el descriptivo otra vez borraría por delante el juicio del
 * técnico. Por eso son dos, y **traer solo toca el primero**.
 *
 * ## Qué se abre y qué no
 *
 * Las categorías nacen plegadas y **se abren solas las que ya tienen trabajo
 * hecho**. El árbol completo son ciento cuarenta y un objetos; abrirlos todos de
 * golpe es una pantalla de varios metros donde no se encuentra nada, y abrirlos
 * todos cerrados obliga a buscar a ciegas lo que uno ya había escrito.
 *
 * ## «Pasa a CAPEX», ahora sin adivinar
 *
 * Marcar sigue sin crear nada: se recorre el inventario marcando y las
 * actuaciones se generan todas de una vez. Lo que cambia es que ahora **cada
 * equipo cuelga de un objeto**, así que la actuación sabe dónde va. Antes el
 * capítulo se deducía del sistema técnico, y «Protección contra incendios» vale
 * `H06 + H10` —dos capítulos—: esos equipos no se podían generar. Preguntar el
 * objeto mientras se inventaría, con el equipo delante, resuelve la ambigüedad
 * donde hay alguien que sabe la respuesta.
 *
 * `[LIM]` Los equipos dados de alta antes de esto **no tienen objeto** y no se
 * les inventa uno: un capítulo tiene once objetos y elegir por ellos sería
 * adivinar dónde está la máquina. Salen agrupados al final, en «sin clasificar»,
 * con su desplegable para colocarlos.
 */

/** Lo que la pantalla guarda de un objeto mientras se teclea. */
type Borrador = { texto: string; valoracion: string; validado: boolean }

const VACIO: Borrador = { texto: '', valoracion: '', validado: false }

/** `[REQ]` Un equipo es una parte física del edificio: su objeto vive bajo Hard
 *  Cost. Un honorario o un imprevisto no se inventarían. */
const TIPO_DE_COSTE_FISICO = 'HC'

export function InventarioDelActivo({
  projectId,
  assetId,
}: {
  projectId: string
  assetId: string
}) {
  const [codigos, setCodigos] = useState<CodigoCapex[] | null>(null)
  const [descriptivos, setDescriptivos] = useState<Descriptivo[] | null>(null)
  const [equipos, setEquipos] = useState<Equipo[] | null>(null)
  const [fotos, setFotos] = useState<Foto[]>([])
  const [borradores, setBorradores] = useState<Record<string, Borrador>>({})
  const [abiertos, setAbiertos] = useState<Set<string> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string[] | null>(null)
  const [hecho, setHecho] = useState<string | null>(null)
  const [trabajando, setTrabajando] = useState(false)

  // Devuelve una promesa **a propósito**: «traer de la documentación» tiene que
  // esperarla antes de decir que ha terminado. Sin eso, la pantalla anunciaba
  // «hecho» con la rejilla todavía enseñando lo de antes, que es decirle a
  // alguien que su trabajo está guardado mientras mira datos viejos.
  const recargar = useCallback(() => {
    const descriptivos = obtener<Descriptivo[]>(`/assets/${assetId}/descriptivos`)
      .then((lista) => {
        setDescriptivos(lista)
        // Los borradores se rehacen desde lo guardado: dejar los de antes
        // enseñaría texto que el servidor no tiene, que es la peor forma de
        // creerse que algo está guardado.
        setBorradores(
          Object.fromEntries(
            lista.map((d) => [
              d.capex_code_id,
              { texto: d.texto, valoracion: d.valoracion, validado: d.validado },
            ]),
          ),
        )
      })
      .catch((e: Error) => setError(e.message))
    const equipos = obtener<Equipo[]>(`/projects/${projectId}/equipment?asset_id=${assetId}`)
      .then(setEquipos)
      .catch((e: Error) => setError(e.message))
    const fotos = obtener<Foto[]>(`/projects/${projectId}/photos?asset_id=${assetId}`)
      .then(setFotos)
      .catch(() => setFotos([]))
    return Promise.all([descriptivos, equipos, fotos])
  }, [projectId, assetId])

  useEffect(() => {
    void recargar()
  }, [recargar])

  useEffect(() => {
    obtener<CodigoCapex[]>('/catalogs/capex-codes')
      .then(setCodigos)
      .catch((e: Error) => setError(e.message))
  }, [])

  /** El árbol: raíces con objetos → capítulos con objetos → objetos. */
  const arbol = useMemo(() => {
    if (!codigos) return []
    const porPadre = new Map<string | null, CodigoCapex[]>()
    for (const c of codigos) {
      const clave = c.parent_id
      if (!porPadre.has(clave)) porPadre.set(clave, [])
      porPadre.get(clave)!.push(c)
    }
    const ordenar = (l: CodigoCapex[]) => [...l].sort((a, b) => a.code.localeCompare(b.code))
    // Las raíces, en el orden de la hoja del cliente: alfabéticamente ESG queda
    // delante de Hard Cost, que no es como el cliente lee su árbol. Del nivel 2
    // hacia abajo los códigos van con dos cifras, así que el orden alfabético ya
    // es el bueno.
    const raices = [...(porPadre.get(null) ?? [])].sort((a, b) =>
      porTipoDeCoste(a.code, b.code),
    )
    return raices
      .map((raiz) => ({
        raiz,
        capitulos: ordenar(porPadre.get(raiz.id) ?? [])
          .map((cap) => ({ cap, objetos: ordenar(porPadre.get(cap.id) ?? []) }))
          // Un capítulo sin objetos no se inventaría: los soft costs, los
          // operativos y los imprevistos son costes, no cosas del edificio.
          .filter((c) => c.objetos.length > 0),
      }))
      .filter((r) => r.capitulos.length > 0)
  }, [codigos])

  const porObjeto = useMemo(() => {
    const d = new Map<string, Descriptivo>()
    for (const x of descriptivos ?? []) d.set(x.capex_code_id, x)
    return d
  }, [descriptivos])

  const equiposDe = useCallback(
    (codeId: string) => (equipos ?? []).filter((e) => e.capex_code_id === codeId),
    [equipos],
  )

  /** Las fotografías de un objeto son las que lo señalan **y** las que retratan
   *  uno de sus equipos: atar la foto a la máquina ya dice de qué objeto es, y
   *  pedir el dato dos veces es pedirlo dos veces. */
  const fotosDe = useCallback(
    (codeId: string) => {
      const suyos = new Set(equiposDe(codeId).map((e) => e.id))
      return fotos.filter(
        (f) => f.capex_code_id === codeId || (f.equipment_id && suyos.has(f.equipment_id)),
      )
    },
    [fotos, equiposDe],
  )

  const conAlgo = useCallback(
    (codeId: string) => {
      const b = borradores[codeId] ?? VACIO
      return (
        b.texto.trim() !== '' ||
        b.valoracion.trim() !== '' ||
        equiposDe(codeId).length > 0 ||
        fotosDe(codeId).length > 0
      )
    },
    [borradores, equiposDe, fotosDe],
  )

  // Se abre lo que ya tiene trabajo hecho, una sola vez y cuando hay de qué.
  useEffect(() => {
    if (abiertos !== null || !arbol.length || descriptivos === null || equipos === null) return
    const puestos = new Set<string>()
    for (const { raiz, capitulos } of arbol) {
      for (const { cap, objetos } of capitulos) {
        const vivos = objetos.filter((o) => conAlgo(o.id))
        if (!vivos.length) continue
        puestos.add(raiz.id)
        puestos.add(cap.id)
        for (const o of vivos) puestos.add(o.id)
      }
    }
    // Las raíces siempre abiertas: son seis y esconderlas no ahorra nada.
    for (const { raiz } of arbol) puestos.add(raiz.id)
    setAbiertos(puestos)
  }, [abiertos, arbol, descriptivos, equipos, conAlgo])

  const alternar = (id: string) =>
    setAbiertos((previos) => {
      const s = new Set(previos ?? [])
      if (s.has(id)) s.delete(id)
      else s.add(id)
      return s
    })

  const sucias = useMemo(() => {
    const fuera: { capex_code_id: string; borrador: Borrador }[] = []
    for (const [codeId, b] of Object.entries(borradores)) {
      const d = porObjeto.get(codeId)
      const guardado: Borrador = d
        ? { texto: d.texto, valoracion: d.valoracion, validado: d.validado }
        : VACIO
      if (
        b.texto !== guardado.texto ||
        b.valoracion !== guardado.valoracion ||
        b.validado !== guardado.validado
      ) {
        fuera.push({ capex_code_id: codeId, borrador: b })
      }
    }
    return fuera
  }, [borradores, porObjeto])

  const conContenido = useMemo(
    () =>
      arbol
        .flatMap((r) => r.capitulos)
        .flatMap((c) => c.objetos)
        .filter((o) => conAlgo(o.id)),
    [arbol, conAlgo],
  )
  const totalObjetos = useMemo(
    () => arbol.flatMap((r) => r.capitulos).reduce((n, c) => n + c.objetos.length, 0),
    [arbol],
  )
  const revisados = conContenido.filter((o) => (borradores[o.id] ?? VACIO).validado).length
  const marcados = equipos?.filter((e) => e.pasa_a_capex).length ?? 0
  const sinObjeto = equipos?.filter((e) => !e.capex_code_id) ?? []
  const objetosDelCatalogo = useMemo(
    () =>
      arbol
        .filter((r) => r.raiz.code === TIPO_DE_COSTE_FISICO)
        .flatMap((r) => r.capitulos)
        .flatMap((c) => c.objetos.map((o) => ({ cap: c.cap, o }))),
    [arbol],
  )

  async function conAviso(hacer: () => Promise<void>) {
    setError(null)
    setAviso(null)
    setHecho(null)
    setTrabajando(true)
    try {
      await hacer()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se ha podido completar')
    } finally {
      setTrabajando(false)
    }
  }

  function traer() {
    return conAviso(async () => {
      const r = await enviar<DescriptivosTraidos>(
        `/assets/${assetId}/descriptivos/desde-documentacion`,
        {},
      )
      setHecho(
        `${r.creados} descriptivo(s) nuevo(s), ${r.completados} completado(s) y ` +
          `${r.respetados} respetado(s) porque ya tenían texto o estaban validados. ` +
          'Las valoraciones no se tocan: no salen de ningún documento.',
      )
      if (r.avisos.length) setAviso(r.avisos)
      await recargar()
    })
  }

  function guardar() {
    return conAviso(async () => {
      const lineas = sucias.map((s) => ({ capex_code_id: s.capex_code_id, ...s.borrador }))
      const actualizados = await enviar<Descriptivo[]>(
        `/assets/${assetId}/descriptivos`,
        { lineas },
        'PUT',
      )
      setDescriptivos(actualizados)
      setBorradores(
        Object.fromEntries(
          actualizados.map((d) => [
            d.capex_code_id,
            { texto: d.texto, valoracion: d.valoracion, validado: d.validado },
          ]),
        ),
      )
      setHecho(`${lineas.length} objeto(s) guardado(s).`)
    })
  }

  function marcar(equipo: Equipo, pasa: boolean) {
    return conAviso(async () => {
      await enviar<Equipo>(`/equipment/${equipo.id}`, { pasa_a_capex: pasa }, 'PATCH')
      setEquipos((previos) =>
        (previos ?? []).map((e) => (e.id === equipo.id ? { ...e, pasa_a_capex: pasa } : e)),
      )
    })
  }

  function colocar(equipo: Equipo, capexCodeId: string) {
    return conAviso(async () => {
      const actualizado = await enviar<Equipo>(
        `/equipment/${equipo.id}`,
        { capex_code_id: capexCodeId || null },
        'PATCH',
      )
      setEquipos((previos) =>
        (previos ?? []).map((e) => (e.id === equipo.id ? actualizado : e)),
      )
      if (capexCodeId) setAbiertos((p) => new Set(p ?? []).add(capexCodeId))
    })
  }

  function generar() {
    return conAviso(async () => {
      const r = await enviar<EsqueletoDeEquipos>(
        `/assets/${assetId}/equipment/generar-capex`,
        {},
      )
      setHecho(
        `${r.creadas} actuación(es) creada(s) de ${r.marcados} equipo(s) marcado(s), ` +
          `cada una colgando de la categoría de su objeto. ` +
          `${r.omitidas} ya existían y no se han duplicado.`,
      )
      if (r.avisos.length) setAviso(r.avisos)
    })
  }

  function escribir(codeId: string, campo: keyof Borrador, valor: string | boolean) {
    setBorradores((previos) => ({
      ...previos,
      [codeId]: { ...(previos[codeId] ?? VACIO), [campo]: valor },
    }))
  }

  if (!codigos || !descriptivos || !equipos) {
    return <p className="cargando">Cargando el inventario…</p>
  }

  return (
    // `aria-busy` mientras se guarda o se trae: un lector de pantalla anuncia
    // que la región está trabajando en vez de leer a medias lo que va a cambiar.
    // Es además lo único a lo que se puede esperar desde fuera sin adivinar,
    // porque un mensaje de «hecho» puede ser el de la operación anterior.
    <section className="inventario-activo" aria-busy={trabajando}>
      <h3>Inventario del activo</h3>
      <p className="ayuda">
        El árbol del cliente, categoría a categoría, y dentro de cada objeto lo que se sabe de
        él: <strong>qué hay</strong> (Descriptivo, que sale de la memoria técnica) y{' '}
        <strong>en qué estado está</strong> (Valoración, que la escribe quien lo ha visto), con
        sus equipos y sus fotografías. Las categorías nacen plegadas; se abren solas las que ya
        tienen trabajo hecho.
      </p>

      {error && <Mensaje tipo="error">{error}</Mensaje>}
      {hecho && <Mensaje tipo="ok">{hecho}</Mensaje>}
      {aviso?.map((a) => (
        <Mensaje key={a} tipo="aviso">
          {a}
        </Mensaje>
      ))}

      <p className="recuento">
        <strong>{conContenido.length}</strong> de {totalObjetos} objetos con contenido ·{' '}
        {revisados} validados · {equipos.length} equipos · {marcados} marcados para CAPEX
      </p>

      <div className="filtro">
        <button
          type="button"
          className="secundario"
          disabled={trabajando}
          onClick={() => void traer()}
        >
          Traer descriptivos de la documentación
        </button>
        <button
          type="button"
          disabled={trabajando || sucias.length === 0}
          onClick={() => void guardar()}
        >
          Guardar el inventario {sucias.length > 0 ? `(${sucias.length})` : ''}
        </button>
        <button
          type="button"
          disabled={trabajando || marcados === 0}
          onClick={() => void generar()}
        >
          Generar actuaciones de los marcados ({marcados})
        </button>
      </div>

      {arbol.map(({ raiz, capitulos }) => (
        <section key={raiz.id} className="rama-inventario">
          <Cabecera
            abierto={abiertos?.has(raiz.id) ?? false}
            alAlternar={() => alternar(raiz.id)}
            codigo={raiz.code}
            nombre={raiz.name_es}
            nivel={1}
            marca={`${capitulos.reduce(
              (n, c) => n + c.objetos.filter((o) => conAlgo(o.id)).length,
              0,
            )}/${capitulos.reduce((n, c) => n + c.objetos.length, 0)} objetos`}
          />
          {(abiertos?.has(raiz.id) ?? false) && (
            <ul className="arbol-inventario">
              {capitulos.map(({ cap, objetos }) => {
                const vivos = objetos.filter((o) => conAlgo(o.id)).length
                const equiposDelCap = objetos.reduce((n, o) => n + equiposDe(o.id).length, 0)
                return (
                  <li key={cap.id}>
                    <Cabecera
                      abierto={abiertos?.has(cap.id) ?? false}
                      alAlternar={() => alternar(cap.id)}
                      codigo={cap.code}
                      nombre={cap.name_es}
                      nivel={2}
                      marca={
                        `${vivos}/${objetos.length} objetos` +
                        (equiposDelCap ? ` · ${equiposDelCap} eq.` : '')
                      }
                    />
                    {(abiertos?.has(cap.id) ?? false) && (
                      <ul className="arbol-inventario">
                        {objetos.map((o) => (
                          <li key={o.id}>
                            <Cabecera
                              abierto={abiertos?.has(o.id) ?? false}
                              alAlternar={() => alternar(o.id)}
                              codigo={o.code}
                              nombre={o.name_es}
                              nivel={3}
                              conAlgo={conAlgo(o.id)}
                              marca={marcasDe(
                                borradores[o.id] ?? VACIO,
                                equiposDe(o.id),
                                fotosDe(o.id).length,
                              )}
                            />
                            {(abiertos?.has(o.id) ?? false) && (
                              <FichaDeObjeto
                                codigo={o}
                                guardado={porObjeto.get(o.id) ?? null}
                                borrador={borradores[o.id] ?? VACIO}
                                equipos={equiposDe(o.id)}
                                fotos={fotosDe(o.id)}
                                trabajando={trabajando}
                                alEscribir={(campo, valor) => escribir(o.id, campo, valor)}
                                alMarcar={marcar}
                              />
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      ))}

      {sinObjeto.length > 0 && (
        <section className="sin-clasificar">
          <h4>Equipos sin objeto ({sinObjeto.length})</h4>
          <p className="ayuda">
            Se dieron de alta antes de que el inventario preguntara de qué objeto cuelga cada
            equipo. <strong>No se les ha puesto uno automáticamente</strong>: un capítulo tiene
            once objetos y elegir por usted sería adivinar dónde está la máquina. Colóquelos y
            dejarán de estar aquí —y su actuación sabrá dónde ir.
          </p>
          <div className="desbordable">
            <table className="tabla">
              <thead>
                <tr>
                  <th scope="col">Etiqueta</th>
                  <th scope="col">Equipo</th>
                  <th scope="col">Sistema</th>
                  <th scope="col">Objeto del árbol</th>
                </tr>
              </thead>
              <tbody>
                {sinObjeto.map((e) => (
                  <tr key={e.id}>
                    <td>{e.tag ?? '—'}</td>
                    <td>{e.equipment_type}</td>
                    <td>{e.technical_system_name ?? '—'}</td>
                    <td>
                      <select
                        value=""
                        disabled={trabajando}
                        aria-label={`Objeto de ${e.tag ?? e.equipment_type}`}
                        onChange={(ev) => void colocar(e, ev.target.value)}
                      >
                        <option value="">— elija el objeto —</option>
                        {objetosDelCatalogo.map(({ cap, o }) => (
                          <option key={o.id} value={o.id}>
                            {o.code} · {cap.name_es} › {o.name_es}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {totalObjetos === 0 && (
        <Vacio>
          El catálogo del CAPEX no tiene objetos cargados, así que no hay árbol que recorrer.
          Siembre los catálogos y vuelva a entrar.
        </Vacio>
      )}
    </section>
  )
}

/** Las marcas de un objeto: lo que lleva dentro, sin abrirlo. */
function marcasDe(b: Borrador, equipos: Equipo[], fotos: number): string {
  const trozos: string[] = []
  if (b.texto.trim()) trozos.push('descriptivo')
  if (b.valoracion.trim()) trozos.push('valoración')
  if (equipos.length) trozos.push(`${equipos.length} equipo${equipos.length === 1 ? '' : 's'}`)
  const capex = equipos.filter((e) => e.pasa_a_capex).length
  if (capex) trozos.push(`${capex} a CAPEX`)
  if (fotos) trozos.push(`${fotos} foto${fotos === 1 ? '' : 's'}`)
  if (b.validado) trozos.push('validado')
  return trozos.length ? trozos.join(' · ') : 'vacío'
}

function Cabecera({
  abierto,
  alAlternar,
  codigo,
  nombre,
  nivel,
  marca,
  conAlgo,
}: {
  abierto: boolean
  alAlternar: () => void
  codigo: string
  nombre: string
  nivel: 1 | 2 | 3
  marca: string
  conAlgo?: boolean
}) {
  return (
    <button
      type="button"
      className={`cabecera-inv n${nivel} ${conAlgo ? 'con-algo' : ''}`}
      aria-expanded={abierto}
      onClick={alAlternar}
    >
      <span aria-hidden="true" className="flecha">
        {abierto ? '▾' : '▸'}
      </span>
      <span className="codigo">{codigo}</span>
      <span className="nombre-inv">{nombre}</span>
      <span className="marca-inv">{marca}</span>
    </button>
  )
}

function FichaDeObjeto({
  codigo,
  guardado,
  borrador,
  equipos,
  fotos,
  trabajando,
  alEscribir,
  alMarcar,
}: {
  codigo: CodigoCapex
  guardado: Descriptivo | null
  borrador: Borrador
  equipos: Equipo[]
  fotos: Foto[]
  trabajando: boolean
  alEscribir: (campo: keyof Borrador, valor: string | boolean) => void
  alMarcar: (equipo: Equipo, pasa: boolean) => Promise<void>
}) {
  const hayAlgo = borrador.texto.trim() !== '' || borrador.valoracion.trim() !== ''
  return (
    <div className="ficha-objeto">
      <div className="dos-textos">
        <label className="campo">
          Descriptivo
          <textarea
            rows={4}
            maxLength={4000}
            placeholder="Qué hay: tipo, cantidad, características. Sale de la memoria técnica."
            aria-label={`Descriptivo de ${codigo.name_es} (${codigo.code})`}
            value={borrador.texto}
            onChange={(e) => alEscribir('texto', e.target.value)}
          />
          <span className="nota">Qué hay. Dato de documento, no de observación</span>
        </label>
        <label className="campo">
          Valoración
          <textarea
            rows={4}
            maxLength={4000}
            placeholder="En qué estado está, qué se ha observado y qué se concluye."
            aria-label={`Valoración de ${codigo.name_es} (${codigo.code})`}
            value={borrador.valoracion}
            onChange={(e) => alEscribir('valoracion', e.target.value)}
          />
          <span className="nota">En qué estado está. Lo escribe quien lo ha visto</span>
        </label>
      </div>

      <div className="filtro">
        <label className="marca-revision">
          <input
            type="checkbox"
            checked={borrador.validado}
            // Sin ninguno de los dos textos no hay nada que firmar, y el
            // servidor lo rechaza igualmente: deshabilitarla lo explica antes de
            // que alguien se lleve un 422.
            disabled={!hayAlgo}
            onChange={(e) => alEscribir('validado', e.target.checked)}
          />
          Validado por un técnico
        </label>
        <span className="recuento">
          {guardado?.validado ? (
            <>
              {guardado.validado_por_nombre ?? 'alguien'} · {guardado.validado_at?.slice(0, 10)}
            </>
          ) : (
            'Mientras no se marque, el informe lo da por sin validar'
          )}
        </span>
        {guardado?.es_simulada && (
          <span className="recuento simulada">
            extracción SIMULADA: léalo en el documento antes de validarlo
          </span>
        )}
      </div>

      <h5>Inventario relacionado</h5>
      {equipos.length === 0 ? (
        <Vacio>
          Este objeto no tiene equipos inventariados. No siempre hace falta: una cubierta o una
          fachada se describen y se valoran, pero no tienen máquinas que fichar.
        </Vacio>
      ) : (
        <div className="desbordable">
          <table className="tabla equipo-capex">
            <thead>
              <tr>
                <th scope="col">Pasa a CAPEX</th>
                <th scope="col">Etiqueta</th>
                <th scope="col">Equipo</th>
                <th scope="col">Estado</th>
                <th scope="col">Vida residual</th>
              </tr>
            </thead>
            <tbody>
              {equipos.map((e) => (
                <tr key={e.id} className={e.pasa_a_capex ? 'marcado' : ''}>
                  <td className="casilla-marcado">
                    <input
                      type="checkbox"
                      checked={e.pasa_a_capex}
                      disabled={trabajando}
                      aria-label={`Pasa a CAPEX: ${e.tag ?? e.equipment_type}`}
                      onChange={(ev) => void alMarcar(e, ev.target.checked)}
                    />
                  </td>
                  <td>{e.tag ?? '—'}</td>
                  <td>{e.equipment_type}</td>
                  <td>{e.condition ?? '—'}</td>
                  <td>{e.vida_resumen}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h5>Fotografías de este objeto</h5>
      {fotos.length === 0 ? (
        <p className="ayuda">
          Todavía no hay ninguna. Salen solas al atar una fotografía de la visita a uno de estos
          equipos, o al clasificarla en este objeto.
        </p>
      ) : (
        <ul className="fotos-del-objeto">
          {fotos.map((f) => (
            <li key={f.id}>
              <strong>{f.display_name}</strong>
              <span className="recuento">
                {f.taken_at?.slice(0, 10) ?? 'sin fecha'}
                {f.equipment_id && ' · atada a un equipo'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

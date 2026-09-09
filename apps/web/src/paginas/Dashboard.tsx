import { useCallback, useEffect, useMemo, useState } from 'react'
import { obtener } from '../api/cliente'
import type {
  ResumenPorActivo,
  ResumenPorConcepto,
  ResumenPorHorizonte,
  ResumenPorObjeto,
  ResumenPorRiesgo,
} from '../api/tipos'
import { Tarta, type Porcion } from '../graficos/Tarta'
import { euros, eurosExactos, porcentaje } from '../graficos/formato'
import { agrupar, tinteApilado } from '../graficos/paleta'
import { Mensaje, Vacio } from '../ui/Marco'

/**
 * El dashboard del CAPEX: cinco preguntas y sus cinco respuestas.
 *
 * La rejilla de hallazgos contesta «qué hay que hacer». Esta pantalla contesta
 * las cinco que se hacen en la reunión, y que antes se contestaban sumando a
 * mano:
 *
 * | Título en pantalla | Pregunta que contesta | Forma |
 * |---|---|---|
 * | Distribución por concepto de gasto | ¿en qué se va el dinero? | **tarta** — es un reparto parte-todo |
 * | Perfil temporal de la inversión | ¿cuándo hay que pagarlo? | barras, en orden de plazo |
 * | Exposición por grado de riesgo | ¿cuánto de esto es grave? | barras, en orden de gravedad |
 * | Desglose por categoría y objeto | ¿qué parte del edificio? | barras **apiladas** |
 * | Distribución por activo | ¿qué activo? | barras, **siempre de la cartera entera** |
 *
 * `[REQ]` Los títulos van en el **registro de una due diligence técnica**, que es
 * el del informe que sale de aquí. La pregunta coloquial —«en qué se va el
 * dinero»— es la que se hace en la reunión y por eso se conserva en esta tabla y
 * en el texto de ayuda de cada bloque, donde explica; pero el encabezado que se
 * imprime y se enseña al cliente dice lo que dice un informe.
 *
 * `[REQ]` §3.3 de `docs/23`. Era la vista «Resumen» de Hallazgos y CAPEX y
 * sube a pestaña propia, con dos cortes nuevos —riesgo y objeto— y un selector
 * que pasa de un activo a **uno, varios o toda la cartera**.
 *
 * ## El filtro alcanza a toda la pantalla, y admite varios
 *
 * `[REQ]` Un selector arriba, y **los cuatro primeros cortes se piden
 * filtrados**. Las tarjetas de titulares se mueven con él: una que dijera
 * «CAPEX del proyecto» encima de unos gráficos de una sola nave se contradice
 * con ellos, y quien mire por encima se lleva la cifra equivocada.
 *
 * Que admita varios no es una comodidad. La comparación que se hace en una
 * cartera es «las dos naves del polígono frente al resto», y con un activo por
 * consulta hay que sumarlas a mano —que es justo el descuadre que esta pantalla
 * existe para evitar—.
 *
 * ## «Distribución por activo» se queda, y hace de mando
 *
 * `[REQ]` El quinto bloque **no desaparece al filtrar**: es el que permite
 * comparar varios activos en el momento sin salir de la pantalla. Sigue
 * enseñando la cartera entera, y por eso vale de referencia: dice si el
 * edificio que se está mirando es el caro o uno de los baratos, cosa que los
 * otros cuatro, ya filtrados, no pueden decir.
 *
 * Sus barras se **pulsan**: cada una mete o saca ese activo de la selección.
 * La lista de casillas de arriba y estas barras son el mismo mando escrito dos
 * veces —una para elegir sabiendo el nombre, otra para elegir viendo el
 * importe—, y las dos enseñan lo elegido.
 *
 * Y `by-asset` **no se filtra nunca**: es la lista de activos, hace de índice
 * para el selector y da el total del proyecto, que es lo que permite decir qué
 * parte representa la selección sin volver a pedirlo.
 *
 * ## Por qué solo una es una tarta
 *
 * Una tarta sirve para ver **una proporción de un vistazo** y es mala para
 * comparar dos trozos parecidos: el ojo humano compara longitudes mucho mejor
 * que ángulos. El concepto es un reparto —«esto es normativa, esto es mejora»—
 * y ahí la tarta acierta. Los otros cuatro son comparaciones de magnitud, y ahí
 * una barra se lee mejor y no obliga a inventar colores.
 *
 * `[REQ]` Ningún gráfico se identifica solo por color. Cada barra lleva su
 * nombre y su cifra escritos, la tarta lleva leyenda con importes y
 * porcentajes, los tramos apilados llevan el suyo dentro cuando caben y todos
 * en la tabla de debajo. Se imprime en blanco y negro en cada reunión, y uno de
 * cada doce hombres es daltónico.
 */

/** Lo que no depende del filtro: la lista de activos con sus totales. */
type Datos = { activo: ResumenPorActivo[] }

/** Los cuatro cortes que sí lo hacen. */
type Filtrado = {
  concepto: ResumenPorConcepto[]
  horizonte: ResumenPorHorizonte[]
  riesgo: ResumenPorRiesgo[]
  objeto: ResumenPorObjeto[]
}

export function Dashboard({ projectId }: { projectId: string }) {
  const [datos, setDatos] = useState<Datos | null>(null)
  const [error, setError] = useState<string | null>(null)
  /**
   * `[REQ]` Sobre qué activos se lee **toda la pantalla**. Vacío = la cartera
   * entera, agrupada.
   *
   * Son dos preguntas y las dos se hacen en la misma reunión: agregado dice
   * cómo se comporta el parque —si es mantenimiento diferido o normativa—, y
   * por activo dice qué le pasa a ESE edificio, que es sobre el que se negocia
   * el precio. Un parque con un 40 % de normativa puede tenerlo concentrado en
   * una sola nave, y agregado eso no se ve.
   */
  const [elegidos, setElegidos] = useState<string[]>([])
  /**
   * Los cuatro cortes filtrados. Nulo mientras llegan, para no enseñar los de
   * la selección anterior con el selector diciendo otra cosa.
   */
  const [filtrado, setFiltrado] = useState<Filtrado | null>(null)

  const recargar = useCallback(async () => {
    try {
      setDatos({
        activo: await obtener<ResumenPorActivo[]>(
          `/projects/${projectId}/capex/summary/by-asset`,
        ),
      })
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [projectId])

  useEffect(() => {
    void recargar()
  }, [recargar])

  // La clave del filtro para las dependencias del efecto: un array nuevo en
  // cada render volvería a pedirlo todo aunque la selección no haya cambiado.
  const clave = elegidos.join(',')

  // Los cuatro cortes filtrables se piden juntos y aparte del resto: `by-asset`
  // no se filtra —es la lista de activos, y con el filtro puesto sería una sola
  // fila— y hace de índice para el selector.
  useEffect(() => {
    // `?asset_id=…&asset_id=…`, que es como se escribe una lista en una URL.
    const sufijo = clave ? `?${clave.split(',').map((a) => `asset_id=${a}`).join('&')}` : ''
    const base = `/projects/${projectId}/capex/summary`
    let vigente = true
    setFiltrado(null)
    Promise.all([
      obtener<ResumenPorConcepto[]>(`${base}/by-concept${sufijo}`),
      obtener<ResumenPorHorizonte[]>(`${base}/by-horizon${sufijo}`),
      obtener<ResumenPorRiesgo[]>(`${base}/by-risk${sufijo}`),
      obtener<ResumenPorObjeto[]>(`${base}/by-object${sufijo}`),
    ])
      .then(([concepto, horizonte, riesgo, objeto]) => {
        // Si se ha cambiado la selección mientras llegaba esta respuesta, se
        // descarta: sin esto, la más lenta pisa a la más reciente y los
        // gráficos acaban enseñando unos activos distintos de los que dice el
        // selector. Con cuatro peticiones en vuelo la ventana es ancha.
        if (vigente) setFiltrado({ concepto, horizonte, riesgo, objeto })
      })
      .catch((e: Error) => setError(e.message))
    return () => {
      vigente = false
    }
  }, [projectId, clave])

  const alternar = useCallback((id: string) => {
    setElegidos((antes) =>
      antes.includes(id) ? antes.filter((a) => a !== id) : [...antes, id],
    )
  }, [])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!datos) return <p className="cargando">Cargando el dashboard…</p>

  // El total del PROYECTO sale de `by-asset`, que no se filtra. Es lo que
  // permite decir qué parte representa la selección sin pedirlo otra vez, y lo
  // que evita que la pantalla se quede en blanco mientras llegan los cortes.
  const totalDelProyecto = datos.activo.reduce((s, a) => s + Number(a.amount), 0)
  const cartera = datos.activo.length > 1
  // Solo los que siguen existiendo: un activo borrado en otra pestaña dejaría
  // una selección que no se puede quitar porque su barra ya no está.
  const seleccion = datos.activo.filter((a) => elegidos.includes(a.asset_id))

  if (totalDelProyecto <= 0) {
    return (
      <Vacio>
        Todavía no hay ninguna línea de CAPEX valorada. Este dashboard se rellena solo a medida que
        se registran hallazgos con su importe.
      </Vacio>
    )
  }

  const cabecera = (
    <Cabecera
      activos={datos.activo}
      seleccion={seleccion}
      totalDelProyecto={totalDelProyecto}
      cartera={cartera}
      alAlternar={alternar}
      alQuitarFiltro={() => setElegidos([])}
    />
  )

  // Mientras llegan los cortes se enseña el marco —titulares y selector— y no
  // una pantalla en blanco: cambiar de activo no puede hacer desaparecer el
  // propio selector con el que se acaba de elegir.
  if (!filtrado) {
    return (
      <div className="resumen-capex">
        {cabecera}
        <p className="cargando">Cargando los gráficos…</p>
      </div>
    )
  }

  const total = filtrado.concepto.reduce((s, c) => s + Number(c.amount), 0)
  const lineas = filtrado.concepto.reduce((s, c) => s + c.lines, 0)
  const hallazgos = seleccion.length
    ? seleccion.reduce((s, a) => s + a.findings, 0)
    : datos.activo.reduce((s, a) => s + a.findings, 0)
  const deQuien = nombreDeLaSeleccion(seleccion)

  // `[REQ]` Cuatro conceptos y el resto agrupado: es lo que la paleta admite
  // medido, no una preferencia. Ver `graficos/paleta.ts`.
  const { propias, resto } = agrupar(filtrado.concepto, (c) => Number(c.amount))
  const porciones: Porcion[] = [
    ...propias.map((c) => ({
      clave: c.capex_concept_code,
      nombre: c.capex_concept_name,
      valor: Number(c.amount),
    })),
    ...(resto.length > 0
      ? [
          {
            clave: 'OTROS',
            nombre: 'Otros',
            valor: resto.reduce((s, c) => s + Number(c.amount), 0),
            agrupa: resto.length,
          },
        ]
      : []),
  ]

  return (
    <div className="resumen-capex">
      {cabecera}

      {/* `[REC]` Los titulares primero, y como cifras y no como gráficos. Un
          número solo no es un gráfico de una barra: es un número.
          Y **se mueven con el filtro**: una tarjeta que dijera «CAPEX del
          proyecto» encima de unos gráficos de una sola nave se contradice con
          ellos, y quien mire por encima se lleva la cifra equivocada. */}
      <ul className="cifras-clave">
        <li>
          <span className="valor">{eurosExactos.format(total)}</span>
          <span className="rotulo">
            {deQuien ? `CAPEX de ${deQuien}` : 'CAPEX del proyecto'}
          </span>
        </li>
        <li>
          <span className="valor">{hallazgos}</span>
          <span className="rotulo">{hallazgos === 1 ? 'hallazgo' : 'hallazgos'}</span>
        </li>
        <li>
          <span className="valor">{lineas}</span>
          <span className="rotulo">
            {lineas === 1 ? 'línea de CAPEX' : 'líneas de CAPEX'}
          </span>
        </li>
        {seleccion.length ? (
          /* Con una selección puesta, «activos con actuaciones» no dice nada:
             la pregunta pasa a ser cuánto pesa ESTO dentro del proyecto, que es
             lo que se lleva a la negociación. */
          <li>
            <span className="valor">{porcentaje(total, totalDelProyecto)}</span>
            <span className="rotulo">del CAPEX del proyecto</span>
          </li>
        ) : (
          <li>
            <span className="valor">
              {datos.activo.filter((a) => a.findings > 0).length}
              <span className="ayuda"> / {datos.activo.length}</span>
            </span>
            <span className="rotulo">activos con actuaciones</span>
          </li>
        )}
      </ul>

      {total <= 0 ? (
        <Vacio>
          {deQuien
            ? `«${deQuien}» no tiene ninguna línea de CAPEX valorada. No es lo mismo que no tener hallazgos: puede tenerlos sin importe.`
            : 'Todavía no hay ninguna línea de CAPEX valorada.'}
        </Vacio>
      ) : (
        <>
          <section className="bloque">
            <h3>Distribución por concepto de gasto</h3>
            <p className="ayuda">
              Naturaleza de la inversión. Es la distinción que separa un activo caro de uno mal
              mantenido: <strong>lo exigido por normativa hay que ejecutarlo y una mejora es
              discrecional</strong>, y en el total pesan igual.
            </p>
            <Tarta
              porciones={porciones}
              titulo={
                deQuien
                  ? `Reparto del CAPEX de ${deQuien} por concepto de gasto`
                  : 'Reparto del CAPEX del proyecto por concepto de gasto'
              }
              formatear={(v) => eurosExactos.format(v)}
            />
            <Tabla
              columna="Concepto"
              filas={filtrado.concepto.map((c) => ({
                clave: c.capex_concept_code,
                nombre: c.capex_concept_name,
                importe: Number(c.amount),
                detalle: `${c.findings} ${c.findings === 1 ? 'hallazgo' : 'hallazgos'}`,
              }))}
              total={total}
            />
          </section>

          <section className="bloque">
            <h3>Perfil temporal de la inversión</h3>
            <p className="ayuda">
              Por horizonte de ejecución, en orden de plazo y no de importe: lo que se lee aquí es
              el escalonamiento del desembolso, y reordenarlo por cuantía lo destruiría.
            </p>
            <Barras
              filas={filtrado.horizonte.map((h) => ({
                clave: h.time_horizon_code,
                nombre: h.time_horizon_name,
                importe: Number(h.amount),
                detalle: `${h.lines} ${h.lines === 1 ? 'línea' : 'líneas'}`,
              }))}
            />
          </section>

          {/* `[REQ]` El corte que convierte el total en una decisión: un millón
              en riesgo bajo y un millón concentrado en extremo se escriben
              igual y no se negocian igual. Mismos tonos que la matriz de
              riesgos —es el mismo dato leído de otra manera— y, como allí, el
              grado va escrito: el color solo acompaña. */}
          <section className="bloque">
            <h3>Exposición por grado de riesgo</h3>
            <p className="ayuda">
              Cuánta de la inversión corresponde a cada grado, del más severo al menos. Los grados
              sin importe se muestran con cero: uno que desaparece de la lista se confunde con uno
              que no tiene nada.
            </p>
            <Barras
              filas={filtrado.riesgo.map((r) => ({
                clave: r.risk_code,
                nombre:
                  r.risk_code === 'SIN_GRADO' ? r.risk_name : `${r.risk_code} · ${r.risk_name}`,
                importe: Number(r.amount),
                detalle: `${r.findings} ${r.findings === 1 ? 'hallazgo' : 'hallazgos'}`,
                clase: `grado-${r.risk_code.toLowerCase()}`,
              }))}
            />
          </section>

          <section className="bloque">
            <h3>Desglose por categoría y objeto</h3>
            <p className="ayuda">
              Cada barra es una <strong>categoría</strong> del árbol de CAPEX y los tramos de
              dentro son sus <strong>objetos</strong>, de mayor a menor. Un hallazgo codificado
              en la propia categoría, sin descender al objeto, figura como «sin detallar»: no es
              lo mismo que un objeto denominado «General».
            </p>
            <BarrasApiladas filas={filtrado.objeto} />
          </section>

          {/* `[REQ]` **Se queda con el filtro puesto**, al revés que los otros
              cuatro: es el único que sigue enseñando la cartera entera, y es lo
              que permite comparar varios activos en el momento sin salir de la
              pantalla. Con un solo activo en el proyecto no se pinta, porque
              entonces sí sería una barra sola diciendo lo que ya dicen las
              tarjetas. */}
          {cartera && (
            <section className="bloque">
              <h3>Distribución por activo</h3>
              <p className="ayuda">
                En un proyecto de cartera es la cifra que entra en la negociación de cada activo.
                <strong> Este bloque no se filtra nunca</strong>: es la referencia contra la que
                se lee el resto. Los activos sin actuaciones se muestran con cero: uno que
                desaparece de la lista se confunde con uno que se visitó y no tenía nada.
              </p>
              <p className="ayuda">
                Pulse una barra para incorporar ese activo a la selección o retirarlo de ella.
              </p>
              {/* De mayor a menor: es una comparación de magnitudes y la API los
                  devuelve por nombre, que aquí no significa nada. En «cuándo hay
                  que pagarlo» es al revés y por eso allí NO se reordena. */}
              <Barras
                filas={[...datos.activo]
                  .sort((a, b) => Number(b.amount) - Number(a.amount))
                  .map((a) => ({
                    clave: a.asset_id,
                    nombre: a.asset_name,
                    importe: Number(a.amount),
                    detalle: `${a.findings} ${a.findings === 1 ? 'hallazgo' : 'hallazgos'}`,
                  }))}
                alElegir={alternar}
                puestas={elegidos}
              />
            </section>
          )}
        </>
      )}
    </div>
  )
}

/**
 * Cómo se llama lo que se está mirando, o cadena vacía si es todo.
 *
 * Con dos o tres activos se nombran; con más, se cuentan. Una cabecera que
 * enumere quince nombres deja de leerse, y lo que hace falta saber ahí es que
 * **no** se está viendo el proyecto entero.
 */
function nombreDeLaSeleccion(seleccion: ResumenPorActivo[]): string {
  if (seleccion.length === 0) return ''
  if (seleccion.length <= 3) return seleccion.map((a) => a.asset_name).join(', ')
  return `${seleccion.length} activos`
}

/**
 * El selector y el alcance de la pantalla, escrito.
 *
 * `[REQ]` **El alcance va en palabras y no solo en el desplegable.** Los cinco
 * gráficos cambian a la vez, así que una pantalla filtrada sin decirlo se lee
 * como el proyecto entero y las cifras no cuadran con nada. Se saca a su propio
 * componente porque se pinta también mientras cargan los gráficos: quitarlo en
 * ese momento haría desaparecer el selector con el que se acaba de elegir.
 *
 * `[REC]` Casillas y no un desplegable múltiple. Un `<select multiple>` obliga
 * a saber que se elige con la tecla de control y **pierde la selección entera
 * con un clic despistado**, que aquí significa recargar cuatro gráficos y no
 * saber por qué han cambiado. Van dentro de un `<details>` para que quince
 * activos no empujen el primer gráfico fuera de la pantalla.
 */
function Cabecera({
  activos,
  seleccion,
  totalDelProyecto,
  cartera,
  alAlternar,
  alQuitarFiltro,
}: {
  activos: ResumenPorActivo[]
  seleccion: ResumenPorActivo[]
  totalDelProyecto: number
  cartera: boolean
  alAlternar: (id: string) => void
  alQuitarFiltro: () => void
}) {
  const elegidos = new Set(seleccion.map((a) => a.asset_id))
  return (
    <div className="alcance-del-resumen">
      <p className="alcance">
        {seleccion.length ? (
          <>
            Alcance: <strong>{nombreDeLaSeleccion(seleccion)}</strong>
            <button type="button" className="enlace" onClick={alQuitarFiltro}>
              ver los {activos.length} agregados
            </button>
          </>
        ) : cartera ? (
          <>
            Alcance: los <strong>{activos.length} activos</strong> del proyecto, agregados ·{' '}
            {eurosExactos.format(totalDelProyecto)}
          </>
        ) : (
          <>Alcance: un solo activo · {eurosExactos.format(totalDelProyecto)}</>
        )}
      </p>
      {cartera && (
        <details className="filtro-de-activos">
          <summary>
            {seleccion.length
              ? `${seleccion.length} de ${activos.length} activos`
              : `Toda la cartera · ${activos.length} activos`}
          </summary>
          <fieldset>
            <legend className="ayuda">
              Uno, varios o ninguno. Sin ninguna casilla marcada se lee la cartera entera.
            </legend>
            <ul>
              {activos.map((a) => (
                <li key={a.asset_id}>
                  {/* `casilla` es la convención de la casa para una etiqueta con
                      su casilla al lado: sin ella, `label` es una columna y el
                      nombre cae debajo del cuadrito. */}
                  <label className="casilla">
                    <input
                      type="checkbox"
                      checked={elegidos.has(a.asset_id)}
                      onChange={() => alAlternar(a.asset_id)}
                    />
                    {a.asset_code ? `${a.asset_code} · ${a.asset_name}` : a.asset_name}
                    <span className="ayuda"> {euros.format(Number(a.amount))}</span>
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
        </details>
      )}
    </div>
  )
}

type Fila = {
  clave: string
  nombre: string
  importe: number
  detalle: string
  /** Clase de tono, cuando el corte tiene una escala propia —los grados de riesgo—. */
  clase?: string
}

/**
 * Barras horizontales de un solo tono.
 *
 * `[REQ]` La escala la marca **la barra más larga**, no el total del proyecto:
 * con el total, un reparto dominado por una categoría deja las demás como
 * rayas invisibles y el gráfico deja de decir nada de ellas.
 *
 * Con `alElegir`, cada fila es un botón de verdad —no un `div` con un
 * `onClick`—, así que llega con el tabulador, se activa con el teclado y se
 * anuncia como lo que es. `aria-pressed` dice cuáles están puestas: `[REQ]` las
 * marcadas se distinguen **también por escrito**, con su pastilla, porque el
 * realce de color no lo ve quien imprime esto en blanco y negro.
 */
function Barras({
  filas,
  alElegir,
  puestas,
}: {
  filas: Fila[]
  alElegir?: (clave: string) => void
  /** Las claves de las filas que mandan ahora mismo. */
  puestas?: string[]
}) {
  const mayor = Math.max(...filas.map((f) => f.importe), 1)
  const marcadas = new Set(puestas ?? [])
  return (
    <ul className={alElegir ? 'barras elegibles' : 'barras'}>
      {filas.map((f) => {
        const marcada = alElegir !== undefined && marcadas.has(f.clave)
        const contenido = (
          <>
            <span className={f.clase ? `etiqueta ${f.clase}` : 'etiqueta'}>
              {f.nombre}
              {marcada && <span className="pastilla"> en pantalla</span>}
            </span>
            <span className="barra" aria-hidden="true">
              {/* `[REQ]` Cero no pinta nada. El estilo compartido da un mínimo
                  de 2 px para que un importe pequeño no se confunda con «nada»;
                  con un cero hace lo contrario y convierte «nada» en «poco».
                  Los dos casos existen —un plazo sin actuaciones y un plazo con
                  una actuación barata— y tienen que verse distintos. */}
              {f.importe > 0 && (
                <span
                  className={f.clase ? `relleno ${f.clase}` : 'relleno'}
                  style={{ width: `${(f.importe / mayor) * 100}%` }}
                />
              )}
            </span>
            <span className="cifra">{f.detalle}</span>
            <span className="cifra importe">{euros.format(f.importe)}</span>
          </>
        )
        return (
          <li key={f.clave}>
            {alElegir ? (
              <button
                type="button"
                className={marcada ? 'fila marcada' : 'fila'}
                aria-pressed={marcada}
                onClick={() => alElegir(f.clave)}
              >
                {contenido}
              </button>
            ) : (
              contenido
            )}
          </li>
        )
      })}
    </ul>
  )
}

/** Un objeto dentro de su categoría, ya en números. */
type Tramo = { clave: string; nombre: string; importe: number; hallazgos: number }
type Apilada = { codigo: string; nombre: string; importe: number; tramos: Tramo[] }

/** Por debajo de esta parte de la barra, el nombre no cabe dentro del tramo. */
const ANCHO_MINIMO_PARA_ROTULAR = 0.14

/**
 * Una barra por categoría, con sus objetos apilados dentro.
 *
 * `[REQ]` Es lo que pidió el cliente: «por categoría y objeto en barra
 * acumulado». Las barras se escalan **contra la categoría más cara**, no contra
 * el total, por lo mismo que en `Barras`.
 *
 * `[REQ]` **El color no identifica a los objetos: los separa.** Una categoría
 * puede traer dieciséis, y no existe una paleta de dieciséis tonos que pase las
 * comprobaciones de daltonismo. Los tramos van en una escalera de claridades de
 * un solo tono —ver `graficos/paleta.ts`— y quién es cada uno lo dicen: su
 * nombre escrito dentro cuando cabe, el título al pasar por encima, y la tabla
 * de debajo, que los lista todos con su importe y su parte.
 */
function BarrasApiladas({ filas }: { filas: ResumenPorObjeto[] }) {
  const categorias = useMemo(() => agruparPorCategoria(filas), [filas])
  if (categorias.length === 0) return null
  const mayor = Math.max(...categorias.map((c) => c.importe), 1)
  const total = categorias.reduce((s, c) => s + c.importe, 0)

  return (
    <>
      <ul className="barras apiladas">
        {categorias.map((c) => (
          <li key={c.codigo}>
            <span className="etiqueta">
              {c.codigo} · {c.nombre}
            </span>
            <span
              className="barra"
              // La barra entera es decorativa: lo que dice está escrito al lado
              // y desglosado en la tabla. Anunciar tramo a tramo obligaría a un
              // lector de pantalla a recorrer dieciséis nodos sin estructura.
              aria-hidden="true"
              style={{ width: `${(c.importe / mayor) * 100}%` }}
            >
              {c.tramos.map((t, i) => {
                const parte = t.importe / c.importe
                const tinte = tinteApilado(i)
                return (
                  <span
                    key={t.clave}
                    className="tramo"
                    style={{
                      width: `${parte * 100}%`,
                      background: tinte.fondo,
                      color: tinte.texto,
                    }}
                    title={`${t.nombre} · ${euros.format(t.importe)}`}
                  >
                    {parte >= ANCHO_MINIMO_PARA_ROTULAR && (
                      <span className="rotulo-de-tramo">{t.nombre}</span>
                    )}
                  </span>
                )
              })}
            </span>
            <span className="cifra">
              {c.tramos.length} {c.tramos.length === 1 ? 'objeto' : 'objetos'}
            </span>
            <span className="cifra importe">{euros.format(c.importe)}</span>
          </li>
        ))}
      </ul>

      <details className="detalle-tabla">
        <summary>
          Ver los {filas.length} objetos en tabla, con su categoría
        </summary>
        <div className="desbordable">
          <table className="tabla">
            <thead>
              <tr>
                <th scope="col">Categoría</th>
                <th scope="col">Objeto</th>
                <th scope="col">Hallazgos</th>
                <th scope="col" className="numerica">
                  Importe
                </th>
                <th scope="col" className="numerica">
                  % de su categoría
                </th>
              </tr>
            </thead>
            <tbody>
              {categorias.map((c) =>
                c.tramos.map((t, i) => (
                  <tr key={t.clave}>
                    {/* El nombre de la categoría, una sola vez por grupo: al
                        repetirlo en cada fila, la tabla se lee como si hubiera
                        dieciséis categorías distintas. */}
                    <th scope="row">{i === 0 ? `${c.codigo} · ${c.nombre}` : ''}</th>
                    <td>{t.nombre}</td>
                    <td>{t.hallazgos}</td>
                    <td className="numerica">{eurosExactos.format(t.importe)}</td>
                    <td className="numerica">{porcentaje(t.importe, c.importe)}</td>
                  </tr>
                )),
              )}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={3}>Total</td>
                <td className="numerica">{eurosExactos.format(total)}</td>
                <td className="numerica">100,0 %</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </details>
    </>
  )
}

/**
 * Las filas planas de la API, agrupadas por categoría **conservando su orden**.
 *
 * La API ya las devuelve ordenadas —categoría de mayor a menor y, dentro,
 * objeto de mayor a menor—, así que agrupar es recorrer y no reordenar: volver
 * a ordenar aquí sería una segunda fuente de verdad sobre el orden, y las dos
 * acabarían diciendo cosas distintas.
 */
function agruparPorCategoria(filas: ResumenPorObjeto[]): Apilada[] {
  const salida: Apilada[] = []
  for (const f of filas) {
    let grupo = salida[salida.length - 1]
    if (!grupo || grupo.codigo !== f.chapter_code) {
      grupo = { codigo: f.chapter_code, nombre: f.chapter_name, importe: 0, tramos: [] }
      salida.push(grupo)
    }
    const importe = Number(f.amount)
    grupo.importe += importe
    grupo.tramos.push({
      // Un hallazgo codificado en la propia categoría no trae objeto, y no es
      // lo mismo que uno llamado «General»: se dice, no se inventa un nombre.
      clave: f.object_code ?? `${f.chapter_code}·sin-detallar`,
      nombre: f.object_name ?? 'Sin detallar',
      importe,
      hallazgos: f.findings,
    })
  }
  return salida
}

/**
 * Los mismos números de la tarta, en tabla.
 *
 * No es una redundancia: la guía de visualización obliga a una vista en tabla
 * cuando algún tono no llega a 3:1 de contraste contra el fondo, y aquí el agua
 * se queda en 2,74:1. Además es lo que permite leer los conceptos que la tarta
 * agrupa en «Otros», y copiar una cifra exacta.
 */
function Tabla({
  columna,
  filas,
  total,
}: {
  columna: string
  filas: Fila[]
  total: number
}) {
  return (
    <details className="detalle-tabla">
      <summary>Ver los {filas.length} conceptos en tabla</summary>
      <div className="desbordable">
        <table className="tabla">
          <thead>
            <tr>
              <th scope="col">{columna}</th>
              <th scope="col">Hallazgos</th>
              <th scope="col" className="numerica">
                Importe
              </th>
              <th scope="col" className="numerica">
                % del total
              </th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => (
              <tr key={f.clave}>
                <th scope="row">{f.nombre}</th>
                <td>{f.detalle}</td>
                <td className="numerica">{eurosExactos.format(f.importe)}</td>
                <td className="numerica">{porcentaje(f.importe, total)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td>Total</td>
              <td />
              <td className="numerica">{eurosExactos.format(total)}</td>
              <td className="numerica">{porcentaje(total, total)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </details>
  )
}

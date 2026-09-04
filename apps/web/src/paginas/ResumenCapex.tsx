import { useCallback, useEffect, useState } from 'react'
import { obtener } from '../api/cliente'
import type {
  ResumenPorActivo,
  ResumenPorCapitulo,
  ResumenPorConcepto,
  ResumenPorHorizonte,
} from '../api/tipos'
import { Tarta, type Porcion } from '../graficos/Tarta'
import { euros, eurosExactos, porcentaje } from '../graficos/formato'
import { agrupar } from '../graficos/paleta'
import { Mensaje, Vacio } from '../ui/Marco'

/**
 * El resumen del CAPEX: cuatro preguntas y sus cuatro respuestas.
 *
 * La rejilla de hallazgos contesta «qué hay que hacer». Esta vista contesta las
 * cuatro que se hacen en la reunión, y que hoy se contestaban sumando a mano:
 *
 * | Pregunta | Corte | Forma |
 * |---|---|---|
 * | ¿En qué se va el dinero? | concepto | **tarta** — es un reparto parte-todo |
 * | ¿Cuándo hay que pagarlo? | horizonte | barras, en orden de plazo |
 * | ¿Qué parte del edificio? | capítulo | barras, de mayor a menor |
 * | ¿Qué edificio? | activo | barras, solo si hay más de uno y sin filtrar |
 *
 * ## El filtro alcanza a toda la vista
 *
 * `[REQ]` Un selector de activo arriba, y **los tres primeros cortes se piden
 * filtrados**. Las tarjetas de titulares se mueven con él: una que dijera
 * «CAPEX del encargo» encima de unos gráficos de una sola nave se contradice
 * con ellos, y quien mire por encima se lleva la cifra equivocada.
 *
 * «Qué edificio» **desaparece** al elegir uno, y no por ahorrar sitio: con el
 * filtro puesto sería una sola barra con el total otra vez, que es lo que ya
 * dicen las tarjetas. Un gráfico de una barra no es un gráfico.
 *
 * Y `by-asset` **no se filtra nunca**: es la lista de activos, hace de índice
 * para el desplegable y da el total del encargo, que es lo que permite decir
 * qué parte representa el activo elegido sin volver a pedirlo.
 *
 * ## Por qué solo una es una tarta
 *
 * Una tarta sirve para ver **una proporción de un vistazo** y es mala para
 * comparar dos trozos parecidos: el ojo humano compara longitudes mucho mejor
 * que ángulos. El concepto es un reparto —«esto es normativa, esto es mejora»—
 * y ahí la tarta acierta. Los otros tres son comparaciones de magnitud, y ahí
 * una barra se lee mejor y no obliga a inventar colores.
 *
 * Las barras van todas **del mismo tono**, no de colores distintos. El color
 * distinto se usa para decir «esto es otra cosa», y en una comparación de
 * magnitudes todas las barras son la misma cosa medida en sitios distintos:
 * pintarlas de siete colores añade un significado que no existe.
 *
 * `[REQ]` Ningún gráfico se identifica solo por color. Cada barra lleva su
 * nombre y su cifra escritos, la tarta lleva leyenda con importes y
 * porcentajes, y debajo hay una tabla con los mismos números. Se imprime en
 * blanco y negro en cada reunión, y uno de cada doce hombres es daltónico.
 */

/** Lo que no depende del filtro: la lista de activos con sus totales. */
type Datos = { activo: ResumenPorActivo[] }

/** Los tres cortes que sí lo hacen. */
type Filtrado = {
  concepto: ResumenPorConcepto[]
  horizonte: ResumenPorHorizonte[]
  capitulo: ResumenPorCapitulo[]
}

export function ResumenCapex({ projectId }: { projectId: string }) {
  const [datos, setDatos] = useState<Datos | null>(null)
  const [error, setError] = useState<string | null>(null)
  /**
   * `[REQ]` Sobre qué activo se lee **toda la vista**. Vacío = todos, agrupados.
   *
   * Son dos preguntas y las dos se hacen en la misma reunión: agregado dice
   * cómo se comporta el parque —si es mantenimiento diferido o normativa—, y
   * por activo dice qué le pasa a ESE edificio, que es sobre el que se negocia
   * el precio. Un parque con un 40 % de normativa puede tenerlo concentrado en
   * una sola nave, y agregado eso no se ve.
   */
  const [activo, setActivo] = useState('')
  /**
   * Los tres cortes filtrados. Nulo mientras llegan, para no enseñar los del
   * activo anterior con el selector diciendo otra cosa.
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

  // Los tres cortes filtrables se piden juntos y aparte del resto: `by-asset`
  // no se filtra —es la lista de activos, y con el filtro puesto sería una sola
  // fila— y hace de índice para el desplegable.
  useEffect(() => {
    const sufijo = activo ? `?asset_id=${activo}` : ''
    const base = `/projects/${projectId}/capex/summary`
    let vigente = true
    setFiltrado(null)
    Promise.all([
      obtener<ResumenPorConcepto[]>(`${base}/by-concept${sufijo}`),
      obtener<ResumenPorHorizonte[]>(`${base}/by-horizon${sufijo}`),
      obtener<ResumenPorCapitulo[]>(`${base}/by-chapter${sufijo}`),
    ])
      .then(([concepto, horizonte, capitulo]) => {
        // Si se ha cambiado de activo mientras llegaba esta respuesta, se
        // descarta: sin esto, la más lenta pisa a la más reciente y los
        // gráficos acaban enseñando un activo distinto del que dice el
        // selector. Con tres peticiones en vuelo la ventana es más ancha.
        if (vigente) setFiltrado({ concepto, horizonte, capitulo })
      })
      .catch((e: Error) => setError(e.message))
    return () => {
      vigente = false
    }
  }, [projectId, activo])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!datos) return <p className="cargando">Cargando el resumen…</p>

  // El total del ENCARGO sale de `by-asset`, que no se filtra. Es lo que
  // permite decir qué parte del encargo representa el activo elegido sin
  // pedirlo otra vez, y lo que evita que la pantalla se quede en blanco
  // mientras llegan los tres cortes.
  const totalDelEncargo = datos.activo.reduce((s, a) => s + Number(a.amount), 0)
  const cartera = datos.activo.length > 1
  const elegido = datos.activo.find((a) => a.asset_id === activo)

  if (totalDelEncargo <= 0) {
    return (
      <Vacio>
        Todavía no hay ninguna línea de CAPEX valorada. Este resumen se rellena solo a medida que
        se registran hallazgos con su importe.
      </Vacio>
    )
  }

  const selector = cartera ? (
    <label className="filtro-del-resumen">
      Activo
      <select value={activo} onChange={(e) => setActivo(e.target.value)}>
        <option value="">Todos los activos, agrupados</option>
        {datos.activo.map((a) => (
          <option key={a.asset_id} value={a.asset_id}>
            {a.asset_code ? `${a.asset_code} · ${a.asset_name}` : a.asset_name}
          </option>
        ))}
      </select>
    </label>
  ) : null

  // Mientras llegan los tres cortes se enseña el marco —titulares y selector—
  // y no una pantalla en blanco: cambiar de activo no puede hacer desaparecer
  // el propio selector con el que se acaba de elegir.
  if (!filtrado) {
    return (
      <div className="resumen-capex">
        <Cabecera
          selector={selector}
          elegido={elegido}
          totalDelEncargo={totalDelEncargo}
          activos={datos.activo}
          alQuitarFiltro={() => setActivo('')}
        />
        <p className="cargando">Cargando los gráficos…</p>
      </div>
    )
  }

  const total = filtrado.concepto.reduce((s, c) => s + Number(c.amount), 0)
  const lineas = filtrado.concepto.reduce((s, c) => s + c.lines, 0)
  const hallazgos = elegido
    ? elegido.findings
    : datos.activo.reduce((s, a) => s + a.findings, 0)

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
      <Cabecera
        selector={selector}
        elegido={elegido}
        totalDelEncargo={totalDelEncargo}
        activos={datos.activo}
        alQuitarFiltro={() => setActivo('')}
      />

      {/* `[REC]` Los titulares primero, y como cifras y no como gráficos. Un
          número solo no es un gráfico de una barra: es un número.
          Y **se mueven con el filtro**: una tarjeta que dijera «CAPEX del
          encargo» encima de unos gráficos de una sola nave se contradice con
          ellos, y quien mire por encima se lleva la cifra equivocada. */}
      <ul className="cifras-clave">
        <li>
          <span className="valor">{eurosExactos.format(total)}</span>
          <span className="rotulo">
            {elegido ? `CAPEX de ${elegido.asset_name}` : 'CAPEX del encargo'}
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
        {elegido ? (
          /* Con un activo elegido, «activos con actuaciones» no dice nada: la
             pregunta pasa a ser cuánto pesa ESTE dentro del encargo, que es lo
             que se lleva a la negociación. */
          <li>
            <span className="valor">{porcentaje(total, totalDelEncargo)}</span>
            <span className="rotulo">del CAPEX del encargo</span>
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
          {elegido
            ? `«${elegido.asset_name}» no tiene ninguna línea de CAPEX valorada. No es lo mismo que no tener hallazgos: puede tenerlos sin importe.`
            : 'Todavía no hay ninguna línea de CAPEX valorada.'}
        </Vacio>
      ) : (
        <>
          <section className="bloque">
            <h3>En qué se va el dinero</h3>
            <p className="ayuda">
              Por concepto de gasto. Es la distinción que separa un edificio caro de uno mal
              mantenido: <strong>«Normativa» hay que pagarlo y «Mejora» se puede
              decidir</strong>, y en el total valen lo mismo.
            </p>
            <Tarta
              porciones={porciones}
              titulo={
                elegido
                  ? `Reparto del CAPEX de ${elegido.asset_name} por concepto de gasto`
                  : 'Reparto del CAPEX del encargo por concepto de gasto'
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
            <h3>Cuándo hay que pagarlo</h3>
            <p className="ayuda">
              En orden de plazo, no de importe: aquí lo que se lee es el perfil temporal del
              gasto, y reordenarlo por cuantía lo destruiría.
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

          <section className="bloque">
            <h3>Qué parte del edificio</h3>
            <p className="ayuda">
              Por capítulo del árbol de CAPEX. Un hallazgo codificado en un objeto suma en su
              capítulo: si no, el reparto saldría partido en trozos que no suman nada
              reconocible.
            </p>
            <Barras
              filas={filtrado.capitulo.map((c) => ({
                clave: c.chapter_code,
                nombre: `${c.chapter_code} · ${c.chapter_name}`,
                importe: Number(c.amount),
                detalle: `${c.findings} ${c.findings === 1 ? 'hallazgo' : 'hallazgos'}`,
              }))}
            />
          </section>

          {/* `[REQ]` Desaparece al elegir un activo, y no por ahorrar sitio:
              con el filtro puesto sería **una sola barra con el total otra
              vez**, que es lo que ya dicen las tarjetas de arriba. Un gráfico
              de una barra no es un gráfico. Con un solo activo en el encargo,
              lo mismo. */}
          {cartera && !elegido && (
            <section className="bloque">
              <h3>Qué edificio</h3>
              <p className="ayuda">
                En un encargo de cartera es el número que entra en la negociación de cada
                edificio. Los activos sin actuaciones salen con cero: un activo que desaparece
                de la lista se confunde con uno que se visitó y no tenía nada.
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
              />
            </section>
          )}
        </>
      )}
    </div>
  )
}

/**
 * El selector y el alcance de la vista, escrito.
 *
 * `[REQ]` **El alcance va en palabras y no solo en el desplegable.** Los cuatro
 * gráficos cambian a la vez, así que una pantalla filtrada sin decirlo se lee
 * como el encargo entero y las cifras no cuadran con nada. Se saca a su propio
 * componente porque se pinta también mientras cargan los gráficos: quitarlo en
 * ese momento haría desaparecer el selector con el que se acaba de elegir.
 */
function Cabecera({
  selector,
  elegido,
  totalDelEncargo,
  activos,
  alQuitarFiltro,
}: {
  selector: React.ReactNode
  elegido: ResumenPorActivo | undefined
  totalDelEncargo: number
  activos: ResumenPorActivo[]
  alQuitarFiltro: () => void
}) {
  return (
    <div className="alcance-del-resumen">
      <p className="alcance">
        {elegido ? (
          <>
            Todo el resumen, <strong>solo de {elegido.asset_name}</strong>
            <button type="button" className="enlace" onClick={alQuitarFiltro}>
              ver los {activos.length} agrupados
            </button>
          </>
        ) : activos.length > 1 ? (
          <>
            Todo el resumen, con los <strong>{activos.length} activos</strong> del encargo
            agrupados · {eurosExactos.format(totalDelEncargo)}
          </>
        ) : (
          <>Un solo activo en el encargo · {eurosExactos.format(totalDelEncargo)}</>
        )}
      </p>
      {selector}
    </div>
  )
}

type Fila = { clave: string; nombre: string; importe: number; detalle: string }

/**
 * Barras horizontales de un solo tono.
 *
 * `[REQ]` La escala la marca **la barra más larga**, no el total del encargo:
 * con el total, un reparto dominado por una categoría deja las demás como
 * rayas invisibles y el gráfico deja de decir nada de ellas.
 */
function Barras({ filas }: { filas: Fila[] }) {
  const mayor = Math.max(...filas.map((f) => f.importe), 1)
  return (
    <ul className="barras">
      {filas.map((f) => (
        <li key={f.clave}>
          <span className="etiqueta">{f.nombre}</span>
          <span className="barra" aria-hidden="true">
            {/* `[REQ]` Cero no pinta nada. El estilo compartido da un mínimo de
                2 px para que un importe pequeño no se confunda con «nada»; con
                un cero hace lo contrario y convierte «nada» en «poco». Los dos
                casos existen —un plazo sin actuaciones y un plazo con una
                actuación barata— y tienen que verse distintos. */}
            {f.importe > 0 && (
              <span className="relleno" style={{ width: `${(f.importe / mayor) * 100}%` }} />
            )}
          </span>
          <span className="cifra">{f.detalle}</span>
          <span className="cifra importe">{euros.format(f.importe)}</span>
        </li>
      ))}
    </ul>
  )
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

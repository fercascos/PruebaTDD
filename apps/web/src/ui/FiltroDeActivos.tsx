/**
 * El selector de activos de las pantallas de cartera `[REQ]` §3.3.
 *
 * Con las palabras del cliente al revisar el prototipo: *«dentro de un proyecto
 * querría poder seleccionar los activos que quiero visualizar, pudiendo ser
 * todos, uno solo o varios»*. Las tres cosas con el mismo mando: **sin ninguna
 * casilla marcada se lee la cartera entera**, que es lo que se espera al soltar
 * la última.
 *
 * ## Por qué es un componente y no dos copias
 *
 * Lo usan el dashboard y la matriz de riesgos, que son las dos pantallas que
 * agregan varios activos. Escrito dos veces acabarían divergiendo en lo que no
 * se ve —qué cuenta como «sin filtro», si el orden es el de la API o el del
 * importe— y las dos pantallas darían cifras distintas sobre la misma
 * selección, que es justo el descuadre que existen para evitar.
 *
 * ## Que admita varios no es una comodidad
 *
 * La comparación que se hace en una cartera es «las dos naves del polígono
 * frente al resto», y con un activo por consulta hay que sumarlas a mano.
 *
 * `[LIM]` Con **un solo activo** no se pinta: un desplegable con una casilla no
 * filtra nada y ocupa el sitio del titular. Quien lo llama decide, porque cada
 * pantalla sabe qué enseñar en su lugar.
 */

export type ActivoElegible = {
  id: string
  /** Como se lee. Quien llama decide si lleva el código delante. */
  nombre: string
  /** Un dato de apoyo a la derecha —su importe—, si la pantalla lo tiene. */
  pie?: string
}

export function FiltroDeActivos({
  activos,
  elegidos,
  alAlternar,
}: {
  activos: ActivoElegible[]
  elegidos: readonly string[]
  alAlternar: (id: string) => void
}) {
  const puestos = new Set(elegidos)
  return (
    <details className="filtro-de-activos">
      {/* El resumen dice el estado con el mando cerrado. Sin él hay que abrirlo
          para saber si lo que se está mirando es todo o una parte, y eso es
          exactamente lo que no se puede dejar a la memoria de quien mira. */}
      <summary>
        {puestos.size
          ? `${puestos.size} de ${activos.length} activos`
          : `Toda la cartera · ${activos.length} activos`}
      </summary>
      <fieldset>
        {/* La leyenda, corta: se dibuja sobre el borde del `fieldset` y con dos
            renglones queda medio fuera de la caja. La explicación va debajo. */}
        <legend>Activos</legend>
        <p className="ayuda">
          Uno, varios o ninguno. Sin ninguna casilla marcada se lee la cartera entera.
        </p>
        <ul>
          {activos.map((a) => (
            <li key={a.id}>
              {/* `casilla` es la convención de la casa para una etiqueta con su
                  casilla al lado: sin ella, `label` es una columna y el nombre
                  cae debajo del cuadrito. */}
              <label className="casilla">
                <input
                  type="checkbox"
                  checked={puestos.has(a.id)}
                  onChange={() => alAlternar(a.id)}
                />
                {a.nombre}
                {a.pie && <span className="ayuda"> {a.pie}</span>}
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
    </details>
  )
}

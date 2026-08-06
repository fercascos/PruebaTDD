import { useCallback, useEffect, useState } from 'react'
import { obtener } from '../api/cliente'
import type { Activo } from '../api/tipos'
import { Mensaje, Vacio } from '../ui/Marco'

type Grado = {
  code: string
  name: string
  score: number | null
  hallazgos: number
  importe: string
  por_horizonte: Record<string, string>
}

type Capitulo = {
  code: string
  name: string
  por_grado: Record<string, number>
  importe: string
}

type Matriz = {
  horizontes: string[]
  grados: Grado[]
  capitulos: Capitulo[]
  total_por_horizonte: Record<string, string>
  total_hallazgos: number
  total_importe: string
}

const euros = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0,
})

const NOMBRE_DE_HORIZONTE: Record<string, string> = {
  CORTO: 'Corto',
  MEDIO: 'Medio',
  LARGO: 'Largo',
  MEJORAS: 'Mejoras',
  OTRO: 'Otro',
}

/**
 * Matriz de riesgos y prioridades `[REQ]` §12 de `docs/09-ux-pantallas.md`.
 *
 * **Riesgo × horizonte temporal**, no la clásica probabilidad × consecuencia:
 * la especificación define el riesgo como un grado único de cuatro niveles ya
 * interpretado, no como dos ejes. Cruzarlo con el plazo responde la pregunta
 * que se hace el inversor: *«¿cuánto de lo grave hay que pagar en los dos
 * primeros años?»*.
 *
 * `[REQ]` **El grado nunca se identifica solo por color.** Cada fila lleva su
 * código (`01`…`04`) y su nombre escritos, y las barras llevan su cifra al
 * lado. Un daltónico —y son uno de cada doce hombres— tiene que poder leer
 * esta pantalla, y quien la imprima en blanco y negro para una reunión,
 * también. El color acompaña; no informa por sí solo.
 */
export function PestanaRiesgos({ projectId }: { projectId: string }) {
  const [datos, setDatos] = useState<Matriz | null>(null)
  const [activos, setActivos] = useState<Activo[]>([])
  const [activo, setActivo] = useState('')
  const [capitulo, setCapitulo] = useState('')
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(() => {
    const partes = [
      activo ? `asset_id=${activo}` : '',
      capitulo ? `chapter_code=${encodeURIComponent(capitulo)}` : '',
    ].filter(Boolean)
    obtener<Matriz>(
      `/projects/${projectId}/risk-matrix${partes.length ? `?${partes.join('&')}` : ''}`,
    )
      .then(setDatos)
      .catch((e: Error) => setError(e.message))
  }, [projectId, activo, capitulo])

  useEffect(recargar, [recargar])

  useEffect(() => {
    obtener<Activo[]>(`/projects/${projectId}/assets`)
      .then(setActivos)
      .catch(() => setActivos([]))
  }, [projectId])

  if (error) return <Mensaje tipo="error">{error}</Mensaje>
  if (!datos) return <p className="cargando">Cargando la matriz…</p>

  const total = Number(datos.total_importe)
  // La barra más larga marca la escala. Con el total general, un proyecto con
  // un grado dominante dejaría los demás como rayas invisibles.
  const mayor = Math.max(...datos.grados.map((g) => Number(g.importe)), 1)

  return (
    <>
      <div className="filtro">
        <label>
          Activo
          <select value={activo} onChange={(e) => setActivo(e.target.value)}>
            <option value="">Todos</option>
            {activos.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Capítulo
          <select value={capitulo} onChange={(e) => setCapitulo(e.target.value)}>
            <option value="">Todos</option>
            {datos.capitulos.map((c) => (
              <option key={c.code} value={c.code}>
                {c.code} · {c.name}
              </option>
            ))}
          </select>
        </label>
        <span className="ayuda">
          {datos.total_hallazgos} hallazgos · {euros.format(total)}
        </span>
      </div>

      {datos.total_hallazgos === 0 ? (
        <Vacio>
          Todavía no hay hallazgos que clasificar. La matriz se rellena sola a medida que se
          registran.
        </Vacio>
      ) : (
        <>
          <section className="bloque">
            <h3>Distribución por grado de riesgo e importe</h3>
            <ul className="barras">
              {datos.grados.map((g) => (
                <li key={g.code}>
                  {/* El código y el nombre, escritos. El color solo acompaña. */}
                  <span className={`etiqueta grado-${g.code.toLowerCase()}`}>
                    <strong>{g.code === 'SIN_GRADO' ? '–' : g.code}</strong> {g.name}
                  </span>
                  <span className="barra" aria-hidden="true">
                    <span
                      className={`relleno grado-${g.code.toLowerCase()}`}
                      style={{ width: `${(Number(g.importe) / mayor) * 100}%` }}
                    />
                  </span>
                  <span className="cifra">
                    {g.hallazgos} {g.hallazgos === 1 ? 'hallazgo' : 'hallazgos'}
                  </span>
                  <span className="cifra importe">{euros.format(Number(g.importe))}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="bloque">
            <h3>Riesgo × horizonte temporal</h3>
            <div className="desbordable">
              <table className="tabla matriz">
                <caption className="ayuda">
                  Cuánto dinero hay en cada cruce de gravedad y plazo. Responde a «¿cuánto de lo
                  grave hay que pagar en los dos primeros años?».
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Grado</th>
                    {datos.horizontes.map((h) => (
                      <th key={h} scope="col" className="numerica">
                        {NOMBRE_DE_HORIZONTE[h] ?? h}
                      </th>
                    ))}
                    <th scope="col" className="numerica">
                      Total
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {datos.grados.map((g) => (
                    <tr key={g.code}>
                      <th scope="row">
                        <span className={`marca-grado grado-${g.code.toLowerCase()}`} />
                        <strong>{g.code === 'SIN_GRADO' ? '–' : g.code}</strong> {g.name}
                      </th>
                      {datos.horizontes.map((h) => {
                        const valor = Number(g.por_horizonte[h] ?? 0)
                        return (
                          <td key={h} className="numerica">
                            {/* Un guion y no «0 €»: un cero explícito afirma que
                                ese cruce cuesta cero, y lo que dice es que no
                                hay nada ahí. */}
                            {valor === 0 ? '—' : euros.format(valor)}
                          </td>
                        )
                      })}
                      <td className="numerica">
                        <strong>{euros.format(Number(g.importe))}</strong>
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th scope="row">Total</th>
                    {datos.horizontes.map((h) => (
                      <td key={h} className="numerica">
                        {euros.format(Number(datos.total_por_horizonte[h] ?? 0))}
                      </td>
                    ))}
                    <td className="numerica">
                      <strong>{euros.format(total)}</strong>
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </section>

          {datos.capitulos.length > 0 && (
            <section className="bloque">
              <h3>Riesgo por capítulo</h3>
              <p className="ayuda">De mayor a menor importe.</p>
              <ul className="capitulos">
                {datos.capitulos.map((c) => (
                  <li key={c.code}>
                    <span className="nombre">
                      <strong>{c.code}</strong> {c.name}
                    </span>
                    <span className="grados">
                      {datos.grados
                        .filter((g) => (c.por_grado[g.code] ?? 0) > 0)
                        .map((g) => (
                          <span
                            key={g.code}
                            className={`pastilla grado-${g.code.toLowerCase()}`}
                            title={g.name}
                          >
                            {g.code === 'SIN_GRADO' ? '–' : g.code}:{c.por_grado[g.code]}
                          </span>
                        ))}
                    </span>
                    <span className="cifra importe">{euros.format(Number(c.importe))}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <p className="ayuda">
            El grado nunca se identifica solo por color: cada fila lleva su código y su nombre
            escritos. Los importes son los del CAPEX del encargo; lo descartado no suma.
          </p>
        </>
      )}
    </>
  )
}

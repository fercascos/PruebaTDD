/** El panel: filtros, tarjetas, series, reparto y la tabla de activos. */
import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'

import { consulta, pedir } from '../api/cliente'
import type { Activo, Cartera, Panel as PanelDatos, Vector } from '../api/tipos'
import { Barras } from '../graficos/Barras'
import { Donut } from '../graficos/Donut'
import { cantidad } from '../graficos/formato'
import { COLOR, ETIQUETA, UNIDAD, VECTORES } from '../graficos/paleta'
import { Filtros, ultimosMeses } from '../ui/Filtros'
import type { Seleccion } from '../ui/Filtros'
import { Tarjeta } from '../ui/Tarjeta'

export function Panel() {
  const [carteras, setCarteras] = useState<Cartera[]>([])
  const [activos, setActivos] = useState<Activo[]>([])
  const [datos, setDatos] = useState<PanelDatos | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const [seleccion, setSeleccion] = useState<Seleccion>({
    ...ultimosMeses(12),
    cartera: '',
    activo: '',
    vectores: [...VECTORES],
  })

  useEffect(() => {
    void (async () => {
      const [c, a] = await Promise.all([
        pedir<Cartera[]>('/api/v1/carteras'),
        pedir<Activo[]>('/api/v1/activos'),
      ])
      setCarteras(c)
      setActivos(a)
    })()
  }, [])

  const cargar = useCallback(async () => {
    setCargando(true)
    try {
      const parametros = consulta({
        desde: seleccion.desde,
        hasta: seleccion.hasta,
        cartera: seleccion.cartera || undefined,
        activo: seleccion.activo || undefined,
        vector: seleccion.vectores.length === VECTORES.length ? undefined : seleccion.vectores,
      })
      setDatos(await pedir<PanelDatos>(`/api/v1/indicadores/panel${parametros}`))
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo cargar el panel')
    } finally {
      setCargando(false)
    }
  }, [seleccion])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const vectoresConDatos = useMemo(
    () => (datos ? datos.totales.map((t) => t.vector) : []),
    [datos],
  )
  const [vectorDelReparto, setVectorDelReparto] = useState<Vector>('ELECTRICIDAD')
  const vectorReparto = vectoresConDatos.includes(vectorDelReparto)
    ? vectorDelReparto
    : (vectoresConDatos[0] ?? 'ELECTRICIDAD')

  return (
    <section>
      <Filtros
        carteras={carteras}
        activos={activos}
        seleccion={seleccion}
        cambiar={setSeleccion}
      />

      {error && <p className="error">{error}</p>}
      {cargando && <p className="apagado">Calculando…</p>}

      {datos && datos.totales.length === 0 && !cargando && (
        <p className="vacio">
          No hay consumos en este periodo con estos filtros. Si acaba de entrar como cliente y
          esto está vacío, puede que aún no le hayan abierto ninguna cartera.
        </p>
      )}

      {datos && datos.totales.length > 0 && (
        <>
          <div className="tarjetas">
            {datos.totales.map((t) => (
              <Tarjeta key={t.vector} total={t} />
            ))}
          </div>

          <div className="paneles">
            {datos.totales.map((t) => (
              <Barras
                key={t.vector}
                titulo={ETIQUETA[t.vector]}
                unidad={UNIDAD[t.vector]}
                color={COLOR[t.vector]}
                barras={datos.serie
                  .filter((p) => p.vector === t.vector)
                  .map((p) => ({ mes: p.mes, valor: Number(p.cantidad) }))}
              />
            ))}
          </div>

          <div className="reparto">
            <label>
              Reparto por activo
              <select
                value={vectorReparto}
                onChange={(e) => setVectorDelReparto(e.target.value as Vector)}
              >
                {vectoresConDatos.map((v) => (
                  <option key={v} value={v}>
                    {ETIQUETA[v]}
                  </option>
                ))}
              </select>
            </label>
            <Donut
              titulo={ETIQUETA[vectorReparto]}
              unidad={UNIDAD[vectorReparto]}
              color={COLOR[vectorReparto]}
              porciones={datos.activos
                .map((a) => ({
                  etiqueta: a.nombre,
                  valor: Number(
                    a.totales.find((t) => t.vector === vectorReparto)?.medido ?? 0,
                  ),
                }))
                .filter((p) => p.valor > 0)}
            />
          </div>

          {/* La misma información en tabla. No es un extra de accesibilidad:
              dos de los cuatro tonos no llegan a 3:1 en modo claro, así que la
              tabla es parte del trato. */}
          <table className="activos">
            <caption>
              Activos del periodo · intensidades sobre la superficie de referencia de cada uno
            </caption>
            <thead>
              <tr>
                <th>Activo</th>
                <th>Superficie</th>
                <th>Ocupantes</th>
                {vectoresConDatos.map((v) => (
                  <th key={v} colSpan={2}>
                    {ETIQUETA[v]}
                  </th>
                ))}
              </tr>
              <tr className="subcabecera">
                <th />
                <th>m²</th>
                <th>media</th>
                {vectoresConDatos.map((v) => (
                  <Fragment key={v}>
                    <th>{UNIDAD[v]}</th>
                    <th>{UNIDAD[v]}/m²</th>
                  </Fragment>
                ))}
              </tr>
            </thead>
            <tbody>
              {datos.activos.map((a) => (
                <tr key={a.activo_id}>
                  <th scope="row">
                    <span className="codigo">{a.codigo}</span> {a.nombre}
                  </th>
                  <td>
                    {cantidad(a.superficie_m2)}
                    <span className="apagado"> {a.superficie_de_referencia.toLowerCase()}</span>
                  </td>
                  <td>{cantidad(a.ocupantes_medios)}</td>
                  {vectoresConDatos.map((v) => (
                    <Fragment key={v}>
                      <td>{cantidad(a.totales.find((t) => t.vector === v)?.medido)}</td>
                      <td>{cantidad(a.intensidades.find((i) => i.vector === v)?.por_m2)}</td>
                    </Fragment>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  )
}

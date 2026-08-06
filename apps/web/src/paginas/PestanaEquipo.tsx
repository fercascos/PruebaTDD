import { useCallback, useEffect, useState } from 'react'
import { borrar, enviar, obtener } from '../api/cliente'
import type { Activo, Equipo, SistemaTecnico } from '../api/tipos'
import { Campo, Rejilla } from '../ui/Formulario'
import { Mensaje, Vacio } from '../ui/Marco'
import { ImportarInventario } from './ImportarInventario'

const CONDICION = [
  { code: 'BUENO', nombre: 'Bueno' },
  { code: 'ACEPTABLE', nombre: 'Aceptable' },
  { code: 'DEFICIENTE', nombre: 'Deficiente' },
  { code: 'MUY_DEFICIENTE', nombre: 'Muy deficiente' },
  { code: 'FUERA_DE_SERVICIO', nombre: 'Fuera de servicio' },
] as const

const OBSOLESCENCIA = [
  { code: 'ACTUAL', nombre: 'Actual' },
  { code: 'PROXIMO_A_OBSOLETO', nombre: 'Próximo a obsoleto' },
  { code: 'OBSOLETO', nombre: 'Obsoleto' },
  { code: 'SIN_REPUESTOS', nombre: 'Sin repuestos' },
] as const

const CRITICIDAD = [
  { code: 'ALTA', nombre: 'Alta' },
  { code: 'MEDIA', nombre: 'Media' },
  { code: 'BAJA', nombre: 'Baja' },
] as const

function nombreDe(lista: readonly { code: string; nombre: string }[], code: string | null) {
  return lista.find((x) => x.code === code)?.nombre ?? '—'
}

/**
 * Inventario de equipo `[REQ]` §7 / P-15.
 *
 * **Es opcional.** Un encargo entero se puede entregar sin dar de alta un solo
 * equipo, y nada en la aplicación lo reclama. Existe porque en una visita a un
 * edificio con instalaciones alguien apunta el fabricante, el modelo y el año
 * de la enfriadora en una libreta, y esa libreta acaba siendo la única fuente
 * para justificar por qué se propone sustituirla.
 *
 * **La vida residual no se teclea** (P-15). Se introduce el año de instalación
 * y la vida útil esperada; lo que queda lo calcula el servidor cada vez que se
 * lee, así que un inventario cargado hoy sigue diciendo la verdad en 2029.
 *
 * **Estado y obsolescencia son columnas distintas a propósito.** Una caldera
 * de 1998 en perfecto estado de conservación sigue siendo obsoleta —sin
 * repuestos y fuera de reglamento— y hay que sustituirla igual. Fundirlas en
 * una sola columna perdería justo el caso que decide la sustitución.
 */
export function PestanaEquipo({ projectId }: { projectId: string }) {
  const [equipos, setEquipos] = useState<Equipo[] | null>(null)
  const [activos, setActivos] = useState<Activo[]>([])
  const [sistemas, setSistemas] = useState<SistemaTecnico[]>([])
  const [activo, setActivo] = useState('')
  const [sistema, setSistema] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [soloVencidos, setSoloVencidos] = useState(false)
  const [creando, setCreando] = useState(false)
  const [importando, setImportando] = useState(false)
  const [editando, setEditando] = useState<Equipo | null>(null)
  const [error, setError] = useState<string | null>(null)

  const recargar = useCallback(() => {
    const p = new URLSearchParams()
    if (activo) p.set('asset_id', activo)
    if (sistema) p.set('technical_system_id', sistema)
    if (busqueda.trim()) p.set('q', busqueda.trim())
    if (soloVencidos) p.set('solo_vencidos', 'true')
    obtener<Equipo[]>(`/projects/${projectId}/equipment?${p}`)
      .then(setEquipos)
      .catch((e: Error) => setError(e.message))
  }, [projectId, activo, sistema, busqueda, soloVencidos])

  useEffect(recargar, [recargar])

  useEffect(() => {
    obtener<Activo[]>(`/projects/${projectId}/assets`)
      .then(setActivos)
      .catch(() => setActivos([]))
    obtener<SistemaTecnico[]>('/catalogs/technical-systems')
      .then(setSistemas)
      .catch(() => setSistemas([]))
  }, [projectId])

  async function eliminar(equipo: Equipo) {
    setError(null)
    try {
      await borrar(`/equipment/${equipo.id}`)
      recargar()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  if (importando) {
    return (
      <ImportarInventario
        projectId={projectId}
        alTerminar={recargar}
        alCerrar={() => {
          setImportando(false)
          recargar()
        }}
      />
    )
  }

  if (editando || creando) {
    return (
      <FichaDeEquipo
        projectId={projectId}
        equipo={editando}
        activos={activos}
        sistemas={sistemas}
        activoPorDefecto={activo}
        alGuardar={() => {
          setEditando(null)
          setCreando(false)
          recargar()
        }}
        alCerrar={() => {
          setEditando(null)
          setCreando(false)
        }}
      />
    )
  }

  const vencidos = equipos?.filter((e) => e.vencido).length ?? 0

  return (
    <div className="inventario">
      {error && <Mensaje tipo="error">{error}</Mensaje>}

      <div className="filtro">
        <Campo etiqueta="Activo">
          <select value={activo} onChange={(e) => setActivo(e.target.value)}>
            <option value="">— todos —</option>
            {activos.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </Campo>
        <Campo etiqueta="Sistema técnico">
          <select value={sistema} onChange={(e) => setSistema(e.target.value)}>
            <option value="">— todos —</option>
            {sistemas.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name_es}
              </option>
            ))}
          </select>
        </Campo>
        <Campo etiqueta="Buscar" ayuda="Fabricante, modelo, número de serie…">
          <input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
        </Campo>
        <label className="casilla">
          <input
            type="checkbox"
            checked={soloVencidos}
            onChange={(e) => setSoloVencidos(e.target.checked)}
          />
          Solo los que han agotado su vida útil
        </label>
        <button
          type="button"
          className="secundario"
          onClick={() => setImportando(true)}
          disabled={activos.length === 0}
        >
          Importar desde Excel
        </button>
        <button type="button" onClick={() => setCreando(true)} disabled={activos.length === 0}>
          Añadir equipo
        </button>
      </div>

      {activos.length === 0 && (
        <Mensaje tipo="aviso">
          El encargo todavía no tiene activos. Un equipo cuelga siempre de uno: dé de alta el
          edificio primero.
        </Mensaje>
      )}

      {!equipos ? (
        <p className="cargando">Cargando el inventario…</p>
      ) : equipos.length === 0 ? (
        <Vacio>
          Sin equipos en el inventario. Es opcional: un encargo se entrega igual sin él. Sirve para
          apuntar en la visita el fabricante, el modelo y el año de lo que después se propone
          sustituir.
        </Vacio>
      ) : (
        <>
          {vencidos > 0 && (
            <Mensaje tipo="aviso">
              {vencidos} equipo(s) han agotado su vida útil esperada. Es una estimación a partir del
              año de instalación, no un dictamen: un equipo con mantenimiento puede seguir dando
              servicio.
            </Mensaje>
          )}
          <div className="desbordable">
            <table className="tabla inventario">
              <thead>
                <tr>
                  <th scope="col">Etiqueta</th>
                  <th scope="col">Equipo</th>
                  <th scope="col">Sistema</th>
                  <th scope="col">Fabricante y modelo</th>
                  <th scope="col">Nº de serie</th>
                  <th scope="col" className="numerica">
                    Instalado
                  </th>
                  <th scope="col" className="numerica">
                    Vida útil
                  </th>
                  <th scope="col">Vida residual</th>
                  <th scope="col">Estado</th>
                  <th scope="col">Obsolescencia</th>
                  <th scope="col">Criticidad</th>
                  <th scope="col">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {equipos.map((e) => (
                  <tr key={e.id} className={e.vencido ? 'vencido' : ''}>
                    <td>{e.tag ?? '—'}</td>
                    <td>
                      {e.equipment_type}
                      {Number(e.quantity) !== 1 && (
                        <span className="ayuda">
                          {' '}
                          × {e.quantity} {e.unit}
                        </span>
                      )}
                    </td>
                    <td>{e.technical_system_name ?? '—'}</td>
                    <td>
                      {e.manufacturer ?? '—'}
                      {e.model && <div className="ayuda">{e.model}</div>}
                    </td>
                    <td>{e.serial_number ?? '—'}</td>
                    <td className="numerica">{e.install_year ?? '—'}</td>
                    <td className="numerica">
                      {e.expected_life_years ? `${e.expected_life_years} años` : '—'}
                    </td>
                    {/* [REQ] P-15 · Calculada por el servidor en cada lectura, con
                        el texto explicando en qué plazo cae la reposición. Nunca
                        se identifica solo por color: la cifra está escrita. */}
                    <td className="vida" title={e.vida_resumen}>
                      {e.remaining_life_years === null ? (
                        <span className="ayuda">sin datos</span>
                      ) : (
                        <>
                          <strong>
                            {e.remaining_life_years < 0
                              ? `vencida hace ${Math.abs(e.remaining_life_years)} años`
                              : `${e.remaining_life_years} años`}
                          </strong>
                          {e.horizonte_name && <div className="ayuda">{e.horizonte_name}</div>}
                        </>
                      )}
                    </td>
                    <td>{nombreDe(CONDICION, e.condition)}</td>
                    <td>{nombreDe(OBSOLESCENCIA, e.obsolescence)}</td>
                    <td>{nombreDe(CRITICIDAD, e.criticality)}</td>
                    <td className="acciones">
                      <button type="button" className="enlace" onClick={() => setEditando(e)}>
                        Editar
                      </button>
                      <button
                        type="button"
                        className="enlace"
                        onClick={() => void eliminar(e)}
                        title="Se conserva en la base: la ficha se escribió en una visita a la que no se vuelve"
                      >
                        Quitar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

type Formulario = {
  asset_id: string
  equipment_type: string
  technical_system_id: string
  tag: string
  manufacturer: string
  model: string
  serial_number: string
  install_year: string
  expected_life_years: string
  condition: string
  obsolescence: string
  criticality: string
  quantity: string
  unit: string
  has_documentation: boolean
  notes: string
}

function desde(equipo: Equipo | null, activoPorDefecto: string, activos: Activo[]): Formulario {
  return {
    // `||` y no `??`: el filtro de activo vale CADENA VACÍA cuando está en
    // «todos», y `??` solo cae al siguiente valor con null o undefined. Con
    // `??` el formulario se quedaba sin activo mientras el desplegable
    // enseñaba el primero —el navegador hace eso cuando el valor no casa con
    // ninguna opción—, así que parecía relleno y el botón de guardar seguía
    // deshabilitado sin decir por qué.
    asset_id: equipo?.asset_id || activoPorDefecto || activos[0]?.id || '',
    equipment_type: equipo?.equipment_type ?? '',
    technical_system_id: equipo?.technical_system_id ?? '',
    tag: equipo?.tag ?? '',
    manufacturer: equipo?.manufacturer ?? '',
    model: equipo?.model ?? '',
    serial_number: equipo?.serial_number ?? '',
    install_year: equipo?.install_year?.toString() ?? '',
    expected_life_years: equipo?.expected_life_years?.toString() ?? '',
    condition: equipo?.condition ?? '',
    obsolescence: equipo?.obsolescence ?? '',
    criticality: equipo?.criticality ?? '',
    quantity: equipo?.quantity ?? '1',
    unit: equipo?.unit ?? 'ud',
    has_documentation: equipo?.has_documentation ?? false,
    notes: equipo?.notes ?? '',
  }
}

function FichaDeEquipo({
  projectId,
  equipo,
  activos,
  sistemas,
  activoPorDefecto,
  alGuardar,
  alCerrar,
}: {
  projectId: string
  equipo: Equipo | null
  activos: Activo[]
  sistemas: SistemaTecnico[]
  activoPorDefecto: string
  alGuardar: () => void
  alCerrar: () => void
}) {
  const [f, setF] = useState<Formulario>(() => desde(equipo, activoPorDefecto, activos))
  const [error, setError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)

  function cambiar<K extends keyof Formulario>(campo: K, valor: Formulario[K]) {
    setF((previo) => ({ ...previo, [campo]: valor }))
  }

  // [REQ] P-15 · La vida residual se enseña calculada mientras se teclea, y el
  // campo no existe: es la forma de que quede claro que no se introduce.
  const anio = new Date().getFullYear()
  const fin =
    f.install_year && f.expected_life_years
      ? Number(f.install_year) + Number(f.expected_life_years)
      : null

  // El año de instalación y la vida esperada van juntos o no van: con la mitad
  // del dato no hay nada que calcular, y la base lo rechaza con un CHECK.
  const mediaVida = Boolean(f.install_year) !== Boolean(f.expected_life_years)

  async function guardar() {
    setError(null)
    setGuardando(true)
    const cuerpo = {
      equipment_type: f.equipment_type.trim(),
      technical_system_id: f.technical_system_id || null,
      tag: f.tag.trim() || null,
      manufacturer: f.manufacturer.trim() || null,
      model: f.model.trim() || null,
      serial_number: f.serial_number.trim() || null,
      install_year: f.install_year ? Number(f.install_year) : null,
      expected_life_years: f.expected_life_years ? Number(f.expected_life_years) : null,
      condition: f.condition || null,
      obsolescence: f.obsolescence || null,
      criticality: f.criticality || null,
      quantity: f.quantity || '1',
      unit: f.unit.trim() || 'ud',
      has_documentation: f.has_documentation,
      notes: f.notes.trim() || null,
    }
    try {
      if (equipo) {
        await enviar(`/equipment/${equipo.id}`, cuerpo, 'PATCH')
      } else {
        await enviar(`/projects/${projectId}/equipment`, { ...cuerpo, asset_id: f.asset_id })
      }
      alGuardar()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="ficha-equipo">
      <div className="titular">
        <h2>{equipo ? 'Editar equipo' : 'Nuevo equipo'}</h2>
        <button type="button" className="secundario" onClick={alCerrar}>
          Cerrar
        </button>
      </div>

      {error && <Mensaje tipo="error">{error}</Mensaje>}

      <section>
        <h3>Identificación</h3>
        <Rejilla>
          <Campo etiqueta="Activo">
            <select
              value={f.asset_id}
              onChange={(e) => cambiar('asset_id', e.target.value)}
              disabled={equipo !== null}
            >
              {activos.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Etiqueta" ayuda="Como está rotulado en la sala: CL-01, AS-Norte…">
            <input
              value={f.tag}
              maxLength={40}
              onChange={(e) => cambiar('tag', e.target.value)}
            />
          </Campo>
          <Campo etiqueta="Tipo de equipo">
            <input
              value={f.equipment_type}
              maxLength={120}
              onChange={(e) => cambiar('equipment_type', e.target.value)}
              placeholder="Enfriadora, ascensor, cuadro general…"
            />
          </Campo>
          <Campo etiqueta="Sistema técnico">
            <select
              value={f.technical_system_id}
              onChange={(e) => cambiar('technical_system_id', e.target.value)}
            >
              <option value="">— sin clasificar —</option>
              {sistemas.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name_es}
                </option>
              ))}
            </select>
          </Campo>
        </Rejilla>
        <Rejilla>
          <Campo etiqueta="Fabricante">
            <input
              value={f.manufacturer}
              maxLength={120}
              onChange={(e) => cambiar('manufacturer', e.target.value)}
            />
          </Campo>
          <Campo etiqueta="Modelo">
            <input
              value={f.model}
              maxLength={120}
              onChange={(e) => cambiar('model', e.target.value)}
            />
          </Campo>
          <Campo etiqueta="Número de serie">
            <input
              value={f.serial_number}
              maxLength={120}
              onChange={(e) => cambiar('serial_number', e.target.value)}
            />
          </Campo>
          <Campo etiqueta="Cantidad">
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={f.quantity}
              onChange={(e) => cambiar('quantity', e.target.value)}
            />
          </Campo>
          <Campo etiqueta="Unidad">
            <input
              value={f.unit}
              maxLength={20}
              onChange={(e) => cambiar('unit', e.target.value)}
            />
          </Campo>
        </Rejilla>
      </section>

      <section>
        <h3>Vida útil</h3>
        <Rejilla>
          <Campo etiqueta="Año de instalación">
            <input
              type="number"
              min={1800}
              max={2200}
              value={f.install_year}
              onChange={(e) => cambiar('install_year', e.target.value)}
            />
          </Campo>
          <Campo etiqueta="Vida útil esperada (años)">
            <input
              type="number"
              min={1}
              max={200}
              value={f.expected_life_years}
              onChange={(e) => cambiar('expected_life_years', e.target.value)}
            />
          </Campo>
        </Rejilla>

        {mediaVida && (
          <Mensaje tipo="aviso">
            El año de instalación y la vida útil esperada van juntos o no van: con solo uno de los
            dos no hay vida residual que calcular.
          </Mensaje>
        )}

        {/* [REQ] P-15 · No hay campo de vida residual, y no es un descuido: se
            calcula. Enseñarla aquí mientras se teclea evita que alguien la
            busque para rellenarla a mano. */}
        <p className="vida-calculada">
          {fin === null ? (
            <span className="ayuda">
              La vida residual se calcula: rellene el año de instalación y la vida útil esperada.
            </span>
          ) : (
            <>
              Agota su vida útil en <strong>{fin}</strong>
              {' · '}
              {fin - anio < 0
                ? `vencida hace ${anio - fin} año(s)`
                : `le quedan ${fin - anio} año(s)`}
              . <span className="ayuda">Se recalcula sola cada año: no se guarda.</span>
            </>
          )}
        </p>
      </section>

      <section>
        <h3>Valoración</h3>
        <Rejilla>
          <Campo etiqueta="Estado de conservación">
            <select value={f.condition} onChange={(e) => cambiar('condition', e.target.value)}>
              <option value="">— sin valorar —</option>
              {CONDICION.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </Campo>
          <Campo
            etiqueta="Obsolescencia"
            ayuda="No es lo mismo que el estado: un equipo bien conservado puede no tener repuestos"
          >
            <select
              value={f.obsolescence}
              onChange={(e) => cambiar('obsolescence', e.target.value)}
            >
              <option value="">— sin valorar —</option>
              {OBSOLESCENCIA.map((o) => (
                <option key={o.code} value={o.code}>
                  {o.nombre}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Criticidad" ayuda="Qué pasa si se para">
            <select value={f.criticality} onChange={(e) => cambiar('criticality', e.target.value)}>
              <option value="">— sin valorar —</option>
              {CRITICIDAD.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </Campo>
        </Rejilla>
        <label className="casilla">
          <input
            type="checkbox"
            checked={f.has_documentation}
            onChange={(e) => cambiar('has_documentation', e.target.checked)}
          />
          Hay documentación del equipo (manual, ficha técnica, contrato de mantenimiento)
        </label>
        <Campo etiqueta="Observaciones">
          <textarea rows={3} value={f.notes} onChange={(e) => cambiar('notes', e.target.value)} />
        </Campo>
      </section>

      <div className="acciones">
        <button
          type="button"
          onClick={() => void guardar()}
          disabled={guardando || !f.equipment_type.trim() || !f.asset_id || mediaVida}
        >
          {guardando ? 'Guardando…' : 'Guardar equipo'}
        </button>
        <button type="button" className="secundario" onClick={alCerrar}>
          Cancelar
        </button>
      </div>
    </div>
  )
}

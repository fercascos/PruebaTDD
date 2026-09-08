import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { enviar, obtener } from '../api/cliente'
import type { Proyecto } from '../api/tipos'
import { Campo, Formulario, Rejilla } from '../ui/Formulario'

type Cliente = { id: string; name: string; projects: number }

/**
 * Las ocho fases del proceso, con la explicación de qué significa cada una.
 *
 * `[REQ]` §3.1.5 · **Se eligen a la carta al dar de alta el proyecto.** Un
 * proyecto sin Q&A no debe arrastrar una fase vacía que nadie va a rellenar y
 * que ensucia la ficha para siempre.
 */
const FASES = [
  { code: 'SOLICITUD_DOCUMENTACION', nombre: 'Solicitud de documentación', porDefecto: true },
  { code: 'VDR', nombre: 'Acceso al repositorio del cliente', porDefecto: false },
  { code: 'VISITA', nombre: 'Visita a los activos', porDefecto: true },
  { code: 'QA', nombre: 'Rondas de preguntas y respuestas', porDefecto: false },
  {
    code: 'RED_FLAG_CAPEX',
    nombre: 'Red Flag / CAPEX',
    porDefecto: true,
    calculada: true,
  },
  { code: 'FULL_REPORT', nombre: 'Informe completo', porDefecto: true, calculada: true },
  { code: 'PRESENTACION_CLIENTE', nombre: 'Presentación al cliente', porDefecto: false },
  { code: 'DEFENSA', nombre: 'Defensa del informe', porDefecto: false },
] as const

export function NuevoProyecto() {
  const navegar = useNavigate()
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [clienteId, setClienteId] = useState('')
  const [clienteNuevo, setClienteNuevo] = useState('')
  const [nombre, setNombre] = useState('')
  const [arranque, setArranque] = useState('')
  const [cierre, setCierre] = useState('')
  const [fecha, setFecha] = useState('')
  const [fases, setFases] = useState<Set<string>>(
    new Set(FASES.filter((f) => f.porDefecto).map((f) => f.code)),
  )

  useEffect(() => {
    obtener<Cliente[]>('/clients')
      .then(setClientes)
      .catch(() => setClientes([]))
  }, [])

  async function guardar() {
    // `[REQ]` El cliente que no está en la lista **no bloquea**: se manda el
    // nombre y la API crea el proyecto igual, con el cliente pendiente de
    // validar y un aviso en el buzón del administrador. Antes se daba de alta
    // aquí mismo, y un cliente entraba al catálogo sin que nadie lo revisara.
    const proyecto = await enviar<Proyecto>('/projects', {
      ...(clienteId ? { client_id: clienteId } : { client_name: clienteNuevo.trim() }),
      name: nombre.trim(),
      start_date: arranque || null,
      close_date: cierre || null,
      report_due_date: fecha || null,
      applicable_phases: [...fases].map((code) => ({ code })),
    })
    navegar(`/proyectos/${proyecto.id}`)
  }

  function alternar(code: string) {
    setFases((previas) => {
      const nuevas = new Set(previas)
      if (nuevas.has(code)) nuevas.delete(code)
      else nuevas.add(code)
      return nuevas
    })
  }

  return (
    <>
      <h1>Nuevo proyecto</h1>
      <Formulario
        titulo="Datos del proyecto"
        enviar={guardar}
        textoDeEnvio="Crear proyecto"
        alCancelar={() => navegar('/proyectos')}
      >
        <Rejilla>
          {/* `[REQ]` El código lo genera el servidor al crear: `AAAA-NNN`, por
              organización y año. Se enseña bloqueado y no oculto porque es lo
              primero que se dice por teléfono, y **no se puede cambiar
              después**: la API no tiene por dónde. */}
          <Campo
            etiqueta="Código interno"
            ayuda="Lo asigna la aplicación al crear el proyecto. Único e inalterable"
          >
            <div className="campo-bloqueado">
              <output>Se genera al crear · 2026-NNN</output>
            </div>
          </Campo>
          <Campo etiqueta="Nombre del proyecto">
            <input
              required
              maxLength={200}
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="TDD Cartera Norte"
            />
          </Campo>
          <Campo etiqueta="Cliente">
            <select
              value={clienteId}
              onChange={(e) => {
                setClienteId(e.target.value)
                if (e.target.value) setClienteNuevo('')
              }}
            >
              <option value="">— no está en la lista —</option>
              {clientes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.projects})
                </option>
              ))}
            </select>
          </Campo>
          {!clienteId && (
            <Campo
              etiqueta="Si no está en la lista, escríbalo"
              ayuda="No bloquea: el proyecto se crea y el administrador recibe el aviso para validarlo"
            >
              <input
                required
                value={clienteNuevo}
                onChange={(e) => setClienteNuevo(e.target.value)}
                placeholder="Inversora Ficticia S.L."
              />
            </Campo>
          )}
          <Campo etiqueta="Fecha de arranque">
            <input type="date" value={arranque} onChange={(e) => setArranque(e.target.value)} />
          </Campo>
          <Campo etiqueta="Fecha de cierre prevista">
            <input
              type="date"
              value={cierre}
              min={arranque || undefined}
              onChange={(e) => setCierre(e.target.value)}
            />
          </Campo>
          <Campo etiqueta="Fecha de entrega prevista" ayuda="El compromiso de entrega del informe">
            <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </Campo>
        </Rejilla>

        <h3>Fases aplicables</h3>
        <p className="ayuda">
          Se crean solo las que marque. Un proyecto sin Q&amp;A no arrastra una fase vacía que nadie
          va a rellenar. Las marcadas como <em>calculada</em> no se marcan a mano después: su estado
          sale del trabajo que hay debajo.
        </p>
        <ul className="lista-fases">
          {FASES.map((f) => (
            <li key={f.code}>
              <label className="casilla">
                <input
                  type="checkbox"
                  checked={fases.has(f.code)}
                  onChange={() => alternar(f.code)}
                />
                {f.nombre}
                {'calculada' in f && f.calculada && <span className="candado">calculada</span>}
              </label>
            </li>
          ))}
        </ul>
      </Formulario>
    </>
  )
}

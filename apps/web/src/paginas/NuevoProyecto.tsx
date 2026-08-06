import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { enviar, obtener } from '../api/cliente'
import type { Proyecto } from '../api/tipos'
import { Campo, Formulario, Rejilla } from '../ui/Formulario'

type Cliente = { id: string; name: string; projects: number }

/**
 * Las ocho fases del proceso, con la explicación de qué significa cada una.
 *
 * `[REQ]` §3.1.5 · **Se eligen a la carta al dar de alta el encargo.** Un
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
  const [codigo, setCodigo] = useState('')
  const [nombre, setNombre] = useState('')
  const [moneda, setMoneda] = useState('EUR')
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
    // El cliente puede no existir todavía: darlo de alta aquí evita mandar al
    // usuario a otra pantalla a mitad de rellenar el encargo, que es donde se
    // pierde lo escrito.
    let cliente = clienteId
    if (!cliente && clienteNuevo.trim()) {
      cliente = (await enviar<Cliente>('/clients', { name: clienteNuevo.trim() })).id
    }
    if (!cliente) throw new Error('Elija un cliente o escriba el nombre de uno nuevo')

    const proyecto = await enviar<Proyecto>('/projects', {
      client_id: cliente,
      internal_code: codigo.trim(),
      name: nombre.trim(),
      currency: moneda,
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
      <h1>Nuevo encargo</h1>
      <Formulario
        titulo="Datos del encargo"
        enviar={guardar}
        textoDeEnvio="Crear encargo"
        alCancelar={() => navegar('/proyectos')}
      >
        <Rejilla>
          <Campo etiqueta="Código interno" ayuda="Único dentro de la organización">
            <input
              required
              maxLength={40}
              value={codigo}
              onChange={(e) => setCodigo(e.target.value)}
              placeholder="2026-014"
            />
          </Campo>
          <Campo etiqueta="Nombre del encargo">
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
              <option value="">— dar de alta uno nuevo —</option>
              {clientes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.projects})
                </option>
              ))}
            </select>
          </Campo>
          {!clienteId && (
            <Campo etiqueta="Nombre del cliente nuevo">
              <input
                value={clienteNuevo}
                onChange={(e) => setClienteNuevo(e.target.value)}
                placeholder="Inversora Ficticia S.L."
              />
            </Campo>
          )}
          <Campo etiqueta="Moneda">
            <select value={moneda} onChange={(e) => setMoneda(e.target.value)}>
              <option value="EUR">EUR</option>
              <option value="USD">USD</option>
              <option value="GBP">GBP</option>
            </select>
          </Campo>
          <Campo etiqueta="Fecha de entrega prevista">
            <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </Campo>
        </Rejilla>

        <h3>Fases aplicables</h3>
        <p className="ayuda">
          Se crean solo las que marque. Un encargo sin Q&amp;A no arrastra una fase vacía que nadie
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

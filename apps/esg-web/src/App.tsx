import { useState } from 'react'

import { Cargar } from './paginas/Cargar'
import { Entrar } from './paginas/Entrar'
import { Panel } from './paginas/Panel'
import { Revision } from './paginas/Revision'
import { useSesion } from './sesion'

type Pestana = 'panel' | 'cargar' | 'revision'

export function App() {
  const { yo, cargando, salir } = useSesion()
  const [pestana, setPestana] = useState<Pestana>('panel')

  if (cargando) return <main className="cargando">Entrando…</main>
  if (!yo) return <Entrar />

  return (
    <>
      <header className="barra">
        <h1>Panel ESG</h1>
        <nav>
          <button
            type="button"
            className={pestana === 'panel' ? 'activa' : ''}
            onClick={() => setPestana('panel')}
          >
            Panel
          </button>
          {/* Las pestañas de carga no se enseñan a quien no puede cargar. La
              API responde 403 igual: esto es cortesía, no seguridad. */}
          {yo.escribe_datos && (
            <>
              <button
                type="button"
                className={pestana === 'cargar' ? 'activa' : ''}
                onClick={() => setPestana('cargar')}
              >
                Cargar fichero
              </button>
              <button
                type="button"
                className={pestana === 'revision' ? 'activa' : ''}
                onClick={() => setPestana('revision')}
              >
                Facturas IA
              </button>
            </>
          )}
        </nav>
        <div className="quien">
          <span title={`${yo.email} · ${yo.rol}`}>
            {yo.nombre} <em>{yo.organizacion}</em>
          </span>
          <button type="button" onClick={() => void salir()}>
            Salir
          </button>
        </div>
      </header>
      <main>
        {pestana === 'panel' && <Panel />}
        {pestana === 'cargar' && <Cargar />}
        {pestana === 'revision' && <Revision puedeEscribir={yo.escribe_datos} />}
      </main>
    </>
  )
}

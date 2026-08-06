import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { cerrarSesion, obtener } from '../api/cliente'
import type { Perfil } from '../api/tipos'

export function Marco({ children }: { children: ReactNode }) {
  const [perfil, setPerfil] = useState<Perfil | null>(null)
  const navegar = useNavigate()

  useEffect(() => {
    obtener<Perfil>('/auth/me')
      .then(setPerfil)
      .catch(() => setPerfil(null))
  }, [])

  return (
    <div className="marco">
      <header className="cabecera">
        <strong className="marca">Due diligence técnica</strong>
        <nav>
          <NavLink to="/proyectos">Proyectos</NavLink>
          <NavLink to="/plantillas">Plantillas</NavLink>
          <NavLink to="/sugerencias">Sugerencias</NavLink>
        </nav>
        <div className="sesion">
          {perfil && (
            <span title={perfil.email}>
              {perfil.full_name} · <em>{perfil.org_role}</em>
            </span>
          )}
          <button
            type="button"
            className="secundario"
            onClick={() => void cerrarSesion().then(() => navegar('/entrar'))}
          >
            Salir
          </button>
        </div>
      </header>
      <main>{children}</main>
    </div>
  )
}

export function Mensaje({ tipo, children }: { tipo: 'error' | 'aviso' | 'ok'; children: ReactNode }) {
  return (
    <p className={`mensaje ${tipo}`} role={tipo === 'error' ? 'alert' : 'status'}>
      {children}
    </p>
  )
}

/**
 * Estado vacío con explicación.
 *
 * Una tabla vacía sin más deja al usuario preguntándose si no hay datos o si
 * ha fallado la carga. Decirlo cuesta una línea.
 */
export function Vacio({ children }: { children: ReactNode }) {
  return <p className="vacio">{children}</p>
}

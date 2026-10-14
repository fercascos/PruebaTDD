import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { cerrarSesion, obtener } from '../api/cliente'
import type { Perfil } from '../api/tipos'
import { useIdioma, useT } from '../i18n/idioma'
import { useHayRed } from './red'

/**
 * El selector de idioma `[REQ]` S-05.
 *
 * Vive en la cabecera y no en un ajuste escondido: quien abre la aplicación en
 * inglés tiene que poder cambiarla sin saber dónde buscar, y quien la enseña a
 * un compañero de fuera, también.
 */
function Idioma() {
  const { idioma, cambiar } = useIdioma()
  const t = useT()
  return (
    <div className="idioma-interfaz" role="group" aria-label={t('Idioma de la interfaz')}>
      <button
        type="button"
        className={idioma === 'es' ? 'activo' : ''}
        aria-pressed={idioma === 'es'}
        onClick={() => cambiar('es')}
      >
        ES
      </button>
      <button
        type="button"
        className={idioma === 'en' ? 'activo' : ''}
        aria-pressed={idioma === 'en'}
        onClick={() => cambiar('en')}
      >
        EN
      </button>
    </div>
  )
}

export function Marco({ children }: { children: ReactNode }) {
  const [perfil, setPerfil] = useState<Perfil | null>(null)
  const hayRed = useHayRed()
  const navegar = useNavigate()
  const t = useT()

  useEffect(() => {
    obtener<Perfil>('/auth/me')
      .then(setPerfil)
      .catch(() => setPerfil(null))
  }, [])

  return (
    <div className="marco">
      <header className="cabecera">
        <strong className="marca">{t('Due diligence técnica')}</strong>
        <nav>
          <NavLink to="/proyectos">{t('Proyectos')}</NavLink>
          <NavLink to="/plantillas">{t('Plantillas')}</NavLink>
          <NavLink to="/sugerencias">{t('Sugerencias')}</NavLink>
          <NavLink to="/personas">{t('Personas')}</NavLink>
        </nav>
        <div className="sesion">
          <Idioma />
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
            {t('Salir')}
          </button>
        </div>
      </header>
      {!hayRed && (
        <p className="sin-red" role="status">
          <strong>{t('Sin conexión.')}</strong>{' '}
          {t(
            'Puede seguir haciendo fotografías: se guardan en el dispositivo y se suben cuando vuelva la cobertura. Lo demás necesita red y va a fallar.',
          )}
        </p>
      )}
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

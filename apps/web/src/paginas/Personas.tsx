import { useCallback, useEffect, useState } from 'react'
import { enviar, obtener } from '../api/cliente'
import type { Perfil } from '../api/tipos'
import { Campo, Formulario, Rejilla } from '../ui/Formulario'
import { Mensaje, Vacio } from '../ui/Marco'

type Persona = {
  id: string
  full_name: string
  email: string
  org_role: string
  is_active: boolean
}

/** Los seis roles de §11. La API los valida igualmente y dice cuáles valen. */
const ROLES = [
  { code: 'ADMIN', nombre: 'Administrador' },
  { code: 'DIRECTOR_PROYECTO', nombre: 'Director de proyecto' },
  { code: 'CONSULTOR', nombre: 'Consultor' },
  { code: 'TECNICO_ESPECIALISTA', nombre: 'Técnico especialista' },
  { code: 'REVISOR', nombre: 'Revisor' },
  { code: 'LECTOR', nombre: 'Lector' },
] as const

/**
 * Personas de la organización.
 *
 * Sin esta pantalla la aplicación la usaba **una sola persona**: la cuenta que
 * crea `make db-admin`. Dar de alta al resto del equipo existía en la API y no
 * tenía dónde pulsarse.
 *
 * `[REC]` La contraseña inicial la fija quien da de alta. Lo correcto sería una
 * invitación por correo, que exige SMTP y no está montado; mientras tanto se
 * dice en pantalla que hay que comunicarla por un canal aparte y que la persona
 * debería cambiarla al entrar. No se disimula.
 */
export function Personas() {
  const [personas, setPersonas] = useState<Persona[] | null>(null)
  const [perfil, setPerfil] = useState<Perfil | null>(null)
  const [dando, setDando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  const recargar = useCallback(() => {
    obtener<Persona[]>('/users?incluir_inactivos=true')
      .then(setPersonas)
      .catch((e: Error) => setError(e.message))
  }, [])

  useEffect(() => {
    recargar()
    obtener<Perfil>('/auth/me')
      .then(setPerfil)
      .catch(() => setPerfil(null))
  }, [recargar])

  const esAdmin = perfil?.org_role === 'ADMIN'

  async function cambiar(persona: Persona, cambios: Record<string, unknown>) {
    setError(null)
    setAviso(null)
    try {
      await enviar(`/users/${persona.id}`, cambios, 'PATCH')
      if (cambios.is_active === false) {
        setAviso(
          `Se han cerrado las sesiones abiertas de ${persona.full_name}. ` +
            'Desactivar echa a alguien ahora, no cuando caduque su token de refresco.',
        )
      }
      recargar()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  if (personas === null) return <p className="cargando">Cargando personas…</p>

  return (
    <>
      <h1>Personas</h1>
      <p className="ayuda">
        Quién puede entrar y con qué rol. La matriz completa de permisos está en{' '}
        <code>docs/07-roles-permisos.md</code>.
      </p>

      {error && <Mensaje tipo="error">{error}</Mensaje>}
      {aviso && <Mensaje tipo="aviso">{aviso}</Mensaje>}

      {!esAdmin && (
        <Mensaje tipo="aviso">
          Solo un administrador puede dar de alta o modificar cuentas. Aquí las ve, pero no las
          cambia: la API lo rechaza igualmente con un 403.
        </Mensaje>
      )}

      {esAdmin &&
        (dando ? (
          <Alta
            alGuardar={() => {
              setDando(false)
              recargar()
            }}
            alCancelar={() => setDando(false)}
          />
        ) : (
          <button type="button" onClick={() => setDando(true)}>
            Dar de alta a alguien
          </button>
        ))}

      {personas.length === 0 ? (
        <Vacio>No hay nadie más en la organización.</Vacio>
      ) : (
        <div className="desbordable">
          <table className="tabla">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Correo</th>
                <th>Rol</th>
                <th>Estado</th>
                {esAdmin && <th>Acciones</th>}
              </tr>
            </thead>
            <tbody>
              {personas.map((p) => (
                <tr key={p.id} className={p.is_active ? '' : 'inactiva'}>
                  <td>{p.full_name}</td>
                  <td>{p.email}</td>
                  <td>
                    {esAdmin && p.id !== perfil?.id ? (
                      <select
                        value={p.org_role}
                        onChange={(e) => void cambiar(p, { org_role: e.target.value })}
                      >
                        {ROLES.map((r) => (
                          <option key={r.code} value={r.code}>
                            {r.nombre}
                          </option>
                        ))}
                      </select>
                    ) : (
                      (ROLES.find((r) => r.code === p.org_role)?.nombre ?? p.org_role)
                    )}
                  </td>
                  <td>
                    <span className={`estado e-${p.is_active ? 'validado' : 'descartado'}`}>
                      {p.is_active ? 'Activa' : 'Desactivada'}
                    </span>
                  </td>
                  {esAdmin && (
                    <td>
                      {p.id === perfil?.id ? (
                        // Desactivarse a uno mismo deja la organización
                        // potencialmente sin administrador y al usuario fuera en
                        // la siguiente petición. La API devuelve 422; aquí ni se
                        // ofrece el botón.
                        <em className="ayuda">es su propia cuenta</em>
                      ) : (
                        <button
                          type="button"
                          className="secundario"
                          onClick={() => void cambiar(p, { is_active: !p.is_active })}
                        >
                          {p.is_active ? 'Desactivar' : 'Reactivar'}
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function Alta({ alGuardar, alCancelar }: { alGuardar: () => void; alCancelar: () => void }) {
  const [nombre, setNombre] = useState('')
  const [correo, setCorreo] = useState('')
  const [rol, setRol] = useState<string>('CONSULTOR')
  const [clave, setClave] = useState('')
  const [gestiona, setGestiona] = useState(false)

  return (
    <Formulario
      titulo="Nueva persona"
      textoDeEnvio="Dar de alta"
      alCancelar={alCancelar}
      enviar={async () => {
        await enviar('/users', {
          full_name: nombre.trim(),
          email: correo.trim(),
          org_role: rol,
          password: clave,
          can_manage_suggestions: gestiona,
        })
        alGuardar()
      }}
    >
      <Rejilla>
        <Campo etiqueta="Nombre y apellidos">
          <input required maxLength={160} value={nombre} onChange={(e) => setNombre(e.target.value)} />
        </Campo>
        <Campo etiqueta="Correo">
          <input
            required
            type="email"
            value={correo}
            onChange={(e) => setCorreo(e.target.value)}
            placeholder="nombre@ejemplo.example"
          />
        </Campo>
        <Campo etiqueta="Rol">
          <select value={rol} onChange={(e) => setRol(e.target.value)}>
            {ROLES.map((r) => (
              <option key={r.code} value={r.code}>
                {r.nombre}
              </option>
            ))}
          </select>
        </Campo>
      </Rejilla>

      <Campo
        etiqueta="Contraseña inicial"
        ayuda="Mínimo 12 caracteres. Comuníquela por un canal aparte; quien entre debería cambiarla"
      >
        <input
          required
          type="password"
          minLength={12}
          value={clave}
          onChange={(e) => setClave(e.target.value)}
        />
      </Campo>
      <p className="ayuda">
        `[REC]` Lo correcto sería una invitación por correo. Exige SMTP y no está montado, así que
        de momento la fija quien da de alta. No se disimula que es un apaño.
      </p>

      <label className="casilla">
        <input
          type="checkbox"
          checked={gestiona}
          onChange={(e) => setGestiona(e.target.checked)}
        />
        Atiende el buzón de sugerencias
      </label>
      <p className="ayuda">
        `[REQ]` P-41 · El permiso es separable del rol para que alguien pueda atender el buzón{' '}
        <strong>sin</strong> ser administrador. Un administrador lo atiende igualmente, lleve o no la
        marca.
      </p>
    </Formulario>
  )
}

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { enviar } from '../api/cliente'
import { Mensaje } from '../ui/Marco'

/**
 * «He olvidado mi contraseña» `[REQ]` §10.2.
 *
 * **La pantalla no sabe si la cuenta existe, y no debe saberlo.** El servidor
 * responde lo mismo siempre; aquí se enseña esa respuesta tal cual. Cualquier
 * intento de ser más útil —«ese correo no está registrado»— desharía la
 * protección que el servidor acaba de aplicar y convertiría el formulario en
 * un comprobador de cuentas.
 */
export function Recuperar() {
  const [email, setEmail] = useState('')
  const [aviso, setAviso] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function pedir(evento: React.FormEvent) {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      const r = await enviar<{ detail: string }>('/auth/password/forgot', { email })
      setAviso(r.detail)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="entrar">
      <form onSubmit={(e) => void pedir(e)}>
        <h1>Recuperar el acceso</h1>
        <p className="ayuda">
          Escriba su correo y le enviaremos un enlace para elegir una contraseña nueva.
        </p>

        <label>
          Correo electrónico
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>

        {error && <Mensaje tipo="error">{error}</Mensaje>}
        {aviso && <Mensaje tipo="ok">{aviso}</Mensaje>}

        <button type="submit" disabled={enviando || !email}>
          {enviando ? 'Enviando…' : 'Enviarme el enlace'}
        </button>
        <Link className="enlace" to="/entrar">
          Volver a entrar
        </Link>
      </form>
    </div>
  )
}

/**
 * Elegir contraseña nueva desde el enlace del correo.
 *
 * **El token se lee del fragmento** (`/restablecer#...`), no de la cadena de
 * consulta. El fragmento no se manda al servidor, así que el enlace no acaba
 * en el registro de acceso del proxy ni se filtra por la cabecera `Referer`.
 */
export function Restablecer() {
  const token = window.location.hash.slice(1)
  const [clave, setClave] = useState('')
  const [repetida, setRepetida] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [listo, setListo] = useState(false)
  const navegar = useNavigate()

  const noCoinciden = repetida !== '' && clave !== repetida

  async function guardar(evento: React.FormEvent) {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      await enviar('/auth/password/reset', { token, new_password: clave })
      setListo(true)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setEnviando(false)
    }
  }

  if (!token) {
    return (
      <div className="entrar">
        <form onSubmit={(e) => e.preventDefault()}>
          <h1>Enlace incompleto</h1>
          <Mensaje tipo="error">
            Este enlace no lleva el código de recuperación. Suele pasar al copiarlo a mano desde el
            correo: ábralo pulsando sobre él, o pida uno nuevo.
          </Mensaje>
          <Link className="enlace" to="/recuperar">
            Pedir un enlace nuevo
          </Link>
        </form>
      </div>
    )
  }

  if (listo) {
    return (
      <div className="entrar">
        <form onSubmit={(e) => e.preventDefault()}>
          <h1>Contraseña cambiada</h1>
          <Mensaje tipo="ok">
            Ya puede entrar con la contraseña nueva. Se han cerrado todas las sesiones que hubiera
            abiertas, también en otros dispositivos.
          </Mensaje>
          <button type="button" onClick={() => navegar('/entrar')}>
            Entrar
          </button>
        </form>
      </div>
    )
  }

  return (
    <div className="entrar">
      <form onSubmit={(e) => void guardar(e)}>
        <h1>Elegir contraseña nueva</h1>
        <p className="ayuda">
          El enlace caduca a los 30 minutos y solo sirve una vez. Al terminar se cerrarán todas sus
          sesiones abiertas.
        </p>

        <label>
          Contraseña nueva
          <input
            type="password"
            autoComplete="new-password"
            required
            value={clave}
            onChange={(e) => setClave(e.target.value)}
          />
        </label>

        <label>
          Repítala
          <input
            type="password"
            autoComplete="new-password"
            required
            value={repetida}
            onChange={(e) => setRepetida(e.target.value)}
          />
        </label>

        {/* Se comprueba aquí y no en el servidor: es un error de tecleo, no una
            regla de negocio, y esperar a la respuesta para decirlo gastaría un
            viaje por una errata. */}
        {noCoinciden && <Mensaje tipo="aviso">Las dos contraseñas no coinciden.</Mensaje>}
        {error && <Mensaje tipo="error">{error}</Mensaje>}

        <button type="submit" disabled={enviando || !clave || noCoinciden}>
          {enviando ? 'Guardando…' : 'Guardar la contraseña'}
        </button>
        <Link className="enlace" to="/recuperar">
          Pedir un enlace nuevo
        </Link>
      </form>
    </div>
  )
}

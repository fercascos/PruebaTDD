import { useState } from 'react'
import { ErrorDeApi, iniciarSesion } from '../api/cliente'
import { Mensaje } from '../ui/Marco'

export function Entrar() {
  const [email, setEmail] = useState('')
  const [clave, setClave] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function enviar(evento: React.FormEvent) {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      await iniciarSesion(email, clave)
    } catch (e) {
      // El servidor devuelve el mismo mensaje para correo desconocido y clave
      // incorrecta, y aquí no se intenta adivinar cuál fue: distinguirlo en la
      // interfaz desharía la protección que el servidor acaba de aplicar.
      setError(
        e instanceof ErrorDeApi && e.status === 429
          ? e.message
          : 'Correo o contraseña incorrectos',
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="entrar">
      <form onSubmit={(e) => void enviar(e)}>
        <h1>Due diligence técnica</h1>
        <p className="ayuda">Acceda con las credenciales de su organización.</p>

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

        <label>
          Contraseña
          <input
            type="password"
            autoComplete="current-password"
            required
            value={clave}
            onChange={(e) => setClave(e.target.value)}
          />
        </label>

        {error && <Mensaje tipo="error">{error}</Mensaje>}

        <button type="submit" disabled={enviando || !email || !clave}>
          {enviando ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}

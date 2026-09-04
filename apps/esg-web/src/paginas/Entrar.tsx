/** La puerta. Con Azure delante, un botón; en desarrollo, un correo. */
import { useState } from 'react'

import { useSesion } from '../sesion'

export function Entrar() {
  const { modo, entrar, error, cargando } = useSesion()
  const [correo, setCorreo] = useState('')

  return (
    <main className="entrar">
      <h1>Panel ESG</h1>
      <p className="apagado">Consumos de agua, electricidad, gas y residuos por activo y cartera.</p>

      {modo === 'entra' ? (
        <button type="button" className="principal" onClick={() => entrar()} disabled={cargando}>
          Entrar con Microsoft
        </button>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            void entrar(correo)
          }}
        >
          <label>
            Correo (modo desarrollo)
            <input
              type="email"
              required
              value={correo}
              onChange={(e) => setCorreo(e.target.value)}
              placeholder="nombre@empresa.example"
            />
          </label>
          <button type="submit" className="principal" disabled={cargando}>
            Entrar
          </button>
          <p className="apagado nota">
            Este modo solo existe en desarrollo: la API no arranca con él fuera de local.
          </p>
        </form>
      )}

      {error && <p className="error">{error}</p>}
    </main>
  )
}

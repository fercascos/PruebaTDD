import type { ReactNode } from 'react'
import { useState } from 'react'
import { ErrorDeApi } from '../api/cliente'
import { Mensaje } from './Marco'

/**
 * Envoltorio de formulario con el manejo de errores en un solo sitio.
 *
 * Lo que resuelve: **el `422` de la API llega con el campo que falla**, y sin
 * esto cada formulario tendría que desmontar esa estructura por su cuenta.
 * Repetirlo en seis pantallas garantiza que en cinco se acabe enseñando
 * «Error 422» y el usuario no sepa qué corregir.
 */
export function Formulario({
  titulo,
  enviar,
  children,
  textoDeEnvio = 'Guardar',
  alCancelar,
}: {
  titulo: string
  enviar: () => Promise<void>
  children: ReactNode
  textoDeEnvio?: string
  alCancelar?: () => void
}) {
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function alEnviar(evento: React.FormEvent) {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      await enviar()
    } catch (e) {
      setError(
        e instanceof ErrorDeApi
          ? e.message
          : e instanceof Error
            ? e.message
            : 'No se ha podido guardar',
      )
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form className="dialogo" onSubmit={(e) => void alEnviar(e)}>
      <h3>{titulo}</h3>
      {children}
      {error && <Mensaje tipo="error">{error}</Mensaje>}
      <div className="acciones">
        <button type="submit" disabled={enviando}>
          {enviando ? 'Guardando…' : textoDeEnvio}
        </button>
        {alCancelar && (
          <button type="button" className="secundario" onClick={alCancelar}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  )
}

/** Campo de texto con su etiqueta y su ayuda opcional. */
export function Campo({
  etiqueta,
  ayuda,
  children,
}: {
  etiqueta: string
  ayuda?: string
  children: ReactNode
}) {
  return (
    <label>
      {etiqueta}
      {children}
      {ayuda && <span className="ayuda">{ayuda}</span>}
    </label>
  )
}

/**
 * Rejilla de campos.
 *
 * La ficha del activo tiene veinte campos: en una sola columna obliga a
 * desplazarse tres pantallas para rellenar algo que cabe en una.
 */
export function Rejilla({ children }: { children: ReactNode }) {
  return <div className="rejilla-campos">{children}</div>
}

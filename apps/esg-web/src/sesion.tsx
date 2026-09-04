/**
 * La sesión: quién ha entrado y con qué token se llama a la API.
 *
 * Dos modos, elegidos por configuración y no por rama de código dentro de cada
 * pantalla:
 *
 *  · `entra` — Microsoft Entra ID con MSAL. El token lo emite Azure y MSAL lo
 *    renueva en silencio; esta aplicación nunca lo guarda en `localStorage` ni
 *    lo copia a ningún sitio.
 *  · `local` — la propia API firma un token de desarrollo para un correo que ya
 *    esté dado de alta. Existe para poder trabajar sin un directorio delante;
 *    la API no admite ese modo fuera de desarrollo.
 *
 * En los dos casos, **el token no dice qué puede hacer nadie**: eso lo dice
 * `/api/v1/yo`, que lo calcula el servidor. La interfaz enseña u oculta botones
 * con esa respuesta, y si alguien la ignora, la API responde 403 igual.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { ErrorDeApi, pedir, ponerProveedorDeToken } from './api/cliente'
import type { Yo } from './api/tipos'

type Modo = 'entra' | 'local'

const MODO: Modo = (import.meta.env.VITE_AUTH_MODE as Modo) ?? 'local'
const CLIENTE_AZURE = import.meta.env.VITE_AZURE_CLIENT_ID ?? ''
const DIRECTORIO_AZURE = import.meta.env.VITE_AZURE_TENANT_ID ?? 'common'
//: El ámbito que se pide para llamar a NUESTRA API. No vale `User.Read`: ese
//: token va dirigido a Microsoft Graph y nuestra API lo rechaza por `aud`, que
//: es exactamente lo que tiene que hacer.
const AMBITO = import.meta.env.VITE_AZURE_SCOPE ?? `api://${CLIENTE_AZURE}/acceso`

const CLAVE_LOCAL = 'esg.token.desarrollo'

interface Sesion {
  modo: Modo
  yo: Yo | null
  cargando: boolean
  error: string | null
  entrar: (correo?: string) => Promise<void>
  salir: () => Promise<void>
}

const Contexto = createContext<Sesion | null>(null)

/** MSAL se carga solo en el modo `entra`: en desarrollo ni se descarga. */
async function msal() {
  const { PublicClientApplication } = await import('@azure/msal-browser')
  const aplicacion = new PublicClientApplication({
    auth: {
      clientId: CLIENTE_AZURE,
      authority: `https://login.microsoftonline.com/${DIRECTORIO_AZURE}`,
      redirectUri: window.location.origin,
    },
    // `sessionStorage` y no `localStorage`: cerrar la pestaña cierra la sesión.
    // En un puesto compartido —los hay— la diferencia no es de estilo.
    cache: { cacheLocation: 'sessionStorage' },
  })
  await aplicacion.initialize()
  await aplicacion.handleRedirectPromise()
  return aplicacion
}

export function ProveedorDeSesion({ children }: { children: ReactNode }) {
  const [yo, setYo] = useState<Yo | null>(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const cargarPerfil = useCallback(async () => {
    try {
      setYo(await pedir<Yo>('/api/v1/yo'))
      setError(null)
    } catch (e) {
      setYo(null)
      // El 403 es el caso que hay que explicar: identidad buena, sin alta.
      if (e instanceof ErrorDeApi && e.estado === 403) setError(e.message)
      else if (e instanceof ErrorDeApi && e.estado !== 401) setError(e.message)
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    let vivo = true
    async function arrancar() {
      if (MODO === 'entra') {
        const aplicacion = await msal()
        ponerProveedorDeToken(async () => {
          const cuenta = aplicacion.getAllAccounts()[0]
          if (!cuenta) return null
          const respuesta = await aplicacion.acquireTokenSilent({
            scopes: [AMBITO],
            account: cuenta,
          })
          return respuesta.accessToken
        })
        if (aplicacion.getAllAccounts().length === 0) {
          if (vivo) setCargando(false)
          return
        }
      } else {
        ponerProveedorDeToken(async () => sessionStorage.getItem(CLAVE_LOCAL))
        if (!sessionStorage.getItem(CLAVE_LOCAL)) {
          if (vivo) setCargando(false)
          return
        }
      }
      if (vivo) await cargarPerfil()
    }
    void arrancar()
    return () => {
      vivo = false
    }
  }, [cargarPerfil])

  const entrar = useCallback(
    async (correo?: string) => {
      setError(null)
      if (MODO === 'entra') {
        const aplicacion = await msal()
        await aplicacion.loginRedirect({ scopes: [AMBITO] })
        return
      }
      setCargando(true)
      try {
        const { access_token } = await pedir<{ access_token: string }>(
          '/api/v1/desarrollo/token',
          { method: 'POST', body: JSON.stringify({ email: correo }) },
        )
        sessionStorage.setItem(CLAVE_LOCAL, access_token)
        await cargarPerfil()
      } catch (e) {
        setCargando(false)
        setError(e instanceof Error ? e.message : 'No se pudo entrar')
      }
    },
    [cargarPerfil],
  )

  const salir = useCallback(async () => {
    if (MODO === 'entra') {
      const aplicacion = await msal()
      await aplicacion.logoutRedirect()
      return
    }
    sessionStorage.removeItem(CLAVE_LOCAL)
    setYo(null)
  }, [])

  const valor = useMemo<Sesion>(
    () => ({ modo: MODO, yo, cargando, error, entrar, salir }),
    [yo, cargando, error, entrar, salir],
  )
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export function useSesion(): Sesion {
  const sesion = useContext(Contexto)
  if (!sesion) throw new Error('useSesion fuera del proveedor')
  return sesion
}

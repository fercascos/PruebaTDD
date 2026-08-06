import { useEffect, useState } from 'react'

/**
 * ¿Hay conexión?
 *
 * `navigator.onLine` miente en un sentido —dice `true` conectado a un wifi de
 * hotel sin salida— pero **nunca en el otro**: si dice `false`, no hay red. Con
 * eso basta para lo único que se hace con el dato, que es *explicar por qué
 * acaba de fallar algo* en vez de dejar un error críptico en pantalla.
 *
 * No se usa para bloquear nada. Si se deshabilitaran los botones con esta
 * señal, el wifi sin salida dejaría la aplicación inservible por un dato que ni
 * siquiera es fiable; y al revés, un usuario con cobertura intermitente sabe
 * mejor que el navegador si merece la pena intentarlo.
 *
 * Vive fuera del componente para poder probarse: montar `Marco` entero para
 * comprobar dos escuchas de eventos sería mucho aparato para muy poco.
 */
export function useHayRed(): boolean {
  const [hayRed, setHayRed] = useState(leerEstado)

  useEffect(() => {
    const conectado = () => setHayRed(true)
    const desconectado = () => setHayRed(false)
    window.addEventListener('online', conectado)
    window.addEventListener('offline', desconectado)
    // Entre el primer render y este efecto puede haberse caído la red: si no se
    // releyera aquí, el aviso no aparecería hasta el siguiente cambio de estado.
    setHayRed(leerEstado())
    return () => {
      window.removeEventListener('online', conectado)
      window.removeEventListener('offline', desconectado)
    }
  }, [])

  return hayRed
}

/** En duda, se asume que hay red: un aviso falso de «sin conexión» asusta. */
export function leerEstado(): boolean {
  return typeof navigator === 'undefined' || navigator.onLine !== false
}

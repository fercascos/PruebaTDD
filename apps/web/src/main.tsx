import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import './estilos.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

/**
 * `[REQ]` §15.8 · El armazón guardado, para que la aplicación abra sin red.
 *
 * Solo en producción: en desarrollo, un service worker sirviendo módulos de la
 * caché convierte cualquier recarga en una partida de adivinar por qué el
 * cambio no aparece.
 *
 * `[LIM]` Guarda el armazón; **no sincroniza en segundo plano**. Las fotos
 * pendientes viven en IndexedDB y se suben cuando alguien abre la aplicación,
 * no solas con el móvil en el bolsillo.
 */
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    // Un fallo al registrarlo no puede tumbar la aplicación: sin worker sigue
    // funcionando con red, que es el caso normal.
    void navigator.serviceWorker.register('/sw.js').catch(() => undefined)
  })
}

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './App'
import { ProveedorDeSesion } from './sesion'
import './estilos.css'

createRoot(document.getElementById('raiz')!).render(
  <StrictMode>
    <ProveedorDeSesion>
      <App />
    </ProveedorDeSesion>
  </StrictMode>,
)

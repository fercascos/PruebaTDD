/**
 * El prototipo navegable: la aplicación de verdad en un solo fichero.
 *
 * `[REQ]` No es una maqueta. Es `src/App.tsx` —las mismas pantallas, el mismo
 * `cliente.ts`, la misma hoja de estilos— con dos cambios y ninguno más:
 *
 * 1. Sus `fetch` los contesta `servidor.ts` con respuestas **grabadas de la API
 *    real** sobre un encargo de demostración con datos ficticios.
 * 2. Las rutas van en el fragmento (`#/proyectos`), porque un fichero suelto no
 *    tiene detrás quien sirva `/proyectos` al recargar.
 *
 * La sesión se da por iniciada: pedir una contraseña en un prototipo solo
 * consigue que quien lo abre no pase de la primera pantalla.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import { App } from '../src/App'
import '../src/estilos.css'
import { type Grabacion, instalar } from './servidor'
import grabacion from './grabacion.json'
import './prototipo.css'

instalar(grabacion as unknown as Grabacion)

// El token de refresco que la aplicación busca al arrancar. Su valor da igual:
// quien contesta `/auth/refresh` es la grabación. Sin esto, el prototipo abre
// en la pantalla de inicio de sesión y no hay contraseña que valga.
localStorage.setItem('tdd.refresh', 'prototipo')

function Aviso() {
  return (
    <aside className="aviso-prototipo">
      <p>
        <strong>Prototipo navegable.</strong> Es la aplicación real con datos{' '}
        <strong>ficticios</strong> y la API grabada: se navega y se filtra, pero{' '}
        <strong>no guarda nada</strong>. Lo que escribe avisa de que no puede.
      </p>
      <button
        type="button"
        onClick={(e) => (e.currentTarget.parentElement as HTMLElement).remove()}
        aria-label="Ocultar el aviso"
      >
        Entendido
      </button>
    </aside>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Aviso />
    <App Enrutador={HashRouter} />
  </StrictMode>,
)

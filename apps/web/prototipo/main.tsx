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
import { fijarIdioma, traducir } from '../src/i18n/traducir'
import '../src/estilos.css'
import { type Grabacion, instalar } from './servidor'
import grabacion from 'grabacion'
import './prototipo.css'

instalar(grabacion as unknown as Grabacion)

// El token de refresco que la aplicación busca al arrancar. Su valor da igual:
// quien contesta `/auth/refresh` es la grabación. Sin esto, el prototipo abre
// en la pantalla de inicio de sesión y no hay contraseña que valga.
localStorage.setItem('tdd.refresh', 'prototipo')

/* `[REQ]` El idioma con el que arranca, que lo fija la compilación y **tiene
   que ser el mismo con el que se grabó**: la grabación incrustada contesta en
   un idioma y solo en uno, así que abrir en el otro enseñaría los rótulos
   traducidos y los datos no. El selector ES/EN sigue estando y sigue
   funcionando para los rótulos; los datos no cambian, y por eso el fichero
   lleva el idioma en el nombre. */
localStorage.setItem('tdd.idioma', __TDD_IDIOMA__)

/* Y además se fija **antes de pintar**, sin esperar al proveedor.
   `ProveedorDeIdioma` vive dentro de `App` y lo fija al montarse, pero el
   aviso de aquí abajo se pinta antes que `App`: sin esto saldría en castellano
   en el prototipo inglés, que es justo lo primero que se lee.

   El aviso usa `traducir()` y no el `hook`, así que no reacciona al selector
   ES/EN. Es coherente con lo que hay: la grabación incrustada contesta en un
   solo idioma, así que cambiar de idioma traduce los rótulos y no los datos. */
fijarIdioma(__TDD_IDIOMA__)

/** El aviso de que esto es un prototipo.
 *
 *  `[REQ]` Su texto se traduce como el de cualquier pantalla, y no se dejó
 *  fuera por descuido: el extractor solo mira `src/`, así que éste es el único
 *  sitio de la aplicación donde una cadena no entra en el catálogo sola. Está
 *  escrito a mano aquí, y la prueba de entradas muertas no lo ve porque no lo
 *  ve el extractor. `[LIM]` Si alguien cambia esta frase y no la clave, el
 *  aviso del prototipo inglés sale en castellano y nada falla.
 */
function Aviso() {
  return (
    <aside className="aviso-prototipo">
      <p>
        <strong>{traducir('Prototipo navegable.')}</strong> {traducir('Es la aplicación real con datos')}{' '}
        <strong>{traducir('ficticios')}</strong>{' '}
        {traducir('y la API grabada: se navega y se filtra, pero')}{' '}
        <strong>{traducir('no guarda nada')}</strong>
        {traducir('. Lo que escribe avisa de que no puede.')}
      </p>
      <button
        type="button"
        onClick={(e) => (e.currentTarget.parentElement as HTMLElement).remove()}
        aria-label={traducir('Ocultar el aviso')}
      >
        {traducir('Entendido')}
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

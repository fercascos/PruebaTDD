import { type ComponentType, type ReactNode, useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { alCambiarSesion, haySesion, restaurarSesion } from './api/cliente'
import { ProveedorDeIdioma, traducir, useIdioma } from './i18n/idioma'
import { Marco } from './ui/Marco'
import { Entrar } from './paginas/Entrar'
import { Recuperar, Restablecer } from './paginas/Recuperar'
import { Proyectos } from './paginas/Proyectos'
import { FichaDeProyecto } from './paginas/FichaDeProyecto'
import { Plantillas } from './paginas/Plantillas'
import { NuevoProyecto } from './paginas/NuevoProyecto'
import { Sugerencias } from './paginas/Sugerencias'
import { Personas } from './paginas/Personas'

/**
 * `Enrutador` es `BrowserRouter` **siempre en la aplicación**: las rutas son
 * de verdad, se comparten por correo y el servidor las sirve.
 *
 * Existe como parámetro por el prototipo navegable (`prototipo/`), que es un
 * solo fichero HTML sin servidor detrás: ahí las rutas van en el fragmento
 * (`#/proyectos`), porque un `/proyectos` sin nadie que lo sirva se rompe al
 * recargar. Es la única diferencia entre la aplicación y el prototipo, y por
 * eso está aquí y no en una copia de este fichero.
 */
export function App({
  Enrutador = BrowserRouter,
}: {
  Enrutador?: ComponentType<{ children: ReactNode }>
} = {}) {
  const [autenticado, setAutenticado] = useState(haySesion())
  const [comprobando, setComprobando] = useState(true)

  useEffect(() => {
    // Al recargar la página el token de acceso se ha perdido —vive en
    // memoria a propósito—, así que se intenta recuperar la sesión con el de
    // refresco antes de decidir si hay que enseñar el login.
    restaurarSesion()
      .then(setAutenticado)
      .finally(() => setComprobando(false))
    return alCambiarSesion(setAutenticado)
  }, [])

  if (comprobando) {
    return <p className="cargando">{traducir('Recuperando la sesión…')}</p>
  }

  return (
    <ProveedorDeIdioma>
      <Contenido Enrutador={Enrutador} autenticado={autenticado} />
    </ProveedorDeIdioma>
  )
}

/**
 * El árbol de rutas, **remontado al cambiar de idioma**.
 *
 * `[REQ]` 0030 · La mitad del texto de una pantalla no está en el código: los
 * nombres de las zonas, los capítulos de CAPEX y los conceptos vienen de la
 * API, que los devuelve en el idioma de la cabecera `Accept-Language`. Traducir
 * los rótulos repinta, pero **no vuelve a pedir los datos**, así que al pulsar
 * «EN» la pantalla quedaba a medias: los botones en inglés y las zonas en
 * castellano.
 *
 * `key={idioma}` lo arregla sin tocar ni una pantalla: React desmonta el
 * subárbol y lo monta de nuevo, así que cada `useEffect` que pide datos se
 * ejecuta otra vez, ahora con la cabecera nueva.
 *
 * `[LIM]` Es una maza, no un bisturí: se pierde el estado local de la pantalla
 * —un formulario a medio rellenar, un acordeón abierto, el desplazamiento—. Se
 * acepta porque cambiar de idioma es una acción deliberada y poco frecuente, y
 * porque la alternativa —que cada pantalla meta el idioma en las dependencias
 * de su `useEffect`— son cincuenta sitios donde olvidarse, y olvidarse no
 * falla: deja media pantalla en el otro idioma.
 */
function Contenido({
  Enrutador,
  autenticado,
}: {
  Enrutador: ComponentType<{ children: ReactNode }>
  autenticado: boolean
}) {
  const { idioma } = useIdioma()
  return (
    <Enrutador key={idioma}>
      <Routes>
        <Route
          path="/entrar"
          element={autenticado ? <Navigate to="/proyectos" replace /> : <Entrar />}
        />
        {/* Las dos son anónimas a propósito: quien ha perdido el acceso no
            tiene sesión, y redirigirle a «entrar» le dejaría en el bucle del
            que intenta salir. */}
        <Route path="/recuperar" element={<Recuperar />} />
        <Route path="/restablecer" element={<Restablecer />} />
        <Route
          path="/*"
          element={
            autenticado ? (
              <Marco>
                <Routes>
                  <Route path="/proyectos" element={<Proyectos />} />
                  <Route path="/proyectos/nuevo" element={<NuevoProyecto />} />
                  <Route path="/proyectos/:id/*" element={<FichaDeProyecto />} />
                  <Route path="/plantillas" element={<Plantillas />} />
                  <Route path="/sugerencias" element={<Sugerencias />} />
                  <Route path="/personas" element={<Personas />} />
                  <Route path="*" element={<Navigate to="/proyectos" replace />} />
                </Routes>
              </Marco>
            ) : (
              <Navigate to="/entrar" replace />
            )
          }
        />
      </Routes>
    </Enrutador>
  )
}

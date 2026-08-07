import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { alCambiarSesion, haySesion, restaurarSesion } from './api/cliente'
import { Marco } from './ui/Marco'
import { Entrar } from './paginas/Entrar'
import { Recuperar, Restablecer } from './paginas/Recuperar'
import { Proyectos } from './paginas/Proyectos'
import { FichaDeProyecto } from './paginas/FichaDeProyecto'
import { Plantillas } from './paginas/Plantillas'
import { NuevoProyecto } from './paginas/NuevoProyecto'
import { Sugerencias } from './paginas/Sugerencias'
import { Personas } from './paginas/Personas'

export function App() {
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
    return <p className="cargando">Recuperando la sesión…</p>
  }

  return (
    <BrowserRouter>
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
    </BrowserRouter>
  )
}

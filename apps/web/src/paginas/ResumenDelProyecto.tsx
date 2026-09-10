import { Suspense, lazy, useEffect, useState } from 'react'
import { enviar } from '../api/cliente'
import type { Proyecto } from '../api/tipos'
import { Mensaje } from '../ui/Marco'
import { PestanaFases } from './PestanaFases'

/** Leaflet pesa ~150 KB y se carga solo cuando esta pantalla se abre. */
const MapaDeActivos = lazy(() =>
  import('./MapaDeActivos').then((m) => ({ default: m.MapaDeActivos })),
)

/**
 * El Resumen del proyecto `[REQ]` §3.1 de `docs/23`.
 *
 * Estaba `[PDV]` desde el rediseño y el cliente lo definió al revisar el
 * prototipo: *«habrá que meter un cuadro de texto que recoja la información
 * básica del proyecto, que sirva como introducción en el informe final y muestre
 * todas las ubicaciones de todos los activos del proyecto en un mismo mapa»*.
 *
 * Tres bloques, en este orden:
 *
 * 1. **La introducción**, que es lo primero que se lee del informe y por tanto
 *    lo primero que se escribe.
 * 2. **El mapa de todos los activos**, que es lo que convierte una lista de
 *    nombres en una cartera: dos naves en el mismo polígono y una oficina a
 *    treinta kilómetros no se cuentan igual.
 * 3. **Las fases**, que era lo único que había aquí antes.
 *
 * ## La introducción la escribe una persona
 *
 * `[REQ]` Sale **tal cual** en el documento que se entrega al cliente, así que
 * no se genera ni se propone. Es la diferencia con los datos de la memoria
 * técnica, que sí se leen de un documento y por eso nacen marcados «sin
 * validar»: aquí no hay nada que validar porque no lo ha escrito una máquina.
 *
 * `[LIM]` **Todavía no llega al PPTX.** El texto se guarda y se lee, y el
 * informe no lo imprime aún: eso es un marcador de la plantilla y su mapeo, y
 * no se afirma que funcione algo que no se ha probado.
 */
export function ResumenDelProyecto({
  projectId,
  proyecto,
  alGuardar,
}: {
  projectId: string
  proyecto: Proyecto
  alGuardar: () => void
}) {
  const [texto, setTexto] = useState(proyecto.summary_text ?? '')
  const [error, setError] = useState<string | null>(null)
  const [hecho, setHecho] = useState(false)
  const [guardando, setGuardando] = useState(false)

  // Si el proyecto se recarga —al guardar, o al volver a esta pestaña—, la
  // pantalla vuelve a lo que hay en la base: dejar el borrador de antes
  // enseñaría texto que el servidor no tiene.
  useEffect(() => setTexto(proyecto.summary_text ?? ''), [proyecto.summary_text])

  const cambiado = texto !== (proyecto.summary_text ?? '')

  async function guardar() {
    setError(null)
    setHecho(false)
    setGuardando(true)
    try {
      await enviar(`/projects/${projectId}`, { summary_text: texto }, 'PATCH')
      setHecho(true)
      alGuardar()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se ha podido guardar')
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="resumen-proyecto">
      {error && <Mensaje tipo="error">{error}</Mensaje>}
      {hecho && !cambiado && <Mensaje tipo="ok">Introducción guardada.</Mensaje>}

      <section className="introduccion">
        <h3>Introducción del proyecto</h3>
        <p className="ayuda">
          La información básica: qué se compra, para quién, con qué alcance se revisa y qué
          queda fuera. <strong>Abre el informe final tal como se escriba aquí</strong>, así que
          la redacta una persona y no se genera sola.
        </p>
        <textarea
          className="texto-introduccion"
          rows={9}
          maxLength={8000}
          aria-label="Introducción del proyecto"
          placeholder="Alcance del trabajo, tipología de los activos, fechas de visita, limitaciones generales…"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
        />
        <div className="filtro">
          <button
            type="button"
            disabled={guardando || !cambiado}
            onClick={() => void guardar()}
          >
            Guardar la introducción
          </button>
          <span className="recuento">
            {texto.trim().length} de 8.000 caracteres
            {cambiado && ' · sin guardar'}
          </span>
        </div>
      </section>

      <section className="mapa-de-la-cartera">
        <h3>Dónde están los activos</h3>
        <p className="ayuda">
          Todos los del proyecto en el mismo mapa: dos naves en el mismo polígono y una oficina
          a treinta kilómetros no se gestionan igual.
        </p>
        <Suspense fallback={<p className="cargando">Cargando el mapa…</p>}>
          <MapaDeActivos projectId={projectId} />
        </Suspense>
      </section>

      <section className="fases-del-proyecto">
        <h3>Fases de la due diligence</h3>
        <PestanaFases projectId={projectId} />
      </section>
    </div>
  )
}

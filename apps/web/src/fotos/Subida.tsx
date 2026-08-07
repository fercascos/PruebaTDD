import { useCallback, useEffect, useRef, useState } from 'react'
import { ErrorDeApi, subirFichero } from '../api/cliente'
import type { Foto } from '../api/tipos'
import { comoCola, guardar, guardarVarias, olvidar, pendientesDe } from './almacen'
import {
  type ElementoDeCola,
  type Origen,
  crearElementos,
  esImagenAdmitida,
  procesar,
  reencolarFallidas,
  resumir,
} from './cola'

/**
 * Subida de fotografías desde los **tres orígenes** que pidió el cliente.
 *
 * En el servidor es el mismo endpoint; aquí la diferencia está en el `input`
 * que lo abre, y esa diferencia es todo lo que hace falta:
 *
 * | Origen | `input` | Qué abre en el móvil |
 * |---|---|---|
 * | Ordenador | `multiple` | El explorador de archivos |
 * | Carrete | `accept="image/*" multiple` | La galería de fotos |
 * | Cámara | `accept="image/*" capture="environment"` | **La cámara trasera, directamente** |
 *
 * `capture` es el atributo que hace que el móvil abra la cámara en vez de la
 * galería. Sin él, «hacer una foto» exigiría salir de la aplicación, disparar
 * y volver a entrar a buscarla, que es exactamente lo que nadie hace en una
 * visita con casco puesto.
 *
 * `[REQ]` §15.8 · **La cola se guarda en IndexedDB.** Antes vivía en memoria:
 * cerrar la pestaña, quedarse sin batería o que el móvil descartara la página
 * al abrir la cámara —cosa que hace— perdía todo lo que faltaba por subir. En
 * una visita sin cobertura eso significa volver a subir al edificio. Ahora al
 * volver a entrar la cola sigue ahí, con sus fotos dentro.
 */
export function Subida({
  projectId,
  assetId,
  zoneId,
  technicalSystemId,
  alTerminar,
}: {
  projectId: string
  assetId?: string
  zoneId?: string
  /** `[REQ]` §3.2 · Clasificar al disparar: en la sala de máquinas se sabe que
   *  la foto es de climatización, y clasificarla después son 400 clics. */
  technicalSystemId?: string
  alTerminar: () => void
}) {
  const [elementos, setElementos] = useState<ElementoDeCola[]>([])
  const [enCurso, setEnCurso] = useState(false)
  const [descartados, setDescartados] = useState<string[]>([])
  const [recuperadas, setRecuperadas] = useState(0)
  const entradas = {
    ORDENADOR: useRef<HTMLInputElement>(null),
    CARRETE: useRef<HTMLInputElement>(null),
    CAMARA: useRef<HTMLInputElement>(null),
  }

  // Al abrir la pestaña se recupera lo que quedó a medias. No se sube solo: la
  // decisión de gastar datos es del usuario, que puede estar con el móvil en
  // itinerancia. Se le dice cuántas hay y él pulsa.
  useEffect(() => {
    let vigente = true
    pendientesDe(projectId)
      .then((guardadas) => {
        if (!vigente || guardadas.length === 0) return
        setElementos(comoCola(guardadas))
        setRecuperadas(guardadas.length)
      })
      .catch(() => undefined)
    return () => {
      vigente = false
    }
  }, [projectId])

  const subirUno = useCallback(
    async (elemento: ElementoDeCola) => {
      try {
        const foto = await subirFichero<Foto>(`/projects/${projectId}/photos`, elemento.archivo, {
          origin: elemento.origen,
          asset_id: assetId,
          zone_id: zoneId,
          technical_system_id: technicalSystemId,
        })
        return { tipo: 'ok' as const, photoId: foto.id }
      } catch (e) {
        if (e instanceof ErrorDeApi && e.esConflicto) {
          // Duplicado exacto: la foto ya está en el proyecto. No es un fallo y
          // no debe contarse como tal, o el resumen asustaría sin motivo.
          return { tipo: 'duplicado' as const, mensaje: e.message }
        }
        return {
          tipo: 'error' as const,
          mensaje: e instanceof Error ? e.message : 'Fallo de red',
          status: e instanceof ErrorDeApi ? e.status : undefined,
        }
      }
    },
    [projectId, assetId, zoneId, technicalSystemId],
  )

  async function anadir(archivos: FileList | null, origen: Origen) {
    if (!archivos || archivos.length === 0) return
    const todos = Array.from(archivos)
    const validos = todos.filter(esImagenAdmitida)
    // Se filtra en el cliente para no mandar 40 ficheros que el servidor va a
    // rechazar uno a uno, y se dice cuáles se han dejado fuera: descartar en
    // silencio haría pensar que se han subido.
    setDescartados(todos.filter((a) => !esImagenAdmitida(a)).map((a) => a.name))

    const nuevos = crearElementos(validos, origen)
    // Se guardan ANTES de intentar subirlas. Si se guardaran después, un corte
    // durante la primera subida perdería justo las fotos que este mecanismo
    // existe para no perder.
    await guardarVarias(projectId, nuevos)
    setElementos((previos) => [...previos, ...nuevos])
    await lanzar(nuevos)
  }

  /**
   * Procesa una tanda y **mantiene la cola persistida al día**.
   *
   * Lo que llega al servidor se olvida —subido o rechazado por duplicado, que
   * también significa que está—; lo fallido se queda guardado, que es
   * exactamente lo que hay que poder reintentar mañana.
   */
  async function lanzar(tanda: ElementoDeCola[]) {
    setEnCurso(true)
    await procesar(tanda, subirUno, {
      alCambiar: (actuales) => {
        setElementos((previos) => [...previos])
        for (const e of actuales) {
          const promesa =
            e.estado === 'HECHO' || e.estado === 'DUPLICADO'
              ? olvidar(e.id)
              : guardar(projectId, e)
          // El almacén no puede tumbar la subida: si IndexedDB falla —cuota
          // llena, modo privado—, las fotos siguen yendo al servidor, que es lo
          // que de verdad importa.
          void promesa.catch(() => undefined)
        }
      },
    })
    setEnCurso(false)
    setRecuperadas(0)
    alTerminar()
  }

  async function reintentar() {
    const reencolados = reencolarFallidas(elementos)
    setElementos(reencolados)
    await lanzar(reencolados.filter((e) => e.estado === 'PENDIENTE'))
  }

  const resumen = resumir(elementos)

  return (
    <section className="subida">
      <h3>Añadir fotografías</h3>

      <div className="origenes">
        <button type="button" onClick={() => entradas.ORDENADOR.current?.click()}>
          Desde el ordenador
        </button>
        <button type="button" onClick={() => entradas.CARRETE.current?.click()}>
          Desde el carrete
        </button>
        <button type="button" className="destacado" onClick={() => entradas.CAMARA.current?.click()}>
          Hacer una foto
        </button>
      </div>

      {/* Los tres `input` están ocultos: el botón visible es el que se pulsa,
          pero cada uno abre una cosa distinta en el móvil. */}
      <input
        ref={entradas.ORDENADOR}
        type="file"
        multiple
        hidden
        onChange={(e) => void anadir(e.target.files, 'ORDENADOR')}
      />
      <input
        ref={entradas.CARRETE}
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(e) => void anadir(e.target.files, 'CARRETE')}
      />
      <input
        ref={entradas.CAMARA}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => void anadir(e.target.files, 'CAMARA')}
      />

      {recuperadas > 0 && !enCurso && (
        <div className="mensaje aviso recuperadas">
          <p>
            Quedaron <strong>{recuperadas}</strong> fotografías sin subir de una sesión anterior.
            Siguen guardadas en este dispositivo.
          </p>
          <button
            type="button"
            onClick={() => void reintentar()}
            title="No se suben solas: la decisión de gastar datos es suya"
          >
            Subirlas ahora
          </button>
        </div>
      )}

      {descartados.length > 0 && (
        <p className="mensaje aviso">
          No son imágenes y se han dejado fuera: {descartados.join(', ')}
        </p>
      )}

      {resumen.total > 0 && (
        <div className="progreso">
          <div className="barra">
            <span style={{ width: `${resumen.porcentaje}%` }} />
          </div>
          <p>
            {resumen.hechas} subidas · {resumen.duplicadas} ya estaban ·{' '}
            {resumen.fallidas} con error · {resumen.pendientes + resumen.subiendo} pendientes
          </p>
          {!enCurso && resumen.fallidas > 0 && (
            <button type="button" className="secundario" onClick={() => void reintentar()}>
              Reintentar las {resumen.fallidas} fallidas
            </button>
          )}
        </div>
      )}

      {elementos.some((e) => e.estado === 'FALLIDO' || e.estado === 'DUPLICADO') && (
        <ul className="incidencias">
          {elementos
            .filter((e) => e.estado === 'FALLIDO' || e.estado === 'DUPLICADO')
            .map((e) => (
              <li key={e.id} className={e.estado.toLowerCase()}>
                <strong>{e.archivo.name}</strong> — {e.error ?? e.mensajeDeDuplicado}
              </li>
            ))}
        </ul>
      )}
    </section>
  )
}

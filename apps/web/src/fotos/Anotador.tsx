import { useEffect, useRef, useState } from 'react'
import { enviar, peticionAutenticada } from '../api/cliente'
import { Mensaje } from '../ui/Marco'
import {
  type Forma,
  type TipoDeForma,
  COLORES,
  HERRAMIENTAS,
  dibujar,
  nueva,
  relativa,
  tieneTamano,
} from './formas'

/**
 * Lienzo de anotaciones `[REQ]` §15.2.
 *
 * Señalar la fisura con una flecha es lo que hace útil una foto técnica. El
 * backend guardaba la capa desde el principio —versionada, reversible, con el
 * original intacto— pero **no había dónde dibujarla**, y el informe tampoco la
 * pintaba: anotar producía un JSON que no llegaba a ninguna parte.
 *
 * Las coordenadas se guardan en **fracción del lado (0..1)**, no en píxeles del
 * lienzo. El lienzo mide lo que quepa en la pantalla del móvil; la foto tiene
 * 4000 px y el PPTX se mide en pulgadas. Con píxeles, la flecha apuntaría a un
 * sitio distinto en cada uno de los tres. El servidor rechaza cualquier
 * coordenada fuera de ese rango, así que un fallo aquí sale como error y no
 * como una anotación torcida en el informe entregado.
 */
export function Anotador({
  photoId,
  alGuardar,
  alCerrar,
}: {
  photoId: string
  alGuardar: () => void
  alCerrar: () => void
}) {
  const lienzo = useRef<HTMLCanvasElement>(null)
  const [fondo, setFondo] = useState<HTMLImageElement | null>(null)
  const [formas, setFormas] = useState<Forma[]>([])
  const [herramienta, setHerramienta] = useState<TipoDeForma>('FLECHA')
  const [color, setColor] = useState(COLORES[0]!.valor)
  const [grosor, setGrosor] = useState(3)
  const [enCurso, setEnCurso] = useState<Forma | null>(null)
  const [texto, setTexto] = useState('Fisura')
  const [error, setError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)

  // La vista de 1600 px, no el original: el lienzo no necesita los 4000 de la
  // cámara y traérselos por una red móvil sería absurdo.
  useEffect(() => {
    let vigente = true
    let url: string | null = null
    peticionAutenticada(`/photos/${photoId}/download?variante=VISTA_1600`)
      .then((blob) => {
        if (!vigente) return
        url = URL.createObjectURL(blob)
        const img = new Image()
        img.onload = () => vigente && setFondo(img)
        img.src = url
      })
      .catch(() => setError('No se ha podido cargar la fotografía'))
    return () => {
      vigente = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [photoId])

  // Repintado completo en cada cambio. Con un puñado de formas sobra, y evita
  // el clásico de las capas incrementales: deshacer obliga a repintar igual.
  useEffect(() => {
    const canvas = lienzo.current
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx || !fondo) return
    canvas.width = fondo.naturalWidth
    canvas.height = fondo.naturalHeight
    ctx.drawImage(fondo, 0, 0)
    for (const forma of [...formas, ...(enCurso ? [enCurso] : [])]) {
      dibujar(ctx, forma, canvas.width, canvas.height)
    }
  }, [fondo, formas, enCurso])

  function puntoDe(evento: React.PointerEvent<HTMLCanvasElement>) {
    const caja = evento.currentTarget.getBoundingClientRect()
    // Se divide por el tamaño MOSTRADO, no por el del lienzo: el canvas se
    // escala con CSS para caber en la pantalla, y usar `canvas.width` daría
    // coordenadas desplazadas en cuanto la ventana no midiera lo mismo.
    return relativa(evento.clientX - caja.left, evento.clientY - caja.top, caja.width, caja.height)
  }

  function empezar(evento: React.PointerEvent<HTMLCanvasElement>) {
    if (!fondo) return
    evento.currentTarget.setPointerCapture(evento.pointerId)
    const { x, y } = puntoDe(evento)
    setEnCurso(nueva(herramienta, x, y, color, grosor, texto))
  }

  function mover(evento: React.PointerEvent<HTMLCanvasElement>) {
    if (!enCurso) return
    const { x, y } = puntoDe(evento)
    setEnCurso({ ...enCurso, x2: x, y2: y })
  }

  function soltar() {
    if (!enCurso) return
    // Un clic sin arrastrar no crea una forma invisible de tamaño cero: el
    // usuario creería haber anotado algo y en el informe no habría nada.
    if (enCurso.tipo === 'TEXTO' || tieneTamano(enCurso)) {
      setFormas((previas) => [...previas, enCurso])
    }
    setEnCurso(null)
  }

  async function guardar() {
    setError(null)
    setGuardando(true)
    try {
      await enviar(`/photos/${photoId}/versions/annotate`, {
        annotations: { shapes: formas },
      })
      alGuardar()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="anotador">
      <div className="barra">
        {HERRAMIENTAS.map((h) => (
          <button
            key={h.tipo}
            type="button"
            className={herramienta === h.tipo ? '' : 'secundario'}
            onClick={() => setHerramienta(h.tipo)}
          >
            {h.nombre}
          </button>
        ))}

        <span className="colores">
          {COLORES.map((c) => (
            <button
              key={c.valor}
              type="button"
              className={`muestra ${color === c.valor ? 'elegida' : ''}`}
              style={{ background: c.valor }}
              title={c.nombre}
              aria-label={c.nombre}
              onClick={() => setColor(c.valor)}
            />
          ))}
        </span>

        <label className="grosor">
          Trazo
          <input
            type="range"
            min={1}
            max={12}
            value={grosor}
            onChange={(e) => setGrosor(Number(e.target.value))}
          />
        </label>

        {herramienta === 'TEXTO' && (
          <input
            className="texto-anotacion"
            value={texto}
            maxLength={200}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Texto de la anotación"
          />
        )}

        <button
          type="button"
          className="secundario"
          disabled={formas.length === 0}
          onClick={() => setFormas((previas) => previas.slice(0, -1))}
        >
          Deshacer
        </button>
        <button
          type="button"
          className="secundario"
          disabled={formas.length === 0}
          onClick={() => setFormas([])}
        >
          Limpiar
        </button>
      </div>

      {error && <Mensaje tipo="error">{error}</Mensaje>}

      <div className="lienzo">
        {!fondo && <p className="cargando">Cargando la fotografía…</p>}
        <canvas
          ref={lienzo}
          onPointerDown={empezar}
          onPointerMove={mover}
          onPointerUp={soltar}
          onPointerCancel={soltar}
          // `touch-action: none` en el CSS: sin eso, arrastrar en el móvil hace
          // scroll de la página en vez de dibujar.
        />
      </div>

      <p className="ayuda">
        `[REQ]` §15.2 · <strong>El original no se toca.</strong> Esto crea una versión nueva con la
        capa encima; el fichero de la cámara sigue igual y las anotaciones se pueden volver a
        editar. Se queman sobre la imagen solo al generar el informe.
      </p>

      <div className="acciones">
        <button type="button" onClick={() => void guardar()} disabled={guardando || !fondo}>
          {guardando ? 'Guardando…' : `Guardar ${formas.length} anotaciones`}
        </button>
        <button type="button" className="secundario" onClick={alCerrar}>
          Cancelar
        </button>
      </div>
    </div>
  )
}

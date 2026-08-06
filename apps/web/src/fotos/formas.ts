/**
 * Las formas de la capa de anotaciones · lógica pura, sin React.
 *
 * Vive aparte del componente para poder probar lo que de verdad puede salir
 * mal: la conversión a coordenadas relativas y el descarte de las formas de
 * tamaño cero. Montar un canvas para comprobar una división sería mucho aparato
 * para muy poco.
 *
 * El formato es el que valida el servidor (`tdd/evidence/anotaciones.py`), y
 * las coordenadas van en **fracción del lado (0..1)**: el lienzo mide lo que
 * quepa en la pantalla, la foto tiene 4000 px y el PPTX se mide en pulgadas.
 * Con píxeles, la flecha apuntaría a un sitio distinto en cada uno.
 */

export type TipoDeForma = 'FLECHA' | 'RECTANGULO' | 'ELIPSE' | 'LINEA' | 'TEXTO'

export type Forma = {
  tipo: TipoDeForma
  x1: number
  y1: number
  x2: number
  y2: number
  color: string
  grosor: number
  texto: string
}

export const HERRAMIENTAS: readonly { tipo: TipoDeForma; nombre: string }[] = [
  { tipo: 'FLECHA', nombre: 'Flecha' },
  { tipo: 'RECTANGULO', nombre: 'Recuadro' },
  { tipo: 'ELIPSE', nombre: 'Elipse' },
  { tipo: 'LINEA', nombre: 'Línea' },
  { tipo: 'TEXTO', nombre: 'Texto' },
]

/** Colores que se distinguen sobre hormigón, ladrillo y cielo. */
export const COLORES: readonly { valor: string; nombre: string }[] = [
  { valor: '#DC2626', nombre: 'Rojo' },
  { valor: '#F59E0B', nombre: 'Ámbar' },
  { valor: '#059669', nombre: 'Verde' },
  { valor: '#1D4ED8', nombre: 'Azul' },
  { valor: '#FFFFFF', nombre: 'Blanco' },
]

/** Grosor mínimo por debajo del cual el trazo deja de verse en pantalla. */
const MINIMO_VISIBLE = 0.005

/**
 * Punto del lienzo → fracción del lado.
 *
 * Se divide por el tamaño **mostrado**, no por el del `canvas`: el elemento se
 * escala con CSS para caber en la pantalla, y usar `canvas.width` daría
 * coordenadas desplazadas en cuanto la ventana no midiera lo mismo que la
 * imagen. Se acota a [0,1] porque el puntero puede salirse del elemento
 * mientras se arrastra, y el servidor rechaza cualquier cosa fuera de rango.
 */
export function relativa(
  x: number,
  y: number,
  ancho: number,
  alto: number,
): { x: number; y: number } {
  const acotar = (v: number) => Math.min(1, Math.max(0, v))
  return {
    x: acotar(ancho > 0 ? x / ancho : 0),
    y: acotar(alto > 0 ? y / alto : 0),
  }
}

export function nueva(
  tipo: TipoDeForma,
  x: number,
  y: number,
  color: string,
  grosor: number,
  texto: string,
): Forma {
  return { tipo, x1: x, y1: y, x2: x, y2: y, color, grosor, texto: tipo === 'TEXTO' ? texto : '' }
}

/**
 * ¿La forma tiene tamaño suficiente para verse?
 *
 * Un clic sin arrastrar produce una forma de tamaño cero: invisible en el
 * informe y presente en la capa. El usuario creería haber anotado algo.
 */
export function tieneTamano(forma: Forma): boolean {
  return (
    Math.abs(forma.x2 - forma.x1) > MINIMO_VISIBLE ||
    Math.abs(forma.y2 - forma.y1) > MINIMO_VISIBLE
  )
}

/** Grosor en píxeles del lienzo, escalado igual que en el servidor. */
export function grosorEnPixeles(grosor: number, ancho: number, alto: number): number {
  return Math.max(1, Math.round(grosor * (Math.max(ancho, alto) / 1000)))
}

/**
 * Pinta una forma sobre el contexto 2D.
 *
 * Espeja lo que hace `rasterizar` en el servidor. **No es duplicación
 * evitable**: uno pinta en el navegador para que el usuario vea lo que está
 * haciendo y el otro quema la capa en el JPEG del informe, y no hay forma de
 * compartir código entre Canvas y Pillow. Lo que sí se comparte es el formato,
 * y por eso las coordenadas son relativas: es lo que garantiza que las dos
 * pinten en el mismo sitio.
 */
export function dibujar(
  ctx: CanvasRenderingContext2D,
  forma: Forma,
  ancho: number,
  alto: number,
): void {
  const x1 = forma.x1 * ancho
  const y1 = forma.y1 * alto
  const x2 = forma.x2 * ancho
  const y2 = forma.y2 * alto
  const grosor = grosorEnPixeles(forma.grosor, ancho, alto)

  ctx.save()
  ctx.strokeStyle = forma.color
  ctx.fillStyle = forma.color
  ctx.lineWidth = grosor
  ctx.lineCap = 'round'

  if (forma.tipo === 'RECTANGULO') {
    ctx.strokeRect(Math.min(x1, x2), Math.min(y1, y2), Math.abs(x2 - x1), Math.abs(y2 - y1))
  } else if (forma.tipo === 'ELIPSE') {
    ctx.beginPath()
    ctx.ellipse(
      (x1 + x2) / 2,
      (y1 + y2) / 2,
      Math.abs(x2 - x1) / 2,
      Math.abs(y2 - y1) / 2,
      0,
      0,
      Math.PI * 2,
    )
    ctx.stroke()
  } else if (forma.tipo === 'TEXTO') {
    const tamano = Math.max(10, Math.round(forma.grosor * 5 * (Math.max(ancho, alto) / 1000)))
    ctx.font = `${tamano}px sans-serif`
    // Contorno oscuro detrás: el rojo sobre una fachada clara y el blanco sobre
    // una sombra desaparecen igual, y una anotación ilegible no está.
    ctx.lineWidth = Math.max(1, grosor / 2)
    ctx.strokeStyle = '#000000'
    ctx.strokeText(forma.texto, x1, y1 + tamano)
    ctx.fillText(forma.texto, x1, y1 + tamano)
  } else {
    ctx.beginPath()
    ctx.moveTo(x1, y1)
    ctx.lineTo(x2, y2)
    ctx.stroke()
    if (forma.tipo === 'FLECHA') {
      const angulo = Math.atan2(y2 - y1, x2 - x1)
      const largo = grosor * 4
      const apertura = (28 * Math.PI) / 180
      ctx.beginPath()
      ctx.moveTo(x2, y2)
      ctx.lineTo(x2 - largo * Math.cos(angulo - apertura), y2 - largo * Math.sin(angulo - apertura))
      ctx.lineTo(x2 - largo * Math.cos(angulo + apertura), y2 - largo * Math.sin(angulo + apertura))
      ctx.closePath()
      ctx.fill()
    }
  }
  ctx.restore()
}

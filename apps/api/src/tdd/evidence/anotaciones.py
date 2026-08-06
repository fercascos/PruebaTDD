"""`[REQ]` §15.2 · La capa de anotaciones: qué es válido y cómo se pinta.

La capa se guardaba desde el principio —versionada, auditada, con el original
intacto— pero **no la veía nadie**: no había lienzo para dibujarla y el
generador de PPTX insertaba la foto sin ella. Anotar producía un JSON que no
llegaba a ninguna parte.

Dos decisiones sostienen este módulo:

**Las coordenadas son relativas (0..1), no píxeles.** Una flecha que señala una
fisura tiene que seguir señalándola en la miniatura de 320 px, en la vista de
1600 y en el PPTX a las pulgadas que toque. Con píxeles del original, la primera
vez que algo se redimensiona la flecha apunta al cielo. Es el fallo clásico de
las anotaciones, y aquí es imposible por construcción.

**El esquema se valida.** Antes bastaba con que el JSON trajera una clave
`shapes`; dentro podía ir cualquier cosa. Un renderizador que recibe basura solo
tiene malas opciones: adivinar, reventar, o dibujar algo que nadie pidió. Se
comprueba a la entrada y se rechaza con un mensaje que dice qué forma falla y
por qué.

Es lógica pura: ni base de datos ni HTTP. Se prueba sin levantar nada.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

#: Versión del formato de la capa. Va guardada con las anotaciones para que,
#: si algún día cambia, se sepa qué se está leyendo en vez de deducirlo.
VERSION_DE_FORMATO = 1

#: Grosores en píxeles **sobre una imagen de 1000 px de ancho**. Se escalan con
#: la imagen: un trazo de 3 px sobre una foto de 4000 px no se ve.
GROSOR_BASE = 1000


class TipoDeForma(StrEnum):
    FLECHA = "FLECHA"
    RECTANGULO = "RECTANGULO"
    ELIPSE = "ELIPSE"
    TEXTO = "TEXTO"
    LINEA = "LINEA"


class AnotacionInvalida(ValueError):
    """La capa no cumple el formato. El mensaje dice qué forma y por qué."""


@dataclass(frozen=True, slots=True)
class Forma:
    """Una anotación. Todas las coordenadas en fracción del lado (0..1)."""

    tipo: TipoDeForma
    #: Extremos. En rectángulo y elipse son dos esquinas opuestas; en flecha y
    #: línea, origen y punta; en texto, la esquina donde empieza.
    x1: float
    y1: float
    x2: float = 0.0
    y2: float = 0.0
    color: str = "#DC2626"
    grosor: float = 3.0
    texto: str = ""


@dataclass(frozen=True, slots=True)
class Capa:
    formas: tuple[Forma, ...] = field(default_factory=tuple)
    version: int = VERSION_DE_FORMATO

    def como_json(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "shapes": [
                {
                    "tipo": f.tipo.value,
                    "x1": f.x1,
                    "y1": f.y1,
                    "x2": f.x2,
                    "y2": f.y2,
                    "color": f.color,
                    "grosor": f.grosor,
                    "texto": f.texto,
                }
                for f in self.formas
            ],
        }


#: Tope de formas por capa. No es una restricción de negocio: es lo que impide
#: que un cliente mal escrito mande cien mil polígonos y el renderizado del
#: informe se quede colgado sin que nadie sepa por qué.
MAX_FORMAS = 200

MAX_TEXTO = 200


def _fraccion(valor: Any, campo: str, indice: int) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise AnotacionInvalida(f"Forma {indice}: «{campo}» no es un número") from exc
    if not 0.0 <= numero <= 1.0:
        # Fuera de [0,1] no es un despiste redondeable: significa que quien
        # escribe está mandando píxeles, y aceptarlo produciría anotaciones que
        # apuntan a cualquier sitio en cuanto cambie el tamaño.
        raise AnotacionInvalida(
            f"Forma {indice}: «{campo}» vale {numero}. Las coordenadas van en "
            "fracción del lado (0 a 1), no en píxeles."
        )
    return numero


def _color(valor: Any, indice: int) -> str:
    texto = str(valor or "#DC2626").strip()
    if not (
        texto.startswith("#")
        and len(texto) == 7  # noqa: PLR2004 — «#» más seis dígitos hexadecimales
        and all(c in "0123456789abcdefABCDEF" for c in texto[1:])
    ):
        raise AnotacionInvalida(f"Forma {indice}: «{texto}» no es un color #RRGGBB")
    return texto.upper()


#: Trazo por defecto y límites. Un grosor absurdo no cambia **dónde** señala la
#: anotación —a diferencia de una coordenada—, así que se acota y se sigue en
#: vez de rechazar la capa entera.
GROSOR_POR_DEFECTO = 3.0
GROSOR_MINIMO = 0.5
GROSOR_MAXIMO = 20.0


def _grosor(valor: Any, indice: int) -> float:
    if valor is None or valor == "":
        return GROSOR_POR_DEFECTO
    try:
        numero = float(valor)
    except (TypeError, ValueError) as exc:
        raise AnotacionInvalida(f"Forma {indice}: «grosor» no es un número") from exc
    return max(GROSOR_MINIMO, min(numero, GROSOR_MAXIMO))


def leer(bruto: Any) -> Capa:
    """Valida la capa recibida y la devuelve tipada.

    Rechaza en vez de arreglar: una coordenada fuera de rango que se recorta en
    silencio deja una flecha señalando un sitio que nadie eligió, y eso en un
    informe entregado es peor que un error al guardar.
    """
    if not isinstance(bruto, dict):
        raise AnotacionInvalida("La capa de anotaciones debe ser un objeto")
    formas_brutas = bruto.get("shapes")
    if not isinstance(formas_brutas, list):
        raise AnotacionInvalida("La capa debe traer la lista «shapes»")
    if len(formas_brutas) > MAX_FORMAS:
        raise AnotacionInvalida(f"Demasiadas formas: el máximo es {MAX_FORMAS}")

    formas: list[Forma] = []
    for indice, cruda in enumerate(formas_brutas, 1):
        if not isinstance(cruda, dict):
            raise AnotacionInvalida(f"Forma {indice}: se esperaba un objeto")
        try:
            tipo = TipoDeForma(str(cruda.get("tipo", "")).upper())
        except ValueError as exc:
            disponibles = ", ".join(t.value for t in TipoDeForma)
            raise AnotacionInvalida(
                f"Forma {indice}: tipo «{cruda.get('tipo')}» desconocido. "
                f"Disponibles: {disponibles}"
            ) from exc

        texto = str(cruda.get("texto", ""))[:MAX_TEXTO]
        if tipo is TipoDeForma.TEXTO and not texto.strip():
            # Un texto vacío no dibuja nada y ocupa sitio en la capa: quien lo
            # mandó cree que ha anotado algo.
            raise AnotacionInvalida(f"Forma {indice}: una anotación de texto no puede ir vacía")

        formas.append(
            Forma(
                tipo=tipo,
                x1=_fraccion(cruda.get("x1", 0), "x1", indice),
                y1=_fraccion(cruda.get("y1", 0), "y1", indice),
                x2=_fraccion(cruda.get("x2", 0), "x2", indice),
                y2=_fraccion(cruda.get("y2", 0), "y2", indice),
                color=_color(cruda.get("color"), indice),
                # Nada de `or 3`: un grosor 0 es un valor, no una ausencia, y
                # con `or` se convertía silenciosamente en el trazo por defecto.
                grosor=_grosor(cruda.get("grosor"), indice),
                texto=texto,
            )
        )

    version = bruto.get("version", VERSION_DE_FORMATO)
    return Capa(formas=tuple(formas), version=int(version) if str(version).isdigit() else 1)


# ─────────────────────────────────────────────────────────────────────────────
#  Rasterizado
# ─────────────────────────────────────────────────────────────────────────────


def _punta_de_flecha(
    x1: float, y1: float, x2: float, y2: float, largo: float
) -> list[tuple[float, float]]:
    """Los tres vértices de la cabeza, orientados según la propia flecha."""
    import math

    angulo = math.atan2(y2 - y1, x2 - x1)
    apertura = math.radians(28)
    return [
        (x2, y2),
        (x2 - largo * math.cos(angulo - apertura), y2 - largo * math.sin(angulo - apertura)),
        (x2 - largo * math.cos(angulo + apertura), y2 - largo * math.sin(angulo + apertura)),
    ]


def rasterizar(imagen: bytes, capa: Capa) -> bytes:
    """Devuelve un JPEG con las anotaciones pintadas encima.

    `[REQ]` §15.2 · **El original no se toca.** Esto produce un derivado
    desechable, que es lo que se inserta en el informe; el fichero de la cámara
    sigue donde estaba, byte a byte, y la capa se puede volver a editar.
    """
    from PIL import Image, ImageDraw, ImageFont

    with Image.open(io.BytesIO(imagen)) as original:
        # `convert` porque un PNG con transparencia no se puede guardar como
        # JPEG, y la foto anotada tiene que ser JPEG para pesar lo razonable.
        lienzo = original.convert("RGB")

    ancho, alto = lienzo.size
    dibujo = ImageDraw.Draw(lienzo)
    # El grosor escala con la imagen: un trazo de 3 px sobre una foto de 4000
    # no se ve, y sobre una miniatura de 320 la tapa entera.
    escala = max(ancho, alto) / GROSOR_BASE

    for forma in capa.formas:
        x1, y1 = forma.x1 * ancho, forma.y1 * alto
        x2, y2 = forma.x2 * ancho, forma.y2 * alto
        grosor = max(1, round(forma.grosor * escala))

        if forma.tipo is TipoDeForma.RECTANGULO:
            # Pillow exige la caja ordenada: dibujar de derecha a izquierda es
            # lo normal con el ratón y sin esto no pintaría nada.
            dibujo.rectangle(
                [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)],
                outline=forma.color,
                width=grosor,
            )
        elif forma.tipo is TipoDeForma.ELIPSE:
            dibujo.ellipse(
                [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)],
                outline=forma.color,
                width=grosor,
            )
        elif forma.tipo is TipoDeForma.LINEA:
            dibujo.line([x1, y1, x2, y2], fill=forma.color, width=grosor)
        elif forma.tipo is TipoDeForma.FLECHA:
            dibujo.line([x1, y1, x2, y2], fill=forma.color, width=grosor)
            dibujo.polygon(_punta_de_flecha(x1, y1, x2, y2, largo=grosor * 4), fill=forma.color)
        elif forma.tipo is TipoDeForma.TEXTO:
            tamano = max(10, round(forma.grosor * 5 * escala))
            try:
                fuente: Any = ImageFont.truetype("DejaVuSans.ttf", tamano)
            except OSError:
                # `[LIM]` Sin tipografía escalable en el sistema, Pillow solo
                # ofrece un bitmap diminuto. Se pinta igual: un texto pequeño es
                # mejor que una anotación que desaparece sin avisar.
                fuente = ImageFont.load_default()
            # Un halo oscuro detrás: el rojo sobre una fachada clara y el blanco
            # sobre una sombra desaparecen igual, y una anotación ilegible es
            # una anotación que no está.
            dibujo.text(
                (x1, y1),
                forma.texto,
                fill=forma.color,
                font=fuente,
                stroke_width=max(1, grosor // 2),
                stroke_fill="#000000",
            )

    salida = io.BytesIO()
    lienzo.save(salida, format="JPEG", quality=88, optimize=True)
    return salida.getvalue()

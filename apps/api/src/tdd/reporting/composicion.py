"""Lo que se coloca **dentro** de la plantilla y no es texto `[REQ]` §3.2.

Dos cosas que el cliente pidió sobre su Full Report con estas palabras:

> *«Todas las fotos que vayamos adjuntando en la parte de inventario deberán
> aparecer en cada recuadro azul, y el pie de cada foto —lo que aparece en la
> plantilla como "Descripción"— es el título de esa foto.»*
>
> *«Sobre el CAPEX, en vez de la tabla que aparece ahí deberá ir la tabla pegada
> de CAPEX de nuestra herramienta.»*

Las dos se declaran en las **notas del orador**, que no se imprimen:

| En las notas | Qué hace |
|---|---|
| `@fotos: HC.H02` | Reparte las fotos de esa sección entre los marcos de la diapositiva |
| `@capex` | Pone la tabla nativa **aquí**, en lugar de lo que hubiera |

## Por qué no hay marcadores para esto

Un marcador es texto que se sustituye por texto. Una fotografía ocupa un marco
con una proporción, y la tabla del CAPEX son diez columnas con subtotales: ni
una ni otra caben en un `{{...}}`. Lo que la plantilla aporta es **la geometría**
—dónde va cada cosa y de qué tamaño—, y eso ya está dibujado en sus
diapositivas: se lee de ahí en vez de pedir que alguien lo escriba.

## Lo que se respeta de la plantilla

**La proporción de la foto.** El marco es 3,15 × 2,36 in —cuatro tercios— y una
fotografía de móvil no lo es: se encaja dentro sin deformarla y se centra. Una
fachada estirada desacredita el informe antes de que nadie lea una línea.

`[LIM]` **Los marcos que sobran se retiran, con su pie.** Una sección con dos
fotos deja dos rectángulos azules vacíos si no se quitan, y un rectángulo azul
vacío en un entregable se lee como un fallo de maquetación.
"""

from __future__ import annotations

import io
import re
from typing import Any

from pptx.presentation import Presentation as Presentacion
from pptx.slide import Slide
from pptx.util import Emu, Inches

from tdd.reporting.marcadores import codigo_y_ancestros
from tdd.reporting.repeticion import mover_detras, notas_de

#: `@fotos: HC.H02` en las notas de la diapositiva de fotografías.
#:
#: Admite **varios códigos separados por coma**, porque la plantilla del cliente
#: tiene páginas de fotos que sirven a dos secciones: la de ascensores y
#: fontanería, que comparten diapositiva de texto, comparten también la de
#: fotos. Con un solo código, las fotos de la segunda sección se perdían.
FOTOS = re.compile(r"@fotos\s*:\s*([A-Za-z0-9.,\s]+)", re.IGNORECASE)

#: `@capex` en las notas de la diapositiva que debe llevar la tabla.
CAPEX = re.compile(r"@capex\b", re.IGNORECASE)

#: Un marco de fotografía de la plantilla del cliente mide 3,15 × 2,36 in. Se
#: admite un margen amplio porque las cuatro plantillas difieren en centésimas.
MARCO_MIN_IN = 1.5

#: Un pie de foto mide 4,11 × 0,27 in: ancho y muy bajo. Es lo que lo distingue
#: del marco, que es alto. No se busca por el texto «Descripción» porque las
#: plantillas inglesas lo escriben en inglés en algunas diapositivas.
PIE_ALTO_MAX_IN = 0.6


def codigos_de_fotos(slide: Slide) -> list[str]:
    """Los códigos que esta diapositiva de fotos reclama. Vacío si no es una."""
    encontrado = FOTOS.search(notas_de(slide))
    if encontrado is None:
        return []
    return [c.strip().upper() for c in encontrado.group(1).split(",") if c.strip()]


def lleva_capex(slide: Slide) -> bool:
    return CAPEX.search(notas_de(slide)) is not None


def secciones_declaradas(prs: Presentacion) -> set[str]:
    """Los códigos que la plantilla reclama con `@fotos`."""
    return {c for s in prs.slides for c in codigos_de_fotos(s)}


def cae_en_una_seccion(foto: Any, declaradas: set[str]) -> bool:
    """¿Va esta fotografía a alguna diapositiva de sección?

    Se mira contra el código de la foto **y sus ancestros**: la de una
    enfriadora `HC.H08.01` cae en la diapositiva de climatización, que pide el
    capítulo `HC.H08`.
    """
    codigo = getattr(foto, "capex_code", "") or ""
    return bool(declaradas & set(codigo_y_ancestros(codigo))) if codigo else False


def _marcos_y_pies(slide: Slide) -> tuple[list[Any], list[Any]]:
    """Los huecos de imagen y sus pies, **en el orden de lectura**.

    De arriba abajo y de izquierda a derecha, que es como se miran cuatro fotos
    en una diapositiva. Sin ordenar, el orden es el del XML —el de creación en
    PowerPoint— y la tercera foto podía salir arriba a la derecha.
    """
    marcos, pies = [], []
    for forma in slide.shapes:
        if forma.width is None or forma.height is None:
            continue
        alto = Emu(forma.height).inches
        ancho = Emu(forma.width).inches
        if alto >= MARCO_MIN_IN and ancho >= MARCO_MIN_IN:
            marcos.append(forma)
        elif alto <= PIE_ALTO_MAX_IN and ancho >= MARCO_MIN_IN and forma.has_text_frame:
            pies.append(forma)

    def por_lectura(f: Any) -> tuple[int, int]:
        # Redondeado a un cuarto de pulgada: dos marcos de la misma fila no
        # están exactamente a la misma altura en la plantilla real —difieren en
        # centésimas— y sin redondear se ordenarían en escalera.
        return (round(Emu(f.top).inches * 4), round(Emu(f.left).inches * 4))

    return sorted(marcos, key=por_lectura), sorted(pies, key=por_lectura)


def _fotos_de(fotos: list[Any], codigos: list[str]) -> list[Any]:
    """Las fotografías de una o varias secciones, en el orden del consultor.

    Una foto entra en la sección de su propio código y en la de sus ancestros:
    la de una enfriadora —`HC.H08.01`— sale en la diapositiva de climatización
    aunque esa esté atada al capítulo `HC.H08`.
    """
    quiere = set(codigos)
    return [
        f for f in fotos if quiere & set(codigo_y_ancestros(getattr(f, "capex_code", "") or ""))
    ]


def _colocar(slide: Slide, marco: Any, datos: bytes) -> bool:
    """Pone la imagen en el hueco del marco y retira el marco.

    Se conserva la proporción: se encaja dentro y se centra. El marco original
    se retira después, porque es un rectángulo de color que se vería detrás.
    """
    from PIL import Image

    try:
        with Image.open(io.BytesIO(datos)) as img:
            ancho_px, alto_px = img.size
    except Exception:  # noqa: BLE001 — una foto ilegible no tumba el informe
        return False
    proporcion = ancho_px / alto_px if alto_px else 1.0

    hueco_ancho = Emu(marco.width).inches
    hueco_alto = Emu(marco.height).inches
    ancho = hueco_ancho
    alto = ancho / proporcion
    if alto > hueco_alto:
        alto = hueco_alto
        ancho = alto * proporcion

    izquierda = Emu(marco.left).inches + (hueco_ancho - ancho) / 2
    arriba = Emu(marco.top).inches + (hueco_alto - alto) / 2
    slide.shapes.add_picture(
        io.BytesIO(datos), Inches(izquierda), Inches(arriba), Inches(ancho), Inches(alto)
    )
    marco._element.getparent().remove(marco._element)
    return True


def _titulo(foto: Any) -> str:
    """El pie: el título que le puso quien la subió.

    `[REQ]` Con las palabras del cliente: *«el pie de cada foto, lo que aparece
    en la plantilla como "Descripción", es el título de esa foto»*.
    """
    return str(getattr(foto, "caption", "") or "")


def _vaciar(forma: Any) -> None:
    forma._element.getparent().remove(forma._element)


def repartir_fotos(prs: Presentacion, fotos: list[Any], *, clonar: Any) -> tuple[int, list[str]]:
    """Coloca las fotos de cada sección en su diapositiva. Devuelve `(puestas, avisos)`.

    Con más fotos que marcos, la diapositiva **se clona**: cuatro por página,
    tantas páginas como hagan falta. Es lo que hacía a mano quien montaba el
    informe, y la plantilla ya trae la maqueta de esa página.
    """
    puestas = 0
    avisos: list[str] = []
    for slide in list(prs.slides):
        codigos = codigos_de_fotos(slide)
        if not codigos:
            continue
        codigo = " + ".join(codigos)
        marcos, pies = _marcos_y_pies(slide)
        if not marcos:
            avisos.append(
                f"La diapositiva de fotos de «{codigo}» no tiene ningún marco reconocible: "
                "se esperan formas de al menos 1,5 × 1,5 in."
            )
            continue

        suyas = _fotos_de(fotos, codigos)
        if not suyas:
            # Sin fotos, los marcos vacíos se retiran con sus pies: cuatro
            # rectángulos de color en un entregable se leen como un fallo.
            for forma in marcos + pies:
                _vaciar(forma)
            continue

        paginas = [suyas[i : i + len(marcos)] for i in range(0, len(suyas), len(marcos))]
        destino: Slide = slide
        for indice, tanda in enumerate(paginas):
            if indice > 0:
                destino = clonar(prs, slide)
            _rellenar(destino, tanda)
            puestas += len(tanda)
        if len(paginas) > 1:
            avisos.append(
                f"«{codigo}» tiene {len(suyas)} fotografías y caben {len(marcos)} por "
                f"diapositiva: se han añadido {len(paginas) - 1} más."
            )
    return puestas, avisos


def _rellenar(slide: Slide, tanda: list[Any]) -> None:
    """Una tanda de fotos en los marcos de UNA diapositiva."""
    marcos, pies = _marcos_y_pies(slide)
    for indice, marco in enumerate(marcos):
        pie = pies[indice] if indice < len(pies) else None
        if indice < len(tanda):
            if _colocar(slide, marco, tanda[indice].datos) and pie is not None:
                _escribir_pie(pie, _titulo(tanda[indice]))
        else:
            _vaciar(marco)
            if pie is not None:
                _vaciar(pie)


def _escribir_pie(forma: Any, texto: str) -> None:
    """El título de la foto, **con el formato del pie de la plantilla**.

    Se escribe en el primer `run` y se borran los demás, que es lo mismo que
    hace la sustitución de marcadores: vaciar el marco y añadir texto suelto le
    quitaría la tipografía y la cursiva que la plantilla le puso.
    """
    parrafos = forma.text_frame.paragraphs
    if not parrafos or not parrafos[0].runs:
        forma.text_frame.text = texto
        return
    parrafos[0].runs[0].text = texto
    for sobrante in parrafos[0].runs[1:]:
        sobrante._r.getparent().remove(sobrante._r)
    for otro in parrafos[1:]:
        otro._p.getparent().remove(otro._p)


def poner_capex(
    prs: Presentacion, trozos: list[Any], *, clonar: Any, insertar: Any
) -> tuple[int, list[str]]:
    """Pone la tabla nativa donde la plantilla la pide. Devuelve `(usadas, avisos)`.

    `[REQ]` Con las palabras del cliente: *«en vez de la tabla que aparece ahí
    deberá ir la tabla pegada de CAPEX de nuestra herramienta»*. Lo que había en
    esa diapositiva es una **imagen** pegada desde Excel: se retira, porque
    dejarla debajo de la tabla nueva daría dos tablas con cifras distintas.

    Si la tabla no cabe en una diapositiva, se clona la de la plantilla: cada
    trozo conserva su portadilla, su pie y su numeración.
    """
    avisos: list[str] = []
    anfitrionas = [s for s in prs.slides if lleva_capex(s)]
    if not anfitrionas:
        return 0, avisos
    if len(anfitrionas) > 1:
        avisos.append(
            f"{len(anfitrionas)} diapositivas piden la tabla de CAPEX con «@capex». "
            "Se usa la primera; las demás se han dejado como estaban."
        )
    modelo = anfitrionas[0]

    # Las copias se sacan **antes** de escribir nada, y todas del modelo
    # intacto. Clonarlo sobre la marcha lo copiaba con el trozo anterior ya
    # dentro: el «(2/2)» salía dibujado encima de las filas del «(1/2)», con las
    # dos tablas superpuestas y los textos pisándose.
    destinos: list[Slide] = [modelo]
    anterior: Slide = modelo
    for _ in trozos[1:]:
        copia = clonar(prs, modelo)
        # Clonar añade al final de la presentación: sin esto, el «(2/2)» salía
        # como última diapositiva del informe, detrás de las conclusiones.
        mover_detras(prs, copia, anterior)
        destinos.append(copia)
        anterior = copia

    usadas = 0
    for destino, trozo in zip(destinos, trozos, strict=True):
        # Lo pegado desde Excel se retira: son imágenes, y la tabla nativa se
        # dibujaría encima sin taparlas del todo.
        for forma in list(destino.shapes):
            if forma.shape_type == 13:  # PICTURE  # noqa: PLR2004
                _vaciar(forma)
        insertar(destino, trozo)
        usadas += 1
    return usadas, avisos

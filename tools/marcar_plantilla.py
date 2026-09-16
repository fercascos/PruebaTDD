"""Escribe los marcadores dentro de una copia de la plantilla real del cliente.

    python3 tools/marcar_plantilla.py original.pptx marcada.pptx
    python3 tools/marcar_plantilla.py original.pptx --solo-ver

`[REQ]` El cliente pidió *«que te suba yo unas plantillas en PPT y tú vayas
rellenando con los textos que aparecen en la aplicación las distintas slides»*.
Sus plantillas **no traen ningún marcador**: son sus diapositivas reales, con
sus textos de relleno («XXXXXXXX»). Esto las convierte en plantillas de la
aplicación **sin que nadie teclee nada en PowerPoint**.

## Lo que hace, exactamente

Sustituye los párrafos de relleno por su marcador, **y nada más**. No mueve
formas, no cambia tipografías, no toca colores ni diseños: escribe texto dentro
de los párrafos que ya existen. El resultado se abre en PowerPoint igual que el
original y se puede corregir a mano si algún marcador quedó en mal sitio.

`[REQ]` **El original no se toca.** Se lee y se escribe un fichero nuevo.

## Cómo sabe qué va en cada sitio

La sección de análisis técnico de su Full Report son **catorce secciones de
sistema ya maquetadas** —«CUBIERTA», «FACHADAS»…—, cada una con su pareja de
diapositivas: una de texto y otra de cuatro fotos. `SECCIONES` ata cada título a
su código del árbol de CAPEX, y de ahí salen el descriptivo y la valoración.

`[SUP]` La correspondencia la he deducido comparando los títulos de la plantilla
con el árbol de §5.3. La mayoría es literal —«CUBIERTA» es el capítulo
«Cubierta»— y esas no admiten discusión. Las que sí, y **siguen sin validar**,
van marcadas `[PDV]` en la tabla: son las dos subsecciones inglesas de
propagación del fuego, que agrupan varios objetos del CTE bajo un solo título.

## Las fotografías y la tabla de CAPEX

Van en las **notas del orador**, que no se imprimen:

* La diapositiva **siguiente** a la de texto de cada sección es la de sus cuatro
  marcos, y recibe `@fotos: <código de la sección>`. `[REQ]` Con las palabras
  del cliente: *«todas las fotos que vayamos adjuntando en la parte de
  inventario deberán aparecer en cada recuadro azul, y el pie de cada foto es el
  título de esa foto»*.
* Las diapositivas de la sección 07 reciben `@capex: <tablas>`. `[REQ]` *«En vez
  de la tabla que aparece ahí deberá ir la tabla pegada de CAPEX de nuestra
  herramienta.»* La sección **no tiene una tabla, tiene cinco**: las dos de
  detalle —obra de arquitectura y de instalaciones—, la matriz de riesgo por
  plazo que va detrás de cada una, el resumen por capítulo y el presupuesto de
  costes duros y blandos. Se clasifican por la forma de sus imágenes, no por su
  posición: las cuatro plantillas no numeran igual.

`[LIM]` La **leyenda de riesgo** de las páginas de la matriz —los cuatro grados
y la escala de plazos— se queda como está: son imágenes aparte y son contenido
fijo del informe, no datos del proyecto.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, cast

import pptx
from pptx.presentation import Presentation
from pptx.shapes.autoshape import Shape
from pptx.shapes.base import BaseShape
from pptx.slide import Slide
from pptx.text.text import TextFrame
from pptx.util import Emu

#: `(título en la plantilla, código del árbol, nota)`.
#:
#: El título se compara en mayúsculas y sin tildes, porque las cuatro plantillas
#: —A y B, castellano e inglés— escriben algunos con acento y otros sin él.
SECCIONES: tuple[tuple[str, str, str], ...] = (
    # ── Arquitectura ────────────────────────────────────────────────────────
    ("CIMENTACION", "HC.H01.01", ""),
    ("FOUNDATION", "HC.H01.01", ""),
    ("ESTRUCTURA", "HC.H01.04", "comparte diapositiva con cimentación"),
    ("STRUCTURE", "HC.H01.04", "comparte diapositiva con cimentación"),
    ("CUBIERTA", "HC.H02", ""),
    ("ROOF", "HC.H02", ""),
    ("FACHADAS", "HC.H03", ""),
    ("FACADES", "HC.H03", ""),
    # `[SUP]` El informe desglosa el capítulo de interiores en TRES secciones y
    # el árbol lo tiene como un capítulo con objetos. Se atan al objeto.
    ("PARTICIONES INTERIORES", "HC.H04.01", "el árbol lo llama «Particiones y revestimientos»"),
    ("INTERIOR PARTITIONS", "HC.H04.01", "el árbol lo llama «Particiones y revestimientos»"),
    ("SUELOS Y TECHOS", "HC.H04.03", ""),
    ("FLOORS AND CEILINGS", "HC.H04.03", ""),
    ("CARPINTERIA Y CERRAJERIA", "HC.H04.02", ""),
    ("CARPENTRY AND LOCKSMITH", "HC.H04.02", ""),
    ("ZONAS EXTERIORES", "HC.H05", ""),
    ("OUTDOOR AREAS", "HC.H05", ""),
    ("PROTECCION PASIVA CONTRA INCENDIOS", "HC.H06", ""),
    ("PASSIVE FIRE PROTECTION", "HC.H06", ""),
    ("ACCESIBILIDAD", "HC.H07", ""),
    ("ACCESIBILITY", "HC.H07", ""),
    # ── Instalaciones ───────────────────────────────────────────────────────
    ("AIRE ACONDICIONADO Y VENTILACION", "HC.H08", ""),
    ("AIR CONDITIONING/VENTILATION", "HC.H08", ""),
    ("ELECTRICIDAD Y ILUMINACION", "HC.H09", ""),
    ("ELECTRICAL INSTALATION", "HC.H09", ""),
    ("TELECOMUNICACIONES", "HC.H14", ""),
    ("TELECOMMUNICATIONS", "HC.H14", ""),
    # `[REQ]` «Protección contra incendios» a secas es la ACTIVA. Lo confirmó el
    # cliente: *«sobre Protección contra Incendios, esto debe ir en el análisis
    # técnico de instalaciones»*, y en su plantilla esta sección está justamente
    # ahí, bajo la cabecera «ANÁLISIS TÉCNICO · INSTALACIONES». La PASIVA es
    # obra —sectorización, resistencia al fuego de la estructura— y tiene su
    # propia sección unas diapositivas antes, dentro de ARQUITECTURA.
    ("PROTECCION CONTRA INCENDIOS", "HC.H10", "PCI activa, en instalaciones"),
    ("FIRE PROTECTION", "HC.H10", "PCI activa, en instalaciones"),
    ("ASCENSORES", "HC.H12", ""),
    ("ELEVATORS", "HC.H12", ""),
    # `[REQ]` Fontanería **sí tiene sección**, y comparte diapositiva con
    # ascensores igual que estructura comparte con cimentación. `docs/18` decía
    # que no la había: se escribió sin abrir la diapositiva del final. Está en
    # las cuatro, y la inglesa la llama «Plumbing and Sewage».
    (
        "FONTANERIA Y SANEAMIENTO",
        "HC.H11",
        "solo en castellano; comparte diapositiva con ascensores",
    ),
    ("PLUMBING AND SEWAGE", "HC.H11", ""),
    # ── Protección pasiva, desarrollada solo en las plantillas INGLESAS ──────
    # `[PDV]` La castellana tiene la sección **vacía**; la inglesa la desglosa
    # en cuatro subsecciones repartidas en tres diapositivas. Dos casan exacto
    # con un objeto del árbol y dos son grupos del CTE: se atan al objeto que
    # mejor los nombra y **están sin validar**.
    ("INTERNAL FIRE SPREAD - HIDDEN SPACES AND INSTALLATIONS", "HC.H06.03", ""),
    ("INTERNAL FIRE SPREAD - STRUCTURE FIRE RESISTANCE", "HC.H06.04", ""),
    ("INTERNAL FIRE SPREAD", "HC.H06.01", "[PDV] agrupa varios objetos del CTE"),
    ("EXTERNAL FIRE SPREAD", "HC.H06.06", "[PDV] agrupa horizontal, vertical y cubierta"),
    ("EVACUATION - OCCUPANCY", "HC.H06.09", ""),
)

#: Un **título de la plantilla** y el marcador que va en el relleno de debajo.
#:
#: `[LIM]` Solo están los que la aplicación sabe rellenar. El análisis de
#: licencias y la documentación consultada tienen su hueco en la plantilla y
#: **no hay dato que poner**: se quedan con el relleno «XXXX» para que quien
#: redacta vea que le toca escribirlos. Inventar un marcador para ellos daría un
#: informe con apartados vacíos y aire de estar terminado.
CAMPOS_POR_TITULO: dict[str, str] = {
    # ── La ficha del edificio (sección 02) ──────────────────────────────────
    "EMPLAZAMIENTO": "{{asset.address}}",
    "LOCATION": "{{asset.address}}",
    "DESCRIPCION": "{{asset.descriptivo}}",
    "DESCRIPTION": "{{asset.descriptivo}}",
    "BUILDING DESCRIPTION": "{{asset.descriptivo}}",
    # ── El resumen ejecutivo (sección 01) ───────────────────────────────────
    #
    # Los dos puntos forman parte del título y no sobran: «ARQUITECTURA» a secas
    # es también la cabecera de la sección 04, y sin ellos el resumen ejecutivo
    # se confundiría con una sección de análisis técnico.
    "ARQUITECTURA:": "{{resumen:ARQUITECTURA}}",
    "ARCHITECTURE:": "{{resumen:ARQUITECTURA}}",
    "INSTALACIONES:": "{{resumen:INSTALACIONES}}",
    "INSTALLATIONS:": "{{resumen:INSTALACIONES}}",
    # ── La documentación consultada (sección 08) ────────────────────────────
    #
    # La plantilla castellana titula este cuadro en inglés. Se admiten los dos.
    "CONSULTED DOCUMENTS": "{{docs.consultados}}",
    "DOCUMENTACION CONSULTADA": "{{docs.consultados}}",
}

#: Cuando el hueco **no tiene título propio** porque lo pone el patrón.
#:
#: `[REQ]` Es el caso del análisis de licencias: su diapositiva es un párrafo de
#: relleno y nada más, y «ANÁLISIS DE LICENCIAS» vive en el patrón, que es quien
#: lo pinta. Buscar el título dentro de la diapositiva no encontraba nada.
#:
#: Solo se aplica a una diapositiva **en la que no haya caído ningún otro
#: marcador**: un patrón lo comparten muchas páginas —el de arquitectura, hasta
#: dieciocho— y esto tiene que alcanzar a la que va suelta, no a todas.
CAMPOS_POR_PATRON: dict[str, str] = {
    "ANALISIS DE LICENCIAS": "{{docs.licencias}}",
    "LICENSING ANALYSIS": "{{docs.licencias}}",
    "PLANNING ANALYSIS": "{{docs.licencias}}",
}

#: Los títulos que NO son una sección de sistema aunque estén en mayúsculas y
#: solos en su diapositiva. Sin esta lista, «DESCRIPCIÓN» recibiría marcadores
#: de sección y el informe sacaría el descriptivo de un capítulo en la ficha del
#: edificio.
NO_SON_SECCION = frozenset(
    {
        "DESCRIPCION",
        "DESCRIPTION",
        "BUILDING DESCRIPTION",
        "EMPLAZAMIENTO",
        "LOCATION",
        "CONSULTED DOCUMENTS",
        "DOCUMENTACION CONSULTADA",
        "MEASUREMENTS AEO CRITERIA",
        "CRITERIO DE MEDICION AEO",
    }
)


#: Lo que la plantilla usa como texto de relleno. Un párrafo que sea solo esto
#: es un hueco a rellenar; uno con texto de verdad —la nota legal, el criterio
#: AEO— **no se toca**, porque es contenido fijo del informe.
def _es_relleno(texto: str) -> bool:
    limpio = texto.strip()
    return bool(limpio) and set(limpio) <= {"X", "x"} and len(limpio) >= 5  # noqa: PLR2004


def _sin_tildes(texto: str) -> str:
    """Mayúsculas, sin tildes y con los guiones largos normalizados.

    Las cuatro plantillas escriben los títulos con criterios distintos —`FAÇADES`
    con cedilla, `Internal Fire Spread – Hidden Spaces` con guión largo—, y
    compararlos tal cual dejaría secciones sin marcar sin decir por qué.
    """
    tabla = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñÇç–—", "AEIOUUNaeiouunCc--")
    return " ".join(texto.translate(tabla).strip().upper().split())


def _codigo_de(titulo: str) -> str | None:
    clave = _sin_tildes(titulo)
    if clave in NO_SON_SECCION:
        return None
    for nombre, codigo, _ in SECCIONES:
        if clave == nombre:
            return codigo
    return None


def marcar(prs: Presentation) -> list[str]:
    """Escribe los marcadores y las directivas. Devuelve qué se ha puesto."""
    puestos: list[str] = []
    codigos_por_diapositiva: dict[int, list[str]] = {}
    for numero, slide in enumerate(prs.slides, start=1):
        lineas = _marcar_diapositiva(slide, numero)
        puestos += lineas
        codigos = _codigos_de(lineas)
        if codigos:
            codigos_por_diapositiva[numero] = codigos

    puestos += _marcar_fotos(prs, codigos_por_diapositiva)
    puestos += _marcar_capex(prs)
    puestos += _marcar_cabeceras(prs)
    puestos += _marcar_portada(prs)
    return puestos


# ─────────────────────────────────────────────────────────────────────────────
#  Los campos globales: la cabecera de todas las páginas y la portada
# ─────────────────────────────────────────────────────────────────────────────

#: El rótulo que la plantilla pone donde va el nombre del proyecto. Está escrito
#: así en los **patrones** —uno por sección del informe— y en inglés en las
#: portadillas, que lo llevan a mano.
ROTULOS_DEL_PROYECTO = frozenset({"NOMBRE DEL PROYECTO", "PROJECT NAME"})


def _marcar_cabeceras(prs: Presentation) -> list[str]:
    """`{{project.name}}` donde la plantilla pone «NOMBRE DEL PROYECTO».

    `[REQ]` Ese rótulo **no está en ninguna diapositiva**: está en los once
    patrones, uno por sección —«ANÁLISIS TÉCNICO ARQUITECTURA», «ESTIMACIÓN
    ECONÓMICA - CAPEX»…—, y es el patrón el que lo pinta en las sesenta y siete
    páginas. Marcarlo ahí rellena el informe entero de una vez; marcarlo
    diapositiva a diapositiva no habría encontrado nada.

    El **título de la sección**, que va en el párrafo de arriba del mismo cuadro,
    no se toca: es contenido del informe, no un dato del proyecto.
    """
    puestos: list[str] = []
    patrones = {id(s.slide_layout): s.slide_layout for s in prs.slides}
    for patron in patrones.values():
        if _poner_en_rotulo(patron, ROTULOS_DEL_PROYECTO, "{{project.name}}"):
            puestos.append(f"patrón «{patron.name}»: {{{{project.name}}}}")
    # Las portadillas de sección lo llevan escrito en la propia diapositiva, en
    # inglés, porque no usan el patrón de su sección.
    for numero, slide in enumerate(prs.slides, start=1):
        if _poner_en_rotulo(slide, ROTULOS_DEL_PROYECTO, "{{project.name}}"):
            puestos.append(f"diap. {numero}: {{{{project.name}}}}")
    return puestos


def _poner_en_rotulo(contenedor: Any, rotulos: frozenset[str], marcador: str) -> bool:
    """Sustituye el párrafo cuyo texto sea uno de los rótulos. ¿Lo encontró?"""
    for forma in contenedor.shapes:
        marco = _marco(forma)
        if marco is None:
            continue
        for parrafo in marco.paragraphs:
            if _sin_tildes(parrafo.text) in rotulos:
                _escribir(parrafo, marcador)
                return True
    return False


#: La portada. `[SUP]` Que el hueco de debajo del título sea el **nombre del
#: proyecto** es lectura mía: la plantilla pone «XXX» y no dice de qué. Es lo que
#: hay en una portada de TDD debajo de «Due Diligence Técnica», y si el cliente
#: quiere ahí la dirección del inmueble se cambia el marcador a mano.
PORTADA_TITULO = frozenset(
    {
        # La plantilla escribe «Dilligence» con dos eles. Se admiten las dos
        # grafías: corregirle la errata al cliente no es cosa de esta
        # herramienta, y buscar solo la correcta no habría encontrado su portada.
        "DUE DILLIGENCE TECNICA",
        "DUE DILIGENCE TECNICA",
        "TECHNICAL DUE DILIGENCE",
    }
)


def _marcar_portada(prs: Presentation) -> list[str]:
    """El nombre del proyecto y la fecha, en la primera diapositiva.

    La fecha de la plantilla —«Febrero 2026»— **no es un relleno**: es una fecha
    de verdad, de otro encargo. Por eso no la detecta `_es_relleno` y hay que
    tratarla aparte; dejarla puesta sacaría el informe con la fecha de otro.
    """
    if not len(prs.slides):
        return []
    portada = prs.slides[0]
    if not any(
        _sin_tildes(p.text) in PORTADA_TITULO
        for f in portada.shapes
        if (m := _marco(f)) is not None
        for p in m.paragraphs
    ):
        return []

    puestos: list[str] = []
    for forma in portada.shapes:
        marco = _marco(forma)
        if marco is None:
            continue
        for parrafo in marco.paragraphs:
            texto = parrafo.text.strip()
            if _es_relleno(texto) or set(texto) <= {"X", "x"} and texto:
                _escribir(parrafo, "{{project.name}}")
                puestos.append("diap. 1: {{project.name}}")
            elif _es_una_fecha(texto):
                _escribir(parrafo, "{{report.month}}")
                puestos.append("diap. 1: {{report.month}}")
    return puestos


def _es_una_fecha(texto: str) -> bool:
    """«Febrero 2026» y sus equivalentes: un mes y un año, y nada más."""
    partes = _sin_tildes(texto).split()
    if len(partes) != 2:  # noqa: PLR2004
        return False
    mes, ano = partes
    return mes in MESES_EN_PORTADA and ano.isdigit() and len(ano) == 4  # noqa: PLR2004


#: Los meses como los escribe una portada, en los dos idiomas de las plantillas.
MESES_EN_PORTADA = frozenset(
    {
        *("ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO"),
        *("JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"),
        *("JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE"),
        *("JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"),
    }
)


def _codigos_de(lineas: list[str]) -> list[str]:
    """Los códigos que han caído en una diapositiva, sin repetir y en orden."""
    vistos: list[str] = []
    for linea in lineas:
        codigo = linea.rsplit(":", 1)[-1].rstrip("}")
        if codigo not in vistos:
            vistos.append(codigo)
    return vistos


def _marcar_fotos(prs: Presentation, codigos: dict[int, list[str]]) -> list[str]:
    """`@fotos` en la diapositiva **siguiente** a la de texto de cada sección.

    Es la pareja que la plantilla ya trae: una de texto y otra de cuatro marcos.
    Se comprueba que la siguiente tenga de verdad marcos de imagen antes de
    escribir nada, porque en las plantillas inglesas la protección pasiva ocupa
    tres diapositivas seguidas de texto y ahí no hay pareja.

    Cuando una diapositiva lleva **dos secciones** —cimentación y estructura,
    ascensores y fontanería— su página de fotos recibe el código del capítulo
    común si lo hay, y si no, el de la primera. `[SUP]` Sin validar: puede que
    el cliente quiera las dos secciones repartidas en la misma página.
    """
    puestos: list[str] = []
    for numero, suyos in codigos.items():
        if numero >= len(prs.slides):
            continue
        siguiente = prs.slides[numero]  # `numero` es 1-based: esta es la de después
        if not _tiene_marcos(siguiente):
            continue
        # Las dos secciones de una diapositiva compartida —ascensores y
        # fontanería— comparten también su página de fotos, y `@fotos` admite
        # los dos códigos. Con uno solo, las fotos de la segunda se perdían.
        codigo = ", ".join(suyos)
        _anotar(siguiente, f"@fotos: {codigo}")
        puestos.append(f"diap. {numero + 1}: @fotos: {codigo}")
    return puestos


def _tiene_marcos(slide: Slide) -> bool:
    """¿Es una diapositiva de fotos? Cuatro formas grandes y sin imagen dentro."""
    from pptx.util import Emu

    grandes = [
        f
        for f in slide.shapes
        if f.width is not None
        and f.height is not None
        and Emu(f.width).inches >= 1.5  # noqa: PLR2004
        and Emu(f.height).inches >= 1.5  # noqa: PLR2004
        and f.shape_type != 13  # no una imagen ya puesta  # noqa: PLR2004
    ]
    return len(grandes) >= 2  # noqa: PLR2004


#: Cómo se titula la portadilla de la sección del CAPEX, en los dos idiomas.
PORTADILLA_CAPEX = frozenset({"CAPEX"})


#: Una tabla de detalle ocupa la página: cruza casi todo el ancho de la
#: diapositiva y sus trozos suman más de media altura. Es lo que la distingue de
#: los resúmenes, que son tablas anchas pero bajas. Medido sobre la plantilla
#: real: las de detalle son de 9,06 × 5,2 in y los resúmenes no pasan de 3,2 in
#: de alto.
DETALLE_ANCHO_MIN_IN = 8.5
DETALLE_ALTO_MIN_IN = 4.5

#: Las diapositivas de la matriz de riesgo llevan, además de la tabla, los dos
#: bloques de la **leyenda** —los cuatro grados y la escala de plazos—, cada uno
#: pegado como su propia imagen. Tres imágenes o más es esa página.
IMAGENES_CON_LEYENDA = 3


def _es_portadilla(slide: Slide) -> bool:
    """¿Es una de las separatas de sección? Llevan el número solo, «07», «08»."""
    for forma in slide.shapes:
        marco = _marco(forma)
        if marco is not None and marco.text.strip().isdigit() and len(marco.text.strip()) == 2:  # noqa: PLR2004
            return True
    return False


def _imagenes(slide: Slide) -> list[Any]:
    """Las imágenes de la diapositiva, de mayor a menor superficie."""
    fotos = [
        f
        for f in slide.shapes
        if f.shape_type == 13 and f.width is not None and f.height is not None  # noqa: PLR2004
    ]
    return sorted(fotos, key=lambda f: -(f.width * f.height))


def _marcar_capex(prs: Presentation) -> list[str]:
    """Las **cinco** tablas de la sección 07, cada una en su diapositiva.

    `[REQ]` La sección no tiene una tabla: tiene dos de detalle —obra de
    arquitectura y de instalaciones—, una matriz de riesgo por plazo detrás de
    cada una, un resumen por capítulo y un presupuesto de costes. Estaban las
    cinco pegadas desde Excel, con los números de otro proyecto.

    Se recorre **desde su portadilla y hasta la siguiente**, y cada diapositiva
    se clasifica por la forma de sus imágenes, no por su posición: las cuatro
    plantillas —A y B, castellano e inglés— no numeran igual.

    `[SUP]` Que la matriz que va **detrás** de cada tabla de detalle sea la de
    *ese* bloque, y no la del proyecto entero, es lectura mía: la plantilla trae
    las dos con las mismas cifras, que es lo que pasa cuando un ejemplo se copia
    y no se actualiza. Si el cliente las quiere globales, se le quita el bloque
    a la directiva en las notas y no hay que tocar nada más.
    """
    inicio = next(
        (
            n
            for n, s in enumerate(prs.slides, start=1)
            if any(
                (m := _marco(f)) is not None and _sin_tildes(m.text) in PORTADILLA_CAPEX
                for f in s.shapes
            )
        ),
        None,
    )
    if inicio is None:
        return []

    detalle: list[int] = []
    matrices: list[int] = []
    resumenes: list[int] = []
    for numero in range(inicio + 1, len(prs.slides) + 1):
        slide = prs.slides[numero - 1]
        if _es_portadilla(slide):
            break
        imagenes = _imagenes(slide)
        if not imagenes:
            continue
        ancho = max(Emu(f.width).inches for f in imagenes)
        alto = sum(Emu(f.height).inches for f in imagenes)
        if ancho >= DETALLE_ANCHO_MIN_IN and alto >= DETALLE_ALTO_MIN_IN:
            detalle.append(numero)
        elif len(imagenes) >= IMAGENES_CON_LEYENDA:
            matrices.append(numero)
        else:
            resumenes.append(numero)

    return _escribir_capex(prs, detalle, matrices, resumenes)


#: El orden en que la plantilla coloca sus dos bloques de obra.
BLOQUES = ("arquitectura", "instalaciones")


def _escribir_capex(
    prs: Presentation, detalle: list[int], matrices: list[int], resumenes: list[int]
) -> list[str]:
    """Escribe las directivas que ha deducido `_marcar_capex`."""
    puestos: list[str] = []

    def poner(numero: int, directiva: str) -> None:
        _anotar(prs.slides[numero - 1], directiva)
        puestos.append(f"diap. {numero}: {directiva}")

    # El reparto en dos bloques solo se aplica si hay **exactamente** dos tablas
    # de detalle, que es como está la plantilla. Con una o con tres, partir el
    # CAPEX por un criterio que no se cumple dejaría actuaciones fuera de todas
    # las tablas: se prefiere una sola tabla completa, que no pierde nada.
    parte_en_bloques = len(detalle) == len(BLOQUES)
    for i, numero in enumerate(detalle):
        poner(numero, f"@capex: detalle:{BLOQUES[i]}" if parte_en_bloques else "@capex: detalle")

    for i, numero in enumerate(matrices):
        ambito = f":{BLOQUES[i]}" if parte_en_bloques and i < len(BLOQUES) else ""
        poner(numero, f"@capex: riesgos{ambito}")

    # Lo que queda son el resumen por capítulo y el presupuesto, en ese orden.
    # El primero trae las dos tablas en una sola imagen, así que pide las dos y
    # se apilan en el mismo hueco.
    for numero, directiva in zip(
        resumenes, ("@capex: capitulos, riesgos", "@capex: costes"), strict=False
    ):
        poner(numero, directiva)

    return puestos


def _ya_se_repite(slide: Slide) -> bool:
    """¿Lleva ya un `@repeat` en las notas? Dos seguidos no tendrían sentido."""
    if not slide.has_notes_slide:
        return False
    marco = slide.notes_slide.notes_text_frame
    return marco is not None and "@repeat" in marco.text.lower()


def _marco(forma: BaseShape) -> TextFrame | None:
    """El cuadro de texto de una forma, o `None` si no lo tiene.

    `has_text_frame` contesta la pregunta pero no estrecha el tipo, así que la
    comprobación y el acceso viven juntos aquí en lugar de repetidos.
    """
    if not forma.has_text_frame:
        return None
    return cast("TextFrame", cast("Shape", forma).text_frame)


def _anotar(slide: Slide, linea: str) -> None:
    """Añade una línea a las notas del orador, sin borrar lo que hubiera."""
    marco = slide.notes_slide.notes_text_frame
    if marco is None:  # pragma: no cover — un patrón de notas sin marcador de texto
        return
    actual = marco.text or ""
    marco.text = f"{actual}\n{linea}".strip() if actual.strip() else linea


def _marcar_diapositiva(slide: Slide, numero: int) -> list[str]:
    """Una diapositiva de sistema: título, relleno, «Valoración», relleno.

    Se recorre el cuadro de texto **en orden**, llevando cuenta de en qué
    sección se está y de si el siguiente relleno es el descriptivo o la
    valoración. Es lo que permite que la primera diapositiva, que lleva
    cimentación y estructura seguidas, reciba los cuatro marcadores correctos.
    """
    puestos: list[str] = []
    for forma in slide.shapes:
        marco = _marco(forma)
        if marco is None:
            continue
        codigo: str | None = None
        campo: str | None = None
        toca_valoracion = False
        for parrafo in marco.paragraphs:
            texto = parrafo.text.strip()
            if not texto:
                continue
            # Un campo de la ficha del edificio: «EMPLAZAMIENTO» y el relleno de
            # debajo es la dirección del activo. Va antes que la búsqueda de
            # sección porque estos títulos están en `NO_SON_SECCION` justamente
            # para que no se los tome por un capítulo del árbol.
            posible_campo = CAMPOS_POR_TITULO.get(_sin_tildes(texto))
            if posible_campo is not None:
                campo, codigo = posible_campo, None
                continue
            posible = _codigo_de(texto)
            if posible is not None:
                codigo, campo, toca_valoracion = posible, None, False
                continue
            if campo is not None and _es_relleno(texto):
                _escribir(parrafo, campo)
                puestos.append(f"diap. {numero}: {campo}")
                # Un campo del edificio es de **un activo**, y una diapositiva
                # que no se repite no sabe de cuál: saldría en blanco sin decir
                # por qué. La ficha se repite, una por edificio, que es lo que
                # hace a mano quien monta un informe de cartera.
                if campo.startswith("{{asset.") and not _ya_se_repite(slide):
                    _anotar(slide, "@repeat: asset")
                    puestos.append(f"diap. {numero}: @repeat: asset")
                campo = None
                continue
            # `[REQ]` «Valuation» es lo que escriben las plantillas inglesas.
            # Estaba puesto «Assessment», que es lo que yo habría escrito y no
            # lo que pone su fichero: sin esto, el párrafo de la valoración
            # inglesa recibía el marcador del DESCRIPTIVO y el informe salía con
            # el mismo texto repetido dos veces.
            if _sin_tildes(texto) in {"VALORACION", "VALUATION", "ASSESSMENT"}:
                toca_valoracion = True
                continue
            if codigo is not None and _es_relleno(texto):
                marcador = f"{{{{{'valoracion' if toca_valoracion else 'descriptivo'}:{codigo}}}}}"
                _escribir(parrafo, marcador)
                puestos.append(f"diap. {numero}: {marcador}")
                toca_valoracion = False

    # Si no ha caído nada y el **patrón** dice de qué sección es, el relleno de
    # esta diapositiva es el de esa sección. Ver `CAMPOS_POR_PATRON`.
    return puestos or _marcar_por_patron(slide, numero)


def _marcar_por_patron(slide: Slide, numero: int) -> list[str]:
    """El hueco de una diapositiva cuyo título lo pone el patrón."""
    marcador = next(
        (
            CAMPOS_POR_PATRON[clave]
            for forma in slide.slide_layout.shapes
            if (marco := _marco(forma)) is not None
            for parrafo in marco.paragraphs
            if (clave := _sin_tildes(parrafo.text)) in CAMPOS_POR_PATRON
        ),
        None,
    )
    if marcador is None:
        return []
    for forma in slide.shapes:
        marco = _marco(forma)
        if marco is None:
            continue
        for parrafo in marco.paragraphs:
            if _es_relleno(parrafo.text.strip()):
                _escribir(parrafo, marcador)
                return [f"diap. {numero}: {marcador}"]
    return []


def _escribir(parrafo: object, texto: str) -> None:
    """Cambia el texto **conservando el formato del primer `run`**.

    Vaciar el párrafo y añadir texto suelto le quitaría la tipografía, el cuerpo
    y el color, que es justo lo que no se puede tocar de la plantilla de un
    cliente. Se escribe en el primer `run` y se borran los demás, que es lo que
    hace la propia sustitución de marcadores al generar.
    """
    runs = list(parrafo.runs)  # type: ignore[attr-defined]
    if not runs:
        return
    runs[0].text = texto
    for sobrante in runs[1:]:
        sobrante._r.getparent().remove(sobrante._r)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path, help="la plantilla del cliente, sin tocar")
    parser.add_argument("salida", type=Path, nargs="?", help="dónde escribir la marcada")
    parser.add_argument(
        "--solo-ver",
        action="store_true",
        help="dice qué marcaría y no escribe nada",
    )
    args = parser.parse_args(argv)

    if not args.solo_ver and args.salida is None:
        print("Falta el fichero de salida (o use --solo-ver).", file=sys.stderr)
        return 2
    if args.salida is not None and args.salida.exists():
        print(f"{args.salida} ya existe. Elija otro nombre o bórrelo.", file=sys.stderr)
        return 2

    prs = pptx.Presentation(str(args.original))
    puestos = marcar(prs)
    for linea in puestos:
        print(" ·", linea)
    print(f"\n{len(puestos)} marcadores en {len(prs.slides)} diapositivas.")

    if args.solo_ver:
        return 0
    assert args.salida is not None
    prs.save(str(args.salida))
    print(f"Escrita {args.salida}. El original no se ha tocado.")
    return 0


if __name__ == "__main__":  # pragma: no cover — punto de entrada
    raise SystemExit(main())

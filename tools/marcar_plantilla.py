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
con el árbol de §5.3, y **no está validada con el cliente**. Tres son decisiones
discutibles y se señalan en la tabla.

`[LIM]` **Las fotografías no se marcan.** Las cuatro autoformas vacías de cada
diapositiva par son marcos de imagen, y la inserción de imágenes por marcador no
está construida. Se quedan como están.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pptx import Presentation
from pptx.slide import Slide

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
    # `[SUP]` «Protección contra incendios» a secas es la ACTIVA: la pasiva
    # tiene su propia sección unas diapositivas antes.
    ("PROTECCION CONTRA INCENDIOS", "HC.H10", "se entiende como PCI activa"),
    ("FIRE PROTECTION", "HC.H10", "se entiende como PCI activa"),
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
    """Escribe los marcadores. Devuelve qué se ha puesto y dónde."""
    puestos: list[str] = []
    for numero, slide in enumerate(prs.slides, start=1):
        puestos += _marcar_diapositiva(slide, numero)
    return puestos


def _marcar_diapositiva(slide: Slide, numero: int) -> list[str]:
    """Una diapositiva de sistema: título, relleno, «Valoración», relleno.

    Se recorre el cuadro de texto **en orden**, llevando cuenta de en qué
    sección se está y de si el siguiente relleno es el descriptivo o la
    valoración. Es lo que permite que la primera diapositiva, que lleva
    cimentación y estructura seguidas, reciba los cuatro marcadores correctos.
    """
    puestos: list[str] = []
    for forma in slide.shapes:
        if not forma.has_text_frame:
            continue
        codigo: str | None = None
        toca_valoracion = False
        for parrafo in forma.text_frame.paragraphs:
            texto = parrafo.text.strip()
            if not texto:
                continue
            posible = _codigo_de(texto)
            if posible is not None:
                codigo, toca_valoracion = posible, False
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
    return puestos


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

    prs = Presentation(str(args.original))
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

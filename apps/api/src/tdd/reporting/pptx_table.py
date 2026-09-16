"""Tabla nativa de CAPEX en PowerPoint `[REQ]` P-31.

Sustituye a la imagen EMF pegada desde Excel. Los colores y anchos salen del
render de la plantilla real del cliente, no de una propuesta.
"""

from __future__ import annotations

from typing import Any

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.slide import Slide
from pptx.util import Emu, Inches, Pt

from tdd.reporting.capex_layout import TITULO_GRUPO, Alineacion, CapexTableLayout
from tdd.reporting.fonts import FAMILIA_DEL_INFORME

#: Muestreados del render de la plantilla del cliente (docs/20 §20.3).
VERDE_TITULO = RGBColor(0xA9, 0xC7, 0x8C)
GRIS_CABECERA = RGBColor(0xB0, 0xB0, 0xB0)
ORO_GRUPO = RGBColor(0x9A, 0x8C, 0x4E)
GRIS_SECCION = RGBColor(0xA6, 0xA6, 0xA6)
#: Las secciones de nivel 1 —el tipo de coste— y la fila de TOTAL, más oscuras
#: que las de capítulo para que se lean como lo que son: el grupo de arriba.
GRIS_TIPO_DE_COSTE = RGBColor(0x59, 0x59, 0x59)
BLANCO = RGBColor(0xFF, 0xFF, 0xFF)
NEGRO = RGBColor(0x00, 0x00, 0x00)

#: Un color por plazo, como en el original.
COLOR_PLAZO = {
    "corto": RGBColor(0xF8, 0xCB, 0xCB),
    "medio": RGBColor(0xFB, 0xE5, 0xA6),
    "largo": RGBColor(0xC8, 0xE6, 0xC9),
    "mejoras": RGBColor(0xBD, 0xD7, 0xEE),
    "otro": RGBColor(0xE0, 0xE0, 0xE0),
}

#: P-38 · toda la tipografía del informe unificada en **una sola familia**, y
#: `[REQ]` P-46 dice cuál: **Century Gothic**, la de las plantillas del cliente.
#:
#: Lo pidió así —*«el informe debería estar en Century Gothic»*— después de ver
#: que el informe generado salía **mezclado**: cuarenta y ocho páginas suyas en
#: Century Gothic y seis de tablas en Montserrat, que es justo lo que P-38
#: quería evitar. La familia del informe es la de la plantilla, no la nuestra.
#:
#: `[LIM]` Century Gothic **no está instalada en el servidor** y no es libre, así
#: que el aviso de desbordamiento no puede medirse: se dice al generar, con
#: nombre y apellidos, en vez de callar. Ver `reporting/fonts.py`.
#:
#: `[SUP]` A cambio, es la que **sí está** en el ordenador de quien abre el
#: informe: viene con Microsoft Office. Montserrat no, y no se incrusta en el
#: PPTX, así que las tablas se veían con una sustituta en la máquina del cliente.
#:
#: Sale de `reporting/fonts.py` y no de una constante escrita aquí: la familia
#: del informe se declara **en un solo sitio**, que es lo que impide que la
#: tabla y el aviso de fuentes ausentes acaben hablando de familias distintas.
FUENTE_CUERPO = FAMILIA_DEL_INFORME
#: La misma familia: el peso de la cabecera lo da la **negrita**, que ya se
#: aplica. Century Gothic no publica un «Medium» como familia propia.
FUENTE_CABECERA = FAMILIA_DEL_INFORME

_ALIGN = {
    Alineacion.IZQUIERDA: PP_ALIGN.LEFT,
    Alineacion.CENTRO: PP_ALIGN.CENTER,
    Alineacion.DERECHA: PP_ALIGN.RIGHT,
}


def _escribir(
    celda: Any, texto: str, *, pt: float, negrita: bool, color: Any, alineacion: Any
) -> None:
    celda.text_frame.word_wrap = True
    p = celda.text_frame.paragraphs[0]
    p.alignment = alineacion
    # El tamaño va **en el párrafo** y no solo en el run. Una celda vacía —y en
    # una tabla de CAPEX hay muchas: cada importe que no aplica— se quedaba con
    # un run sin texto, y el render le daba el cuerpo por omisión de la
    # plantilla, 18 pt: la fila medía 0,30 in en vez de los 0,17 pedidos. Con
    # eso todas las tablas salían un 75 % más altas de lo calculado, cabían
    # menos filas de las previstas y en la diapositiva del resumen la fila de
    # TOTAL acababa debajo de la tabla siguiente.
    p.font.size = Pt(pt)
    p.font.name = FUENTE_CABECERA if negrita else FUENTE_CUERPO
    if texto:
        run = p.add_run()
        run.text = texto
        run.font.size = Pt(pt)
        run.font.bold = negrita
        run.font.color.rgb = color
        run.font.name = FUENTE_CABECERA if negrita else FUENTE_CUERPO
    celda.margin_left = celda.margin_right = Emu(27432)  # 0,03 in
    celda.margin_top = celda.margin_bottom = Emu(9144)


def insertar_tabla(
    slide: Slide,
    layout: CapexTableLayout,
    *,
    left_in: float = 0.47,
    top_in: float = 1.55,
    alto_fila_in: float = 0.17,
    cuerpo_pt: float = 5.0,
    ancho_in: float | None = None,
) -> None:
    """Dibuja la tabla en la diapositiva, con su cabecera de dos niveles.

    `ancho_in` reescala las columnas **en proporción** para que la tabla ocupe
    justo el hueco que la plantilla le reserva. Los resúmenes de la sección 07
    van cada uno en un marco de ancho distinto —5,78 in la matriz de riesgo,
    8,99 in el resumen por capítulo— y con un ancho fijo uno se saldría de la
    diapositiva y el otro dejaría medio folio en blanco.
    """
    n_col = len(layout.columnas)
    # Los resúmenes de presupuesto no llevan columnas de plazo, así que tampoco
    # llevan la banda de «CAPEX ESTIMADO» ni la segunda fila de cabecera. Antes
    # se creaba igualmente y quedaba **entera** como continuación de
    # combinación, una fila sin una sola celda propia: el render la daba por
    # inválida y dibujaba la tabla pegada a la esquina de la diapositiva,
    # encima de la cabecera, con la última fila fuera de la página.
    del_grupo = [i for i, c in enumerate(layout.columnas) if c.grupo == "capex"]
    filas_de_cabecera = 2 if del_grupo else 1
    # + 1 del título de bloque.
    n_fil = len(layout.filas) + filas_de_cabecera + 1

    escala = 1.0 if ancho_in is None else ancho_in / layout.ancho_total_in
    forma = slide.shapes.add_table(
        n_fil,
        n_col,
        Inches(left_in),
        Inches(top_in),
        Inches(layout.ancho_total_in * escala),
        Inches(alto_fila_in * n_fil),
    )
    tabla = forma.table
    for i, c in enumerate(layout.columnas):
        tabla.columns[i].width = Inches(c.ancho_in * escala)
    for f in range(n_fil):
        tabla.rows[f].height = Inches(alto_fila_in)

    # ── Fila 0 · título del bloque, combinado de lado a lado ────────────────
    tabla.cell(0, 0).merge(tabla.cell(0, n_col - 1))
    c0 = tabla.cell(0, 0)
    c0.fill.solid()
    c0.fill.fore_color.rgb = VERDE_TITULO
    _escribir(
        c0, layout.titulo, pt=cuerpo_pt + 2, negrita=True, color=BLANCO, alineacion=PP_ALIGN.CENTER
    )

    # ── Cabecera, de uno o de dos niveles ───────────────────────────────────
    for i, col in enumerate(layout.columnas):
        if col.grupo is None:
            # Sin grupo: la cabecera ocupa las dos filas, si hay dos.
            if filas_de_cabecera == 2:  # noqa: PLR2004
                tabla.cell(1, i).merge(tabla.cell(2, i))
            celda = tabla.cell(1, i)
            celda.fill.solid()
            celda.fill.fore_color.rgb = ORO_GRUPO if col.key == "riesgo" else GRIS_CABECERA
            _escribir(
                celda,
                layout.titulo_columna(col),
                pt=cuerpo_pt,
                negrita=True,
                color=BLANCO if col.key == "riesgo" else NEGRO,
                alineacion=PP_ALIGN.CENTER,
            )
        else:
            celda = tabla.cell(2, i)
            celda.fill.solid()
            celda.fill.fore_color.rgb = COLOR_PLAZO.get(col.key, GRIS_CABECERA)
            _escribir(
                celda,
                layout.titulo_columna(col),
                pt=cuerpo_pt,
                negrita=False,
                color=NEGRO,
                alineacion=PP_ALIGN.CENTER,
            )

    if del_grupo:
        tabla.cell(1, del_grupo[0]).merge(tabla.cell(1, del_grupo[-1]))
        cg = tabla.cell(1, del_grupo[0])
        cg.fill.solid()
        cg.fill.fore_color.rgb = ORO_GRUPO
        _escribir(
            cg,
            TITULO_GRUPO["capex"][0 if layout.locale.startswith("es") else 1],
            pt=cuerpo_pt,
            negrita=True,
            color=BLANCO,
            alineacion=PP_ALIGN.CENTER,
        )

    # ── Cuerpo ──────────────────────────────────────────────────────────────
    #
    # Las secciones vienen en dos niveles: el tipo de coste —«HARD COSTS»— y
    # dentro el capítulo. Se distinguen por tono, como en la hoja del cliente:
    # si los dos fuesen del mismo gris, una tabla con cinco capítulos parecería
    # tener diez secciones sueltas en vez de dos grupos.
    for f, fila in enumerate(layout.filas, start=filas_de_cabecera + 1):
        seccion = fila.tipo in ("seccion", "total")
        fondo = GRIS_SECCION if fila.nivel == 2 else GRIS_TIPO_DE_COSTE
        for i, col in enumerate(layout.columnas):
            celda = tabla.cell(f, i)
            # En los resúmenes la columna del rótulo va sombreada aunque la fila
            # sea de datos: es como los pinta la plantilla, con el grado de
            # riesgo o el capítulo en gris y los importes sobre blanco.
            destacada = seccion or col.key in fila.destacadas
            if destacada:
                celda.fill.solid()
                celda.fill.fore_color.rgb = fondo
            else:
                celda.fill.background()
            _escribir(
                celda,
                fila.celdas.get(col.key, ""),
                pt=cuerpo_pt,
                negrita=destacada,
                color=BLANCO if destacada else NEGRO,
                alineacion=_ALIGN[col.alineacion],
            )

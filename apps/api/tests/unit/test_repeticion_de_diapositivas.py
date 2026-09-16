"""Diapositivas que se repiten `[REQ]` §17.2, regla 5.

Con las palabras del cliente: *«que vayas rellenando con los textos que aparecen
en la aplicación las distintas slides del informe»*. Un proyecto de cartera tiene
seis activos y la plantilla tiene **una** diapositiva de activo.

Lo que se fija aquí es lo que distingue una repetición útil de una que engaña:

* que cada copia lleve **sus** datos y no los del primer elemento;
* que las copias queden **en el sitio del modelo**, no detrás de las
  conclusiones;
* que el modelo **desaparezca** —si no, el informe sale con los marcadores a la
  vista—;
* y que una colección vacía retire la diapositiva en vez de dejar un hueco con
  `{{...}}` escrito.
"""

from __future__ import annotations

import io
from typing import Any

from pptx import Presentation
from pptx.util import Inches

from tdd.reporting import repeticion
from tdd.reporting.clone import sustituir_marcadores


def _plantilla(*paginas: tuple[str, str]) -> bytes:
    """Una plantilla con una diapositiva por `(texto, notas)`."""
    prs = Presentation()
    for texto, notas in paginas:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        caja = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2))
        caja.text_frame.text = texto
        if notas:
            slide.notes_slide.notes_text_frame.text = notas
    salida = io.BytesIO()
    prs.save(salida)
    return salida.getvalue()


def _textos(prs: Any) -> list[str]:
    return [
        " ".join(f.text_frame.text for f in s.shapes if f.has_text_frame).strip()
        for s in prs.slides
    ]


SNAPSHOT: dict[str, Any] = {
    "project": {"name": "Cartera Ficticia", "internal_code": "2026-001", "client_name": "Cliente"},
    "assets": [
        {"id": "a1", "name": "Nave Norte", "city": "Getafe"},
        {"id": "a2", "name": "Nave Sur", "city": "Illescas"},
        {"id": "a3", "name": "Edificio Este", "city": "Madrid"},
    ],
    "findings": [
        {"id": "f1", "asset_id": "a1", "title": "Cubierta con ampollas", "risk_code": "03"},
        {"id": "f2", "asset_id": "a2", "title": "Cuadro sin diferencial", "risk_code": "04"},
    ],
    "capex_items": [],
    "photos": [],
    "limitations": [],
    "visits": [],
    "descriptivos": [],
    "catalogs": {"risk_levels": [], "time_horizons": []},
    "generated_at": "2026-09-14T10:00:00Z",
}


def _expandir(plantilla: bytes, snapshot: dict[str, Any] | None = None) -> tuple[Any, list[str]]:
    from tdd.reporting import marcadores as mk

    datos = SNAPSHOT if snapshot is None else snapshot
    prs = Presentation(io.BytesIO(plantilla))
    globales = mk.globales(datos)
    _, avisos = repeticion.expandir(
        prs, datos, globales, sustituir=lambda s, v: sustituir_marcadores(s, v)
    )
    return prs, avisos


def test_una_diapositiva_por_activo_con_sus_propios_datos() -> None:
    """Lo que hacía antes: rellenar el primero y perder los otros cinco."""
    prs, avisos = _expandir(
        _plantilla(
            ("Portada {{project.name}}", ""), ("{{asset.name}} · {{asset.city}}", "@repeat: asset")
        )
    )
    textos = _textos(prs)
    assert len(textos) == 4  # la portada + tres activos
    assert textos[1:] == [
        "Nave Norte · Getafe",
        "Nave Sur · Illescas",
        "Edificio Este · Madrid",
    ]
    assert avisos == []


def test_las_copias_van_en_el_sitio_del_modelo_y_no_al_final() -> None:
    """Clonar añade siempre al final. Un informe cuyas diapositivas de activo
    aparecen detrás de las conclusiones no es el informe que se diseñó."""
    prs, _ = _expandir(
        _plantilla(
            ("Portada", ""),
            ("{{asset.name}}", "@repeat: asset"),
            ("Conclusiones", ""),
        )
    )
    textos = _textos(prs)
    assert textos[0] == "Portada"
    assert textos[1:4] == ["Nave Norte", "Nave Sur", "Edificio Este"]
    assert textos[-1] == "Conclusiones"


def test_el_modelo_desaparece() -> None:
    """Si se quedara, el informe saldría con «{{asset.name}}» escrito."""
    prs, _ = _expandir(_plantilla(("{{asset.name}}", "@repeat: asset")))
    assert all("{{" not in t for t in _textos(prs)), _textos(prs)


def test_una_diapositiva_por_hallazgo() -> None:
    prs, _ = _expandir(_plantilla(("{{finding.title}}", "@repeat: finding")))
    assert _textos(prs) == ["Cubierta con ampollas", "Cuadro sin diferencial"]


def test_los_globales_siguen_valiendo_dentro_de_una_repetida() -> None:
    """Una diapositiva de activo lleva el nombre del proyecto en el pie."""
    prs, _ = _expandir(_plantilla(("{{project.name}} — {{asset.name}}", "@repeat: asset")))
    assert _textos(prs)[0] == "Cartera Ficticia — Nave Norte"


def test_el_tope_deja_fuera_y_lo_dice() -> None:
    prs, avisos = _expandir(_plantilla(("{{asset.name}}", "@repeat: asset\n@max: 2")))
    assert _textos(prs) == ["Nave Norte", "Nave Sur"]
    assert len(avisos) == 1
    assert "dejado fuera 1" in avisos[0]


def test_una_coleccion_vacia_retira_la_diapositiva() -> None:
    """`[LIM]` Y no deja un hueco con los marcadores a la vista, que es lo que
    delata un informe hecho a máquina."""
    vacio = {**SNAPSHOT, "findings": []}
    prs, avisos = _expandir(
        _plantilla(("Portada", ""), ("{{finding.title}}", "@repeat: finding")), vacio
    )
    assert _textos(prs) == ["Portada"]
    assert len(avisos) == 1
    assert "retirado" in avisos[0]


def test_una_coleccion_que_no_existe_avisa_en_vez_de_callarse() -> None:
    """Ignorarlo dejaría una diapositiva con aspecto de estar bien."""
    prs, avisos = _expandir(_plantilla(("{{asset.name}}", "@repeat: edificios")))
    assert len(avisos) == 1
    assert "edificios" in avisos[0]
    # La diapositiva se queda, sin repetir: el generador la rellenará con los
    # valores globales, que es el comportamiento de antes de `@repeat`.
    assert len(prs.slides) == 1


def test_sin_notas_no_pasa_nada() -> None:
    """La mayoría de las diapositivas de una plantilla no llevan notas, y
    preguntar por ellas no puede reventar ni crearlas."""
    prs, avisos = _expandir(_plantilla(("Portada {{project.name}}", "")))
    assert len(prs.slides) == 1
    assert avisos == []


# ─────────────────────────────────────────────────────────────────────────────
#  Dos trampas del formato, encontradas generando el primer informe de verdad
# ─────────────────────────────────────────────────────────────────────────────


def test_retirar_una_diapositiva_y_anadir_otra_no_se_come_ninguna() -> None:
    """`python-pptx` bautiza cada diapositiva nueva con **el número de las que
    hay**, no con el primer nombre libre.

    Quitar una de tres y añadir otra producía dos partes llamadas `slide3.xml`;
    el ZIP guardaba las dos con el mismo nombre y al abrirlo una se había comido
    a la otra, **sin ningún error por el camino**. El informe salía con una
    diapositiva repetida y otra desaparecida.

    Pasa en cuanto se generan la tabla de CAPEX o las fotos después de una
    repetición, que es siempre.
    """
    prs = Presentation(io.BytesIO(_plantilla(("A", ""), ("B", ""), ("C", ""))))
    repeticion._retirar(prs, prs.slides[1])
    nueva = prs.slides.add_slide(prs.slide_layouts[6])
    nueva.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1)).text_frame.text = "NUEVA"

    salida = io.BytesIO()
    prs.save(salida)
    assert _textos(Presentation(io.BytesIO(salida.getvalue()))) == ["A", "C", "NUEVA"]


def test_las_copias_no_heredan_las_notas_del_modelo() -> None:
    """Y por dos razones, las dos con consecuencias visibles.

    Una parte de notas guarda un enlace **de vuelta** a su diapositiva, así que
    compartirla mantenía viva a la modelo después de retirarla: al guardar se
    escribían dos partes con el mismo nombre y **el modelo se comía a la primera
    copia**. Un informe de dos activos salía con uno, y el hueco del otro
    enseñaba los `{{marcadores}}` sin sustituir.

    Y la nota del modelo lleva el `@repeat`: heredada, la copia pediría
    repetirse otra vez.
    """
    prs, _ = _expandir(_plantilla(("{{asset.name}}", "@repeat: asset")))
    assert [repeticion.notas_de(s) for s in prs.slides] == ["", "", ""]
    assert all(repeticion.plan_de(s) is None for s in prs.slides)

    # Y el fichero guardado trae los tres activos, no el modelo repetido.
    salida = io.BytesIO()
    prs.save(salida)
    assert _textos(Presentation(io.BytesIO(salida.getvalue()))) == [
        "Nave Norte",
        "Nave Sur",
        "Edificio Este",
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  Marcadores de sección: un código del árbol dentro del marcador
# ─────────────────────────────────────────────────────────────────────────────


def test_el_marcador_de_capitulo_agrega_lo_de_sus_objetos() -> None:
    """`[REQ]` §3.2 · Es lo que pide la plantilla real: «CUBIERTA» es el capítulo
    `HC.H02` entero, y «SUELOS Y TECHOS» es el objeto `HC.H04.03`, porque el
    informe desglosa interiores en tres secciones."""
    from tdd.reporting import marcadores as mk

    datos = {
        **SNAPSHOT,
        "descriptivos": [
            {"capex_code": "HC.H04.01", "capex_name": "Particiones", "texto": "Tabiquería seca"},
            {"capex_code": "HC.H04.03", "capex_name": "Suelos y techos", "texto": "Terrazo"},
        ],
    }
    valores = mk.por_codigo(datos)
    # El objeto trae lo suyo, sin repetir el título de su diapositiva.
    assert valores["descriptivo:HC.H04.03"] == "Terrazo"
    # El capítulo agrega los dos, cada uno con el nombre de su objeto delante.
    assert (
        valores["descriptivo:HC.H04"]
        == "· Particiones: Tabiquería seca\n· Suelos y techos: Terrazo"
    )


def test_una_seccion_sin_datos_sale_en_blanco_y_no_con_el_marcador() -> None:
    """Un edificio sin nada de telecomunicaciones deja esa sección vacía, que es
    lo que el consultor rellenaría a mano. Dejar `{{descriptivo:HC.H14}}` escrito
    sería peor que el hueco: sale impreso delante del cliente."""
    from tdd.reporting import generator

    plantilla = _plantilla(("CUBIERTA {{descriptivo:HC.H02}} TELECO {{descriptivo:HC.H14}}", ""))
    # Sin hallazgos: esta prueba mira los marcadores, y el generador produce
    # además el XLSX sobre la plantilla del cliente, que exige hallazgos bien
    # codificados. Dárselos aquí sería montar un caso de otra prueba.
    datos = {
        **SNAPSHOT,
        "findings": [],
        "descriptivos": [{"capex_code": "HC.H02", "capex_name": "Cubierta", "texto": "Deck"}],
    }
    r = generator.generar(plantilla, datos)
    texto = _textos(Presentation(io.BytesIO(r.pptx)))[0]
    assert "Deck" in texto
    assert "{{" not in texto, texto
    assert r.marcadores_sin_resolver == []
    assert r.secciones_sin_datos == ["descriptivo:HC.H14"]


# ─────────────────────────────────────────────────────────────────────────────
#  La tabla de CAPEX en la diapositiva que la plantilla reserva
# ─────────────────────────────────────────────────────────────────────────────


def test_los_trozos_de_la_tabla_de_capex_van_seguidos_y_no_al_final() -> None:
    """`[REQ]` *«en vez de la tabla que aparece ahí deberá ir la tabla pegada de
    CAPEX de nuestra herramienta»*.

    Una tabla que no cabe se parte, y cada trozo necesita su propia diapositiva.
    Clonar añade al final de la presentación: el «(2/2)» salía como última
    diapositiva del informe, detrás de las conclusiones.
    """
    from tdd.reporting import composicion
    from tdd.reporting.clone import clonar_diapositiva

    prs = Presentation(
        io.BytesIO(
            _plantilla(
                ("Portada", ""),
                ("Tabla de CAPEX", "@capex"),
                ("Conclusiones", ""),
            )
        )
    )

    usadas, avisos = composicion.poner_capex(
        prs,
        {"detalle": ["trozo 1", "trozo 2"]},
        clonar=clonar_diapositiva,
        insertar=_insertar_de_prueba,
    )

    assert (usadas, avisos) == (2, [])
    textos = _textos(prs)
    assert "trozo 1" in textos[1]
    assert "trozo 2" in textos[2]
    assert textos[-1] == "Conclusiones"
    # Cada trozo, en su diapositiva y **solo el suyo**: la copia se sacaba del
    # modelo cuando ya llevaba el trozo anterior dentro, y las dos tablas
    # salían superpuestas en el mismo sitio.
    assert "trozo 1" not in textos[2], textos[2]


def _insertar_de_prueba(
    slide: Any, trozo: Any, izq: float = 1.0, arriba: float = 4.0, ancho: float | None = None
) -> float:
    """Sustituye a la tabla nativa: escribe el nombre del trozo y dónde cayó."""
    caja = slide.shapes.add_textbox(Inches(izq), Inches(arriba), Inches(ancho or 8.0), Inches(0.4))
    caja.text_frame.text = f"{trozo} @{izq:.2f},{arriba:.2f}"
    return 1.0


# ─────────────────────────────────────────────────────────────────────────────
#  Las cinco tablas de la sección 07
# ─────────────────────────────────────────────────────────────────────────────


def _con_imagenes(*paginas: tuple[str, list[tuple[float, float, float, float]]]) -> bytes:
    """Una plantilla cuyas diapositivas llevan imágenes donde van las tablas.

    La sección 07 del cliente trae sus tablas **pegadas desde Excel**, y la
    posición y el tamaño de esas imágenes es lo que dice dónde va cada tabla
    nueva. Tienen que ser imágenes de verdad y no autoformas: es por el tipo de
    forma por lo que se distingue el hueco de una tabla del resto del diseño.
    """
    from tests.unit.test_imagenes import imagen

    datos = imagen(color=(120, 120, 120))
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(10), Inches(7.5)
    for notas, marcos in paginas:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        for izq, arriba, ancho, alto in marcos:
            slide.shapes.add_picture(
                io.BytesIO(datos), Inches(izq), Inches(arriba), Inches(ancho), Inches(alto)
            )
        if notas:
            slide.notes_slide.notes_text_frame.text = notas
    salida = io.BytesIO()
    prs.save(salida)
    return salida.getvalue()


def test_capex_sin_lista_sigue_significando_la_tabla_de_detalle() -> None:
    """Una plantilla marcada antes de que la directiva admitiese nombres tiene
    que seguir generando lo mismo, sin que nadie la vuelva a marcar."""
    from tdd.reporting import composicion

    prs = Presentation(io.BytesIO(_plantilla(("Tabla", "@capex"))))
    assert composicion.tablas_de_capex(prs.slides[0]) == ["detalle"]


def test_una_diapositiva_puede_pedir_varias_tablas() -> None:
    from tdd.reporting import composicion

    prs = Presentation(io.BytesIO(_plantilla(("Resumen", "@capex: capitulos, riesgos"))))
    assert composicion.tablas_de_capex(prs.slides[0]) == ["capitulos", "riesgos"]


def test_cada_tabla_va_al_marco_de_su_imagen_y_la_leyenda_se_queda() -> None:
    """`[REQ]` La diapositiva de la matriz de riesgo trae, además de la tabla,
    los dos bloques de la **leyenda** pegados como imágenes aparte.

    Se retiraban las tres, y la página salía sin los cuatro grados de riesgo ni
    la escala de plazos: la tabla quedaba sin el criterio que la explica.
    """
    from tdd.reporting import composicion
    from tdd.reporting.clone import clonar_diapositiva

    # Como en la plantilla real: la matriz es la imagen grande y las otras dos,
    # pequeñas, son la leyenda.
    prs = Presentation(
        io.BytesIO(
            _con_imagenes(("@capex: riesgos", [(0.68, 4.35, 2.97, 0.95), (3.44, 4.35, 5.78, 2.58)]))
        )
    )
    puestas, avisos = composicion.poner_capex(
        prs, {"riesgos": ["matriz"]}, clonar=clonar_diapositiva, insertar=_insertar_de_prueba
    )

    assert (puestas, avisos) == (1, [])
    # La tabla va en el marco de la imagen grande, no en una posición fija.
    assert "matriz @3.44,4.35" in _textos(prs)[0]
    # Y la leyenda sigue ahí: quedan dos formas, el rectángulo pequeño y la
    # caja de texto que ha sustituido al grande.
    assert len(prs.slides[0].shapes) == 2  # noqa: PLR2004


def test_dos_tablas_en_un_solo_marco_se_apilan() -> None:
    """La diapositiva del resumen trae las dos tablas en una sola imagen."""
    from tdd.reporting import composicion
    from tdd.reporting.clone import clonar_diapositiva

    prs = Presentation(
        io.BytesIO(_con_imagenes(("@capex: capitulos, riesgos", [(0.50, 1.42, 8.99, 3.18)])))
    )
    puestas, _ = composicion.poner_capex(
        prs,
        {"capitulos": ["por capítulo"], "riesgos": ["por riesgo"]},
        clonar=clonar_diapositiva,
        insertar=_insertar_de_prueba,
    )

    assert puestas == 2  # noqa: PLR2004
    texto = _textos(prs)[0]
    assert "por capítulo @0.50,1.42" in texto
    # La segunda arranca donde acabó la primera —que declaró 1,0 in de alto—,
    # no encima de ella.
    assert "por riesgo @0.50,2.42" in texto


def test_una_tabla_que_no_existe_avisa_en_vez_de_callarse() -> None:
    from tdd.reporting import composicion
    from tdd.reporting.clone import clonar_diapositiva

    prs = Presentation(io.BytesIO(_con_imagenes(("@capex: inventada", [(1.0, 1.0, 5.0, 3.0)]))))
    puestas, avisos = composicion.poner_capex(
        prs, {"detalle": ["x"]}, clonar=clonar_diapositiva, insertar=_insertar_de_prueba
    )

    assert puestas == 0
    assert len(avisos) == 1
    assert "inventada" in avisos[0]


# ─────────────────────────────────────────────────────────────────────────────
#  Los campos globales: la cabecera vive en el PATRÓN, no en las diapositivas
# ─────────────────────────────────────────────────────────────────────────────


def _con_cabecera_en_el_patron(texto_del_patron: str, *paginas: str) -> bytes:
    """Una plantilla que escribe en su patrón, como hace la del cliente.

    Su cabecera —«ANÁLISIS TÉCNICO ARQUITECTURA» y debajo el nombre del
    proyecto— no está en ninguna de las sesenta y siete diapositivas: está en
    once patrones, y es el patrón el que la pinta en todas.
    """
    prs = Presentation()
    # Un patrón no deja añadir cuadros de texto desde `python-pptx`, así que se
    # escribe en el marcador de título que ya trae: es lo mismo que hace la
    # plantilla del cliente, que escribe la cabecera en un cuadro del patrón.
    patron = prs.slide_layouts[5]
    patron.placeholders[0].text_frame.text = texto_del_patron
    for texto in paginas:
        slide = prs.slides.add_slide(patron)
        slide.shapes.add_textbox(Inches(1), Inches(2), Inches(8), Inches(1)).text_frame.text = texto
    salida = io.BytesIO()
    prs.save(salida)
    return salida.getvalue()


def test_el_marcador_del_patron_se_rellena_en_todas_las_paginas() -> None:
    """Sustituir solo en las diapositivas dejaba el informe entero con el rótulo
    de la plantilla —«NOMBRE DEL PROYECTO»— en lo alto de cada página."""
    from tdd.reporting import generator

    prs = Presentation(io.BytesIO(_con_cabecera_en_el_patron("{{project.name}}", "A", "B", "C")))
    sin_resolver, avisos = generator.sustituir_en_los_patrones(
        prs, {"project.name": "Cartera Ficticia"}
    )

    assert (sin_resolver, avisos) == ([], [])
    # El patrón es uno solo y lo comparten las tres páginas: se escribe una vez
    # y sale en las tres.
    patrones = {id(s.slide_layout) for s in prs.slides}
    assert len(patrones) == 1
    assert prs.slides[0].slide_layout.shapes[0].text_frame.text == "Cartera Ficticia"


def test_un_patron_compartido_no_se_sustituye_dos_veces() -> None:
    """Es el mismo objeto para las tres páginas. A la segunda pasada ya no
    quedaría marcador, y se contaría un «no resuelto» que no existe."""
    from tdd.reporting import generator

    prs = Presentation(io.BytesIO(_con_cabecera_en_el_patron("{{project.name}}", "A", "B", "C")))
    sin_resolver, _ = generator.sustituir_en_los_patrones(prs, {})
    # Una sola vez, aunque lo usen tres diapositivas.
    assert sin_resolver == ["project.name"]


def test_un_marcador_de_activo_en_el_patron_avisa() -> None:
    """Saldría **igual en todas** las páginas, con los datos del primer activo.
    Desde fuera parece que la repetición no funciona."""
    from tdd.reporting import generator

    prs = Presentation(io.BytesIO(_con_cabecera_en_el_patron("{{asset.name}}", "A")))
    _, avisos = generator.sustituir_en_los_patrones(prs, {"asset.name": "Nave Norte"})

    assert len(avisos) == 1
    assert "asset.name" in avisos[0]
    assert "muévalo a la diapositiva" in avisos[0]


def test_con_varios_activos_una_ficha_que_no_se_repite_avisa() -> None:
    """`[SUP]` Fuera de una diapositiva repetida, `{{asset.*}}` es el **primer**
    activo. Con un edificio eso es lo que se quiere; con tres, el informe enseña
    la ficha del primero y calla las otras dos, y desde fuera parece una ficha
    sin más."""
    from tdd.reporting import generator

    # Sin hallazgos: esta prueba mira el aviso de ámbito, y el generador produce
    # además el XLSX sobre la plantilla del cliente, que exige hallazgos bien
    # codificados. Dárselos aquí sería montar un caso de otra prueba.
    datos = {**SNAPSHOT, "findings": [], "capex_items": []}
    r = generator.generar(_plantilla(("Dirección: {{asset.address}}", "")), datos)

    assert any("asset.address" in a and "@repeat: asset" in a for a in r.avisos_de_composicion), (
        r.avisos_de_composicion
    )


def test_con_un_solo_activo_no_se_avisa_de_nada() -> None:
    """«El primero» y «el único» son lo mismo: no hay nada que contar."""
    from tdd.reporting import generator

    datos = {**SNAPSHOT, "assets": [SNAPSHOT["assets"][0]], "findings": [], "capex_items": []}
    r = generator.generar(_plantilla(("Dirección: {{asset.address}}", "")), datos)

    assert r.avisos_de_composicion == []


# ─────────────────────────────────────────────────────────────────────────────
#  El resumen ejecutivo: un bloque de obra entero, y las cifras
# ─────────────────────────────────────────────────────────────────────────────

RESUMEN: dict[str, Any] = {
    **SNAPSHOT,
    "findings": [
        {"id": "f1", "capex_code": "HC.H02.01", "title": "Cubierta", "risk_name": "Alto"},
        {"id": "f2", "capex_code": "HC.H03", "title": "Fachada", "risk_name": "Moderado"},
        {"id": "f3", "capex_code": "HC.H03", "title": "Juntas", "risk_name": "Moderado"},
        {"id": "f4", "capex_code": "HC.H09.02", "title": "CGBT", "risk_name": "Extremo"},
    ],
    "capex_items": [
        {"finding_id": "f1", "time_horizon_code": "MEDIO", "amount": "83407.50"},
        {"finding_id": "f2", "time_horizon_code": "CORTO", "amount": "14300"},
        {"finding_id": "f4", "time_horizon_code": "CORTO", "amount": "6200"},
    ],
    "catalogs": {
        "risk_levels": [
            {"code": "04", "name_es": "Extremo", "score": 4},
            {"code": "03", "name_es": "Alto", "score": 3},
            {"code": "02", "name_es": "Moderado", "score": 2},
        ],
        "time_horizons": [
            {"code": "CORTO", "name_es": "Corto plazo", "sort_order": 1},
            {"code": "MEDIO", "name_es": "Medio plazo", "sort_order": 2},
        ],
    },
}


def test_un_bloque_de_obra_vale_como_ambito() -> None:
    """`[REQ]` El resumen ejecutivo de la plantilla es **una diapositiva para
    arquitectura y otra para instalaciones**, sin desglosar por capítulo. El
    bloque sale del código del capítulo, como el capítulo sale del objeto."""
    from tdd.reporting import marcadores as mk

    assert mk.codigo_y_ancestros("HC.H02.01") == ["HC.H02.01", "HC.H02", "HC", "ARQUITECTURA"]
    assert mk.codigo_y_ancestros("HC.H09.02")[-1] == "INSTALACIONES"
    # Lo que no es obra no tiene bloque: su sitio es el resumen de presupuesto.
    assert mk.codigo_y_ancestros("SC.S01") == ["SC.S01", "SC"]


def test_el_resumen_cuenta_las_deficiencias_y_el_capex_del_bloque() -> None:
    from tdd.reporting import marcadores as mk

    valores = mk.por_codigo(RESUMEN)
    assert valores["resumen:ARQUITECTURA"] == (
        "3 deficiencias detectadas: 1 de riesgo alto y 2 de riesgo moderado.\n"
        "CAPEX estimado: 97.707,50 € (14.300,00 € a corto plazo y 83.407,50 € a medio plazo)."
    )


def test_cada_grado_de_riesgo_lleva_su_de_riesgo_delante() -> None:
    """Abreviarlo deja los nombres haciendo de adjetivo, y entonces tienen que
    concordar: «2 moderado» donde el castellano pide «2 moderadas». Concordar no
    se puede, porque los grados son de catálogo y el cliente los renombra."""
    from tdd.reporting import marcadores as mk

    primera = mk.por_codigo(RESUMEN)["resumen:ARQUITECTURA"].split("\n")[0]
    assert primera.count("de riesgo") == 2  # noqa: PLR2004


def test_un_solo_grado_no_repite_el_numero() -> None:
    """«1 deficiencia detectada: 1 de riesgo extremo» dice dos veces lo mismo."""
    from tdd.reporting import marcadores as mk

    assert mk.por_codigo(RESUMEN)["resumen:INSTALACIONES"] == (
        "1 deficiencia detectada, de riesgo extremo.\nCAPEX estimado: 6.200,00 €."
    )


def test_un_bloque_sin_nada_no_emite_el_marcador() -> None:
    """Y entonces el generador lo vacía, como cualquier sección sin datos: un
    «0 deficiencias detectadas» impreso sería afirmar algo que nadie ha
    comprobado —puede ser que no se revisara—."""
    from tdd.reporting import marcadores as mk

    solo_obra = {**RESUMEN, "findings": RESUMEN["findings"][:1], "capex_items": []}
    valores = mk.por_codigo(solo_obra)
    assert "resumen:ARQUITECTURA" in valores
    assert "resumen:INSTALACIONES" not in valores


def test_la_introduccion_del_proyecto_llega_al_informe() -> None:
    """`[REQ]` §3.1 · El esquema dice de ella «sale tal cual en el informe» y no
    salía: no estaba en el snapshot ni tenía marcador, así que alguien la
    escribía en la ficha del proyecto y se perdía."""
    from tdd.reporting import marcadores as mk

    datos = {**SNAPSHOT, "project": {**SNAPSHOT["project"], "summary_text": "Compra de la nave."}}
    assert mk.globales(datos)["project.summary"] == "Compra de la nave."


# ─────────────────────────────────────────────────────────────────────────────
#  Documentación consultada y análisis de licencias
# ─────────────────────────────────────────────────────────────────────────────

#: Lo que hay de verdad en la base: por el mismo nodo, la casilla del árbol del
#: activo y la línea libre de la checklist del proyecto. Y no dicen lo mismo.
DOCUMENTACION: list[dict[str, Any]] = [
    {
        "asset_id": "a1",
        "asset_name": "Nave Norte",
        "code": "S1.1.1",
        "categoria": "Licencia de Obras",
        "title": "Licencia de Obras",
        "status": "RECIBIDA",
        "unavailable_reason": None,
    },
    # El caso que rompía el informe: se pidió y se anotó «no disponible»;
    # después llegó y se marcó la casilla del árbol, sin volver a tocar la
    # petición. El informe la daba por aportada Y por no disponible.
    {
        "asset_id": None,
        "asset_name": None,
        "code": "S1.1.2",
        "categoria": "Licencia de Primera Ocupación",
        "title": "Licencia de primera ocupación",
        "status": "NO_DISPONIBLE",
        "unavailable_reason": "El cliente no la localiza",
    },
    {
        "asset_id": "a1",
        "asset_name": "Nave Norte",
        "code": "S1.1.2",
        "categoria": "Licencia de Primera Ocupación",
        "title": "Licencia de Primera Ocupación",
        "status": "RECIBIDA",
        "unavailable_reason": None,
    },
    {
        "asset_id": "a1",
        "asset_name": "Nave Norte",
        "code": "S1.1.4",
        "categoria": "Licencia de Funcionamiento",
        "title": "Licencia de Funcionamiento",
        "status": "NO_DISPONIBLE",
        "unavailable_reason": "El ayuntamiento no la emitió en su día",
    },
    {
        "asset_id": "a1",
        "asset_name": "Nave Norte",
        "code": "S2.1",
        "categoria": "Memoria técnica",
        "title": "Memoria técnica",
        "status": "PARCIAL",
        "unavailable_reason": None,
    },
    # No aplica: ni es una ausencia ni un hallazgo. No sale.
    {
        "asset_id": "a1",
        "asset_name": "Nave Norte",
        "code": "S1.3.1",
        "categoria": "Requerimientos",
        "title": "Requerimientos",
        "status": "NO_APLICA",
        "unavailable_reason": None,
    },
]


def _docs(extra: list[dict[str, Any]] | None = None) -> dict[str, str]:
    from tdd.reporting import marcadores as mk

    return mk.globales({**SNAPSHOT, "documentacion": DOCUMENTACION + (extra or [])})


def test_el_informe_no_puede_dar_un_documento_por_aportado_y_por_ausente() -> None:
    """`[REQ]` Manda la casilla del árbol del activo: es el estado del nodo para
    ese edificio y es lo que la aplicación mantiene al día."""
    licencias = _docs()["docs.licencias"]
    assert licencias.count("Licencia de Primera Ocupación") == 1
    assert "El cliente no la localiza" not in licencias


def test_el_analisis_de_licencias_agrupa_por_estado() -> None:
    assert _docs()["docs.licencias"] == (
        "Aportadas:\n· Licencia de Obras\n· Licencia de Primera Ocupación\n"
        "No disponibles:\n· Licencia de Funcionamiento — El ayuntamiento no la emitió en su día"
    )


def test_solo_la_rama_urbanistica_entra_en_el_analisis_de_licencias() -> None:
    """`S2.1` es documentación técnica: su sitio es la documentación consultada,
    no el análisis de licencias."""
    assert "Memoria técnica" not in _docs()["docs.licencias"]


def test_lo_consultado_es_lo_aportado_y_lo_parcial_se_dice() -> None:
    """Una casilla en «solicitada» no se ha consultado —se pidió y no llegó— y
    decir lo contrario en un entregable firmado es lo que no puede pasar."""
    consultados = _docs()["docs.consultados"]
    assert consultados == (
        "· S1.1.1 Licencia de Obras\n"
        "· S1.1.2 Licencia de Primera Ocupación\n"
        "· S2.1 Memoria técnica (parcial)"
    )
    assert _docs()["docs.consultados_count"] == "3"


def test_con_un_solo_edificio_no_se_repite_su_nombre() -> None:
    assert "[Nave Norte]" not in _docs()["docs.consultados"]


def test_con_varios_edificios_cada_linea_dice_de_cual_es() -> None:
    """Sin esto, dos edificios con la misma licencia en estados distintos
    volverían a producir dos líneas que se contradicen."""
    otro = [
        {
            "asset_id": "a2",
            "asset_name": "Nave Sur",
            "code": "S1.1.1",
            "categoria": "Licencia de Obras",
            "title": "Licencia de Obras",
            "status": "RECIBIDA",
            "unavailable_reason": None,
        }
    ]
    consultados = _docs(otro)["docs.consultados"]
    assert "· S1.1.1 Licencia de Obras [Nave Norte]" in consultados
    assert "· S1.1.1 Licencia de Obras [Nave Sur]" in consultados

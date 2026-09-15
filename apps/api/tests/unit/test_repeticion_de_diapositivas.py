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

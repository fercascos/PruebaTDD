"""Lectura determinista de una memoria técnica, y el límite de la clasificación.

`[REQ]` No hay ninguna memoria de cliente en el repositorio, ni la habrá: el
documento contra el que se escribió esto es confidencial. Las pruebas de aquí
usan **tablas y textos construidos en el momento**, con las etiquetas y la
redacción que se observaron en una memoria real.

Lo que se comprueba no es que el extractor «funcione», sino las cuatro cosas de
las que depende que un dato leído de un PDF no acabe siendo un error caro:

* que **«12.410 m²» sean doce mil**, no doce con cuarenta y uno;
* que **la ocupación no se confunda** con la construida ni la útil con la
  alquilable;
* que un valor **anonimizado o sin rellenar** no se vuelque como si fuera dato;
* y que lo que no se reconoce **se declare** en vez de perderse.
"""

from __future__ import annotations

from decimal import Decimal

from tdd.memoria.clasificacion import PorSeccion
from tdd.memoria.extraccion import Extraccion, Seccion, _decimal, _leer_tabla, normalizar

# ─────────────────────────────────────────────────────────────────────────────
#  Números
# ─────────────────────────────────────────────────────────────────────────────


def test_el_punto_es_separador_de_millares() -> None:
    """`[REQ]` Es el fallo que más caro sale y menos se ve.

    `Decimal("12.410")` son doce coma cuatro. En castellano, «12.410 m²» son
    doce mil cuatrocientos diez, y esa cifra puesta en una ficha de activo no
    la mira nadie dos veces.
    """
    assert _decimal("12.410 m²") == Decimal("12410")
    assert _decimal("6.023 m²") == Decimal("6023")
    assert _decimal("8.134") == Decimal("8134")


def test_la_coma_sigue_siendo_decimal() -> None:
    assert _decimal("11,50 m") == Decimal("11.50")
    assert _decimal("1.234,56") == Decimal("1234.56")


def test_una_celda_sin_numero_no_inventa_uno() -> None:
    assert _decimal("indicar") is None
    assert _decimal("") is None


def test_normalizar_quita_tildes_y_colapsa_espacios() -> None:
    """Es lo que permite una entrada de vocabulario por concepto y no una por
    cada forma de teclearlo."""
    assert normalizar("  Superficie  ÚTIL   total ") == "superficie util total"
    assert normalizar("Ocupación") == "ocupacion"


# ─────────────────────────────────────────────────────────────────────────────
#  La tabla de superficies
# ─────────────────────────────────────────────────────────────────────────────

#: Con las etiquetas y el orden observados en una memoria real.
SUPERFICIES = [
    ["Concepto", "Superficie aproximada"],
    ["Útil planta baja", "6.023 m²"],
    ["Útil planta primera", "1.234 m²"],
    ["Útil total", "7.257 m²"],
    ["Construida total", "8.134 m²"],
    ["Parcela", "12.410 m²"],
    ["Ocupación", "6.766 m²"],
    ["Urbanización exterior", "5.644 m²"],
]


def test_cada_superficie_va_a_su_campo_y_no_al_de_al_lado() -> None:
    """`[REQ]` La razón de que sean columnas propias y no reutilizadas."""
    e = Extraccion()
    _leer_tabla(SUPERFICIES, e)

    assert e.propuesta["usable_area_sqm"] == "7257"
    assert e.propuesta["total_built_sqm"] == "8134"
    assert e.propuesta["plot_area_sqm"] == "12410"
    # «Ocupación» es la palabra de la memoria. Se descubrió leyendo una.
    assert e.propuesta["occupied_area_sqm"] == "6766"
    assert e.propuesta["urbanised_area_sqm"] == "5644"


def test_la_util_por_planta_sale_dividida_y_no_se_suma_al_total() -> None:
    """`[REC]` El total lo da la memoria aparte y puede no cuadrar con la suma:
    una memoria puede itemizar solo las oficinas y dar un total que incluye el
    altillo. Derivar el total de la suma haría que la aplicación contradijera al
    documento sin decírselo a nadie."""
    e = Extraccion()
    _leer_tabla(SUPERFICIES, e)

    assert [(p.label, p.level, p.usable_area_sqm) for p in e.plantas] == [
        ("Útil planta baja", 0, Decimal("6023")),
        ("Útil planta primera", 1, Decimal("1234")),
    ]
    # 6.023 + 1.234 = 7.257 aquí, pero el total sale de SU fila, no de la suma.
    assert e.propuesta["usable_area_sqm"] == "7257"


def test_la_cabecera_de_la_tabla_no_se_toma_por_un_dato() -> None:
    e = Extraccion()
    _leer_tabla(SUPERFICIES, e)
    assert "Concepto" not in e.desconocidos


def test_cada_dato_guarda_la_celda_tal_y_como_estaba_escrita() -> None:
    """`[REQ]` La evidencia es lo que hace comprobable una propuesta.

    Y tiene que ser **literal**. «`plot_area_sqm` = 12410» es la lectura de la
    máquina repetida: si la máquina confundió el separador de millares, ese
    texto no lo delata. «Parcela | 12.410 m²» sí, porque quien valida lo compara
    con el PDF y ve la misma cadena o no la ve.
    """
    e = Extraccion()
    _leer_tabla(SUPERFICIES, e)

    assert e.evidencias["plot_area_sqm"] == "Parcela | 12.410 m²"
    assert e.evidencias["occupied_area_sqm"] == "Ocupación | 6.766 m²"
    # También las plantas, que no son campos del activo y van por su nombre.
    assert e.evidencias["planta:Útil planta baja"] == "Útil planta baja | 6.023 m²"


# ─────────────────────────────────────────────────────────────────────────────
#  Lo que no se sabe
# ─────────────────────────────────────────────────────────────────────────────


def test_un_valor_anonimizado_no_se_vuelca_como_dato() -> None:
    """`[REQ]` Un documento anonimizado —o uno a medio rellenar— trae
    marcadores entre corchetes. Volcarlos llenaría la ficha de texto que parece
    un dato y no lo es."""
    e = Extraccion()
    _leer_tabla([["Promotor", "[PROMOTOR]"], ["Emplazamiento", "[UBICACIÓN]"]], e)

    assert "developer" not in e.propuesta
    assert "address_line" not in e.propuesta
    assert len(e.avisos) == 2
    assert all("a mano" in a for a in e.avisos)


def test_una_etiqueta_desconocida_se_declara_en_vez_de_perderse() -> None:
    """Es como se descubre el sinónimo que falta. Descartarla en silencio
    dejaría creer que el documento no traía el dato."""
    e = Extraccion()
    _leer_tabla([["Superficie de sótano", "900 m²"]], e)

    assert e.desconocidos == {"Superficie de sótano": "900 m²"}
    assert not e.propuesta


def test_las_etiquetas_de_portada_que_no_son_del_activo_salen_aparte() -> None:
    """El consultor quiere verlas al validar aunque la ficha no tenga dónde
    guardarlas."""
    e = Extraccion()
    _leer_tabla([["Tipo de actuación", "Construcción de nave"]], e)

    assert e.informativos == {"Tipo de actuación": "Construcción de nave"}
    assert not e.desconocidos


# ─────────────────────────────────────────────────────────────────────────────
#  La clasificación, y su límite
# ─────────────────────────────────────────────────────────────────────────────

#: Redactada como la sección real que hizo evidente el problema.
INSTALACIONES = Seccion(
    codigo="MC.6",
    titulo="Instalaciones",
    cuerpo=(
        "Acometida y centro de transformación, cuadros, LED, emergencia, fuerza, "
        "tierras y rayo; AF y ACS; climatización y ventilación de oficinas; PCI; "
        "redes separadas de pluviales y fecales; telecomunicaciones; y ascensor "
        "accesible de dos paradas."
    ),
)
ESTRUCTURA = Seccion(
    codigo="MC.3",
    titulo="Sistema estructural",
    cuerpo="Hormigón prefabricado en pilares, vigas, jácenas, correas y placas alveolares.",
)

CAPITULOS = {
    "HC.H01": "Estructura",
    "HC.H08": "HVAC",
    "HC.H09": "Electricidad",
    "HC.H10": "Protección activa contra incendios",
    "HC.H11": "Fontanería y saneamiento",
    "HC.H12": "Transporte vertical",
    "HC.H14": "Telecomunicaciones",
}
MAPA = {
    "MC.3": ["HC.H01"],
    "MC.6": ["HC.H08", "HC.H09", "HC.H10", "HC.H11", "HC.H12", "HC.H14"],
}


def test_una_seccion_que_toca_un_solo_capitulo_es_correcta_por_construccion() -> None:
    d = PorSeccion(mapa=MAPA).clasificar([ESTRUCTURA], CAPITULOS)

    assert {o.capex_chapter_code for o in d.objetos} == {"HC.H01"}
    assert "Vigas" in [o.nombre for o in d.objetos]


def test_una_seccion_que_toca_seis_capitulos_lo_dice_en_vez_de_repartir_al_azar() -> None:
    """`[LIM]` Es el límite honesto del adaptador que hay hoy.

    Un diccionario de palabras clave acertaría en esta memoria y fallaría en la
    siguiente escrita con otras palabras, y ese fallo **no se vería**: los
    objetos saldrían en el capítulo equivocado con aspecto de estar bien.
    """
    d = PorSeccion(mapa=MAPA).clasificar([INSTALACIONES], CAPITULOS)

    assert {o.capex_chapter_code for o in d.objetos} == {"HC.H08"}, "todos al primero"
    assert any("6 capítulos" in a and "a mano" in a for a in d.avisos)


def test_el_dictamen_declara_que_es_simulado() -> None:
    """`[REQ]` Una clasificación simulada no puede pasar por una de verdad ni en
    la base ni en la pantalla. Es la misma regla que la revisión documental."""
    d = PorSeccion(mapa=MAPA).clasificar([ESTRUCTURA], CAPITULOS)
    assert d.es_simulado is True
    assert d.proveedor == "por-seccion"


def test_cada_objeto_viaja_con_su_evidencia() -> None:
    """Una propuesta sin respaldo es un acto de fe. Quien valida tiene que poder
    ir a la memoria y comprobarlo."""
    d = PorSeccion(mapa=MAPA).clasificar([ESTRUCTURA], CAPITULOS)
    for objeto in d.objetos:
        assert objeto.evidencia
        assert objeto.seccion.startswith("MC.3")


def test_la_normativa_y_los_agentes_no_producen_objetos() -> None:
    """«Real Decreto 314/2006» no es algo que se repare. Clasificar las
    secciones que no describen obra produciría partidas que no lo son."""
    normativa = Seccion(
        codigo="MN", titulo="Normativa aplicable", cuerpo="Código Técnico, accesibilidad, acústica."
    )
    agentes = Seccion(
        codigo="MG.2", titulo="Agentes del proyecto", cuerpo="Promotor, proyectista, contratista."
    )

    d = PorSeccion(mapa={"MN": ["HC.H01"], "MG.2": ["HC.H01"]}).clasificar(
        [normativa, agentes], CAPITULOS
    )
    assert d.objetos == []

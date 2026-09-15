"""El diseño de la tabla de CAPEX y su contrato con el exportador.

La prueba que más importa es `test_el_pptx_y_el_xlsx_no_pueden_divergir`: es la
que impide que, dentro de seis meses, el PowerPoint y el Excel que viajan en el
mismo correo tengan columnas distintas.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tdd.reporting import capex_layout as cl


def _linea(**kw) -> cl.LineaCapex:
    """Una línea con los tres niveles del árbol puestos, que es como llegan del
    snapshot desde que la tabla agrupa igual que la plantilla."""
    base = dict(
        numero="",
        zona="Cubierta",
        concepto="Vida útil",
        descripcion="Renovar impermeabilización",
        riesgo="Moderado",
        comentarios="Fin de vida útil",
        horizonte="MEDIO",
        importe=Decimal("83407.50"),
        tipo_de_coste="Hard Costs",
        capitulo="Cubierta",
        objeto="Cubierta",
        recuperable="NO",
    )
    return cl.LineaCapex(**{**base, **kw})


LINEAS = [
    _linea(),
    _linea(
        concepto="Mantenimiento",
        descripcion="Limpieza de lucernarios",
        riesgo="Bajo",
        comentarios="Gasto operativo",
        horizonte="CORTO",
        importe=Decimal("2300.00"),
        objeto="General",
        recuperable="SI",
    ),
    _linea(
        zona="General",
        concepto="Normativa",
        descripcion="Adecuación RIPCI",
        riesgo="Extremo",
        comentarios="Incumplimiento",
        horizonte="CORTO",
        importe=Decimal("144780.00"),
        capitulo="Protección activa contra incendios",
        objeto="Inspección RIPCI",
    ),
    _linea(
        zona="General",
        concepto="Otro",
        descripcion="Petición del cliente",
        riesgo="Bajo",
        comentarios="Fuera del alcance",
        horizonte="OTRO",
        importe=Decimal("12000.00"),
        tipo_de_coste="Soft Costs",
        capitulo="Licencias y Tasas",
        objeto="General",
        recuperable="N.A.",
    ),
]


def _layout(**kw) -> cl.CapexTableLayout:
    return cl.construir(LINEAS, capitulo="Arquitectura", **kw)


# ─────────────────────────────────────────────────────────────────────────────
#  Estructura verificada sobre el render de la plantilla real
# ─────────────────────────────────────────────────────────────────────────────


def test_las_columnas_son_las_del_render_y_en_su_orden() -> None:
    """docs/20 §20.3 C-6 · El render destapó `Nº` y `Group`, y que `Comments`
    va ANTES de las columnas de plazo. Al llegar la plantilla CAPEX vigente se
    añadieron `Objeto`, `Recuperable` y `TOTAL`; el tipo de coste y el capítulo
    NO son columnas —son filas de sección— porque en 4:3 no cabe repetir el
    mismo texto quince veces."""
    claves = [c.key for c in _layout().columnas]
    assert claves == [
        "no",
        "objeto",
        "zona",
        "descripcion",
        "riesgo",
        "comentarios",
        "concepto",
        "recuperable",
        "corto",
        "medio",
        "largo",
        "mejoras",
        "otro",
        "total",
    ]


def test_la_columna_de_riesgo_existe() -> None:
    """C-7 · Afirmé que la tabla no llevaba riesgo. El render demostró que sí:
    es la columna `Group`, con High/Moderate/Low."""
    riesgo = next(c for c in _layout().columnas if c.key == "riesgo")
    assert riesgo.titulo_en == "Group"
    fila = next(f for f in _layout().filas if f.tipo == "dato")
    assert fila.celdas["riesgo"] in {"Moderado", "Bajo", "Extremo", "Alto"}


def test_la_cabecera_de_plazos_se_agrupa() -> None:
    plazos = [c for c in _layout().columnas if c.grupo == "capex"]
    assert len(plazos) == 5
    assert all(c.es_importe for c in plazos)


def test_la_columna_otro_se_muestra_por_defecto() -> None:
    """[REQ] P-37 · El Excel de trabajo la tiene y es la versión más actualizada."""
    assert "otro" in {c.key for c in _layout().columnas}
    assert "otro" not in {c.key for c in _layout(incluir_otro=False).columnas}


# ─────────────────────────────────────────────────────────────────────────────
#  Formato de importe
# ─────────────────────────────────────────────────────────────────────────────


def test_una_celda_sin_importe_queda_en_blanco_y_no_a_cero() -> None:
    """Es como está en la plantilla, y distingue «no aplica» de «cero»: un cero
    explícito afirma que la actuación cuesta cero, que no es lo mismo."""
    assert cl.formatear_importe(None) == ""
    fila = next(f for f in _layout().filas if f.celdas.get("no") == "1.1.1")
    vacias = [fila.celdas[k] for k in ("largo", "mejoras", "otro")]
    assert vacias == ["", "", ""]
    assert "0,00" not in "".join(vacias)


@pytest.mark.parametrize(
    ("valor", "locale", "esperado"),
    [
        (Decimal("83407.50"), "es-ES", "83.407,50 €"),
        (Decimal("1040078.95"), "es-ES", "1.040.078,95 €"),
        (Decimal("0"), "es-ES", "0,00 €"),
        (Decimal("83407.50"), "en-GB", "83,407.50 €"),
    ],
)
def test_formato_de_importe(valor: Decimal, locale: str, esperado: str) -> None:
    assert cl.formatear_importe(valor, locale) == esperado


# ─────────────────────────────────────────────────────────────────────────────
#  Agrupación, subtotales y totales
# ─────────────────────────────────────────────────────────────────────────────


def test_se_agrupa_por_tipo_de_coste_y_capitulo_como_la_plantilla() -> None:
    """Antes se agrupaba por zona, que no está en la plantilla y separaba dos
    actuaciones del mismo sistema por estar en plantas distintas."""
    secciones = [f for f in _layout().filas if f.tipo == "seccion"]
    assert [(f.nivel, f.capitulo) for f in secciones] == [
        (1, "Hard Costs"),
        (2, "Cubierta"),
        (2, "Protección activa contra incendios"),
        (1, "Soft Costs"),
        (2, "Licencias y Tasas"),
    ]


def test_cada_seccion_lleva_su_subtotal() -> None:
    secciones = {f.capitulo: f for f in _layout().filas if f.tipo == "seccion"}
    cubierta = secciones["Cubierta"]
    assert cubierta.celdas["corto"] == "2.300,00 €"
    assert cubierta.celdas["medio"] == "83.407,50 €"
    assert cubierta.celdas["total"] == "85.707,50 €"
    # El de nivel 1 suma sus capítulos.
    assert secciones["Hard Costs"].celdas["total"] == "230.487,50 €"


def test_la_numeracion_es_jerarquica_como_en_el_original() -> None:
    numeros = [f.celdas["no"] for f in _layout().filas if f.tipo in ("seccion", "dato")]
    assert numeros == ["1.", "1.1", "1.1.1", "1.1.2", "1.2", "1.2.1", "2.", "2.1", "2.1.1"]


def test_los_totales_cuadran_con_las_lineas() -> None:
    t = _layout().totales
    assert t["corto"] == Decimal("147080.00")
    assert t["medio"] == Decimal("83407.50")
    assert t["otro"] == Decimal("12000.00")
    # `total` es la suma de los cinco plazos: se excluye o contaría dos veces.
    assert t["total"] == sum(ln.importe for ln in LINEAS)
    assert sum(v for k, v in t.items() if k != "total") == t["total"]


PLAZOS = ("corto", "medio", "largo", "mejoras", "otro")


def test_una_actuacion_sin_recurrencia_llena_una_sola_columna() -> None:
    """P-05 comprobado en la salida, no solo en el modelo."""
    for fila in (f for f in _layout().filas if f.tipo == "dato"):
        con_valor = [k for k in PLAZOS if fila.celdas.get(k)]
        assert len(con_valor) == 1, f"La fila {fila.celdas['no']} llena {con_valor}"


# ─────────────────────────────────────────────────────────────────────────────
#  [REQ] P-44 · Actuaciones recurrentes
# ─────────────────────────────────────────────────────────────────────────────

RECURRENTE = [
    # La misma actuación, dos líneas: hace falta ahora y otra vez en diez años.
    cl.LineaCapex(
        "",
        "Cubierta",
        "Mantenimiento",
        "Limpieza de lucernarios",
        "Bajo",
        "Gasto operativo recurrente",
        "CORTO",
        Decimal("2300.00"),
        finding_id="HAL-1",
    ),
    cl.LineaCapex(
        "",
        "Cubierta",
        "Mantenimiento",
        "Limpieza de lucernarios",
        "Bajo",
        "Gasto operativo recurrente",
        "LARGO",
        Decimal("2300.00"),
        finding_id="HAL-1",
    ),
]


def test_una_actuacion_recurrente_es_una_sola_fila_con_dos_plazos() -> None:
    """P-44 · Es el patrón real del Excel del cliente: 5 de 19 filas lo tienen.

    Dos líneas del mismo hallazgo NO son dos filas de la tabla: son una sola
    actuación que hace falta dos veces, y así se presenta.
    """
    layout = cl.construir(RECURRENTE, capitulo="Arquitectura")
    datos = [f for f in layout.filas if f.tipo == "dato"]

    assert len(datos) == 1, "Las dos líneas del mismo hallazgo van en una fila"
    fila = datos[0]
    assert fila.celdas["corto"] == "2.300,00 €"
    assert fila.celdas["largo"] == "2.300,00 €"
    assert fila.celdas["medio"] == ""
    assert fila.celdas["descripcion"] == "Limpieza de lucernarios"


def test_los_totales_cuentan_las_dos_lineas_de_una_recurrente() -> None:
    """No es doble contabilidad: son dos desembolsos reales en dos momentos."""
    t = cl.construir(RECURRENTE, capitulo="Arquitectura").totales
    assert t["corto"] == Decimal("2300.00")
    assert t["largo"] == Decimal("2300.00")
    # `total` es la suma de los plazos, así que se excluye del cuadre.
    assert t["total"] == Decimal("4600.00")
    assert sum(v for k, v in t.items() if k != "total") == Decimal("4600.00")


def test_p05_sigue_intacta_a_nivel_de_linea() -> None:
    """La decisión del cliente no se ha tocado: cada LÍNEA tiene un horizonte y
    un importe. Lo que puede tener varias líneas es la ACTUACIÓN."""
    for ln in RECURRENTE:
        assert ln.horizonte in {"CORTO", "MEDIO", "LARGO", "MEJORAS", "OTRO"}
        assert isinstance(ln.importe, Decimal)


def test_sin_hallazgo_cada_linea_va_por_su_cuenta() -> None:
    """Las líneas sueltas no se funden por parecerse: solo agrupa el hallazgo."""
    sueltas = [
        cl.LineaCapex(
            "", "Cubierta", "Mant.", "Misma descripción", "Bajo", "", "CORTO", Decimal("100")
        ),
        cl.LineaCapex(
            "", "Cubierta", "Mant.", "Misma descripción", "Bajo", "", "LARGO", Decimal("200")
        ),
    ]
    datos = [f for f in cl.construir(sueltas, capitulo="Arq.").filas if f.tipo == "dato"]
    assert len(datos) == 2


def test_el_titulo_cambia_con_el_idioma() -> None:
    assert "VALORACIÓN" in _layout(locale="es-ES").titulo
    assert "ESTIMATE ASSESSMENT" in _layout(locale="en-GB").titulo
    assert _layout(locale="en-GB").titulo_columna(_layout().columnas[1]) == "Item"


# ─────────────────────────────────────────────────────────────────────────────
#  Partición entre diapositivas
# ─────────────────────────────────────────────────────────────────────────────


def test_una_tabla_corta_no_se_parte() -> None:
    assert len(cl.particionar(_layout(), filas_por_diapositiva=18)) == 1


def test_una_tabla_larga_se_parte_y_numera() -> None:
    muchas = LINEAS * 12
    layout = cl.construir(muchas, capitulo="Arquitectura")
    trozos = cl.particionar(layout, filas_por_diapositiva=10)
    assert len(trozos) > 1
    assert "(1/" in trozos[0].titulo
    assert sum(len(t.filas) for t in trozos) == len(layout.filas)


def test_una_seccion_no_se_queda_huerfana_al_final_de_una_diapositiva() -> None:
    """[REC] Un encabezado de sección solo, al pie de una diapositiva, con sus
    filas en la siguiente, es exactamente lo que nadie quiere ver."""
    layout = cl.construir(LINEAS * 8, capitulo="Arquitectura")
    for trozo in cl.particionar(layout, filas_por_diapositiva=6):
        if len(trozo.filas) > 1:
            assert trozo.filas[-1].tipo != "seccion", "Sección huérfana al final del trozo"


def test_solo_el_ultimo_trozo_lleva_los_totales() -> None:
    trozos = cl.particionar(cl.construir(LINEAS * 12, capitulo="Arq."), filas_por_diapositiva=10)
    assert all(not t.totales for t in trozos[:-1])
    assert trozos[-1].totales


# ─────────────────────────────────────────────────────────────────────────────
#  El contrato entre los dos generadores  [REQ] P-31
# ─────────────────────────────────────────────────────────────────────────────
def test_el_ancho_total_se_mantiene_cerca_del_original() -> None:
    """El original mide 9,06 in. Con la quinta columna de P-37 crece, pero no
    puede desbordar la diapositiva de 10 in menos márgenes."""
    assert _layout().ancho_total_in <= 9.5
    assert _layout(incluir_otro=False).ancho_total_in <= 9.06


# ─────────────────────────────────────────────────────────────────────────────
#  [REQ] P-42 · Los cuatro grados de riesgo
# ─────────────────────────────────────────────────────────────────────────────


def test_los_cuatro_grados_de_riesgo_llegan_a_la_tabla() -> None:
    """P-42 · El ejemplo del cliente solo mostraba tres (`High`/`Moderate`/`Low`),
    pero confirmó que **Extremo tiene que estar**: simplemente no se usó en esa
    muestra. No se agrupa nada al presentar."""
    lineas = [
        cl.LineaCapex("", "General", "Normativa", f"Actuación {g}", g, "", "CORTO", Decimal("1000"))
        for g in ("Bajo", "Moderado", "Alto", "Extremo")
    ]
    filas = [f for f in cl.construir(lineas, capitulo="Arq.").filas if f.tipo == "dato"]
    assert {f.celdas["riesgo"] for f in filas} == {"Bajo", "Moderado", "Alto", "Extremo"}


# ─────────────────────────────────────────────────────────────────────────────
#  Los resúmenes de la sección 07
#
#  `[REQ]` La sección 07 de la plantilla del cliente no tiene una tabla: tiene
#  cinco. Las otras cuatro venían pegadas desde Excel, con los números de otro
#  proyecto impresos en un informe firmado.
# ─────────────────────────────────────────────────────────────────────────────

#: El catálogo de riesgo tal como llega del snapshot: `(nombre, score)`.
NIVELES = [("Extremo", 4), ("Alto", 3), ("Moderado", 2), ("Bajo", 1)]

#: Las mismas líneas, con el **código** del capítulo puesto, que es lo que
#: reparte cada una entre la tabla de arquitectura y la de instalaciones.
LINEAS_CON_CODIGO = [
    _linea(capitulo_code="HC.H02"),  # cubierta → arquitectura
    _linea(
        horizonte="CORTO",
        importe=Decimal("2300.00"),
        riesgo="Bajo",
        capitulo_code="HC.H02",
    ),
    _linea(
        horizonte="CORTO",
        importe=Decimal("144780.00"),
        riesgo="Extremo",
        capitulo="Protección activa contra incendios",
        capitulo_code="HC.H10",  # → instalaciones
    ),
    _linea(
        horizonte="OTRO",
        importe=Decimal("12000.00"),
        riesgo="Bajo",
        tipo_de_coste="Soft Costs",
        capitulo="Licencias y Tasas",
        capitulo_code="SC.S03",  # ni una ni otra: es coste blando
    ),
]


def _fila(layout: cl.CapexTableLayout, rotulo: str) -> cl.Fila:
    clave = layout.columnas[0].key
    return next(f for f in layout.filas if f.celdas.get(clave) == rotulo)


def test_el_resumen_por_riesgo_enseña_los_cuatro_grados_aunque_falte_alguno() -> None:
    """La plantilla los enseña **siempre**. Con solo los presentes, la fila
    desaparecería y quien lee no sabría si es que no hay o si se olvidó."""
    layout = cl.resumen_por_riesgo(LINEAS_CON_CODIGO, niveles=NIVELES)
    rotulos = [f.celdas["riesgo"] for f in layout.filas]
    assert rotulos == ["Extremo", "Alto", "Moderado", "Bajo", "TOTAL"]
    # «Alto» no tiene ninguna línea: sale la fila, con las celdas en blanco.
    assert _fila(layout, "Alto").celdas["total"] == ""


def test_el_resumen_por_riesgo_cuadra_con_las_lineas() -> None:
    layout = cl.resumen_por_riesgo(LINEAS_CON_CODIGO, niveles=NIVELES)
    assert layout.totales["total"] == sum(ln.importe for ln in LINEAS_CON_CODIGO)
    assert _fila(layout, "Extremo").celdas["corto"] == "144.780,00 €"
    assert _fila(layout, "Moderado").celdas["medio"] == "83.407,50 €"


def test_un_riesgo_que_no_esta_en_el_catalogo_no_se_descarta() -> None:
    """Descartarlo cuadraría la tabla restando un importe sin decirlo."""
    lineas = [*LINEAS_CON_CODIGO, _linea(riesgo="Catastrófico", importe=Decimal("500.00"))]
    layout = cl.resumen_por_riesgo(lineas, niveles=NIVELES)
    assert _fila(layout, "Catastrófico").celdas["total"] == "500,00 €"
    assert layout.totales["total"] == sum(ln.importe for ln in lineas)


def test_el_resumen_por_capitulo_recoge_tambien_lo_que_no_es_obra() -> None:
    """Es donde se ve que el presupuesto es mayor que la suma de las dos tablas
    de detalle: el coste blando no cabe en ninguna de las dos."""
    layout = cl.resumen_por_capitulo(LINEAS_CON_CODIGO)
    capitulos = [f.celdas["capitulo"] for f in layout.filas]
    assert "Licencias y Tasas" in capitulos
    assert layout.totales["total"] == sum(ln.importe for ln in LINEAS_CON_CODIGO)


def test_el_resumen_de_costes_separa_mejora_de_capex() -> None:
    """La plantilla las pone en dos columnas porque una mejora no es una
    obligación: se negocia aparte."""
    lineas = [
        _linea(horizonte="CORTO", importe=Decimal("1000.00"), capitulo_code="HC.H02"),
        _linea(horizonte="MEJORAS", importe=Decimal("400.00"), capitulo_code="HC.H02"),
    ]
    layout = cl.resumen_de_costes(lineas)
    total = _fila(layout, "TOTAL PRESUPUESTO (SIN IVA)")
    assert total.celdas["capex"] == "1.000,00 €"
    assert total.celdas["mejoras"] == "400,00 €"
    assert total.celdas["total"] == "1.400,00 €"


def test_el_coste_duro_va_sin_desglose_y_el_blando_con_el() -> None:
    """`[LIM]` El desglose del coste duro es la tabla de la diapositiva
    anterior; repetirlo aquí solo alargaría la página."""
    layout = cl.resumen_de_costes(LINEAS_CON_CODIGO)
    conceptos = [f.celdas["concepto"] for f in layout.filas]
    assert "HARD COSTS" in conceptos
    assert "Cubierta" not in conceptos  # el capítulo de obra no se repite
    assert "Licencias y Tasas" in conceptos  # el de coste blando sí


def test_el_detalle_se_reparte_en_arquitectura_e_instalaciones() -> None:
    """`[REQ]` La plantilla tiene **dos** tablas de detalle, con estos mismos
    capítulos: es la división que su sección 04 ya hace."""
    arquitectura = cl.del_bloque(LINEAS_CON_CODIGO, "arquitectura")
    instalaciones = cl.del_bloque(LINEAS_CON_CODIGO, "instalaciones")

    assert [ln.capitulo_code for ln in arquitectura] == ["HC.H02", "HC.H02"]
    assert [ln.capitulo_code for ln in instalaciones] == ["HC.H10"]
    # El coste blando no está en ninguna de las dos: su sitio es el resumen de
    # presupuesto, no la «valoración de las actuaciones en el inmueble».
    assert sum(ln.importe for ln in arquitectura + instalaciones) == Decimal("230487.50")


def test_un_capitulo_de_obra_nuevo_no_desaparece_en_silencio() -> None:
    """Sumaría en los resúmenes y no saldría en ninguna tabla de detalle: la
    diferencia es invisible salvo que alguien cuadre las cifras a mano."""
    lineas = [*LINEAS_CON_CODIGO, _linea(capitulo_code="HC.H99", importe=Decimal("100.00"))]
    huerfanas = cl.fuera_de_los_bloques(lineas)
    assert [ln.capitulo_code for ln in huerfanas] == ["HC.H99"]
    # Y lo que sí está repartido no se señala.
    assert cl.fuera_de_los_bloques(LINEAS_CON_CODIGO) == []

"""Análisis del XLSX de inventario `[REQ]` §7 / P-15.

Lo que se comprueba aquí no es que lea celdas: es que **no adivine**. Un
sistema técnico que no casa no se aproxima al más parecido, un activo que no
existe no se crea, una columna que no se reconoce se enumera en vez de
perderse, y nada de lo que ya está en la base se sobrescribe por venir en una
hoja.
"""

from __future__ import annotations

from decimal import Decimal

from tdd.equipment.importacion import (
    Activo,
    Estado,
    Sistema,
    analizar,
    clave,
    mapear_cabeceras,
)

NAVE = Activo(id="a-nave", name="Nave Logística Norte", asset_code="NAVE-A")
OFICINAS = Activo(id="a-ofi", name="Edificio de Oficinas", asset_code=None)
ACTIVOS = [NAVE, OFICINAS]

SISTEMAS = [
    Sistema(id="s-clima", code="CLIMATIZACION", name_es="Climatización"),
    Sistema(id="s-asc", code="ASCENSORES", name_es="Ascensores"),
]

CABECERA = [
    "Activo",
    "Etiqueta",
    "Tipo de equipo",
    "Sistema técnico",
    "Fabricante",
    "Año de instalación",
    "Vida útil esperada",
    "Estado de conservación",
]


def fila(*celdas: str) -> list[str]:
    return list(celdas) + [""] * (len(CABECERA) - len(celdas))


def correr(filas: list[list[str]], existentes: dict | None = None, cabecera=None):
    return analizar(
        cabecera if cabecera is not None else CABECERA,
        filas,
        activos=ACTIVOS,
        sistemas=SISTEMAS,
        etiquetas_existentes=existentes or {},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Cabeceras
# ─────────────────────────────────────────────────────────────────────────────


def test_las_cabeceras_se_reconocen_con_tildes_o_sin_ellas() -> None:
    """En un Excel rellenado a mano conviven «Año» y «Ano», y las dos son lo
    mismo. Rechazar por una tilde sería hacer perder el tiempo."""
    mapa, _, ausentes = mapear_cabeceras(["ACTIVO ", "tipo de equipo", "Año de instalación"])
    assert mapa == {0: "asset", 1: "equipment_type", 2: "install_year"}
    assert ausentes == []


def test_una_columna_que_no_se_entiende_se_enumera_y_no_se_pierde_en_silencio() -> None:
    """Una columna «Nº serie» mal escrita perdería el dato sin que nadie se
    enterase hasta buscarlo meses después."""
    _, ignoradas, _ = mapear_cabeceras(["Activo", "Tipo de equipo", "Presupuesto 2027"])
    assert ignoradas == ["Presupuesto 2027"]


def test_sin_columna_de_activo_no_se_recorre_la_hoja() -> None:
    """Se devuelve el diagnóstico y ya. Recorrer trescientas filas para producir
    trescientos errores idénticos entierra el problema real."""
    resultado = correr([fila("x", "y")], cabecera=["Etiqueta", "Tipo de equipo"])
    assert resultado.filas == []
    assert resultado.columnas_ausentes == ["Activo"]


# ─────────────────────────────────────────────────────────────────────────────
#  El activo: existe o es un error
# ─────────────────────────────────────────────────────────────────────────────


def test_el_activo_casa_por_nombre_o_por_codigo() -> None:
    resultado = correr(
        [fila("Nave Logística Norte", "", "Enfriadora"), fila("NAVE-A", "", "Bomba")]
    )
    assert [f.estado for f in resultado.filas] == [Estado.NUEVA, Estado.NUEVA]
    assert {f.valores["asset_id"] for f in resultado.filas} == {"a-nave"}


def test_un_activo_que_no_existe_es_un_error_y_no_se_crea() -> None:
    """`[REQ]` No se inventa nada. Un activo es una ficha con veinte campos y
    una tipología que manda sobre las zonas: fabricarlo a partir del nombre
    suelto de una celda produciría un edificio a medias."""
    resultado = correr([fila("Nave del Sur", "", "Enfriadora")])
    unica = resultado.filas[0]
    assert unica.estado is Estado.ERROR
    assert "no es un activo de este encargo" in unica.errores[0]
    assert "antes de importar" in unica.errores[0]


def test_falta_el_tipo_de_equipo() -> None:
    resultado = correr([fila("NAVE-A", "CL-01", "")])
    assert resultado.filas[0].estado is Estado.ERROR


# ─────────────────────────────────────────────────────────────────────────────
#  El sistema técnico: si no casa, no se aproxima
# ─────────────────────────────────────────────────────────────────────────────


def test_el_sistema_casa_sin_tildes_y_en_cualquier_caja() -> None:
    resultado = correr([fila("NAVE-A", "CL-01", "Enfriadora", "CLIMATIZACION")])
    assert resultado.filas[0].valores["technical_system_id"] == "s-clima"


def test_un_sistema_desconocido_entra_sin_clasificar_y_lo_dice() -> None:
    """No se busca el más parecido: «Climatizacion y ACS» podría ser
    climatización o fontanería, y elegir por él sería inventar el dato."""
    resultado = correr([fila("NAVE-A", "CL-01", "Enfriadora", "Climatizacion y ACS")])
    unica = resultado.filas[0]
    assert unica.estado is Estado.NUEVA
    assert unica.valores["technical_system_id"] is None
    assert "sin clasificar" in unica.avisos[0]


# ─────────────────────────────────────────────────────────────────────────────
#  Vida útil
# ─────────────────────────────────────────────────────────────────────────────


def test_los_dos_anos_o_ninguno() -> None:
    resultado = correr([fila("NAVE-A", "CL-01", "Enfriadora", "", "", "2010", "")])
    assert resultado.filas[0].estado is Estado.ERROR
    assert "juntos o no van" in " ".join(resultado.filas[0].errores)


def test_un_ano_que_excel_da_como_decimal_se_lee_bien() -> None:
    """Una celda numérica llega como «2010.0». Convertir directo a `int`
    reventaría, y la fila entera se perdería por el formato de la celda."""
    resultado = correr([fila("NAVE-A", "CL-01", "Enfriadora", "", "", "2010.0", "20")])
    assert resultado.filas[0].valores["install_year"] == 2010


def test_un_ano_que_no_es_un_numero_se_rechaza_con_su_texto() -> None:
    resultado = correr([fila("NAVE-A", "CL-01", "Enfriadora", "", "", "hacia 2010", "20")])
    assert resultado.filas[0].estado is Estado.ERROR
    assert "hacia 2010" in " ".join(resultado.filas[0].errores)


def test_sin_anos_la_fila_es_valida() -> None:
    """En una visita se apunta el fabricante y no siempre el año. Exigirlo
    dejaría fuera la mitad del inventario real."""
    resultado = correr([fila("NAVE-A", "CL-01", "Enfriadora")])
    assert resultado.filas[0].estado is Estado.NUEVA
    assert resultado.filas[0].valores["install_year"] is None


# ─────────────────────────────────────────────────────────────────────────────
#  Etiquetas: nada se sobrescribe solo
# ─────────────────────────────────────────────────────────────────────────────


def test_una_etiqueta_repetida_en_el_fichero_señala_la_otra_fila() -> None:
    resultado = correr(
        [fila("NAVE-A", "CL-01", "Enfriadora"), fila("NAVE-A", "CL-01", "Otra enfriadora")]
    )
    assert resultado.filas[1].estado is Estado.DUPLICADA_EN_FICHERO
    assert "fila 2" in resultado.filas[1].errores[0]


def test_la_misma_etiqueta_en_dos_activos_distintos_no_es_duplicado() -> None:
    """La etiqueta identifica al equipo DENTRO del activo: así está rotulado en
    la sala, y dos edificios se rotulan igual."""
    resultado = correr(
        [fila("NAVE-A", "CL-01", "Enfriadora"), fila("Edificio de Oficinas", "CL-01", "Enfriadora")]
    )
    assert [f.estado for f in resultado.filas] == [Estado.NUEVA, Estado.NUEVA]


def test_una_etiqueta_que_ya_esta_en_la_base_no_se_toca() -> None:
    """`[REQ]` Nada se sobrescribe solo. La ficha que hay la escribió alguien en
    una visita a la que no se vuelve."""
    existentes = {("a-nave", "cl-01"): "eq-1"}
    resultado = correr([fila("NAVE-A", "CL-01", "Enfriadora")], existentes)
    unica = resultado.filas[0]
    assert unica.estado is Estado.YA_EXISTE
    assert unica.existente_id == "eq-1"
    assert "No se toca" in unica.avisos[0]
    assert resultado.nuevas == []


def test_la_etiqueta_existente_se_compara_normalizada() -> None:
    """«cl-01» y «CL-01 » son el mismo equipo. Sin normalizar, la importación
    chocaría contra el índice único de la base en vez de avisar."""
    existentes = {("a-nave", "cl-01"): "eq-1"}
    resultado = correr([fila("NAVE-A", " CL-01 ", "Enfriadora")], existentes)
    assert resultado.filas[0].estado is Estado.YA_EXISTE


def test_sin_etiqueta_no_hay_choque_posible() -> None:
    """La etiqueta es opcional: hay equipos sin rotular. Dos filas sin etiqueta
    son dos equipos distintos, no un duplicado."""
    resultado = correr([fila("NAVE-A", "", "Enfriadora"), fila("NAVE-A", "", "Enfriadora")])
    assert [f.estado for f in resultado.filas] == [Estado.NUEVA, Estado.NUEVA]


# ─────────────────────────────────────────────────────────────────────────────
#  Valores sueltos
# ─────────────────────────────────────────────────────────────────────────────


def test_el_estado_se_admite_por_etiqueta_o_por_codigo() -> None:
    resultado = correr(
        [
            fila("NAVE-A", "A", "Enfriadora", "", "", "", "", "Muy deficiente"),
            fila("NAVE-A", "B", "Enfriadora", "", "", "", "", "MUY_DEFICIENTE"),
        ]
    )
    assert [f.valores["condition"] for f in resultado.filas] == ["MUY_DEFICIENTE"] * 2


def test_un_estado_inventado_avisa_y_deja_la_fila_sin_valorar_pero_valida() -> None:
    """Perder una ficha entera porque alguien escribió «regular» en una columna
    opcional sería absurdo: el resto de la fila es bueno."""
    resultado = correr([fila("NAVE-A", "A", "Enfriadora", "", "", "", "", "regular")])
    unica = resultado.filas[0]
    assert unica.estado is Estado.NUEVA
    assert unica.valores["condition"] is None
    assert "no es un valor conocido" in unica.avisos[0]


def test_las_filas_en_blanco_del_final_no_cuentan() -> None:
    """Una hoja real tiene decenas."""
    resultado = correr([fila("NAVE-A", "A", "Enfriadora"), fila(""), fila("", "", "")])
    assert len(resultado.filas) == 1


def test_el_numero_de_fila_es_el_que_se_ve_en_excel() -> None:
    """Decir «fila 3» y que sea la 3 ahorra mucho tiempo al corregir."""
    resultado = correr([fila("NAVE-A", "A", "Enfriadora"), fila("Inexistente", "B", "Bomba")])
    assert [f.fila for f in resultado.filas] == [2, 3]


def test_la_cantidad_admite_coma_decimal() -> None:
    resultado = correr(
        [["NAVE-A", "A", "Enfriadora", "", "", "", "", "", "2,5"]],
        cabecera=[*CABECERA, "Cantidad"],
    )
    assert resultado.filas[0].valores["quantity"] == Decimal("2.5")


def test_el_resumen_cuenta_las_tres_cosas() -> None:
    existentes = {("a-nave", "b"): "eq-1"}
    resultado = correr(
        [
            fila("NAVE-A", "A", "Enfriadora"),
            fila("NAVE-A", "B", "Bomba"),
            fila("Inexistente", "C", "Bomba"),
        ],
        existentes,
    )
    assert "1 equipos nuevos" in resultado.resumen()
    assert "1 ya existentes (no se tocan)" in resultado.resumen()
    assert "1 con error" in resultado.resumen()


def test_clave_normaliza_tildes_caja_y_espacios() -> None:
    assert clave("  CLIMATIZACIÓN  ") == "climatizacion"
    assert clave(None) == ""

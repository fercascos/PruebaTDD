"""Leer el fichero que manda el cliente, con sus manías."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from esg.ingesta.lectura_tabular import FicheroIlegible, leer, leer_csv
from esg.ingesta.mapeo import proponer
from esg.ingesta.validacion import analizar_fila, analizar_numero

CSV_ESPANOL = (
    "CUPS;Fecha inicio;Fecha fin;Consumo;Unidad;Tipo\r\n"
    "ES00311234;01/01/2025;31/01/2025;10.240,50;kWh;Electricidad\r\n"
    "ES00311234;01/02/2025;28/02/2025;9.100;kWh;Electricidad\r\n"
).encode("cp1252")


def test_csv_con_punto_y_coma_bom_y_coma_decimal() -> None:
    tabla = leer_csv(CSV_ESPANOL)
    assert tabla.cabeceras[0] == "CUPS"
    assert len(tabla.filas) == 2
    assert tabla.filas[0][0] == 2  # la fila 1 es la de cabeceras


def test_las_filas_en_blanco_no_son_un_error() -> None:
    tabla = leer_csv(b"CUPS;Consumo\r\nES1;10\r\n;\r\nES2;20\r\n")
    assert len(tabla.filas) == 2


def test_un_fichero_sin_cabeceras_se_rechaza_entero() -> None:
    with pytest.raises(FicheroIlegible):
        leer_csv(b"")


def test_un_xlsx_renombrado_a_csv_se_detecta_por_su_firma() -> None:
    """Cien incidencias sin sentido, o una frase útil. Se elige la frase."""
    with pytest.raises(FicheroIlegible) as exc:
        leer(b"PK\x03\x04rotoperoconfirmadezip", nombre="consumos.csv")
    assert "XLSX" in str(exc.value)


def test_una_extension_desconocida_no_se_intenta_leer() -> None:
    with pytest.raises(FicheroIlegible):
        leer(b"algo", nombre="consumos.pdf")


@pytest.mark.parametrize(
    ("escrito", "esperado"),
    [
        ("10.240,50", Decimal("10240.50")),
        ("10,240.50", Decimal("10240.50")),
        ("1234,5", Decimal("1234.5")),
        ("1234.5", Decimal("1234.5")),
        ("1 234,5", Decimal("1234.5")),
        ("1,234", Decimal("1234")),
        ("0,75", Decimal("0.75")),
    ],
)
def test_numeros_como_los_escribe_la_gente(escrito: str, esperado: Decimal) -> None:
    assert analizar_numero(escrito) == esperado


def test_el_mapeo_se_propone_solo_desde_las_cabeceras() -> None:
    mapeo = proponer(leer_csv(CSV_ESPANOL).cabeceras)
    assert mapeo.completo
    assert mapeo.columna("suministro") == "CUPS"
    assert mapeo.columna("cantidad") == "Consumo"
    assert mapeo.columna("vector") == "Tipo"


def test_un_fichero_sin_columna_de_vector_necesita_que_se_diga_cual_es() -> None:
    mapeo = proponer(["CUPS", "Desde", "Hasta", "Consumo", "Unidad"])
    assert not mapeo.completo and "vector" in mapeo.faltan
    con_defecto = proponer(
        ["CUPS", "Desde", "Hasta", "Consumo", "Unidad"], vector_por_defecto="AGUA"
    )
    assert con_defecto.completo


def test_la_fecha_de_fin_del_fichero_es_inclusiva_y_se_guarda_exclusiva() -> None:
    """Sin esto, enero y febrero se solapan un día en cada uno de los doce meses."""
    tabla = leer_csv(CSV_ESPANOL)
    mapeo = proponer(tabla.cabeceras)
    enero, _ = analizar_fila(*tabla.filas[0], mapeo)
    febrero, _ = analizar_fila(*tabla.filas[1], mapeo)
    assert enero is not None and febrero is not None
    assert enero.inicio == date(2025, 1, 1)
    assert enero.fin == date(2025, 2, 1) == febrero.inicio
    assert enero.cantidad == Decimal("10240.50")
    assert enero.vector == "ELECTRICIDAD"


def test_una_fila_mala_no_tumba_la_carga_y_dice_donde_esta() -> None:
    tabla = leer_csv(
        b"CUPS;Fecha inicio;Fecha fin;Consumo;Unidad;Tipo\n"
        b"ES1;01/01/2025;31/01/2025;ochocientos;kWh;Electricidad\n"
    )
    fila, problemas = analizar_fila(*tabla.filas[0], proponer(tabla.cabeceras))
    assert fila is None
    assert [p.codigo for p in problemas] == ["cantidad_invalido"]
    assert problemas[0].fila == 2
    assert problemas[0].columna == "Consumo"
    assert problemas[0].valor == "ochocientos"


def test_un_consumo_negativo_es_una_regularizacion_y_se_rechaza() -> None:
    tabla = leer_csv(
        b"CUPS;Fecha inicio;Fecha fin;Consumo;Unidad;Tipo\n"
        b"ES1;01/01/2025;31/01/2025;-500;kWh;Electricidad\n"
    )
    fila, problemas = analizar_fila(*tabla.filas[0], proponer(tabla.cabeceras))
    assert fila is None
    assert "regularizaci" in problemas[0].mensaje


def test_un_importe_ilegible_no_invalida_el_consumo() -> None:
    """El consumo es el dato; el importe, acompañamiento."""
    tabla = leer_csv(
        b"CUPS;Desde;Hasta;Consumo;Unidad;Tipo;Importe\n"
        b"ES1;01/01/2025;31/01/2025;500;kWh;Electricidad;a convenir\n"
    )
    fila, problemas = analizar_fila(*tabla.filas[0], proponer(tabla.cabeceras))
    assert fila is not None and fila.importe is None
    assert [p.codigo for p in problemas] == ["importe_ignorado"]


def test_un_vector_que_no_existe_se_dice_con_los_que_si() -> None:
    tabla = leer_csv(
        b"CUPS;Desde;Hasta;Consumo;Unidad;Tipo\nES1;01/01/2025;31/01/2025;5;kWh;Fuel\n"
    )
    fila, problemas = analizar_fila(*tabla.filas[0], proponer(tabla.cabeceras))
    assert fila is None
    assert "ELECTRICIDAD" in problemas[0].mensaje and problemas[0].valor == "Fuel"

"""Normalización de unidades."""

from __future__ import annotations

from decimal import Decimal

import pytest

from esg.indicadores.unidades import UNIDAD_NORMAL, UnidadDesconocida, canonica, normalizar


def test_cada_vector_tiene_su_unidad_de_agregacion() -> None:
    assert UNIDAD_NORMAL == {
        "AGUA": "m3",
        "ELECTRICIDAD": "kWh",
        "GAS": "kWh",
        "RESIDUOS": "kg",
    }


@pytest.mark.parametrize("escrito", ["m3", "M3", "m³", " metros cúbicos ", "mc"])
def test_la_misma_unidad_escrita_de_cinco_formas(escrito: str) -> None:
    assert canonica(escrito) == "m3"


def test_una_unidad_que_no_esta_en_la_tabla_no_se_adivina() -> None:
    with pytest.raises(UnidadDesconocida):
        canonica("MW")


def test_megavatios_hora_a_kilovatios_hora() -> None:
    r = normalizar("ELECTRICIDAD", Decimal("12.5"), "MWh")
    assert r.cantidad == Decimal("12500.0000")
    assert r.unidad == "kWh"


def test_litros_a_metros_cubicos() -> None:
    r = normalizar("AGUA", Decimal("2500"), "litros")
    assert r.cantidad == Decimal("2.5000")


def test_toneladas_a_kilos() -> None:
    r = normalizar("RESIDUOS", Decimal("1.25"), "t")
    assert r.cantidad == Decimal("1250.0000")


def test_el_gas_en_kilovatios_hora_pasa_tal_cual() -> None:
    r = normalizar("GAS", Decimal("4120"), "kWh")
    assert r.cantidad == Decimal("4120.0000")
    assert r.factor == Decimal(1)


def test_el_gas_en_metros_cubicos_sin_poder_calorifico_no_se_convierte() -> None:
    """El caso que justifica que `cantidad_normalizada` pueda ser NULL.

    Inventar 11,63 kWh/m³ para toda España mete un 5 % de error en el vector
    que más pesa. Se prefiere una lectura que no suma y lo dice.
    """
    r = normalizar("GAS", Decimal("380"), "m3")
    assert r.cantidad is None
    assert r.motivo is not None and "poder calorífico" in r.motivo


def test_el_gas_en_metros_cubicos_con_el_factor_de_la_factura() -> None:
    r = normalizar("GAS", Decimal("380"), "m³", factor_gas=Decimal("11.32"))
    assert r.cantidad == Decimal("4301.6000")
    assert r.factor == Decimal("11.32")


def test_una_unidad_desconocida_no_tumba_la_carga_pero_no_suma() -> None:
    r = normalizar("ELECTRICIDAD", Decimal("100"), "vatios")
    assert r.cantidad is None
    assert r.motivo is not None and "vatios" in r.motivo

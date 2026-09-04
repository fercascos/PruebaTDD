"""Reparto de una factura a meses naturales."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from esg.indicadores.reparto import dias_cubiertos, dias_en_mes, meses_entre, repartir


def test_una_factura_de_un_mes_natural_no_se_reparte() -> None:
    r = repartir(date(2025, 3, 1), date(2025, 4, 1), Decimal("4120"))
    assert r == {date(2025, 3, 1): Decimal("4120")}


def test_una_factura_a_caballo_de_dos_meses_se_reparte_por_dias() -> None:
    # 14/03 → 16/04: 18 días de marzo y 15 de abril, 33 en total.
    r = repartir(date(2025, 3, 14), date(2025, 4, 16), Decimal("3300"))
    assert r[date(2025, 3, 1)] == Decimal("1800.0000")
    assert r[date(2025, 4, 1)] == Decimal("1500.0000")


def test_lo_repartido_suma_exactamente_lo_facturado() -> None:
    """El céntimo que no cuadra es el que hace que nadie se fíe de la pantalla."""
    r = repartir(date(2025, 1, 10), date(2025, 5, 3), Decimal("1000"))
    assert sum(r.values()) == Decimal("1000")


def test_un_periodo_de_un_ano_toca_los_doce_meses() -> None:
    meses = meses_entre(date(2025, 1, 1), date(2026, 1, 1))
    assert len(meses) == 12
    assert meses[0] == date(2025, 1, 1)
    assert meses[-1] == date(2025, 12, 1)


def test_febrero_bisiesto() -> None:
    assert dias_en_mes(date(2024, 2, 1), date(2024, 3, 1), date(2024, 2, 1)) == 29


def test_un_periodo_vacio_o_invertido_no_reparte_nada() -> None:
    assert repartir(date(2025, 3, 1), date(2025, 3, 1), Decimal("10")) == {}
    assert repartir(date(2025, 4, 1), date(2025, 3, 1), Decimal("10")) == {}


def test_la_cobertura_cuenta_dias_distintos_aunque_lleguen_solapados() -> None:
    cubiertos = dias_cubiertos(
        [(date(2025, 1, 1), date(2025, 1, 20)), (date(2025, 1, 15), date(2025, 2, 1))],
        date(2025, 1, 1),
        date(2025, 2, 1),
    )
    assert cubiertos == 31


def test_la_cobertura_solo_cuenta_dentro_de_la_ventana() -> None:
    cubiertos = dias_cubiertos(
        [(date(2024, 12, 1), date(2025, 1, 11))], date(2025, 1, 1), date(2025, 2, 1)
    )
    assert cubiertos == 10

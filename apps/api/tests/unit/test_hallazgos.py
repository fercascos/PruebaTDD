"""Ciclo de vida del hallazgo · funciones puras."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tdd.findings.service import (
    EstadoDelHallazgo,
    GuardaDeHallazgoIncumplida,
    HechosDelHallazgo,
    TransicionDeHallazgoNoPermitida,
    comprobar_transicion,
    destinos_posibles,
    sale_en_el_informe,
)

COMPLETO = HechosDelHallazgo(
    tiene_lineas_capex=True,
    importe_total=Decimal("5500.00"),
    tiene_descripcion=True,
    tiene_fotos=True,
    precios_sin_validar=0,
)


def test_el_camino_normal_de_un_hallazgo() -> None:
    comprobar_transicion(EstadoDelHallazgo.BORRADOR, EstadoDelHallazgo.EN_REVISION, COMPLETO)
    comprobar_transicion(EstadoDelHallazgo.EN_REVISION, EstadoDelHallazgo.VALIDADO, COMPLETO)


def test_un_validado_puede_volver_a_revision() -> None:
    """Un revisor que encuentra un error en algo ya validado tiene que poder
    devolverlo, o el flujo obliga a mentir."""
    comprobar_transicion(EstadoDelHallazgo.VALIDADO, EstadoDelHallazgo.EN_REVISION, COMPLETO)


def test_no_se_valida_saltandose_la_revision() -> None:
    with pytest.raises(TransicionDeHallazgoNoPermitida):
        comprobar_transicion(EstadoDelHallazgo.BORRADOR, EstadoDelHallazgo.VALIDADO, COMPLETO)


def test_sin_descripcion_no_pasa_a_revision() -> None:
    """Es lo que lee el revisor: mandarle un título suelto no es revisar."""
    sin_texto = HechosDelHallazgo(tiene_descripcion=False, tiene_lineas_capex=True)
    with pytest.raises(GuardaDeHallazgoIncumplida, match="descripción"):
        comprobar_transicion(EstadoDelHallazgo.BORRADOR, EstadoDelHallazgo.EN_REVISION, sin_texto)


def test_sin_linea_de_capex_no_se_valida() -> None:
    sin_linea = HechosDelHallazgo(tiene_descripcion=True, tiene_lineas_capex=False)
    with pytest.raises(GuardaDeHallazgoIncumplida, match="línea de CAPEX"):
        comprobar_transicion(EstadoDelHallazgo.EN_REVISION, EstadoDelHallazgo.VALIDADO, sin_linea)


def test_una_linea_de_importe_cero_sirve_para_validar() -> None:
    """Un hallazgo sin coste asociado —una observación— es un hallazgo válido.
    Exigir importe positivo obligaría a inventar cifras."""
    sin_coste = HechosDelHallazgo(
        tiene_descripcion=True, tiene_lineas_capex=True, importe_total=Decimal("0")
    )
    comprobar_transicion(EstadoDelHallazgo.EN_REVISION, EstadoDelHallazgo.VALIDADO, sin_coste)


def test_con_precios_sin_validar_no_se_valida() -> None:
    """`[REQ]` Ningún proceso automático valida un precio: si quedan pendientes,
    el hallazgo no puede darse por bueno."""
    pendientes = HechosDelHallazgo(
        tiene_descripcion=True, tiene_lineas_capex=True, precios_sin_validar=3
    )
    with pytest.raises(GuardaDeHallazgoIncumplida, match="3 precios"):
        comprobar_transicion(EstadoDelHallazgo.EN_REVISION, EstadoDelHallazgo.VALIDADO, pendientes)


def test_se_puede_descartar_desde_cualquier_estado_activo() -> None:
    for desde in (
        EstadoDelHallazgo.BORRADOR,
        EstadoDelHallazgo.EN_REVISION,
        EstadoDelHallazgo.VALIDADO,
    ):
        comprobar_transicion(desde, EstadoDelHallazgo.DESCARTADO, COMPLETO)


def test_lo_descartado_puede_recuperarse_como_borrador() -> None:
    comprobar_transicion(EstadoDelHallazgo.DESCARTADO, EstadoDelHallazgo.BORRADOR, COMPLETO)


def test_lo_descartado_no_salta_directo_a_validado() -> None:
    with pytest.raises(TransicionDeHallazgoNoPermitida):
        comprobar_transicion(EstadoDelHallazgo.DESCARTADO, EstadoDelHallazgo.VALIDADO, COMPLETO)


def test_los_destinos_explican_por_que_no_se_puede() -> None:
    """Para que la interfaz muestre el botón deshabilitado **con su motivo** en
    vez de ocultarlo, que es lo que deja al usuario sin saber qué le falta."""
    incompleto = HechosDelHallazgo(tiene_descripcion=True, tiene_lineas_capex=False)
    destinos = destinos_posibles(EstadoDelHallazgo.EN_REVISION, incompleto)
    validado = next(d for d in destinos if d["to"] == "VALIDADO")
    assert validado["allowed"] is False
    assert validado["blockers"]


def test_el_borrador_no_sale_en_el_informe() -> None:
    """Lo que aún se está escribiendo no debe aparecer en un documento que se
    entrega al cliente."""
    assert sale_en_el_informe(EstadoDelHallazgo.BORRADOR) is False
    assert sale_en_el_informe(EstadoDelHallazgo.DESCARTADO) is False
    assert sale_en_el_informe(EstadoDelHallazgo.EN_REVISION) is True
    assert sale_en_el_informe(EstadoDelHallazgo.VALIDADO) is True

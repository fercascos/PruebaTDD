"""El cálculo del panel, entero, sin base de datos."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from esg.indicadores.motor import (
    ActivoParaCalculo,
    LecturaAgregable,
    PuntoEsperado,
    calcular_panel,
)

TORRE = uuid.uuid4()
NAVE = uuid.uuid4()
CARTERA = uuid.uuid4()
LUZ_TORRE = uuid.uuid4()
AGUA_TORRE = uuid.uuid4()
LUZ_NAVE = uuid.uuid4()

ACTIVOS = [
    ActivoParaCalculo(
        id=TORRE,
        cartera_id=CARTERA,
        codigo="A-001",
        nombre="Torre Norte",
        superficie_m2=Decimal("10000"),
        superficie_de_referencia="ALQUILABLE",
    ),
    ActivoParaCalculo(
        id=NAVE,
        cartera_id=CARTERA,
        codigo="A-002",
        nombre="Nave Sur",
        superficie_m2=None,
        superficie_de_referencia="ALQUILABLE",
    ),
]
PUNTOS = [
    PuntoEsperado(id=LUZ_TORRE, activo_id=TORRE, vector="ELECTRICIDAD"),
    PuntoEsperado(id=AGUA_TORRE, activo_id=TORRE, vector="AGUA"),
    PuntoEsperado(id=LUZ_NAVE, activo_id=NAVE, vector="ELECTRICIDAD"),
]


def luz(punto: uuid.UUID, activo: uuid.UUID, inicio: date, fin: date, kwh: str, **kw: object):
    return LecturaAgregable(
        punto_id=punto,
        activo_id=activo,
        cartera_id=CARTERA,
        vector="ELECTRICIDAD",
        inicio=inicio,
        fin=fin,
        cantidad_normalizada=Decimal(kwh) if kwh is not None else None,
        **kw,  # type: ignore[arg-type]
    )


def test_suma_por_vector_y_por_activo() -> None:
    panel = calcular_panel(
        desde=date(2025, 1, 1),
        hasta=date(2025, 4, 1),
        lecturas=[
            luz(LUZ_TORRE, TORRE, date(2025, 1, 1), date(2025, 2, 1), "10000"),
            luz(LUZ_TORRE, TORRE, date(2025, 2, 1), date(2025, 3, 1), "9000"),
            luz(LUZ_NAVE, NAVE, date(2025, 1, 1), date(2025, 2, 1), "4000"),
        ],
        activos=ACTIVOS,
        puntos=PUNTOS,
    )
    assert panel.totales["ELECTRICIDAD"].medido == Decimal("23000")
    assert panel.totales["ELECTRICIDAD"].unidad == "kWh"
    torre = next(f for f in panel.activos if f.activo_id == TORRE)
    assert torre.por_vector["ELECTRICIDAD"].medido == Decimal("19000")


def test_la_serie_mensual_reparte_la_factura_a_caballo() -> None:
    panel = calcular_panel(
        desde=date(2025, 3, 1),
        hasta=date(2025, 5, 1),
        lecturas=[luz(LUZ_TORRE, TORRE, date(2025, 3, 14), date(2025, 4, 16), "3300")],
        activos=ACTIVOS,
        puntos=PUNTOS,
    )
    assert panel.serie[("ELECTRICIDAD", date(2025, 3, 1))] == Decimal("1800.0000")
    assert panel.serie[("ELECTRICIDAD", date(2025, 4, 1))] == Decimal("1500.0000")


def test_una_lectura_que_asoma_por_el_borde_solo_cuenta_por_dentro() -> None:
    """El total de enero no puede depender de qué día facturó la comercializadora."""
    panel = calcular_panel(
        desde=date(2025, 1, 1),
        hasta=date(2025, 2, 1),
        # 20 días de diciembre y 11 de enero: 31 días, 3.100 kWh.
        lecturas=[luz(LUZ_TORRE, TORRE, date(2024, 12, 12), date(2025, 1, 12), "3100")],
        activos=ACTIVOS,
        puntos=PUNTOS,
    )
    assert panel.totales["ELECTRICIDAD"].medido == Decimal("1100.0000")


def test_intensidad_por_metro_cuadrado_y_por_ocupante() -> None:
    panel = calcular_panel(
        desde=date(2025, 1, 1),
        hasta=date(2025, 2, 1),
        lecturas=[luz(LUZ_TORRE, TORRE, date(2025, 1, 1), date(2025, 2, 1), "12000")],
        activos=ACTIVOS,
        puntos=PUNTOS,
        ocupacion={TORRE: Decimal("300")},
    )
    torre = next(f for f in panel.activos if f.activo_id == TORRE)
    assert torre.intensidad_por_m2("ELECTRICIDAD") == Decimal("1.2000")
    assert torre.intensidad_por_ocupante("ELECTRICIDAD") == Decimal("40.0000")
    assert torre.superficie_de_referencia == "ALQUILABLE"


def test_sin_superficie_no_hay_intensidad_y_no_es_cero() -> None:
    """Un cero saldría el primero en el ranking de eficiencia."""
    panel = calcular_panel(
        desde=date(2025, 1, 1),
        hasta=date(2025, 2, 1),
        lecturas=[luz(LUZ_NAVE, NAVE, date(2025, 1, 1), date(2025, 2, 1), "4000")],
        activos=ACTIVOS,
        puntos=PUNTOS,
    )
    nave = next(f for f in panel.activos if f.activo_id == NAVE)
    assert nave.intensidad_por_m2("ELECTRICIDAD") is None
    assert nave.intensidad_por_ocupante("ELECTRICIDAD") is None


def test_lo_estimado_no_se_mezcla_con_lo_medido() -> None:
    panel = calcular_panel(
        desde=date(2025, 1, 1),
        hasta=date(2025, 3, 1),
        lecturas=[
            luz(LUZ_TORRE, TORRE, date(2025, 1, 1), date(2025, 2, 1), "10000"),
            luz(LUZ_TORRE, TORRE, date(2025, 2, 1), date(2025, 3, 1), "9000", calidad="ESTIMADO"),
        ],
        activos=ACTIVOS,
        puntos=PUNTOS,
    )
    total = panel.totales["ELECTRICIDAD"]
    assert total.medido == Decimal("10000")
    assert total.estimado == Decimal("9000")
    assert total.total == Decimal("10000")
    # Y la serie tampoco los mezcla: un escalón que es criterio de carga y no
    # consumo estropea la lectura del gráfico.
    assert ("ELECTRICIDAD", date(2025, 2, 1)) not in panel.serie


def test_una_lectura_sin_normalizar_no_suma_pero_cuenta_como_dato_llegado() -> None:
    panel = calcular_panel(
        desde=date(2025, 1, 1),
        hasta=date(2025, 2, 1),
        lecturas=[
            LecturaAgregable(
                punto_id=LUZ_TORRE,
                activo_id=TORRE,
                cartera_id=CARTERA,
                vector="ELECTRICIDAD",
                inicio=date(2025, 1, 1),
                fin=date(2025, 2, 1),
                cantidad_normalizada=None,
            )
        ],
        activos=ACTIVOS,
        puntos=PUNTOS,
    )
    total = panel.totales["ELECTRICIDAD"]
    assert total.medido == Decimal("0.0000")
    assert total.cobertura.lecturas_sin_normalizar == 1
    assert total.cobertura.dias_con_dato == 31


def test_cobertura_de_un_trimestre_con_un_solo_mes_cargado() -> None:
    panel = calcular_panel(
        desde=date(2025, 1, 1),
        hasta=date(2025, 4, 1),
        lecturas=[luz(LUZ_TORRE, TORRE, date(2025, 1, 1), date(2025, 2, 1), "10000")],
        activos=[ACTIVOS[0]],
        puntos=[PUNTOS[0]],
    )
    cobertura = panel.totales["ELECTRICIDAD"].cobertura
    assert cobertura.dias_esperados == 90
    assert cobertura.dias_con_dato == 31
    assert cobertura.porcentaje == Decimal("34.4")


def test_un_suministro_dado_de_alta_a_mitad_de_ventana_no_hunde_la_cobertura() -> None:
    """Un contador que no existía no deja un agujero: no existía."""
    panel = calcular_panel(
        desde=date(2025, 1, 1),
        hasta=date(2025, 4, 1),
        lecturas=[luz(LUZ_TORRE, TORRE, date(2025, 3, 1), date(2025, 4, 1), "10000")],
        activos=[ACTIVOS[0]],
        puntos=[PuntoEsperado(id=LUZ_TORRE, activo_id=TORRE, vector="ELECTRICIDAD",
                              alta_en=date(2025, 3, 1))],
    )
    cobertura = panel.totales["ELECTRICIDAD"].cobertura
    assert cobertura.dias_esperados == 31
    assert cobertura.porcentaje == Decimal("100.0")


def test_variacion_contra_el_periodo_anterior() -> None:
    panel = calcular_panel(
        desde=date(2025, 2, 1),
        hasta=date(2025, 3, 1),
        lecturas=[luz(LUZ_TORRE, TORRE, date(2025, 2, 1), date(2025, 3, 1), "9000")],
        activos=[ACTIVOS[0]],
        puntos=[PUNTOS[0]],
        lecturas_anteriores=[luz(LUZ_TORRE, TORRE, date(2025, 1, 4), date(2025, 2, 1), "10000")],
    )
    assert panel.variacion("ELECTRICIDAD") == Decimal("-10.0")


def test_sin_periodo_anterior_no_hay_variacion_y_no_es_cero() -> None:
    panel = calcular_panel(
        desde=date(2025, 2, 1),
        hasta=date(2025, 3, 1),
        lecturas=[luz(LUZ_TORRE, TORRE, date(2025, 2, 1), date(2025, 3, 1), "9000")],
        activos=[ACTIVOS[0]],
        puntos=[PUNTOS[0]],
        lecturas_anteriores=[],
    )
    assert panel.variacion("ELECTRICIDAD") is None

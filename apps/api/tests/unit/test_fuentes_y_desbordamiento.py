"""Fuentes corporativas y estimación de desbordamiento."""

from __future__ import annotations

import pytest

from tdd.reporting.fonts import (
    FAMILIAS_REQUERIDAS,
    FuenteNoDisponible,
    cargar,
    comprobar_familias,
    localizar,
)
from tdd.reporting.overflow import capacidad_del_marco, evaluar

_HAY_GOTHAM = localizar("Gotham Light") is not None
solo_con_fuentes = pytest.mark.skipif(
    not _HAY_GOTHAM, reason="Las fuentes corporativas no están instaladas (make fonts-install)"
)


def test_se_declaran_las_seis_familias() -> None:
    assert len(FAMILIAS_REQUERIDAS) == 6
    assert "Gotham Ultra" in FAMILIAS_REQUERIDAS


def test_una_familia_inexistente_no_se_sustituye_en_silencio() -> None:
    """`fc-match` SIEMPRE devuelve algo. Sin la comprobación de nombre, se
    mediría con la fuente equivocada y el aviso sería un número inventado."""
    assert localizar("Tipografía Que No Existe 1234") is None


def test_pedir_una_familia_ausente_falla_con_instrucciones() -> None:
    with pytest.raises(FuenteNoDisponible, match="make fonts-install"):
        cargar("Tipografía Que No Existe 1234")


def test_sin_la_fuente_la_estimacion_lo_declara() -> None:
    """No se mide en silencio: un aviso calculado sobre otra fuente es peor que
    no dar aviso, porque el usuario se fía."""
    cap = capacidad_del_marco(
        ancho_in=8.79, alto_in=5.90, cuerpo_pt=10, familia="Tipografía Que No Existe 1234"
    )
    assert cap.fuente_real is False
    assert "no está instalada" in cap.nota


@solo_con_fuentes
def test_todas_las_familias_corporativas_estan_instaladas() -> None:
    estado = comprobar_familias()
    faltan = [f for f, ok in estado.items() if not ok]
    assert not faltan, f"Faltan: {faltan}"


@solo_con_fuentes
def test_las_metricas_de_gotham_light_son_las_medidas() -> None:
    m = cargar("Gotham Light")
    assert m.upm == 1000
    assert round(m.interlineado_em, 2) == 1.20


@solo_con_fuentes
def test_gotham_ultra_es_mas_ancha_que_light() -> None:
    """Es tipografía de titular: por eso los titulares caben peor."""
    texto = "SISTEMA DE CLIMATIZACIÓN Y VENTILACIÓN"
    assert cargar("Gotham Ultra").ancho_texto_em(texto) > cargar("Gotham Light").ancho_texto_em(
        texto
    )


@solo_con_fuentes
def test_las_familias_cubren_el_espanol() -> None:
    """Un informe en español con una fuente sin `ñ` es un fallo que no debe
    descubrirse en producción."""
    for familia in FAMILIAS_REQUERIDAS:
        m = cargar(familia)
        faltan = [c for c in "áéíóúüñÁÉÍÓÚÑ¿¡€ºª" if ord(c) not in m.anchos]
        assert not faltan, f"«{familia}» no tiene: {''.join(faltan)}"


@solo_con_fuentes
def test_la_capacidad_medida_coincide_con_el_render() -> None:
    """docs/20 §20.2 · El render real ajustó la primera línea en 117 caracteres.

    El motor estima 119: un 1,7 % de desviación. [LIM] El render sustituyó la
    fuente, así que esto valida el método, no el emparejamiento concreto.
    """
    cap = capacidad_del_marco(ancho_in=8.79, alto_in=5.90, cuerpo_pt=10, familia="Gotham Light")
    assert 110 <= cap.caracteres_por_linea <= 130
    assert cap.lineas >= 30
    assert cap.fuente_real is True


@solo_con_fuentes
def test_un_titular_largo_a_24_pt_no_cabe_en_una_linea() -> None:
    """El error que la medición evita: un titular que se descubre partido en la
    revisión del borrador, no antes."""
    cap = capacidad_del_marco(
        ancho_in=8.79,
        alto_in=0.40,
        cuerpo_pt=24,
        familia="Gotham Ultra",
        muestra="SISTEMA DE CLIMATIZACIÓN Y VENTILACIÓN",
    )
    titular = "SISTEMA DE CLIMATIZACIÓN Y VENTILACIÓN: DESCRIPCIÓN Y VALORACIÓN"
    assert len(titular) > cap.caracteres_por_linea


@pytest.mark.parametrize(
    ("longitud", "severidad"),
    [(100, "OK"), (3900, "CERCA"), (9000, "DESBORDA")],
)
def test_los_tres_niveles_de_aviso(longitud: int, severidad: str) -> None:
    cap = capacidad_del_marco(ancho_in=8.79, alto_in=5.90, cuerpo_pt=10, familia="Gotham Light")
    assert evaluar("x" * longitud, cap).severidad == severidad


def test_el_aviso_de_desbordamiento_dice_cuanto_sobra() -> None:
    cap = capacidad_del_marco(ancho_in=2.0, alto_in=1.0, cuerpo_pt=10, familia="Gotham Light")
    aviso = evaluar("x" * 5000, cap)
    assert aviso.severidad == "DESBORDA"
    assert "sobran" in aviso.mensaje

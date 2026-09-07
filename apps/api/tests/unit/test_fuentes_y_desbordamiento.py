"""Las fuentes del informe y la estimación de desbordamiento."""

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

_HAY_FUENTES = localizar("Montserrat Light") is not None
solo_con_fuentes = pytest.mark.skipif(
    not _HAY_FUENTES, reason="Montserrat no está instalada (make fonts-install)"
)


def test_se_declaran_las_seis_familias() -> None:
    assert len(FAMILIAS_REQUERIDAS) == 6
    assert "Montserrat Black" in FAMILIAS_REQUERIDAS


def test_ninguna_familia_del_informe_es_comercial() -> None:
    """`[REQ]` P-39. Gotham se descarta, y con ella el paso manual de montarla
    en el despliegue: si vuelve a colarse una familia que no se puede instalar
    con un paquete, la imagen no la tendrá y el aviso de desbordamiento se
    quedará mudo sin que nadie se entere."""
    assert all(f.startswith("Montserrat") for f in FAMILIAS_REQUERIDAS)


def test_no_se_pide_una_familia_que_montserrat_no_publica() -> None:
    """«Montserrat Bold» **no es una familia**: Regular y Bold viven las dos
    dentro de «Montserrat». Pedirla daría por ausente una fuente instalada, y
    el informe avisaría de que le falta algo que sí tiene."""
    assert "Montserrat Bold" not in FAMILIAS_REQUERIDAS
    assert localizar("Montserrat Bold") is None


@solo_con_fuentes
def test_una_variante_parecida_no_cuela_por_el_nombre() -> None:
    """El mismo paquete trae «Montserrat Alternates», que es otra fuente: otras
    formas y otras anchuras. Con la comparación laxa —«contiene»— pasaba por
    Montserrat y se habría medido con ella."""
    ruta = localizar("Montserrat")
    assert ruta is not None
    assert "alternates" not in ruta.name.lower()


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
def test_las_metricas_del_cuerpo_son_las_medidas() -> None:
    m = cargar("Montserrat Light")
    assert m.upm == 1000
    assert round(m.interlineado_em, 2) == 1.22


@solo_con_fuentes
def test_el_peso_de_titular_es_mas_ancho_que_el_del_cuerpo() -> None:
    """Es tipografía de titular: por eso los titulares caben peor."""
    texto = "SISTEMA DE CLIMATIZACIÓN Y VENTILACIÓN"
    negra = cargar("Montserrat Black").ancho_texto_em(texto)
    clara = cargar("Montserrat Light").ancho_texto_em(texto)
    assert negra > clara


@solo_con_fuentes
def test_el_cuerpo_de_montserrat_cabe_menos_que_el_de_gotham() -> None:
    """`[LIM]` El coste medido del cambio de P-39, escrito donde se ve.

    La diapositiva de sistema daba **4.405 caracteres con Gotham Light** y da
    **4.080 con Montserrat Light**: un 7,4 % menos, porque Montserrat es más
    ancha. El aviso de desbordamiento se recalcula solo —sale de la fuente, no
    de una constante—, pero un texto que antes cabía justo ahora no cabe, y
    esta prueba fija el número para que el día que cambie se sepa.
    """
    cap = capacidad_del_marco(ancho_in=8.79, alto_in=5.90, cuerpo_pt=10, familia="Montserrat Light")
    assert cap.caracteres == 4080
    assert cap.caracteres < 4405


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

    El motor estimaba 119 con Gotham y estima 120 con Montserrat. `[LIM]` Aquel
    render sustituyó la fuente, así que esto valida **el método**, no el
    emparejamiento concreto; el margen de la aserción es el que absorbe un
    cambio de familia como éste.
    """
    cap = capacidad_del_marco(ancho_in=8.79, alto_in=5.90, cuerpo_pt=10, familia="Montserrat Light")
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
        familia="Montserrat Black",
        muestra="SISTEMA DE CLIMATIZACIÓN Y VENTILACIÓN",
    )
    titular = "SISTEMA DE CLIMATIZACIÓN Y VENTILACIÓN: DESCRIPCIÓN Y VALORACIÓN"
    assert len(titular) > cap.caracteres_por_linea


@pytest.mark.parametrize(
    ("longitud", "severidad"),
    [(100, "OK"), (3900, "CERCA"), (9000, "DESBORDA")],
)
def test_los_tres_niveles_de_aviso(longitud: int, severidad: str) -> None:
    cap = capacidad_del_marco(ancho_in=8.79, alto_in=5.90, cuerpo_pt=10, familia="Montserrat Light")
    assert evaluar("x" * longitud, cap).severidad == severidad


def test_el_aviso_de_desbordamiento_dice_cuanto_sobra() -> None:
    cap = capacidad_del_marco(ancho_in=2.0, alto_in=1.0, cuerpo_pt=10, familia="Montserrat Light")
    aviso = evaluar("x" * 5000, cap)
    assert aviso.severidad == "DESBORDA"
    assert "sobran" in aviso.mensaje

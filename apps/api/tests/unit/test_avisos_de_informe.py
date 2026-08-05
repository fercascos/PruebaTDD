"""Avisos previos a la generación `[REQ]` §17.7 · funciones puras.

La prueba que resume el módulo es `test_solo_bloquean_los_cinco_que_producirian
_un_documento_incorrecto`: hay cinco avisos bloqueantes y ni uno más, y eso es
una decisión, no un descuido.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from tdd.reporting.warnings import (
    EstadoDelInforme,
    Severidad,
    evaluar,
    motivos_de_bloqueo,
    puede_generarse,
    resumir,
)


def codigos(estado: EstadoDelInforme) -> set[str]:
    return {a.codigo for a in evaluar(estado)}


def test_un_proyecto_limpio_no_genera_avisos() -> None:
    assert evaluar(EstadoDelInforme()) == []


# ─────────────────────────────────────────────────────────────────────────────
#  Los cinco bloqueantes
# ─────────────────────────────────────────────────────────────────────────────


def test_un_marcador_sin_mapear_bloquea() -> None:
    """Sin esto, el marcador saldría literal en la pantalla del cliente, que es
    la peor forma posible de descubrir el fallo."""
    avisos = evaluar(EstadoDelInforme(marcadores_sin_mapear=("project.reference",)))
    assert avisos[0].codigo == "UNMAPPED_PLACEHOLDER"
    assert avisos[0].bloquea
    assert "project.reference" in avisos[0].mensaje


def test_una_plantilla_sin_analizar_bloquea() -> None:
    assert "MISSING_TEMPLATE" in codigos(EstadoDelInforme(plantilla_analizada=False))


def test_una_expresion_inexistente_bloquea() -> None:
    avisos = evaluar(EstadoDelInforme(expresiones_invalidas=("project.inventado",)))
    assert avisos[0].codigo == "INVALID_MAPPING_EXPRESSION"


def test_una_foto_en_cuarentena_seleccionada_bloquea() -> None:
    assert "PHOTO_QUARANTINED" in codigos(EstadoDelInforme(fotos_no_utilizables=(uuid.uuid4(),)))


def test_una_zona_pendiente_de_revisar_bloquea() -> None:
    """Reclasificar un activo puede dejar hallazgos con una zona que ya no
    aplica. Salir en el informe con una zona imposible es peor que parar."""
    assert "ZONE_REVIEW_PENDING" in codigos(
        EstadoDelInforme(lineas_con_zona_a_revisar=(uuid.uuid4(),))
    )


def test_solo_bloquean_los_cinco_que_producirian_un_documento_incorrecto() -> None:
    """Un generador que se niega a producir nada mientras quede un pie de foto
    vacío convierte cada borrador en una pelea, y la reacción del equipo es
    rellenar con texto de relleno para poder avanzar."""
    todo = EstadoDelInforme(
        marcadores_sin_mapear=("a",),
        expresiones_invalidas=("b",),
        plantilla_analizada=False,
        fotos_no_utilizables=(uuid.uuid4(),),
        lineas_con_zona_a_revisar=(uuid.uuid4(),),
        fotos_sin_activo=(uuid.uuid4(),),
        fotos_sin_pie=(uuid.uuid4(),),
        activos_sin_fotos=(uuid.uuid4(),),
        lineas_con_precio_sin_validar=12,
        importe_sin_validar=Decimal("184300.00"),
        desbordamientos=(("system.description", 0.35),),
        diapositivas_de_tabla=3,
        fuentes_ausentes=("Gotham Book",),
        campos_vacios=("asset.city",),
        solicitudes_pendientes=4,
    )
    bloqueantes = {a.codigo for a in evaluar(todo) if a.bloquea}
    assert bloqueantes == {
        "UNMAPPED_PLACEHOLDER",
        "MISSING_TEMPLATE",
        "INVALID_MAPPING_EXPRESSION",
        "PHOTO_QUARANTINED",
        "ZONE_REVIEW_PENDING",
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Los que informan sin bloquear
# ─────────────────────────────────────────────────────────────────────────────


def test_los_precios_sin_validar_avisan_con_su_importe_y_no_bloquean() -> None:
    """`[REC]` Generar con precios sin validar es legítimo —un borrador interno
    lo es— pero enviarlo al cliente sin darse cuenta es un problema real."""
    avisos = evaluar(
        EstadoDelInforme(lineas_con_precio_sin_validar=12, importe_sin_validar=Decimal("184300.00"))
    )
    aviso = next(a for a in avisos if a.codigo == "UNVALIDATED_PRICES")
    assert aviso.bloquea is False
    assert "12 líneas" in aviso.mensaje
    assert "184,300.00" in aviso.mensaje


def test_un_desbordamiento_pequeno_no_avisa() -> None:
    """Avisar de un 3 % de exceso llenaría la lista de ruido y haría que nadie
    la mirase."""
    assert "TEXT_OVERFLOW" not in codigos(
        EstadoDelInforme(desbordamientos=(("system.description", 0.03),))
    )


def test_un_desbordamiento_grande_si_avisa() -> None:
    avisos = evaluar(EstadoDelInforme(desbordamientos=(("system.description", 0.35),)))
    aviso = next(a for a in avisos if a.codigo == "TEXT_OVERFLOW")
    assert aviso.severidad is Severidad.ALTA
    assert "35%" in aviso.mensaje


def test_una_tabla_que_cabe_no_avisa() -> None:
    assert "TABLE_DOES_NOT_FIT" not in codigos(EstadoDelInforme(diapositivas_de_tabla=1))


def test_una_tabla_partida_avisa_de_en_cuantas() -> None:
    avisos = evaluar(EstadoDelInforme(diapositivas_de_tabla=4))
    assert "4 diapositivas" in next(a.mensaje for a in avisos if a.codigo == "TABLE_DOES_NOT_FIT")


def test_una_fuente_ausente_avisa_sin_bloquear() -> None:
    """El PPTX guarda el NOMBRE de la fuente, así que en un equipo que sí la
    tenga se verá bien. Lo que pierde precisión es la medición aquí."""
    avisos = evaluar(EstadoDelInforme(fuentes_ausentes=("Gotham Book",)))
    aviso = next(a for a in avisos if a.codigo == "FONT_NOT_AVAILABLE")
    assert aviso.bloquea is False
    assert "por nombre" in aviso.mensaje


def test_un_campo_vacio_avisa_de_que_saldra_vacio() -> None:
    """`[REQ]` §17.7 · Se inserta texto vacío, nunca el literal `{{...}}` ni un
    «N/D» inventado."""
    avisos = evaluar(EstadoDelInforme(campos_vacios=("asset.city",)))
    aviso = next(a for a in avisos if a.codigo == "EMPTY_FIELD")
    assert aviso.severidad is Severidad.BAJA
    assert "vacío" in aviso.mensaje


def test_la_documentacion_pendiente_recuerda_declarar_la_limitacion() -> None:
    avisos = evaluar(EstadoDelInforme(solicitudes_pendientes=4))
    assert "limitación" in next(a.mensaje for a in avisos if a.codigo == "PENDING_DOC_REQUESTS")


# ─────────────────────────────────────────────────────────────────────────────
#  Orden y resumen
# ─────────────────────────────────────────────────────────────────────────────


def test_los_bloqueantes_van_primero() -> None:
    """Quien mira la lista tiene que ver antes lo que le impide generar que lo
    que solo debería mirar."""
    avisos = evaluar(
        EstadoDelInforme(
            campos_vacios=("a",),
            fotos_sin_pie=(uuid.uuid4(),),
            marcadores_sin_mapear=("x",),
            diapositivas_de_tabla=3,
        )
    )
    assert avisos[0].severidad is Severidad.BLOQUEANTE
    assert [a.severidad for a in avisos] == sorted(
        [a.severidad for a in avisos], key=lambda s: list(Severidad).index(s)
    )


def test_se_puede_generar_cuando_no_hay_bloqueantes() -> None:
    avisos = evaluar(EstadoDelInforme(lineas_con_precio_sin_validar=5, campos_vacios=("a",)))
    assert puede_generarse(avisos) is True
    assert motivos_de_bloqueo(avisos) == []


def test_no_se_puede_generar_con_un_bloqueante() -> None:
    avisos = evaluar(EstadoDelInforme(marcadores_sin_mapear=("x",)))
    assert puede_generarse(avisos) is False
    assert len(motivos_de_bloqueo(avisos)) == 1


def test_el_resumen_cuenta_por_severidad() -> None:
    avisos = evaluar(
        EstadoDelInforme(
            marcadores_sin_mapear=("a", "b"),
            diapositivas_de_tabla=2,
            campos_vacios=("c",),
        )
    )
    resumen = resumir(avisos)
    assert resumen.total == 4
    assert resumen.bloqueantes == 2
    assert resumen.por_severidad["BLOQUEANTE"] == 2


@pytest.mark.parametrize("cuantos", [1, 5, 20])
def test_cada_foto_problematica_genera_su_propio_aviso(cuantos: int) -> None:
    """Un aviso agregado —«hay 20 fotos sin pie»— no permite ir a arreglarlas."""
    avisos = evaluar(EstadoDelInforme(fotos_sin_pie=tuple(uuid.uuid4() for _ in range(cuantos))))
    assert len(avisos) == cuantos
    assert all(a.entidad_id is not None for a in avisos)

"""Motor de fases: estados derivados y sugeridos."""

from __future__ import annotations

import pytest

from tdd.phases.engine import (
    FASES_DERIVADAS,
    EstadoNoEscribible,
    comprobar_estado_escribible,
    describir_avance,
    estado_derivado,
    estado_sugerido,
)
from tdd.phases.engine import (
    HechosDelProyecto as H,
)
from tdd.phases.engine import (
    PhaseCode as C,
)
from tdd.phases.engine import (
    PhaseStatus as E,
)

# ─────────────────────────────────────────────────────────────────────────────
#  Red Flag / CAPEX · derivado del trabajo real
# ─────────────────────────────────────────────────────────────────────────────


def test_sin_lineas_de_capex_la_fase_esta_pendiente() -> None:
    assert estado_derivado(C.RED_FLAG_CAPEX, H()) is E.PENDIENTE


def test_con_lineas_pero_precios_sin_validar_esta_en_curso() -> None:
    """El caso real: 63 líneas escritas, 12 sin validar. No está terminado."""
    h = H(lineas_capex=63, lineas_con_precio_validado=51)
    assert estado_derivado(C.RED_FLAG_CAPEX, h) is E.EN_CURSO


def test_con_todos_los_precios_validados_esta_completada() -> None:
    h = H(lineas_capex=63, lineas_con_precio_validado=63)
    assert estado_derivado(C.RED_FLAG_CAPEX, h) is E.COMPLETADA


def test_una_sola_linea_sin_validar_impide_completar() -> None:
    """El borde que importa: 62 de 63 no es «hecho»."""
    h = H(lineas_capex=63, lineas_con_precio_validado=62)
    assert estado_derivado(C.RED_FLAG_CAPEX, h) is E.EN_CURSO


# ─────────────────────────────────────────────────────────────────────────────
#  Full Report
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("hechos", "esperado"),
    [
        (H(), E.PENDIENTE),
        (H(versiones_de_informe=2), E.EN_CURSO),
        (H(versiones_de_informe=2, versiones_emitidas=1), E.COMPLETADA),
    ],
)
def test_full_report_sigue_a_las_versiones(hechos: H, esperado: E) -> None:
    assert estado_derivado(C.FULL_REPORT, hechos) is esperado


# ─────────────────────────────────────────────────────────────────────────────
#  Las fases derivadas no se marcan a mano
# ─────────────────────────────────────────────────────────────────────────────


def test_las_dos_fases_derivadas_son_las_documentadas() -> None:
    assert {C.RED_FLAG_CAPEX, C.FULL_REPORT} == FASES_DERIVADAS


@pytest.mark.parametrize("codigo", sorted(FASES_DERIVADAS))
def test_no_se_puede_fijar_a_mano_una_fase_derivada(codigo: C) -> None:
    """[REC] Poder marcar «completada» una fase cuyo trabajo no está hecho da una
    falsa sensación de avance justo donde más cuesta el proyecto."""
    with pytest.raises(EstadoNoEscribible, match="no se puede fijar a mano"):
        comprobar_estado_escribible(codigo)


@pytest.mark.parametrize(
    "codigo",
    [C.SOLICITUD_DOCUMENTACION, C.VDR, C.VISITA, C.QA, C.PRESENTACION_CLIENTE, C.DEFENSA],
)
def test_las_demas_fases_si_se_gestionan_a_mano(codigo: C) -> None:
    comprobar_estado_escribible(codigo)  # no lanza


def test_pedir_el_derivado_de_una_fase_que_no_lo_es_falla() -> None:
    with pytest.raises(ValueError, match="no tiene estado derivado"):
        estado_derivado(C.VISITA, H())


# ─────────────────────────────────────────────────────────────────────────────
#  Estados sugeridos para las fases manuales
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("codigo", "hechos", "esperado"),
    [
        (C.SOLICITUD_DOCUMENTACION, H(), E.PENDIENTE),
        (
            C.SOLICITUD_DOCUMENTACION,
            H(documentos_solicitados=5, documentos_resueltos=4),
            E.EN_CURSO,
        ),
        (
            C.SOLICITUD_DOCUMENTACION,
            H(documentos_solicitados=5, documentos_resueltos=5),
            E.COMPLETADA,
        ),
        (C.VDR, H(), E.PENDIENTE),
        (C.VDR, H(tiene_enlace_vdr=True), E.COMPLETADA),
        (C.VISITA, H(activos=3), E.PENDIENTE),
        (C.VISITA, H(activos=3, visitas_agendadas=3, visitas_realizadas=1), E.EN_CURSO),
        (C.VISITA, H(activos=3, visitas_agendadas=3, visitas_realizadas=3), E.COMPLETADA),
        (C.QA, H(), E.PENDIENTE),
        (C.QA, H(rondas_qa=2, rondas_qa_cerradas=1), E.EN_CURSO),
        (C.QA, H(rondas_qa=2, rondas_qa_cerradas=2), E.COMPLETADA),
        (C.PRESENTACION_CLIENTE, H(), E.PENDIENTE),
        (C.PRESENTACION_CLIENTE, H(eventos_registrados=1), E.COMPLETADA),
    ],
)
def test_estado_sugerido(codigo: C, hechos: H, esperado: E) -> None:
    assert estado_sugerido(codigo, hechos) is esperado


def test_el_sugerido_de_una_fase_derivada_es_su_derivado() -> None:
    h = H(lineas_capex=10, lineas_con_precio_validado=10)
    assert estado_sugerido(C.RED_FLAG_CAPEX, h) is E.COMPLETADA


# ─────────────────────────────────────────────────────────────────────────────
#  El detalle que se muestra en la ficha
# ─────────────────────────────────────────────────────────────────────────────


def test_el_detalle_explica_por_que_la_fase_esta_donde_esta() -> None:
    """[REC] Un estado sin explicación obliga a entrar en la fase para entenderlo."""
    h = H(lineas_capex=63, lineas_con_precio_validado=51)
    avance = describir_avance(C.RED_FLAG_CAPEX, E.EN_CURSO, h)
    assert avance.es_derivado is True
    assert "63 líneas" in avance.detalle
    assert "12 sin precio validado" in avance.detalle


def test_el_detalle_de_visitas_dice_cuantos_activos_faltan() -> None:
    avance = describir_avance(C.VISITA, E.EN_CURSO, H(activos=3, visitas_realizadas=1))
    assert avance.detalle == "1 de 3 activos visitados"
    assert avance.es_derivado is False

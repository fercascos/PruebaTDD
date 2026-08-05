"""Máquina de estados del proyecto y sus guardas."""

from __future__ import annotations

import pytest

from tdd.projects.state_machine import (
    EstadoDelEncargo as Enc,
)
from tdd.projects.state_machine import (
    GuardaIncumplida,
    TransicionNoPermitida,
    destinos_posibles,
    validar_transicion,
)
from tdd.projects.state_machine import (
    ProjectStatus as S,
)

COMPLETO = Enc(
    clientes=1,
    activos=3,
    visitas_agendadas=3,
    visitas_realizadas=3,
    versiones_generadas=1,
    aprobaciones_registradas=1,
    fases_posteriores_completadas=True,
)


# ─────────────────────────────────────────────────────────────────────────────
#  El camino feliz, entero
# ─────────────────────────────────────────────────────────────────────────────


def test_el_recorrido_completo_de_un_encargo() -> None:
    recorrido = [
        S.BORRADOR,
        S.EN_PREPARACION,
        S.VISITA_PROGRAMADA,
        S.VISITA_REALIZADA,
        S.EN_ANALISIS,
        S.EN_REVISION,
        S.INFORME_EMITIDO,
        S.CERRADO,
        S.ARCHIVADO,
    ]
    for actual, destino in zip(recorrido, recorrido[1:], strict=False):
        validar_transicion(actual, destino, COMPLETO)


# ─────────────────────────────────────────────────────────────────────────────
#  Guardas · lo que impiden y cómo lo explican
# ─────────────────────────────────────────────────────────────────────────────


def test_un_proyecto_sin_cliente_ni_activo_no_sale_de_borrador() -> None:
    with pytest.raises(GuardaIncumplida) as e:
        validar_transicion(S.BORRADOR, S.EN_PREPARACION, Enc())
    mensaje = str(e.value)
    assert "sin cliente" in mensaje or "no tiene cliente" in mensaje
    assert "activo" in mensaje


def test_faltando_solo_el_activo_lo_dice_solo_de_el() -> None:
    with pytest.raises(GuardaIncumplida) as e:
        validar_transicion(S.BORRADOR, S.EN_PREPARACION, Enc(clientes=1))
    assert "activo" in str(e.value)
    assert "cliente" not in str(e.value)


def test_no_se_da_por_visitado_si_falta_un_activo() -> None:
    """La guarda que evita el descuido caro: 2 de 3 no es «visitas realizadas»."""
    enc = Enc(clientes=1, activos=3, visitas_agendadas=3, visitas_realizadas=2)
    with pytest.raises(GuardaIncumplida) as e:
        validar_transicion(S.VISITA_PROGRAMADA, S.VISITA_REALIZADA, enc)
    assert "queda 1 activo por visitar" in str(e.value)
    assert "2 de 3" in str(e.value)


def test_no_se_pasa_a_revision_sin_informe_generado() -> None:
    enc = Enc(clientes=1, activos=1, versiones_generadas=0)
    with pytest.raises(GuardaIncumplida, match="ninguna versión de informe"):
        validar_transicion(S.EN_ANALISIS, S.EN_REVISION, enc)


def test_no_se_emite_sin_aprobacion_de_un_revisor() -> None:
    enc = Enc(clientes=1, activos=1, versiones_generadas=1, aprobaciones_registradas=0)
    with pytest.raises(GuardaIncumplida, match="aprobación de un revisor"):
        validar_transicion(S.EN_REVISION, S.INFORME_EMITIDO, enc)


def test_no_se_cierra_con_fases_posteriores_pendientes() -> None:
    enc = Enc(clientes=1, activos=1, fases_posteriores_completadas=False)
    with pytest.raises(GuardaIncumplida, match="fases posteriores"):
        validar_transicion(S.INFORME_EMITIDO, S.CERRADO, enc)


# ─────────────────────────────────────────────────────────────────────────────
#  Transiciones que no existen
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("desde", "hasta"),
    [
        (S.BORRADOR, S.EN_ANALISIS),  # saltarse la preparación y la visita
        (S.BORRADOR, S.INFORME_EMITIDO),
        (S.VISITA_PROGRAMADA, S.ARCHIVADO),  # archivar a mitad de proceso
        (S.CERRADO, S.EN_ANALISIS),
        (S.EN_ANALISIS, S.INFORME_EMITIDO),  # sin pasar por revisión
    ],
)
def test_transiciones_inexistentes(desde: S, hasta: S) -> None:
    with pytest.raises(TransicionNoPermitida):
        validar_transicion(desde, hasta, COMPLETO)


def test_no_se_transiciona_al_mismo_estado() -> None:
    with pytest.raises(TransicionNoPermitida, match="ya está en"):
        validar_transicion(S.EN_ANALISIS, S.EN_ANALISIS, COMPLETO)


def test_el_error_dice_que_destinos_hay() -> None:
    """Un mensaje que enseña el proceso ahorra una consulta al soporte."""
    with pytest.raises(TransicionNoPermitida) as e:
        validar_transicion(S.BORRADOR, S.EN_ANALISIS, COMPLETO)
    assert "EN_PREPARACION" in str(e.value)


def test_el_informe_emitido_se_puede_reabrir_pero_no_modificar() -> None:
    """La reapertura crea una versión nueva; la emitida queda intacta."""
    validar_transicion(S.INFORME_EMITIDO, S.EN_ANALISIS, COMPLETO)


def test_un_borrador_se_puede_descartar() -> None:
    validar_transicion(S.BORRADOR, S.ARCHIVADO, Enc())


# ─────────────────────────────────────────────────────────────────────────────
#  Lo que alimenta los botones de la interfaz
# ─────────────────────────────────────────────────────────────────────────────


def test_los_destinos_posibles_traen_lo_que_falta_en_cada_uno() -> None:
    """[REC] Permite mostrar el botón deshabilitado **con su motivo** en vez de
    ocultarlo: un botón que no está no se puede preguntar por qué no está."""
    enc = Enc(clientes=1, activos=3, visitas_agendadas=3, visitas_realizadas=1)
    destinos = destinos_posibles(S.VISITA_PROGRAMADA, enc)

    assert set(destinos) == {S.VISITA_REALIZADA}
    faltan = destinos[S.VISITA_REALIZADA]
    assert len(faltan) == 1
    assert "quedan 2 activos por visitar" in faltan[0]


def test_cuando_todo_esta_listo_no_falta_nada() -> None:
    destinos = destinos_posibles(S.VISITA_PROGRAMADA, COMPLETO)
    assert destinos[S.VISITA_REALIZADA] == []

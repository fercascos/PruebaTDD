"""Guardas del ciclo de vida de una sugerencia."""

from __future__ import annotations

import uuid

import pytest

from tdd.suggestions.service import (
    PeticionTransicion,
    RespuestaObligatoria,
    TransicionInvalida,
    contexto_es_por_referencia,
    validar_transicion,
)
from tdd.suggestions.service import (
    SuggestionStatus as S,
)

ID = uuid.uuid4()


def _t(a: S, **kw) -> PeticionTransicion:
    return PeticionTransicion(a=a, **kw)


@pytest.mark.parametrize(
    ("desde", "hasta"),
    [
        (S.NUEVA, S.EN_REVISION),
        (S.NUEVA, S.DUPLICADA),
        (S.EN_REVISION, S.ACEPTADA),
        (S.EN_REVISION, S.RECHAZADA),
        (S.ACEPTADA, S.APLICADA),
    ],
)
def test_transiciones_permitidas(desde: S, hasta: S) -> None:
    extra: dict = {}
    if hasta is S.RECHAZADA:
        extra["resolution_note"] = "Ya existe en el agrupador; te enseñamos cómo."
    if hasta is S.DUPLICADA:
        extra["duplicate_of_id"] = uuid.uuid4()
    if hasta is S.APLICADA:
        extra["applied_entity_id"] = uuid.uuid4()
    validar_transicion(desde, _t(hasta, **extra), propia_id=ID)


@pytest.mark.parametrize(
    ("desde", "hasta"),
    [
        (S.NUEVA, S.ACEPTADA),  # hay que revisarla antes
        (S.NUEVA, S.APLICADA),  # no se aplica lo que no se ha aceptado
        (S.ACEPTADA, S.RECHAZADA),  # ya se había aceptado
        (S.RECHAZADA, S.EN_REVISION),
        (S.APLICADA, S.NUEVA),
    ],
)
def test_transiciones_prohibidas(desde: S, hasta: S) -> None:
    with pytest.raises(TransicionInvalida):
        validar_transicion(desde, _t(hasta, applied_entity_id=uuid.uuid4()), propia_id=ID)


def test_rechazar_sin_respuesta_no_se_admite() -> None:
    """La regla que sostiene todo el módulo."""
    with pytest.raises(RespuestaObligatoria, match="explicar por qué"):
        validar_transicion(S.EN_REVISION, _t(S.RECHAZADA), propia_id=ID)


def test_una_respuesta_de_dos_palabras_tampoco_vale() -> None:
    with pytest.raises(RespuestaObligatoria):
        validar_transicion(S.EN_REVISION, _t(S.RECHAZADA, resolution_note="  no  "), propia_id=ID)


def test_duplicada_exige_decir_de_cual() -> None:
    with pytest.raises(TransicionInvalida, match="con cuál se agrupa"):
        validar_transicion(S.NUEVA, _t(S.DUPLICADA), propia_id=ID)


def test_una_sugerencia_no_es_duplicada_de_si_misma() -> None:
    with pytest.raises(TransicionInvalida, match="de sí misma"):
        validar_transicion(S.NUEVA, _t(S.DUPLICADA, duplicate_of_id=ID), propia_id=ID)


def test_aplicar_exige_enlazar_lo_que_se_creo() -> None:
    """Sin ese enlace, «aplicada» sería una afirmación no comprobable."""
    with pytest.raises(TransicionInvalida, match="enlazar"):
        validar_transicion(S.ACEPTADA, _t(S.APLICADA), propia_id=ID)


def test_el_mensaje_de_error_dice_que_transiciones_hay() -> None:
    """Un 422 útil ahorra una consulta al soporte."""
    with pytest.raises(TransicionInvalida) as e:
        validar_transicion(S.NUEVA, _t(S.ACEPTADA), propia_id=ID)
    assert "EN_REVISION" in str(e.value)


def test_los_estados_finales_no_admiten_salida() -> None:
    for final in (S.RECHAZADA, S.DUPLICADA, S.APLICADA):
        with pytest.raises(TransicionInvalida, match="estado final"):
            validar_transicion(final, _t(S.EN_REVISION), propia_id=ID)


# ── Privacidad del contexto ──────────────────────────────────────────────────


def test_el_contexto_por_referencia_se_acepta() -> None:
    assert contexto_es_por_referencia({"price_reference_id": str(uuid.uuid4())})
    assert contexto_es_por_referencia(None)


def test_se_detecta_un_payload_que_copia_datos_del_cliente() -> None:
    """[REC] El buzón no puede ser una vía lateral para sacar datos de un
    proyecto: el contexto va por referencia, no copiado."""
    assert not contexto_es_por_referencia({"client_name": "Inversora Ficticia S.L."})
    assert not contexto_es_por_referencia({"capex_total": "1842500.00"})

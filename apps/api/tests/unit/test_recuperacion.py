"""Recuperación de contraseña · lógica pura `[REQ]` §10.2."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tdd.identity.recuperacion import (
    MAXIMO_POR_VENTANA,
    MINUTOS_DE_VALIDEZ,
    MotivoDeRechazo,
    TokenGuardado,
    TokenRechazado,
    comprobar,
    enlace,
    generar,
    huella_de,
    ip_valida,
    se_debe_enviar,
)

AHORA = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def vivo(**cambios) -> TokenGuardado:
    base = {
        "expira_el": AHORA + timedelta(minutes=10),
        "usado_el": None,
        "cuenta_activa": True,
    }
    return TokenGuardado(**{**base, **cambios})


# ── El token ────────────────────────────────────────────────────────────────


def test_el_token_no_se_repite() -> None:
    assert len({generar(ahora=AHORA).valor for _ in range(200)}) == 200


def test_solo_se_guarda_la_huella() -> None:
    t = generar(ahora=AHORA)
    assert t.huella == huella_de(t.valor)
    assert t.valor not in t.huella


def test_caduca_a_los_treinta_minutos() -> None:
    assert generar(ahora=AHORA).expira_el == AHORA + timedelta(minutes=MINUTOS_DE_VALIDEZ)


def test_el_token_cabe_en_una_url_sin_partirse() -> None:
    valor = generar(ahora=AHORA).valor
    assert valor == valor.strip()
    assert all(c.isalnum() or c in "-_" for c in valor)


# ── Comprobación ────────────────────────────────────────────────────────────


def test_un_token_vivo_pasa() -> None:
    comprobar(vivo(), ahora=AHORA)


def test_un_token_que_no_existe() -> None:
    with pytest.raises(TokenRechazado) as e:
        comprobar(None, ahora=AHORA)
    assert e.value.motivo is MotivoDeRechazo.NO_EXISTE


def test_ya_usado_se_avisa_antes_que_caducado() -> None:
    """A quien pulsó dos veces el mismo enlace le sirve más saber que ya lo
    gastó que enterarse de que además han pasado treinta minutos."""
    gastado_y_viejo = vivo(usado_el=AHORA, expira_el=AHORA - timedelta(minutes=1))
    with pytest.raises(TokenRechazado) as e:
        comprobar(gastado_y_viejo, ahora=AHORA)
    assert e.value.motivo is MotivoDeRechazo.YA_USADO


def test_justo_al_caducar_ya_no_vale() -> None:
    """El límite es cerrado: a los treinta minutos exactos, fuera."""
    with pytest.raises(TokenRechazado) as e:
        comprobar(vivo(expira_el=AHORA), ahora=AHORA)
    assert e.value.motivo is MotivoDeRechazo.CADUCADO


def test_una_cuenta_desactivada_no_puede_restablecer() -> None:
    with pytest.raises(TokenRechazado) as e:
        comprobar(vivo(cuenta_activa=False), ahora=AHORA)
    assert e.value.motivo is MotivoDeRechazo.CUENTA_INACTIVA


@pytest.mark.parametrize("motivo", list(MotivoDeRechazo))
def test_todos_los_rechazos_dicen_qué_hacer(motivo: MotivoDeRechazo) -> None:
    """Un mensaje que solo dice «no válido» deja a alguien mirando la pantalla."""
    texto = str(TokenRechazado(motivo))
    assert texto.strip()
    assert "nuevo" in texto or "administrador" in texto


# ── El enlace ───────────────────────────────────────────────────────────────


def test_el_token_va_en_el_fragmento_y_no_en_la_consulta() -> None:
    """Detrás de `#` no se manda al servidor: no acaba en el registro de acceso
    del proxy ni en la cabecera `Referer`."""
    url = enlace("https://tdd.ejemplo.example", "ABC123")
    assert url == "https://tdd.ejemplo.example/restablecer#ABC123"
    assert "?" not in url


def test_la_barra_de_mas_en_la_base_no_duplica() -> None:
    assert enlace("https://x.example/", "T") == "https://x.example/restablecer#T"


# ── Freno al abuso ──────────────────────────────────────────────────────────


def test_se_deja_de_enviar_al_llegar_al_tope() -> None:
    assert se_debe_enviar(0) is True
    assert se_debe_enviar(MAXIMO_POR_VENTANA - 1) is True
    assert se_debe_enviar(MAXIMO_POR_VENTANA) is False


# ── La IP ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("valor", ["192.0.2.10", "2001:db8::1"])
def test_una_ip_de_verdad_se_conserva(valor: str) -> None:
    assert ip_valida(valor) == valor


@pytest.mark.parametrize("valor", ["testclient", "", None, "no-es-una-ip", "1.2.3"])
def test_lo_que_no_es_una_ip_no_revienta_la_columna_inet(valor: str | None) -> None:
    """Guardar una petición de recuperación no puede fallar porque el proxy de
    delante venga mal configurado."""
    assert ip_valida(valor) == ""

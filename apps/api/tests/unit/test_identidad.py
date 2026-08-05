"""Reglas del inicio de sesión · funciones puras.

El bloqueo por intentos y la caducidad de un token se prueban aquí porque la
hora se recibe como parámetro. Con `datetime.now()` dentro del dominio, probar
que un bloqueo expira a los quince minutos exigiría esperar quince minutos o
parchear el reloj global, que es peor.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tdd.identity.service import (
    INTENTOS_ANTES_DE_BLOQUEAR,
    LONGITUD_MINIMA_DE_CLAVE,
    ClaveDebil,
    CredencialRechazada,
    MotivoDeRechazo,
    SesionGuardada,
    SesionNoValida,
    UsuarioParaLogin,
    castigo_por_fallo,
    comprobar_fortaleza,
    comprobar_que_puede_entrar,
    comprobar_sesion_de_refresco,
    generar_token_de_refresco,
    huella_de,
)

AHORA = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def _usuario(**kwargs: object) -> UsuarioParaLogin:
    base = {
        "id": uuid.uuid4(),
        "organization_id": uuid.uuid4(),
        "password_hash": "$argon2id$...",
        "org_role": "CONSULTOR",
        "can_manage_suggestions": False,
        "is_active": True,
        "failed_login_attempts": 0,
        "locked_until": None,
    }
    return UsuarioParaLogin(**{**base, **kwargs})  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
#  Quién puede entrar
# ─────────────────────────────────────────────────────────────────────────────


def test_con_la_clave_correcta_se_entra() -> None:
    comprobar_que_puede_entrar(_usuario(), clave_correcta=True, ahora=AHORA)


def test_un_correo_desconocido_se_rechaza_como_credencial_invalida() -> None:
    """Y no como «usuario no encontrado»: la diferencia regalaría una lista de
    correos válidos a quien esté probando."""
    with pytest.raises(CredencialRechazada) as exc:
        comprobar_que_puede_entrar(None, clave_correcta=False, ahora=AHORA)
    assert exc.value.motivo is MotivoDeRechazo.CREDENCIAL_INVALIDA


def test_una_clave_incorrecta_se_rechaza() -> None:
    with pytest.raises(CredencialRechazada) as exc:
        comprobar_que_puede_entrar(_usuario(), clave_correcta=False, ahora=AHORA)
    assert exc.value.motivo is MotivoDeRechazo.CREDENCIAL_INVALIDA


def test_una_cuenta_desactivada_no_entra_ni_con_la_clave_buena() -> None:
    with pytest.raises(CredencialRechazada) as exc:
        comprobar_que_puede_entrar(_usuario(is_active=False), clave_correcta=True, ahora=AHORA)
    assert exc.value.motivo is MotivoDeRechazo.CUENTA_DESACTIVADA


def test_el_bloqueo_se_comprueba_antes_que_la_contrasena() -> None:
    """Deliberado: probar contraseñas contra una cuenta bloqueada no debe dar
    ninguna pista sobre si alguna acierta."""
    bloqueado = _usuario(locked_until=AHORA + timedelta(minutes=10))
    with pytest.raises(CredencialRechazada) as exc:
        comprobar_que_puede_entrar(bloqueado, clave_correcta=True, ahora=AHORA)
    assert exc.value.motivo is MotivoDeRechazo.CUENTA_BLOQUEADA
    assert exc.value.segundos_restantes == 600


def test_un_bloqueo_caducado_deja_entrar() -> None:
    """El bloqueo no es permanente: uno que exija al administrador convierte un
    error del usuario en una incidencia, y es trivial de usar para dejar a
    alguien fuera."""
    caducado = _usuario(locked_until=AHORA - timedelta(seconds=1))
    comprobar_que_puede_entrar(caducado, clave_correcta=True, ahora=AHORA)


# ─────────────────────────────────────────────────────────────────────────────
#  Contador de intentos
# ─────────────────────────────────────────────────────────────────────────────


def test_el_primer_fallo_no_bloquea() -> None:
    castigo = castigo_por_fallo(0, ahora=AHORA)
    assert castigo.intentos == 1
    assert castigo.se_ha_bloqueado is False


def test_al_llegar_al_umbral_se_bloquea() -> None:
    castigo = castigo_por_fallo(INTENTOS_ANTES_DE_BLOQUEAR - 1, ahora=AHORA)
    assert castigo.intentos == INTENTOS_ANTES_DE_BLOQUEAR
    assert castigo.bloqueado_hasta == AHORA + timedelta(minutes=15)


def test_seguir_fallando_estando_bloqueado_alarga_el_bloqueo() -> None:
    assert castigo_por_fallo(20, ahora=AHORA).se_ha_bloqueado is True


# ─────────────────────────────────────────────────────────────────────────────
#  Tokens de refresco
# ─────────────────────────────────────────────────────────────────────────────


def test_el_token_nunca_se_guarda_en_claro() -> None:
    """De un token de refresco se guarda **solo su SHA-256**. Una filtración de
    la tabla no permite iniciar sesión como nadie."""
    token = generar_token_de_refresco(ahora=AHORA, dias=14)
    assert token.huella == huella_de(token.valor)
    assert token.valor not in token.huella
    assert len(token.huella) == 64


def test_dos_tokens_seguidos_no_se_parecen() -> None:
    a = generar_token_de_refresco(ahora=AHORA, dias=14)
    b = generar_token_de_refresco(ahora=AHORA, dias=14)
    assert a.valor != b.valor


def _sesion(**kwargs: object) -> SesionGuardada:
    base = {
        "id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "organization_id": uuid.uuid4(),
        "family_id": uuid.uuid4(),
        "expires_at": AHORA + timedelta(days=7),
        "revoked_at": None,
        "org_role": "CONSULTOR",
        "can_manage_suggestions": False,
        "is_active": True,
    }
    return SesionGuardada(**{**base, **kwargs})  # type: ignore[arg-type]


def test_una_sesion_vigente_se_refresca() -> None:
    comprobar_sesion_de_refresco(_sesion(), ahora=AHORA)


def test_un_token_desconocido_no_refresca() -> None:
    with pytest.raises(SesionNoValida):
        comprobar_sesion_de_refresco(None, ahora=AHORA)


def test_un_token_caducado_no_refresca() -> None:
    with pytest.raises(SesionNoValida, match="caducado"):
        comprobar_sesion_de_refresco(_sesion(expires_at=AHORA), ahora=AHORA)


def test_reutilizar_un_token_ya_rotado_revoca_la_familia() -> None:
    """La protección que de verdad importa. Si un token ya rotado vuelve a
    aparecer, alguien guardó una copia. Como el legítimo y el ladrón son
    indistinguibles desde aquí, salen los dos."""
    with pytest.raises(SesionNoValida) as exc:
        comprobar_sesion_de_refresco(_sesion(revoked_at=AHORA), ahora=AHORA)
    assert exc.value.revocar_familia is True


def test_una_cuenta_desactivada_no_puede_refrescar() -> None:
    """Desactivar a alguien debe echarlo, no dejarlo dentro hasta que caduque
    su token de catorce días."""
    with pytest.raises(SesionNoValida, match="desactivada"):
        comprobar_sesion_de_refresco(_sesion(is_active=False), ahora=AHORA)


# ─────────────────────────────────────────────────────────────────────────────
#  Fortaleza de la contraseña
# ─────────────────────────────────────────────────────────────────────────────


def test_una_contrasena_larga_vale() -> None:
    """`[REC]` Longitud por encima de composición: es lo que recomienda el NIST
    desde 2017 y lo que de verdad resiste."""
    comprobar_fortaleza("cubierta invertida con lucernarios")


def test_una_contrasena_corta_no_vale() -> None:
    with pytest.raises(ClaveDebil, match=str(LONGITUD_MINIMA_DE_CLAVE)):
        comprobar_fortaleza("corta1234")


def test_la_contrasena_no_puede_contener_la_cuenta() -> None:
    with pytest.raises(ClaveDebil, match="nombre de la cuenta"):
        comprobar_fortaleza("consultor-alfa-2026", email="consultor@alfa.example")


def test_repetir_el_mismo_caracter_no_cuela() -> None:
    with pytest.raises(ClaveDebil, match="repite"):
        comprobar_fortaleza("aaaaaaaaaaaaaaaa")

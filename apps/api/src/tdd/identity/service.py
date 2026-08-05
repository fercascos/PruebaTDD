"""Reglas del inicio de sesión · **funciones puras**.

Todo lo que decide *si* alguien entra está aquí, sin base de datos y sin reloj
propio: la hora se recibe. Eso permite probar el bloqueo por intentos y la
caducidad de un token sin esperar treinta minutos.

Tres reglas gobiernan el módulo, y las tres protegen a personas reales:

1. **El error de inicio de sesión no distingue causas.** «Correo o contraseña
   incorrectos» y nada más. Decir «ese correo no existe» regala una lista de
   usuarios válidos a quien esté probando.
2. **El contador de intentos vive en la base de datos**, no en memoria:
   reiniciar el proceso no puede regalar intentos.
3. **Reutilizar un token de refresco ya rotado revoca la familia entera.** Es
   la señal de que alguien copió el token, y no hay forma de saber cuál de los
   dos extremos es el legítimo, así que salen los dos.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

#: `[SUP]` Intentos antes de bloquear. Cinco es el equilibrio habitual: absorbe
#: los errores de mecanografía sin dejar sitio a la fuerza bruta.
INTENTOS_ANTES_DE_BLOQUEAR = 5

#: `[SUP]` Duración del bloqueo. No es permanente a propósito: un bloqueo que
#: exige intervención del administrador convierte un error del usuario en una
#: incidencia, y es trivial de usar para dejar a alguien fuera.
MINUTOS_DE_BLOQUEO = 15

#: Longitud en bytes del token de refresco antes de codificar.
BYTES_DEL_TOKEN = 32


class MotivoDeRechazo(StrEnum):
    CREDENCIAL_INVALIDA = "CREDENCIAL_INVALIDA"
    CUENTA_BLOQUEADA = "CUENTA_BLOQUEADA"
    CUENTA_DESACTIVADA = "CUENTA_DESACTIVADA"


class MotivoDeRevocacion(StrEnum):
    ROTADA = "ROTADA"
    CIERRE_DE_SESION = "CIERRE_DE_SESION"
    REUTILIZACION = "REUTILIZACION"
    CAMBIO_DE_CLAVE = "CAMBIO_DE_CLAVE"


class CredencialRechazada(Exception):  # noqa: N818 — el dominio está en español
    """El inicio de sesión no procede. El motivo es para el registro, no para
    el usuario: al usuario se le devuelve siempre el mismo mensaje."""

    def __init__(self, motivo: MotivoDeRechazo, *, segundos_restantes: int = 0) -> None:
        super().__init__(motivo.value)
        self.motivo = motivo
        self.segundos_restantes = segundos_restantes


class SesionNoValida(Exception):  # noqa: N818
    """El token de refresco no sirve: caducado, revocado o desconocido."""

    def __init__(self, motivo: str, *, revocar_familia: bool = False) -> None:
        super().__init__(motivo)
        self.motivo = motivo
        self.revocar_familia = revocar_familia


@dataclass(frozen=True, slots=True)
class UsuarioParaLogin:
    """Lo que la base devuelve al buscar por correo, antes de comprobar nada."""

    id: uuid.UUID
    organization_id: uuid.UUID
    password_hash: str
    org_role: str
    can_manage_suggestions: bool
    is_active: bool
    failed_login_attempts: int
    locked_until: datetime | None


@dataclass(frozen=True, slots=True)
class TokenDeRefresco:
    """El token en claro y su huella. **La huella es lo único que se guarda.**"""

    valor: str
    huella: str
    expira_el: datetime


def generar_token_de_refresco(*, ahora: datetime, dias: int) -> TokenDeRefresco:
    valor = secrets.token_urlsafe(BYTES_DEL_TOKEN)
    return TokenDeRefresco(
        valor=valor, huella=huella_de(valor), expira_el=ahora + timedelta(days=dias)
    )


def huella_de(token: str) -> str:
    """SHA-256 del token. Sin sal y sin coste a propósito: el token ya son 256
    bits aleatorios, así que no hay diccionario que aplicar y sí hace falta
    poder buscarlo por igualdad en un índice."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def comprobar_que_puede_entrar(
    usuario: UsuarioParaLogin | None, *, clave_correcta: bool, ahora: datetime
) -> None:
    """Aplica las guardas en el orden en que importan. No devuelve nada: o pasa
    o lanza.

    El orden no es casual. El bloqueo se comprueba **antes** que la contraseña
    para que probar contraseñas contra una cuenta bloqueada no dé ninguna
    información sobre si alguna acierta.
    """
    if usuario is None:
        # Nunca se llega aquí con `clave_correcta=True`: el llamante debe hacer
        # igualmente una verificación falsa para que el tiempo de respuesta no
        # delate si el correo existe.
        raise CredencialRechazada(MotivoDeRechazo.CREDENCIAL_INVALIDA)
    if usuario.locked_until is not None and usuario.locked_until > ahora:
        raise CredencialRechazada(
            MotivoDeRechazo.CUENTA_BLOQUEADA,
            segundos_restantes=int((usuario.locked_until - ahora).total_seconds()),
        )
    if not usuario.is_active:
        raise CredencialRechazada(MotivoDeRechazo.CUENTA_DESACTIVADA)
    if not clave_correcta:
        raise CredencialRechazada(MotivoDeRechazo.CREDENCIAL_INVALIDA)


@dataclass(frozen=True, slots=True)
class CastigoPorFallo:
    intentos: int
    bloqueado_hasta: datetime | None

    @property
    def se_ha_bloqueado(self) -> bool:
        return self.bloqueado_hasta is not None


def castigo_por_fallo(
    intentos_previos: int,
    *,
    ahora: datetime,
    umbral: int = INTENTOS_ANTES_DE_BLOQUEAR,
    minutos: int = MINUTOS_DE_BLOQUEO,
) -> CastigoPorFallo:
    intentos = intentos_previos + 1
    if intentos >= umbral:
        return CastigoPorFallo(
            intentos=intentos, bloqueado_hasta=ahora + timedelta(minutes=minutos)
        )
    return CastigoPorFallo(intentos=intentos, bloqueado_hasta=None)


@dataclass(frozen=True, slots=True)
class SesionGuardada:
    """La fila de `user_session` tal como interesa a este módulo."""

    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    family_id: uuid.UUID
    expires_at: datetime
    revoked_at: datetime | None
    org_role: str
    can_manage_suggestions: bool
    is_active: bool


def comprobar_sesion_de_refresco(sesion: SesionGuardada | None, *, ahora: datetime) -> None:
    """Valida el token de refresco presentado.

    El caso interesante es el tercero: una sesión **ya revocada** que vuelve a
    presentarse. Eso solo ocurre si alguien guardó una copia del token antes de
    rotarlo. Como el legítimo y el ladrón son indistinguibles desde aquí, se
    corta la familia entera y ambos vuelven a iniciar sesión.
    """
    if sesion is None:
        raise SesionNoValida("Token de refresco desconocido")
    if not sesion.is_active:
        raise SesionNoValida("La cuenta está desactivada")
    if sesion.revoked_at is not None:
        raise SesionNoValida("Token de refresco ya utilizado", revocar_familia=True)
    if sesion.expires_at <= ahora:
        raise SesionNoValida("Token de refresco caducado")


#: `[REC]` Mínimos de la contraseña. Longitud por encima de composición: es lo
#: que recomienda el NIST desde 2017 y lo que de verdad resiste.
LONGITUD_MINIMA_DE_CLAVE = 12


class ClaveDebil(Exception):  # noqa: N818
    """La contraseña no cumple los mínimos."""


def comprobar_fortaleza(clave: str, *, email: str = "") -> None:
    if len(clave) < LONGITUD_MINIMA_DE_CLAVE:
        raise ClaveDebil(f"La contraseña debe tener al menos {LONGITUD_MINIMA_DE_CLAVE} caracteres")
    if email and email.split("@")[0].lower() in clave.lower():
        raise ClaveDebil("La contraseña no puede contener el nombre de la cuenta")
    if len(set(clave)) < 5:
        raise ClaveDebil("La contraseña repite demasiado los mismos caracteres")


def ahora_utc() -> datetime:
    return datetime.now(UTC)

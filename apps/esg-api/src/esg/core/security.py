"""Verificación de tokens.

Dos modos, y la diferencia entre ellos importa:

* `entra`  — el token lo emite Azure (Entra ID) y se verifica con **firma
  asimétrica** contra el juego de claves públicas del directorio. Esta
  aplicación no puede emitir uno: no tiene la clave privada. Es lo que se
  quiere en producción.
* `local`  — tokens HS256 firmados por esta misma aplicación, para desarrollo y
  para la suite. La configuración impide usarlo fuera de local.

En los dos casos se comprueban emisor, destinatario y caducidad. Un token
válido **de otra aplicación del mismo directorio** no entra aquí: eso es lo que
hace la comprobación del `aud`, y es la que más fácil se olvida.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient

from esg.core.config import Settings


class TokenInvalido(Exception):
    """El token no es de fiar. **Sin decir por qué**: distinguir «caducado» de
    «firma inválida» le regala información a quien esté probando tokens."""


@dataclass(frozen=True, slots=True)
class Identidad:
    """Lo que el proveedor afirma de quien llama. Todavía no es un usuario
    nuestro: emparejar esto con una fila de `usuario` es otro paso, y a
    propósito."""

    emisor: str
    sujeto: str
    email: str
    nombre: str


class VerificadorLocal:
    """HS256 con el secreto de la aplicación. Solo desarrollo y pruebas."""

    def __init__(self, *, secreto: str, emisor: str = "esg-local", audiencia: str = "esg-api"):
        self._secreto = secreto
        self._emisor = emisor
        self._audiencia = audiencia

    def verificar(self, token: str) -> Identidad:
        try:
            datos: dict[str, Any] = jwt.decode(
                token,
                self._secreto,
                algorithms=["HS256"],
                audience=self._audiencia,
                issuer=self._emisor,
            )
        except jwt.PyJWTError as exc:
            raise TokenInvalido from exc
        return _identidad_desde(datos)


class VerificadorEntra:
    """RS256 contra el JWKS del directorio de Azure.

    El juego de claves se guarda `ttl` segundos. Azure las rota sin avisar: sin
    caché es un viaje de red por petición, y con caché eterna la rotación deja
    fuera a toda la organización a la vez.
    """

    def __init__(
        self,
        *,
        jwks_url: str,
        emisor: str,
        audiencia: str,
        ttl: int = 3600,
        leeway: int = 60,
    ):
        self._cliente = PyJWKClient(jwks_url, cache_keys=True, lifespan=ttl)
        self._emisor = emisor
        self._audiencia = audiencia
        self._leeway = leeway

    def verificar(self, token: str) -> Identidad:
        try:
            clave = self._cliente.get_signing_key_from_jwt(token).key
            datos: dict[str, Any] = jwt.decode(
                token,
                clave,
                # Solo RS256. Sin lista explícita, un token con `alg: none` o
                # firmado con HMAC usando la clave pública como secreto pasaría
                # la verificación: es el ataque clásico contra JWT.
                algorithms=["RS256"],
                audience=self._audiencia,
                issuer=self._emisor,
                leeway=self._leeway,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except Exception as exc:  # PyJWKClientError no hereda de PyJWTError
            raise TokenInvalido from exc
        return _identidad_desde(datos)


def _identidad_desde(datos: dict[str, Any]) -> Identidad:
    """`oid` antes que `sub`, y esto tiene consecuencias.

    En Entra ID el `sub` es **distinto por aplicación** para el mismo usuario:
    emparejar por `sub` significa que la misma persona sería dos usuarios si
    mañana hay una segunda aplicación. El `oid` es el identificador del objeto
    en el directorio y es el mismo en todas.
    """
    sujeto = str(datos.get("oid") or datos.get("sub") or "")
    if not sujeto:
        raise TokenInvalido("El token no identifica a nadie")
    correo = str(datos.get("email") or datos.get("preferred_username") or "")
    return Identidad(
        emisor=str(datos.get("iss", "")),
        sujeto=sujeto,
        email=correo.lower(),
        nombre=str(datos.get("name") or correo or sujeto),
    )


def construir_verificador(settings: Settings) -> VerificadorLocal | VerificadorEntra:
    if settings.auth_mode == "entra":
        return VerificadorEntra(
            jwks_url=settings.jwks_url,
            emisor=settings.emisor_esperado,
            audiencia=settings.azure_client_id,
            ttl=settings.azure_jwks_ttl_seconds,
            leeway=settings.token_leeway_seconds,
        )
    return VerificadorLocal(secreto=settings.app_secret_key)


def emitir_token_local(
    *, secreto: str, sujeto: str, email: str, nombre: str, ttl_minutos: int = 60
) -> str:
    """Token de desarrollo. Existe para poder recorrer la aplicación sin un
    directorio de Azure delante; en producción no hay ninguna ruta que lo
    llame, porque `AUTH_MODE=local` no arranca fuera de local."""
    ahora = int(time.time())
    return jwt.encode(
        {
            "iss": "esg-local",
            "aud": "esg-api",
            "sub": sujeto,
            "oid": sujeto,
            "email": email,
            "name": nombre,
            "iat": ahora,
            "exp": ahora + ttl_minutos * 60,
        },
        secreto,
        algorithm="HS256",
    )


def descubrir_configuracion_oidc(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    """Lee el documento de descubrimiento de un emisor OIDC.

    Se usa desde `tools/`, no desde la petición: el arranque no debe depender
    de que Azure conteste.
    """
    with urllib.request.urlopen(url, timeout=timeout) as respuesta:  # noqa: S310
        datos: dict[str, Any] = json.loads(respuesta.read())
    return datos

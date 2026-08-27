"""Contraseñas y tokens.

No hay ni un secreto en este fichero: todo viene de la configuración.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Argon2id con los parámetros recomendados por OWASP para aplicaciones web.
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def hash_password(clave: str) -> str:
    return _hasher.hash(clave)


def verify_password(clave: str, hash_guardado: str) -> bool:
    try:
        _hasher.verify(hash_guardado, clave)
    except VerifyMismatchError:
        return False
    except Exception:
        # Un hash corrupto o de otro algoritmo no debe tumbar el login: se
        # trata como credencial inválida y el fallo se registra aparte.
        return False
    return True


def necesita_rehash(hash_guardado: str) -> bool:
    """Los parámetros de Argon2 suben con el tiempo; rehashear al iniciar
    sesión mantiene el coste al día sin pedirle nada al usuario."""
    return _hasher.check_needs_rehash(hash_guardado)


def crear_token(
    *,
    secreto: str,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    org_role: str,
    can_manage_suggestions: bool,
    ttl_minutos: int,
) -> str:
    ahora = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org": str(organization_id),
        "role": org_role,
        "sug": can_manage_suggestions,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=ttl_minutos),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, secreto, algorithm="HS256")


def leer_token(token: str, *, secreto: str) -> dict[str, Any]:
    """Descodifica y **valida** el token. Lanza `jwt.PyJWTError` si no es válido."""
    datos: dict[str, Any] = jwt.decode(token, secreto, algorithms=["HS256"])
    return datos

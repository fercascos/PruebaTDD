"""Dependencias de FastAPI: quién eres y con qué contexto se abre la sesión."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from tdd.core.config import Settings, get_settings
from tdd.core.db import ContextoRLS, aplicar_contexto
from tdd.core.security import leer_token

esquema_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class UsuarioActual:
    id: uuid.UUID
    organization_id: uuid.UUID
    org_role: str
    can_manage_suggestions: bool


def obtener_usuario(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UsuarioActual:
    if credenciales is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta la credencial")
    try:
        datos = leer_token(credenciales.credentials, secreto=settings.app_secret_key)
    except jwt.PyJWTError as exc:
        # Mensaje genérico a propósito: distinguir «caducado» de «firma inválida»
        # da información gratis a quien esté probando tokens.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credencial no válida") from exc
    return UsuarioActual(
        id=uuid.UUID(datos["sub"]),
        organization_id=uuid.UUID(datos["org"]),
        org_role=datos["role"],
        can_manage_suggestions=bool(datos.get("sug", False)),
    )


def obtener_sesion(
    request: Request,
    usuario: Annotated[UsuarioActual, Depends(obtener_usuario)],
) -> Iterator[Session]:
    """Abre la sesión **con el contexto RLS ya aplicado**.

    Es el único punto por el que las rutas obtienen una sesión. Así no hay forma
    de consultar sin contexto: y si la hubiera, la RLS no devolvería nada, que es
    el fallo seguro que se busca.
    """
    factory = request.app.state.session_factory
    session: Session = factory()
    try:
        session.begin()
        aplicar_contexto(
            session,
            ContextoRLS(
                organization_id=usuario.organization_id,
                user_id=usuario.id,
                can_manage_suggestions=usuario.can_manage_suggestions,
            ),
        )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def exigir_gestion_de_sugerencias(
    usuario: Annotated[UsuarioActual, Depends(obtener_usuario)],
) -> UsuarioActual:
    """`[REQ]` Solo el administrador ve la bandeja completa.

    La RLS ya lo impide a nivel de fila; esto devuelve un `403` claro en vez de
    una lista vacía, que resultaría desconcertante.
    """
    if not (usuario.org_role == "ADMIN" or usuario.can_manage_suggestions):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Solo un administrador puede ver las propuestas de otros usuarios",
        )
    return usuario


SesionDep = Annotated[Session, Depends(obtener_sesion)]
UsuarioDep = Annotated[UsuarioActual, Depends(obtener_usuario)]
GestorSugerenciasDep = Annotated[UsuarioActual, Depends(exigir_gestion_de_sugerencias)]

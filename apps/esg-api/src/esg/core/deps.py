"""Dependencias de FastAPI: quién eres y con qué contexto se abre la sesión."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from esg.core.config import Settings, get_settings
from esg.core.db import ContextoRLS, aplicar_contexto
from esg.core.security import TokenInvalido
from esg.identidad.service import UsuarioActual, UsuarioDesconocido, emparejar

esquema_bearer = HTTPBearer(auto_error=False)


def obtener_usuario(
    request: Request,
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
) -> UsuarioActual:
    """Verifica el token y lo empareja con una ficha de usuario.

    Abre **su propia** transacción, corta y sin contexto de organización, y la
    cierra antes de que empiece la de la petición. No es un descuido: mientras
    dura el emparejamiento están fijadas las variables `app.login_*`, y no
    deben seguir puestas durante el trabajo de verdad.
    """
    if credenciales is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta la credencial")
    try:
        identidad = request.app.state.verificador.verificar(credenciales.credentials)
    except TokenInvalido as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credencial no válida") from exc

    fabrica: sessionmaker[Session] = request.app.state.session_factory
    session = fabrica()
    try:
        session.begin()
        usuario = emparejar(session, identidad)
        session.commit()
    except UsuarioDesconocido as exc:
        session.rollback()
        # 403 y no 401: la credencial es buena, lo que falta es la invitación.
        # Un 401 haría que el navegador volviera a Azure una y otra vez.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Su identidad es válida pero no tiene acceso a esta aplicación. "
            "Pida a un administrador que le dé de alta.",
        ) from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return usuario


def obtener_sesion(
    request: Request,
    usuario: Annotated[UsuarioActual, Depends(obtener_usuario)],
) -> Iterator[Session]:
    """La única puerta por la que las rutas obtienen una sesión.

    Sale con el contexto RLS aplicado. Si alguien consiguiera otra sin
    contexto, no vería nada: es el fallo seguro, no una segunda barrera.
    """
    fabrica: sessionmaker[Session] = request.app.state.session_factory
    session = fabrica()
    try:
        session.begin()
        aplicar_contexto(
            session,
            ContextoRLS(
                organizacion_id=usuario.organizacion_id,
                usuario_id=usuario.id,
                permisos=usuario.permisos,
            ),
        )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def exigir_escritura_de_datos(
    usuario: Annotated[UsuarioActual, Depends(obtener_usuario)],
) -> UsuarioActual:
    """403 con motivo en vez del 500 que devolvería la RLS al rechazar la fila."""
    if not usuario.permisos.escribe_datos:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Su rol no permite cargar datos de consumo"
        )
    return usuario


def exigir_escritura_de_estructura(
    usuario: Annotated[UsuarioActual, Depends(obtener_usuario)],
) -> UsuarioActual:
    if not usuario.permisos.escribe_estructura:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Su rol no permite modificar carteras, activos ni usuarios"
        )
    return usuario


#: `scope="function"`, igual que en `apps/api`, y por la misma razón: el
#: `commit` de `obtener_sesion` va después del `yield`, y con el ámbito por
#: defecto se ejecutaría **con la respuesta ya enviada**. Quien recibe un 201 y
#: pide ese identificador acto seguido podría no encontrarlo, y un `COMMIT` que
#: falle dejaría al cliente con un 201 de algo que se deshizo.
SesionDep = Annotated[Session, Depends(obtener_sesion, scope="function")]
UsuarioDep = Annotated[UsuarioActual, Depends(obtener_usuario)]
EscrituraDatosDep = Annotated[UsuarioActual, Depends(exigir_escritura_de_datos)]
EscrituraEstructuraDep = Annotated[UsuarioActual, Depends(exigir_escritura_de_estructura)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

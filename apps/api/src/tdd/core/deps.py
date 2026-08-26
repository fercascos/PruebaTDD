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
    #: La marca explícita de la ficha del usuario. **No es el permiso efectivo**:
    #: para eso está `gestiona_sugerencias`.
    can_manage_suggestions: bool

    @property
    def gestiona_sugerencias(self) -> bool:
        """`[REQ]` El permiso **efectivo** sobre el buzón de sugerencias.

        Un ADMIN lo atiende por definición: P-41 hizo el permiso separable para
        que alguien pueda atenderlo **sin** ser administrador, no para que un
        administrador se quede fuera.

        Vive aquí y no repartido por los endpoints porque **este mismo valor es
        el que se pasa a la RLS**. Cuando estaban en dos sitios, la API dejaba
        pasar a un ADMIN sin la marca y la base de datos le bloqueaba la
        escritura: el resultado era un 500 en vez de un permiso claro.
        """
        return self.org_role == "ADMIN" or self.can_manage_suggestions


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

    El `commit` de abajo va después del `yield`, así que **cuándo** se ejecuta lo
    decide FastAPI, no este módulo: por eso `SesionDep` la pide con
    `scope="function"`. Ver allí; el detalle importa más de lo que parece.
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
                # El permiso EFECTIVO, no la marca de la ficha: es lo que
                # leen las políticas RLS, y tiene que decir lo mismo que la
                # comprobación de la API o se producen 500 en vez de 403.
                can_manage_suggestions=usuario.gestiona_sugerencias,
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
    if not usuario.gestiona_sugerencias:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Solo un administrador puede ver las propuestas de otros usuarios",
        )
    return usuario


#: `[REQ]` `scope="function"` y no el valor por defecto, y esto no es un detalle
#: de estilo: decide **si la transacción está confirmada cuando el cliente
#: recibe la respuesta**.
#:
#: FastAPI mantiene dos pilas de salida por petición. La de `scope="request"`
#: —la de siempre— se cierra *después* de haber enviado la respuesta; la de
#: `scope="function"` se cierra en cuanto la ruta devuelve, *antes* de enviarla.
#: Como el `commit` de `obtener_sesion` va después del `yield`, con la pila por
#: defecto se confirmaba con la respuesta ya en el cable, y eso dejaba dos
#: agujeros reales:
#:
#:   · Quien recibía un `201` y pedía ese identificador acto seguido podía no
#:     encontrarlo. Salió sembrando el encargo de demostración, no de la suite.
#:   · Y si el `COMMIT` fallaba —interbloqueo, disco lleno—, el cliente ya tenía
#:     su `201` de algo que se deshizo, sin enterarse jamás.
#:
#: Los dos quedan fijados en `test_confirmacion_antes_de_responder.py`, que mide
#: el orden con una sonda ASGI en vez de encadenar dos peticiones y confiar.
#:
#: `[LIM]` Con una versión de FastAPI anterior a la que introdujo los ámbitos,
#: esto revienta al importar con un `TypeError`. Es lo que se quiere: volver en
#: silencio al comportamiento anterior sería reintroducir el fallo sin avisar.
SesionDep = Annotated[Session, Depends(obtener_sesion, scope="function")]
UsuarioDep = Annotated[UsuarioActual, Depends(obtener_usuario)]
GestorSugerenciasDep = Annotated[UsuarioActual, Depends(exigir_gestion_de_sugerencias)]


#: La configuración como dependencia. Vivía en `identity/router.py`, que no es
#: su sitio: la usan también las fotografías para el plazo de las URL firmadas.
SettingsDep = Annotated[Settings, Depends(get_settings)]

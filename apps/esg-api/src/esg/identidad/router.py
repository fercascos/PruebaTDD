"""Quién soy, quién tiene acceso y qué ve cada uno."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from esg.core.deps import EscrituraEstructuraDep, SesionDep, UsuarioDep
from esg.core.errores import NO_PROCESABLE
from esg.identidad.permisos import ROLES

router = APIRouter(prefix="/api/v1", tags=["identidad"])


class Yo(BaseModel):
    id: uuid.UUID
    email: str
    nombre: str
    rol: str
    organizacion_id: uuid.UUID
    organizacion: str
    ve_todo: bool
    escribe_datos: bool
    escribe_estructura: bool


@router.get("/yo", response_model=Yo)
def quien_soy(sesion: SesionDep, usuario: UsuarioDep) -> Yo:
    """Lo primero que pide la interfaz: con esto decide qué botones enseña.

    Los permisos se devuelven calculados, no deducidos del rol en el navegador:
    la lista de roles con permiso vive en un solo sitio, y el frontend no es
    ese sitio.
    """
    organizacion = sesion.execute(
        text("SELECT nombre FROM organizacion WHERE id = :id"),
        {"id": usuario.organizacion_id},
    ).scalar_one()
    permisos = usuario.permisos
    return Yo(
        id=usuario.id,
        email=usuario.email,
        nombre=usuario.nombre,
        rol=usuario.rol,
        organizacion_id=usuario.organizacion_id,
        organizacion=organizacion,
        ve_todo=permisos.ve_todo,
        escribe_datos=permisos.escribe_datos,
        escribe_estructura=permisos.escribe_estructura,
    )


class NuevoUsuario(BaseModel):
    email: EmailStr
    nombre: str
    rol: str = "LECTOR"


class UsuarioFuera(BaseModel):
    id: uuid.UUID
    email: str
    nombre: str
    rol: str
    activo: bool
    #: `False` mientras no haya entrado nunca: la ficha existe y espera a que
    #: su identidad de Azure la reclame en el primer inicio de sesión.
    emparejado: bool


@router.get("/usuarios", response_model=list[UsuarioFuera])
def listar_usuarios(sesion: SesionDep, usuario: UsuarioDep) -> list[UsuarioFuera]:
    filas = sesion.execute(
        text(
            "SELECT id, email, nombre, rol::text AS rol, activo, "
            "       (sub_oidc IS NOT NULL) AS emparejado "
            "FROM usuario ORDER BY nombre"
        )
    ).mappings()
    return [UsuarioFuera(**f) for f in filas]


@router.post("/usuarios", response_model=UsuarioFuera, status_code=status.HTTP_201_CREATED)
def invitar(
    datos: NuevoUsuario, sesion: SesionDep, usuario: EscrituraEstructuraDep
) -> UsuarioFuera:
    """Da de alta la ficha. **No crea nada en Azure**: el directorio no es
    nuestro. Cuando esa persona entre con su cuenta, se empareja por correo."""
    if datos.rol not in ROLES:
        raise HTTPException(
            NO_PROCESABLE,
            f"Rol no válido. Se admiten: {', '.join(ROLES)}",
        )
    try:
        identificador = sesion.execute(
            text(
                "INSERT INTO usuario (organizacion_id, email, nombre, rol) "
                "VALUES (:org, :email, :nombre, CAST(:rol AS rol_usuario)) RETURNING id"
            ),
            {
                "org": usuario.organizacion_id,
                "email": str(datos.email),
                "nombre": datos.nombre,
                "rol": datos.rol,
            },
        ).scalar_one()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Ya hay un usuario con el correo «{datos.email}»"
        ) from exc
    return UsuarioFuera(
        id=identificador,
        email=str(datos.email),
        nombre=datos.nombre,
        rol=datos.rol,
        activo=True,
        emparejado=False,
    )


class NuevoAmbito(BaseModel):
    cartera_id: uuid.UUID | None = None
    activo_id: uuid.UUID | None = None


class AmbitoFuera(BaseModel):
    id: uuid.UUID
    cartera_id: uuid.UUID | None
    activo_id: uuid.UUID | None
    etiqueta: str


@router.get("/usuarios/{usuario_id}/ambitos", response_model=list[AmbitoFuera])
def listar_ambitos(
    usuario_id: uuid.UUID, sesion: SesionDep, usuario: UsuarioDep
) -> list[AmbitoFuera]:
    filas = sesion.execute(
        text(
            "SELECT v.id, v.cartera_id, v.activo_id, "
            "       COALESCE(c.nombre, a.nombre) AS etiqueta "
            "FROM ambito_de_visibilidad v "
            "LEFT JOIN cartera c ON c.id = v.cartera_id "
            "LEFT JOIN activo a ON a.id = v.activo_id "
            "WHERE v.usuario_id = :usuario ORDER BY etiqueta"
        ),
        {"usuario": usuario_id},
    ).mappings()
    return [AmbitoFuera(**f) for f in filas]


@router.post(
    "/usuarios/{usuario_id}/ambitos",
    response_model=AmbitoFuera,
    status_code=status.HTTP_201_CREATED,
)
def dar_ambito(
    usuario_id: uuid.UUID,
    datos: NuevoAmbito,
    sesion: SesionDep,
    usuario: EscrituraEstructuraDep,
) -> AmbitoFuera:
    """Abre a alguien una cartera o un activo. Es lo único que hará falta el
    día que esto se abra a clientes."""
    if bool(datos.cartera_id) == bool(datos.activo_id):
        raise HTTPException(
            NO_PROCESABLE,
            "Indique una cartera **o** un activo, no las dos cosas ni ninguna",
        )
    try:
        identificador = sesion.execute(
            text(
                "INSERT INTO ambito_de_visibilidad (organizacion_id, usuario_id, cartera_id, "
                "activo_id) VALUES (:org, :usuario, :cartera, :activo) RETURNING id"
            ),
            {
                "org": usuario.organizacion_id,
                "usuario": usuario_id,
                "cartera": datos.cartera_id,
                "activo": datos.activo_id,
            },
        ).scalar_one()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ese ámbito ya estaba dado, o no existe lo que apunta"
        ) from exc
    etiqueta = sesion.execute(
        text(
            "SELECT COALESCE(c.nombre, a.nombre) FROM ambito_de_visibilidad v "
            "LEFT JOIN cartera c ON c.id = v.cartera_id "
            "LEFT JOIN activo a ON a.id = v.activo_id WHERE v.id = :id"
        ),
        {"id": identificador},
    ).scalar_one()
    return AmbitoFuera(
        id=identificador,
        cartera_id=datos.cartera_id,
        activo_id=datos.activo_id,
        etiqueta=etiqueta,
    )


@router.delete("/ambitos/{ambito_id}", status_code=status.HTTP_204_NO_CONTENT)
def quitar_ambito(ambito_id: uuid.UUID, sesion: SesionDep, usuario: EscrituraEstructuraDep) -> None:
    afectadas: int = sesion.execute(
        text("DELETE FROM ambito_de_visibilidad WHERE id = :id"),
        {"id": ambito_id},
        # `rowcount` lo tiene el `CursorResult` que devuelve un UPDATE, pero la
        # firma de `Session.execute` promete el `Result` genérico, que no.
    ).rowcount  # type: ignore[attr-defined]
    if not afectadas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ese ámbito no existe")

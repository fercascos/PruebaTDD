"""Clientes y personas de la organización.

Dos listados pequeños sin los que **no se puede dar de alta un encargo desde la
interfaz**: un proyecto exige cliente, y asignar el equipo exige saber quién hay
en la organización. Los dos existían solo como tablas.

`[REQ]` §13 · El listado de personas devuelve **lo mínimo para elegir a alguien
en un desplegable**: identificador, nombre, correo y rol. Ni el hash de la
contraseña, ni el contador de intentos fallidos, ni la fecha del último acceso.
Un listado que se consulta para rellenar un formulario no tiene por qué
exponer el estado de seguridad de las cuentas.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core.deps import SesionDep, UsuarioDep

router = APIRouter(tags=["Directorio"])


# ─────────────────────────────────────────────────────────────────────────────
#  Clientes
# ─────────────────────────────────────────────────────────────────────────────


class DatosDeCliente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)


class Cliente(BaseModel):
    id: uuid.UUID
    name: str
    #: Cuántos encargos tiene. Evita borrar por error al que sostiene la cartera.
    projects: int = 0


_CLIENTE = """
    SELECT c.id, c.name,
           (SELECT count(*) FROM project p
            WHERE p.client_id = c.id AND p.deleted_at IS NULL) AS projects
    FROM client c
"""


@router.get("/clients", response_model=list[Cliente])
def listar_clientes(s: SesionDep, q: str | None = None) -> Any:
    filas = (
        s.execute(
            text(  # noqa: S608
                f"{_CLIENTE} WHERE c.deleted_at IS NULL "
                "  AND (CAST(:q AS text) IS NULL OR c.name ILIKE '%' || :q || '%') "
                "ORDER BY c.name"
            ),
            {"q": q},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.post("/clients", status_code=status.HTTP_201_CREATED, response_model=Cliente)
def crear_cliente(cuerpo: DatosDeCliente, s: SesionDep, usuario: UsuarioDep) -> Any:
    """Da de alta un cliente, o devuelve el que ya existía con ese nombre.

    Devolver el existente en vez de fallar es deliberado: dos consultores dando
    de alta «Inversora Ficticia» a la vez no es un error del que haya que
    informar, y crear un duplicado partiría la cartera del cliente en dos
    fichas que nadie volvería a juntar.
    """
    nombre = cuerpo.name.strip()
    ya = (
        s.execute(
            text(f"{_CLIENTE} WHERE c.deleted_at IS NULL AND lower(c.name) = lower(:n)"),  # noqa: S608
            {"n": nombre},
        )
        .mappings()
        .first()
    )
    if ya is not None:
        return dict(ya)

    nuevo = s.execute(
        text("INSERT INTO client (organization_id, name) VALUES (:o, :n) RETURNING id"),
        {"o": str(usuario.organization_id), "n": nombre},
    ).scalar_one()
    return dict(
        s.execute(text(f"{_CLIENTE} WHERE c.id = :i"), {"i": str(nuevo)}).mappings().one()  # noqa: S608
    )


@router.patch("/clients/{client_id}", response_model=Cliente)
def renombrar_cliente(client_id: uuid.UUID, cuerpo: DatosDeCliente, s: SesionDep) -> Any:
    hay = s.execute(
        text("UPDATE client SET name = :n WHERE id = :i AND deleted_at IS NULL RETURNING id"),
        {"n": cuerpo.name.strip(), "i": str(client_id)},
    ).first()
    if hay is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado")
    return dict(
        s.execute(text(f"{_CLIENTE} WHERE c.id = :i"), {"i": str(client_id)}).mappings().one()  # noqa: S608
    )


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar_cliente(client_id: uuid.UUID, s: SesionDep) -> None:
    """No se borra un cliente que sostiene encargos.

    Es un `409` y no un borrado en cascada: los proyectos de ese cliente son
    trabajo hecho y facturado, y dejarlos huérfanos por un clic sería el peor
    resultado posible de una pantalla de mantenimiento.
    """
    encargos = s.execute(
        text("SELECT count(*) FROM project WHERE client_id = :i AND deleted_at IS NULL"),
        {"i": str(client_id)},
    ).scalar_one()
    if encargos:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"El cliente tiene {encargos} encargos y no se puede borrar",
        )
    hay = s.execute(
        text(
            "UPDATE client SET deleted_at = now() WHERE id = :i AND deleted_at IS NULL RETURNING id"
        ),
        {"i": str(client_id)},
    ).first()
    if hay is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado")


# ─────────────────────────────────────────────────────────────────────────────
#  Personas
# ─────────────────────────────────────────────────────────────────────────────


class Persona(BaseModel):
    """Lo mínimo para elegir a alguien en un desplegable. Nada más."""

    id: uuid.UUID
    full_name: str
    email: str
    org_role: str
    is_active: bool


@router.get("/users", response_model=list[Persona])
def listar_personas(s: SesionDep, q: str | None = None, incluir_inactivos: bool = False) -> Any:
    """`[REQ]` No devuelve el hash, ni los intentos fallidos, ni el bloqueo.

    Un listado que se consulta para rellenar un formulario no tiene por qué
    exponer el estado de seguridad de las cuentas, y la RLS ya lo acota a la
    propia organización.
    """
    filas = (
        s.execute(
            text(
                "SELECT id, full_name, email, CAST(org_role AS text) AS org_role, is_active "
                "FROM app_user "
                "WHERE (:todos OR is_active) "
                "  AND (CAST(:q AS text) IS NULL "
                "       OR full_name ILIKE '%' || :q || '%' OR email ILIKE '%' || :q || '%') "
                "ORDER BY full_name"
            ),
            {"todos": incluir_inactivos, "q": q},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


class AltaDePersona(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    org_role: str = "CONSULTOR"
    can_manage_suggestions: bool = False
    #: Contraseña inicial. `[REC]` Debería llegar por invitación por correo, que
    #: exige SMTP y todavía no está: mientras tanto, la fija quien da de alta.
    password: str = Field(min_length=12, repr=False)


ROLES = ("ADMIN", "DIRECTOR_PROYECTO", "CONSULTOR", "TECNICO_ESPECIALISTA", "REVISOR", "LECTOR")


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=Persona)
def crear_persona(cuerpo: AltaDePersona, s: SesionDep, usuario: UsuarioDep) -> Any:
    """`[REQ]` Solo un administrador da de alta a otras personas."""
    from tdd.core.security import hash_password
    from tdd.identity.service import ClaveDebil, comprobar_fortaleza

    if usuario.org_role != "ADMIN":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Solo un administrador puede dar de alta usuarios"
        )
    if cuerpo.org_role not in ROLES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Rol desconocido. Disponibles: {', '.join(ROLES)}",
        )
    try:
        comprobar_fortaleza(cuerpo.password, email=cuerpo.email)
    except ClaveDebil as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    ya = s.execute(
        text("SELECT 1 FROM app_user WHERE lower(email) = lower(:e)"), {"e": cuerpo.email}
    ).first()
    if ya is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo")

    nuevo = s.execute(
        text(
            "INSERT INTO app_user (organization_id, email, full_name, password_hash, org_role, "
            "can_manage_suggestions) "
            "VALUES (:o, :e, :n, :h, CAST(:r AS org_role), :g) RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "e": cuerpo.email,
            "n": cuerpo.full_name,
            "h": hash_password(cuerpo.password),
            "r": cuerpo.org_role,
            "g": cuerpo.can_manage_suggestions,
        },
    ).scalar_one()
    return _persona(s, nuevo)


class CambioDePersona(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=160)
    org_role: str | None = None
    can_manage_suggestions: bool | None = None
    is_active: bool | None = None


def _persona(s: Session, user_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text(
                "SELECT id, full_name, email, CAST(org_role AS text) AS org_role, is_active "
                "FROM app_user WHERE id = :i"
            ),
            {"i": str(user_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return dict(fila)


@router.patch("/users/{user_id}", response_model=Persona)
def actualizar_persona(
    user_id: uuid.UUID, cuerpo: CambioDePersona, s: SesionDep, usuario: UsuarioDep
) -> Any:
    if usuario.org_role != "ADMIN":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Solo un administrador puede modificar usuarios"
        )
    if cuerpo.is_active is False and user_id == usuario.id:
        # Desactivarse a uno mismo deja la organización potencialmente sin
        # administrador y al usuario fuera en la siguiente petición.
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "No puede desactivar su propia cuenta"
        )
    cambios = cuerpo.model_dump(exclude_unset=True)
    if not cambios:
        return _persona(s, user_id)
    if "org_role" in cambios and cambios["org_role"] not in ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rol desconocido")

    piezas = [
        "org_role = CAST(:org_role AS org_role)" if c == "org_role" else f"{c} = :{c}"
        for c in cambios
    ]
    s.execute(
        text(f"UPDATE app_user SET {', '.join(piezas)}, updated_at = now() WHERE id = :_id"),  # noqa: S608
        {**cambios, "_id": str(user_id)},
    )
    if cambios.get("is_active") is False:
        # Desactivar debe echar a esa persona ahora, no cuando caduque su token
        # de refresco catorce días después.
        s.execute(
            text(
                "UPDATE user_session SET revoked_at = now(), revoked_reason = 'CIERRE_DE_SESION' "
                "WHERE user_id = :u AND revoked_at IS NULL"
            ),
            {"u": str(user_id)},
        )
    return _persona(s, user_id)

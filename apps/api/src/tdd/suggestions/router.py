"""API del módulo de Sugerencias."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from tdd.core.deps import GestorSugerenciasDep, SesionDep, UsuarioDep
from tdd.suggestions.service import (
    PeticionTransicion,
    RespuestaObligatoria,
    SuggestionStatus,
    SuggestionType,
    TransicionInvalida,
    validar_transicion,
)

router = APIRouter(prefix="/suggestions", tags=["Sugerencias"])


class CrearSugerencia(BaseModel):
    """Cuerpo de alta.

    Nótese lo que **no** está: `organization_id` ni `created_by`. Se toman del
    token, nunca del cuerpo. Es el fallo clásico de un endpoint abierto a todos
    los roles, y aquí es imposible por construcción.
    """

    type: SuggestionType
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1)
    payload: dict[str, Any] | None = None
    context_project_id: uuid.UUID | None = None
    context_entity_type: str | None = Field(default=None, max_length=40)
    context_entity_id: uuid.UUID | None = None
    context_screen: str | None = Field(default=None, max_length=60)


class Sugerencia(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    title: str
    body: str
    created_at: Any
    resolution_note: str | None = None
    context_project_id: uuid.UUID | None = None
    applied_entity_type: str | None = None
    applied_entity_id: uuid.UUID | None = None


class CambiarEstado(BaseModel):
    to: SuggestionStatus
    resolution_note: str | None = None
    duplicate_of_id: uuid.UUID | None = None
    applied_entity_type: str | None = None
    applied_entity_id: uuid.UUID | None = None


_COLUMNAS = (
    "id, type, status, title, body, created_at, resolution_note, "
    "context_project_id, applied_entity_type, applied_entity_id"
)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=Sugerencia)
def crear(cuerpo: CrearSugerencia, s: SesionDep, usuario: UsuarioDep) -> Any:
    """Cualquier usuario autenticado, incluido `LECTOR`."""
    fila = s.execute(
        text(
            f"INSERT INTO suggestion (organization_id, type, status, title, body, payload, "  # noqa: S608
            "created_by, context_project_id, context_entity_type, context_entity_id, "
            "context_screen) VALUES (:org, CAST(:type AS suggestion_type), 'NUEVA', :title, "
            ":body, CAST(:payload AS jsonb), :autor, :cp, :cet, :cei, :cs) "
            f"RETURNING {_COLUMNAS}"
        ),
        {
            "org": usuario.organization_id,
            "autor": usuario.id,
            "type": cuerpo.type.value,
            "title": cuerpo.title,
            "body": cuerpo.body,
            "payload": None if cuerpo.payload is None else __import__("json").dumps(cuerpo.payload),
            "cp": cuerpo.context_project_id,
            "cet": cuerpo.context_entity_type,
            "cei": cuerpo.context_entity_id,
            "cs": cuerpo.context_screen,
        },
    ).mappings().one()
    return dict(fila)


@router.get("/mine", response_model=list[Sugerencia])
def mias(s: SesionDep, usuario: UsuarioDep) -> Any:
    """`[REQ]` P-40 · El autor ve las suyas, con su estado y la respuesta.

    Sin esto, quien propone escribe en un buzón sin fondo y deja de escribir.
    """
    filas = s.execute(
        text(
            f"SELECT {_COLUMNAS} FROM suggestion WHERE created_by = :u "  # noqa: S608
            "ORDER BY created_at DESC"
        ),
        {"u": usuario.id},
    ).mappings().all()
    return [dict(f) for f in filas]


@router.get("", response_model=list[Sugerencia])
def bandeja(
    s: SesionDep,
    _: GestorSugerenciasDep,
    estado: Annotated[SuggestionStatus | None, None] = None,
    tipo: Annotated[SuggestionType | None, None] = None,
) -> Any:
    """`[REQ]` La bandeja completa: **solo administradores**.

    La RLS ya lo garantiza a nivel de fila; la dependencia devuelve un `403`
    explícito en vez de una lista vacía silenciosa.
    """
    filas = s.execute(
        text(
            f"SELECT {_COLUMNAS} FROM suggestion "  # noqa: S608
            # El CAST explícito es necesario: con un parámetro NULL suelto,
            # PostgreSQL no puede inferir el tipo y rechaza la consulta.
            "WHERE (CAST(:estado AS text) IS NULL "
            "       OR status = CAST(:estado AS suggestion_status)) "
            "  AND (CAST(:tipo AS text) IS NULL "
            "       OR type = CAST(:tipo AS suggestion_type)) "
            "ORDER BY created_at DESC"
        ),
        {
            "estado": estado.value if estado else None,
            "tipo": tipo.value if tipo else None,
        },
    ).mappings().all()
    return [dict(f) for f in filas]


@router.get("/{sugerencia_id}", response_model=Sugerencia)
def detalle(sugerencia_id: uuid.UUID, s: SesionDep, usuario: UsuarioDep) -> Any:
    fila = s.execute(
        text(f"SELECT {_COLUMNAS} FROM suggestion WHERE id = :i"),  # noqa: S608
        {"i": sugerencia_id},
    ).mappings().first()
    if fila is None:
        # 404, no 403: no se confirma que exista una sugerencia ajena.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrada")

    # [REC] Abrir una sugerencia con contexto de proyecto deja rastro. Sin esto,
    # el buzón sería una vía para leer sobre proyectos sin que conste el acceso.
    if fila["context_project_id"] is not None:
        s.execute(
            text(
                "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
                "entity_id, project_id, severity) VALUES (:o, :u, 'SUGGESTION_VIEWED', "
                "'suggestion', :i, :p, 'AVISO')"
            ),
            {
                "o": usuario.organization_id,
                "u": usuario.id,
                "i": sugerencia_id,
                "p": fila["context_project_id"],
            },
        )
    return dict(fila)


@router.post("/{sugerencia_id}/transitions", response_model=Sugerencia)
def cambiar_estado(
    sugerencia_id: uuid.UUID, cuerpo: CambiarEstado, s: SesionDep, usuario: GestorSugerenciasDep
) -> Any:
    actual = s.execute(
        text("SELECT status FROM suggestion WHERE id = :i"), {"i": sugerencia_id}
    ).scalar_one_or_none()
    if actual is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrada")

    peticion = PeticionTransicion(
        a=cuerpo.to,
        resolution_note=cuerpo.resolution_note,
        duplicate_of_id=cuerpo.duplicate_of_id,
        applied_entity_type=cuerpo.applied_entity_type,
        applied_entity_id=cuerpo.applied_entity_id,
    )
    try:
        validar_transicion(SuggestionStatus(actual), peticion, propia_id=sugerencia_id)
    except RespuestaObligatoria as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except TransicionInvalida as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    fila = s.execute(
        text(
            "UPDATE suggestion SET status = CAST(:to AS suggestion_status), "  # noqa: S608
            "resolution_note = COALESCE(:nota, resolution_note), "
            "duplicate_of_id = COALESCE(:dup, duplicate_of_id), "
            "applied_entity_type = COALESCE(:aet, applied_entity_type), "
            "applied_entity_id = COALESCE(:aei, applied_entity_id), "
            "resolved_by = :u, resolved_at = now() "
            f"WHERE id = :i RETURNING {_COLUMNAS}"
        ),
        {
            "to": cuerpo.to.value,
            "nota": cuerpo.resolution_note,
            "dup": cuerpo.duplicate_of_id,
            "aet": cuerpo.applied_entity_type,
            "aei": cuerpo.applied_entity_id,
            "u": usuario.id,
            "i": sugerencia_id,
        },
    ).mappings().one()

    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, after_data, severity) VALUES (:o, :u, 'SUGGESTION_STATUS_CHANGED', "
            "'suggestion', :i, CAST(:d AS jsonb), 'INFO')"
        ),
        {
            "o": usuario.organization_id,
            "u": usuario.id,
            "i": sugerencia_id,
            "d": f'{{"from": "{actual}", "to": "{cuerpo.to.value}"}}',
        },
    )
    return dict(fila)


class Resumen(BaseModel):
    nuevas: int
    en_revision: int
    cerradas: int


@router.get("/summary/contadores", response_model=Resumen)
def resumen(s: SesionDep, _: GestorSugerenciasDep) -> Any:
    """Contadores para la insignia del menú."""
    fila = s.execute(
        text(
            "SELECT count(*) FILTER (WHERE status = 'NUEVA') AS nuevas, "
            "count(*) FILTER (WHERE status = 'EN_REVISION') AS en_revision, "
            "count(*) FILTER (WHERE status IN ('ACEPTADA','RECHAZADA','DUPLICADA','APLICADA')) "
            "AS cerradas FROM suggestion"
        )
    ).mappings().one()
    return dict(fila)


Literal  # noqa: B018 — reexportado para los esquemas del cliente generado

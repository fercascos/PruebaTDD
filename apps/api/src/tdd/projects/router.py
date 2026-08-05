"""API de proyectos.

El alta es el punto donde el cliente **elige las fases aplicables** `[REQ]`
§3.1.5. Se crean solo las marcadas: un proyecto sin Q&A no arrastra una fase
vacía que nadie va a rellenar y que ensucia la ficha.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from tdd.core.deps import SesionDep, UsuarioDep
from tdd.phases.engine import PhaseCode
from tdd.phases.repository import contar_para_transicion
from tdd.projects.state_machine import (
    EstadoDelEncargo,
    GuardaIncumplida,
    ProjectStatus,
    TransicionNoPermitida,
    destinos_posibles,
    validar_transicion,
)

router = APIRouter(tags=["Proyectos"])


class FaseAplicable(BaseModel):
    code: PhaseCode
    owner_user_id: uuid.UUID | None = None


class CrearProyecto(BaseModel):
    client_id: uuid.UUID
    internal_code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    report_due_date: Any | None = None
    #: `[REQ]` Las fases se eligen **a la carta** al dar de alta.
    applicable_phases: list[FaseAplicable] = Field(default_factory=list)


class Proyecto(BaseModel):
    id: uuid.UUID
    internal_code: str
    name: str
    status: str
    currency: str


@router.post("/projects", status_code=status.HTTP_201_CREATED, response_model=Proyecto)
def crear(cuerpo: CrearProyecto, s: SesionDep, usuario: UsuarioDep) -> Any:
    fila = (
        s.execute(
            text(
                "INSERT INTO project (organization_id, client_id, internal_code, name, currency, "
                "report_due_date) VALUES (:o, :c, :ic, :n, :cur, :due) "
                "RETURNING id, internal_code, name, CAST(status AS text) AS status, currency"
            ),
            {
                "o": usuario.organization_id,
                "c": cuerpo.client_id,
                "ic": cuerpo.internal_code,
                "n": cuerpo.name,
                "cur": cuerpo.currency,
                "due": cuerpo.report_due_date,
            },
        )
        .mappings()
        .one()
    )

    # Solo las fases marcadas. Las demás ni se crean: activarlas después es un
    # POST, y así la ficha no muestra ocho filas cuando el encargo usa cuatro.
    for orden, fase in enumerate(cuerpo.applicable_phases, 1):
        s.execute(
            text(
                "INSERT INTO project_phase (organization_id, project_id, phase_definition_id, "
                "owner_user_id, display_order) "
                "SELECT :o, :p, pd.id, :u, :ord FROM phase_definition pd WHERE pd.code = :code"
            ),
            {
                "o": usuario.organization_id,
                "p": fila["id"],
                "u": fase.owner_user_id,
                "ord": orden,
                "code": fase.code.value,
            },
        )
    return dict(fila)


class Transicion(BaseModel):
    to: ProjectStatus


class DestinoPosible(BaseModel):
    to: ProjectStatus
    permitida: bool
    falta: list[str]


@router.get("/projects/{project_id}/transitions", response_model=list[DestinoPosible])
def transiciones_disponibles(project_id: uuid.UUID, s: SesionDep) -> Any:
    """Qué se puede hacer ahora y **qué falta para lo que no**.

    `[REC]` Alimenta botones deshabilitados con su motivo, en vez de botones
    ausentes. Un botón que no está no se puede preguntar por qué no está.
    """
    actual = s.execute(
        text("SELECT CAST(status AS text) FROM project WHERE id = :p"), {"p": project_id}
    ).scalar_one_or_none()
    if actual is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")

    c = contar_para_transicion(s, project_id)
    encargo = EstadoDelEncargo(
        clientes=c["clientes"],
        activos=c["activos"],
        visitas_agendadas=c["agendadas"],
        visitas_realizadas=c["realizadas"],
    )
    return [
        {"to": destino, "permitida": not falta, "falta": falta}
        for destino, falta in destinos_posibles(ProjectStatus(actual), encargo).items()
    ]


@router.post("/projects/{project_id}/transitions", response_model=Proyecto)
def transicionar(
    project_id: uuid.UUID, cuerpo: Transicion, s: SesionDep, usuario: UsuarioDep
) -> Any:
    actual = s.execute(
        text("SELECT CAST(status AS text) FROM project WHERE id = :p"), {"p": project_id}
    ).scalar_one_or_none()
    if actual is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")

    c = contar_para_transicion(s, project_id)
    encargo = EstadoDelEncargo(
        clientes=c["clientes"],
        activos=c["activos"],
        visitas_agendadas=c["agendadas"],
        visitas_realizadas=c["realizadas"],
    )
    try:
        validar_transicion(ProjectStatus(actual), cuerpo.to, encargo)
    except GuardaIncumplida as exc:
        # 422: la transición existe, pero falta trabajo. El mensaje dice cuál.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except TransicionNoPermitida as exc:
        # 409: esa transición no existe desde el estado actual.
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    fila = (
        s.execute(
            text(
                "UPDATE project SET status = CAST(:to AS project_status), updated_at = now() "
                "WHERE id = :p RETURNING id, internal_code, name, CAST(status AS text) AS status, "
                "currency"
            ),
            {"to": cuerpo.to.value, "p": project_id},
        )
        .mappings()
        .one()
    )

    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, project_id, after_data, severity) VALUES (:o, :u, "
            "'PROJECT_STATUS_CHANGED', 'project', :p, :p, CAST(:d AS jsonb), 'AVISO')"
        ),
        {
            "o": usuario.organization_id,
            "u": usuario.id,
            "p": project_id,
            "d": f'{{"from": "{actual}", "to": "{cuerpo.to.value}"}}',
        },
    )
    return dict(fila)

"""API de fases del proceso."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from tdd.core.deps import SesionDep, UsuarioDep
from tdd.phases.engine import (
    EstadoNoEscribible,
    PhaseCode,
    PhaseStatus,
    comprobar_estado_escribible,
    describir_avance,
    estado_derivado,
    estado_sugerido,
)
from tdd.phases.repository import reunir_hechos

router = APIRouter(tags=["Fases del proceso"])


class Fase(BaseModel):
    id: uuid.UUID
    code: PhaseCode
    name_es: str
    status: PhaseStatus
    es_derivado: bool
    detalle: str
    owner_user_id: uuid.UUID | None
    display_order: int
    estado_sugerido: PhaseStatus | None = Field(
        default=None,
        description=(
            "Solo para fases NO derivadas: lo que la aplicación deduce del trabajo "
            "hecho. Se ofrece, no se impone: el responsable puede tener motivos "
            "que la aplicación no conoce."
        ),
    )


@router.get("/projects/{project_id}/phases", response_model=list[Fase])
def listar(project_id: uuid.UUID, s: SesionDep) -> Any:
    """Las fases del proyecto, con su estado y **por qué está ahí**.

    Las derivadas se calculan al vuelo: no se lee un `status` que podría estar
    desfasado respecto del trabajo real.
    """
    filas = (
        s.execute(
            text(
                "SELECT ph.id, pd.code, pd.name_es, CAST(ph.status AS text) AS status, "
                "pd.status_is_derived, ph.owner_user_id, ph.display_order "
                "FROM project_phase ph JOIN phase_definition pd ON pd.id = ph.phase_definition_id "
                "WHERE ph.project_id = :p ORDER BY ph.display_order, pd.display_order"
            ),
            {"p": project_id},
        )
        .mappings()
        .all()
    )

    hechos = reunir_hechos(s, project_id)
    salida = []
    for f in filas:
        codigo = PhaseCode(f["code"])
        if f["status_is_derived"]:
            estado = estado_derivado(codigo, hechos)
            sugerido = None
        else:
            estado = PhaseStatus(f["status"])
            calculado = estado_sugerido(codigo, hechos)
            sugerido = calculado if calculado is not estado else None

        avance = describir_avance(codigo, estado, hechos)
        salida.append(
            {
                "id": f["id"],
                "code": codigo,
                "name_es": f["name_es"],
                "status": estado,
                "es_derivado": bool(f["status_is_derived"]),
                "detalle": avance.detalle,
                "owner_user_id": f["owner_user_id"],
                "display_order": f["display_order"],
                "estado_sugerido": sugerido,
            }
        )
    return salida


class ActualizarFase(BaseModel):
    status: PhaseStatus | None = None
    owner_user_id: uuid.UUID | None = None
    notes: str | None = None


@router.patch("/project-phases/{phase_id}", response_model=Fase)
def actualizar(phase_id: uuid.UUID, cuerpo: ActualizarFase, s: SesionDep) -> Any:
    f = (
        s.execute(
            text(
                "SELECT ph.project_id, pd.code, pd.status_is_derived FROM project_phase ph "
                "JOIN phase_definition pd ON pd.id = ph.phase_definition_id WHERE ph.id = :i"
            ),
            {"i": phase_id},
        )
        .mappings()
        .first()
    )
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fase no encontrada")

    if cuerpo.status is not None:
        try:
            comprobar_estado_escribible(PhaseCode(f["code"]))
        except EstadoNoEscribible as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    s.execute(
        text(
            "UPDATE project_phase SET "
            "status = COALESCE(CAST(:st AS phase_status), status), "
            "completed_at = CASE WHEN :st = 'COMPLETADA' THEN now() ELSE completed_at END, "
            "started_at = CASE WHEN :st = 'EN_CURSO' AND started_at IS NULL THEN now() "
            "             ELSE started_at END, "
            "owner_user_id = COALESCE(:u, owner_user_id), "
            "notes = COALESCE(:n, notes), updated_at = now() WHERE id = :i"
        ),
        {
            "st": cuerpo.status.value if cuerpo.status else None,
            "u": cuerpo.owner_user_id,
            "n": cuerpo.notes,
            "i": phase_id,
        },
    )
    return next(f for f in listar(f["project_id"], s) if f["id"] == phase_id)


@router.post("/projects/{project_id}/phases/{code}/activate", response_model=Fase)
def activar(project_id: uuid.UUID, code: PhaseCode, s: SesionDep, usuario: UsuarioDep) -> Any:
    """Activa una fase que no se marcó al dar de alta el proyecto."""
    ya = s.execute(
        text(
            "SELECT ph.id FROM project_phase ph JOIN phase_definition pd "
            "ON pd.id = ph.phase_definition_id WHERE ph.project_id = :p AND pd.code = :c"
        ),
        {"p": project_id, "c": code.value},
    ).scalar_one_or_none()
    if ya is not None:
        s.execute(
            text(
                "UPDATE project_phase SET is_applicable = TRUE, "
                "status = CASE WHEN status = 'NO_APLICA' THEN 'PENDIENTE' ELSE status END "
                "WHERE id = :i"
            ),
            {"i": ya},
        )
    else:
        s.execute(
            text(
                "INSERT INTO project_phase (organization_id, project_id, phase_definition_id, "
                "display_order) SELECT :o, :p, pd.id, pd.display_order "
                "FROM phase_definition pd WHERE pd.code = :c"
            ),
            {"o": usuario.organization_id, "p": project_id, "c": code.value},
        )
    return next(f for f in listar(project_id, s) if f["code"] is code)


class Limitacion(BaseModel):
    title: str
    status: str
    unavailable_reason: str | None


@router.get("/projects/{project_id}/report-limitations", response_model=list[Limitacion])
def limitaciones_del_informe(project_id: uuid.UUID, s: SesionDep) -> Any:
    """`[REC]` Lo que no se ha podido revisar, listo para volcar al informe.

    Declarar las limitaciones es una obligación profesional en una TDD, y hoy
    suele reconstruirse de memoria al final del encargo. Aquí sale de la propia
    checklist: la columna `affects_report_limitations` se calcula sola.
    """
    filas = (
        s.execute(
            text(
                "SELECT d.title, CAST(d.status AS text) AS status, d.unavailable_reason "
                "FROM doc_request_item d JOIN project_phase ph ON ph.id = d.project_phase_id "
                "WHERE ph.project_id = :p AND d.affects_report_limitations "
                "ORDER BY d.display_order"
            ),
            {"p": project_id},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]

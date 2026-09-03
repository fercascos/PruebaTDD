"""API de la revisión documental asistida por IA."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from tdd.core.deps import SesionDep, UsuarioDep
from tdd.evidence.router import AlmacenDep
from tdd.revision_documental import servicio
from tdd.revision_documental.puerto import Revisor
from tdd.revision_documental.simulado import RevisorSimulado

router = APIRouter(tags=["Revisión documental con IA"])


def obtener_revisor(request: Request) -> Revisor:
    """El revisor configurado, o el simulado si no hay ninguno.

    `[LIM]` Hoy siempre es el simulado: no hay proveedor elegido.
    """
    revisor = getattr(request.app.state, "revisor_documental", None)
    if revisor is None:
        return RevisorSimulado()
    return revisor  # type: ignore[no-any-return]


RevisorDep = Annotated[Revisor, Depends(obtener_revisor)]


class Permiso(BaseModel):
    activo: bool
    desde: Any | None = None
    por: uuid.UUID | None = None


class CambiarPermiso(BaseModel):
    activo: bool


@router.get("/projects/{project_id}/ai-doc-review", response_model=Permiso)
def ver_permiso(project_id: uuid.UUID, s: SesionDep) -> Any:
    """Si este encargo tiene autorizada la revisión con IA, y quién la autorizó."""
    p = servicio.permiso_de(s, project_id)
    return {"activo": p.activo, "desde": p.desde, "por": p.por}


@router.put("/projects/{project_id}/ai-doc-review", response_model=Permiso)
def cambiar_permiso(
    project_id: uuid.UUID, cuerpo: CambiarPermiso, s: SesionDep, usuario: UsuarioDep
) -> Any:
    """`[REQ]` Enciende o apaga la revisión con IA en este encargo.

    Solo quien administra o dirige proyectos puede hacerlo: es una autorización
    sobre documentación de un cliente, no una preferencia de la aplicación.
    """
    if usuario.org_role not in ("ADMIN", "DIRECTOR_PROYECTO"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Autorizar el análisis de documentación del cliente corresponde a quien "
            "administra o dirige el proyecto.",
        )
    p = servicio.autorizar(s, project_id, usuario_id=usuario.id, activo=cuerpo.activo)
    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, project_id, severity) VALUES (:o, :u, :a, 'project', :e, :e, 'AVISO')"
        ),
        {
            "o": str(usuario.organization_id),
            "u": str(usuario.id),
            "a": "AI_DOC_REVIEW_ENABLED" if cuerpo.activo else "AI_DOC_REVIEW_DISABLED",
            "e": str(project_id),
        },
    )
    return {"activo": p.activo, "desde": p.desde, "por": p.por}


class Observacion(BaseModel):
    id: uuid.UUID
    check_code: str
    check_name: str
    verdict: str
    summary: str
    evidence_text: str | None
    evidence_page: int | None
    confidence: float | None
    decision: str
    decided_by: uuid.UUID | None
    decision_note: str | None


class Revision(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: str
    provider: str
    model: str | None
    is_simulated: bool = Field(
        description=(
            "Si es cierto, NINGÚN proveedor ha leído el documento: las "
            "observaciones ocupan el sitio de las que vendrán, y no dicen nada "
            "sobre su contenido."
        )
    )
    document_sha256: str
    error_message: str | None
    observaciones: list[Observacion]


def _revision(s: Any, revision_id: uuid.UUID) -> dict[str, Any]:
    cab = (
        s.execute(
            text(
                "SELECT id, document_id, CAST(status AS text) AS status, provider, model, "
                "is_simulated, document_sha256, error_message FROM doc_review WHERE id = :i"
            ),
            {"i": str(revision_id)},
        )
        .mappings()
        .first()
    )
    if cab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revisión no encontrada")
    obs = (
        s.execute(
            text(
                "SELECT f.id, t.code AS check_code, t.name_es AS check_name, "
                "CAST(f.verdict AS text) AS verdict, f.summary, f.evidence_text, "
                "f.evidence_page, f.confidence, CAST(f.decision AS text) AS decision, "
                "f.decided_by, f.decision_note "
                "FROM doc_review_finding f JOIN doc_check_type t ON t.id = f.check_type_id "
                "WHERE f.doc_review_id = :r ORDER BY t.display_order, t.code"
            ),
            {"r": str(revision_id)},
        )
        .mappings()
        .all()
    )
    return {**dict(cab), "observaciones": [dict(o) for o in obs]}


@router.post(
    "/documents/{document_id}/ai-review",
    status_code=status.HTTP_201_CREATED,
    response_model=Revision,
)
def revisar(
    document_id: uuid.UUID,
    s: SesionDep,
    usuario: UsuarioDep,
    almacen: AlmacenDep,
    revisor: RevisorDep,
) -> Any:
    """Pide una revisión del documento y devuelve sus propuestas.

    `[LIM]` Es **síncrono**: con el conector simulado no cuesta nada, pero un
    proveedor real tardaría segundos y esto debería pasar por el worker
    asíncrono. Está anotado como pendiente y no se disimula con un `202` que
    hoy sería mentira.
    """
    try:
        revision_id = servicio.revisar_documento(
            s,
            document_id,
            revisor=revisor,
            almacen=almacen,
            usuario_id=usuario.id,
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except servicio.RevisionNoAutorizada as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    except servicio.DocumentoDemasiadoSensible as exc:
        # 403 y no 422: no es que la petición esté mal formada, es que no se
        # puede hacer. El mensaje dice qué hacer si de verdad hace falta.
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
    return _revision(s, revision_id)


@router.get("/documents/{document_id}/ai-reviews", response_model=list[Revision])
def historial(document_id: uuid.UUID, s: SesionDep) -> Any:
    """Todas las revisiones de un documento, de la más reciente a la más vieja."""
    ids = (
        s.execute(
            text("SELECT id FROM doc_review WHERE document_id = :d ORDER BY requested_at DESC"),
            {"d": str(document_id)},
        )
        .scalars()
        .all()
    )
    return [_revision(s, uuid.UUID(str(i))) for i in ids]


class Decision(BaseModel):
    aceptar: bool
    nota: str | None = None


@router.post("/ai-review-findings/{finding_id}/decision", response_model=Observacion)
def decidir(finding_id: uuid.UUID, cuerpo: Decision, s: SesionDep, usuario: UsuarioDep) -> Any:
    """`[REQ]` Una persona acepta o rechaza la propuesta. Este es el único camino.

    Aceptar **no cambia** el estado de la línea de la checklist: dice que la
    observación es cierta. Qué hacer con ella la decide quien lleva el encargo.
    """
    try:
        servicio.decidir(
            s, finding_id, aceptar=cuerpo.aceptar, usuario_id=usuario.id, nota=cuerpo.nota
        )
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except servicio.DecisionInvalida as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    fila = (
        s.execute(
            text(
                "SELECT f.id, t.code AS check_code, t.name_es AS check_name, "
                "CAST(f.verdict AS text) AS verdict, f.summary, f.evidence_text, "
                "f.evidence_page, f.confidence, CAST(f.decision AS text) AS decision, "
                "f.decided_by, f.decision_note "
                "FROM doc_review_finding f JOIN doc_check_type t ON t.id = f.check_type_id "
                "WHERE f.id = :i"
            ),
            {"i": str(finding_id)},
        )
        .mappings()
        .first()
    )
    return dict(fila) if fila else {}


class TipoDeComprobacion(BaseModel):
    code: str
    name_es: str
    description_es: str


@router.get("/ai-review-checks", response_model=list[TipoDeComprobacion])
def criterios(s: SesionDep) -> Any:
    """`[PDV]` Los criterios que se comprueban hoy.

    Están acordados en su enunciado y pendientes en su detalle. Se sirven desde
    la base para que afinarlos no requiera desplegar.
    """
    return [
        {"code": c.codigo, "name_es": c.nombre, "description_es": c.descripcion}
        for c in servicio.comprobaciones_vigentes(s)
    ]

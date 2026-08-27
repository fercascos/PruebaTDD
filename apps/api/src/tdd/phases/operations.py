"""Lo que se hace *dentro* de cada fase.

`phases/router.py` responde a «¿en qué estado está cada fase?». Este responde a
«¿qué documentación falta, cuándo es la visita, qué preguntas siguen sin
contestar?». Están separados porque el primero es cálculo derivado y este es
trabajo de campo: mezclarlos habría producido un fichero en el que ninguna de
las dos cosas se encuentra.

**Todo lo de aquí alimenta el apartado de limitaciones del informe.** Un
documento marcado `NO_DISPONIBLE` y una pregunta `SIN_RESPUESTA` son lo mismo
desde el punto de vista del informe: algo que no se ha podido revisar y hay que
declarar. La columna `affects_report_limitations` lo calcula sola en las dos
tablas, así que nadie tiene que acordarse al final del encargo.
"""

from __future__ import annotations

import uuid
from datetime import date
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core import concurrencia as cc
from tdd.core.deps import SesionDep, UsuarioDep
from tdd.phases.engine import PhaseCode

router = APIRouter(tags=["Trabajo de las fases"])


# ─────────────────────────────────────────────────────────────────────────────
#  Estados
# ─────────────────────────────────────────────────────────────────────────────
#
# Son enumeraciones y no `str` a propósito. Los tres estados de aquí abajo se
# escriben con un `CAST(:status AS ...)` contra un tipo enumerado de PostgreSQL,
# así que un valor que la base no reconozca la hace fallar: sin estas clases el
# error salía como **500** —«Error interno», sin decir qué valor sobraba ni
# cuáles se admiten— cuando la culpa era enteramente de quien llamaba. Con la
# enumeración, FastAPI responde `422` con la lista de valores válidos y además
# los publica en el OpenAPI. Se descubrió tecleando `PENDIENTE` en una línea del
# checklist documental, que usa `SOLICITADA`.


class DocRequestStatus(StrEnum):
    SOLICITADA = "SOLICITADA"
    RECIBIDA = "RECIBIDA"
    PARCIAL = "PARCIAL"
    NO_DISPONIBLE = "NO_DISPONIBLE"
    NO_APLICA = "NO_APLICA"


class VisitStatus(StrEnum):
    PENDIENTE_DEFINIR = "PENDIENTE_DEFINIR"
    AGENDADO = "AGENDADO"
    VISITADO = "VISITADO"


class QaQuestionStatus(StrEnum):
    ABIERTA = "ABIERTA"
    RESPONDIDA = "RESPONDIDA"
    SIN_RESPUESTA = "SIN_RESPUESTA"
    RETIRADA = "RETIRADA"


def _fase(s: Session, project_id: uuid.UUID, codigo: PhaseCode) -> uuid.UUID:
    """La fase del proyecto, exigiendo que exista.

    `404` y no creación al vuelo: las fases se eligen a la carta al dar de alta
    el encargo, y crear una porque alguien llamó a su endpoint saltaría esa
    decisión sin que nadie lo pidiera.
    """
    fila = s.execute(
        text(
            "SELECT ph.id FROM project_phase ph "
            "JOIN phase_definition pd ON pd.id = ph.phase_definition_id "
            "WHERE ph.project_id = :p AND pd.code = :c"
        ),
        {"p": str(project_id), "c": codigo.value},
    ).scalar()
    if fila is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"El proyecto no tiene la fase {codigo.value}: actívela primero",
        )
    return uuid.UUID(str(fila))


# ─────────────────────────────────────────────────────────────────────────────
#  Checklist de solicitud documental
# ─────────────────────────────────────────────────────────────────────────────


class LineaDeSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    asset_id: uuid.UUID | None = None
    display_order: int = 0


class ActualizarSolicitud(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DocRequestStatus | None = None
    unavailable_reason: str | None = None
    description: str | None = None
    received_at: Any | None = None


class Solicitud(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    asset_id: uuid.UUID | None
    title: str
    description: str | None
    status: str
    unavailable_reason: str | None
    requested_at: Any | None
    received_at: Any | None
    affects_report_limitations: bool
    display_order: int
    #: La versión sobre la que se escribe. Va también como `ETag`.
    row_version: int = 1


_SOLICITUD = """
    SELECT d.id, d.category_id, c.name_es AS category_name, d.asset_id, d.title,
           d.description, CAST(d.status AS text) AS status, d.unavailable_reason,
           d.requested_at, d.received_at, d.affects_report_limitations, d.display_order,
           d.row_version
    FROM doc_request_item d JOIN doc_request_category c ON c.id = d.category_id
"""


@router.post(
    "/projects/{project_id}/doc-requests",
    status_code=status.HTTP_201_CREATED,
    response_model=Solicitud,
)
def anadir_solicitud(
    project_id: uuid.UUID, cuerpo: LineaDeSolicitud, s: SesionDep, usuario: UsuarioDep
) -> Any:
    fase = _fase(s, project_id, PhaseCode.SOLICITUD_DOCUMENTACION)
    nuevo = s.execute(
        text(
            "INSERT INTO doc_request_item (organization_id, project_phase_id, asset_id, "
            "category_id, title, description, display_order, requested_at) "
            "VALUES (:o, :f, :a, :c, :t, :d, :orden, now()) RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "f": str(fase),
            "a": str(cuerpo.asset_id) if cuerpo.asset_id else None,
            "c": str(cuerpo.category_id),
            "t": cuerpo.title,
            "d": cuerpo.description,
            "orden": cuerpo.display_order,
        },
    ).scalar_one()
    return dict(
        s.execute(text(f"{_SOLICITUD} WHERE d.id = :i"), {"i": str(nuevo)}).mappings().one()  # noqa: S608
    )


@router.get("/projects/{project_id}/doc-requests", response_model=list[Solicitud])
def listar_solicitudes(project_id: uuid.UUID, s: SesionDep) -> Any:
    fase = _fase(s, project_id, PhaseCode.SOLICITUD_DOCUMENTACION)
    filas = (
        s.execute(
            text(f"{_SOLICITUD} WHERE d.project_phase_id = :f ORDER BY d.display_order, d.title"),  # noqa: S608
            {"f": str(fase)},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.patch("/doc-requests/{item_id}", response_model=Solicitud)
def actualizar_solicitud(
    item_id: uuid.UUID,
    cuerpo: ActualizarSolicitud,
    s: SesionDep,
    request: Request,
    respuesta: Response,
) -> Any:
    """Marcar `NO_DISPONIBLE` **exige motivo**.

    Lo impone un `CHECK`, y aquí se traduce a un `422` legible. Decir «no
    disponible» sin decir por qué deja el informe sin poder explicar la
    limitación, que es exactamente para lo que sirve el campo.
    """
    actual = (
        s.execute(text(f"{_SOLICITUD} WHERE d.id = :i"), {"i": str(item_id)}).mappings().first()  # noqa: S608
    )
    if actual is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Línea de solicitud no encontrada")
    # `If-Match` opcional: la checklist la repasa una persona a la vez, y las
    # importaciones escriben sin haber leído. Si viene, se honra.
    cc.comprobar(
        request,
        s,
        tabla="doc_request_item",
        fila_id=item_id,
        version_actual=actual["row_version"],
        que="una línea de la checklist",
    )

    cambios = cuerpo.model_dump(exclude_unset=True)
    nuevo_estado = cambios.get("status", actual["status"])
    motivo = cambios.get("unavailable_reason", actual["unavailable_reason"])
    if nuevo_estado == "NO_DISPONIBLE" and not (motivo or "").strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Marcar un documento como no disponible exige explicar por qué: "
            "es lo que se declara como limitación en el informe",
        )
    if not cambios:
        cc.poner(respuesta, actual["row_version"])
        return dict(actual)

    piezas = [
        "status = CAST(:status AS doc_request_status)" if c == "status" else f"{c} = :{c}"
        for c in cambios
    ]
    # Marcar «recibida» sin fecha dejaría el checklist sin saber cuándo llegó.
    if nuevo_estado == "RECIBIDA" and "received_at" not in cambios:
        piezas.append("received_at = COALESCE(received_at, now())")
    s.execute(
        text(f"UPDATE doc_request_item SET {', '.join(piezas)} WHERE id = :_id"),  # noqa: S608
        {**cambios, "_id": str(item_id)},
    )
    nuevo = dict(
        s.execute(text(f"{_SOLICITUD} WHERE d.id = :i"), {"i": str(item_id)}).mappings().one()  # noqa: S608
    )
    cc.poner(respuesta, nuevo["row_version"])
    return nuevo


# ─────────────────────────────────────────────────────────────────────────────
#  Enlace al repositorio documental del cliente
# ─────────────────────────────────────────────────────────────────────────────


class EnlaceVdr(BaseModel):
    """`[REC]` **No hay campo de credenciales, y es deliberado.**

    Guardar la contraseña de un repositorio de terceros multiplicaría la
    superficie de riesgo sin aportar nada: el enlace y a quién pedir acceso
    bastan para trabajar.
    """

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)
    provider: str | None = Field(default=None, max_length=120)
    access_notes: str | None = None
    expires_at: Any | None = None


@router.post("/projects/{project_id}/vdr-link", status_code=status.HTTP_201_CREATED)
def fijar_enlace_vdr(
    project_id: uuid.UUID, cuerpo: EnlaceVdr, s: SesionDep, usuario: UsuarioDep
) -> Any:
    """Sustituye el enlace vigente. El anterior se conserva como histórico:
    saber a qué repositorio se accedió y cuándo forma parte de la trazabilidad
    del encargo."""
    fase = _fase(s, project_id, PhaseCode.VDR)
    s.execute(
        text("UPDATE vdr_link SET is_active = FALSE WHERE project_phase_id = :f AND is_active"),
        {"f": str(fase)},
    )
    nuevo = s.execute(
        text(
            "INSERT INTO vdr_link (organization_id, project_phase_id, provider, url, "
            "access_notes, granted_at, expires_at, is_active) "
            "VALUES (:o, :f, :p, :u, :n, now(), :e, TRUE) RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "f": str(fase),
            "p": cuerpo.provider,
            "u": cuerpo.url,
            "n": cuerpo.access_notes,
            "e": cuerpo.expires_at,
        },
    ).scalar_one()
    return {"id": nuevo, **cuerpo.model_dump()}


@router.get("/projects/{project_id}/vdr-link")
def obtener_enlace_vdr(project_id: uuid.UUID, s: SesionDep) -> Any:
    fase = _fase(s, project_id, PhaseCode.VDR)
    fila = (
        s.execute(
            text(
                "SELECT id, provider, url, access_notes, granted_at, expires_at "
                "FROM vdr_link WHERE project_phase_id = :f AND is_active"
            ),
            {"f": str(fase)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay ningún enlace activo")
    return dict(fila)


# ─────────────────────────────────────────────────────────────────────────────
#  Visitas
# ─────────────────────────────────────────────────────────────────────────────


class Visita(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: uuid.UUID
    scheduled_date: date | None = None
    led_by: uuid.UUID | None = None


class ActualizarVisita(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VisitStatus | None = None
    scheduled_date: date | None = None
    actual_date: date | None = None
    led_by: uuid.UUID | None = None
    #: `[REQ]` Las limitaciones de acceso son de las que más pesan en el
    #: informe: «no se pudo acceder a la cubierta» cambia lo que se puede
    #: afirmar sobre ella.
    access_limitations: str | None = None
    summary: str | None = None


class VisitaLeida(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    asset_name: str
    status: str
    scheduled_date: date | None
    actual_date: date | None
    led_by: uuid.UUID | None
    access_limitations: str | None
    summary: str | None


_VISITA = """
    SELECT v.id, v.asset_id, a.name AS asset_name, CAST(v.status AS text) AS status,
           v.scheduled_date, v.actual_date, v.led_by, v.access_limitations, v.summary
    FROM asset_visit v JOIN asset a ON a.id = v.asset_id
"""


@router.post(
    "/projects/{project_id}/visits", status_code=status.HTTP_201_CREATED, response_model=VisitaLeida
)
def programar_visita(
    project_id: uuid.UUID, cuerpo: Visita, s: SesionDep, usuario: UsuarioDep
) -> Any:
    """Una visita por activo. El estado avanza solo si hay fecha: lo impone un
    `CHECK`, porque «agendado» sin fecha no es agendado."""
    existe = s.execute(
        text("SELECT 1 FROM asset WHERE id = :a AND project_id = :p AND deleted_at IS NULL"),
        {"a": str(cuerpo.asset_id), "p": str(project_id)},
    ).first()
    if existe is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "El activo no es de este proyecto"
        )

    nuevo = s.execute(
        text(
            "INSERT INTO asset_visit (organization_id, project_id, asset_id, status, "
            "scheduled_date, led_by) "
            "VALUES (:o, :p, :a, CAST(:e AS visit_status), :f, :l) RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "p": str(project_id),
            "a": str(cuerpo.asset_id),
            "e": "AGENDADO" if cuerpo.scheduled_date else "PENDIENTE_DEFINIR",
            "f": cuerpo.scheduled_date,
            "l": str(cuerpo.led_by) if cuerpo.led_by else None,
        },
    ).scalar_one()
    return dict(s.execute(text(f"{_VISITA} WHERE v.id = :i"), {"i": str(nuevo)}).mappings().one())  # noqa: S608


@router.get("/projects/{project_id}/visits", response_model=list[VisitaLeida])
def listar_visitas(project_id: uuid.UUID, s: SesionDep) -> Any:
    filas = (
        s.execute(
            text(f"{_VISITA} WHERE v.project_id = :p ORDER BY v.scheduled_date NULLS LAST, a.name"),  # noqa: S608
            {"p": str(project_id)},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.patch("/visits/{visit_id}", response_model=VisitaLeida)
def actualizar_visita(visit_id: uuid.UUID, cuerpo: ActualizarVisita, s: SesionDep) -> Any:
    actual = (
        s.execute(text(f"{_VISITA} WHERE v.id = :i"), {"i": str(visit_id)}).mappings().first()  # noqa: S608
    )
    if actual is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Visita no encontrada")
    cambios = cuerpo.model_dump(exclude_unset=True)
    if not cambios:
        return dict(actual)

    nuevo_estado = cambios.get("status", actual["status"])
    fecha_real = cambios.get("actual_date", actual["actual_date"])
    if nuevo_estado == "VISITADO" and fecha_real is None:
        # La fecha real es la que fecha el informe: «visitado» sin ella deja el
        # documento sin poder decir cuándo se vio lo que describe.
        cambios["actual_date"] = date.today()
    if nuevo_estado == "AGENDADO" and not (
        cambios.get("scheduled_date") or actual["scheduled_date"]
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Agendar una visita exige fecha prevista"
        )

    piezas = [
        "status = CAST(:status AS visit_status)" if c == "status" else f"{c} = :{c}"
        for c in cambios
    ]
    s.execute(
        text(f"UPDATE asset_visit SET {', '.join(piezas)} WHERE id = :_id"),  # noqa: S608
        {**cambios, "_id": str(visit_id)},
    )
    return dict(
        s.execute(text(f"{_VISITA} WHERE v.id = :i"), {"i": str(visit_id)}).mappings().one()
    )  # noqa: S608


# ─────────────────────────────────────────────────────────────────────────────
#  Rondas de preguntas y respuestas
# ─────────────────────────────────────────────────────────────────────────────


class NuevaRonda(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=240)
    notes: str | None = None


class Pregunta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    asset_id: uuid.UUID | None = None


class Respuesta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str | None = None
    status: QaQuestionStatus | None = None


class PreguntaLeida(BaseModel):
    id: uuid.UUID
    number: int
    question: str
    answer: str | None
    status: str
    asset_id: uuid.UUID | None
    affects_report_limitations: bool


class Ronda(BaseModel):
    id: uuid.UUID
    round_number: int
    title: str | None
    status: str
    sent_at: Any | None
    answered_at: Any | None
    questions: list[PreguntaLeida] = Field(default_factory=list)


def _leer_ronda(s: Session, ronda_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text(
                "SELECT id, round_number, title, CAST(status AS text) AS status, sent_at, "
                "answered_at FROM qa_round WHERE id = :i"
            ),
            {"i": str(ronda_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ronda no encontrada")
    preguntas = (
        s.execute(
            text(
                "SELECT id, number, question, answer, CAST(status AS text) AS status, asset_id, "
                "affects_report_limitations FROM qa_question WHERE qa_round_id = :r ORDER BY number"
            ),
            {"r": str(ronda_id)},
        )
        .mappings()
        .all()
    )
    return {**dict(fila), "questions": [dict(p) for p in preguntas]}


@router.post(
    "/projects/{project_id}/qa-rounds", status_code=status.HTTP_201_CREATED, response_model=Ronda
)
def abrir_ronda(
    project_id: uuid.UUID, cuerpo: NuevaRonda, s: SesionDep, usuario: UsuarioDep
) -> Any:
    """El número de ronda lo pone el servidor.

    Dejarlo al cliente produciría dos «ronda 2» en cuanto dos personas abrieran
    una a la vez, y el índice único lo rechazaría con un error incomprensible.
    """
    fase = _fase(s, project_id, PhaseCode.QA)
    nuevo = s.execute(
        text(
            "INSERT INTO qa_round (organization_id, project_phase_id, round_number, title, notes) "
            "SELECT :o, :f, COALESCE(MAX(round_number), 0) + 1, :t, :n "
            "FROM qa_round WHERE project_phase_id = :f RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "f": str(fase),
            "t": cuerpo.title,
            "n": cuerpo.notes,
        },
    ).scalar_one()
    return _leer_ronda(s, nuevo)


@router.get("/projects/{project_id}/qa-rounds", response_model=list[Ronda])
def listar_rondas(project_id: uuid.UUID, s: SesionDep) -> Any:
    fase = _fase(s, project_id, PhaseCode.QA)
    ids = (
        s.execute(
            text("SELECT id FROM qa_round WHERE project_phase_id = :f ORDER BY round_number"),
            {"f": str(fase)},
        )
        .scalars()
        .all()
    )
    return [_leer_ronda(s, i) for i in ids]


@router.post(
    "/qa-rounds/{round_id}/questions",
    status_code=status.HTTP_201_CREATED,
    response_model=Ronda,
)
def anadir_pregunta(
    round_id: uuid.UUID, cuerpo: Pregunta, s: SesionDep, usuario: UsuarioDep
) -> Any:
    _leer_ronda(s, round_id)
    s.execute(
        text(
            "INSERT INTO qa_question (organization_id, qa_round_id, asset_id, number, question) "
            "SELECT :o, :r, :a, COALESCE(MAX(number), 0) + 1, :q "
            "FROM qa_question WHERE qa_round_id = :r"
        ),
        {
            "o": str(usuario.organization_id),
            "r": str(round_id),
            "a": str(cuerpo.asset_id) if cuerpo.asset_id else None,
            "q": cuerpo.question,
        },
    )
    return _leer_ronda(s, round_id)


@router.patch("/qa-questions/{question_id}", response_model=Ronda)
def responder(question_id: uuid.UUID, cuerpo: Respuesta, s: SesionDep) -> Any:
    """Marcar `RESPONDIDA` sin respuesta cerraría la ronda en falso.

    Lo impide un `CHECK`; aquí se traduce a un `422` que dice qué falta.
    """
    ronda = s.execute(
        text("SELECT qa_round_id FROM qa_question WHERE id = :i"), {"i": str(question_id)}
    ).scalar()
    if ronda is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pregunta no encontrada")

    cambios = cuerpo.model_dump(exclude_unset=True)
    if "answer" in cambios and cambios["answer"] and "status" not in cambios:
        # Responder es lo que cambia el estado: pedir dos campos para una sola
        # acción es la clase de fricción que hace que la gente no lo rellene.
        cambios["status"] = "RESPONDIDA"
    if cambios.get("status") == "RESPONDIDA" and not (cambios.get("answer") or "").strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Marcar una pregunta como respondida exige escribir la respuesta",
        )
    if cambios:
        piezas = [
            "status = CAST(:status AS qa_question_status)" if c == "status" else f"{c} = :{c}"
            for c in cambios
        ]
        if cambios.get("status") == "RESPONDIDA":
            piezas.append("answered_at = now()")
        s.execute(
            text(f"UPDATE qa_question SET {', '.join(piezas)} WHERE id = :_id"),  # noqa: S608
            {**cambios, "_id": str(question_id)},
        )
    return _leer_ronda(s, ronda)


class EstadoDeRonda(BaseModel):
    status: str


@router.post("/qa-rounds/{round_id}/status", response_model=Ronda)
def cambiar_estado_de_ronda(round_id: uuid.UUID, cuerpo: EstadoDeRonda, s: SesionDep) -> Any:
    """Cerrar una ronda **no obliga a que todo esté respondido**.

    Lo que queda sin contestar pasa a `SIN_RESPUESTA` y aparece como limitación
    del informe. Bloquear el cierre obligaría a inventar respuestas para poder
    avanzar, que es peor que declarar honestamente que no las hubo.
    """
    ronda = _leer_ronda(s, round_id)
    if cuerpo.status not in ("ABIERTA", "ENVIADA", "RESPONDIDA", "CERRADA"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Estado de ronda desconocido")

    s.execute(
        text(
            "UPDATE qa_round SET status = CAST(:e AS qa_round_status), "
            "sent_at = CASE WHEN :e = 'ENVIADA' THEN COALESCE(sent_at, now()) ELSE sent_at END, "
            "answered_at = CASE WHEN :e IN ('RESPONDIDA', 'CERRADA') "
            "                   THEN COALESCE(answered_at, now()) ELSE answered_at END "
            "WHERE id = :i"
        ),
        {"e": cuerpo.status, "i": str(round_id)},
    )
    if cuerpo.status == "CERRADA":
        s.execute(
            text(
                "UPDATE qa_question SET status = 'SIN_RESPUESTA' "
                "WHERE qa_round_id = :r AND status = 'ABIERTA'"
            ),
            {"r": str(round_id)},
        )
    del ronda
    return _leer_ronda(s, round_id)


# ─────────────────────────────────────────────────────────────────────────────
#  Hitos de fase
# ─────────────────────────────────────────────────────────────────────────────


class Hito(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase_code: PhaseCode
    event_date: date
    counterparty: str | None = Field(default=None, max_length=200)
    attendees: list[str] = Field(default_factory=list)
    outcome: str | None = None
    notes: str | None = None


@router.post("/projects/{project_id}/phase-events", status_code=status.HTTP_201_CREATED)
def registrar_hito(project_id: uuid.UUID, cuerpo: Hito, s: SesionDep, usuario: UsuarioDep) -> Any:
    """La presentación y la defensa del informe se documentan aquí: fecha,
    interlocutor y resultado. Es lo que convierte «se presentó» en algo
    verificable meses después."""
    import json

    fase = _fase(s, project_id, cuerpo.phase_code)
    nuevo = s.execute(
        text(
            "INSERT INTO phase_event (organization_id, project_phase_id, event_date, "
            "counterparty, attendees, outcome, notes) "
            "VALUES (:o, :f, :d, :c, CAST(:a AS jsonb), :r, :n) RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "f": str(fase),
            "d": cuerpo.event_date,
            "c": cuerpo.counterparty,
            "a": json.dumps(cuerpo.attendees, ensure_ascii=False),
            "r": cuerpo.outcome,
            "n": cuerpo.notes,
        },
    ).scalar_one()
    return {"id": nuevo, **cuerpo.model_dump(mode="json")}


@router.get("/projects/{project_id}/phase-events")
def listar_hitos(project_id: uuid.UUID, s: SesionDep) -> Any:
    filas = (
        s.execute(
            text(
                "SELECT e.id, pd.code AS phase_code, e.event_date, e.counterparty, e.attendees, "
                "e.outcome, e.notes FROM phase_event e "
                "JOIN project_phase ph ON ph.id = e.project_phase_id "
                "JOIN phase_definition pd ON pd.id = ph.phase_definition_id "
                "WHERE ph.project_id = :p ORDER BY e.event_date DESC"
            ),
            {"p": str(project_id)},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]

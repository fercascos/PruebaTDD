"""Orquesta una revisión: comprueba el permiso, llama al proveedor, guarda.

La regla que estructura el módulo entero: **lo que sale de aquí son propuestas**.
Ninguna función de este fichero toca `doc_request_item.status`, y ninguna marca
una observación como aceptada sin recibir el usuario que la acepta. La base lo
respalda con dos restricciones (`project_revision_ia_con_autoria` y
`doc_finding_decidida_con_persona`), pero el servicio no se apoya en que la
base falle: comprueba antes y da un error que se entiende.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.revision_documental.puerto import (
    Comprobacion,
    Dictamen,
    Documento,
    RevisionNoDisponible,
    Revisor,
    Veredicto,
)


class RevisionNoAutorizada(PermissionError):
    """El encargo no tiene encendida la revisión con IA.

    `[REQ]` No es un fallo técnico ni un problema de rol: es la ausencia de la
    autorización expresa que el cliente exige por encargo. Se distingue de un
    403 corriente para que el mensaje pueda decir qué falta y quién lo enciende.
    """


class DocumentoDemasiadoSensible(PermissionError):
    """`[REQ]` Un documento `RESTRINGIDO` no se manda a un proveedor de IA.

    El interruptor del encargo es la autorización expresa que el cliente exige,
    y no basta para éste. `RESTRINGIDO` es el nivel que la propia aplicación
    define como «solo lo descarga quien administra o dirige»: mandárselo a un
    tercero mientras un consultor del equipo no puede ni abrirlo es incoherente,
    y la incoherencia se resolvería siempre por el lado malo.

    Es el caso del **plan de autoprotección**, que nace `RESTRINGIDO`: lleva
    procedimientos de emergencia, puntos de reunión y datos de las personas con
    responsabilidad en una emergencia.

    `[REC]` No hay un segundo interruptor. Si en un encargo concreto hay que
    revisarlo, se baja su clasificación a mano —lo cual queda en `audit_log` con
    quién y cuándo— y entonces se revisa. Una decisión así tiene que dejar
    rastro; un interruptor más lo convertiría en un clic sin memoria.
    """


class DecisionInvalida(ValueError):
    """Se ha intentado decidir sobre una propuesta que ya estaba decidida."""


@dataclass(frozen=True, slots=True)
class Permiso:
    """El estado del interruptor de un encargo, con su autoría."""

    activo: bool
    desde: Any | None = None
    por: uuid.UUID | None = None


def permiso_de(s: Session, project_id: uuid.UUID) -> Permiso:
    fila = (
        s.execute(
            text(
                "SELECT ai_doc_review_enabled, ai_doc_review_enabled_at, "
                "ai_doc_review_enabled_by FROM project WHERE id = :p"
            ),
            {"p": str(project_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        return Permiso(activo=False)
    return Permiso(
        activo=bool(fila["ai_doc_review_enabled"]),
        desde=fila["ai_doc_review_enabled_at"],
        por=fila["ai_doc_review_enabled_by"],
    )


def autorizar(s: Session, project_id: uuid.UUID, *, usuario_id: uuid.UUID, activo: bool) -> Permiso:
    """Enciende o apaga la revisión con IA en un encargo.

    `[REQ]` Encender deja constancia de **quién** y **cuándo**. Apagar borra la
    autoría a la vez que el permiso: dejarla puesta daría a entender que sigue
    autorizado, y el interruptor volvería a encenderse arrastrando una
    autorización vieja.
    """
    if activo:
        s.execute(
            text(
                "UPDATE project SET ai_doc_review_enabled = TRUE, "
                "ai_doc_review_enabled_at = now(), ai_doc_review_enabled_by = :u, "
                "updated_at = now() WHERE id = :p"
            ),
            {"u": str(usuario_id), "p": str(project_id)},
        )
    else:
        s.execute(
            text(
                "UPDATE project SET ai_doc_review_enabled = FALSE, "
                "ai_doc_review_enabled_at = NULL, ai_doc_review_enabled_by = NULL, "
                "updated_at = now() WHERE id = :p"
            ),
            {"p": str(project_id)},
        )
    return permiso_de(s, project_id)


def comprobaciones_vigentes(s: Session) -> list[Comprobacion]:
    """Los criterios activos, en su orden. Salen de la base, no del código."""
    filas = (
        s.execute(
            text(
                "SELECT code, name_es, description_es FROM doc_check_type "
                "WHERE is_active ORDER BY display_order, code"
            )
        )
        .mappings()
        .all()
    )
    return [
        Comprobacion(codigo=f["code"], nombre=f["name_es"], descripcion=f["description_es"])
        for f in filas
    ]


def _documento_para_revisar(s: Session, document_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text(
                "SELECT d.id, d.project_id, d.organization_id, d.doc_request_item_id, "
                "d.display_name, d.original_filename, d.file_extension, d.mime_type, "
                "d.sha256, d.status, CAST(d.confidentiality AS text) AS confidentiality, "
                "o.storage_key, i.title AS solicitado, "
                "c.name_es AS categoria "
                "FROM document d "
                "JOIN stored_object o ON o.id = d.stored_object_id "
                "LEFT JOIN doc_request_item i ON i.id = d.doc_request_item_id "
                "LEFT JOIN doc_request_category c ON c.id = i.category_id "
                "WHERE d.id = :i AND d.deleted_at IS NULL"
            ),
            {"i": str(document_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise LookupError("Documento no encontrado")
    return dict(fila)


def revisar_documento(  # noqa: PLR0913 — cada uno es una dependencia distinta
    s: Session,
    document_id: uuid.UUID,
    *,
    revisor: Revisor,
    almacen: Any,
    usuario_id: uuid.UUID,
    fecha_encargo: date | None = None,
) -> uuid.UUID:
    """Revisa un documento y guarda el resultado como propuestas.

    Devuelve el id de la revisión. Levanta `RevisionNoAutorizada` si el encargo
    no la tiene encendida, y deja la revisión en `FALLIDA` **con su motivo** si
    el proveedor no puede hacerla: un fallo silencioso dejaría a quien lo pidió
    esperando una respuesta que no va a llegar.
    """
    doc = _documento_para_revisar(s, document_id)
    permiso = permiso_de(s, uuid.UUID(str(doc["project_id"])))
    if not permiso.activo:
        raise RevisionNoAutorizada(
            "Este encargo no tiene activada la revisión de documentación con IA. "
            "La activa quien dirige el proyecto, y queda registrado quién lo hizo."
        )
    # `[REQ]` Y el interruptor del encargo NO basta para un documento
    # RESTRINGIDO. Esto faltaba: la comprobación de confidencialidad estaba en
    # `descargar()` y no aquí, así que un documento que un consultor del equipo
    # no puede ni abrir sí se podía mandar a un proveedor externo con solo el
    # interruptor del encargo encendido. Se descubrió al clasificar el plan de
    # autoprotección como RESTRINGIDO.
    if doc["confidentiality"] == "RESTRINGIDO":
        raise DocumentoDemasiadoSensible(
            f"«{doc['display_name']}» está clasificado como RESTRINGIDO y no se envía a "
            "ningún proveedor de IA, ni con la revisión del encargo activada. Es el nivel "
            "que solo puede descargar quien administra o dirige. Si hay que revisarlo, "
            "baje su clasificación primero: quedará registrado quién lo hizo."
        )

    criterios = comprobaciones_vigentes(s)
    revision_id = uuid.UUID(
        str(
            s.execute(
                text(
                    "INSERT INTO doc_review (organization_id, project_id, document_id, "
                    "doc_request_item_id, status, provider, document_sha256, requested_by, "
                    "started_at) VALUES (:o, :p, :d, :i, 'EN_CURSO', :prov, :sha, :u, now()) "
                    "RETURNING id"
                ),
                {
                    "o": str(doc["organization_id"]),
                    "p": str(doc["project_id"]),
                    "d": str(document_id),
                    "i": str(doc["doc_request_item_id"]) if doc["doc_request_item_id"] else None,
                    "prov": revisor.nombre,
                    "sha": doc["sha256"],
                    "u": str(usuario_id),
                },
            ).scalar_one()
        )
    )

    try:
        contenido = almacen.leer(doc["storage_key"])
        dictamen = revisor.revisar(
            Documento(
                nombre=f"{doc['display_name']}.{doc['file_extension']}",
                mime_type=doc["mime_type"],
                contenido=contenido,
                sha256=doc["sha256"],
                solicitado=doc["solicitado"],
                categoria=doc["categoria"],
            ),
            criterios,
            fecha_encargo=fecha_encargo,
        )
    except (RevisionNoDisponible, OSError, KeyError) as exc:
        s.execute(
            text(
                "UPDATE doc_review SET status = 'FALLIDA', finished_at = now(), "
                "error_message = :e WHERE id = :i"
            ),
            {"e": str(exc) or exc.__class__.__name__, "i": str(revision_id)},
        )
        return revision_id

    _guardar_observaciones(s, revision_id, doc["organization_id"], dictamen)
    s.execute(
        text(
            "UPDATE doc_review SET status = 'COMPLETADA', finished_at = now(), "
            "model = :m, is_simulated = :sim WHERE id = :i"
        ),
        {"m": dictamen.modelo, "sim": dictamen.simulado, "i": str(revision_id)},
    )
    return revision_id


def _guardar_observaciones(
    s: Session, revision_id: uuid.UUID, organization_id: Any, dictamen: Dictamen
) -> None:
    """Cada observación entra como `PROPUESTA`. No hay otro camino.

    Un criterio que la base no conozca se **descarta con su motivo** en vez de
    reventar la revisión entera: el proveedor podría devolver un código viejo
    tras desactivarse un criterio, y perder las otras tres observaciones por eso
    sería desproporcionado.
    """
    for obs in dictamen.observaciones:
        check_id = s.execute(
            text("SELECT id FROM doc_check_type WHERE code = :c AND is_active"),
            {"c": obs.comprobacion},
        ).scalar_one_or_none()
        if check_id is None:
            continue
        s.execute(
            text(
                "INSERT INTO doc_review_finding (organization_id, doc_review_id, "
                "check_type_id, verdict, summary, evidence_text, evidence_page, confidence) "
                "VALUES (:o, :r, :c, CAST(:v AS doc_finding_verdict), :s, :e, :p, :cf)"
            ),
            {
                "o": str(organization_id),
                "r": str(revision_id),
                "c": str(check_id),
                "v": Veredicto(obs.veredicto).value,
                "s": obs.resumen,
                "e": obs.evidencia,
                "p": obs.pagina,
                "cf": obs.confianza,
            },
        )


def decidir(
    s: Session,
    finding_id: uuid.UUID,
    *,
    aceptar: bool,
    usuario_id: uuid.UUID,
    nota: str | None = None,
) -> None:
    """Una persona acepta o rechaza una propuesta.

    `[REQ]` Este es el único camino por el que una observación deja de ser
    propuesta, y exige un usuario. No existe una versión «del sistema».

    Decidir **no cambia** el estado de la línea de la checklist. Aceptar «este
    certificado está caducado» no convierte la línea en `NO_DISPONIBLE`: dice
    que la observación es cierta. Qué hacer con ella —pedir el documento otra
    vez, abrir un hallazgo, anotarlo como limitación— lo decide quien lleva el
    encargo, con la información delante.
    """
    actual = s.execute(
        text("SELECT CAST(decision AS text) FROM doc_review_finding WHERE id = :i"),
        {"i": str(finding_id)},
    ).scalar_one_or_none()
    if actual is None:
        raise LookupError("Observación no encontrada")
    if actual != "PROPUESTA":
        raise DecisionInvalida(
            f"Esta observación ya está {actual.lower()}: no se decide dos veces."
        )

    s.execute(
        text(
            "UPDATE doc_review_finding SET decision = CAST(:d AS doc_finding_decision), "
            "decided_by = :u, decided_at = now(), decision_note = :n WHERE id = :i"
        ),
        {
            "d": "ACEPTADA" if aceptar else "RECHAZADA",
            "u": str(usuario_id),
            "n": nota,
            "i": str(finding_id),
        },
    )

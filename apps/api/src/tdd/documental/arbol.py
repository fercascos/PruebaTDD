"""El árbol documental del activo `[REQ]` §3.2 b.

El cliente entregó su hoja v2 con **73 nodos en tres niveles**, de los que 60 no
tienen hijos. Un nodo sin hijos es una **casilla**: lleva estado, lleva motivo
cuando no hay documento y lleva los ficheros colgando. Los otros 13 solo agrupan,
y por eso no se les puede poner estado —intentarlo da `422`, no un estado que
nadie sabría interpretar después—.

## Una casilla sin fila no es un error, es lo normal

El árbol tiene 60 casillas y un proyecto empieza sin ninguna tocada. Crear 60
filas vacías por activo al dar de alta el proyecto llenaría la tabla de ruido y
obligaría a mantenerlas sincronizadas si el árbol cambiase. Aquí la fila
**aparece cuando alguien hace algo**: pone un estado o adjunta un documento.

Eso da seis situaciones, no cinco:

| En pantalla | En la base |
|---|---|
| Pendiente de pedir | no hay fila |
| Solicitada | `SOLICITADA` |
| Recibida | `RECIBIDA` |
| Recibida en parte | `PARCIAL` |
| No disponible | `NO_DISPONIBLE` |
| No aplica | `NO_APLICA` |

`[REC]` **`PARCIAL` no estaba en la hoja del cliente**, que define cuatro
estados. Se mantiene porque ya existía en la base y porque cuenta como limitación
del informe igual que `NO_DISPONIBLE`: recibir tres de los ocho boletines
eléctricos no es haberlos recibido, y el sitio donde eso se declara es el
informe. `[PDV]` Está sin validar con el cliente.

## Lo que NO hace este módulo

**Subir ficheros.** Eso ya lo hace `POST /documents` con `doc_request_item_id`, y
desde hoy clasifica el documento por el código del nodo. Duplicar la subida aquí
habría significado dos caminos con dos validaciones de antivirus y de MIME.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core import concurrencia as cc
from tdd.core.deps import SesionDep, UsuarioDep
from tdd.phases.engine import PhaseCode
from tdd.phases.operations import DocRequestStatus

router = APIRouter(tags=["Árbol documental"])


class DocumentoDeCasilla(BaseModel):
    """Lo justo para pintar la lista de adjuntos y poder descargarlos."""

    id: uuid.UUID
    display_name: str
    doc_type: str
    confidentiality: str
    version_number: int
    uploaded_at: str


class Nodo(BaseModel):
    """Un nodo del árbol, con lo que haya pasado en él si es casilla."""

    code: str
    name_es: str
    category_id: uuid.UUID
    level: int
    parent_code: str | None
    es_casilla: bool

    #: `None` mientras nadie haya tocado la casilla. No es «falta un dato»: es
    #: «pendiente de pedir», que es por donde empiezan las 60.
    item_id: uuid.UUID | None = None
    status: str | None = None
    unavailable_reason: str | None = None
    received_at: str | None = None
    #: Lo calcula la base (`affects_report_limitations`). Viaja para que la
    #: pantalla pueda avisar de lo que va a acabar en las limitaciones del
    #: informe sin repetir aquí la regla de qué estados cuentan.
    limita_el_informe: bool = False
    row_version: int | None = None
    documentos: list[DocumentoDeCasilla] = Field(default_factory=list)


class EstadoDeCasilla(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DocRequestStatus
    unavailable_reason: str | None = None


def _activo(s: Session, asset_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text("SELECT id, project_id FROM asset WHERE id = :i AND deleted_at IS NULL"),
            {"i": str(asset_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activo no encontrado")
    return dict(fila)


def _fase_documental(s: Session, project_id: uuid.UUID) -> uuid.UUID:
    """La fase de solicitud de documentación del proyecto, exigiendo que exista.

    Se repite la consulta de `phases.operations._fase` en vez de importarla
    porque aquí el `404` tiene que decir otra cosa: quien mira el árbol de un
    activo no ha pedido una fase, ha abierto una pestaña, y «el proyecto no tiene
    la fase SOLICITUD_DOCUMENTACION» sin más no le dice qué hacer.
    """
    fila = s.execute(
        text(
            "SELECT ph.id FROM project_phase ph "
            "JOIN phase_definition pd ON pd.id = ph.phase_definition_id "
            "WHERE ph.project_id = :p AND pd.code = :c"
        ),
        {"p": str(project_id), "c": PhaseCode.SOLICITUD_DOCUMENTACION.value},
    ).scalar()
    if fila is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Este proyecto no tiene activada la fase de solicitud de documentación, "
            "que es donde vive el árbol. Actívela en la pestaña de fases del proyecto.",
        )
    return uuid.UUID(str(fila))


_NODOS = """
    SELECT id AS category_id, code, name_es
    FROM doc_request_category
    WHERE organization_id IS NULL AND code ~ '^S[0-9]'
    ORDER BY display_order, code
"""

_CASILLAS = """
    SELECT d.id AS item_id, d.category_id, CAST(d.status AS text) AS status,
           d.unavailable_reason, CAST(d.received_at AS text) AS received_at,
           d.affects_report_limitations, d.row_version
    FROM doc_request_item d
    WHERE d.project_phase_id = :f AND d.asset_id = :a
"""

_ADJUNTOS = """
    SELECT doc.doc_request_item_id, doc.id, doc.display_name,
           CAST(doc.doc_type AS text) AS doc_type,
           CAST(doc.confidentiality AS text) AS confidentiality,
           doc.version_number, CAST(doc.uploaded_at AS text) AS uploaded_at
    FROM document doc
    WHERE doc.asset_id = :a AND doc.deleted_at IS NULL
      AND doc.doc_request_item_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM document s2
                      WHERE s2.supersedes_document_id = doc.id AND s2.deleted_at IS NULL)
    ORDER BY doc.uploaded_at DESC
"""


def _leer_arbol(s: Session, asset_id: uuid.UUID, fase: uuid.UUID) -> list[dict[str, Any]]:
    nodos = [dict(f) for f in s.execute(text(_NODOS)).mappings().all()]
    if not nodos:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El árbol documental no está sembrado en esta base de datos. "
            "Ejecute `python3 -m tdd.db.sembrar`.",
        )

    casillas = {
        str(f["category_id"]): dict(f)
        for f in s.execute(text(_CASILLAS), {"f": str(fase), "a": str(asset_id)}).mappings().all()
    }
    adjuntos: dict[str, list[dict[str, Any]]] = {}
    for f in s.execute(text(_ADJUNTOS), {"a": str(asset_id)}).mappings().all():
        adjuntos.setdefault(str(f["doc_request_item_id"]), []).append(
            {k: v for k, v in dict(f).items() if k != "doc_request_item_id"}
        )

    con_hijos = {n["code"].rsplit(".", 1)[0] for n in nodos if "." in str(n["code"])}
    salida: list[dict[str, Any]] = []
    for n in nodos:
        codigo = str(n["code"])
        fila = casillas.get(str(n["category_id"]))
        salida.append(
            {
                **n,
                "level": codigo.count(".") + 1,
                "parent_code": codigo.rsplit(".", 1)[0] if "." in codigo else None,
                "es_casilla": codigo not in con_hijos,
                "item_id": fila["item_id"] if fila else None,
                "status": fila["status"] if fila else None,
                "unavailable_reason": fila["unavailable_reason"] if fila else None,
                "received_at": fila["received_at"] if fila else None,
                "limita_el_informe": bool(fila["affects_report_limitations"]) if fila else False,
                "row_version": fila["row_version"] if fila else None,
                "documentos": adjuntos.get(str(fila["item_id"]), []) if fila else [],
            }
        )
    return salida


@router.get("/assets/{asset_id}/doc-tree", response_model=list[Nodo])
def arbol(asset_id: uuid.UUID, s: SesionDep) -> Any:
    """Los 73 nodos del activo, en el orden de la hoja del cliente.

    Se devuelven **siempre los 73**, tenga o no algo cada casilla: el árbol es
    la lista de lo que hay que pedir, y una casilla vacía es precisamente la que
    hay que mirar. Devolver solo las tocadas dejaría la pantalla enseñando lo
    que ya está hecho.
    """
    activo = _activo(s, asset_id)
    fase = _fase_documental(s, uuid.UUID(str(activo["project_id"])))
    return _leer_arbol(s, asset_id, fase)


@router.put("/assets/{asset_id}/doc-tree/{code}", response_model=Nodo)
def fijar_estado(
    asset_id: uuid.UUID,
    code: str,
    cuerpo: EstadoDeCasilla,
    s: SesionDep,
    usuario: UsuarioDep,
    request: Request,
    respuesta: Response,
) -> Any:
    """Pone el estado de una casilla, creándola si es la primera vez.

    Dos reglas que la base ya impone y que aquí se traducen a mensajes:

    * **Un nodo que agrupa no tiene estado.** Marcar `S1.1` como recibida cuando
      cuelgan cuatro licencias no dice nada de ninguna de las cuatro.
    * **`NO_DISPONIBLE` exige motivo.** Es lo que se declara como limitación del
      informe, y sin él la limitación se queda en «falta algo».
    """
    activo = _activo(s, asset_id)
    fase = _fase_documental(s, uuid.UUID(str(activo["project_id"])))

    nodo = (
        s.execute(
            text(
                "SELECT id, name_es FROM doc_request_category "
                "WHERE organization_id IS NULL AND code = :c"
            ),
            {"c": code},
        )
        .mappings()
        .first()
    )
    if nodo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"El árbol documental no tiene «{code}»")
    hijos = s.execute(
        text(
            "SELECT 1 FROM doc_request_category "
            "WHERE organization_id IS NULL AND code LIKE :p LIMIT 1"
        ),
        {"p": f"{code}.%"},
    ).first()
    if hijos is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"«{code}» agrupa a otros nodos y no lleva estado propio: "
            "el estado se pone en los que cuelgan de él.",
        )

    motivo = (cuerpo.unavailable_reason or "").strip() or None
    if cuerpo.status is DocRequestStatus.NO_DISPONIBLE and not motivo:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Marcar un documento como no disponible exige explicar por qué: "
            "es lo que se declara como limitación en el informe",
        )

    actual = (
        s.execute(
            text(
                "SELECT id, row_version FROM doc_request_item "
                "WHERE project_phase_id = :f AND asset_id = :a AND category_id = :c"
            ),
            {"f": str(fase), "a": str(asset_id), "c": str(nodo["id"])},
        )
        .mappings()
        .first()
    )
    if actual is not None:
        cc.comprobar(
            request,
            s,
            tabla="doc_request_item",
            fila_id=uuid.UUID(str(actual["id"])),
            version_actual=actual["row_version"],
            que="una casilla del árbol documental",
        )
        s.execute(
            text(
                "UPDATE doc_request_item SET status = CAST(:e AS doc_request_status), "
                "unavailable_reason = :m, updated_by = :u, "
                # Marcar «recibida» sin fecha dejaría el árbol sin saber cuándo
                # llegó, y esa fecha es la que se contrasta con la del informe.
                "received_at = CASE WHEN :e IN ('RECIBIDA', 'PARCIAL') "
                "                   THEN COALESCE(received_at, now()) ELSE received_at END "
                "WHERE id = :i"
            ),
            {
                "e": cuerpo.status.value,
                "m": motivo,
                "u": str(usuario.id),
                "i": str(actual["id"]),
            },
        )
    else:
        s.execute(
            text(
                "INSERT INTO doc_request_item (organization_id, project_phase_id, asset_id, "
                "category_id, title, status, unavailable_reason, requested_at, received_at, "
                "display_order, updated_by) "
                "VALUES (:o, :f, :a, :c, :t, CAST(:e AS doc_request_status), :m, now(), "
                "        CASE WHEN :e IN ('RECIBIDA', 'PARCIAL') THEN now() END, :orden, :u)"
            ),
            {
                "o": str(usuario.organization_id),
                "f": str(fase),
                "a": str(asset_id),
                "c": str(nodo["id"]),
                # El título es el nombre del nodo. Se copia y no se deja en la
                # clave ajena porque el nombre del nodo puede cambiar en una
                # revisión de la hoja del cliente, y lo que se pidió en su día
                # tiene que seguir leyéndose como se pidió.
                "t": str(nodo["name_es"])[:240],
                "e": cuerpo.status.value,
                "m": motivo,
                "orden": 0,
                "u": str(usuario.id),
            },
        )

    devuelto = next(n for n in _leer_arbol(s, asset_id, fase) if n["code"] == code)
    if devuelto["row_version"] is not None:
        cc.poner(respuesta, int(devuelto["row_version"]))
    return devuelto

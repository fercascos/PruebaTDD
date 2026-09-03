"""API de extracción: del documento subido a la propuesta que alguien valida."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core.deps import SesionDep, UsuarioDep
from tdd.evidence.router import AlmacenDep
from tdd.extraccion import memoria_tecnica as _registra_memoria  # noqa: F401 — registra al importar
from tdd.extraccion.puerto import Procedencia, SinExtractor, para, tipos_soportados

router = APIRouter(tags=["Extracción documental"])


class PropuestaLeida(BaseModel):
    id: uuid.UUID
    campo: str
    valor: str
    estado: str
    #: La procedencia. Es lo que permite a quien valida ir al documento.
    document_id: uuid.UUID | None
    doc_type: str
    seccion: str | None
    evidencia: str | None
    extractor: str
    es_simulada: bool
    decidida_por: uuid.UUID | None = None
    #: El valor que tiene HOY el activo en ese campo, para poder comparar.
    valor_actual: str | None = None


class ResultadoDeExtraccion(BaseModel):
    document_id: uuid.UUID
    doc_type: str
    extractor: str
    es_simulada: bool
    propuestas: int
    plantas: int
    objetos: int
    desconocidos: dict[str, str]
    avisos: list[str]


def _documento(s: Session, document_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text(
                "SELECT d.id, d.asset_id, CAST(d.doc_type AS text) AS doc_type, "
                "d.stored_object_id, so.storage_key "
                "FROM document d JOIN stored_object so ON so.id = d.stored_object_id "
                "WHERE d.id = :d AND d.deleted_at IS NULL"
            ),
            {"d": str(document_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    return dict(fila)


@router.get("/extraccion/tipos-soportados", response_model=list[str])
def soportados() -> Any:
    """Qué tipos de documento sabe leer hoy la aplicación.

    Se expone para que la pantalla ofrezca el botón de extraer **solo** donde
    va a funcionar. Ofrecerlo en todos y fallar en la mayoría enseña a la gente
    a no pulsarlo.
    """
    return list(tipos_soportados())


@router.post(
    "/documents/{document_id}/extraer",
    status_code=status.HTTP_201_CREATED,
    response_model=ResultadoDeExtraccion,
)
def extraer(
    document_id: uuid.UUID,
    s: SesionDep,
    usuario: UsuarioDep,
    almacen: AlmacenDep,
) -> Any:
    """`[REQ]` Lee el documento con el extractor de **su tipo** y propone.

    No escribe nada en el activo ni en el CAPEX. Deja propuestas pendientes,
    cada una con el documento y el párrafo del que salió, para que el gestor de
    la due diligence las revise y decida.

    `[REQ]` Volver a extraer el mismo documento **sustituye sus propuestas
    pendientes**, no las acumula. Pero **no toca las que ya se decidieron**:
    reabrir algo que una persona ya aceptó o descartó, sin decírselo, es la
    forma más rápida de que deje de fiarse de la pantalla.
    """
    documento = _documento(s, document_id)
    if documento["asset_id"] is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El documento no está asignado a ningún activo: no hay a quién proponerle "
            "los datos. Asígnelo primero.",
        )

    try:
        extractor = para(documento["doc_type"])
    except SinExtractor as exc:
        # 422 y no 500: no es una avería, es que ese tipo todavía no se lee. El
        # mensaje dice cuáles sí, que es lo accionable.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    contenido = almacen.leer(documento["storage_key"])
    aportacion = extractor.leer(
        contenido,
        Procedencia(doc_type=documento["doc_type"], document_id=document_id),
    )

    # Se retiran solo las PENDIENTES de este documento. Las decididas se quedan.
    s.execute(
        text("DELETE FROM propuesta_de_dato WHERE document_id = :d AND estado = 'PENDIENTE'"),
        {"d": str(document_id)},
    )
    decididos = {
        fila[0]
        for fila in s.execute(
            text(
                "SELECT campo FROM propuesta_de_dato "
                "WHERE document_id = :d AND estado <> 'PENDIENTE'"
            ),
            {"d": str(document_id)},
        ).all()
    }

    guardadas = 0
    for campo in aportacion.campos:
        if campo.campo in decididos:
            continue
        s.execute(
            text(
                "INSERT INTO propuesta_de_dato (organization_id, asset_id, campo, valor, "
                "document_id, doc_type, seccion, evidencia, extractor, es_simulada) "
                "VALUES (:o, :a, :c, :v, :d, CAST(:t AS doc_type), :s, :e, :x, :sim)"
            ),
            {
                "o": str(usuario.organization_id),
                "a": str(documento["asset_id"]),
                "c": campo.campo,
                "v": campo.valor,
                "d": str(document_id),
                "t": documento["doc_type"],
                "s": campo.procedencia.seccion,
                "e": campo.procedencia.evidencia,
                "x": aportacion.extractor,
                "sim": aportacion.es_simulada,
            },
        )
        guardadas += 1

    avisos = list(aportacion.avisos)
    if omitidas := len(decididos & {c.campo for c in aportacion.campos}):
        avisos.append(
            f"{omitidas} campos no se han vuelto a proponer porque alguien ya decidió "
            "sobre ellos desde este mismo documento."
        )

    return {
        "document_id": document_id,
        "doc_type": documento["doc_type"],
        "extractor": aportacion.extractor,
        "es_simulada": aportacion.es_simulada,
        "propuestas": guardadas,
        "plantas": len(aportacion.plantas),
        "objetos": len(aportacion.objetos),
        "desconocidos": aportacion.desconocidos,
        "avisos": avisos,
    }


@router.get("/assets/{asset_id}/propuestas", response_model=list[PropuestaLeida])
def listar(
    asset_id: uuid.UUID,
    s: SesionDep,
    estado: str | None = None,
) -> Any:
    """Lo que la documentación propone sobre este activo, sin aplicar.

    Cada fila trae **el valor que el activo tiene hoy** al lado. Sin eso, quien
    valida no puede distinguir «esto completa un hueco» de «esto contradice lo
    que ya había», que son dos decisiones muy distintas.
    """
    filas = (
        s.execute(
            text(
                "SELECT id, campo, valor, CAST(estado AS text) AS estado, document_id, "
                "CAST(doc_type AS text) AS doc_type, seccion, evidencia, extractor, "
                "es_simulada, decidida_por FROM propuesta_de_dato "
                # El `CAST` no es cosmético: sin él PostgreSQL no sabe de qué
                # tipo es el parámetro cuando llega a `NULL` y rechaza la
                # consulta entera. Filtrar por estado es opcional; que no
                # filtrar reviente, no.
                "WHERE asset_id = :a AND (CAST(:e AS text) IS NULL "
                "OR CAST(estado AS text) = CAST(:e AS text)) "
                "ORDER BY campo, created_at"
            ),
            {"a": str(asset_id), "e": estado},
        )
        .mappings()
        .all()
    )
    if not filas:
        return []

    activo = (
        s.execute(text("SELECT * FROM asset WHERE id = :a"), {"a": str(asset_id)})
        .mappings()
        .first()
    )
    if activo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activo no encontrado")

    salida = []
    for fila in filas:
        actual = activo.get(fila["campo"])
        salida.append({**dict(fila), "valor_actual": None if actual is None else str(actual)})
    return salida


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aceptar: list[uuid.UUID] = Field(default_factory=list)
    descartar: list[uuid.UUID] = Field(default_factory=list)


class ResultadoDeDecision(BaseModel):
    aceptadas: int
    descartadas: int
    campos: list[str]


@router.post("/assets/{asset_id}/propuestas/decidir", response_model=ResultadoDeDecision)
def decidir(
    asset_id: uuid.UUID,
    cuerpo: Decision,
    s: SesionDep,
    usuario: UsuarioDep,
) -> Any:
    """`[REQ]` **El botón.** Aplica al activo lo que el gestor acepta.

    Se decide propuesta a propuesta y no «todo o nada» a propósito: cuando dos
    documentos discrepan sobre la misma superficie, aceptar las dos no tiene
    sentido y aceptar el lote entero obligaría a elegir a ciegas.

    `[REQ]` Aceptar dos propuestas del mismo campo en la misma llamada se
    rechaza. Aplicarlas en orden dejaría ganando a la última, que es un
    resultado que depende de cómo se ordenó una lista y que nadie ha decidido.
    """
    if not cuerpo.aceptar and not cuerpo.descartar:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "No se ha indicado ninguna propuesta"
        )

    aceptadas = (
        s.execute(
            text(
                "SELECT id, campo, valor FROM propuesta_de_dato "
                "WHERE asset_id = :a AND id = ANY(:ids) AND estado = 'PENDIENTE'"
            ),
            {"a": str(asset_id), "ids": [str(i) for i in cuerpo.aceptar]},
        )
        .mappings()
        .all()
    )
    if len(aceptadas) != len(cuerpo.aceptar):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Alguna propuesta no existe, no es de este activo o ya estaba decidida. "
            "Vuelva a cargar la lista: puede que otra persona la haya resuelto.",
        )

    campos = [fila["campo"] for fila in aceptadas]
    if len(set(campos)) != len(campos):
        repetidos = sorted({c for c in campos if campos.count(c) > 1})
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Hay dos propuestas aceptadas para el mismo campo ({', '.join(repetidos)}). "
            "Elija una: aplicarlas en orden dejaría ganando a la última por azar.",
        )

    from tdd.memoria.router import CAMPOS_PROPONIBLES

    if fuera := sorted(set(campos) - set(CAMPOS_PROPONIBLES)):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Estos campos no se pueden proponer sobre un activo: {', '.join(fuera)}",
        )

    # `[REQ]` **No se toca `memoria_validada_at`.** Es tentador —el gestor acaba
    # de validar algo— y sería falso: ese testigo dice «alguien ha revisado la
    # memoria de este edificio», y la ficha del activo lo enseña como
    # «validada». Aceptar una superficie salida de un plan de autoprotección no
    # es eso. Quién aceptó qué, y de qué documento, queda en cada fila de
    # `propuesta_de_dato`, que es más fino y además es cierto.
    for fila in aceptadas:
        s.execute(
            text(  # noqa: S608 — el nombre sale de CAMPOS_PROPONIBLES, no del usuario
                f"UPDATE asset SET {fila['campo']} = :v, updated_at = now() WHERE id = :a"
            ),
            {"v": fila["valor"], "a": str(asset_id)},
        )

    for estado, ids in (("ACEPTADA", cuerpo.aceptar), ("DESCARTADA", cuerpo.descartar)):
        if not ids:
            continue
        s.execute(
            text(
                "UPDATE propuesta_de_dato SET estado = CAST(:e AS propuesta_estado), "
                "decidida_at = now(), decidida_por = :u "
                "WHERE asset_id = :a AND id = ANY(:ids) AND estado = 'PENDIENTE'"
            ),
            {"e": estado, "u": str(usuario.id), "a": str(asset_id), "ids": [str(i) for i in ids]},
        )

    return {
        "aceptadas": len(cuerpo.aceptar),
        "descartadas": len(cuerpo.descartar),
        "campos": sorted(campos),
    }

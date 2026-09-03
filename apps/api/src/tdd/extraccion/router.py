"""API de extracción: del documento subido a la propuesta que alguien valida."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core.deps import SesionDep, UsuarioDep
from tdd.evidence.router import AlmacenDep

# Importar registra. Cada extractor nuevo se añade aquí y en ningún otro sitio:
# es lo que permite que añadir un lector no obligue a tocar los que ya hay.
from tdd.extraccion import memoria_tecnica as _registra_memoria  # noqa: F401
from tdd.extraccion import plan_autoproteccion as _registra_plan  # noqa: F401
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
    #: `[REQ]` Cuántas limitaciones del informe ha aportado. Un plan de
    #: autoprotección puede no proponer ni un dato y aportar aquí la reserva más
    #: importante del encargo, así que `propuestas: 0` no significa que la
    #: lectura no haya servido para nada.
    limitaciones: int = 0
    #: `[REQ]` Cuántos medios del edificio ha propuesto al inventario.
    equipos: int = 0
    desconocidos: dict[str, str]
    avisos: list[str]


class LimitacionLeida(BaseModel):
    """Una limitación que un documento propone para el informe."""

    id: uuid.UUID
    texto: str
    motivo: str
    estado: str
    document_id: uuid.UUID | None
    doc_type: str
    seccion: str | None
    evidencia: str | None
    extractor: str
    es_simulada: bool
    decidida_por: uuid.UUID | None = None
    #: Cómo se llama el documento del que salió, para no obligar a otra petición.
    documento: str | None = None


def _documento(s: Session, document_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text(
                "SELECT d.id, d.asset_id, d.project_id, CAST(d.doc_type AS text) AS doc_type, "
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

    # `[REQ]` El activo hace falta para los CAMPOS, no para extraer.
    #
    # Esto era un 409 incondicional al principio del endpoint, y estaba mal: un
    # plan de autoprotección cubre un complejo entero y sus limitaciones son del
    # encargo, no de una nave. Con la comprobación delante, el documento que más
    # limitaciones aporta era justo el que no se podía leer.
    #
    # Ahora solo se exige si el documento propone campos y no hay a quién
    # proponérselos. Se comprueba **después de leer** porque hasta entonces no
    # se sabe si los propone.
    if documento["asset_id"] is None and aportacion.campos:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"El documento propone {len(aportacion.campos)} datos del edificio y no está "
            "asignado a ningún activo: no hay a quién proponérselos. Asígnelo primero.",
        )

    # Se retiran solo las PENDIENTES de este documento. Las decididas se quedan.
    s.execute(
        text("DELETE FROM propuesta_de_dato WHERE document_id = :d AND estado = 'PENDIENTE'"),
        {"d": str(document_id)},
    )
    s.execute(
        text("DELETE FROM limitacion_de_documento WHERE document_id = :d AND estado = 'PENDIENTE'"),
        {"d": str(document_id)},
    )
    s.execute(
        text("DELETE FROM propuesta_de_equipo WHERE document_id = :d AND estado = 'PENDIENTE'"),
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

    # Las limitaciones ya decididas tampoco se reabren. Se comparan por texto
    # porque es lo que las identifica: la misma salvedad releída del mismo
    # documento es la misma salvedad, y la clave única de la tabla dice eso.
    ya_decididas = {
        fila[0]
        for fila in s.execute(
            text(
                "SELECT texto FROM limitacion_de_documento "
                "WHERE document_id = :d AND estado <> 'PENDIENTE'"
            ),
            {"d": str(document_id)},
        ).all()
    }
    limitaciones = 0
    for limitacion in aportacion.limitaciones:
        if limitacion.texto in ya_decididas:
            continue
        procedencia = limitacion.procedencia
        s.execute(
            text(
                "INSERT INTO limitacion_de_documento (organization_id, project_id, asset_id, "
                "texto, motivo, document_id, doc_type, seccion, evidencia, extractor, "
                "es_simulada) VALUES (:o, :p, :a, :txt, CAST(:m AS limitacion_motivo), :d, "
                "CAST(:t AS doc_type), :s, :e, :x, :sim)"
            ),
            {
                "o": str(usuario.organization_id),
                "p": str(documento["project_id"]),
                # Se hereda del documento si lo tiene. Un plan de complejo no lo
                # tiene, y entonces la limitación es del encargo, que es lo
                # correcto: el alcance del informe es el encargo.
                "a": None if documento["asset_id"] is None else str(documento["asset_id"]),
                "txt": limitacion.texto,
                "m": limitacion.motivo,
                "d": str(document_id),
                "t": documento["doc_type"],
                "s": None if procedencia is None else procedencia.seccion,
                "e": None if procedencia is None else procedencia.evidencia,
                "x": aportacion.extractor,
                "sim": aportacion.es_simulada,
            },
        )
        limitaciones += 1

    # Los medios que el documento enumera. El sistema técnico se resuelve por
    # su código de catálogo: el extractor no conoce identificadores de la base,
    # y no debe.
    equipos_decididos = {
        fila[0]
        for fila in s.execute(
            text(
                "SELECT equipment_type FROM propuesta_de_equipo "
                "WHERE document_id = :d AND estado <> 'PENDIENTE'"
            ),
            {"d": str(document_id)},
        ).all()
    }
    equipos = 0
    sistemas_desconocidos: set[str] = set()
    for equipo in aportacion.equipos:
        if equipo.equipment_type in equipos_decididos:
            continue
        sistema_id = s.execute(
            text("SELECT id FROM technical_system WHERE code = :c"),
            {"c": equipo.sistema_code},
        ).scalar()
        if sistema_id is None:
            # No se descarta el equipo: se guarda sin sistema y se declara. Un
            # medio real perdido por un código de catálogo que no cuadra sería
            # peor que uno sin clasificar.
            sistemas_desconocidos.add(equipo.sistema_code)
        procedencia_eq = equipo.procedencia
        s.execute(
            text(
                "INSERT INTO propuesta_de_equipo (organization_id, project_id, "
                "technical_system_id, equipment_type, quantity, unit, descripcion, "
                "document_id, doc_type, seccion, evidencia, extractor, es_simulada) "
                "VALUES (:o, :p, :ts, :tipo, :cant, :u, :desc, :d, CAST(:t AS doc_type), "
                ":s, :e, :x, :sim)"
            ),
            {
                "o": str(usuario.organization_id),
                "p": str(documento["project_id"]),
                "ts": None if sistema_id is None else str(sistema_id),
                "tipo": equipo.equipment_type,
                "cant": equipo.cantidad,
                "u": equipo.unidad,
                "desc": equipo.descripcion,
                "d": str(document_id),
                "t": documento["doc_type"],
                "s": None if procedencia_eq is None else procedencia_eq.seccion,
                "e": None if procedencia_eq is None else procedencia_eq.evidencia,
                "x": aportacion.extractor,
                "sim": aportacion.es_simulada,
            },
        )
        equipos += 1

    avisos = list(aportacion.avisos)
    if sistemas_desconocidos:
        avisos.append(
            f"Estos códigos de sistema técnico no están en el catálogo: "
            f"{', '.join(sorted(sistemas_desconocidos))}. Los equipos se han propuesto "
            "igual, sin sistema: hay que asignárselo a mano."
        )
    if omitidas := len(decididos & {c.campo for c in aportacion.campos}):
        avisos.append(
            f"{omitidas} campos no se han vuelto a proponer porque alguien ya decidió "
            "sobre ellos desde este mismo documento."
        )
    if saltadas := len(ya_decididas & {lim.texto for lim in aportacion.limitaciones}):
        avisos.append(
            f"{saltadas} limitaciones no se han vuelto a proponer porque alguien ya "
            "decidió sobre ellas."
        )

    return {
        "document_id": document_id,
        "doc_type": documento["doc_type"],
        "extractor": aportacion.extractor,
        "es_simulada": aportacion.es_simulada,
        "propuestas": guardadas,
        "plantas": len(aportacion.plantas),
        "objetos": len(aportacion.objetos),
        "limitaciones": limitaciones,
        "equipos": equipos,
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


# ─────────────────────────────────────────────────────────────────────────────
#  Limitaciones que aporta la documentación `[REQ]`
#
#  La tercera clase de limitación del informe. Las dos que ya había salen de lo
#  que NO llegó —una línea de la checklist sin recibir, una pregunta sin
#  respuesta— y se calculan solas. Ésta es lo contrario: el documento llegó, la
#  casilla está marcada, y el documento dice que no se puede confiar en él.
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/projects/{project_id}/limitaciones-documentales", response_model=list[LimitacionLeida]
)
def listar_limitaciones(
    project_id: uuid.UUID,
    s: SesionDep,
    estado: str | None = None,
) -> Any:
    """Lo que la documentación del encargo dice sobre su propia fiabilidad.

    Sin filtro salen todas, con su estado. La pantalla pide las pendientes para
    que alguien decida y las aceptadas para enseñar qué va a ir al informe.
    """
    filas = (
        s.execute(
            text(
                "SELECT l.id, l.texto, CAST(l.motivo AS text) AS motivo, "
                "CAST(l.estado AS text) AS estado, l.document_id, "
                "CAST(l.doc_type AS text) AS doc_type, l.seccion, l.evidencia, l.extractor, "
                "l.es_simulada, l.decidida_por, d.display_name AS documento "
                "FROM limitacion_de_documento l "
                "LEFT JOIN document d ON d.id = l.document_id "
                "WHERE l.project_id = :p AND (CAST(:e AS text) IS NULL "
                "OR CAST(l.estado AS text) = CAST(:e AS text)) "
                "ORDER BY l.motivo, l.created_at"
            ),
            {"p": str(project_id), "e": estado},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


class DecisionDeLimitaciones(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aceptar: list[uuid.UUID] = Field(default_factory=list)
    descartar: list[uuid.UUID] = Field(default_factory=list)


class ResultadoDeLimitaciones(BaseModel):
    aceptadas: int
    descartadas: int


@router.post(
    "/projects/{project_id}/limitaciones-documentales/decidir",
    response_model=ResultadoDeLimitaciones,
)
def decidir_limitaciones(
    project_id: uuid.UUID,
    cuerpo: DecisionDeLimitaciones,
    s: SesionDep,
    usuario: UsuarioDep,
) -> Any:
    """`[REQ]` Qué limitaciones entran en el informe. Las acepta una persona.

    Aceptar aquí **no redacta nada**: el texto ya está escrito y sale del
    documento. Lo que hace es decidir que esa reserva forma parte del alcance
    declarado del informe, que es una firma profesional y no un detalle.

    Descartar tampoco es borrar. La fila se queda con su testigo: si el cliente
    pregunta por qué el informe no menciona que el plan se redactó con las naves
    vacías, la respuesta está en la base y no en la memoria de nadie.
    """
    if not cuerpo.aceptar and not cuerpo.descartar:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "No se ha indicado ninguna limitación"
        )

    todas = [*cuerpo.aceptar, *cuerpo.descartar]
    if len(set(todas)) != len(todas):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Hay una limitación en las dos listas a la vez: aceptarla y descartarla en la "
            "misma llamada dejaría ganando al orden de ejecución, que no lo ha decidido nadie.",
        )

    existentes = s.execute(
        text(
            "SELECT count(*) FROM limitacion_de_documento "
            "WHERE project_id = :p AND id = ANY(:ids) AND estado = 'PENDIENTE'"
        ),
        {"p": str(project_id), "ids": [str(i) for i in todas]},
    ).scalar_one()
    if existentes != len(todas):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Alguna limitación no existe, no es de este encargo o ya estaba decidida. "
            "Vuelva a cargar la lista: puede que otra persona la haya resuelto.",
        )

    for estado, ids in (("ACEPTADA", cuerpo.aceptar), ("DESCARTADA", cuerpo.descartar)):
        if not ids:
            continue
        s.execute(
            text(
                "UPDATE limitacion_de_documento SET estado = CAST(:e AS propuesta_estado), "
                "decidida_at = now(), decidida_por = :u "
                "WHERE project_id = :p AND id = ANY(:ids) AND estado = 'PENDIENTE'"
            ),
            {
                "e": estado,
                "u": str(usuario.id),
                "p": str(project_id),
                "ids": [str(i) for i in ids],
            },
        )

    return {"aceptadas": len(cuerpo.aceptar), "descartadas": len(cuerpo.descartar)}


# ─────────────────────────────────────────────────────────────────────────────
#  Los medios que un documento dice que existen `[REQ]`
#
#  El capítulo 4 de la Norma Básica de Autoprotección los enumera. Teclearlos a
#  mano después es el trabajo repetido que el cliente pidió evitar.
# ─────────────────────────────────────────────────────────────────────────────


class EquipoLeido(BaseModel):
    id: uuid.UUID
    equipment_type: str
    #: Puede venir vacía: «rociadores sobre la superficie de almacenamiento» no
    #: trae número, y poner un 1 metería un uno en un inventario.
    quantity: str | None
    unit: str
    descripcion: str | None
    estado: str
    technical_system_id: uuid.UUID | None
    technical_system_name: str | None
    document_id: uuid.UUID | None
    doc_type: str
    seccion: str | None
    evidencia: str | None
    extractor: str
    es_simulada: bool
    decidida_por: uuid.UUID | None = None
    #: El equipo creado al aceptarla. Cierra la trazabilidad al revés: desde la
    #: ficha del equipo se llega al documento que lo declaró.
    equipment_id: uuid.UUID | None = None
    documento: str | None = None


@router.get("/projects/{project_id}/propuestas-de-equipo", response_model=list[EquipoLeido])
def listar_equipos_propuestos(
    project_id: uuid.UUID,
    s: SesionDep,
    estado: str | None = None,
) -> Any:
    """Los medios que la documentación del encargo dice que existen."""
    filas = (
        s.execute(
            text(
                "SELECT e.id, e.equipment_type, CAST(e.quantity AS text) AS quantity, e.unit, "
                "e.descripcion, CAST(e.estado AS text) AS estado, e.technical_system_id, "
                "ts.name_es AS technical_system_name, e.document_id, "
                "CAST(e.doc_type AS text) AS doc_type, e.seccion, e.evidencia, e.extractor, "
                "e.es_simulada, e.decidida_por, e.equipment_id, d.display_name AS documento "
                "FROM propuesta_de_equipo e "
                "LEFT JOIN technical_system ts ON ts.id = e.technical_system_id "
                "LEFT JOIN document d ON d.id = e.document_id "
                "WHERE e.project_id = :p AND (CAST(:e AS text) IS NULL "
                "OR CAST(e.estado AS text) = CAST(:e AS text)) "
                "ORDER BY ts.sort_order NULLS LAST, e.equipment_type"
            ),
            {"p": str(project_id), "e": estado},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


class Aceptacion(BaseModel):
    """`[REQ]` Aceptar un equipo exige decir **a qué activo va**.

    El documento no lo dice: un plan cubre un complejo de seis naves y habla de
    «dieciséis hidrantes distribuidos por el perímetro». Adivinar el activo lo
    haría pasar por sabido, y el inventario es lo que después se recorre en una
    visita: un equipo en la nave equivocada es una visita perdida.
    """

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    asset_id: uuid.UUID
    zone_id: uuid.UUID | None = None
    #: La cantidad, cuando el documento no la traía o hay que corregirla.
    quantity: Decimal | None = None
    #: `[REQ]` Cada cuántos meses se revisa. El plan declara periodicidades en
    #: bloque —trimestral, semestral, anual, quinquenal— y **no dice cuál le
    #: toca a cuál**, así que esto lo pone una persona o queda vacío.
    maintenance_months: int | None = Field(default=None, gt=0)


class DecisionDeEquipos(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aceptar: list[Aceptacion] = Field(default_factory=list)
    descartar: list[uuid.UUID] = Field(default_factory=list)


class ResultadoDeEquipos(BaseModel):
    aceptadas: int
    descartadas: int
    #: Los equipos creados, para que la pantalla pueda enlazarlos.
    equipment_ids: list[uuid.UUID]


@router.post(
    "/projects/{project_id}/propuestas-de-equipo/decidir",
    response_model=ResultadoDeEquipos,
)
def decidir_equipos(
    project_id: uuid.UUID,
    cuerpo: DecisionDeEquipos,
    s: SesionDep,
    usuario: UsuarioDep,
) -> Any:
    """`[REQ]` Aceptar crea la ficha de equipo; descartar deja constancia.

    Es la única de las tres decisiones que **escribe una fila nueva** en vez de
    actualizar una que ya existía, y por eso pide el activo: el equipo tiene que
    nacer en algún sitio y el documento no lo dice.
    """
    if not cuerpo.aceptar and not cuerpo.descartar:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "No se ha indicado ninguna propuesta"
        )

    ids = [a.id for a in cuerpo.aceptar] + list(cuerpo.descartar)
    if len(set(ids)) != len(ids):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Hay una propuesta repetida entre las dos listas: aceptarla y descartarla en "
            "la misma llamada dejaría ganando al orden de ejecución, que no lo ha "
            "decidido nadie.",
        )

    pendientes = {
        str(fila["id"]): dict(fila)
        for fila in s.execute(
            text(
                "SELECT id, technical_system_id, equipment_type, quantity, unit, descripcion "
                "FROM propuesta_de_equipo "
                "WHERE project_id = :p AND id = ANY(:ids) AND estado = 'PENDIENTE'"
            ),
            {"p": str(project_id), "ids": [str(i) for i in ids]},
        )
        .mappings()
        .all()
    }
    if len(pendientes) != len(ids):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Alguna propuesta no existe, no es de este encargo o ya estaba decidida. "
            "Vuelva a cargar la lista: puede que otra persona la haya resuelto.",
        )

    creados: list[uuid.UUID] = []
    for aceptada in cuerpo.aceptar:
        propuesta = pendientes[str(aceptada.id)]
        # El activo tiene que ser del encargo. Sin esto, un identificador de otro
        # proyecto crearía un equipo cruzado que la RLS no ve como error porque
        # las dos filas son de la misma organización.
        del_encargo = s.execute(
            text("SELECT 1 FROM asset WHERE id = :a AND project_id = :p AND deleted_at IS NULL"),
            {"a": str(aceptada.asset_id), "p": str(project_id)},
        ).first()
        if del_encargo is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"El activo {aceptada.asset_id} no es de este encargo.",
            )

        equipment_id = s.execute(
            text(
                "INSERT INTO equipment (organization_id, project_id, asset_id, "
                "technical_system_id, zone_id, equipment_type, quantity, unit, notes, "
                "maintenance_months, created_by) "
                "VALUES (:o, :p, :a, :ts, :z, :tipo, COALESCE(:cant, 1), :u, :notas, :mm, :by) "
                "RETURNING id"
            ),
            {
                "o": str(usuario.organization_id),
                "p": str(project_id),
                "a": str(aceptada.asset_id),
                "z": None if aceptada.zone_id is None else str(aceptada.zone_id),
                "ts": (
                    None
                    if propuesta["technical_system_id"] is None
                    else str(propuesta["technical_system_id"])
                ),
                "tipo": propuesta["equipment_type"],
                # La que corrija quien acepta manda sobre la del documento. Y si
                # ninguna de las dos hay, `equipment.quantity` es NOT NULL con
                # DEFAULT 1: el COALESCE lo pone explícito en vez de dejarlo al
                # azar de la columna.
                "cant": aceptada.quantity
                if aceptada.quantity is not None
                else propuesta["quantity"],
                "u": propuesta["unit"],
                "notas": propuesta["descripcion"],
                "mm": aceptada.maintenance_months,
                "by": str(usuario.id),
            },
        ).scalar_one()
        creados.append(uuid.UUID(str(equipment_id)))

        s.execute(
            text(
                "UPDATE propuesta_de_equipo SET estado = 'ACEPTADA', decidida_at = now(), "
                "decidida_por = :u, equipment_id = :eq WHERE id = :i"
            ),
            {"u": str(usuario.id), "eq": str(equipment_id), "i": str(aceptada.id)},
        )

    if cuerpo.descartar:
        s.execute(
            text(
                "UPDATE propuesta_de_equipo SET estado = 'DESCARTADA', decidida_at = now(), "
                "decidida_por = :u WHERE project_id = :p AND id = ANY(:ids) "
                "AND estado = 'PENDIENTE'"
            ),
            {
                "u": str(usuario.id),
                "p": str(project_id),
                "ids": [str(i) for i in cuerpo.descartar],
            },
        )

    return {
        "aceptadas": len(cuerpo.aceptar),
        "descartadas": len(cuerpo.descartar),
        "equipment_ids": creados,
    }

"""API de hallazgos.

**El alta crea el hallazgo y su línea de CAPEX en una sola operación** `[REC]`.
No es un atajo: es que en la tabla real del cliente son la misma fila. Pedirle
al consultor que cree primero el hallazgo y después vaya a otra pantalla a
añadirle el importe multiplicaría por dos los pasos de la operación que más
veces se repite en todo el proyecto —sesenta o setenta veces por encargo— y
dejaría hallazgos huérfanos cada vez que alguien se distrajera a mitad.

`[REQ]` **P-44 · Una actuación puede tener varias líneas, una por plazo.** La
limpieza de lucernarios hace falta ahora *y* otra vez dentro de diez años. Lo
que sigue prohibido —y lo impide un índice único— es que el mismo hallazgo
tenga dos líneas en el **mismo** plazo, que sería un duplicado.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core import concurrencia as cc
from tdd.core.deps import SesionDep, UsuarioDep
from tdd.findings.service import (
    EstadoDelHallazgo,
    GuardaDeHallazgoIncumplida,
    HechosDelHallazgo,
    TransicionDeHallazgoNoPermitida,
    comprobar_transicion,
    destinos_posibles,
)

router = APIRouter(tags=["Hallazgos"])


# ─────────────────────────────────────────────────────────────────────────────
#  Esquemas
# ─────────────────────────────────────────────────────────────────────────────


class LineaDeCapex(BaseModel):
    """`[REQ]` P-05 · **Un horizonte y un importe.** No cinco columnas."""

    model_config = ConfigDict(extra="forbid")

    time_horizon_code: str
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_pct: Decimal | None = Field(default=None, ge=0, le=1)
    measurement_unit: str | None = Field(default=None, max_length=20)
    measurement_quantity: Decimal | None = Field(default=None, ge=0)
    measurement_unit_price: Decimal | None = Field(default=None, ge=0)


class CrearHallazgo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: uuid.UUID
    capex_code_id: uuid.UUID
    zone_id: uuid.UUID
    title: str = Field(min_length=1, max_length=240)
    description: str = ""
    comments: str | None = None
    recommendation: str | None = None
    risk_level_id: uuid.UUID | None = None
    capex_concept_id: uuid.UUID | None = None
    tenant_recoverable: str = "NA"
    owner_user_id: uuid.UUID | None = None
    #: Las líneas del hallazgo. Una por plazo (P-44). Vacío es válido: en campo
    #: se anota lo que se ve antes de saber cuánto cuesta.
    capex_lines: list[LineaDeCapex] = Field(default_factory=list)


class ActualizarHallazgo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: uuid.UUID | None = None
    capex_code_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    comments: str | None = None
    recommendation: str | None = None
    risk_level_id: uuid.UUID | None = None
    capex_concept_id: uuid.UUID | None = None
    tenant_recoverable: str | None = None
    owner_user_id: uuid.UUID | None = None


class LineaLeida(BaseModel):
    id: uuid.UUID
    time_horizon_code: str
    amount: Decimal
    tax_pct: Decimal
    tax_amount: Decimal
    total_cost: Decimal
    amount_source: str
    price_status: str
    computed_base: Decimal | None
    #: `[REQ]` §14 · Contra qué se validó el precio. Un importe validado sin
    #: procedencia visible obliga a abrir la auditoría para responder «¿de dónde
    #: sale esto?», que es la pregunta que llega seis meses después.
    selected_price_reference_id: uuid.UUID | None = None
    price_reference_label: str | None = None
    price_validation_note: str | None = None
    #: `[REQ]` La versión DE LA LÍNEA. Es la que hay que mandar en `If-Match`
    #: al editarla, no la del hallazgo: editar una línea no toca la fila del
    #: hallazgo, así que su versión no serviría para detectar que otra persona
    #: cambió esta misma línea.
    row_version: int = 1


class Hallazgo(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    asset_id: uuid.UUID
    capex_code_id: uuid.UUID
    zone_id: uuid.UUID
    risk_level_id: uuid.UUID | None
    capex_concept_id: uuid.UUID | None
    title: str
    description: str
    comments: str | None
    recommendation: str | None
    tenant_recoverable: str
    status: str
    owner_user_id: uuid.UUID | None
    #: `[REQ]` La versión sobre la que se está escribiendo. Va también como
    #: `ETag`; aquí se repite porque la pantalla la reenvía en `If-Match` y
    #: sacarla del cuerpo evita leer cabeceras en cada `fetch`.
    row_version: int = 1
    capex_lines: list[LineaLeida] = Field(default_factory=list)
    #: Suma de las líneas. `[REQ]` Cualquier cambio devuelve los totales.
    total_amount: Decimal = Decimal("0")
    total_with_tax: Decimal = Decimal("0")


class CambioDeEstado(BaseModel):
    to: EstadoDelHallazgo


class DesdeFoto(BaseModel):
    """`[REC]` Atajo de campo: hereda activo y zona de la fotografía."""

    model_config = ConfigDict(extra="forbid")

    photo_id: uuid.UUID
    capex_code_id: uuid.UUID
    title: str = Field(min_length=1, max_length=240)
    description: str = ""
    risk_level_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None


# ─────────────────────────────────────────────────────────────────────────────
#  Auxiliares
# ─────────────────────────────────────────────────────────────────────────────

_CAMPOS = """
    id, project_id, asset_id, capex_code_id, zone_id, risk_level_id, capex_concept_id,
    title, description, comments, recommendation,
    CAST(tenant_recoverable AS text) AS tenant_recoverable,
    CAST(status AS text) AS status, owner_user_id, row_version
"""

_LINEAS = """
    SELECT ci.id, th.code AS time_horizon_code, ci.amount, ci.tax_pct, ci.tax_amount,
           ci.row_version,
           ci.total_cost, CAST(ci.amount_source AS text) AS amount_source,
           CAST(ci.price_status AS text) AS price_status, ci.computed_base,
           ci.selected_price_reference_id, ci.price_validation_note,
           CASE WHEN pr.id IS NULL THEN NULL
                ELSE ps.name || ' · ' || pr.description END AS price_reference_label
    FROM capex_item ci
    JOIN time_horizon th ON th.id = ci.time_horizon_id
    LEFT JOIN price_reference pr ON pr.id = ci.selected_price_reference_id
    LEFT JOIN price_source ps ON ps.id = pr.price_source_id
    WHERE ci.finding_id = :f ORDER BY th.sort_order
"""


def _proyecto_existe(s: Session, project_id: uuid.UUID) -> None:
    if (
        s.execute(
            text("SELECT 1 FROM project WHERE id = :p AND deleted_at IS NULL"),
            {"p": str(project_id)},
        ).first()
        is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")


def leer_hallazgo(s: Session, finding_id: uuid.UUID) -> dict[str, Any]:
    """El hallazgo con sus líneas y **los totales ya calculados**.

    Público —sin guion bajo— porque lo usa también el traslado de medición del
    módulo de CAPEX: cualquier cambio sobre una línea devuelve el hallazgo
    entero, y esa lectura tiene que ser la misma en los dos sitios.
    """
    return _leer(s, finding_id)


def _leer(s: Session, finding_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text(f"SELECT {_CAMPOS} FROM finding WHERE id = :i AND deleted_at IS NULL"),  # noqa: S608
            {"i": str(finding_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hallazgo no encontrado")
    lineas = [dict(f) for f in s.execute(text(_LINEAS), {"f": str(finding_id)}).mappings().all()]
    return {
        **dict(fila),
        "capex_lines": lineas,
        "total_amount": sum((line["amount"] for line in lineas), Decimal("0")),
        "total_with_tax": sum((line["total_cost"] for line in lineas), Decimal("0")),
    }


def _hechos(s: Session, finding_id: uuid.UUID) -> HechosDelHallazgo:
    fila = s.execute(
        text(
            "SELECT count(ci.id) AS lineas, COALESCE(sum(ci.amount), 0) AS importe, "
            "count(*) FILTER (WHERE ci.price_status <> 'VALIDADO' "
            "               AND ci.amount > 0) AS sin_validar, "
            "(SELECT length(trim(description)) FROM finding WHERE id = :f) AS largo_descripcion, "
            "(SELECT count(*) FROM photo_link pl WHERE pl.entity_type = 'FINDING' "
            "   AND pl.entity_id = :f) AS fotos "
            "FROM capex_item ci WHERE ci.finding_id = :f"
        ),
        {"f": str(finding_id)},
    ).one()
    return HechosDelHallazgo(
        tiene_lineas_capex=fila.lineas > 0,
        importe_total=Decimal(fila.importe),
        tiene_descripcion=(fila.largo_descripcion or 0) > 0,
        tiene_fotos=fila.fotos > 0,
        precios_sin_validar=fila.sin_validar,
    )


def _zona_permitida(s: Session, asset_id: uuid.UUID, zone_id: uuid.UUID) -> None:
    """`[REQ]` La tipología del activo determina las zonas admisibles.

    Se comprueba aquí y no solo en la interfaz: un cliente de API o un
    formulario cacheado no pasan por el desplegable.
    """
    ok = s.execute(
        text(
            "SELECT 1 FROM asset a JOIN zone_typology zt ON zt.typology_id = a.typology_id "
            "WHERE a.id = :a AND zt.zone_id = :z"
        ),
        {"a": str(asset_id), "z": str(zone_id)},
    ).first()
    if ok is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Esa zona no corresponde a la tipología del activo",
        )


def _perfil_de_coste(s: Session, organization_id: uuid.UUID) -> uuid.UUID:
    """El perfil por defecto de la organización, creándolo si no existe.

    Se crea al vuelo y no en la semilla porque una organización nueva debe
    poder empezar a trabajar sin que nadie configure nada primero.
    """
    fila = s.execute(
        text(
            "SELECT id FROM cost_profile WHERE organization_id = :o "
            "ORDER BY is_default DESC, created_at LIMIT 1"
        ),
        {"o": str(organization_id)},
    ).scalar()
    if fila is not None:
        return fila  # type: ignore[return-value]
    return s.execute(  # type: ignore[return-value]
        text(
            "INSERT INTO cost_profile (organization_id, name, cascade_config, is_default) "
            "VALUES (:o, 'Perfil por defecto', CAST(:c AS jsonb), TRUE) RETURNING id"
        ),
        {"o": str(organization_id), "c": '{"convencion": "espanola", "version": 1}'},
    ).scalar_one()


def _insertar_linea(
    s: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    finding_id: uuid.UUID,
    perfil_id: uuid.UUID,
    linea: LineaDeCapex,
    tax_por_defecto: Decimal,
) -> None:
    horizonte = s.execute(
        text("SELECT id FROM time_horizon WHERE code = :c"), {"c": linea.time_horizon_code}
    ).scalar()
    if horizonte is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Horizonte temporal desconocido: {linea.time_horizon_code}",
        )
    medicion = (linea.measurement_quantity, linea.measurement_unit_price)
    base_calculada = (
        linea.measurement_quantity * linea.measurement_unit_price
        if all(v is not None for v in medicion)
        else None
    )
    try:
        s.execute(
            text(
                "INSERT INTO capex_item (organization_id, project_id, finding_id, cost_profile_id, "
                "time_horizon_id, amount, tax_pct, measurement_unit, measurement_quantity, "
                "measurement_unit_price, computed_base) "
                "VALUES (:o, :p, :f, :perfil, :h, :importe, :tax, :unidad, :cantidad, "
                "        :precio, :base)"
            ),
            {
                "o": str(organization_id),
                "p": str(project_id),
                "f": str(finding_id),
                "perfil": str(perfil_id),
                "h": str(horizonte),
                "importe": linea.amount,
                "tax": linea.tax_pct if linea.tax_pct is not None else tax_por_defecto,
                "unidad": linea.measurement_unit,
                "cantidad": linea.measurement_quantity,
                "precio": linea.measurement_unit_price,
                "base": base_calculada,
            },
        )
    except Exception as exc:  # noqa: BLE001
        if "capex_item_hallazgo_plazo_uniq" in str(exc):
            # P-44 permite varias líneas por hallazgo, una por plazo. Dos en el
            # mismo plazo sí es un duplicado, y conviene decirlo con claridad.
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Este hallazgo ya tiene una línea en el plazo {linea.time_horizon_code}. "
                "Una actuación recurrente lleva una línea por plazo, no dos en el mismo.",
            ) from exc
        raise


# ─────────────────────────────────────────────────────────────────────────────
#  Alta y consulta
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/projects/{project_id}/findings",
    status_code=status.HTTP_201_CREATED,
    response_model=Hallazgo,
)
def crear(project_id: uuid.UUID, cuerpo: CrearHallazgo, s: SesionDep, usuario: UsuarioDep) -> Any:
    """`[REC]` Crea el hallazgo **y sus líneas de CAPEX** en una operación."""
    _proyecto_existe(s, project_id)
    _zona_permitida(s, cuerpo.asset_id, cuerpo.zone_id)

    finding_id = s.execute(
        text(
            "INSERT INTO finding (organization_id, project_id, asset_id, capex_code_id, zone_id, "
            "risk_level_id, capex_concept_id, title, description, comments, recommendation, "
            "tenant_recoverable, owner_user_id, created_by) "
            "VALUES (:o, :p, :a, :cc, :z, :r, :con, :t, :d, :com, :rec, "
            "CAST(:tr AS tenant_recoverable), :own, :u) RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "p": str(project_id),
            "a": str(cuerpo.asset_id),
            "cc": str(cuerpo.capex_code_id),
            "z": str(cuerpo.zone_id),
            "r": str(cuerpo.risk_level_id) if cuerpo.risk_level_id else None,
            "con": str(cuerpo.capex_concept_id) if cuerpo.capex_concept_id else None,
            "t": cuerpo.title,
            "d": cuerpo.description,
            "com": cuerpo.comments,
            "rec": cuerpo.recommendation,
            "tr": cuerpo.tenant_recoverable,
            "own": str(cuerpo.owner_user_id) if cuerpo.owner_user_id else None,
            "u": str(usuario.id),
        },
    ).scalar_one()

    if cuerpo.capex_lines:
        perfil = _perfil_de_coste(s, usuario.organization_id)
        tax = s.execute(
            text("SELECT tax_pct FROM cost_profile WHERE id = :i"), {"i": str(perfil)}
        ).scalar_one()
        for linea in cuerpo.capex_lines:
            _insertar_linea(
                s,
                organization_id=usuario.organization_id,
                project_id=project_id,
                finding_id=finding_id,
                perfil_id=perfil,
                linea=linea,
                tax_por_defecto=tax,
            )
    return _leer(s, finding_id)


@router.get("/projects/{project_id}/findings", response_model=list[Hallazgo])
def listar(  # noqa: PLR0913 — filtros de §10.8, cada uno independiente
    project_id: uuid.UUID,
    s: SesionDep,
    asset_id: uuid.UUID | None = None,
    zone_id: uuid.UUID | None = None,
    #: Incluye el subárbol completo del código: filtrar por «Cubiertas» trae
    #: también sus elementos.
    capex_code_id: uuid.UUID | None = None,
    estado: str | None = Query(default=None, alias="status"),
    risk_level_id: uuid.UUID | None = None,
    q: str | None = None,
) -> Any:
    _proyecto_existe(s, project_id)
    filas = (
        s.execute(
            text(  # noqa: S608
                f"""
                SELECT {_CAMPOS} FROM finding f
                WHERE f.project_id = :p AND f.deleted_at IS NULL
                  AND (CAST(:activo AS uuid) IS NULL OR f.asset_id = CAST(:activo AS uuid))
                  AND (CAST(:zona AS uuid) IS NULL OR f.zone_id = CAST(:zona AS uuid))
                  AND (CAST(:riesgo AS uuid) IS NULL OR f.risk_level_id = CAST(:riesgo AS uuid))
                  AND (CAST(:estado AS text) IS NULL OR f.status::text = CAST(:estado AS text))
                  AND (CAST(:q AS text) IS NULL
                       OR f.title ILIKE '%' || :q || '%' OR f.description ILIKE '%' || :q || '%')
                  AND (CAST(:codigo AS uuid) IS NULL OR f.capex_code_id IN (
                        -- El subárbol completo: filtrar por «Cubiertas» debe
                        -- traer también sus elementos, o el filtro engaña.
                        SELECT d.id FROM capex_code d, capex_code p
                        WHERE p.id = CAST(:codigo AS uuid) AND d.path <@ p.path))
                ORDER BY f.created_at
                """
            ),
            {
                "p": str(project_id),
                "activo": str(asset_id) if asset_id else None,
                "zona": str(zone_id) if zone_id else None,
                "riesgo": str(risk_level_id) if risk_level_id else None,
                "estado": estado,
                "q": q,
                "codigo": str(capex_code_id) if capex_code_id else None,
            },
        )
        .mappings()
        .all()
    )
    return [_leer(s, f["id"]) for f in filas]


@router.get("/findings/{finding_id}", response_model=Hallazgo)
def obtener(finding_id: uuid.UUID, s: SesionDep, respuesta: Response) -> Any:
    fila = _leer(s, finding_id)
    cc.poner(respuesta, fila["row_version"])
    return fila


@router.patch("/findings/{finding_id}", response_model=Hallazgo)
def actualizar(
    finding_id: uuid.UUID,
    cuerpo: ActualizarHallazgo,
    s: SesionDep,
    request: Request,
    respuesta: Response,
) -> Any:
    """`[REQ]` `If-Match` es **obligatorio** aquí.

    Un hallazgo es lo que de verdad se edita a cuatro manos —quien redacta, quien
    clasifica el riesgo y quien revisa—, así que dejar la cabecera opcional
    significaría que una pantalla nueva que se olvide de mandarla pierde la
    protección sin que nadie lo note.
    """
    actual = _leer(s, finding_id)
    cc.comprobar(
        request,
        s,
        tabla="finding",
        fila_id=finding_id,
        version_actual=actual["row_version"],
        que="un hallazgo",
        obligatoria=True,
    )
    cambios = cuerpo.model_dump(exclude_unset=True)
    if not cambios:
        cc.poner(respuesta, actual["row_version"])
        return actual
    if "zone_id" in cambios or "asset_id" in cambios:
        _zona_permitida(
            s,
            cambios.get("asset_id") or actual["asset_id"],
            cambios.get("zone_id") or actual["zone_id"],
        )
    piezas = []
    for campo in cambios:
        if campo == "tenant_recoverable":
            piezas.append("tenant_recoverable = CAST(:tenant_recoverable AS tenant_recoverable)")
        else:
            piezas.append(f"{campo} = :{campo}")
    s.execute(
        text(f"UPDATE finding SET {', '.join(piezas)}, updated_at = now() WHERE id = :_id"),  # noqa: S608
        {**cambios, "_id": str(finding_id)},
    )
    nuevo = _leer(s, finding_id)
    cc.poner(respuesta, nuevo["row_version"])
    return nuevo


@router.delete("/findings/{finding_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(finding_id: uuid.UUID, s: SesionDep, request: Request) -> None:
    """Borrado lógico. Para quitarlo del informe conservando el rastro de que
    se valoró, lo correcto es `DESCARTADO`, no borrarlo.

    `If-Match` obligatorio: borrar un hallazgo que otro acaba de reescribir es
    justo el caso en que hace más falta enterarse.
    """
    actual = _leer(s, finding_id)
    cc.comprobar(
        request,
        s,
        tabla="finding",
        fila_id=finding_id,
        version_actual=actual["row_version"],
        que="un hallazgo",
        obligatoria=True,
    )
    s.execute(
        text("UPDATE finding SET deleted_at = now() WHERE id = :i AND deleted_at IS NULL"),
        {"i": str(finding_id)},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Estados
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/projects/{project_id}/risk-matrix")
def matriz_de_riesgos(
    project_id: uuid.UUID,
    s: SesionDep,
    asset_id: uuid.UUID | None = None,
    chapter_code: str | None = None,
) -> Any:
    """`[REQ]` §12 · Riesgo × horizonte temporal.

    No la clásica probabilidad × consecuencia: la especificación revisada define
    el riesgo como un grado único de cuatro niveles **ya interpretado**, no como
    dos ejes. Cruzarlo con el plazo responde la pregunta que se hace el
    inversor: «¿cuánto de lo grave hay que pagar en los dos primeros años?».

    La consulta trae **una fila por línea de CAPEX**, y un `LEFT JOIN` para que
    un hallazgo sin importe llegue igual: en campo se anota lo que se ve antes
    de saber cuánto cuesta, y si no contara, la matriz diría que no hay nada que
    mirar en esa zona. La agregación —incluido no contar dos veces una actuación
    recurrente (P-44)— vive en `riesgos.py`, que es lógica pura y se prueba sin
    base de datos.
    """
    from tdd.findings import riesgos

    _proyecto_existe(s, project_id)
    filas = (
        s.execute(
            text(
                "SELECT f.id::text AS finding_id, "
                "  rl.code AS risk_code, rl.name_es AS risk_name, rl.score AS risk_score, "
                "  cap.code AS chapter_code, cap.name_es AS chapter_name, "
                "  th.code AS horizonte, COALESCE(ci.amount, 0) AS importe "
                "FROM finding f "
                "LEFT JOIN risk_level rl ON rl.id = f.risk_level_id "
                "JOIN capex_code cc ON cc.id = f.capex_code_id "
                # El capítulo es el nivel 2 del árbol. Un código de nivel 2 es su
                # propio capítulo; uno de nivel 3 cuelga de él.
                "LEFT JOIN capex_code cap ON cap.id = "
                "  CASE WHEN cc.level = 2 THEN cc.id ELSE cc.parent_id END "
                "LEFT JOIN capex_item ci ON ci.finding_id = f.id "
                "LEFT JOIN time_horizon th ON th.id = ci.time_horizon_id "
                "WHERE f.project_id = :p AND f.deleted_at IS NULL "
                "  AND CAST(f.status AS text) = ANY(:estados) "
                "  AND (CAST(:a AS uuid) IS NULL OR f.asset_id = CAST(:a AS uuid)) "
                "  AND (CAST(:c AS text) IS NULL OR cap.code = CAST(:c AS text))"
            ),
            {
                "p": str(project_id),
                "a": str(asset_id) if asset_id else None,
                "c": chapter_code,
                # Lo descartado queda fuera: decir que no se hace y seguir
                # sumándolo al riesgo del encargo sería contradictorio.
                "estados": ["BORRADOR", "EN_REVISION", "VALIDADO"],
            },
        )
        .mappings()
        .all()
    )

    catalogo = [
        (f.code, f.name_es, f.score)
        for f in s.execute(text("SELECT code, name_es, score FROM risk_level ORDER BY score")).all()
    ]
    horizontes = [
        f[0] for f in s.execute(text("SELECT code FROM time_horizon ORDER BY sort_order")).all()
    ]

    matriz = riesgos.construir(
        [
            riesgos.FilaDeHallazgo(
                finding_id=f["finding_id"],
                risk_code=f["risk_code"],
                risk_name=f["risk_name"],
                risk_score=f["risk_score"],
                chapter_code=f["chapter_code"],
                chapter_name=f["chapter_name"],
                horizonte=f["horizonte"],
                importe=Decimal(str(f["importe"])),
            )
            for f in filas
        ],
        grados_del_catalogo=catalogo,
        horizontes=horizontes,
    )
    return matriz.como_json(horizontes)


@router.get("/findings/{finding_id}/transitions")
def transiciones(finding_id: uuid.UUID, s: SesionDep) -> Any:
    """Cada destino con sus impedimentos, para deshabilitar el botón **con su
    motivo** en vez de ocultarlo."""
    actual = _leer(s, finding_id)
    return destinos_posibles(EstadoDelHallazgo(actual["status"]), _hechos(s, finding_id))


@router.post("/findings/{finding_id}/transitions", response_model=Hallazgo)
def cambiar_estado(
    finding_id: uuid.UUID, cuerpo: CambioDeEstado, s: SesionDep, usuario: UsuarioDep
) -> Any:
    actual = _leer(s, finding_id)
    try:
        comprobar_transicion(EstadoDelHallazgo(actual["status"]), cuerpo.to, _hechos(s, finding_id))
    except GuardaDeHallazgoIncumplida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except TransicionDeHallazgoNoPermitida as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    s.execute(
        text(
            "UPDATE finding SET status = CAST(:e AS finding_status), updated_at = now() "
            "WHERE id = :i"
        ),
        {"e": cuerpo.to.value, "i": str(finding_id)},
    )
    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, before_data, after_data) VALUES (:o, :u, 'FINDING_TRANSITIONED', "
            "'finding', :i, CAST(:antes AS jsonb), CAST(:despues AS jsonb))"
        ),
        {
            "o": str(usuario.organization_id),
            "u": str(usuario.id),
            "i": str(finding_id),
            "antes": f'{{"status": "{actual["status"]}"}}',
            "despues": f'{{"status": "{cuerpo.to.value}"}}',
        },
    )
    return _leer(s, finding_id)


# ─────────────────────────────────────────────────────────────────────────────
#  Atajo de campo
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/findings/from-photo", status_code=status.HTTP_201_CREATED, response_model=Hallazgo)
def desde_foto(cuerpo: DesdeFoto, s: SesionDep, usuario: UsuarioDep) -> Any:
    """`[REC]` Crea el hallazgo heredando activo y zona de la fotografía.

    Es el flujo de campo: se ve algo, se fotografía y se anota **desde la
    propia foto**. Volver a teclear el activo y la zona que la foto ya sabe es
    trabajo repetido y una fuente de errores de asignación.
    """
    foto = (
        s.execute(
            text(
                "SELECT project_id, asset_id, zone_id FROM photo "
                "WHERE id = :i AND deleted_at IS NULL"
            ),
            {"i": str(cuerpo.photo_id)},
        )
        .mappings()
        .first()
    )
    if foto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fotografía no encontrada")
    if foto["asset_id"] is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "La fotografía no está asignada a ningún activo: asígnela antes de crear el hallazgo",
        )
    zona = cuerpo.zone_id or foto["zone_id"]
    if zona is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "La fotografía no tiene zona: indíquela en la petición",
        )

    hallazgo = crear(
        foto["project_id"],
        CrearHallazgo(
            asset_id=foto["asset_id"],
            capex_code_id=cuerpo.capex_code_id,
            zone_id=zona,
            title=cuerpo.title,
            description=cuerpo.description,
            risk_level_id=cuerpo.risk_level_id,
        ),
        s,
        usuario,
    )
    # La foto queda enlazada como evidencia: es el motivo por el que existe el
    # hallazgo, y el informe la necesitará.
    s.execute(
        text(
            "INSERT INTO photo_link (organization_id, photo_id, entity_type, entity_id, role, "
            "created_by) VALUES (:o, :f, 'FINDING', :h, 'EVIDENCIA', :u) ON CONFLICT DO NOTHING"
        ),
        {
            "o": str(usuario.organization_id),
            "f": str(cuerpo.photo_id),
            "h": str(hallazgo["id"]),
            "u": str(usuario.id),
        },
    )
    return hallazgo


# ─────────────────────────────────────────────────────────────────────────────
#  Líneas de CAPEX del hallazgo
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/findings/{finding_id}/capex-items",
    status_code=status.HTTP_201_CREATED,
    response_model=Hallazgo,
)
def anadir_linea(
    finding_id: uuid.UUID, cuerpo: LineaDeCapex, s: SesionDep, usuario: UsuarioDep
) -> Any:
    """`[REQ]` P-44 · Añade otra línea al mismo hallazgo, en **otro** plazo."""
    actual = _leer(s, finding_id)
    perfil = _perfil_de_coste(s, usuario.organization_id)
    tax = s.execute(
        text("SELECT tax_pct FROM cost_profile WHERE id = :i"), {"i": str(perfil)}
    ).scalar_one()
    _insertar_linea(
        s,
        organization_id=usuario.organization_id,
        project_id=actual["project_id"],
        finding_id=finding_id,
        perfil_id=perfil,
        linea=cuerpo,
        tax_por_defecto=tax,
    )
    return _leer(s, finding_id)


class ActualizarLinea(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal | None = Field(default=None, ge=0)
    tax_pct: Decimal | None = Field(default=None, ge=0, le=1)
    measurement_unit: str | None = Field(default=None, max_length=20)
    measurement_quantity: Decimal | None = Field(default=None, ge=0)
    measurement_unit_price: Decimal | None = Field(default=None, ge=0)


@router.patch("/capex-items/{item_id}", response_model=Hallazgo)
def actualizar_linea(
    item_id: uuid.UUID,
    cuerpo: ActualizarLinea,
    s: SesionDep,
    request: Request,
    respuesta: Response,
) -> Any:
    """`[REQ]` Cualquier cambio devuelve **los totales recalculados**.

    Devolver solo la línea obligaría a la interfaz a recalcular el total por su
    cuenta, y ese cálculo duplicado es donde aparecen los descuadres entre lo
    que se ve en pantalla y lo que sale en el informe.

    `If-Match` obligatorio, y se compara contra la versión **de la línea**: dos
    personas ajustando importes distintos del mismo hallazgo no se estorban, y
    dos ajustando el mismo importe sí se enteran.

    `[LIM]` El `ETag` de la respuesta es el **del hallazgo**, porque el cuerpo
    es el hallazgo. La versión de cada línea viaja dentro, en `capex_lines`.
    """
    fila = (
        s.execute(
            text("SELECT finding_id, row_version FROM capex_item WHERE id = :i"),
            {"i": str(item_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Línea no encontrada")
    finding_id = fila["finding_id"]
    cc.comprobar(
        request,
        s,
        tabla="capex_item",
        fila_id=item_id,
        version_actual=fila["row_version"],
        que="una línea de CAPEX",
        obligatoria=True,
    )

    cambios = cuerpo.model_dump(exclude_unset=True)
    if cambios:
        if {"measurement_quantity", "measurement_unit_price"} & cambios.keys():
            # `computed_base` se recalcula sola: si se dejara a mano, una línea
            # podría enseñar un desglose que no cuadra con su propia medición.
            cambios["computed_base"] = None
        asignaciones = ", ".join(f"{c} = :{c}" for c in cambios)
        s.execute(
            text(  # noqa: S608
                f"UPDATE capex_item SET {asignaciones}, updated_at = now() WHERE id = :_id"
            ),
            {**cambios, "_id": str(item_id)},
        )
        s.execute(
            text(
                "UPDATE capex_item SET computed_base = "
                "  measurement_quantity * measurement_unit_price "
                "WHERE id = :i AND measurement_quantity IS NOT NULL "
                "  AND measurement_unit_price IS NOT NULL"
            ),
            {"i": str(item_id)},
        )
    nuevo = _leer(s, finding_id)
    cc.poner(respuesta, nuevo["row_version"])
    return nuevo


@router.delete("/capex-items/{item_id}", response_model=Hallazgo)
def borrar_linea(item_id: uuid.UUID, s: SesionDep, request: Request, respuesta: Response) -> Any:
    """`If-Match` obligatorio: borrar una línea cuyo importe otro acaba de
    corregir es exactamente la pérdida que esto viene a evitar."""
    fila = (
        s.execute(
            text("SELECT finding_id, row_version FROM capex_item WHERE id = :i"),
            {"i": str(item_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Línea no encontrada")
    cc.comprobar(
        request,
        s,
        tabla="capex_item",
        fila_id=item_id,
        version_actual=fila["row_version"],
        que="una línea de CAPEX",
        obligatoria=True,
    )
    s.execute(text("DELETE FROM capex_item WHERE id = :i"), {"i": str(item_id)})
    nuevo = _leer(s, fila["finding_id"])
    cc.poner(respuesta, nuevo["row_version"])
    return nuevo

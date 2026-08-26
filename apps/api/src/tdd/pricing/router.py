"""API del comparador de referencias de precio `[REQ]` §14.

**Ningún endpoint de este fichero sale a la red.** No hay «buscar en fuentes
externas» porque no hay ninguna fuente externa habilitada (P-06) y porque
consultar un proveedor sin licencia vigente ni revisión de sus condiciones de
uso es justo lo que el cliente prohibió. Lo que hay es:

* lo que ya está registrado, con su procedencia,
* **la lista de lo que no se ha consultado y por qué**, y
* una validación que exige una persona detrás.

Habilitar una fuente es una acción de administración con su propia trazabilidad,
y la base de datos la respalda con un `CHECK`: sin revisión documentada de las
condiciones de uso, la fila no entra.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from tdd.core import concurrencia as cc
from tdd.core.deps import SesionDep, UsuarioDep
from tdd.pricing import service

router = APIRouter(tags=["Precios"])


# ─────────────────────────────────────────────────────────────────────────────
#  Fuentes
# ─────────────────────────────────────────────────────────────────────────────


class FuenteLeida(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    source_type: str
    is_enabled: bool
    tos_reviewed: bool
    tos_url: str | None
    license_expires_at: date | None
    disabled_reason: str | None
    #: `None` si la fuente se puede usar. Si no, por qué no.
    motivo_de_no_consulta: str | None


_FUENTE = (
    "SELECT id, code, name, CAST(source_type AS text) AS source_type, is_enabled, "
    "tos_reviewed, tos_url, license_expires_at, disabled_reason FROM price_source"
)


def _con_motivo(fila: Any) -> dict[str, Any]:
    fuente = service.Fuente(
        code=fila["code"],
        name=fila["name"],
        source_type=service.TipoDeFuente(fila["source_type"]),
        is_enabled=fila["is_enabled"],
        tos_reviewed=fila["tos_reviewed"],
        disabled_reason=fila["disabled_reason"],
        license_expires_at=fila["license_expires_at"],
        tos_url=fila["tos_url"],
    )
    return {
        **dict(fila),
        "motivo_de_no_consulta": service.motivo_de_no_consulta(fuente, hoy=date.today()),
    }


@router.get("/price-sources", response_model=list[FuenteLeida])
def listar_fuentes(s: SesionDep) -> Any:
    """Todas las fuentes, **habilitadas y no habilitadas**.

    Las que no lo están salen con su motivo: una pantalla que solo enseña las
    disponibles hace creer que se ha buscado en todas partes.
    """
    filas = s.execute(text(f"{_FUENTE} ORDER BY name")).mappings().all()  # noqa: S608
    return [_con_motivo(f) for f in filas]


class AltaDeFuente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=160)
    source_type: service.TipoDeFuente
    tos_url: str | None = None
    license_reference: str | None = Field(default=None, max_length=160)
    license_expires_at: date | None = None
    disabled_reason: str | None = None


@router.post("/price-sources", status_code=status.HTTP_201_CREATED, response_model=FuenteLeida)
def crear_fuente(cuerpo: AltaDeFuente, s: SesionDep, usuario: UsuarioDep) -> Any:
    """Da de alta una fuente. **Nace deshabilitada**, siempre.

    `[REQ]` Habilitarla exige una revisión documentada de sus condiciones de uso,
    que es otra llamada y deja rastro. Que naciera habilitada convertiría un
    alta rutinaria en una autorización tácita para consultar a un tercero.
    """
    if usuario.org_role != "ADMIN":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Solo un administrador gestiona las fuentes de precio"
        )
    nueva = s.execute(
        text(
            "INSERT INTO price_source (organization_id, code, name, source_type, is_enabled, "
            "tos_url, license_reference, license_expires_at, disabled_reason) "
            "VALUES (:o, :c, :n, CAST(:t AS price_source_type), FALSE, :u, :lr, :le, :d) "
            "RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "c": cuerpo.code,
            "n": cuerpo.name,
            "t": cuerpo.source_type.value,
            "u": cuerpo.tos_url,
            "lr": cuerpo.license_reference,
            "le": cuerpo.license_expires_at,
            "d": cuerpo.disabled_reason,
        },
    ).scalar_one()
    fila = s.execute(text(f"{_FUENTE} WHERE id = :i"), {"i": str(nueva)}).mappings().one()  # noqa: S608
    return _con_motivo(fila)


class RevisionDeCondiciones(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: `[REQ]` Afirmar que se han leído las condiciones es un acto explícito.
    he_revisado_las_condiciones: bool
    tos_url: str | None = None
    license_reference: str | None = Field(default=None, max_length=160)
    license_expires_at: date | None = None
    habilitar: bool = False
    disabled_reason: str | None = None


@router.post("/price-sources/{source_id}/review", response_model=FuenteLeida)
def revisar_condiciones(
    source_id: uuid.UUID, cuerpo: RevisionDeCondiciones, s: SesionDep, usuario: UsuarioDep
) -> Any:
    """`[REQ]` Registra la revisión de las condiciones de uso y, si procede,
    habilita la fuente.

    Es el único camino para que una fuente pase a habilitada, y queda con nombre
    y fecha. La base de datos lo respalda con un `CHECK`: si esto se saltara, la
    fila no entraría igual.

    **Habilitar una fuente no dispara ninguna consulta.** Solo deja de decir que
    no se ha mirado; lo que se registre después seguirá entrando a mano o por
    importación, porque en este sistema no hay ningún cliente HTTP de precios.
    """
    if usuario.org_role != "ADMIN":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Solo un administrador revisa las condiciones de uso"
        )
    if cuerpo.habilitar and not cuerpo.he_revisado_las_condiciones:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No se puede habilitar una fuente sin declarar que se han revisado "
            "sus condiciones de uso.",
        )
    hay = s.execute(
        text(
            "UPDATE price_source SET tos_reviewed = :r, "
            "  tos_reviewed_by = CASE WHEN :r THEN CAST(:u AS uuid) ELSE NULL END, "
            "  tos_reviewed_at = CASE WHEN :r THEN now() ELSE NULL END, "
            "  tos_url = COALESCE(:tu, tos_url), "
            "  license_reference = COALESCE(:lr, license_reference), "
            "  license_expires_at = COALESCE(:le, license_expires_at), "
            "  is_enabled = :h, disabled_reason = :d "
            "WHERE id = :i RETURNING id"
        ),
        {
            "r": cuerpo.he_revisado_las_condiciones,
            "u": str(usuario.id),
            "tu": cuerpo.tos_url,
            "lr": cuerpo.license_reference,
            "le": cuerpo.license_expires_at,
            "h": cuerpo.habilitar,
            "d": cuerpo.disabled_reason,
            "i": str(source_id),
        },
    ).first()
    if hay is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuente no encontrada")

    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, after_data, severity) VALUES (:o, :u, 'PRICE_SOURCE_REVIEWED', "
            "'price_source', :i, CAST(:d AS jsonb), 'AVISO')"
        ),
        {
            "o": str(usuario.organization_id),
            "u": str(usuario.id),
            "i": str(source_id),
            "d": (
                f'{{"revisada": {str(cuerpo.he_revisado_las_condiciones).lower()}, '
                f'"habilitada": {str(cuerpo.habilitar).lower()}}}'
            ),
        },
    )
    fila = s.execute(text(f"{_FUENTE} WHERE id = :i"), {"i": str(source_id)}).mappings().one()  # noqa: S608
    return _con_motivo(fila)


# ─────────────────────────────────────────────────────────────────────────────
#  Referencias
# ─────────────────────────────────────────────────────────────────────────────


class ReferenciaLeida(BaseModel):
    id: uuid.UUID
    source_code: str
    source_name: str
    source_type: str
    description: str
    unit: str
    unit_price: Decimal
    currency: str
    price_date: date | None
    retrieved_at: Any | None
    geo_scope: str | None
    includes_tax: bool | None
    includes_installation: bool | None
    scope_included: str | None
    scope_excluded: str | None
    provenance_note: str | None
    source_url: str | None


class NoConsultada(BaseModel):
    code: str
    name: str
    motivo: str


class Comparacion(BaseModel):
    referencias: list[ReferenciaLeida]
    #: `[REQ]` §14 · Lo que **no** se ha mirado, y por qué.
    no_consultadas: list[NoConsultada]
    aviso: str


_REFERENCIA = (
    "SELECT pr.id, ps.code AS source_code, ps.name AS source_name, "
    "CAST(ps.source_type AS text) AS source_type, pr.description, pr.unit, pr.unit_price, "
    "pr.currency, pr.price_date, pr.retrieved_at, pr.geo_scope, pr.includes_tax, "
    "pr.includes_installation, pr.scope_included, pr.scope_excluded, pr.provenance_note, "
    "pr.source_url FROM price_reference pr JOIN price_source ps ON ps.id = pr.price_source_id"
)


@router.get("/price-references", response_model=Comparacion)
def comparar_referencias(s: SesionDep, q: str | None = None, unit: str | None = None) -> Any:
    """El comparador `[REQ]` §14.

    **No consulta nada.** Devuelve las referencias ya registradas —tecleadas,
    importadas de un XLSX o sacadas de un PDF adjunto— y, al lado, las fuentes
    que no se han mirado con su motivo. Ninguna viene marcada como elegida.
    """
    filas = (
        s.execute(
            text(
                f"{_REFERENCIA} "  # noqa: S608
                "WHERE (CAST(:q AS text) IS NULL OR pr.description ILIKE '%' || :q || '%') "
                "  AND (CAST(:u AS text) IS NULL OR pr.unit = CAST(:u AS text))"
            ),
            {"q": q, "u": unit},
        )
        .mappings()
        .all()
    )
    fuentes = s.execute(text(f"{_FUENTE} ORDER BY name")).mappings().all()  # noqa: S608

    comparacion = service.comparar(
        [
            service.Referencia(
                id=str(f["id"]),
                source_code=f["source_code"],
                source_name=f["source_name"],
                description=f["description"],
                unit=f["unit"],
                unit_price=Decimal(str(f["unit_price"])),
                currency=f["currency"],
                price_date=f["price_date"],
                retrieved_at=f["retrieved_at"],
                geo_scope=f["geo_scope"],
                includes_tax=f["includes_tax"],
                includes_installation=f["includes_installation"],
                scope_included=f["scope_included"],
                scope_excluded=f["scope_excluded"],
                provenance_note=f["provenance_note"],
            )
            for f in filas
        ],
        [
            service.Fuente(
                code=f["code"],
                name=f["name"],
                source_type=service.TipoDeFuente(f["source_type"]),
                is_enabled=f["is_enabled"],
                tos_reviewed=f["tos_reviewed"],
                disabled_reason=f["disabled_reason"],
                license_expires_at=f["license_expires_at"],
                tos_url=f["tos_url"],
            )
            for f in fuentes
        ],
        hoy=date.today(),
    )
    # El orden lo decide el servicio; los datos completos salen de las filas.
    por_id = {str(f["id"]): dict(f) for f in filas}
    return {
        "referencias": [por_id[r.id] for r in comparacion.referencias],
        "no_consultadas": [
            {"code": f.code, "name": f.name, "motivo": f.motivo} for f in comparacion.no_consultadas
        ],
        "aviso": comparacion.aviso,
    }


class AltaDeReferencia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price_source_id: uuid.UUID
    description: str = Field(min_length=1)
    unit: str = Field(min_length=1, max_length=20)
    unit_price: Decimal = Field(ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    source_url: str | None = None
    price_date: date | None = None
    geo_scope: str | None = Field(default=None, max_length=40)
    includes_tax: bool | None = None
    includes_installation: bool | None = None
    scope_included: str | None = None
    scope_excluded: str | None = None
    provenance_note: str | None = None


@router.post("/price-references", status_code=status.HTTP_201_CREATED)
def crear_referencia(cuerpo: AltaDeReferencia, s: SesionDep, usuario: UsuarioDep) -> Any:
    """Registra una referencia **a mano**. Es la única forma de que entre una.

    `[REQ]` P-06 · No hay importación automática desde ningún proveedor. Si un
    precio sale de un PDF o de un catálogo, alguien lo teclea y lo firma con su
    usuario, que es lo que hace que se pueda preguntar por él.
    """
    nueva = s.execute(
        text(
            "INSERT INTO price_reference (organization_id, price_source_id, description, unit, "
            "unit_price, currency, source_url, retrieved_at, price_date, geo_scope, includes_tax, "
            "includes_installation, scope_included, scope_excluded, provenance_note, created_by) "
            "VALUES (:o, :ps, :d, :u, :up, :c, :su, now(), :pd, :g, :it, :ii, :si, :se, :pn, :cb) "
            "RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "ps": str(cuerpo.price_source_id),
            "d": cuerpo.description,
            "u": cuerpo.unit,
            "up": cuerpo.unit_price,
            "c": cuerpo.currency,
            "su": cuerpo.source_url,
            "pd": cuerpo.price_date,
            "g": cuerpo.geo_scope,
            "it": cuerpo.includes_tax,
            "ii": cuerpo.includes_installation,
            "si": cuerpo.scope_included,
            "se": cuerpo.scope_excluded,
            "pn": cuerpo.provenance_note,
            "cb": str(usuario.id),
        },
    ).scalar_one()
    return dict(
        s.execute(text(f"{_REFERENCIA} WHERE pr.id = :i"), {"i": str(nueva)}).mappings().one()  # noqa: S608
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Actualización por índice y validación
# ─────────────────────────────────────────────────────────────────────────────


class PeticionDeIndice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: Decimal = Field(ge=0)
    #: `[REQ]` P-06 · Los dos valores los introduce el usuario. No hay catálogo
    #: de índices y no se inventa ninguno: publicar una cifra que nadie ha
    #: verificado sería exactamente inventar una fuente de precios.
    indice_origen: Decimal = Field(gt=0)
    indice_destino: Decimal = Field(gt=0)
    factor_geografico: Decimal = Field(default=Decimal("1"), gt=0)


@router.post("/prices/index-update")
def previsualizar_indice(cuerpo: PeticionDeIndice) -> Any:
    """Calcula sin guardar. Como la cascada de CAPEX, devuelve la fórmula.

    No exige sesión de base de datos: es aritmética expuesta por HTTP.
    """
    try:
        r = service.actualizar_por_indice(
            cuerpo.base,
            indice_origen=cuerpo.indice_origen,
            indice_destino=cuerpo.indice_destino,
            factor_geografico=cuerpo.factor_geografico,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return {
        "base": str(r.base),
        "resultado": str(r.resultado),
        "formula": r.formula,
        "nota": (
            "No se ha aplicado nada. Al aplicarlo, el precio vuelve a quedar "
            "pendiente de validación."
        ),
    }


class ValidacionDePrecio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: El importe que se aplica. Editable: puede no ser el de ninguna referencia.
    amount: Decimal = Field(ge=0)
    price_reference_id: uuid.UUID | None = None
    justificacion: str | None = None


@router.post("/capex-items/{item_id}/validate-price")
def validar_precio(
    item_id: uuid.UUID,
    cuerpo: ValidacionDePrecio,
    s: SesionDep,
    usuario: UsuarioDep,
    request: Request,
) -> Any:
    """`[REQ]` Da un precio por bueno. **Con una persona detrás, siempre.**

    Nada valida un precio automáticamente. La base de datos lo respalda: su
    `CHECK` exige revisor, fecha y nota para que la fila llegue a `VALIDADO`.
    """
    from tdd.findings.router import leer_hallazgo

    fila = (
        s.execute(
            text("SELECT finding_id, amount, row_version FROM capex_item WHERE id = :i"),
            {"i": str(item_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Línea no encontrada")
    # Se honra si viene: validar un precio que otro acaba de cambiar dejaría la
    # validación apuntando a un importe que ya no es el que se revisó.
    cc.comprobar(
        request,
        s,
        tabla="capex_item",
        fila_id=item_id,
        version_actual=fila["row_version"],
        que="una línea de CAPEX",
    )

    if cuerpo.price_reference_id is None:
        # El `CHECK` de la base lo exige igualmente; aquí sale un 422 que dice
        # qué hacer en vez de un error de integridad que no dice nada.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, service.SIN_PROCEDENCIA)

    referencia = None
    if cuerpo.price_reference_id is not None:
        cruda = (
            s.execute(
                text(f"{_REFERENCIA} WHERE pr.id = :i"),  # noqa: S608
                {"i": str(cuerpo.price_reference_id)},
            )
            .mappings()
            .first()
        )
        if cruda is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Referencia no encontrada")
        referencia = service.Referencia(
            id=str(cruda["id"]),
            source_code=cruda["source_code"],
            source_name=cruda["source_name"],
            description=cruda["description"],
            unit=cruda["unit"],
            unit_price=Decimal(str(cruda["unit_price"])),
            currency=cruda["currency"],
            price_date=cruda["price_date"],
        )

    try:
        nota = service.comprobar_validacion(
            importe=cuerpo.amount,
            referencia=referencia,
            justificacion=cuerpo.justificacion,
        )
    except service.ValidacionRechazada as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    s.execute(
        text(
            "UPDATE capex_item SET amount = :a, price_status = 'VALIDADO', "
            "price_validated_by = :u, price_validated_at = now(), price_validation_note = :n, "
            "selected_price_reference_id = :r, updated_at = now() WHERE id = :i"
        ),
        {
            "a": cuerpo.amount,
            "u": str(usuario.id),
            "n": nota,
            "r": str(cuerpo.price_reference_id) if cuerpo.price_reference_id else None,
            "i": str(item_id),
        },
    )
    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, before_data, after_data, severity) VALUES (:o, :u, 'PRICE_VALIDATED', "
            "'capex_item', :i, CAST(:antes AS jsonb), CAST(:despues AS jsonb), 'INFO')"
        ),
        {
            "o": str(usuario.organization_id),
            "u": str(usuario.id),
            "i": str(item_id),
            "antes": f'{{"amount": "{fila["amount"]}"}}',
            "despues": f'{{"amount": "{cuerpo.amount}"}}',
        },
    )
    return leer_hallazgo(s, fila["finding_id"])

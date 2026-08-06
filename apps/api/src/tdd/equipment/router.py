"""API del inventario de equipo `[REQ]` §7 / P-15.

**Es opcional, y eso se nota en que no aparece en ninguna otra parte.** Ningún
hallazgo lo exige, ninguna línea de CAPEX lo referencia y ningún informe se
bloquea por no tenerlo. Un encargo entero se puede entregar sin dar de alta un
solo equipo. Está aquí porque en una visita a un edificio con instalaciones
alguien apunta el fabricante, el modelo y el año de la enfriadora en una
libreta, y esa libreta acaba siendo la única fuente para justificar por qué se
propone sustituirla.

**La vida residual no se teclea** (P-15). Se guarda el año de instalación y la
vida útil esperada; lo que queda se calcula al leer, en `service.py`. Ver ahí
por qué no puede ser una columna generada.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core.deps import SesionDep, UsuarioDep
from tdd.equipment import service

router = APIRouter(tags=["Inventario de equipo"])


class Equipo(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    asset_id: uuid.UUID
    technical_system_id: uuid.UUID | None
    technical_system_name: str | None
    zone_id: uuid.UUID | None
    zone_name: str | None
    tag: str | None
    equipment_type: str
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    install_year: int | None
    expected_life_years: int | None
    condition: str | None
    obsolescence: str | None
    criticality: str | None
    quantity: Decimal
    unit: str
    has_documentation: bool
    notes: str | None

    # Calculado, nunca almacenado. P-15.
    end_of_life_year: int | None
    remaining_life_years: int | None
    vencido: bool
    horizonte_code: str | None
    horizonte_name: str | None
    vida_resumen: str


class DatosDeEquipo(BaseModel):
    """`extra="forbid"`: un campo mal escrito se rechaza en vez de perderse."""

    model_config = ConfigDict(extra="forbid")

    asset_id: uuid.UUID
    equipment_type: str = Field(min_length=1, max_length=120)
    technical_system_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    tag: str | None = Field(default=None, max_length=40)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    install_year: int | None = Field(default=None, ge=1800, le=2200)
    expected_life_years: int | None = Field(default=None, gt=0, le=200)
    condition: str | None = None
    obsolescence: str | None = None
    criticality: str | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit: str = Field(default="ud", min_length=1, max_length=20)
    has_documentation: bool = False
    notes: str | None = None


class CambioDeEquipo(BaseModel):
    """Todo opcional: un `PATCH` corrige un campo sin reenviar la ficha entera."""

    model_config = ConfigDict(extra="forbid")

    equipment_type: str | None = Field(default=None, min_length=1, max_length=120)
    technical_system_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    tag: str | None = Field(default=None, max_length=40)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    install_year: int | None = Field(default=None, ge=1800, le=2200)
    expected_life_years: int | None = Field(default=None, gt=0, le=200)
    condition: str | None = None
    obsolescence: str | None = None
    criticality: str | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    has_documentation: bool | None = None
    notes: str | None = None


_CAMPOS = """
    e.id, e.project_id, e.asset_id, e.technical_system_id, e.zone_id, e.tag,
    e.equipment_type, e.manufacturer, e.model, e.serial_number,
    e.install_year, e.expected_life_years, e.end_of_life_year,
    CAST(e.condition AS text) AS condition,
    CAST(e.obsolescence AS text) AS obsolescence,
    CAST(e.criticality AS text) AS criticality,
    e.quantity, e.unit, e.has_documentation, e.notes,
    ts.name_es AS technical_system_name, z.name_es AS zone_name
"""

_DESDE = """
    FROM equipment e
    LEFT JOIN technical_system ts ON ts.id = e.technical_system_id
    LEFT JOIN zone z ON z.id = e.zone_id
"""

#: Las enumeraciones de la base. Se repiten aquí para poder devolver un 422 que
#: diga los valores válidos, en vez de un error de tipo de PostgreSQL que
#: menciona un nombre de tipo interno.
VALORES = {
    "condition": ["BUENO", "ACEPTABLE", "DEFICIENTE", "MUY_DEFICIENTE", "FUERA_DE_SERVICIO"],
    "obsolescence": ["ACTUAL", "PROXIMO_A_OBSOLETO", "OBSOLETO", "SIN_REPUESTOS"],
    "criticality": ["ALTA", "MEDIA", "BAJA"],
}


def _comprobar_enumerados(datos: dict[str, Any]) -> None:
    for campo, validos in VALORES.items():
        valor = datos.get(campo)
        if valor is not None and valor not in validos:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"«{campo}» no admite «{valor}». Valores válidos: {', '.join(validos)}.",
            )


def _horizontes(s: Session) -> list[service.Horizonte]:
    filas = (
        s.execute(
            text(
                "SELECT code, name_es, year_from, year_to FROM time_horizon "
                "WHERE is_execution_term ORDER BY sort_order"
            )
        )
        .mappings()
        .all()
    )
    return [service.Horizonte(**dict(f)) for f in filas]


def _con_vida(fila: Any, horizontes: list[service.Horizonte], *, anio: int) -> dict[str, Any]:
    vida = service.calcular_vida(fila["end_of_life_year"], horizontes, anio_actual=anio)
    return {
        **dict(fila),
        "end_of_life_year": vida.end_of_life_year,
        "remaining_life_years": vida.remaining_life_years,
        "vencido": vida.vencido,
        "horizonte_code": vida.horizonte_code,
        "horizonte_name": vida.horizonte_name,
        "vida_resumen": vida.resumen,
    }


def _leer(s: Session, equipment_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text(f"SELECT {_CAMPOS} {_DESDE} WHERE e.id = :i AND e.deleted_at IS NULL"),  # noqa: S608
            {"i": str(equipment_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    return _con_vida(fila, _horizontes(s), anio=date.today().year)


@router.get("/projects/{project_id}/equipment", response_model=list[Equipo])
def listar(
    project_id: uuid.UUID,
    s: SesionDep,
    asset_id: uuid.UUID | None = None,
    technical_system_id: uuid.UUID | None = None,
    q: str | None = None,
    solo_vencidos: bool = False,
) -> Any:
    """El inventario del encargo, con filtros.

    `solo_vencidos` compara contra el año en curso en SQL y no contra un valor
    guardado: un inventario cargado en 2025 tiene que seguir diciendo la verdad
    en 2027 sin que nadie lo recalcule.
    """
    filas = (
        s.execute(
            text(
                f"SELECT {_CAMPOS} {_DESDE} "  # noqa: S608
                "WHERE e.project_id = :p AND e.deleted_at IS NULL "
                "  AND (CAST(:a AS uuid) IS NULL OR e.asset_id = CAST(:a AS uuid)) "
                "  AND (CAST(:ts AS uuid) IS NULL OR e.technical_system_id = CAST(:ts AS uuid)) "
                "  AND (CAST(:q AS text) IS NULL "
                "       OR e.search_vector @@ plainto_tsquery('spanish', CAST(:q AS text))) "
                "  AND (NOT :v OR (e.end_of_life_year IS NOT NULL "
                "                  AND e.end_of_life_year < EXTRACT(YEAR FROM current_date))) "
                "ORDER BY ts.sort_order NULLS LAST, e.tag NULLS LAST, e.equipment_type"
            ),
            {
                "p": str(project_id),
                "a": str(asset_id) if asset_id else None,
                "ts": str(technical_system_id) if technical_system_id else None,
                "q": q,
                "v": solo_vencidos,
            },
        )
        .mappings()
        .all()
    )
    horizontes = _horizontes(s)
    anio = date.today().year
    return [_con_vida(f, horizontes, anio=anio) for f in filas]


@router.post(
    "/projects/{project_id}/equipment",
    status_code=status.HTTP_201_CREATED,
    response_model=Equipo,
)
def crear(project_id: uuid.UUID, cuerpo: DatosDeEquipo, s: SesionDep, usuario: UsuarioDep) -> Any:
    datos = cuerpo.model_dump()
    _comprobar_enumerados(datos)

    # El activo tiene que ser del encargo. Sin esto se podría colgar un equipo
    # de un activo de otro proyecto de la misma organización, y el inventario
    # dejaría de cuadrar sin que nada avisara.
    if (
        s.execute(
            text("SELECT 1 FROM asset WHERE id = :a AND project_id = :p AND deleted_at IS NULL"),
            {"a": str(cuerpo.asset_id), "p": str(project_id)},
        ).first()
        is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El activo no pertenece a este proyecto")

    nuevo = s.execute(
        text(
            "INSERT INTO equipment (organization_id, project_id, asset_id, technical_system_id, "
            "zone_id, tag, equipment_type, manufacturer, model, serial_number, install_year, "
            "expected_life_years, condition, obsolescence, criticality, quantity, unit, "
            "has_documentation, notes, created_by) "
            "VALUES (:o, :p, :a, :ts, :z, :tag, :et, :man, :mod, :sn, :iy, :el, "
            "  CAST(:cond AS equipment_condition), CAST(:obs AS equipment_obsolescence), "
            "  CAST(:crit AS equipment_criticality), :qty, :u, :hd, :n, :cb) "
            "RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "p": str(project_id),
            "a": str(cuerpo.asset_id),
            "ts": str(cuerpo.technical_system_id) if cuerpo.technical_system_id else None,
            "z": str(cuerpo.zone_id) if cuerpo.zone_id else None,
            "tag": (cuerpo.tag or "").strip() or None,
            "et": cuerpo.equipment_type.strip(),
            "man": cuerpo.manufacturer,
            "mod": cuerpo.model,
            "sn": cuerpo.serial_number,
            "iy": cuerpo.install_year,
            "el": cuerpo.expected_life_years,
            "cond": cuerpo.condition,
            "obs": cuerpo.obsolescence,
            "crit": cuerpo.criticality,
            "qty": cuerpo.quantity,
            "u": cuerpo.unit,
            "hd": cuerpo.has_documentation,
            "n": cuerpo.notes,
            "cb": str(usuario.id),
        },
    ).scalar_one()
    return _leer(s, nuevo)


@router.get("/equipment/{equipment_id}", response_model=Equipo)
def leer(equipment_id: uuid.UUID, s: SesionDep) -> Any:
    return _leer(s, equipment_id)


@router.patch("/equipment/{equipment_id}", response_model=Equipo)
def modificar(equipment_id: uuid.UUID, cuerpo: CambioDeEquipo, s: SesionDep) -> Any:
    cambios = cuerpo.model_dump(exclude_unset=True)
    if not cambios:
        return _leer(s, equipment_id)
    _comprobar_enumerados(cambios)

    enumerados = {
        "condition": "equipment_condition",
        "obsolescence": "equipment_obsolescence",
        "criticality": "equipment_criticality",
    }
    trozos = []
    for campo in cambios:
        if campo in enumerados:
            trozos.append(f"{campo} = CAST(:{campo} AS {enumerados[campo]})")
        else:
            trozos.append(f"{campo} = :{campo}")
    parametros: dict[str, Any] = {
        k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in cambios.items()
    }
    if "tag" in parametros:
        parametros["tag"] = (parametros["tag"] or "").strip() or None
    parametros["i"] = str(equipment_id)

    hay = s.execute(
        text(  # noqa: S608
            f"UPDATE equipment SET {', '.join(trozos)}, updated_at = now() "
            "WHERE id = :i AND deleted_at IS NULL RETURNING id"
        ),
        parametros,
    ).first()
    if hay is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    return _leer(s, equipment_id)


@router.delete("/equipment/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(equipment_id: uuid.UUID, s: SesionDep) -> None:
    """Borrado lógico.

    La ficha se ha escrito en una visita a la que no se vuelve. Borrarla de
    verdad significaría volver al edificio para recuperar el número de serie de
    una enfriadora.
    """
    hay = s.execute(
        text(
            "UPDATE equipment SET deleted_at = now(), updated_at = now() "
            "WHERE id = :i AND deleted_at IS NULL RETURNING id"
        ),
        {"i": str(equipment_id)},
    ).first()
    if hay is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")

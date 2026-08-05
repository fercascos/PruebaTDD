"""API de catálogos.

El endpoint que importa aquí es `GET /catalogs/zones?typology_id=`: es lo que
hace posible el desplegable dependiente sin duplicar la regla en el frontend.
La matriz de 86 relaciones vive en la base de datos y **en un solo sitio**.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from tdd.core.deps import SesionDep

router = APIRouter(prefix="/catalogs", tags=["Catálogos"])


class ElementoCatalogo(BaseModel):
    id: uuid.UUID
    code: str
    name_es: str


class GradoDeRiesgo(ElementoCatalogo):
    score: int
    # [REQ] La definición íntegra viaja con el grado: se muestra al clasificar,
    # no en un manual aparte. Si no está a la vista en el momento de decidir,
    # cada consultor aplica su criterio y la matriz del informe deja de
    # significar nada.
    definition_es: str


class Horizonte(ElementoCatalogo):
    year_from: int | None
    year_to: int | None
    is_execution_term: bool


class CodigoCapex(ElementoCatalogo):
    level: int
    parent_id: uuid.UUID | None


@router.get("/asset-typologies", response_model=list[ElementoCatalogo])
def tipologias(s: SesionDep) -> Any:
    filas = s.execute(
        text("SELECT id, code, name_es FROM asset_typology ORDER BY sort_order")
    ).mappings().all()
    return [dict(f) for f in filas]


@router.get("/zones", response_model=list[ElementoCatalogo])
def zonas(s: SesionDep, typology_id: uuid.UUID | None = None) -> Any:
    """`[REQ]` §3.3.2 · Zonas filtradas por tipología.

    Sin `typology_id` devuelve las 20; con él, solo las que aplican. Es el
    endpoint que impide ofrecer «Almacén» en un hotel.
    """
    if typology_id is None:
        filas = s.execute(
            text("SELECT id, code, name_es FROM zone ORDER BY sort_order")
        ).mappings().all()
    else:
        filas = s.execute(
            text(
                "SELECT z.id, z.code, z.name_es FROM zone z "
                "JOIN zone_typology zt ON zt.zone_id = z.id "
                "WHERE zt.typology_id = :t ORDER BY z.sort_order"
            ),
            {"t": typology_id},
        ).mappings().all()
    return [dict(f) for f in filas]


@router.get("/risk-levels", response_model=list[GradoDeRiesgo])
def riesgos(s: SesionDep) -> Any:
    filas = s.execute(
        text("SELECT id, code, name_es, score, definition_es FROM risk_level ORDER BY score")
    ).mappings().all()
    return [dict(f) for f in filas]


@router.get("/time-horizons", response_model=list[Horizonte])
def horizontes(s: SesionDep) -> Any:
    filas = s.execute(
        text(
            "SELECT id, code, name_es, year_from, year_to, is_execution_term "
            "FROM time_horizon ORDER BY sort_order"
        )
    ).mappings().all()
    return [dict(f) for f in filas]


@router.get("/capex-concepts", response_model=list[ElementoCatalogo])
def conceptos(s: SesionDep) -> Any:
    filas = s.execute(
        text("SELECT id, code, name_es FROM capex_concept ORDER BY code")
    ).mappings().all()
    return [dict(f) for f in filas]


@router.get("/capex-codes", response_model=list[CodigoCapex])
def codigos(
    s: SesionDep,
    level: int | None = None,
    parent_id: uuid.UUID | None = None,
    q: str | None = None,
) -> Any:
    filas = s.execute(
        text(
            "SELECT id, code, name_es, level, parent_id FROM capex_code "
            "WHERE deprecated_at IS NULL "
            "  AND (:level IS NULL OR level = :level) "
            "  AND (CAST(:parent AS uuid) IS NULL OR parent_id = CAST(:parent AS uuid)) "
            "  AND (:q IS NULL OR name_es ILIKE '%' || :q || '%' OR code ILIKE '%' || :q || '%') "
            "ORDER BY code"
        ),
        {"level": level, "parent": parent_id, "q": q},
    ).mappings().all()
    return [dict(f) for f in filas]


class ComprobacionZona(BaseModel):
    permitida: bool
    motivo: str | None = None


@router.get("/zones/{zone_id}/allowed", response_model=ComprobacionZona)
def zona_permitida(zone_id: uuid.UUID, typology_id: uuid.UUID, s: SesionDep) -> Any:
    """Comprobación explícita, útil al reclasificar un activo.

    Cambiar la tipología de un activo puede dejar líneas de CAPEX en zonas que
    ya no aplican. Este endpoint alimenta la previsualización de impacto.
    """
    existe = s.execute(
        text("SELECT 1 FROM zone WHERE id = :z"), {"z": zone_id}
    ).first()
    if existe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zona desconocida")
    permitida = s.execute(
        text("SELECT 1 FROM zone_typology WHERE zone_id = :z AND typology_id = :t"),
        {"z": zone_id, "t": typology_id},
    ).first() is not None
    if permitida:
        return {"permitida": True, "motivo": None}
    nombres = s.execute(
        text(
            "SELECT z.name_es, t.name_es FROM zone z, asset_typology t "
            "WHERE z.id = :z AND t.id = :t"
        ),
        {"z": zone_id, "t": typology_id},
    ).first()
    zona, tipologia = nombres if nombres else ("la zona", "esa tipología")
    return {
        "permitida": False,
        "motivo": f"«{zona}» no aplica a un activo de tipología {tipologia}.",
    }

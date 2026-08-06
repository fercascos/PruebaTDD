"""API del CAPEX.

Dos endpoints merecen atención:

* `POST /capex/preview-calculation` calcula **sin persistir**. Alimenta el bloque
  «Cómo se calcula» de la interfaz, que muestra la fórmula con sus operandos.
* `POST /capex-items/{id}/carry-measurement` es la **acción explícita** con la
  que el consultor traslada el resultado de la medición al importe de la línea.
  P-05b exige que sea explícita: la cascada nunca se aplica sola sobre un
  importe tecleado.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from tdd.capex.engine import CascadeConfig, apply_tax, run_cascade
from tdd.core.deps import SesionDep, UsuarioDep

router = APIRouter(tags=["CAPEX"])


class Porcentajes(BaseModel):
    indirect_pct: Decimal = Field(ge=0)
    overhead_pct: Decimal = Field(ge=0)
    profit_pct: Decimal = Field(ge=0)
    fees_pct: Decimal = Field(ge=0)
    contingency_pct: Decimal = Field(ge=0)


class PeticionCalculo(BaseModel):
    quantity: Decimal = Field(ge=0)
    unit_price: Decimal = Field(ge=0)
    percentages: Porcentajes
    tax_pct: Decimal = Field(default=Decimal("0"), ge=0)
    rounding_mode: str = "HALF_UP"
    round_each_step: bool = True


class PeldanoCalculado(BaseModel):
    key: str
    label: str
    base_amount: Decimal
    pct: Decimal
    amount: Decimal


class ResultadoCalculo(BaseModel):
    direct_cost: Decimal
    steps: list[PeldanoCalculado]
    pem: Decimal | None
    pec: Decimal | None
    computed_base: Decimal
    tax_amount: Decimal
    total_with_tax: Decimal
    calc_version: int
    nota: str


@router.post("/capex/preview-calculation", response_model=ResultadoCalculo)
def previsualizar_calculo(cuerpo: PeticionCalculo) -> Any:
    """Calcula la cascada **sin tocar la base de datos**.

    No exige sesión de base de datos a propósito: es una función pura expuesta
    por HTTP, y el usuario puede jugar con los porcentajes sin efectos.
    """
    try:
        config = CascadeConfig.spanish_default(
            **cuerpo.percentages.model_dump(),
            rounding_mode=cuerpo.rounding_mode,
            round_each_step=cuerpo.round_each_step,
        )
        resultado = run_cascade(
            quantity=cuerpo.quantity, unit_price=cuerpo.unit_price, config=config
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    totales = apply_tax(resultado.computed_base, cuerpo.tax_pct)
    return {
        "direct_cost": resultado.direct_cost,
        "steps": [
            {
                "key": line.key.value,
                "label": line.label,
                "base_amount": line.base_amount,
                "pct": line.pct,
                "amount": line.amount,
            }
            for line in resultado.lines
        ],
        "pem": resultado.pem,
        "pec": resultado.pec,
        "computed_base": resultado.computed_base,
        "tax_amount": totales.tax_amount,
        "total_with_tax": totales.total_cost,
        "calc_version": resultado.calc_version,
        "nota": (
            "La cascada llega hasta la base imponible. El impuesto se aplica una sola vez, "
            "sobre el importe de la línea. Este cálculo no se ha guardado: para usarlo, "
            "trasládelo al importe con el botón correspondiente."
        ),
    }


class LineaCapex(BaseModel):
    id: uuid.UUID
    amount: Decimal
    tax_pct: Decimal
    tax_amount: Decimal
    total_cost: Decimal
    amount_source: str
    computed_base: Decimal | None
    time_horizon_code: str


_SELECT = (
    "SELECT ci.id, ci.amount, ci.tax_pct, ci.tax_amount, ci.total_cost, "
    "CAST(ci.amount_source AS text) AS amount_source, ci.computed_base, "
    "th.code AS time_horizon_code "
    "FROM capex_item ci JOIN time_horizon th ON th.id = ci.time_horizon_id"
)


@router.get("/projects/{project_id}/capex-items", response_model=list[LineaCapex])
def listar(project_id: uuid.UUID, s: SesionDep) -> Any:
    filas = (
        s.execute(
            text(f"{_SELECT} WHERE ci.project_id = :p ORDER BY ci.created_at"),  # noqa: S608
            {"p": project_id},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


class ResumenPorHorizonte(BaseModel):
    time_horizon_code: str
    time_horizon_name: str
    lines: int
    amount: Decimal
    tax_amount: Decimal
    total_cost: Decimal


@router.get(
    "/projects/{project_id}/capex/summary/by-horizon",
    response_model=list[ResumenPorHorizonte],
)
def resumen_por_horizonte(project_id: uuid.UUID, s: SesionDep) -> Any:
    """P-05 · Con un horizonte por línea, esto es un `GROUP BY`.

    Con cinco columnas editables serían cinco sumas independientes que podrían
    descuadrar entre sí; así es imposible.
    """
    filas = (
        s.execute(
            text(
                "SELECT th.code AS time_horizon_code, th.name_es AS time_horizon_name, "
                "count(ci.id) AS lines, COALESCE(sum(ci.amount), 0) AS amount, "
                "COALESCE(sum(ci.tax_amount), 0) AS tax_amount, "
                "COALESCE(sum(ci.total_cost), 0) AS total_cost "
                "FROM time_horizon th LEFT JOIN capex_item ci "
                "  ON ci.time_horizon_id = th.id AND ci.project_id = :p "
                "GROUP BY th.code, th.name_es, th.sort_order ORDER BY th.sort_order"
            ),
            {"p": project_id},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.get(
    "/projects/{project_id}/capex/export.xlsx",
    tags=["CAPEX"],
    response_class=Response,
    responses={
        200: {
            "content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}},
            "description": "Libro con la hoja CAPEX.",
        }
    },
)
def exportar_xlsx(project_id: uuid.UUID, s: SesionDep) -> Response:
    """`[REQ]` P-31 · El botón de **exportar el CAPEX a XLSX**.

    Lo pidió el cliente para poder adjuntar el fichero en el envío que el equipo
    hace fuera de la plataforma. El generador existía y estaba probado, pero no
    había ninguna ruta que lo sirviera: el botón no habría tenido a dónde
    llamar. Se detectó recorriendo la aplicación en marcha.

    `[REQ]` Consume **el mismo `CapexTableLayout`** que la tabla nativa del
    PPTX. Es lo que garantiza que el Excel que el equipo adjunta a un correo y
    el PowerPoint que va en ese mismo correo no tengan columnas distintas.

    `[LIM]` Exporta el estado **actual** del proyecto, no una versión emitida.
    Para el CAPEX congelado de un informe ya publicado está la descarga de esa
    versión, que lee de su snapshot. El nombre del fichero lo dice.
    """
    from tdd.exports.capex_xlsx import generar_xlsx
    from tdd.reporting import snapshot as snap
    from tdd.reporting.capex_layout import construir
    from tdd.reporting.generator import lineas_de_capex

    # Estados de TRABAJO, no los publicables: el equipo comparte el CAPEX
    # mientras todavía lo construye, y un fichero que se deja fuera las líneas
    # en borrador da un total que no cuadra con la pantalla desde la que se
    # pulsó el botón. Lo descartado sigue fuera.
    datos = snap.construir(s, project_id, estados=snap.ESTADOS_DE_TRABAJO)
    proyecto = datos["project"]
    lineas = lineas_de_capex(datos)
    if not lineas:
        # 409 y no un libro vacío: un Excel con la cabecera y ninguna fila se
        # adjunta a un correo sin que nadie note que no lleva nada dentro.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El encargo todavía no tiene ninguna línea de CAPEX que exportar",
        )

    layout = construir(lineas, capitulo=str(proyecto.get("name") or ""), locale="es-ES")
    nombre = f"CAPEX_{proyecto.get('internal_code') or project_id}_actual.xlsx"
    return Response(
        content=generar_xlsx(layout),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


class TrasladarMedicion(BaseModel):
    confirmar: bool = Field(
        description=(
            "Debe ser true. El traslado es una acción explícita del usuario: la "
            "aplicación nunca sustituye un importe tecleado por su cuenta [REQ] P-05b."
        )
    )


@router.post("/capex-items/{item_id}/carry-measurement", response_model=LineaCapex)
def trasladar_medicion(
    item_id: uuid.UUID, cuerpo: TrasladarMedicion, s: SesionDep, usuario: UsuarioDep
) -> Any:
    """Traslada `computed_base` al importe de la línea. **Acción explícita.**"""
    if not cuerpo.confirmar:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "El traslado exige confirmación explícita del usuario",
        )
    fila = (
        s.execute(
            text("SELECT computed_base, amount FROM capex_item WHERE id = :i"), {"i": item_id}
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Línea no encontrada")
    if fila["computed_base"] is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Esta línea no tiene desglose por medición: no hay nada que trasladar",
        )

    s.execute(
        text(
            "UPDATE capex_item SET amount = computed_base, amount_source = 'MEDICION', "
            "updated_at = now() WHERE id = :i"
        ),
        {"i": item_id},
    )
    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, before_data, after_data, severity) VALUES (:o, :u, 'CAPEX_UPDATED', "
            "'capex_item', :i, CAST(:antes AS jsonb), CAST(:despues AS jsonb), 'INFO')"
        ),
        {
            "o": usuario.organization_id,
            "u": usuario.id,
            "i": item_id,
            "antes": f'{{"amount": "{fila["amount"]}"}}',
            "despues": f'{{"amount": "{fila["computed_base"]}", "amount_source": "MEDICION"}}',
        },
    )
    nueva = (
        s.execute(
            text(f"{_SELECT} WHERE ci.id = :i"),
            {"i": item_id},  # noqa: S608
        )
        .mappings()
        .one()
    )
    return dict(nueva)

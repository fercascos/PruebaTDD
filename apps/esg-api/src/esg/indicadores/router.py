"""El panel: lo que pinta el dashboard, con sus filtros."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from esg.core.deps import SesionDep, UsuarioDep
from esg.core.errores import NO_PROCESABLE
from esg.indicadores.consultas import Filtros, panel

router = APIRouter(prefix="/api/v1/indicadores", tags=["indicadores"])

#: Tope de ventana. No es capricho: el reparto a meses se hace en memoria (ver
#: la limitación declarada en `motor.py`), y una consulta de veinte años sobre
#: una cartera entera es la forma de descubrirlo en producción.
MAXIMO_DE_DIAS = 366 * 6


class CoberturaFuera(BaseModel):
    dias_esperados: int
    dias_con_dato: int
    porcentaje: Decimal | None
    lecturas_sin_normalizar: int


class TotalFuera(BaseModel):
    vector: str
    unidad: str
    medido: Decimal
    estimado: Decimal
    variacion_porcentual: Decimal | None
    cobertura: CoberturaFuera


class PuntoDeSerie(BaseModel):
    vector: str
    mes: date
    cantidad: Decimal


class IntensidadFuera(BaseModel):
    vector: str
    por_m2: Decimal | None
    por_ocupante: Decimal | None


class ActivoDelPanel(BaseModel):
    activo_id: uuid.UUID
    codigo: str
    nombre: str
    cartera_id: uuid.UUID
    superficie_m2: Decimal | None
    superficie_de_referencia: str
    ocupantes_medios: Decimal | None
    totales: list[TotalFuera]
    intensidades: list[IntensidadFuera]


class PanelFuera(BaseModel):
    desde: date
    hasta: date
    totales: list[TotalFuera]
    serie: list[PuntoDeSerie]
    activos: list[ActivoDelPanel]


@router.get("/panel", response_model=PanelFuera)
def obtener_panel(
    sesion: SesionDep,
    usuario: UsuarioDep,
    desde: date,
    hasta: date,
    cartera: list[uuid.UUID] = Query(default_factory=list),
    activo: list[uuid.UUID] = Query(default_factory=list),
    vector: list[str] = Query(default_factory=list),
    tipologia: list[str] = Query(default_factory=list),
) -> PanelFuera:
    """`hasta` es **exclusiva**, igual que en el resto del dominio.

    Un trimestre es `desde=2025-01-01&hasta=2025-04-01`. Es lo que hace que dos
    trimestres consecutivos no compartan un día ni se dejen otro fuera.
    """
    if hasta <= desde:
        raise HTTPException(NO_PROCESABLE, "«hasta» tiene que ser posterior a «desde»")
    if (hasta - desde).days > MAXIMO_DE_DIAS:
        raise HTTPException(
            NO_PROCESABLE,
            f"La ventana no puede pasar de {MAXIMO_DE_DIAS} días",
        )

    resultado = panel(
        sesion,
        Filtros(
            desde=desde,
            hasta=hasta,
            carteras=cartera or None,
            activos=activo or None,
            vectores=vector or None,
            tipologias=tipologia or None,
        ),
    )

    def total_fuera(t, variacion: Decimal | None) -> TotalFuera:  # type: ignore[no-untyped-def]
        return TotalFuera(
            vector=t.vector,
            unidad=t.unidad,
            medido=t.medido,
            estimado=t.estimado,
            variacion_porcentual=variacion,
            cobertura=CoberturaFuera(
                dias_esperados=t.cobertura.dias_esperados,
                dias_con_dato=t.cobertura.dias_con_dato,
                porcentaje=t.cobertura.porcentaje,
                lecturas_sin_normalizar=t.cobertura.lecturas_sin_normalizar,
            ),
        )

    return PanelFuera(
        desde=resultado.desde,
        hasta=resultado.hasta,
        totales=[total_fuera(t, resultado.variacion(v)) for v, t in resultado.totales.items()],
        serie=[PuntoDeSerie(vector=v, mes=m, cantidad=c) for (v, m), c in resultado.serie.items()],
        activos=[
            ActivoDelPanel(
                activo_id=f.activo_id,
                codigo=f.codigo,
                nombre=f.nombre,
                cartera_id=f.cartera_id,
                superficie_m2=f.superficie_m2,
                superficie_de_referencia=f.superficie_de_referencia,
                ocupantes_medios=f.ocupantes_medios,
                totales=[total_fuera(t, None) for t in f.por_vector.values()],
                intensidades=[
                    IntensidadFuera(
                        vector=v,
                        por_m2=f.intensidad_por_m2(v),
                        por_ocupante=f.intensidad_por_ocupante(v),
                    )
                    for v in f.por_vector
                ],
            )
            for f in resultado.activos
        ],
    )

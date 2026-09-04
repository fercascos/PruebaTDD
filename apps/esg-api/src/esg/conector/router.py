"""Importación desde el lector de facturas y cola de revisión."""

from __future__ import annotations

import uuid

# `asdict` y no `vars`: `Incidencia` es un dataclass con `slots`, así que no
# tiene `__dict__` y `vars()` revienta. Lo hizo, en la primera carga con una
# fila mala —es decir, en el camino que más se recorre—.
from dataclasses import asdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text

from esg.conector.puerto import ConectorNoConfigurado, ErrorDelConector
from esg.conector.servicio import importar
from esg.core.deps import EscrituraDatosDep, SesionDep, SettingsDep, UsuarioDep
from esg.core.errores import NO_PROCESABLE
from esg.ingesta.router import IncidenciaFuera

router = APIRouter(prefix="/api/v1", tags=["conector"])


class ResultadoImportacion(BaseModel):
    carga_id: uuid.UUID
    facturas_leidas: int
    confirmadas: int
    pendientes_de_revision: int
    rechazadas: int
    incidencias: list[IncidenciaFuera]


@router.post("/conector/importar", response_model=ResultadoImportacion)
def importar_facturas(
    desde: date,
    hasta: date,
    request: Request,
    sesion: SesionDep,
    usuario: EscrituraDatosDep,
    settings: SettingsDep,
) -> ResultadoImportacion:
    """Trae las facturas leídas por la IA en esa ventana.

    El lector se inyecta en `app.state`, igual que la fábrica de sesiones: la
    ruta no sabe si detrás hay Azure o el doble en memoria, y eso es lo que
    permite probar esta ruta entera sin red.
    """
    if hasta <= desde:
        raise HTTPException(NO_PROCESABLE, "«hasta» tiene que ser posterior a «desde»")
    try:
        resultado = importar(
            sesion,
            request.app.state.lector_de_facturas,
            desde=desde,
            hasta=hasta,
            organizacion_id=usuario.organizacion_id,
            usuario_id=usuario.id,
            confianza_minima=settings.lector_facturas_confianza_minima,
        )
    except ConectorNoConfigurado as exc:
        # 503 y no 500: no está roto, es que esta instalación todavía no tiene
        # lector. El mensaje dice qué falta.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except ErrorDelConector as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return ResultadoImportacion(
        carga_id=resultado.carga_id,
        facturas_leidas=resultado.facturas_leidas,
        confirmadas=resultado.confirmadas,
        pendientes_de_revision=resultado.pendientes_de_revision,
        rechazadas=resultado.rechazadas,
        incidencias=[IncidenciaFuera(**asdict(i)) for i in resultado.incidencias],
    )


class LecturaPendiente(BaseModel):
    id: uuid.UUID
    activo: str
    suministro: str
    vector: str
    inicio: date
    fin: date
    cantidad: Decimal
    unidad: str
    confianza: Decimal | None
    nota: str | None


@router.get("/lecturas/pendientes", response_model=list[LecturaPendiente])
def lecturas_pendientes(
    sesion: SesionDep, usuario: UsuarioDep, limite: int = 100
) -> list[LecturaPendiente]:
    """Lo que la IA leyó con poca confianza y todavía no suma en ningún panel."""
    filas = sesion.execute(
        text(
            "SELECT l.id, a.nombre AS activo, p.codigo AS suministro, "
            "       p.vector::text AS vector, l.inicio, l.fin, l.cantidad, l.unidad, "
            "       l.confianza, l.nota "
            "FROM lectura l "
            "JOIN punto_de_suministro p ON p.id = l.punto_id "
            "JOIN activo a ON a.id = p.activo_id "
            "WHERE l.estado = 'PENDIENTE_REVISION' "
            "ORDER BY l.confianza NULLS FIRST, l.inicio LIMIT :limite"
        ),
        {"limite": min(limite, 500)},
    ).mappings()
    return [LecturaPendiente(**f) for f in filas]


class Resolucion(BaseModel):
    #: `CONFIRMADA` o `DESCARTADA`. No hay tercera opción: dejarla pendiente es
    #: no llamar a esta ruta.
    estado: str
    nota: str | None = None


@router.post("/lecturas/{lectura_id}/resolver", status_code=status.HTTP_204_NO_CONTENT)
def resolver_lectura(
    lectura_id: uuid.UUID,
    resolucion: Resolucion,
    sesion: SesionDep,
    usuario: EscrituraDatosDep,
) -> None:
    """Una persona decide sobre una lectura dudosa.

    Confirmar la mete en las sumas; descartarla la deja fuera **sin borrarla**,
    con quién y cuándo. Un dato que estuvo a punto de entrar en un informe no
    desaparece sin rastro.
    """
    if resolucion.estado not in ("CONFIRMADA", "DESCARTADA"):
        raise HTTPException(
            NO_PROCESABLE,
            "El estado tiene que ser CONFIRMADA o DESCARTADA",
        )
    afectadas: int = sesion.execute(
        text(
            "UPDATE lectura SET estado = CAST(:estado AS estado_lectura), "
            "nota = COALESCE(:nota, nota) "
            "WHERE id = :id AND estado = 'PENDIENTE_REVISION'"
        ),
        {"estado": resolucion.estado, "nota": resolucion.nota, "id": lectura_id},
        # `rowcount` lo tiene el `CursorResult` que devuelve un UPDATE, pero la
        # firma de `Session.execute` promete el `Result` genérico, que no.
    ).rowcount  # type: ignore[attr-defined]
    if not afectadas:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "No hay ninguna lectura pendiente con ese identificador"
        )

"""Traer de la base lo que el motor necesita.

Aquí solo hay `SELECT`s. Todo el cálculo vive en `motor.py`, que no sabe que
existe una base de datos: es lo que permite probar el cálculo entero sin
levantar nada y probar estas consultas con datos de verdad.

**Ninguna consulta de este módulo filtra por organización ni por ámbito.** No
es un olvido: lo hace la RLS con el contexto de la sesión. Repetir aquí el
filtro daría la falsa impresión de que la seguridad depende de acordarse.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from esg.indicadores.motor import (
    ActivoParaCalculo,
    LecturaAgregable,
    Panel,
    PuntoEsperado,
    calcular_panel,
)

_SUPERFICIE_POR_CRITERIO = {
    "BRUTA": "superficie_bruta_m2",
    "ALQUILABLE": "superficie_alquilable_m2",
    "OCUPADA": "superficie_ocupada_m2",
}


@dataclass(frozen=True, slots=True)
class Filtros:
    desde: date
    hasta: date
    carteras: list[uuid.UUID] | None = None
    activos: list[uuid.UUID] | None = None
    vectores: list[str] | None = None
    #: Tipología del activo. Un cliente compara sus oficinas con sus oficinas.
    tipologias: list[str] | None = None


def _condiciones(filtros: Filtros) -> tuple[str, dict[str, object]]:
    partes: list[str] = ["a.borrado_en IS NULL"]
    parametros: dict[str, object] = {}
    if filtros.carteras:
        partes.append("a.cartera_id = ANY(:carteras)")
        parametros["carteras"] = filtros.carteras
    if filtros.activos:
        partes.append("a.id = ANY(:activos)")
        parametros["activos"] = filtros.activos
    if filtros.tipologias:
        partes.append("a.tipologia::text = ANY(:tipologias)")
        parametros["tipologias"] = filtros.tipologias
    return " AND ".join(partes), parametros


def activos_del_filtro(session: Session, filtros: Filtros) -> list[ActivoParaCalculo]:
    donde, parametros = _condiciones(filtros)
    filas = session.execute(
        text(
            "SELECT a.id, a.cartera_id, a.codigo, a.nombre, "
            "       a.superficie_bruta_m2, a.superficie_alquilable_m2, a.superficie_ocupada_m2, "
            # La superficie de referencia del activo manda; si no la tiene,
            # se hereda la de su cartera. Es la regla del diseño, y vive en la
            # consulta para que no haya dos formas de resolverla.
            "       COALESCE(a.superficie_de_referencia, c.superficie_de_referencia)::text "
            "         AS criterio "
            "FROM activo a JOIN cartera c ON c.id = a.cartera_id "
            f"WHERE {donde} ORDER BY a.codigo"
        ),
        parametros,
    ).mappings()
    return [
        ActivoParaCalculo(
            id=f["id"],
            cartera_id=f["cartera_id"],
            codigo=f["codigo"],
            nombre=f["nombre"],
            superficie_m2=f[_SUPERFICIE_POR_CRITERIO[f["criterio"]]],
            superficie_de_referencia=f["criterio"],
        )
        for f in filas
    ]


def _puntos(
    session: Session, activos: list[uuid.UUID], vectores: list[str] | None
) -> list[PuntoEsperado]:
    if not activos:
        return []
    condicion = "p.activo_id = ANY(:activos) AND p.borrado_en IS NULL"
    parametros: dict[str, object] = {"activos": activos}
    if vectores:
        condicion += " AND p.vector::text = ANY(:vectores)"
        parametros["vectores"] = vectores
    filas = session.execute(
        text(
            "SELECT p.id, p.activo_id, p.vector::text AS vector, p.alta_en, p.baja_en "
            f"FROM punto_de_suministro p WHERE {condicion}"
        ),
        parametros,
    ).mappings()
    return [
        PuntoEsperado(
            id=f["id"],
            activo_id=f["activo_id"],
            vector=f["vector"],
            alta_en=f["alta_en"],
            baja_en=f["baja_en"],
        )
        for f in filas
    ]


def _lecturas(
    session: Session,
    activos: list[uuid.UUID],
    vectores: list[str] | None,
    desde: date,
    hasta: date,
) -> list[LecturaAgregable]:
    if not activos:
        return []
    condicion = (
        "p.activo_id = ANY(:activos) AND l.estado = 'CONFIRMADA' "
        # El solape se pregunta con rangos y no con comparaciones sueltas: una
        # factura que empieza antes de la ventana y acaba dentro también cuenta,
        # y con `l.inicio >= :desde` se habría quedado fuera.
        "AND daterange(l.inicio, l.fin, '[)') && daterange(:desde, :hasta, '[)')"
    )
    parametros: dict[str, object] = {"activos": activos, "desde": desde, "hasta": hasta}
    if vectores:
        condicion += " AND p.vector::text = ANY(:vectores)"
        parametros["vectores"] = vectores
    filas = session.execute(
        text(
            "SELECT l.punto_id, p.activo_id, a.cartera_id, p.vector::text AS vector, "
            "       l.inicio, l.fin, l.cantidad_normalizada, l.calidad::text AS calidad "
            "FROM lectura l "
            "JOIN punto_de_suministro p ON p.id = l.punto_id "
            "JOIN activo a ON a.id = p.activo_id "
            f"WHERE {condicion}"
        ),
        parametros,
    ).mappings()
    return [
        LecturaAgregable(
            punto_id=f["punto_id"],
            activo_id=f["activo_id"],
            cartera_id=f["cartera_id"],
            vector=f["vector"],
            inicio=f["inicio"],
            fin=f["fin"],
            cantidad_normalizada=f["cantidad_normalizada"],
            calidad=f["calidad"],
        )
        for f in filas
    ]


def _ocupacion(
    session: Session, activos: list[uuid.UUID], desde: date, hasta: date
) -> dict[uuid.UUID, Decimal]:
    if not activos:
        return {}
    filas = session.execute(
        text(
            "SELECT activo_id, avg(ocupantes_medios) AS media FROM ocupacion "
            "WHERE activo_id = ANY(:activos) AND mes >= :desde AND mes < :hasta "
            "GROUP BY activo_id"
        ),
        {"activos": activos, "desde": desde.replace(day=1), "hasta": hasta},
    ).mappings()
    return {f["activo_id"]: f["media"] for f in filas}


def panel(session: Session, filtros: Filtros, *, comparar: bool = True) -> Panel:
    """El panel completo de una ventana, con su comparativa."""
    activos = activos_del_filtro(session, filtros)
    ids = [a.id for a in activos]
    dias = (filtros.hasta - filtros.desde).days
    anterior_desde = date.fromordinal(filtros.desde.toordinal() - dias)
    return calcular_panel(
        desde=filtros.desde,
        hasta=filtros.hasta,
        lecturas=_lecturas(session, ids, filtros.vectores, filtros.desde, filtros.hasta),
        activos=activos,
        puntos=_puntos(session, ids, filtros.vectores),
        ocupacion=_ocupacion(session, ids, filtros.desde, filtros.hasta),
        lecturas_anteriores=(
            _lecturas(session, ids, filtros.vectores, anterior_desde, filtros.desde)
            if comparar
            else None
        ),
    )

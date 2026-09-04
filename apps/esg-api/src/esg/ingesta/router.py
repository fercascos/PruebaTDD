"""Carga manual de ficheros: proponer mapeo, simular y aplicar."""

from __future__ import annotations

import uuid

# `asdict` y no `vars`: `Incidencia` es un dataclass con `slots`, así que no
# tiene `__dict__` y `vars()` revienta. Lo hizo, en la primera carga con una
# fila mala —es decir, en el camino que más se recorre—.
from dataclasses import asdict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import text

from esg.core.deps import EscrituraDatosDep, SesionDep, UsuarioDep
from esg.core.errores import NO_PROCESABLE
from esg.ingesta.lectura_tabular import FicheroIlegible, leer
from esg.ingesta.mapeo import Mapeo, proponer
from esg.ingesta.servicio import procesar

router = APIRouter(prefix="/api/v1/cargas", tags=["ingesta"])

#: Tope de tamaño del fichero subido. Un Excel de consumos de una cartera
#: entera no pasa de unos pocos MB; lo que llega por encima de esto suele ser
#: un fichero equivocado, y leerlo entero en memoria para descubrirlo es la
#: forma de tumbar el proceso.
MAXIMO_MB = 25


class IncidenciaFuera(BaseModel):
    fila: int | None
    columna: str | None
    codigo: str
    mensaje: str
    valor: str | None


class MapeoFuera(BaseModel):
    columnas: dict[str, str]
    faltan: list[str]
    avisos: list[str]
    cabeceras: list[str]


class ResultadoFuera(BaseModel):
    carga_id: uuid.UUID | None
    aplicada: bool
    filas_totales: int
    filas_aceptadas: int
    filas_rechazadas: int
    filas_sin_normalizar: int
    ya_cargado_antes: bool
    mapeo: MapeoFuera | None
    incidencias: list[IncidenciaFuera]


async def _leer_subida(fichero: UploadFile) -> bytes:
    contenido = await fichero.read()
    if len(contenido) > MAXIMO_MB * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"El fichero pasa de {MAXIMO_MB} MB",
        )
    return contenido


@router.post("/proponer-mapeo", response_model=MapeoFuera)
async def proponer_mapeo(
    usuario: EscrituraDatosDep,
    fichero: UploadFile = File(...),
    hoja: str | None = Form(default=None),
    vector_por_defecto: str | None = Form(default=None),
) -> MapeoFuera:
    """Qué columna es qué, antes de tocar nada. No escribe una sola fila."""
    contenido = await _leer_subida(fichero)
    try:
        tabla = leer(contenido, nombre=fichero.filename or "sin-nombre", hoja=hoja)
    except FicheroIlegible as exc:
        raise HTTPException(NO_PROCESABLE, str(exc)) from exc
    mapeo = proponer(tabla.cabeceras, vector_por_defecto=vector_por_defecto)
    return MapeoFuera(
        columnas=mapeo.columnas,
        faltan=mapeo.faltan,
        avisos=list(mapeo.avisos),
        cabeceras=tabla.cabeceras,
    )


@router.post("", response_model=ResultadoFuera)
async def cargar(
    sesion: SesionDep,
    usuario: EscrituraDatosDep,
    fichero: UploadFile = File(...),
    aplicar: bool = Form(default=False),
    hoja: str | None = Form(default=None),
    vector_por_defecto: str | None = Form(default=None),
    columnas: str | None = Form(default=None),
    fin_inclusivo: bool = Form(default=True),
) -> ResultadoFuera:
    """Simula (`aplicar=false`) o aplica la carga.

    La simulación **escribe de verdad y lo deshace**: es la única forma de que
    detecte los solapes y los duplicados, que es lo que de verdad hace fallar
    una carga. Una simulación que solo mira el fichero diría «1.200 filas
    correctas» y la carga real fallaría en la 37.
    """
    contenido = await _leer_subida(fichero)
    mapeo: Mapeo | None = None
    if columnas:
        import json

        try:
            mapeo = Mapeo(
                columnas=json.loads(columnas),
                fin_inclusivo=fin_inclusivo,
                vector_por_defecto=vector_por_defecto,
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(NO_PROCESABLE, "El mapeo de columnas no es JSON válido") from exc

    resultado = procesar(
        sesion,
        contenido=contenido,
        nombre=fichero.filename or "sin-nombre",
        organizacion_id=usuario.organizacion_id,
        usuario_id=usuario.id,
        hoja=hoja,
        mapeo=mapeo,
        vector_por_defecto=vector_por_defecto,
        aplicar=aplicar,
    )
    return ResultadoFuera(
        carga_id=resultado.carga_id,
        aplicada=resultado.aplicada,
        filas_totales=resultado.filas_totales,
        filas_aceptadas=resultado.filas_aceptadas,
        filas_rechazadas=resultado.filas_rechazadas,
        filas_sin_normalizar=resultado.filas_sin_normalizar,
        ya_cargado_antes=resultado.ya_cargado_antes,
        mapeo=(
            MapeoFuera(
                columnas=resultado.mapeo.columnas,
                faltan=resultado.mapeo.faltan,
                avisos=list(resultado.mapeo.avisos),
                cabeceras=[],
            )
            if resultado.mapeo
            else None
        ),
        incidencias=[IncidenciaFuera(**asdict(i)) for i in resultado.incidencias],
    )


class CargaFuera(BaseModel):
    id: uuid.UUID
    tipo: str
    nombre: str
    estado: str
    filas_totales: int
    filas_aceptadas: int
    filas_rechazadas: int
    creada_en: str


@router.get("", response_model=list[CargaFuera])
def listar_cargas(sesion: SesionDep, usuario: UsuarioDep, limite: int = 50) -> list[CargaFuera]:
    filas = sesion.execute(
        text(
            "SELECT id, tipo::text AS tipo, nombre, estado::text AS estado, filas_totales, "
            "filas_aceptadas, filas_rechazadas, creada_en::text AS creada_en "
            "FROM carga ORDER BY creada_en DESC LIMIT :limite"
        ),
        {"limite": min(limite, 200)},
    ).mappings()
    return [CargaFuera(**f) for f in filas]


@router.get("/{carga_id}/incidencias", response_model=list[IncidenciaFuera])
def incidencias_de_la_carga(
    carga_id: uuid.UUID, sesion: SesionDep, usuario: UsuarioDep
) -> list[IncidenciaFuera]:
    filas = sesion.execute(
        text(
            "SELECT fila, columna, codigo, mensaje, valor FROM incidencia_de_carga "
            "WHERE carga_id = :carga ORDER BY fila NULLS FIRST"
        ),
        {"carga": carga_id},
    ).mappings()
    return [IncidenciaFuera(**f) for f in filas]

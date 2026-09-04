"""Esquemas de entrada y salida de la estructura (cartera, activo, suministro)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from esg.indicadores.unidades import VECTORES

Vector = str
TIPOLOGIAS = (
    "OFICINAS",
    "COMERCIAL",
    "LOGISTICO",
    "RESIDENCIAL",
    "HOTELERO",
    "INDUSTRIAL",
    "OTROS",
)
CRITERIOS = ("BRUTA", "ALQUILABLE", "OCUPADA")
AMBITOS = ("COMUN", "PRIVATIVO", "TOTAL")


class NuevaCartera(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    codigo: str = Field(min_length=1, max_length=50)
    cliente_id: uuid.UUID | None = None
    superficie_de_referencia: str = "ALQUILABLE"


class CarteraFuera(BaseModel):
    id: uuid.UUID
    nombre: str
    codigo: str
    cliente_id: uuid.UUID | None
    cliente: str | None
    superficie_de_referencia: str
    activos: int


class NuevoActivo(BaseModel):
    cartera_id: uuid.UUID
    codigo: str = Field(min_length=1, max_length=50)
    nombre: str = Field(min_length=1, max_length=200)
    direccion: str | None = None
    municipio: str | None = None
    pais: str = "ES"
    tipologia: str = "OTROS"
    superficie_bruta_m2: Decimal | None = None
    superficie_alquilable_m2: Decimal | None = None
    superficie_ocupada_m2: Decimal | None = None
    superficie_de_referencia: str | None = None
    anio_construccion: int | None = None
    incorporado_en: date | None = None


class ActivoFuera(BaseModel):
    id: uuid.UUID
    cartera_id: uuid.UUID
    cartera: str
    codigo: str
    nombre: str
    municipio: str | None
    tipologia: str
    superficie_m2: Decimal | None
    superficie_de_referencia: str
    suministros: int


class NuevoSuministro(BaseModel):
    activo_id: uuid.UUID
    vector: str
    codigo: str = Field(min_length=1, max_length=100)
    descripcion: str | None = None
    ambito: str = "TOTAL"
    comercializadora: str | None = None
    unidad_de_factura: str
    fraccion: str | None = None
    alta_en: date | None = None
    baja_en: date | None = None


class SuministroFuera(BaseModel):
    id: uuid.UUID
    activo_id: uuid.UUID
    vector: str
    codigo: str
    descripcion: str | None
    ambito: str
    unidad_de_factura: str
    fraccion: str | None
    alta_en: date | None
    baja_en: date | None
    lecturas: int


class OcupacionEntra(BaseModel):
    mes: date
    ocupantes_medios: Decimal


def validar_enumerado(valor: str, admitidos: tuple[str, ...], campo: str) -> str:
    """Un valor fuera de catálogo se rechaza **con la lista de los que valen**.

    El desplegable de la interfaz y este catálogo salen del mismo sitio; cuando
    no era así, la interfaz ofrecía tipos que la API rechazaba.
    """
    if valor not in admitidos:
        raise ValueError(f"{campo} no válido. Se admiten: {', '.join(admitidos)}")
    return valor


VECTORES_ADMITIDOS = tuple(VECTORES)

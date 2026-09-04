"""Unidades y normalización.

Regla de oro del módulo: **lo que no se sabe convertir no se convierte**. La
función devuelve `None` y quien la llama tiene que decidir qué hace con esa
lectura —dejarla fuera de la suma y contarla en la cobertura—, que es
exactamente lo que hace el motor. La alternativa cómoda, inventar un factor
razonable, produce sumas que cuadran y que no significan nada.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

VECTORES: Final = ("AGUA", "ELECTRICIDAD", "GAS", "RESIDUOS")

#: La unidad en la que se agrega cada vector. Todo lo demás se convierte a esta.
UNIDAD_NORMAL: Final[dict[str, str]] = {
    "AGUA": "m3",
    "ELECTRICIDAD": "kWh",
    "GAS": "kWh",
    "RESIDUOS": "kg",
}

#: Cómo se escribe cada unidad en la vida real. Un fichero de un cliente trae
#: «m³», otro «M3», otro «metros cúbicos». No es una lista completa ni pretende
#: serlo: lo que no esté aquí se rechaza con su nombre en la incidencia, y se
#: añade. Adivinar por parecido acabaría convirtiendo «MW» en «MWh».
_ALIAS: Final[dict[str, str]] = {
    "kwh": "kWh",
    "kw/h": "kWh",
    "kw h": "kWh",
    "kilovatios hora": "kWh",
    "mwh": "MWh",
    "gwh": "GWh",
    "gj": "GJ",
    "th": "th",
    "termia": "th",
    "termias": "th",
    "m3": "m3",
    "m³": "m3",
    "metros cubicos": "m3",
    "metros cúbicos": "m3",
    "mc": "m3",
    "l": "l",
    "litro": "l",
    "litros": "l",
    "kg": "kg",
    "kilo": "kg",
    "kilos": "kg",
    "kilogramos": "kg",
    "t": "t",
    "tn": "t",
    "ton": "t",
    "tonelada": "t",
    "toneladas": "t",
}

#: Factores que no dependen de nada: son definiciones.
_FIJOS: Final[dict[tuple[str, str], Decimal]] = {
    ("kWh", "kWh"): Decimal(1),
    ("MWh", "kWh"): Decimal(1000),
    ("GWh", "kWh"): Decimal(1000000),
    # 1 GJ = 1e9 J; 1 kWh = 3,6e6 J.
    ("GJ", "kWh"): Decimal("277.77777778"),
    # 1 termia = 1 kcal·1000 = 4,1868 MJ → 1,163 kWh. Es una definición, no una
    # medida: la termia sigue apareciendo en facturas de gas antiguas.
    ("th", "kWh"): Decimal("1.163"),
    ("m3", "m3"): Decimal(1),
    ("l", "m3"): Decimal("0.001"),
    ("kg", "kg"): Decimal(1),
    ("t", "kg"): Decimal(1000),
}


class UnidadDesconocida(Exception):
    """No se sabe qué es esa unidad. Se dice cuál, y no se convierte."""


@dataclass(frozen=True, slots=True)
class Normalizada:
    cantidad: Decimal | None
    unidad: str
    factor: Decimal | None
    #: Por qué no se pudo normalizar. `None` cuando sí se pudo.
    motivo: str | None = None


def canonica(unidad: str) -> str:
    """Devuelve la forma canónica de una unidad escrita como sea."""
    limpia = " ".join(unidad.strip().lower().split())
    if limpia in _ALIAS:
        return _ALIAS[limpia]
    raise UnidadDesconocida(unidad)


def normalizar(
    vector: str, cantidad: Decimal, unidad: str, *, factor_gas: Decimal | None = None
) -> Normalizada:
    """Lleva una cantidad a la unidad de agregación de su vector.

    `factor_gas` es el poder calorífico superior corregido, en kWh/m³, tal y
    como lo trae **esa** factura. Se pide explícitamente y no se coge de una
    tabla general a propósito: en España va de 10,7 a 12,0 kWh/m³ según red,
    presión y periodo, y usar 11,63 para todo mete un error del 5 % en el
    vector que más pesa en la huella de un edificio con calderas.
    """
    destino = UNIDAD_NORMAL[vector]
    try:
        origen = canonica(unidad)
    except UnidadDesconocida:
        return Normalizada(None, destino, None, motivo=f"unidad desconocida: «{unidad}»")

    if vector == "GAS" and origen == "m3":
        if factor_gas is None:
            return Normalizada(
                None,
                destino,
                None,
                motivo=(
                    "gas en m³ sin poder calorífico del periodo: la lectura se guarda "
                    "pero no se agrega"
                ),
            )
        return Normalizada(_redondear(cantidad * factor_gas), destino, factor_gas)

    factor = _FIJOS.get((origen, destino))
    if factor is None:
        return Normalizada(
            None, destino, None, motivo=f"no hay conversión de «{origen}» a «{destino}»"
        )
    return Normalizada(_redondear(cantidad * factor), destino, factor)


def _redondear(v: Decimal) -> Decimal:
    """Cuatro decimales, los mismos que `NUMERIC(18,4)` de la tabla.

    Redondear aquí y no al escribir evita que el número que devuelve la API sea
    distinto del que quedó guardado, que es de esos desajustes que solo se ven
    cuando un cliente suma a mano la columna del Excel exportado.
    """
    return v.quantize(Decimal("0.0001"))

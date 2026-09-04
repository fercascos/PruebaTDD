"""Qué columna del fichero es qué campo.

Cada cliente manda su Excel. El mapeo se **propone** automáticamente por el
nombre de las cabeceras y se **confirma** desde la interfaz; la propuesta que
se confirma se guarda en la carga, así que el mes siguiente el mismo fichero
entra sin volver a emparejar nada a mano.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

#: Campos que necesita una lectura de consumo. El resto son opcionales.
OBLIGATORIOS: Final = ("suministro", "inicio", "fin", "cantidad", "unidad")

#: Cabeceras que se han visto en ficheros reales, en español e inglés. La lista
#: se amplía sin miedo: proponer de más no rompe nada, porque el mapeo se
#: confirma antes de aplicar.
_ALIAS: Final[dict[str, tuple[str, ...]]] = {
    "activo": (
        "activo",
        "edificio",
        "inmueble",
        "codigo activo",
        "código activo",
        "asset",
        "building",
        "property",
    ),
    "suministro": (
        "suministro",
        "cups",
        "contador",
        "punto de suministro",
        "punto suministro",
        "poliza",
        "póliza",
        "contrato",
        "meter",
        "supply point",
    ),
    "vector": (
        "vector",
        "tipo",
        "tipo de consumo",
        "suministro tipo",
        "energia",
        "energía",
        "utility",
        "commodity",
    ),
    "inicio": (
        "inicio",
        "fecha inicio",
        "desde",
        "periodo desde",
        "fecha desde",
        "start",
        "period start",
        "from",
    ),
    "fin": ("fin", "fecha fin", "hasta", "periodo hasta", "fecha hasta", "end", "period end", "to"),
    "cantidad": (
        "cantidad",
        "consumo",
        "consumo total",
        "importe consumo",
        "valor",
        "medida",
        "quantity",
        "consumption",
        "usage",
    ),
    "unidad": ("unidad", "unidades", "um", "udm", "unit", "uom"),
    "calidad": ("calidad", "tipo de dato", "medido", "estimado", "quality", "data quality"),
    "importe": ("importe", "coste", "euros", "importe total", "cost", "amount"),
    "moneda": ("moneda", "divisa", "currency"),
    "factor_gas": (
        "pcs",
        "poder calorifico",
        "poder calorífico",
        "factor conversion",
        "factor conversión",
        "kwh/m3",
        "kwh/m³",
    ),
    "fraccion": ("fraccion", "fracción", "residuo", "tipo de residuo", "waste stream"),
    "referencia": (
        "referencia",
        "factura",
        "num factura",
        "nº factura",
        "numero de factura",
        "invoice",
        "invoice number",
    ),
}


@dataclass(frozen=True, slots=True)
class Mapeo:
    """Campo del dominio → nombre de la columna en el fichero."""

    columnas: dict[str, str]
    #: `[REQ]` La fecha de fin que trae un fichero de facturas es **inclusiva**:
    #: «del 01/03 al 31/03». El modelo guarda `[inicio, fin)`, así que se le
    #: suma un día al entrar. Sin esto, marzo y abril se solapan un día —o
    #: dejan un día muerto— en cada uno de los doce meses, y la restricción de
    #: solape rechaza la carga entera del segundo mes.
    fin_inclusivo: bool = True
    #: Vector para todas las filas cuando el fichero no trae columna: es el
    #: caso normal de los listados que manda una comercializadora, que son de
    #: un solo suministro.
    vector_por_defecto: str | None = None
    avisos: tuple[str, ...] = field(default=())

    def columna(self, campo: str) -> str | None:
        return self.columnas.get(campo)

    @property
    def faltan(self) -> list[str]:
        ausentes = [c for c in OBLIGATORIOS if c not in self.columnas]
        if "vector" not in self.columnas and not self.vector_por_defecto:
            ausentes.append("vector")
        return ausentes

    @property
    def completo(self) -> bool:
        return not self.faltan


def _normalizar(cabecera: str) -> str:
    tabla = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")
    return " ".join(cabecera.strip().lower().translate(tabla).replace("_", " ").split())


def proponer(cabeceras: list[str], *, vector_por_defecto: str | None = None) -> Mapeo:
    """Propone un mapeo a partir de los nombres de las cabeceras.

    Empareja por igualdad de la cabecera normalizada, no por parecido. Un
    emparejamiento aproximado acertaría más veces y fallaría en silencio: la
    columna «consumo agua» y la columna «consumo agua caliente» se parecen
    demasiado como para dejar que lo decida una distancia de edición.
    """
    normalizadas = {_normalizar(c): c for c in cabeceras if c}
    columnas: dict[str, str] = {}
    for campo, alias in _ALIAS.items():
        for candidato in alias:
            if candidato in normalizadas:
                columnas[campo] = normalizadas[candidato]
                break
    avisos: list[str] = []
    sobrantes = [c for c in cabeceras if c and c not in columnas.values()]
    if sobrantes:
        avisos.append(
            "Columnas sin usar: " + ", ".join(sobrantes[:8]) + ("…" if len(sobrantes) > 8 else "")
        )
    return Mapeo(columnas=columnas, vector_por_defecto=vector_por_defecto, avisos=tuple(avisos))

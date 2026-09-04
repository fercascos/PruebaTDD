"""El contrato con el lector de facturas por IA.

El lector ya existe y corre en Azure: no se construye aquí, se consume. Lo que
sí se construye aquí es la **frontera**, y por eso es un puerto:

* Su formato exacto es la pregunta P-1 del diseño, todavía abierta. Cuando
  llegue la respuesta, cambia `azure.py` y no cambia nada más.
* La suite no puede depender de un servicio externo con clave. `EnMemoria`
  entrega las mismas facturas sin red.

`fin` es **exclusiva** en este contrato, como en todo el dominio. La conversión
desde la fecha inclusiva que trae una factura la hace el adaptador, no el
dominio: es lo único que hay que recordar al escribir un adaptador nuevo, y
está aquí escrito.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FacturaLeida:
    #: Identificador de la factura en el sistema de origen. Es lo que impide
    #: importarla dos veces: se guarda en `lectura.referencia_externa`, que
    #: tiene índice único.
    referencia: str
    suministro: str
    vector: str
    inicio: date
    fin: date
    cantidad: Decimal
    unidad: str
    #: Confianza global de la lectura, 0 a 1. Por debajo del umbral la lectura
    #: entra como PENDIENTE_REVISION y no suma en el panel hasta que alguien la
    #: mira. La IA acierta mucho; «mucho» no es «siempre», y una factura mal
    #: leída no se distingue de una buena una vez está dentro de la suma.
    confianza: float = 1.0
    #: Confianza campo a campo, tal y como la da el lector. Se guarda en la
    #: nota de la lectura: cuando alguien revisa, lo primero que necesita saber
    #: es **qué campo** venía dudoso.
    confianza_por_campo: dict[str, float] = field(default_factory=dict)
    importe: Decimal | None = None
    moneda: str | None = None
    #: Poder calorífico de la factura de gas, si el lector lo extrae.
    factor_gas: Decimal | None = None
    #: Dónde está el documento original. No se copia el PDF: se guarda el
    #: enlace, porque el original ya vive en el sistema que lo leyó y duplicarlo
    #: obligaría a mantener dos copias sincronizadas de un documento contable.
    documento_url: str | None = None


@dataclass(frozen=True, slots=True)
class Lote:
    facturas: list[FacturaLeida]
    #: Cursor de la siguiente página. `None` = no hay más.
    siguiente: str | None = None


class LectorDeFacturas(Protocol):
    def facturas(self, *, desde: date, hasta: date, cursor: str | None = None) -> Lote: ...


class LectorNoConfigurado:
    """Lo que se instala cuando no hay conector configurado.

    Falla al usarse, no al arrancar: una instalación que todavía no tiene el
    lector debe poder cargar ficheros con normalidad, y quien pulse «importar
    facturas» debe leer por qué no puede, no un error de conexión.
    """

    def facturas(self, *, desde: date, hasta: date, cursor: str | None = None) -> Lote:
        raise ConectorNoConfigurado(
            "No hay lector de facturas configurado: falta LECTOR_FACTURAS_URL"
        )


class ConectorNoConfigurado(Exception):
    pass


class ErrorDelConector(Exception):
    """El lector contestó algo que no se puede usar. Lleva el detalle dentro."""

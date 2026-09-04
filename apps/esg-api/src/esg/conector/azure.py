"""Adaptador HTTP del lector de facturas desplegado en Azure.

`[LIM]` Escrito contra el contrato **supuesto** de la pregunta P-1: `GET
/facturas?desde=&hasta=&cursor=` con clave en cabecera y respuesta JSON. No se
ha ejercitado contra el servicio real. Lo que sí está probado es todo lo que
hay detrás de esta frontera, con el doble en memoria; cuando llegue el contrato
de verdad, lo que cambia es este fichero.

Se usa `urllib` de la biblioteca estándar y no un cliente HTTP nuevo: es una
llamada GET con una cabecera. Una dependencia más en producción tiene que
ganarse el sitio.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from esg.conector.puerto import ErrorDelConector, FacturaLeida, Lote

_VECTORES = {
    "agua": "AGUA",
    "water": "AGUA",
    "electricidad": "ELECTRICIDAD",
    "electricity": "ELECTRICIDAD",
    "gas": "GAS",
    "residuos": "RESIDUOS",
    "waste": "RESIDUOS",
}


class LectorAzure:
    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        timeout: float = 30.0,
        fin_inclusiva: bool = True,
    ):
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._fin_inclusiva = fin_inclusiva

    def facturas(self, *, desde: date, hasta: date, cursor: str | None = None) -> Lote:
        parametros = {"desde": desde.isoformat(), "hasta": hasta.isoformat()}
        if cursor:
            parametros["cursor"] = cursor
        peticion = urllib.request.Request(  # noqa: S310 — URL de configuración, no de usuario
            f"{self._url}/facturas?{urllib.parse.urlencode(parametros)}",
            headers={
                "Ocp-Apim-Subscription-Key": self._api_key,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(peticion, timeout=self._timeout) as respuesta:  # noqa: S310
                datos: dict[str, Any] = json.loads(respuesta.read())
        except urllib.error.HTTPError as exc:
            raise ErrorDelConector(
                f"El lector de facturas respondió {exc.code}: {exc.reason}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ErrorDelConector(f"No se pudo hablar con el lector de facturas: {exc}") from exc

        return Lote(
            facturas=[self._traducir(f) for f in datos.get("facturas", [])],
            siguiente=datos.get("siguiente"),
        )

    def _traducir(self, bruto: dict[str, Any]) -> FacturaLeida:
        """De la respuesta del lector a la factura del dominio.

        Todo lo que puede venir mal se comprueba aquí, en la frontera: dentro
        del dominio una `FacturaLeida` ya es un dato bueno. Un campo que falta
        es un error del conector, no cien incidencias fila a fila.
        """
        try:
            inicio = _fecha(bruto["periodo_inicio"])
            fin = _fecha(bruto["periodo_fin"])
            cantidad = _decimal(bruto["cantidad"])
            vector_bruto = str(bruto["vector"]).strip().lower()
            referencia = str(bruto["referencia"])
            suministro = str(bruto["suministro"])
            unidad = str(bruto["unidad"])
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise ErrorDelConector(f"Factura ilegible del lector: {exc}") from exc

        vector = _VECTORES.get(vector_bruto, vector_bruto.upper())
        confianzas = {str(k): float(v) for k, v in (bruto.get("confianza_por_campo") or {}).items()}
        # La confianza global es **la del peor campo**, no la media: una media
        # alta esconde que la fecha del periodo venía al 40 %, y una fecha mal
        # leída mueve el consumo de mes.
        confianza = float(bruto.get("confianza", min(confianzas.values(), default=1.0)))
        return FacturaLeida(
            referencia=referencia,
            suministro=suministro,
            vector=vector,
            inicio=inicio,
            fin=fin + timedelta(days=1) if self._fin_inclusiva else fin,
            cantidad=cantidad,
            unidad=unidad,
            confianza=confianza,
            confianza_por_campo=confianzas,
            importe=_decimal(bruto["importe"]) if bruto.get("importe") is not None else None,
            moneda=bruto.get("moneda"),
            factor_gas=(
                _decimal(bruto["factor_gas"]) if bruto.get("factor_gas") is not None else None
            ),
            documento_url=bruto.get("documento_url"),
        )


def _fecha(valor: Any) -> date:
    if isinstance(valor, date):
        return valor
    return datetime.fromisoformat(str(valor)[:10]).date()


def _decimal(valor: Any) -> Decimal:
    return Decimal(str(valor))

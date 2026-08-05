"""Ciclo de vida de un hallazgo · **funciones puras**.

Un hallazgo es la fila que rellena el consultor: código CAPEX, zona, riesgo,
concepto y su importe. Su estado gobierna si sale en el informe.

`DESCARTADO` merece explicación. Existe para que **lo que se decide no incluir
deje rastro**: sin él, la única forma de quitar un hallazgo del informe sería
borrarlo, y seis meses después nadie sabría que llegó a valorarse ni por qué se
dejó fuera. En una due diligence eso es información, no basura.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class EstadoDelHallazgo(StrEnum):
    BORRADOR = "BORRADOR"
    EN_REVISION = "EN_REVISION"
    VALIDADO = "VALIDADO"
    DESCARTADO = "DESCARTADO"


#: De `VALIDADO` se puede volver a revisión: un revisor que encuentra un error
#: en algo ya validado tiene que poder devolverlo, o el flujo obliga a mentir.
TRANSICIONES: dict[EstadoDelHallazgo, frozenset[EstadoDelHallazgo]] = {
    EstadoDelHallazgo.BORRADOR: frozenset(
        {EstadoDelHallazgo.EN_REVISION, EstadoDelHallazgo.DESCARTADO}
    ),
    EstadoDelHallazgo.EN_REVISION: frozenset(
        {EstadoDelHallazgo.VALIDADO, EstadoDelHallazgo.BORRADOR, EstadoDelHallazgo.DESCARTADO}
    ),
    EstadoDelHallazgo.VALIDADO: frozenset(
        {EstadoDelHallazgo.EN_REVISION, EstadoDelHallazgo.DESCARTADO}
    ),
    EstadoDelHallazgo.DESCARTADO: frozenset({EstadoDelHallazgo.BORRADOR}),
}


class TransicionDeHallazgoNoPermitida(Exception):  # noqa: N818 — dominio en español
    """El cambio de estado no existe. Se traduce a `409`."""


class GuardaDeHallazgoIncumplida(Exception):  # noqa: N818
    """La transición existe pero falta algo. Se traduce a `422`."""


@dataclass(frozen=True, slots=True)
class HechosDelHallazgo:
    """Lo que hay que saber para decidir si puede avanzar."""

    tiene_lineas_capex: bool = False
    importe_total: Decimal = Decimal("0")
    tiene_descripcion: bool = False
    tiene_fotos: bool = False
    precios_sin_validar: int = 0


def comprobar_transicion(
    desde: EstadoDelHallazgo, hasta: EstadoDelHallazgo, hechos: HechosDelHallazgo
) -> None:
    """Valida el cambio de estado y sus guardas.

    Las guardas son deliberadamente pocas. Un hallazgo con demasiados
    requisitos para avanzar no se rellena mejor: se rellena con texto de
    relleno para poder avanzar, que es peor que dejarlo incompleto y visible.
    """
    if hasta not in TRANSICIONES[desde]:
        posibles = ", ".join(sorted(TRANSICIONES[desde])) or "ninguno"
        raise TransicionDeHallazgoNoPermitida(
            f"Un hallazgo en «{desde}» no puede pasar a «{hasta}». Destinos posibles: {posibles}"
        )
    if hasta is EstadoDelHallazgo.EN_REVISION and not hechos.tiene_descripcion:
        raise GuardaDeHallazgoIncumplida(
            "Un hallazgo sin descripción no puede pasar a revisión: es lo que lee el revisor"
        )
    if hasta is EstadoDelHallazgo.VALIDADO:
        if not hechos.tiene_lineas_capex:
            raise GuardaDeHallazgoIncumplida(
                "Un hallazgo validado necesita al menos una línea de CAPEX, "
                "aunque sea de importe cero"
            )
        if hechos.precios_sin_validar:
            raise GuardaDeHallazgoIncumplida(
                f"Quedan {hechos.precios_sin_validar} precios pendientes de validación humana"
            )


def destinos_posibles(
    desde: EstadoDelHallazgo, hechos: HechosDelHallazgo
) -> list[dict[str, object]]:
    """Cada destino con sus impedimentos, para que la interfaz muestre el botón
    **deshabilitado con su motivo** en vez de ocultarlo."""
    salida: list[dict[str, object]] = []
    for destino in sorted(TRANSICIONES[desde]):
        try:
            comprobar_transicion(desde, destino, hechos)
        except GuardaDeHallazgoIncumplida as exc:
            salida.append({"to": destino.value, "allowed": False, "blockers": [str(exc)]})
        else:
            salida.append({"to": destino.value, "allowed": True, "blockers": []})
    return salida


#: Estados que cuentan para el informe. `BORRADOR` no: lo que aún se está
#: escribiendo no debe aparecer en un documento que se entrega.
ESTADOS_QUE_SALEN_EN_EL_INFORME = frozenset(
    {EstadoDelHallazgo.EN_REVISION, EstadoDelHallazgo.VALIDADO}
)


def sale_en_el_informe(estado: EstadoDelHallazgo) -> bool:
    return estado in ESTADOS_QUE_SALEN_EN_EL_INFORME

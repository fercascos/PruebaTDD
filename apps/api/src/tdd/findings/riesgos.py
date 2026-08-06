"""Matriz de riesgos `[REQ]` §12 de `docs/09-ux-pantallas.md`.

**Riesgo × horizonte temporal**, no la clásica probabilidad × consecuencia. La
especificación revisada define el riesgo como un grado único de cuatro niveles
*ya interpretado*, no como dos ejes; cruzarlo con el plazo responde la pregunta
que se hace el inversor: *«¿cuánto de lo grave hay que pagar en los dos primeros
años?»*.

Tres cosas que parecen detalles y no lo son:

**Un hallazgo y un importe no son la misma cuenta.** Un hallazgo sin líneas de
CAPEX existe y cuesta cero —en campo se anota lo que se ve antes de saber cuánto
vale—, así que el número de hallazgos y la suma de dinero se cuentan por
separado. Mezclarlos daría un recuento que baja al añadir un importe.

**Una actuación recurrente (P-44) tiene varias líneas, una por plazo.** Cuenta
como **un** hallazgo, pero su dinero se reparte entre las columnas. Contar
líneas en vez de hallazgos inflaría el recuento justo en las actuaciones más
caras, que son las que se miran.

**Los hallazgos sin grado asignado no desaparecen.** Salen en su propia fila.
Esconderlos haría que los totales de la matriz no cuadraran con el CAPEX del
proyecto y nadie sabría por qué faltan cien mil euros.

Es lógica pura sobre filas ya leídas: se prueba sin base de datos.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

#: Etiqueta de la fila de los hallazgos sin grado. No es un código del catálogo
#: a propósito: si lo fuera, alguien acabaría creándolo en la tabla.
SIN_GRADO = "SIN_GRADO"


@dataclass(frozen=True, slots=True)
class FilaDeHallazgo:
    """Un hallazgo con **una** de sus líneas de CAPEX.

    Un hallazgo sin líneas llega una vez con `horizonte=None` e `importe=0`:
    así el recuento lo ve y la suma no se altera.
    """

    finding_id: str
    risk_code: str | None
    risk_name: str | None
    risk_score: int | None
    chapter_code: str | None
    chapter_name: str | None
    horizonte: str | None
    importe: Decimal


@dataclass(slots=True)
class Celda:
    hallazgos: int = 0
    importe: Decimal = Decimal("0")


@dataclass(slots=True)
class Grado:
    code: str
    name: str
    score: int | None
    hallazgos: int = 0
    importe: Decimal = Decimal("0")
    #: Importe por horizonte. Las claves son los códigos de `time_horizon`.
    por_horizonte: dict[str, Decimal] = field(default_factory=dict)


@dataclass(slots=True)
class Capitulo:
    code: str
    name: str
    #: Cuántos hallazgos de cada grado. `{"04": 2, "03": 1}`.
    por_grado: dict[str, int] = field(default_factory=dict)
    importe: Decimal = Decimal("0")


@dataclass(slots=True)
class Matriz:
    grados: list[Grado]
    capitulos: list[Capitulo]
    #: Totales de cada columna, en el orden de `horizontes`.
    total_por_horizonte: dict[str, Decimal]
    total_hallazgos: int
    total_importe: Decimal

    def como_json(self, horizontes: list[str]) -> dict[str, Any]:
        return {
            "horizontes": horizontes,
            "grados": [
                {
                    "code": g.code,
                    "name": g.name,
                    "score": g.score,
                    "hallazgos": g.hallazgos,
                    "importe": str(g.importe),
                    "por_horizonte": {
                        h: str(g.por_horizonte.get(h, Decimal("0"))) for h in horizontes
                    },
                }
                for g in self.grados
            ],
            "capitulos": [
                {
                    "code": c.code,
                    "name": c.name,
                    "por_grado": c.por_grado,
                    "importe": str(c.importe),
                }
                for c in self.capitulos
            ],
            "total_por_horizonte": {
                h: str(self.total_por_horizonte.get(h, Decimal("0"))) for h in horizontes
            },
            "total_hallazgos": self.total_hallazgos,
            "total_importe": str(self.total_importe),
        }


def construir(
    filas: list[FilaDeHallazgo],
    *,
    grados_del_catalogo: list[tuple[str, str, int]],
    horizontes: list[str],
) -> Matriz:
    """Agrega las filas en la matriz.

    `grados_del_catalogo` llega entero y en orden aunque no haya ningún hallazgo
    de ese grado: una matriz a la que le faltan filas según el proyecto no se
    puede comparar con la del encargo siguiente, y el lector no sabe si es que
    no hay nada o es que la fila se ha caído.
    """
    # Un hallazgo aparece tantas veces como líneas tenga (P-44). Se recuerda
    # cuál se ha contado ya para no inflar el recuento en las actuaciones
    # recurrentes, que son justo las más caras.
    vistos_por_grado: dict[str, set[str]] = defaultdict(set)
    vistos_por_capitulo: dict[str, set[str]] = defaultdict(set)
    todos_los_hallazgos: set[str] = set()

    grados = {
        code: Grado(code=code, name=name, score=score) for code, name, score in grados_del_catalogo
    }
    grados[SIN_GRADO] = Grado(code=SIN_GRADO, name="Sin clasificar", score=None)
    capitulos: dict[str, Capitulo] = {}
    total_por_horizonte: dict[str, Decimal] = dict.fromkeys(horizontes, Decimal("0"))
    total_importe = Decimal("0")

    for fila in filas:
        clave = fila.risk_code or SIN_GRADO
        grado = grados.get(clave)
        if grado is None:
            # Un grado que ya no está en el catálogo —retirado después de
            # clasificar— no puede hacer desaparecer el hallazgo del total.
            grado = Grado(code=clave, name=fila.risk_name or clave, score=fila.risk_score)
            grados[clave] = grado

        if fila.finding_id not in vistos_por_grado[clave]:
            vistos_por_grado[clave].add(fila.finding_id)
            grado.hallazgos += 1
        todos_los_hallazgos.add(fila.finding_id)

        grado.importe += fila.importe
        total_importe += fila.importe
        if fila.horizonte:
            grado.por_horizonte[fila.horizonte] = (
                grado.por_horizonte.get(fila.horizonte, Decimal("0")) + fila.importe
            )
            total_por_horizonte[fila.horizonte] = (
                total_por_horizonte.get(fila.horizonte, Decimal("0")) + fila.importe
            )

        if fila.chapter_code:
            capitulo = capitulos.setdefault(
                fila.chapter_code,
                Capitulo(code=fila.chapter_code, name=fila.chapter_name or fila.chapter_code),
            )
            if fila.finding_id not in vistos_por_capitulo[fila.chapter_code]:
                vistos_por_capitulo[fila.chapter_code].add(fila.finding_id)
                capitulo.por_grado[clave] = capitulo.por_grado.get(clave, 0) + 1
            capitulo.importe += fila.importe

    # Los grados de mayor a menor: lo grave arriba, que es donde se mira.
    # `SIN_GRADO` al final, sin score, para que no se cuele entre los ordenados.
    ordenados = sorted(
        grados.values(),
        key=lambda g: (g.score is None, -(g.score or 0), g.code),
    )
    # Los capítulos por dinero: el que más pesa primero.
    capitulos_ordenados = sorted(capitulos.values(), key=lambda c: (-c.importe, c.code))

    return Matriz(
        grados=ordenados,
        capitulos=capitulos_ordenados,
        total_por_horizonte=total_por_horizonte,
        total_hallazgos=len(todos_los_hallazgos),
        total_importe=total_importe,
    )

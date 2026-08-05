"""Motor de cálculo de CAPEX.

`[REC]` **Función pura.** No accede a base de datos, ni a red, ni al reloj.
Entran datos, salen datos. Eso lo hace comprobable al céntimo y en milisegundos,
y es lo que permite que la cascada sea auditable.

Dos reglas que este módulo hace cumplir, y que vienen de decisiones del cliente:

* **P-05b · La cascada NUNCA se aplica sobre un importe tecleado a mano.** Ese
  importe ya es la base imponible final —lleva dentro indirectos, honorarios y
  contingencia—. La cascada es una *calculadora* opcional cuyo resultado el
  usuario traslada con una acción explícita.
* **P-16 · Lo que define el resultado es sobre qué base se aplica cada
  porcentaje, no el orden.** Intercambiar dos peldaños que se componen da el
  mismo número, porque multiplicar es conmutativo. Por eso cada paso declara su
  base, y no una posición.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_UP, Decimal
from enum import StrEnum

CALC_VERSION = 1
"""Se guarda en cada línea. Permite reproducir un informe antiguo aunque la
fórmula haya evolucionado."""

_ROUNDING = {
    "HALF_UP": ROUND_HALF_UP,
    "HALF_EVEN": ROUND_HALF_EVEN,
    "UP": ROUND_UP,
    "DOWN": ROUND_DOWN,
}


class StepKey(StrEnum):
    """Los peldaños de la cascada. `direct` no es un paso: es el punto de partida."""

    DIRECT = "direct"
    INDIRECT = "indirect"
    OVERHEAD = "overhead"
    PROFIT = "profit"
    FEES = "fees"
    CONTINGENCY = "contingency"


@dataclass(frozen=True, slots=True)
class CascadeStep:
    """Un peldaño: un porcentaje y **sobre qué se calcula**."""

    key: StepKey
    base: tuple[StepKey, ...]
    pct: Decimal

    def __post_init__(self) -> None:
        if self.key in self.base:
            raise ValueError(f"El peldaño «{self.key}» no puede calcularse sobre sí mismo")
        if not self.base:
            raise ValueError(f"El peldaño «{self.key}» no declara base")
        if self.pct < 0:
            raise ValueError(f"El porcentaje de «{self.key}» no puede ser negativo")


@dataclass(frozen=True, slots=True)
class CascadeConfig:
    """Configuración de la cascada.

    `[REQ]` P-16 · La estructura por defecto es la convención española de
    presupuestación: los indirectos se suman al coste directo para formar el
    **PEM**; gastos generales y beneficio industrial se aplican **sobre el PEM**
    —no sobre el coste directo desnudo— para formar el **PEC**; los honorarios
    técnicos van sobre el PEC; y la contingencia, la última, sobre todo lo
    anterior.

    Los **porcentajes** no viven aquí: los fija el cliente en su perfil de
    costes. Lo que aquí se fija es **sobre qué se aplica cada uno**.
    """

    steps: tuple[CascadeStep, ...]
    rounding_mode: str = "HALF_UP"
    decimals: int = 2
    round_each_step: bool = True
    version: int = CALC_VERSION

    def __post_init__(self) -> None:
        if self.rounding_mode not in _ROUNDING:
            raise ValueError(f"Modo de redondeo desconocido: {self.rounding_mode}")
        seen: set[StepKey] = {StepKey.DIRECT}
        for step in self.steps:
            if step.key in seen:
                raise ValueError(f"Peldaño duplicado: {step.key}")
            missing = [b for b in step.base if b not in seen]
            if missing:
                # Un peldaño no puede apoyarse en otro que aún no se ha calculado.
                # Sin esta comprobación la cascada daría un resultado silenciosamente
                # distinto según el orden de declaración.
                raise ValueError(
                    f"El peldaño «{step.key}» se apoya en {missing}, que no se ha calculado todavía"
                )
            seen.add(step.key)

    @classmethod
    def spanish_default(
        cls,
        *,
        indirect_pct: Decimal,
        overhead_pct: Decimal,
        profit_pct: Decimal,
        fees_pct: Decimal,
        contingency_pct: Decimal,
        rounding_mode: str = "HALF_UP",
        decimals: int = 2,
        round_each_step: bool = True,
    ) -> CascadeConfig:
        d, i = StepKey.DIRECT, StepKey.INDIRECT
        o, p = StepKey.OVERHEAD, StepKey.PROFIT
        f = StepKey.FEES
        return cls(
            steps=(
                CascadeStep(i, (d,), indirect_pct),
                # GG y BI sobre el PEM = directo + indirectos [REQ] P-16
                CascadeStep(o, (d, i), overhead_pct),
                CascadeStep(p, (d, i), profit_pct),
                # Honorarios sobre el PEC = PEM + GG + BI
                CascadeStep(f, (d, i, o, p), fees_pct),
                # Contingencia sobre todo lo anterior
                CascadeStep(StepKey.CONTINGENCY, (d, i, o, p, f), contingency_pct),
            ),
            rounding_mode=rounding_mode,
            decimals=decimals,
            round_each_step=round_each_step,
        )


@dataclass(frozen=True, slots=True)
class CascadeLine:
    """Un peldaño ya calculado, con sus operandos a la vista.

    `[REQ]` «Los cálculos deben ser transparentes; no ocultes las fórmulas.»
    Esta estructura es lo que alimenta el bloque «Cómo se calcula» de la
    interfaz: cada línea lleva su base, su porcentaje y su resultado.
    """

    key: StepKey
    label: str
    base_keys: tuple[StepKey, ...]
    base_amount: Decimal
    pct: Decimal
    amount: Decimal


@dataclass(frozen=True, slots=True)
class CascadeResult:
    """Resultado de la calculadora de medición.

    `computed_base` es el **final de la cascada**: la base imponible calculada.
    Los impuestos NO están aquí — se aplican a nivel de línea, sobre el importe
    que el usuario haya decidido, exista o no medición.
    """

    direct_cost: Decimal
    lines: tuple[CascadeLine, ...]
    computed_base: Decimal
    calc_version: int = CALC_VERSION
    subtotals: dict[str, Decimal] = field(default_factory=dict)

    @property
    def pem(self) -> Decimal | None:
        """Presupuesto de Ejecución Material, si la cascada lo produce."""
        return self.subtotals.get("PEM")

    @property
    def pec(self) -> Decimal | None:
        """Presupuesto de Ejecución por Contrata, si la cascada lo produce."""
        return self.subtotals.get("PEC")


_LABELS = {
    StepKey.INDIRECT: "Costes indirectos",
    StepKey.OVERHEAD: "Gastos generales",
    StepKey.PROFIT: "Beneficio industrial",
    StepKey.FEES: "Honorarios técnicos",
    StepKey.CONTINGENCY: "Contingencia",
}


def _quantize(value: Decimal, cfg: CascadeConfig) -> Decimal:
    exp = Decimal(1).scaleb(-cfg.decimals)
    return value.quantize(exp, rounding=_ROUNDING[cfg.rounding_mode])


def compute_direct_cost(quantity: Decimal, unit_price: Decimal) -> Decimal:
    """Coste directo = cantidad × precio unitario.

    Se conserva con toda su precisión: el redondeo es una decisión posterior y
    explícita, no un efecto secundario de la multiplicación.
    """
    if quantity < 0:
        raise ValueError("La cantidad no puede ser negativa")
    if unit_price < 0:
        raise ValueError("El precio unitario no puede ser negativo")
    return quantity * unit_price


def run_cascade(*, quantity: Decimal, unit_price: Decimal, config: CascadeConfig) -> CascadeResult:
    """Ejecuta la cascada de medición y devuelve el desglose completo.

    Devuelve **la base imponible calculada**, no el total: los impuestos se
    aplican fuera, sobre el importe de la línea (`apply_tax`).
    """
    direct = compute_direct_cost(quantity, unit_price)
    amounts: dict[StepKey, Decimal] = {StepKey.DIRECT: direct}
    lines: list[CascadeLine] = []

    for step in config.steps:
        base_amount = sum((amounts[k] for k in step.base), start=Decimal(0))
        amount = base_amount * step.pct
        if config.round_each_step:
            amount = _quantize(amount, config)
        amounts[step.key] = amount
        lines.append(
            CascadeLine(
                key=step.key,
                label=_LABELS.get(step.key, step.key.value),
                base_keys=step.base,
                base_amount=_quantize(base_amount, config),
                pct=step.pct,
                amount=amount,
            )
        )

    computed_base = _quantize(sum(amounts.values(), start=Decimal(0)), config)

    subtotals: dict[str, Decimal] = {}
    if StepKey.INDIRECT in amounts:
        subtotals["PEM"] = _quantize(amounts[StepKey.DIRECT] + amounts[StepKey.INDIRECT], config)
    if {StepKey.OVERHEAD, StepKey.PROFIT} <= amounts.keys() and "PEM" in subtotals:
        subtotals["PEC"] = _quantize(
            subtotals["PEM"] + amounts[StepKey.OVERHEAD] + amounts[StepKey.PROFIT], config
        )

    return CascadeResult(
        direct_cost=_quantize(direct, config),
        lines=tuple(lines),
        computed_base=computed_base,
        calc_version=config.version,
        subtotals=subtotals,
    )


@dataclass(frozen=True, slots=True)
class LineTotals:
    """El importe de una línea, con sus impuestos encima."""

    amount: Decimal
    tax_pct: Decimal
    tax_amount: Decimal
    total_cost: Decimal


def apply_tax(
    amount: Decimal, tax_pct: Decimal, *, rounding_mode: str = "HALF_UP", decimals: int = 2
) -> LineTotals:
    """Aplica el impuesto sobre el importe de la línea.

    `[REQ]` P-05b · Esto ocurre **siempre**, lleve la línea desglose por medición
    o no, y **una sola vez**. Es el único porcentaje del perfil de costes que
    afecta a todas las líneas del proyecto.
    """
    if amount < 0:
        raise ValueError("El importe de la línea no puede ser negativo")
    if tax_pct < 0:
        raise ValueError("El porcentaje de impuesto no puede ser negativo")
    exp = Decimal(1).scaleb(-decimals)
    rounding = _ROUNDING[rounding_mode]
    tax_amount = (amount * tax_pct).quantize(exp, rounding=rounding)
    return LineTotals(
        amount=amount.quantize(exp, rounding=rounding),
        tax_pct=tax_pct,
        tax_amount=tax_amount,
        total_cost=amount.quantize(exp, rounding=rounding) + tax_amount,
    )

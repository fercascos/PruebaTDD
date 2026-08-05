"""Pruebas del motor de CAPEX.

La primera es la que ancla P-16: si alguien cambia la base de un peldaño sin
querer, esta prueba lo detecta antes de que llegue a un informe.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tdd.capex.engine import (
    CascadeConfig,
    CascadeStep,
    StepKey,
    apply_tax,
    run_cascade,
)

PCT = {
    "indirect_pct": Decimal("0.08"),
    "overhead_pct": Decimal("0.13"),
    "profit_pct": Decimal("0.06"),
    "fees_pct": Decimal("0.06"),
    "contingency_pct": Decimal("0.10"),
}


def _spanish() -> CascadeConfig:
    return CascadeConfig.spanish_default(**PCT)


# ─────────────────────────────────────────────────────────────────────────────
#  P-16 · La cascada acordada, anclada a un valor exacto
# ─────────────────────────────────────────────────────────────────────────────


def test_cascada_espanola_da_el_valor_acordado_con_el_cliente() -> None:
    """P-16 · 48.500 € de coste directo → 72.679,34 € de base imponible.

    Es el ejemplo trabajado de docs/11 §16.3. Si este número cambia, es que
    alguien ha tocado la estructura de la cascada, y eso es una decisión de
    negocio que no puede colarse en un `git push`.
    """
    r = run_cascade(quantity=Decimal("1"), unit_price=Decimal("48500"), config=_spanish())

    assert r.pem == Decimal("52380.00"), "PEM = directo + indirectos"
    assert r.pec == Decimal("62332.20"), "PEC = PEM × (1 + GG + BI)"
    assert r.computed_base == Decimal("72679.34")


def test_gg_y_bi_se_aplican_sobre_el_pem_no_sobre_el_coste_directo() -> None:
    """La corrección que P-16 destapó.

    Calcular GG y BI sobre el coste directo desnudo daba 71.819,77 €: un 1,2 %
    menos, unos 22.000 € en un CAPEX de 1,84 M€. Esta prueba fija la base
    correcta comprobando el importe de cada peldaño, no solo el total.
    """
    r = run_cascade(quantity=Decimal("1"), unit_price=Decimal("48500"), config=_spanish())
    por_peldano = {line.key: line for line in r.lines}

    assert por_peldano[StepKey.OVERHEAD].base_amount == Decimal("52380.00")
    assert por_peldano[StepKey.OVERHEAD].amount == Decimal("6809.40")
    assert por_peldano[StepKey.PROFIT].base_amount == Decimal("52380.00")
    assert por_peldano[StepKey.PROFIT].amount == Decimal("3142.80")
    assert por_peldano[StepKey.FEES].base_amount == Decimal("62332.20")
    assert por_peldano[StepKey.CONTINGENCY].base_amount == Decimal("66072.13")


def test_el_orden_entre_peldanos_que_se_componen_no_cambia_el_resultado() -> None:
    """Multiplicar es conmutativo: por eso P-16 va de bases, no de orden."""
    d, i = StepKey.DIRECT, StepKey.INDIRECT
    f, c = StepKey.FEES, StepKey.CONTINGENCY

    honorarios_primero = CascadeConfig(
        steps=(
            CascadeStep(i, (d,), Decimal("0.08")),
            CascadeStep(f, (d, i), Decimal("0.06")),
            CascadeStep(c, (d, i, f), Decimal("0.10")),
        )
    )
    contingencia_primero = CascadeConfig(
        steps=(
            CascadeStep(i, (d,), Decimal("0.08")),
            CascadeStep(c, (d, i), Decimal("0.10")),
            CascadeStep(f, (d, i, c), Decimal("0.06")),
        )
    )
    a = run_cascade(quantity=Decimal("1"), unit_price=Decimal("48500"), config=honorarios_primero)
    b = run_cascade(quantity=Decimal("1"), unit_price=Decimal("48500"), config=contingencia_primero)

    assert a.computed_base == b.computed_base == Decimal("61075.08")


def test_la_transparencia_de_la_formula_es_verificable() -> None:
    """[REQ] Cada peldaño expone base, porcentaje e importe, y cuadran entre sí."""
    r = run_cascade(quantity=Decimal("3"), unit_price=Decimal("1250.50"), config=_spanish())

    for line in r.lines:
        esperado = (line.base_amount * line.pct).quantize(Decimal("0.01"))
        assert line.amount == esperado, f"El peldaño «{line.label}» no cuadra con sus operandos"

    suma = r.direct_cost + sum(line.amount for line in r.lines)
    assert r.computed_base == suma, "La base imponible debe ser la suma de todos los peldaños"


# ─────────────────────────────────────────────────────────────────────────────
#  P-05b · El impuesto va fuera de la cascada, sobre el importe de la línea
# ─────────────────────────────────────────────────────────────────────────────


def test_el_impuesto_se_aplica_sobre_el_importe_de_la_linea() -> None:
    t = apply_tax(Decimal("72679.34"), Decimal("0.21"))
    assert t.tax_amount == Decimal("15262.66")
    assert t.total_cost == Decimal("87942.00")


def test_el_impuesto_no_es_un_peldano_de_la_cascada() -> None:
    """P-05b · La cascada termina en la base imponible. Nada de impuestos dentro."""
    r = run_cascade(quantity=Decimal("1"), unit_price=Decimal("48500"), config=_spanish())
    assert all(line.key != "tax" for line in r.lines)
    assert r.computed_base == Decimal("72679.34")  # sin IVA


def test_una_linea_sin_medicion_tambien_lleva_impuesto() -> None:
    """El caso normal tras P-06: importe tecleado a mano, sin cascada ninguna."""
    t = apply_tax(Decimal("48500.00"), Decimal("0.21"))
    assert t.total_cost == Decimal("58685.00")


# ─────────────────────────────────────────────────────────────────────────────
#  Dinero: Decimal exacto, nunca coma flotante
# ─────────────────────────────────────────────────────────────────────────────


def test_no_hay_error_de_coma_flotante() -> None:
    """0,1 + 0,2 debe dar 0,30 exacto. Con float daría 0,30000000000000004."""
    t = apply_tax(Decimal("0.10") + Decimal("0.20"), Decimal("0"))
    assert t.amount == Decimal("0.30")


def test_la_suma_de_lineas_cuadra_con_el_total_al_centimo() -> None:
    """La garantía verificable de docs/11: agregar no puede introducir desvíos."""
    importes = [Decimal("48500.00"), Decimal("22855.33"), Decimal("144780.67"), Decimal("0.01")]
    totales = [apply_tax(i, Decimal("0.21")) for i in importes]

    suma_bases = sum(t.amount for t in totales)
    suma_impuestos = sum(t.tax_amount for t in totales)
    suma_totales = sum(t.total_cost for t in totales)

    assert suma_bases == Decimal("216136.01")
    assert suma_bases + suma_impuestos == suma_totales


@pytest.mark.parametrize(
    ("modo", "esperado"),
    [("HALF_UP", Decimal("0.13")), ("DOWN", Decimal("0.12")), ("UP", Decimal("0.13"))],
)
def test_el_modo_de_redondeo_es_una_decision_explicita(modo: str, esperado: Decimal) -> None:
    t = apply_tax(Decimal("0.125"), Decimal("1.00"), rounding_mode=modo)
    assert t.tax_amount == esperado


# ─────────────────────────────────────────────────────────────────────────────
#  Configuración: qué se acepta y qué no
# ─────────────────────────────────────────────────────────────────────────────


def test_un_peldano_no_puede_apoyarse_en_otro_no_calculado_todavia() -> None:
    """Sin esta guarda, la cascada daría un número distinto según el orden de
    declaración, y en silencio."""
    with pytest.raises(ValueError, match="no se ha calculado todavía"):
        CascadeConfig(
            steps=(
                CascadeStep(StepKey.FEES, (StepKey.CONTINGENCY,), Decimal("0.06")),
                CascadeStep(StepKey.CONTINGENCY, (StepKey.DIRECT,), Decimal("0.10")),
            )
        )


def test_un_peldano_no_puede_calcularse_sobre_si_mismo() -> None:
    with pytest.raises(ValueError, match="sobre sí mismo"):
        CascadeStep(StepKey.FEES, (StepKey.FEES,), Decimal("0.06"))


def test_no_se_admiten_porcentajes_ni_importes_negativos() -> None:
    with pytest.raises(ValueError, match="no puede ser negativo"):
        CascadeStep(StepKey.FEES, (StepKey.DIRECT,), Decimal("-0.06"))
    with pytest.raises(ValueError, match="cantidad no puede ser negativa"):
        run_cascade(quantity=Decimal("-1"), unit_price=Decimal("100"), config=_spanish())


def test_la_cascada_es_configurable_sin_tocar_codigo() -> None:
    """Cambiar los porcentajes es editar el perfil de costes, no desplegar."""
    otra = CascadeConfig.spanish_default(
        indirect_pct=Decimal("0.05"),
        overhead_pct=Decimal("0.10"),
        profit_pct=Decimal("0.06"),
        fees_pct=Decimal("0.04"),
        contingency_pct=Decimal("0.05"),
    )
    r = run_cascade(quantity=Decimal("1"), unit_price=Decimal("48500"), config=otra)
    assert r.pem == Decimal("50925.00")
    assert r.computed_base != Decimal("72679.34")


def test_el_motor_es_puro_y_reproducible() -> None:
    """Mismos datos, mismo resultado. Sin reloj, sin red, sin base de datos."""
    a = run_cascade(quantity=Decimal("7"), unit_price=Decimal("333.33"), config=_spanish())
    b = run_cascade(quantity=Decimal("7"), unit_price=Decimal("333.33"), config=_spanish())
    assert a == b

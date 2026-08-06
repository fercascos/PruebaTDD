"""Vida residual del inventario de equipo `[REQ]` §7 / P-15.

Lo que se comprueba aquí no es que reste bien: es que la vida residual **no
caduque** y que el plazo de reposición salga del catálogo del sistema y no de
unos umbrales inventados en este módulo.
"""

from __future__ import annotations

from tdd.equipment.service import (
    SIN_DATOS,
    Horizonte,
    calcular_vida,
    horizonte_de_reposicion,
    vida_residual,
)

#: Los plazos tal como se siembran desde §3.3.4. `MEJORAS` y `OTRO` no están:
#: no tienen rango de años y no son plazos temporales.
PLAZOS = [
    Horizonte(code="CORTO", name_es="Corto plazo", year_from=1, year_to=2),
    Horizonte(code="MEDIO", name_es="Medio plazo", year_from=3, year_to=5),
    Horizonte(code="LARGO", name_es="Largo plazo", year_from=6, year_to=10),
]


def test_la_vida_residual_sale_del_ano_en_curso() -> None:
    assert vida_residual(2030, anio_actual=2026) == 4


def test_el_mismo_equipo_da_un_ano_menos_al_ano_siguiente() -> None:
    """Es la razón por la que esto no es una columna generada.

    Una columna `remaining_life_years` calculada al escribir valdría el día que
    se guarda y mentiría a partir del 1 de enero siguiente. PostgreSQL además
    no la admitiría: exige que la expresión sea IMMUTABLE, y el año en curso no
    lo es.
    """
    assert vida_residual(2030, anio_actual=2026) == 4
    assert vida_residual(2030, anio_actual=2027) == 3


def test_un_equipo_vencido_da_un_numero_negativo_y_no_cero() -> None:
    """Recortar a cero escondería la diferencia entre «vencido el año pasado» y
    «vencido hace una década», que es justo la que decide la urgencia."""
    assert vida_residual(2020, anio_actual=2026) == -6


def test_sin_datos_no_se_inventa_una_vida_residual() -> None:
    assert vida_residual(None, anio_actual=2026) is None


# ─────────────────────────────────────────────────────────────────────────────
#  El plazo sale del catálogo, no de este módulo
# ─────────────────────────────────────────────────────────────────────────────


def test_cuatro_anos_caen_en_el_plazo_medio_del_catalogo() -> None:
    """3-5 años es `MEDIO` porque lo fijó el cliente en §3.3.4, no porque lo
    decida este módulo."""
    assert horizonte_de_reposicion(4, PLAZOS).code == "MEDIO"


def test_dos_anos_caen_en_corto_y_seis_en_largo() -> None:
    assert horizonte_de_reposicion(2, PLAZOS).code == "CORTO"
    assert horizonte_de_reposicion(6, PLAZOS).code == "LARGO"


def test_un_equipo_ya_vencido_cae_en_el_plazo_mas_inmediato() -> None:
    """Su reposición no está «en el pasado»: está pendiente, y es lo más urgente
    que hay en la lista."""
    assert horizonte_de_reposicion(-6, PLAZOS).code == "CORTO"
    assert horizonte_de_reposicion(0, PLAZOS).code == "CORTO"


def test_mas_alla_del_ultimo_plazo_no_se_empuja_al_largo() -> None:
    """Un equipo con veinte años por delante cae fuera de la ventana de estudio.
    Colocarlo en «largo plazo» diría que hay que reponerlo en diez años."""
    assert horizonte_de_reposicion(20, PLAZOS) is None


def test_si_el_catalogo_cambia_el_reparto_cambia_con_el() -> None:
    """No hay ningún 2, 5 ni 10 escrito en el módulo: si mañana el cliente
    redefine el corto plazo, esto sigue funcionando sin tocar código."""
    otros = [
        Horizonte(code="YA", name_es="Inmediato", year_from=1, year_to=1),
        Horizonte(code="LUEGO", name_es="Más adelante", year_from=2, year_to=30),
    ]
    assert horizonte_de_reposicion(4, otros).code == "LUEGO"
    assert horizonte_de_reposicion(1, otros).code == "YA"


def test_sin_plazos_sembrados_no_revienta() -> None:
    assert horizonte_de_reposicion(4, []) is None


# ─────────────────────────────────────────────────────────────────────────────
#  El resumen: una frase, la misma en la API, la pantalla y el informe
# ─────────────────────────────────────────────────────────────────────────────


def test_el_resumen_de_un_equipo_vencido_dice_cuanto_hace_y_que_es_urgente() -> None:
    vida = calcular_vida(2020, PLAZOS, anio_actual=2026)
    assert vida.vencido is True
    assert "agotada hace 6 año(s)" in vida.resumen
    assert "corto plazo" in vida.resumen


def test_el_resumen_de_un_equipo_con_vida_por_delante() -> None:
    vida = calcular_vida(2030, PLAZOS, anio_actual=2026)
    assert vida.vencido is False
    assert vida.remaining_life_years == 4
    assert vida.horizonte_code == "MEDIO"
    assert "quedan 4 año(s)" in vida.resumen


def test_el_equipo_que_agota_su_vida_este_ano_no_es_vencido_pero_es_de_corto() -> None:
    vida = calcular_vida(2026, PLAZOS, anio_actual=2026)
    assert vida.vencido is False
    assert vida.remaining_life_years == 0
    assert vida.horizonte_code == "CORTO"
    assert "este año" in vida.resumen


def test_sin_datos_el_resumen_dice_que_falta_y_no_finge_un_calculo() -> None:
    vida = calcular_vida(None, PLAZOS, anio_actual=2026)
    assert vida.remaining_life_years is None
    assert vida.vencido is False
    assert vida.horizonte_code is None
    assert vida.resumen == SIN_DATOS

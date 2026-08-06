"""La matriz de riesgo × horizonte `[REQ]` §12 de `docs/09-ux-pantallas.md`.

Lógica pura sobre filas ya leídas: no hace falta base de datos. Lo que se
comprueba es lo que hace que los números signifiquen algo — que los totales
cuadren y que nada desaparezca por el camino—, porque una matriz cuyos totales
no coinciden con el CAPEX del proyecto no la usa nadie dos veces.
"""

from __future__ import annotations

from decimal import Decimal

from tdd.findings.riesgos import SIN_GRADO, FilaDeHallazgo, construir

CATALOGO = [("01", "Bajo", 1), ("02", "Moderado", 2), ("03", "Alto", 3), ("04", "Extremo", 4)]
HORIZONTES = ["CORTO", "MEDIO", "LARGO", "MEJORAS", "OTRO"]


def fila(
    finding_id: str,
    riesgo: str | None = "03",
    horizonte: str | None = "CORTO",
    importe: str = "1000",
    capitulo: str | None = "HC.H08",
) -> FilaDeHallazgo:
    nombres = {c: n for c, n, _ in CATALOGO}
    puntos = {c: s for c, _, s in CATALOGO}
    return FilaDeHallazgo(
        finding_id=finding_id,
        risk_code=riesgo,
        risk_name=nombres.get(riesgo or "") if riesgo else None,
        risk_score=puntos.get(riesgo or "") if riesgo else None,
        chapter_code=capitulo,
        chapter_name="HVAC" if capitulo else None,
        horizonte=horizonte,
        importe=Decimal(importe),
    )


def matriz(filas: list[FilaDeHallazgo]):
    return construir(filas, grados_del_catalogo=CATALOGO, horizontes=HORIZONTES)


def grado(m, code: str):
    return next(g for g in m.grados if g.code == code)


# ─────────────────────────────────────────────────────────────────────────────
#  Lo que hace que los números signifiquen algo
# ─────────────────────────────────────────────────────────────────────────────


def test_los_totales_cuadran_con_la_suma_de_las_filas() -> None:
    """Si la matriz no suma lo mismo que el CAPEX del proyecto, nadie la usa dos
    veces: se pasa el resto del encargo buscando los euros que faltan."""
    m = matriz(
        [
            fila("a", "04", "CORTO", "412500"),
            fila("b", "03", "CORTO", "271700"),
            fila("c", "03", "MEDIO", "412500"),
            fila("d", "02", "LARGO", "298000"),
        ]
    )
    assert m.total_importe == Decimal("1394700")
    assert sum(m.total_por_horizonte.values()) == m.total_importe
    assert sum(g.importe for g in m.grados) == m.total_importe


def test_una_actuacion_recurrente_cuenta_una_vez_y_reparte_su_dinero() -> None:
    """`[REQ]` P-44 · Es el caso que más fácil se cuenta mal.

    Una actuación con líneas en dos plazos son **dos filas** de entrada y **un**
    hallazgo. Contar líneas inflaría el recuento justo en las actuaciones más
    caras, que son las que se miran.
    """
    m = matriz(
        [
            fila("recurrente", "03", "CORTO", "10000"),
            fila("recurrente", "03", "LARGO", "25000"),
        ]
    )
    alto = grado(m, "03")
    assert alto.hallazgos == 1, "una actuación recurrente es un hallazgo, no dos"
    assert alto.importe == Decimal("35000")
    assert alto.por_horizonte["CORTO"] == Decimal("10000")
    assert alto.por_horizonte["LARGO"] == Decimal("25000")
    assert m.total_hallazgos == 1


def test_un_hallazgo_sin_importe_cuenta_como_hallazgo() -> None:
    """En campo se anota lo que se ve antes de saber cuánto cuesta. Si no
    contara, la matriz diría que no hay nada que mirar en esa zona."""
    m = matriz([fila("sin_precio", "04", horizonte=None, importe="0")])
    extremo = grado(m, "04")
    assert extremo.hallazgos == 1
    assert extremo.importe == Decimal("0")
    assert m.total_hallazgos == 1


def test_los_hallazgos_sin_grado_salen_en_su_propia_fila() -> None:
    """Esconderlos haría que los totales no cuadraran con el CAPEX del proyecto
    y nadie sabría por qué faltan cien mil euros."""
    m = matriz([fila("a", "03", importe="1000"), fila("sin_clasificar", None, importe="5000")])
    sin = grado(m, SIN_GRADO)
    assert sin.hallazgos == 1
    assert sin.importe == Decimal("5000")
    assert m.total_importe == Decimal("6000")


def test_el_catalogo_entero_aparece_aunque_no_haya_hallazgos() -> None:
    """Una matriz a la que le faltan filas según el proyecto no se puede
    comparar con la del encargo siguiente, y el lector no sabe si es que no hay
    nada o es que la fila se ha caído."""
    m = matriz([fila("a", "03")])
    codigos = [g.code for g in m.grados]
    assert codigos[:4] == ["04", "03", "02", "01"], "de más grave a menos"
    assert grado(m, "01").hallazgos == 0
    assert grado(m, "01").importe == Decimal("0")


def test_lo_grave_va_arriba_y_lo_sin_clasificar_al_final() -> None:
    m = matriz([fila("a", None), fila("b", "01")])
    assert [g.code for g in m.grados] == ["04", "03", "02", "01", SIN_GRADO]


def test_un_grado_retirado_del_catalogo_no_hace_desaparecer_su_dinero() -> None:
    """Retirar un grado después de haber clasificado con él es posible: los
    catálogos son datos. Lo que no puede pasar es que el hallazgo se evapore."""
    fantasma = FilaDeHallazgo(
        finding_id="viejo",
        risk_code="09",
        risk_name="Grado retirado",
        risk_score=9,
        chapter_code="HC.H01",
        chapter_name="Estructura",
        horizonte="CORTO",
        importe=Decimal("7777"),
    )
    m = matriz([fantasma])
    assert m.total_importe == Decimal("7777")
    assert grado(m, "09").hallazgos == 1


# ─────────────────────────────────────────────────────────────────────────────
#  Reparto por horizonte
# ─────────────────────────────────────────────────────────────────────────────


def test_cada_horizonte_suma_lo_suyo() -> None:
    m = matriz(
        [
            fila("a", "04", "CORTO", "100"),
            fila("b", "03", "CORTO", "200"),
            fila("c", "02", "MEJORAS", "50"),
        ]
    )
    assert m.total_por_horizonte["CORTO"] == Decimal("300")
    assert m.total_por_horizonte["MEJORAS"] == Decimal("50")
    assert m.total_por_horizonte["LARGO"] == Decimal("0")


def test_los_cinco_horizontes_estan_siempre() -> None:
    """Aunque estén a cero: cinco columnas fijas es lo que permite comparar dos
    encargos de un vistazo."""
    m = matriz([fila("a", "03", "CORTO", "100")])
    salida = m.como_json(HORIZONTES)
    assert list(salida["total_por_horizonte"]) == HORIZONTES
    assert list(salida["grados"][0]["por_horizonte"]) == HORIZONTES


def test_un_hallazgo_sin_horizonte_suma_al_grado_pero_no_a_ninguna_columna() -> None:
    m = matriz([fila("a", "03", horizonte=None, importe="500")])
    assert grado(m, "03").importe == Decimal("500")
    assert sum(m.total_por_horizonte.values()) == Decimal("0")
    # Y por eso el total general no tiene por qué coincidir con el de columnas.
    assert m.total_importe == Decimal("500")


# ─────────────────────────────────────────────────────────────────────────────
#  Riesgo por capítulo
# ─────────────────────────────────────────────────────────────────────────────


def test_el_capitulo_cuenta_hallazgos_por_grado() -> None:
    m = matriz(
        [
            fila("a", "04", capitulo="HC.H08"),
            fila("b", "03", capitulo="HC.H08"),
            fila("c", "03", capitulo="HC.H08"),
            fila("d", "01", capitulo="HC.H01"),
        ]
    )
    hvac = next(c for c in m.capitulos if c.code == "HC.H08")
    assert hvac.por_grado == {"04": 1, "03": 2}


def test_una_actuacion_recurrente_no_se_cuenta_dos_veces_en_su_capitulo() -> None:
    m = matriz(
        [
            fila("recurrente", "03", "CORTO", "10", capitulo="HC.H08"),
            fila("recurrente", "03", "LARGO", "20", capitulo="HC.H08"),
        ]
    )
    hvac = next(c for c in m.capitulos if c.code == "HC.H08")
    assert hvac.por_grado == {"03": 1}
    assert hvac.importe == Decimal("30")


def test_los_capitulos_salen_por_dinero_de_mayor_a_menor() -> None:
    """El que más pesa primero: es la lista que se lee en diagonal."""
    m = matriz(
        [
            fila("a", "01", importe="100", capitulo="HC.H01"),
            fila("b", "01", importe="900", capitulo="HC.H09"),
            fila("c", "01", importe="500", capitulo="HC.H03"),
        ]
    )
    assert [c.code for c in m.capitulos] == ["HC.H09", "HC.H03", "HC.H01"]


def test_un_hallazgo_sin_capitulo_no_inventa_uno() -> None:
    m = matriz([fila("a", "03", capitulo=None, importe="400")])
    assert m.capitulos == []
    # Pero su dinero sigue en el total: no se pierde por no tener capítulo.
    assert m.total_importe == Decimal("400")


# ─────────────────────────────────────────────────────────────────────────────
#  Un proyecto vacío
# ─────────────────────────────────────────────────────────────────────────────


def test_sin_hallazgos_la_matriz_existe_y_esta_a_cero() -> None:
    """Devolver una matriz vacía en vez de nada: la pantalla enseña la
    estructura y el usuario ve que no hay datos, no que algo ha fallado."""
    m = matriz([])
    assert len(m.grados) == 5  # los cuatro del catálogo más «sin clasificar»
    assert m.total_hallazgos == 0
    assert m.total_importe == Decimal("0")
    assert all(v == Decimal("0") for v in m.total_por_horizonte.values())

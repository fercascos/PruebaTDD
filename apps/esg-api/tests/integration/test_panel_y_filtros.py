"""El panel: agregación, filtros, intensidades y lo que ve cada cual."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.db

VENTANA = {"desde": "2023-01-01", "hasta": "2023-04-01"}


@pytest.fixture(scope="module", autouse=True)
def consumos_de_2023(request) -> None:
    """Un trimestre de consumo real en las dos carteras."""
    fabrica = request.getfixturevalue("fabrica")
    datos = request.getfixturevalue("datos")
    from esg.core.db import ContextoRLS, aplicar_contexto
    from esg.identidad.permisos import permisos_de

    filas = [
        ("luz_torre", "2023-01-01", "2023-02-01", 12000, "kWh"),
        ("luz_torre", "2023-02-01", "2023-03-01", 10000, "kWh"),
        ("luz_torre", "2023-03-01", "2023-04-01", 11000, "kWh"),
        ("agua_torre", "2023-01-01", "2023-04-01", 900, "m3"),
        ("luz_nave", "2023-01-01", "2023-02-01", 20000, "kWh"),
    ]
    s = fabrica()
    try:
        s.begin()
        aplicar_contexto(
            s,
            ContextoRLS(
                organizacion_id=datos["org_a"],
                usuario_id=datos["gestor_a"],
                permisos=permisos_de("GESTOR"),
            ),
        )
        for punto, inicio, fin, cantidad, unidad in filas:
            s.execute(
                text(
                    "INSERT INTO lectura (organizacion_id, punto_id, inicio, fin, cantidad, "
                    "unidad, cantidad_normalizada, unidad_normalizada, origen) VALUES "
                    "(:o, :p, :i, :f, :c, :u, :c, :u, 'MANUAL')"
                ),
                {
                    "o": datos["org_a"],
                    "p": datos[punto],
                    "i": inicio,
                    "f": fin,
                    "c": cantidad,
                    "u": unidad,
                },
            )
        for mes in ("2023-01-01", "2023-02-01", "2023-03-01"):
            s.execute(
                text(
                    "INSERT INTO ocupacion (organizacion_id, activo_id, mes, ocupantes_medios) "
                    "VALUES (:o, :a, :m, 300) ON CONFLICT (activo_id, mes) DO NOTHING"
                ),
                {"o": datos["org_a"], "a": datos["torre"], "m": mes},
            )
        s.commit()
    finally:
        s.close()


def panel(cliente, cab, **extra):
    return cliente.get("/api/v1/indicadores/panel", params={**VENTANA, **extra}, headers=cab).json()


def total(cuerpo, vector: str) -> Decimal:
    return Decimal(next(t["medido"] for t in cuerpo["totales"] if t["vector"] == vector))


def test_el_panel_suma_los_dos_activos(cliente, cab) -> None:
    cuerpo = panel(cliente, cab("admin_a"))
    assert total(cuerpo, "ELECTRICIDAD") == Decimal("53000")
    assert total(cuerpo, "AGUA") == Decimal("900")


def test_filtrar_por_cartera(cliente, cab, datos) -> None:
    cuerpo = panel(cliente, cab("admin_a"), cartera=str(datos["cartera_a"]))
    assert total(cuerpo, "ELECTRICIDAD") == Decimal("33000")
    assert [a["codigo"] for a in cuerpo["activos"]] == ["A-001"]


def test_filtrar_por_activo_y_por_vector(cliente, cab, datos) -> None:
    cuerpo = panel(cliente, cab("admin_a"), activo=str(datos["torre"]), vector="ELECTRICIDAD")
    assert [t["vector"] for t in cuerpo["totales"]] == ["ELECTRICIDAD"]
    assert total(cuerpo, "ELECTRICIDAD") == Decimal("33000")


def test_la_serie_mensual_reparte_la_lectura_trimestral_de_agua(cliente, cab) -> None:
    """900 m³ del 1 de enero al 1 de abril: 90 días, repartidos por días."""
    cuerpo = panel(cliente, cab("admin_a"), vector="AGUA")
    serie = {p["mes"]: Decimal(p["cantidad"]) for p in cuerpo["serie"]}
    assert serie["2023-01-01"] == Decimal("310.0000")  # 31 días
    assert serie["2023-02-01"] == Decimal("280.0000")  # 28 días
    assert serie["2023-03-01"] == Decimal("310.0000")  # 31 días
    assert sum(serie.values()) == Decimal("900")


def test_intensidades_por_metro_cuadrado_y_por_ocupante(cliente, cab, datos) -> None:
    cuerpo = panel(cliente, cab("admin_a"), activo=str(datos["torre"]))
    torre = cuerpo["activos"][0]
    assert torre["superficie_m2"] == "10000.00"
    assert torre["superficie_de_referencia"] == "ALQUILABLE"
    luz = next(i for i in torre["intensidades"] if i["vector"] == "ELECTRICIDAD")
    assert Decimal(luz["por_m2"]) == Decimal("3.3000")
    assert Decimal(luz["por_ocupante"]) == Decimal("110.0000")


def test_un_activo_sin_ocupacion_no_inventa_la_intensidad_por_ocupante(cliente, cab, datos) -> None:
    cuerpo = panel(cliente, cab("admin_a"), activo=str(datos["nave"]))
    nave = cuerpo["activos"][0]
    luz = next(i for i in nave["intensidades"] if i["vector"] == "ELECTRICIDAD")
    assert luz["por_ocupante"] is None
    assert luz["por_m2"] is not None


def test_la_cobertura_dice_cuanto_falta(cliente, cab, datos) -> None:
    """La Nave solo tiene enero cargado de un trimestre entero."""
    cuerpo = panel(cliente, cab("admin_a"), activo=str(datos["nave"]))
    cobertura = cuerpo["totales"][0]["cobertura"]
    assert cobertura["dias_esperados"] == 90
    assert cobertura["dias_con_dato"] == 31
    assert Decimal(cobertura["porcentaje"]) == Decimal("34.4")


def test_sin_periodo_anterior_no_hay_variacion(cliente, cab) -> None:
    cuerpo = panel(cliente, cab("admin_a"))
    assert all(t["variacion_porcentual"] is None for t in cuerpo["totales"])


def test_un_cliente_solo_ve_los_consumos_de_su_cartera(cliente, cab) -> None:
    """La misma ruta, el mismo trimestre, otro total. Sin un `if` en el código."""
    cuerpo = panel(cliente, cab("cliente_a"))
    assert total(cuerpo, "ELECTRICIDAD") == Decimal("33000")
    assert [a["codigo"] for a in cuerpo["activos"]] == ["A-001"]


def test_un_cliente_sin_ambito_ve_un_panel_vacio(cliente, cab) -> None:
    cuerpo = panel(cliente, cab("cliente_sin_ambito_a"))
    assert cuerpo["totales"] == []
    assert cuerpo["activos"] == []


def test_la_ventana_tiene_que_tener_sentido_y_un_tope(cliente, cab) -> None:
    respuesta = cliente.get(
        "/api/v1/indicadores/panel",
        params={"desde": "2023-04-01", "hasta": "2023-01-01"},
        headers=cab("admin_a"),
    )
    assert respuesta.status_code == 422
    largo = cliente.get(
        "/api/v1/indicadores/panel",
        params={"desde": "1990-01-01", "hasta": "2023-01-01"},
        headers=cab("admin_a"),
    )
    assert largo.status_code == 422

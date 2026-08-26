"""La matriz de riesgos contra la base real `[REQ]` §12.

La agregación ya está probada aparte, sin base de datos. Aquí se comprueba lo
que solo se ve con SQL de por medio: que el `LEFT JOIN` no pierde hallazgos sin
importe, que el capítulo se deduce bien del árbol de códigos, y sobre todo **que
el total de la matriz coincide con el CAPEX del proyecto**. Si no coincidiera,
la pantalla mandaría a alguien a buscar euros que no faltan.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.db

RUTA = "/api/v1"


@pytest.fixture(scope="module")
def catalogo(motor_admin: Engine) -> dict[str, Any]:
    with motor_admin.begin() as conn:
        tipologia = conn.execute(
            text("SELECT id FROM asset_typology ORDER BY sort_order LIMIT 1")
        ).scalar_one()
        zona = conn.execute(
            text(
                "SELECT z.id FROM zone z JOIN zone_typology zt ON zt.zone_id = z.id "
                "WHERE zt.typology_id = :t ORDER BY z.sort_order LIMIT 1"
            ),
            {"t": tipologia},
        ).scalar_one()
        # Dos códigos de nivel 3 de capítulos DISTINTOS, para poder comprobar
        # el desglose por capítulo.
        codigos = conn.execute(
            text(
                "SELECT DISTINCT ON (cc.parent_id) cc.id, p.code AS capitulo, p.name_es "
                "FROM capex_code cc JOIN capex_code p ON p.id = cc.parent_id "
                "WHERE cc.level = 3 ORDER BY cc.parent_id, cc.code LIMIT 2"
            )
        ).all()
        riesgos = {
            f.code: str(f.id) for f in conn.execute(text("SELECT id, code FROM risk_level")).all()
        }
    return {
        "tipologia": str(tipologia),
        "zona": str(zona),
        "codigo_a": str(codigos[0].id),
        "capitulo_a": codigos[0].capitulo,
        "codigo_b": str(codigos[1].id),
        "capitulo_b": codigos[1].capitulo,
        "riesgos": riesgos,
    }


@pytest.fixture
def proyecto(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo con riesgos') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"RSK-{uuid.uuid4().hex[:6]}",
                },
            ).scalar_one()
        )


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any]) -> str:
    return str(
        cliente.post(
            f"{RUTA}/projects/{proyecto}/assets",
            headers=cab("consultor_a"),
            json={"name": "Edificio Norte", "typology_id": catalogo["tipologia"]},
        ).json()["id"]
    )


def crear(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    catalogo: dict[str, Any],
    activo: str,
    *,
    riesgo: str | None = "03",
    codigo: str = "codigo_a",
    lineas: list[dict[str, str]] | None = None,
    titulo: str = "Anomalía",
) -> Any:
    cuerpo: dict[str, Any] = {
        "asset_id": activo,
        "capex_code_id": catalogo[codigo],
        "zone_id": catalogo["zona"],
        "title": titulo,
        "description": "Observado en visita.",
        "capex_lines": lineas or [],
    }
    if riesgo:
        cuerpo["risk_level_id"] = catalogo["riesgos"][riesgo]
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/findings", headers=cab("consultor_a"), json=cuerpo
    )
    assert r.status_code == 201, r.text
    return r.json()


def matriz(cliente: TestClient, cab: Any, proyecto: str, **consulta: Any) -> Any:
    cadena = "&".join(f"{k}={v}" for k, v in consulta.items())
    r = cliente.get(
        f"{RUTA}/projects/{proyecto}/risk-matrix" + (f"?{cadena}" if cadena else ""),
        headers=cab("consultor_a"),
    )
    assert r.status_code == 200, r.text
    return r.json()


def grado(datos: Any, code: str) -> Any:
    return next(g for g in datos["grados"] if g["code"] == code)


# ─────────────────────────────────────────────────────────────────────────────
#  Que los números cuadren
# ─────────────────────────────────────────────────────────────────────────────


def test_el_total_de_la_matriz_es_el_capex_del_proyecto(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """La comprobación que sostiene toda la pantalla. Si no cuadra, manda a
    alguien a buscar euros que no faltan."""
    crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        riesgo="04",
        lineas=[{"time_horizon_code": "CORTO", "amount": "412500.00"}],
    )
    crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        riesgo="02",
        lineas=[{"time_horizon_code": "LARGO", "amount": "298000.00"}],
    )

    resumen = cliente.get(
        f"{RUTA}/projects/{proyecto}/capex/summary/by-horizon", headers=cab("consultor_a")
    ).json()
    capex_total = sum(Decimal(f["amount"]) for f in resumen)

    datos = matriz(cliente, cab, proyecto)
    assert Decimal(datos["total_importe"]) == capex_total == Decimal("710500.00")


def test_una_actuacion_recurrente_cuenta_una_vez_y_reparte_su_dinero(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """`[REQ]` P-44 · Con SQL de por medio, la actuación llega como dos filas."""
    crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        riesgo="03",
        lineas=[
            {"time_horizon_code": "CORTO", "amount": "10000.00"},
            {"time_horizon_code": "LARGO", "amount": "25000.00"},
        ],
    )
    datos = matriz(cliente, cab, proyecto)
    alto = grado(datos, "03")
    assert alto["hallazgos"] == 1, "una actuación recurrente es un hallazgo, no dos"
    assert Decimal(alto["por_horizonte"]["CORTO"]) == Decimal("10000.00")
    assert Decimal(alto["por_horizonte"]["LARGO"]) == Decimal("25000.00")
    assert datos["total_hallazgos"] == 1


def test_un_hallazgo_sin_importe_no_desaparece(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """El `LEFT JOIN` es lo que lo salva. Con un `JOIN` a secas, lo que se anota
    en campo antes de saber el precio no existiría para esta pantalla."""
    crear(cliente, cab, proyecto, catalogo, activo, riesgo="04", lineas=[])
    datos = matriz(cliente, cab, proyecto)
    assert grado(datos, "04")["hallazgos"] == 1
    assert Decimal(grado(datos, "04")["importe"]) == Decimal("0")
    assert datos["total_hallazgos"] == 1


def test_un_hallazgo_sin_grado_sale_en_su_fila(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        riesgo=None,
        lineas=[{"time_horizon_code": "MEDIO", "amount": "5000.00"}],
    )
    datos = matriz(cliente, cab, proyecto)
    sin = grado(datos, "SIN_GRADO")
    assert sin["hallazgos"] == 1
    assert Decimal(sin["importe"]) == Decimal("5000.00")
    assert Decimal(datos["total_importe"]) == Decimal("5000.00")


def test_lo_descartado_no_suma(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    catalogo: dict[str, Any],
    activo: str,
    motor_admin: Engine,
) -> None:
    """Decir que una actuación no se hace y seguir sumándola al riesgo del
    encargo sería contradictorio."""
    descartado = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        riesgo="04",
        lineas=[{"time_horizon_code": "CORTO", "amount": "99999.00"}],
    )
    with motor_admin.begin() as conn:
        conn.execute(
            text("UPDATE finding SET status = 'DESCARTADO' WHERE id = :i"),
            {"i": descartado["id"]},
        )
    datos = matriz(cliente, cab, proyecto)
    assert Decimal(datos["total_importe"]) == Decimal("0")
    assert datos["total_hallazgos"] == 0


def test_un_hallazgo_borrado_tampoco_suma(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    borrado = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        lineas=[{"time_horizon_code": "CORTO", "amount": "1000.00"}],
    )
    cliente.delete(
        f"{RUTA}/findings/{borrado['id']}",
        headers={**cab("consultor_a"), "If-Match": f'"{borrado["row_version"]}"'},
    )
    assert Decimal(matriz(cliente, cab, proyecto)["total_importe"]) == Decimal("0")


# ─────────────────────────────────────────────────────────────────────────────
#  Estructura estable
# ─────────────────────────────────────────────────────────────────────────────


def test_estan_los_cuatro_grados_y_los_cinco_horizontes_aunque_esten_vacios(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Una matriz que cambia de forma según el proyecto no se puede comparar con
    la del encargo siguiente."""
    datos = matriz(cliente, cab, proyecto)
    assert [g["code"] for g in datos["grados"]] == ["04", "03", "02", "01", "SIN_GRADO"]
    assert datos["horizontes"] == ["CORTO", "MEDIO", "LARGO", "MEJORAS", "OTRO"]
    assert datos["total_hallazgos"] == 0


def test_cada_grado_trae_su_puntuacion_para_no_depender_del_color(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REQ]` §12 · «El grado nunca se identifica solo por color.» El código y
    la puntuación viajan con cada fila para que la pantalla pueda escribirlos."""
    datos = matriz(cliente, cab, proyecto)
    extremo = grado(datos, "04")
    assert extremo["score"] == 4
    assert extremo["name"] == "Extremo"
    assert grado(datos, "SIN_GRADO")["score"] is None


# ─────────────────────────────────────────────────────────────────────────────
#  Capítulos y filtros
# ─────────────────────────────────────────────────────────────────────────────


def test_el_capitulo_se_deduce_del_arbol_de_codigos(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """El hallazgo guarda un código de nivel 3; el capítulo es su padre."""
    crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        riesgo="03",
        codigo="codigo_a",
        lineas=[{"time_horizon_code": "CORTO", "amount": "100.00"}],
    )
    datos = matriz(cliente, cab, proyecto)
    codigos = [c["code"] for c in datos["capitulos"]]
    assert catalogo["capitulo_a"] in codigos


def test_los_capitulos_salen_por_dinero(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        codigo="codigo_a",
        lineas=[{"time_horizon_code": "CORTO", "amount": "100.00"}],
    )
    crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        codigo="codigo_b",
        lineas=[{"time_horizon_code": "CORTO", "amount": "900.00"}],
    )
    datos = matriz(cliente, cab, proyecto)
    assert datos["capitulos"][0]["code"] == catalogo["capitulo_b"]


def test_se_filtra_por_capitulo(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        codigo="codigo_a",
        lineas=[{"time_horizon_code": "CORTO", "amount": "100.00"}],
    )
    crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        codigo="codigo_b",
        lineas=[{"time_horizon_code": "CORTO", "amount": "900.00"}],
    )
    solo_b = matriz(cliente, cab, proyecto, chapter_code=catalogo["capitulo_b"])
    assert Decimal(solo_b["total_importe"]) == Decimal("900.00")


def test_se_filtra_por_activo(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    otro = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Edificio Sur", "typology_id": catalogo["tipologia"]},
    ).json()["id"]
    crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        lineas=[{"time_horizon_code": "CORTO", "amount": "100.00"}],
    )
    crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        str(otro),
        lineas=[{"time_horizon_code": "CORTO", "amount": "900.00"}],
    )
    solo_norte = matriz(cliente, cab, proyecto, asset_id=activo)
    assert Decimal(solo_norte["total_importe"]) == Decimal("100.00")


# ─────────────────────────────────────────────────────────────────────────────
#  Aislamiento
# ─────────────────────────────────────────────────────────────────────────────


def test_otra_organizacion_no_ve_la_matriz(cliente: TestClient, cab: Any, proyecto: str) -> None:
    r = cliente.get(f"{RUTA}/projects/{proyecto}/risk-matrix", headers=cab("admin_b"))
    assert r.status_code == 404


def test_un_proyecto_inexistente_es_un_404(cliente: TestClient, cab: Any) -> None:
    r = cliente.get(f"{RUTA}/projects/{uuid.uuid4()}/risk-matrix", headers=cab("consultor_a"))
    assert r.status_code == 404

"""El comparador de precios contra la base real `[REQ]` §14.

Aquí se comprueban las garantías que **están en la base de datos**, no en el
servicio: que una fuente no puede habilitarse sin revisión documentada de sus
condiciones de uso, y que un precio no llega a `VALIDADO` sin persona, fecha,
nota y procedencia. Si algún día alguien reescribe el servicio, estas siguen.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.db

RUTA = "/api/v1"


def codigo() -> str:
    return f"F{uuid.uuid4().hex[:8].upper()}"


@pytest.fixture
def fuente_manual(cliente: TestClient, cab: Any) -> dict[str, Any]:
    r = cliente.post(
        f"{RUTA}/price-sources",
        headers=cab("admin_a"),
        json={"code": codigo(), "name": "Introducido a mano", "source_type": "MANUAL"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def referencia(
    cliente: TestClient, cab: Any, fuente: dict[str, Any], **extra: Any
) -> dict[str, Any]:
    cuerpo = {
        "price_source_id": fuente["id"],
        "description": "Sustitución de enfriadora 300 kW",
        "unit": "ud",
        "unit_price": "48500.00",
        "price_date": "2025-11-01",
        **extra,
    }
    r = cliente.post(f"{RUTA}/price-references", headers=cab("consultor_a"), json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
#  Fuentes: nada se habilita sin revisar las condiciones
# ─────────────────────────────────────────────────────────────────────────────


def test_una_fuente_nace_deshabilitada(cliente: TestClient, cab: Any) -> None:
    """`[REQ]` Que naciera habilitada convertiría un alta rutinaria en una
    autorización tácita para consultar a un tercero."""
    r = cliente.post(
        f"{RUTA}/price-sources",
        headers=cab("admin_a"),
        json={
            "code": codigo(),
            "name": "Precio Centro",
            "source_type": "BASE_PRECIOS_LICENCIADA",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_enabled"] is False
    assert r.json()["motivo_de_no_consulta"] is not None


def test_no_se_habilita_sin_declarar_que_se_han_revisado_las_condiciones(
    cliente: TestClient, cab: Any
) -> None:
    fuente = cliente.post(
        f"{RUTA}/price-sources",
        headers=cab("admin_a"),
        json={"code": codigo(), "name": "Proveedor X", "source_type": "API_OFICIAL"},
    ).json()

    r = cliente.post(
        f"{RUTA}/price-sources/{fuente['id']}/review",
        headers=cab("admin_a"),
        json={"he_revisado_las_condiciones": False, "habilitar": True},
    )
    assert r.status_code == 422
    assert "condiciones de uso" in r.json()["detail"]


def test_la_base_de_datos_lo_impide_tambien(
    cliente: TestClient, cab: Any, motor_admin: Engine, datos_base: dict[str, uuid.UUID]
) -> None:
    """`[REQ]` La garantía no depende de que una pantalla se acuerde.

    Se intenta por SQL directo, saltándose la API entera: el `CHECK`
    `fuente_exige_revision_de_condiciones` tiene que rechazarlo igual.
    """
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError), motor_admin.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO price_source (organization_id, code, name, source_type, "
                "is_enabled, tos_reviewed) "
                "VALUES (:o, :c, 'Colada por SQL', 'API_OFICIAL', TRUE, FALSE)"
            ),
            {"o": str(datos_base["org_a"]), "c": codigo()},
        )


def test_revisar_y_habilitar_deja_rastro_con_nombre_y_fecha(
    cliente: TestClient, cab: Any, motor_admin: Engine
) -> None:
    fuente = cliente.post(
        f"{RUTA}/price-sources",
        headers=cab("admin_a"),
        json={"code": codigo(), "name": "Base licenciada", "source_type": "CATALOGO_INTERNO"},
    ).json()

    r = cliente.post(
        f"{RUTA}/price-sources/{fuente['id']}/review",
        headers=cab("admin_a"),
        json={
            "he_revisado_las_condiciones": True,
            "habilitar": True,
            "tos_url": "https://ejemplo.example/condiciones",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_enabled"] is True
    assert r.json()["motivo_de_no_consulta"] is None

    with motor_admin.begin() as conn:
        revisor, cuando = conn.execute(
            text("SELECT tos_reviewed_by, tos_reviewed_at FROM price_source WHERE id = :i"),
            {"i": fuente["id"]},
        ).one()
    assert revisor is not None and cuando is not None


def test_un_consultor_no_habilita_fuentes(cliente: TestClient, cab: Any) -> None:
    r = cliente.post(
        f"{RUTA}/price-sources",
        headers=cab("consultor_a"),
        json={"code": codigo(), "name": "Intento", "source_type": "API_OFICIAL"},
    )
    assert r.status_code == 403


def test_una_licencia_caducada_vuelve_a_dejar_la_fuente_fuera(
    cliente: TestClient, cab: Any
) -> None:
    fuente = cliente.post(
        f"{RUTA}/price-sources",
        headers=cab("admin_a"),
        json={"code": codigo(), "name": "Con licencia", "source_type": "BASE_PRECIOS_LICENCIADA"},
    ).json()
    r = cliente.post(
        f"{RUTA}/price-sources/{fuente['id']}/review",
        headers=cab("admin_a"),
        json={
            "he_revisado_las_condiciones": True,
            "habilitar": True,
            "license_expires_at": str(date.today() - timedelta(days=1)),
        },
    )
    assert r.status_code == 200
    assert "caducó" in (r.json()["motivo_de_no_consulta"] or "")


# ─────────────────────────────────────────────────────────────────────────────
#  El comparador dice lo que NO ha mirado
# ─────────────────────────────────────────────────────────────────────────────


def test_el_comparador_enumera_las_fuentes_no_consultadas(
    cliente: TestClient, cab: Any, fuente_manual: dict[str, Any]
) -> None:
    """`[REQ]` §14 · Una lista de resultados sin esa columna sugiere que se ha
    buscado en todas partes."""
    cliente.post(
        f"{RUTA}/price-sources",
        headers=cab("admin_a"),
        json={
            "code": codigo(),
            "name": "Precio Centro",
            "source_type": "BASE_PRECIOS_LICENCIADA",
            "disabled_reason": "Pendiente de licencia vigente y de revisión de condiciones.",
        },
    )
    referencia(cliente, cab, fuente_manual)

    datos = cliente.get(f"{RUTA}/price-references", headers=cab("consultor_a")).json()
    motivos = [f["motivo"] for f in datos["no_consultadas"]]
    assert any("Pendiente de licencia" in m for m in motivos)
    assert "un consultor debe validar" in datos["aviso"].lower()


def test_ninguna_referencia_viene_marcada_como_elegida(
    cliente: TestClient, cab: Any, fuente_manual: dict[str, Any]
) -> None:
    referencia(cliente, cab, fuente_manual)
    datos = cliente.get(f"{RUTA}/price-references", headers=cab("consultor_a")).json()
    for r in datos["referencias"]:
        assert "recomendada" not in r
        assert "elegida" not in r


def test_las_referencias_se_buscan_por_descripcion(
    cliente: TestClient, cab: Any, fuente_manual: dict[str, Any]
) -> None:
    marca = uuid.uuid4().hex[:8]
    referencia(cliente, cab, fuente_manual, description=f"Enfriadora {marca}")
    datos = cliente.get(f"{RUTA}/price-references?q={marca}", headers=cab("consultor_a")).json()
    assert len(datos["referencias"]) == 1


def test_otra_organizacion_no_ve_las_referencias(
    cliente: TestClient, cab: Any, fuente_manual: dict[str, Any]
) -> None:
    creada = referencia(cliente, cab, fuente_manual)
    datos = cliente.get(f"{RUTA}/price-references", headers=cab("admin_b")).json()
    assert creada["id"] not in [r["id"] for r in datos["referencias"]]


# ─────────────────────────────────────────────────────────────────────────────
#  Validación: siempre con una persona detrás
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def linea(cliente: TestClient, cab: Any, motor_admin: Engine, datos_base: dict[str, uuid.UUID]):
    """Un hallazgo con una línea de CAPEX sin validar."""
    with motor_admin.begin() as conn:
        tipologia = conn.execute(text("SELECT id FROM asset_typology LIMIT 1")).scalar_one()
        zona = conn.execute(
            text(
                "SELECT z.id FROM zone z JOIN zone_typology zt ON zt.zone_id = z.id "
                "WHERE zt.typology_id = :t LIMIT 1"
            ),
            {"t": tipologia},
        ).scalar_one()
        cod = conn.execute(text("SELECT id FROM capex_code WHERE level = 3 LIMIT 1")).scalar_one()
        proyecto = conn.execute(
            text(
                "INSERT INTO project (organization_id, client_id, internal_code, name) "
                "VALUES (:o, :c, :cod, 'Encargo de precios') RETURNING id"
            ),
            {
                "o": str(datos_base["org_a"]),
                "c": str(datos_base["cliente_a"]),
                "cod": f"PRE-{uuid.uuid4().hex[:6]}",
            },
        ).scalar_one()

    activo = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave", "typology_id": str(tipologia)},
    ).json()
    hallazgo = cliente.post(
        f"{RUTA}/projects/{proyecto}/findings",
        headers=cab("consultor_a"),
        json={
            "asset_id": activo["id"],
            "capex_code_id": str(cod),
            "zone_id": str(zona),
            "title": "Enfriadora al final de su vida útil",
            "description": "Observada en visita.",
            "capex_lines": [{"time_horizon_code": "CORTO", "amount": "40000.00"}],
        },
    ).json()
    return hallazgo["capex_lines"][0]


def test_validar_con_la_referencia_tal_cual(
    cliente: TestClient, cab: Any, fuente_manual: dict[str, Any], linea: dict[str, Any]
) -> None:
    ref = referencia(cliente, cab, fuente_manual)
    r = cliente.post(
        f"{RUTA}/capex-items/{linea['id']}/validate-price",
        headers=cab("consultor_a"),
        json={"amount": "48500.00", "price_reference_id": ref["id"]},
    )
    assert r.status_code == 200, r.text
    validada = next(x for x in r.json()["capex_lines"] if x["id"] == linea["id"])
    assert validada["price_status"] == "VALIDADO"
    assert Decimal(validada["amount"]) == Decimal("48500.00")


def test_un_importe_distinto_sin_explicacion_se_rechaza(
    cliente: TestClient, cab: Any, fuente_manual: dict[str, Any], linea: dict[str, Any]
) -> None:
    ref = referencia(cliente, cab, fuente_manual)
    r = cliente.post(
        f"{RUTA}/capex-items/{linea['id']}/validate-price",
        headers=cab("consultor_a"),
        json={"amount": "52000.00", "price_reference_id": ref["id"]},
    )
    assert r.status_code == 422
    assert "48500" in r.json()["detail"]


def test_un_precio_sin_referencia_se_rechaza_diciendo_que_hacer(
    cliente: TestClient, cab: Any, linea: dict[str, Any]
) -> None:
    """`[REQ]` «Una partida con precio conserva su procedencia.» El `CHECK`
    `precio_exige_referencia` lo impide igualmente; esto lo dice antes y explica
    la salida en vez de reventar con un error de integridad."""
    r = cliente.post(
        f"{RUTA}/capex-items/{linea['id']}/validate-price",
        headers=cab("consultor_a"),
        json={"amount": "1000.00", "justificacion": "Media de tres presupuestos pedidos."},
    )
    assert r.status_code == 422
    assert "referencia" in r.json()["detail"].lower()


def test_la_validacion_queda_con_nombre_fecha_y_nota(
    cliente: TestClient,
    cab: Any,
    fuente_manual: dict[str, Any],
    linea: dict[str, Any],
    motor_admin: Engine,
) -> None:
    ref = referencia(cliente, cab, fuente_manual)
    cliente.post(
        f"{RUTA}/capex-items/{linea['id']}/validate-price",
        headers=cab("consultor_a"),
        json={
            "amount": "52000.00",
            "price_reference_id": ref["id"],
            "justificacion": "Oferta en firme del proveedor, incluye puesta en marcha.",
        },
    )
    with motor_admin.begin() as conn:
        quien, cuando, nota, procedencia = conn.execute(
            text(
                "SELECT price_validated_by, price_validated_at, price_validation_note, "
                "selected_price_reference_id FROM capex_item WHERE id = :i"
            ),
            {"i": linea["id"]},
        ).one()
    assert quien is not None
    assert cuando is not None
    assert "Oferta en firme" in nota
    assert str(procedencia) == ref["id"]


def test_la_base_de_datos_no_deja_validar_sin_nota(
    cliente: TestClient, cab: Any, linea: dict[str, Any], motor_admin: Engine
) -> None:
    """`[REQ]` La validación es SIEMPRE humana. Se intenta por SQL directo."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError), motor_admin.begin() as conn:
        conn.execute(
            text("UPDATE capex_item SET price_status = 'VALIDADO' WHERE id = :i"),
            {"i": linea["id"]},
        )


def test_validar_queda_auditado(
    cliente: TestClient,
    cab: Any,
    fuente_manual: dict[str, Any],
    linea: dict[str, Any],
    motor_admin: Engine,
) -> None:
    ref = referencia(cliente, cab, fuente_manual)
    cliente.post(
        f"{RUTA}/capex-items/{linea['id']}/validate-price",
        headers=cab("consultor_a"),
        json={"amount": "48500.00", "price_reference_id": ref["id"]},
    )
    with motor_admin.begin() as conn:
        acciones = (
            conn.execute(
                text("SELECT action FROM audit_log WHERE entity_id = :i"), {"i": linea["id"]}
            )
            .scalars()
            .all()
        )
    assert "PRICE_VALIDATED" in acciones


# ─────────────────────────────────────────────────────────────────────────────
#  Actualización por índice
# ─────────────────────────────────────────────────────────────────────────────


def test_la_actualizacion_por_indice_no_guarda_nada(cliente: TestClient, cab: Any) -> None:
    r = cliente.post(
        f"{RUTA}/prices/index-update",
        headers=cab("consultor_a"),
        json={
            "base": "48500.00",
            "indice_origen": "112.7",
            "indice_destino": "118.4",
            "factor_geografico": "1.05",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["resultado"] == "53500.62"
    assert "112.7" in r.json()["formula"]
    assert "no se ha aplicado" in r.json()["nota"].lower()


def test_un_indice_a_cero_se_rechaza(cliente: TestClient, cab: Any) -> None:
    r = cliente.post(
        f"{RUTA}/prices/index-update",
        headers=cab("consultor_a"),
        json={"base": "100", "indice_origen": "0", "indice_destino": "110"},
    )
    assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
#  Lo que la API NO ofrece
# ─────────────────────────────────────────────────────────────────────────────


def test_no_existe_ningun_endpoint_que_consulte_fuentes_externas(cliente: TestClient) -> None:
    """`[REQ]` «No inventes APIs ni fuentes de precios», y nada de scraping.

    Se mira el OpenAPI: si alguien añadiera una ruta de búsqueda remota, esta
    prueba lo diría antes de que llegara a producción.
    """
    rutas = cliente.get("/openapi.json").json()["paths"]
    sospechosas = [
        r
        for r in rutas
        if any(p in r.lower() for p in ("scrape", "fetch-prices", "price-search", "lookup"))
    ]
    assert sospechosas == [], f"rutas que sugieren consulta externa: {sospechosas}"

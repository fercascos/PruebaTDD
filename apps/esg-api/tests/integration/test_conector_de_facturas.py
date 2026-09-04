"""El conector con el lector de facturas de Azure, sin salir a la red."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from esg.conector.memoria import LectorEnMemoria
from esg.conector.puerto import FacturaLeida, LectorNoConfigurado
from tests.conftest import montar_app

pytestmark = pytest.mark.db

VENTANA = {"desde": "2024-01-01", "hasta": "2024-04-01"}


def factura(
    referencia: str,
    inicio: str,
    fin: str,
    kwh: str,
    confianza: float = 0.99,
    suministro: str = "ES0031000000001",
):
    return FacturaLeida(
        referencia=referencia,
        suministro=suministro,
        vector="ELECTRICIDAD",
        inicio=date.fromisoformat(inicio),
        fin=date.fromisoformat(fin),
        cantidad=Decimal(kwh),
        unidad="kWh",
        confianza=confianza,
        confianza_por_campo={"cantidad": confianza, "periodo": 0.99},
        importe=Decimal("1450.20"),
        moneda="EUR",
        documento_url="https://ejemplo.invalid/factura.pdf",
    )


def con_lector(motor_app, fabrica, facturas, **kwargs):
    return TestClient(montar_app(motor_app, fabrica, LectorEnMemoria(facturas, **kwargs)))


def test_importar_facturas_confiables_las_confirma(motor_app, fabrica, cab) -> None:
    with con_lector(
        motor_app,
        fabrica,
        [
            factura("F-2024-001", "2024-01-01", "2024-02-01", "12000"),
            factura("F-2024-002", "2024-02-01", "2024-03-01", "10000"),
        ],
    ) as c:
        respuesta = c.post("/api/v1/conector/importar", params=VENTANA, headers=cab("analista_a"))
        assert respuesta.status_code == 200
        cuerpo = respuesta.json()
        assert cuerpo["facturas_leidas"] == 2
        assert cuerpo["confirmadas"] == 2
        assert cuerpo["pendientes_de_revision"] == 0

        panel = c.get(
            "/api/v1/indicadores/panel",
            params={**VENTANA, "vector": "ELECTRICIDAD"},
            headers=cab("analista_a"),
        ).json()
        assert Decimal(panel["totales"][0]["medido"]) == Decimal("22000")


def test_una_factura_dudosa_espera_a_que_alguien_la_mire(motor_app, fabrica, cab) -> None:
    """La IA acierta mucho. «Mucho» no es «siempre», y una factura mal leída no
    se distingue de una buena una vez está dentro de la suma."""
    with con_lector(
        motor_app,
        fabrica,
        [factura("F-2024-003", "2024-03-01", "2024-04-01", "99000", confianza=0.42)],
    ) as c:
        cuerpo = c.post(
            "/api/v1/conector/importar", params=VENTANA, headers=cab("analista_a")
        ).json()
        assert cuerpo["pendientes_de_revision"] == 1
        assert cuerpo["confirmadas"] == 0

        # No suma: el total sigue siendo el de las dos facturas confirmadas.
        panel = c.get(
            "/api/v1/indicadores/panel",
            params={**VENTANA, "vector": "ELECTRICIDAD"},
            headers=cab("analista_a"),
        ).json()
        assert Decimal(panel["totales"][0]["medido"]) == Decimal("22000")

        pendientes = c.get("/api/v1/lecturas/pendientes", headers=cab("analista_a")).json()
        assert len(pendientes) == 1
        assert pendientes[0]["confianza"] == "0.420"
        assert "documento" in pendientes[0]["nota"]

        # Alguien la mira y la confirma: ahora sí suma.
        resolver = c.post(
            f"/api/v1/lecturas/{pendientes[0]['id']}/resolver",
            json={"estado": "CONFIRMADA"},
            headers=cab("analista_a"),
        )
        assert resolver.status_code == 204
        panel = c.get(
            "/api/v1/indicadores/panel",
            params={**VENTANA, "vector": "ELECTRICIDAD"},
            headers=cab("analista_a"),
        ).json()
        assert Decimal(panel["totales"][0]["medido"]) == Decimal("121000")


def test_la_misma_factura_no_entra_dos_veces(motor_app, fabrica, cab) -> None:
    with con_lector(
        motor_app, fabrica, [factura("F-2024-001", "2024-01-01", "2024-02-01", "12000")]
    ) as c:
        cuerpo = c.post(
            "/api/v1/conector/importar", params=VENTANA, headers=cab("analista_a")
        ).json()
        assert cuerpo["rechazadas"] == 1
        assert cuerpo["incidencias"][0]["codigo"] == "factura_rechazada"


def test_una_factura_de_un_suministro_que_no_existe_se_avisa(motor_app, fabrica, cab) -> None:
    fuera = FacturaLeida(
        referencia="F-2024-999",
        suministro="ES-QUE-NO-EXISTE",
        vector="ELECTRICIDAD",
        inicio=date(2024, 1, 1),
        fin=date(2024, 2, 1),
        cantidad=Decimal("100"),
        unidad="kWh",
    )
    with con_lector(motor_app, fabrica, [fuera]) as c:
        cuerpo = c.post(
            "/api/v1/conector/importar", params=VENTANA, headers=cab("analista_a")
        ).json()
        assert cuerpo["rechazadas"] == 1
        assert cuerpo["incidencias"][0]["codigo"] == "suministro_desconocido"


def test_se_recorren_todas_las_paginas(motor_app, fabrica, cab) -> None:
    # Contra el suministro de la Nave, que no tiene nada cargado en 2024: si
    # fueran del mismo contador que las facturas de arriba, las rechazaría el
    # solape y esta prueba diría «no hay paginación» por el motivo equivocado.
    facturas = [
        factura(
            f"F-2024-1{n:02d}",
            f"2024-01-{n:02d}",
            f"2024-01-{n + 1:02d}",
            "10",
            suministro="ES0031000000002",
        )
        for n in range(10, 20)
    ]
    with con_lector(motor_app, fabrica, facturas, pagina=3) as c:
        cuerpo = c.post(
            "/api/v1/conector/importar", params=VENTANA, headers=cab("analista_a")
        ).json()
        assert cuerpo["facturas_leidas"] == 10
        assert cuerpo["confirmadas"] == 10


def test_sin_conector_configurado_se_dice_que_falta_configurarlo(motor_app, fabrica, cab) -> None:
    """503 y no 500: no está roto, es que esta instalación no tiene lector."""
    app = montar_app(motor_app, fabrica)
    app.state.lector_de_facturas = LectorNoConfigurado()
    with TestClient(app) as c:
        respuesta = c.post("/api/v1/conector/importar", params=VENTANA, headers=cab("analista_a"))
        assert respuesta.status_code == 503
        assert "LECTOR_FACTURAS_URL" in respuesta.json()["detail"]


def test_un_lector_no_puede_lanzar_la_importacion(motor_app, fabrica, cab) -> None:
    with con_lector(motor_app, fabrica, []) as c:
        assert (
            c.post("/api/v1/conector/importar", params=VENTANA, headers=cab("lector_a")).status_code
            == 403
        )

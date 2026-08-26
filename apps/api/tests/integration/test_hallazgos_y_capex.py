"""Hallazgos y CAPEX punta a punta.

La prueba central de este fichero es la de P-44: un hallazgo con **dos líneas
en dos plazos** —una actuación recurrente— frente a dos líneas en el **mismo**
plazo, que sí es un duplicado y la base de datos rechaza.
"""

from __future__ import annotations

import io
import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.unit.test_imagenes import imagen

pytestmark = pytest.mark.db

RUTA = "/api/v1"


@pytest.fixture(scope="module")
def catalogo(motor_admin: Engine) -> dict[str, Any]:
    """Identificadores del catálogo que hacen falta para crear un hallazgo."""
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
        zona_ajena = conn.execute(
            text(
                "SELECT z.id FROM zone z WHERE NOT EXISTS ("
                "  SELECT 1 FROM zone_typology zt WHERE zt.zone_id = z.id AND zt.typology_id = :t)"
                " LIMIT 1"
            ),
            {"t": tipologia},
        ).scalar()
        codigo = conn.execute(
            text("SELECT id FROM capex_code WHERE level = 3 ORDER BY code LIMIT 1")
        ).scalar_one()
        codigo_padre = conn.execute(
            text("SELECT parent_id FROM capex_code WHERE id = :i"), {"i": codigo}
        ).scalar_one()
        riesgo = conn.execute(text("SELECT id FROM risk_level ORDER BY score LIMIT 1")).scalar_one()
    return {
        "tipologia": str(tipologia),
        "zona": str(zona),
        "zona_ajena": str(zona_ajena) if zona_ajena else None,
        "codigo": str(codigo),
        "codigo_padre": str(codigo_padre),
        "riesgo": str(riesgo),
    }


@pytest.fixture
def proyecto(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    """Un proyecto por prueba: los totales se comprueban sumando todo lo que
    hay dentro, y compartirlo haría depender el resultado del orden."""
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo de hallazgos') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"HAL-{uuid.uuid4().hex[:6]}",
                },
            ).scalar_one()
        )


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any]) -> str:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave A", "typology_id": catalogo["tipologia"]},
    )
    return str(r.json()["id"])


def con_version(cabeceras: dict[str, str], fila: dict[str, Any]) -> dict[str, str]:
    """Las cabeceras de sesión más el `If-Match` que exigen hallazgos y líneas.

    `[REQ]` La API rechaza con `428` una escritura que no diga sobre qué versión
    escribe. Que estas pruebas tengan que pasar por aquí **es la comprobación**:
    si alguien quitara la exigencia, seguirían pasando y no habría forma de
    notarlo, así que `test_concurrencia` cubre además el caso sin cabecera.
    """
    return {**cabeceras, "If-Match": f'"{fila["row_version"]}"'}


def crear(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    catalogo: dict[str, Any],
    activo: str,
    **campos: Any,
) -> Any:
    cuerpo = {
        "asset_id": activo,
        "capex_code_id": catalogo["codigo"],
        "zone_id": catalogo["zona"],
        "title": "Fisuras en la solera del aparcamiento",
        "description": "Fisuras de retracción de anchura inferior a 1 mm, sin asientos.",
        **campos,
    }
    return cliente.post(
        f"{RUTA}/projects/{proyecto}/findings", headers=cab("consultor_a"), json=cuerpo
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Alta conjunta
# ─────────────────────────────────────────────────────────────────────────────


def test_el_alta_crea_hallazgo_y_linea_en_una_sola_operacion(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """`[REC]` En la tabla real del cliente son la misma fila. Partirlo en dos
    pantallas multiplicaría por dos los pasos de la operación que más se repite
    en todo el proyecto."""
    r = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        capex_lines=[{"time_horizon_code": "CORTO", "amount": "5500.00"}],
    )
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["status"] == "BORRADOR"
    assert len(cuerpo["capex_lines"]) == 1
    assert cuerpo["total_amount"] == "5500.0000"


def test_un_hallazgo_sin_importe_es_valido(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """En campo se anota lo que se ve antes de saber cuánto cuesta. Exigir el
    importe en el alta obligaría a inventarlo."""
    r = crear(cliente, cab, proyecto, catalogo, activo)
    assert r.status_code == 201
    assert r.json()["capex_lines"] == []


def test_la_zona_debe_corresponder_a_la_tipologia_del_activo(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """`[REQ]` Se comprueba en el servidor y no solo en el desplegable: un
    cliente de API o un formulario cacheado no pasan por la interfaz."""
    if catalogo["zona_ajena"] is None:
        pytest.skip("la tipología admite todas las zonas del catálogo")
    r = crear(cliente, cab, proyecto, catalogo, activo, zone_id=catalogo["zona_ajena"])
    assert r.status_code == 422
    assert "tipología" in r.json()["detail"]


def test_un_campo_desconocido_se_rechaza(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    r = crear(cliente, cab, proyecto, catalogo, activo, importe=5000)
    assert r.status_code == 422


def test_un_horizonte_inexistente_se_rechaza_con_su_nombre(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    r = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        capex_lines=[{"time_horizon_code": "MAÑANA", "amount": "10.00"}],
    )
    assert r.status_code == 422
    assert "MAÑANA" in r.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
#  P-44 · Actuaciones recurrentes
# ─────────────────────────────────────────────────────────────────────────────


def test_una_actuacion_recurrente_tiene_una_linea_por_plazo(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """`[REQ]` P-44 · La limpieza de lucernarios hace falta ahora **y** otra vez
    dentro de diez años. Así aparece en la tabla real del cliente."""
    r = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        title="Limpieza de lucernarios",
        capex_lines=[
            {"time_horizon_code": "CORTO", "amount": "2300.00"},
            {"time_horizon_code": "LARGO", "amount": "2300.00"},
        ],
    )
    assert r.status_code == 201, r.text
    plazos = {line["time_horizon_code"] for line in r.json()["capex_lines"]}
    assert plazos == {"CORTO", "LARGO"}
    assert r.json()["total_amount"] == "4600.0000"


def test_dos_lineas_en_el_mismo_plazo_si_son_un_duplicado(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """P-05 sigue intacta: una LÍNEA tiene un horizonte y un importe. Lo que
    puede tener varias líneas es la ACTUACIÓN."""
    hallazgo = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        capex_lines=[{"time_horizon_code": "CORTO", "amount": "2300.00"}],
    ).json()

    r = cliente.post(
        f"{RUTA}/findings/{hallazgo['id']}/capex-items",
        headers=cab("consultor_a"),
        json={"time_horizon_code": "CORTO", "amount": "500.00"},
    )
    assert r.status_code == 409
    assert "recurrente" in r.json()["detail"]


def test_se_anade_una_linea_en_otro_plazo_despues(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    hallazgo = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        capex_lines=[{"time_horizon_code": "CORTO", "amount": "2300.00"}],
    ).json()
    r = cliente.post(
        f"{RUTA}/findings/{hallazgo['id']}/capex-items",
        headers=cab("consultor_a"),
        json={"time_horizon_code": "MEDIO", "amount": "1700.00"},
    )
    assert r.status_code == 201
    assert r.json()["total_amount"] == "4000.0000"


# ─────────────────────────────────────────────────────────────────────────────
#  Totales recalculados
# ─────────────────────────────────────────────────────────────────────────────


def test_cambiar_una_linea_devuelve_los_totales_recalculados(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """`[REQ]` Devolver solo la línea obligaría a la interfaz a recalcular por
    su cuenta, y ese cálculo duplicado es donde aparecen los descuadres entre
    la pantalla y el informe."""
    hallazgo = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        capex_lines=[{"time_horizon_code": "CORTO", "amount": "1000.00", "tax_pct": "0.21"}],
    ).json()
    linea = hallazgo["capex_lines"][0]

    r = cliente.patch(
        f"{RUTA}/capex-items/{linea['id']}",
        headers=con_version(cab("consultor_a"), linea),
        json={"amount": "2000.00"},
    )
    assert r.status_code == 200
    assert r.json()["total_amount"] == "2000.0000"
    assert r.json()["total_with_tax"] == "2420.0000"


def test_el_impuesto_lo_calcula_la_base_de_datos(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """Columnas generadas: no hay ninguna ruta de código que pueda dejar un
    `total_cost` que no cuadre con su importe."""
    hallazgo = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        capex_lines=[{"time_horizon_code": "CORTO", "amount": "1000.00", "tax_pct": "0.21"}],
    ).json()
    linea = hallazgo["capex_lines"][0]
    assert linea["tax_amount"] == "210.0000"
    assert linea["total_cost"] == "1210.0000"


def test_la_medicion_recalcula_su_base(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """`computed_base` no se teclea: si se dejara a mano, una línea podría
    enseñar un desglose que no cuadra con su propia medición."""
    hallazgo = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        capex_lines=[
            {
                "time_horizon_code": "CORTO",
                "amount": "0",
                "measurement_unit": "m2",
                "measurement_quantity": "250.00",
                "measurement_unit_price": "22.00",
            }
        ],
    ).json()
    assert hallazgo["capex_lines"][0]["computed_base"] == "5500.0000"

    r = cliente.patch(
        f"{RUTA}/capex-items/{hallazgo['capex_lines'][0]['id']}",
        headers=con_version(cab("consultor_a"), hallazgo["capex_lines"][0]),
        json={"measurement_quantity": "300.00"},
    )
    assert r.json()["capex_lines"][0]["computed_base"] == "6600.0000"


# ─────────────────────────────────────────────────────────────────────────────
#  `[REQ]` P-05b · El traslado de la medición es una acción EXPLÍCITA
#
#  La cascada nunca sustituye sola un importe tecleado: quien lo escribió puede
#  tener un presupuesto real delante, y la fórmula no sabe nada de eso.
# ─────────────────────────────────────────────────────────────────────────────


def _con_medicion(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    catalogo: dict[str, Any],
    activo: str,
    **extra: Any,
) -> Any:
    return crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        capex_lines=[
            {
                "time_horizon_code": "CORTO",
                "amount": "9999.00",
                "measurement_unit": "m2",
                "measurement_quantity": "250.00",
                "measurement_unit_price": "22.00",
                **extra,
            }
        ],
    ).json()


def test_trasladar_la_medicion_sin_confirmar_se_rechaza(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """Sin la confirmación no hay traslado. Es lo que impide que un cliente de
    la API lo dispare por descuido y pise un importe que alguien negoció."""
    hallazgo = _con_medicion(cliente, cab, proyecto, catalogo, activo)
    linea = hallazgo["capex_lines"][0]

    r = cliente.post(
        f"{RUTA}/capex-items/{linea['id']}/carry-measurement",
        headers=cab("consultor_a"),
        json={"confirmar": False},
    )
    assert r.status_code == 422
    assert "confirmaci" in r.json()["detail"].lower()

    # Y el importe sigue siendo el tecleado, no la base calculada.
    sigue = cliente.get(f"{RUTA}/findings/{hallazgo['id']}", headers=cab("consultor_a")).json()
    assert Decimal(sigue["capex_lines"][0]["amount"]) == Decimal("9999.00")


def test_trasladar_la_medicion_confirmada_sustituye_el_importe(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    hallazgo = _con_medicion(cliente, cab, proyecto, catalogo, activo)
    linea = hallazgo["capex_lines"][0]

    r = cliente.post(
        f"{RUTA}/capex-items/{linea['id']}/carry-measurement",
        headers=cab("consultor_a"),
        json={"confirmar": True},
    )
    assert r.status_code == 200, r.text
    nueva = next(x for x in r.json()["capex_lines"] if x["id"] == linea["id"])
    assert Decimal(nueva["amount"]) == Decimal("5500.00")
    # Queda dicho de dónde salió el número: no es lo mismo un importe tecleado
    # que uno que viene de una medición.
    assert nueva["amount_source"] == "MEDICION"


def test_el_traslado_devuelve_el_hallazgo_con_los_totales_al_dia(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """`[REQ]` Cualquier cambio sobre una línea devuelve **el hallazgo**.

    Devolvía solo la línea, y era una incoherencia con la regla que el propio
    módulo declara: la interfaz habría tenido que rehacer la suma por su cuenta
    justo después de que el servidor cambiara un importe, y ese cálculo
    duplicado es donde aparecen los descuadres entre lo que se ve y lo que se
    entrega.
    """
    hallazgo = _con_medicion(cliente, cab, proyecto, catalogo, activo)
    linea = hallazgo["capex_lines"][0]
    assert Decimal(hallazgo["total_amount"]) == Decimal("9999.00")

    devuelto = cliente.post(
        f"{RUTA}/capex-items/{linea['id']}/carry-measurement",
        headers=cab("consultor_a"),
        json={"confirmar": True},
    ).json()

    assert "capex_lines" in devuelto, "debe devolver el hallazgo, no la línea suelta"
    assert Decimal(devuelto["total_amount"]) == Decimal("5500.00")


def test_sin_desglose_no_hay_nada_que_trasladar(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """Un 409 que lo explica, no un traslado silencioso de `NULL` a cero: poner
    a cero un importe por error es una afirmación de que la actuación no cuesta
    nada."""
    hallazgo = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        capex_lines=[{"time_horizon_code": "CORTO", "amount": "1200.00"}],
    ).json()

    r = cliente.post(
        f"{RUTA}/capex-items/{hallazgo['capex_lines'][0]['id']}/carry-measurement",
        headers=cab("consultor_a"),
        json={"confirmar": True},
    )
    assert r.status_code == 409
    assert "medición" in r.json()["detail"]


def test_otra_organizacion_no_traslada_una_medicion_ajena(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    hallazgo = _con_medicion(cliente, cab, proyecto, catalogo, activo)
    r = cliente.post(
        f"{RUTA}/capex-items/{hallazgo['capex_lines'][0]['id']}/carry-measurement",
        headers=cab("admin_b"),
        json={"confirmar": True},
    )
    assert r.status_code == 404


def test_borrar_una_linea_devuelve_el_hallazgo_sin_ella(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    hallazgo = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        capex_lines=[
            {"time_horizon_code": "CORTO", "amount": "100.00"},
            {"time_horizon_code": "MEDIO", "amount": "200.00"},
        ],
    ).json()
    a_borrar = hallazgo["capex_lines"][0]
    r = cliente.delete(
        f"{RUTA}/capex-items/{a_borrar['id']}", headers=con_version(cab("consultor_a"), a_borrar)
    )
    assert r.status_code == 200
    assert len(r.json()["capex_lines"]) == 1


# ─────────────────────────────────────────────────────────────────────────────
#  Estados
# ─────────────────────────────────────────────────────────────────────────────


def test_el_hallazgo_avanza_de_borrador_a_validado(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    hallazgo = crear(
        cliente,
        cab,
        proyecto,
        catalogo,
        activo,
        capex_lines=[{"time_horizon_code": "CORTO", "amount": "0"}],
    ).json()
    for destino in ("EN_REVISION", "VALIDADO"):
        r = cliente.post(
            f"{RUTA}/findings/{hallazgo['id']}/transitions",
            headers=cab("consultor_a"),
            json={"to": destino},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == destino


def test_sin_linea_de_capex_no_se_valida(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    hallazgo = crear(cliente, cab, proyecto, catalogo, activo).json()
    cliente.post(
        f"{RUTA}/findings/{hallazgo['id']}/transitions",
        headers=cab("consultor_a"),
        json={"to": "EN_REVISION"},
    )
    r = cliente.post(
        f"{RUTA}/findings/{hallazgo['id']}/transitions",
        headers=cab("consultor_a"),
        json={"to": "VALIDADO"},
    )
    assert r.status_code == 422


def test_saltarse_la_revision_es_un_conflicto(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    hallazgo = crear(cliente, cab, proyecto, catalogo, activo).json()
    r = cliente.post(
        f"{RUTA}/findings/{hallazgo['id']}/transitions",
        headers=cab("consultor_a"),
        json={"to": "VALIDADO"},
    )
    assert r.status_code == 409


def test_los_destinos_llegan_con_sus_impedimentos(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    hallazgo = crear(cliente, cab, proyecto, catalogo, activo).json()
    cliente.post(
        f"{RUTA}/findings/{hallazgo['id']}/transitions",
        headers=cab("consultor_a"),
        json={"to": "EN_REVISION"},
    )
    destinos = cliente.get(
        f"{RUTA}/findings/{hallazgo['id']}/transitions", headers=cab("consultor_a")
    ).json()
    validado = next(d for d in destinos if d["to"] == "VALIDADO")
    assert validado["allowed"] is False
    assert validado["blockers"]


def test_el_cambio_de_estado_queda_auditado(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    catalogo: dict[str, Any],
    activo: str,
    motor_admin: Engine,
) -> None:
    hallazgo = crear(cliente, cab, proyecto, catalogo, activo).json()
    cliente.post(
        f"{RUTA}/findings/{hallazgo['id']}/transitions",
        headers=cab("consultor_a"),
        json={"to": "EN_REVISION"},
    )
    with motor_admin.begin() as conn:
        traza = conn.execute(
            text(
                "SELECT before_data, after_data FROM audit_log "
                "WHERE entity_id = :i AND action = 'FINDING_TRANSITIONED'"
            ),
            {"i": hallazgo["id"]},
        ).one()
    assert traza.before_data["status"] == "BORRADOR"
    assert traza.after_data["status"] == "EN_REVISION"


# ─────────────────────────────────────────────────────────────────────────────
#  Atajo de campo
# ─────────────────────────────────────────────────────────────────────────────


def test_el_hallazgo_desde_una_foto_hereda_activo_y_zona(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """`[REC]` Es el flujo de campo: se ve algo, se fotografía y se anota desde
    la propia foto. Volver a teclear lo que la foto ya sabe es trabajo repetido
    y una fuente de errores de asignación."""
    foto = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab("consultor_a"),
        files={"file": ("campo.jpg", io.BytesIO(imagen(color=(21, 71, 121))), "image/jpeg")},
        data={"asset_id": activo, "zone_id": catalogo["zona"], "origin": "CAMARA"},
    ).json()

    r = cliente.post(
        f"{RUTA}/findings/from-photo",
        headers=cab("consultor_a"),
        json={
            "photo_id": foto["id"],
            "capex_code_id": catalogo["codigo"],
            "title": "Corrosión en soporte de canalón",
            "description": "Óxido activo con pérdida de sección apreciable.",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["asset_id"] == activo
    assert r.json()["zone_id"] == catalogo["zona"]


def test_la_foto_queda_enlazada_como_evidencia(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    catalogo: dict[str, Any],
    activo: str,
    motor_admin: Engine,
) -> None:
    """Es el motivo por el que existe el hallazgo, y el informe la necesitará."""
    foto = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab("consultor_a"),
        files={"file": ("campo2.jpg", io.BytesIO(imagen(color=(9, 99, 199))), "image/jpeg")},
        data={"asset_id": activo, "zone_id": catalogo["zona"]},
    ).json()
    hallazgo = cliente.post(
        f"{RUTA}/findings/from-photo",
        headers=cab("consultor_a"),
        json={
            "photo_id": foto["id"],
            "capex_code_id": catalogo["codigo"],
            "title": "Humedad en falso techo",
        },
    ).json()

    with motor_admin.begin() as conn:
        papel = conn.execute(
            text(
                "SELECT CAST(role AS text) FROM photo_link WHERE photo_id = :f "
                "AND entity_type = 'FINDING' AND entity_id = :h"
            ),
            {"f": foto["id"], "h": hallazgo["id"]},
        ).scalar_one()
    assert papel == "EVIDENCIA"


def test_una_foto_sin_activo_no_puede_generar_un_hallazgo(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any]
) -> None:
    """Se acepta subir una foto sin activo, pero un hallazgo sin activo no
    sabría a qué edificio se refiere."""
    foto = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab("consultor_a"),
        files={"file": ("suelta.jpg", io.BytesIO(imagen(color=(5, 55, 155))), "image/jpeg")},
    ).json()
    r = cliente.post(
        f"{RUTA}/findings/from-photo",
        headers=cab("consultor_a"),
        json={"photo_id": foto["id"], "capex_code_id": catalogo["codigo"], "title": "Algo"},
    )
    assert r.status_code == 422
    assert "activo" in r.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
#  Filtros y aislamiento
# ─────────────────────────────────────────────────────────────────────────────


def test_filtrar_por_codigo_incluye_el_subarbol(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """Filtrar por «Cubiertas» debe traer también sus elementos. Si no, el
    filtro engaña: parece que no hay nada y lo que hay está un nivel más abajo."""
    crear(cliente, cab, proyecto, catalogo, activo)
    r = cliente.get(
        f"{RUTA}/projects/{proyecto}/findings?capex_code_id={catalogo['codigo_padre']}",
        headers=cab("consultor_a"),
    )
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_otra_organizacion_no_ve_el_hallazgo(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    hallazgo = crear(cliente, cab, proyecto, catalogo, activo).json()
    assert (
        cliente.get(f"{RUTA}/findings/{hallazgo['id']}", headers=cab("admin_b")).status_code == 404
    )


def test_el_borrado_del_hallazgo_es_logico(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    catalogo: dict[str, Any],
    activo: str,
    motor_admin: Engine,
) -> None:
    hallazgo = crear(cliente, cab, proyecto, catalogo, activo).json()
    assert (
        cliente.delete(
            f"{RUTA}/findings/{hallazgo['id']}",
            headers=con_version(cab("consultor_a"), hallazgo),
        ).status_code
        == 204
    )
    with motor_admin.begin() as conn:
        assert (
            conn.execute(
                text("SELECT deleted_at FROM finding WHERE id = :i"), {"i": hallazgo["id"]}
            ).scalar_one()
            is not None
        )


def test_una_medicion_incompleta_dice_que_falta_en_vez_de_reventar(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> None:
    """`[REQ]` Olvidar la unidad daba un `500` «Error interno».

    El `CHECK` de la base exige el trío entero —unidad, cantidad y precio—, y
    sin traducirlo el usuario recibía un error genérico que no decía qué
    corregir. Se descubrió escribiendo una prueba de concurrencia que omitía la
    unidad sin querer.
    """
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/findings",
        headers=cab("consultor_a"),
        json={
            "asset_id": activo,
            "capex_code_id": catalogo["codigo"],
            "zone_id": catalogo["zona"],
            "title": "Sin unidad",
            "capex_lines": [
                {
                    "time_horizon_code": "CORTO",
                    "amount": "100.00",
                    "measurement_quantity": "10.00",
                    "measurement_unit_price": "10.00",
                }
            ],
        },
    )
    assert r.status_code == 422
    assert "unidad" in r.json()["detail"]

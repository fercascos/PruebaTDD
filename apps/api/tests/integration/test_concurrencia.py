"""Concurrencia optimista `[REQ]`.

El escenario que estas pruebas reproducen, con nombres: **Marta** abre un
hallazgo, **Luis** abre el mismo hallazgo, Marta corrige la descripción y
guarda, Luis guarda su cambio de riesgo treinta segundos después.

Antes de esto, la corrección de Marta desaparecía y nadie se enteraba. Aquí se
comprueba que ya no: que Luis recibe un `412`, que el mensaje dice **quién** lo
cambió, y —lo que de verdad importa— que **el texto de Marta sigue ahí**.

`consultor_a` y `consultor2_a` son las dos personas. Son de la misma
organización a propósito: el aislamiento entre organizaciones ya lo cubre
`test_rls_y_restricciones`, y lo que se prueba aquí es lo contrario, dos
compañeros trabajando en el mismo encargo.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.db

RUTA = "/api/v1"


@pytest.fixture(scope="module")
def catalogo(motor_admin: Engine) -> dict[str, Any]:
    """Lo mínimo del catálogo para poder crear un hallazgo."""
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
        codigo = conn.execute(
            text("SELECT id FROM capex_code WHERE level = 3 ORDER BY code LIMIT 1")
        ).scalar_one()
    return {
        "tipologia": str(tipologia),
        "zone_id": str(zona),
        "capex_code_id": str(codigo),
    }


@pytest.fixture
def proyecto(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    """Uno por prueba: dos personas editando a la vez es justo lo que se
    prueba, y compartir el encargo haría depender el resultado del orden."""
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo a cuatro manos') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"CON-{uuid.uuid4().hex[:6]}",
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


def etag(fila: dict[str, Any]) -> str:
    return f'"{fila["row_version"]}"'


def con(cabeceras: dict[str, str], fila: dict[str, Any]) -> dict[str, str]:
    return {**cabeceras, "If-Match": etag(fila)}


@pytest.fixture
def hallazgo(
    cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any], activo: str
) -> dict[str, Any]:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/findings",
        headers=cab("consultor_a"),
        json={
            "asset_id": activo,
            "capex_code_id": catalogo["capex_code_id"],
            "zone_id": catalogo["zone_id"],
            "title": "Junta de dilatación abierta",
            "description": "Descripción original",
            "capex_lines": [{"time_horizon_code": "CORTO", "amount": "1000.00"}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


# ─────────────────────────────────────────────────────────────────────────────
#  El escenario completo
# ─────────────────────────────────────────────────────────────────────────────


def test_el_segundo_en_guardar_no_pisa_al_primero(
    cliente: TestClient, cab: Any, hallazgo: dict[str, Any]
) -> None:
    """`[REQ]` La prueba que da sentido a todo el módulo.

    Lo que se comprueba al final no es el código de estado: es que **el texto
    de Marta sigue en la base**. Un 412 que aun así hubiera escrito no serviría
    de nada.
    """
    # Los dos abren la misma versión.
    abierto_por_marta = cliente.get(
        f"{RUTA}/findings/{hallazgo['id']}", headers=cab("consultor_a")
    ).json()
    abierto_por_luis = cliente.get(
        f"{RUTA}/findings/{hallazgo['id']}", headers=cab("consultor2_a")
    ).json()
    assert abierto_por_marta["row_version"] == abierto_por_luis["row_version"]

    # Marta guarda primero.
    marta = cliente.patch(
        f"{RUTA}/findings/{hallazgo['id']}",
        headers=con(cab("consultor_a"), abierto_por_marta),
        json={"description": "Junta abierta 4 cm en la fachada norte"},
    )
    assert marta.status_code == 200, marta.text

    # Luis guarda después, con la versión que leyó hace un rato.
    luis = cliente.patch(
        f"{RUTA}/findings/{hallazgo['id']}",
        headers=con(cab("consultor2_a"), abierto_por_luis),
        json={"description": "Junta abierta, revisar"},
    )
    assert luis.status_code == 412

    # Y lo que de verdad importa: no se ha perdido nada.
    ahora = cliente.get(f"{RUTA}/findings/{hallazgo['id']}", headers=cab("admin_a")).json()
    assert ahora["description"] == "Junta abierta 4 cm en la fachada norte"


def test_el_mensaje_dice_quien_lo_cambio(
    cliente: TestClient, cab: Any, hallazgo: dict[str, Any]
) -> None:
    """`[REQ]` «Alguien lo cambió» no ayuda a resolverlo; un nombre sí.

    Es la razón de que exista la columna `updated_by` y de que la rellene el
    disparador: quien recibe el conflicto sabe con quién hablar.
    """
    viejo = cliente.get(f"{RUTA}/findings/{hallazgo['id']}", headers=cab("consultor2_a")).json()
    cliente.patch(
        f"{RUTA}/findings/{hallazgo['id']}",
        headers=con(cab("consultor_a"), viejo),
        json={"title": "Junta de dilatación abierta en fachada norte"},
    )
    choque = cliente.patch(
        f"{RUTA}/findings/{hallazgo['id']}",
        headers=con(cab("consultor2_a"), viejo),
        json={"title": "Otra cosa"},
    )
    assert choque.status_code == 412
    detalle = choque.json()["detail"]
    assert "Consultor" in detalle or "consultor" in detalle.lower()
    assert "no se han guardado" in detalle


def test_reintentar_con_la_version_nueva_funciona(
    cliente: TestClient, cab: Any, hallazgo: dict[str, Any]
) -> None:
    """El conflicto no es un callejón sin salida: se recarga y se vuelve."""
    viejo = cliente.get(f"{RUTA}/findings/{hallazgo['id']}", headers=cab("consultor2_a")).json()
    cliente.patch(
        f"{RUTA}/findings/{hallazgo['id']}",
        headers=con(cab("consultor_a"), viejo),
        json={"comments": "Medido en obra"},
    )
    assert (
        cliente.patch(
            f"{RUTA}/findings/{hallazgo['id']}",
            headers=con(cab("consultor2_a"), viejo),
            json={"comments": "Otra cosa"},
        ).status_code
        == 412
    )
    fresco = cliente.get(f"{RUTA}/findings/{hallazgo['id']}", headers=cab("consultor2_a")).json()
    segundo = cliente.patch(
        f"{RUTA}/findings/{hallazgo['id']}",
        headers=con(cab("consultor2_a"), fresco),
        json={"comments": "Medido en obra · confirmado"},
    )
    assert segundo.status_code == 200
    assert segundo.json()["comments"] == "Medido en obra · confirmado"


# ─────────────────────────────────────────────────────────────────────────────
#  La cabecera y el contador
# ─────────────────────────────────────────────────────────────────────────────


def test_sin_if_match_un_hallazgo_no_se_modifica(
    cliente: TestClient, cab: Any, hallazgo: dict[str, Any]
) -> None:
    """`[REQ]` `428`, no un guardado silencioso.

    Es lo que impide que una pantalla nueva pierda la protección por olvidarse
    de mandar la cabecera: no se le olvida, se le rechaza.
    """
    r = cliente.patch(
        f"{RUTA}/findings/{hallazgo['id']}",
        headers=cab("consultor_a"),
        json={"description": "sin cabecera"},
    )
    assert r.status_code == 428
    assert "If-Match" in r.json()["detail"]


def test_sin_if_match_una_linea_tampoco(
    cliente: TestClient, cab: Any, hallazgo: dict[str, Any]
) -> None:
    r = cliente.patch(
        f"{RUTA}/capex-items/{hallazgo['capex_lines'][0]['id']}",
        headers=cab("consultor_a"),
        json={"amount": "2000.00"},
    )
    assert r.status_code == 428


def test_la_lectura_devuelve_el_etag(
    cliente: TestClient, cab: Any, hallazgo: dict[str, Any]
) -> None:
    r = cliente.get(f"{RUTA}/findings/{hallazgo['id']}", headers=cab("consultor_a"))
    assert r.headers["ETag"] == etag(r.json())
    # Sin `W/`: `If-Match` exige comparación fuerte.
    assert not r.headers["ETag"].startswith("W/")


def test_cada_escritura_sube_el_contador(
    cliente: TestClient, cab: Any, hallazgo: dict[str, Any]
) -> None:
    """Lo lleva el disparador, así que ningún `UPDATE` puede saltárselo."""
    actual = hallazgo
    for i in range(3):
        r = cliente.patch(
            f"{RUTA}/findings/{hallazgo['id']}",
            headers=con(cab("consultor_a"), actual),
            json={"comments": f"vuelta {i}"},
        )
        assert r.status_code == 200
        assert r.json()["row_version"] == actual["row_version"] + 1
        actual = r.json()


def test_un_asterisco_vale_por_cualquier_version(
    cliente: TestClient, cab: Any, hallazgo: dict[str, Any]
) -> None:
    """`If-Match: *` significa «existe», y la fila ya se ha leído."""
    r = cliente.patch(
        f"{RUTA}/findings/{hallazgo['id']}",
        headers={**cab("consultor_a"), "If-Match": "*"},
        json={"comments": "con asterisco"},
    )
    assert r.status_code == 200


def test_un_etag_debil_se_acepta_igual(
    cliente: TestClient, cab: Any, hallazgo: dict[str, Any]
) -> None:
    """Rechazarlo por la `W/` daría un 412 que parece un conflicto de edición
    sin serlo, y depurar eso desde la pantalla es un mal rato evitable."""
    r = cliente.patch(
        f"{RUTA}/findings/{hallazgo['id']}",
        headers={**cab("consultor_a"), "If-Match": f'W/"{hallazgo["row_version"]}"'},
        json={"comments": "débil"},
    )
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
#  Las líneas de CAPEX llevan su propia versión
# ─────────────────────────────────────────────────────────────────────────────


def test_dos_lineas_distintas_del_mismo_hallazgo_no_se_estorban(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    catalogo: dict[str, Any],
    activo: str,
) -> None:
    """`[REQ]` Por eso se compara contra la versión **de la línea**.

    Si se comparase contra la del hallazgo, ajustar el importe a corto plazo
    bloquearía a quien está ajustando el de medio, que no se pisan en nada.
    """
    h = cliente.post(
        f"{RUTA}/projects/{proyecto}/findings",
        headers=cab("consultor_a"),
        json={
            "asset_id": activo,
            "capex_code_id": catalogo["capex_code_id"],
            "zone_id": catalogo["zone_id"],
            "title": "Cubierta",
            "capex_lines": [
                {"time_horizon_code": "CORTO", "amount": "100.00"},
                {"time_horizon_code": "MEDIO", "amount": "200.00"},
            ],
        },
    ).json()
    corto, medio = h["capex_lines"][0], h["capex_lines"][1]

    primero = cliente.patch(
        f"{RUTA}/capex-items/{corto['id']}",
        headers=con(cab("consultor_a"), corto),
        json={"amount": "150.00"},
    )
    assert primero.status_code == 200

    # La otra línea sigue en su versión: no la ha tocado nadie.
    segundo = cliente.patch(
        f"{RUTA}/capex-items/{medio['id']}",
        headers=con(cab("consultor2_a"), medio),
        json={"amount": "250.00"},
    )
    assert segundo.status_code == 200
    assert segundo.json()["total_amount"] == "400.0000"


def test_la_misma_linea_editada_a_la_vez_si_choca(
    cliente: TestClient, cab: Any, hallazgo: dict[str, Any]
) -> None:
    linea = hallazgo["capex_lines"][0]
    cliente.patch(
        f"{RUTA}/capex-items/{linea['id']}",
        headers=con(cab("consultor_a"), linea),
        json={"amount": "1500.00"},
    )
    choque = cliente.patch(
        f"{RUTA}/capex-items/{linea['id']}",
        headers=con(cab("consultor2_a"), linea),
        json={"amount": "9999.00"},
    )
    assert choque.status_code == 412
    ahora = cliente.get(f"{RUTA}/findings/{hallazgo['id']}", headers=cab("admin_a")).json()
    assert ahora["capex_lines"][0]["amount"] == "1500.0000"


# ─────────────────────────────────────────────────────────────────────────────
#  Donde la cabecera es opcional
# ─────────────────────────────────────────────────────────────────────────────


def test_un_activo_se_puede_modificar_sin_cabecera(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """`[LIM]` Opcional a propósito: las importaciones escriben sin haber leído.

    Exigirles una versión que no tienen obligaría a una lectura previa que
    tampoco elimina la carrera —entre leer y escribir cabe otra petición— y
    solo añadiría ruido.
    """
    r = cliente.patch(
        f"{RUTA}/assets/{activo}", headers=cab("consultor_a"), json={"notes": "sin cabecera"}
    )
    assert r.status_code == 200


def test_pero_si_la_cabecera_viene_se_honra(cliente: TestClient, cab: Any, activo: str) -> None:
    """Opcional no significa ignorada: quien la manda queda protegido."""
    viejo = cliente.get(f"{RUTA}/assets/{activo}", headers=cab("consultor_a")).json()
    cliente.patch(
        f"{RUTA}/assets/{activo}", headers=con(cab("consultor_a"), viejo), json={"notes": "primero"}
    )
    r = cliente.patch(
        f"{RUTA}/assets/{activo}",
        headers=con(cab("consultor2_a"), viejo),
        json={"notes": "segundo"},
    )
    assert r.status_code == 412
    ahora = cliente.get(f"{RUTA}/assets/{activo}", headers=cab("admin_a")).json()
    assert ahora["notes"] == "primero"


def test_una_fila_que_no_existe_da_404_no_412(cliente: TestClient, cab: Any) -> None:
    """El orden importa: comprobar la versión de algo inexistente daría un
    conflicto donde lo que pasa es que no está."""
    r = cliente.patch(
        f"{RUTA}/findings/{uuid.uuid4()}",
        headers={**cab("consultor_a"), "If-Match": '"1"'},
        json={"comments": "x"},
    )
    assert r.status_code == 404

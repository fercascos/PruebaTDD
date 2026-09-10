"""La visita del activo `[REQ]` §3.2 c de `docs/23`.

Lo que la hoja del cliente pide de esta sección son tres bloques —datos de la
visita, equipo implicado y fotos— y casi todo estaba ya en `asset_visit`. Lo que
se comprueba aquí es lo que se ha añadido, y una promesa hecha al cliente:

* **el equipo implicado son dos cosas en la misma lista**: usuarios de la
  aplicación y gente de fuera que nunca va a tener cuenta, y cada línea es una
  cosa o la otra, nunca las dos;
* **cuatro «Responsable» no es un tope**, es lo que cabía en una hoja de cálculo;
* **el coste de la visita NO sale en el informe**. Es coste interno del encargo,
  y esa promesa no se sostiene con un comentario: se sostiene mirando el
  snapshot.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from tdd.reporting import snapshot

pytestmark = pytest.mark.db

RUTA = "/api/v1"


@pytest.fixture
def proyecto(cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]) -> str:
    r = cliente.post(
        f"{RUTA}/projects",
        headers=cab("admin_a"),
        json={
            "client_id": str(datos_base["cliente_a"]),
            "internal_code": f"VIS-{uuid.uuid4().hex[:6]}",
            "name": "Proyecto con visitas",
            "applicable_phases": [{"code": "VISITA"}],
        },
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine) -> str:
    with motor_admin.begin() as conn:
        tipologia = conn.execute(text("SELECT id FROM asset_typology LIMIT 1")).scalar_one()
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": f"Nave {uuid.uuid4().hex[:6]}", "typology_id": str(tipologia)},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def programar(cliente: TestClient, cab: Any, proyecto: str, activo: str, **campos: Any) -> Any:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/visits",
        headers=cab("consultor_a"),
        json={"asset_id": activo, **campos},
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


# ─────────────────────────────────────────────────────────────────────────────
#  V1 · Datos de la visita
# ─────────────────────────────────────────────────────────────────────────────


def test_el_punto_de_encuentro_se_guarda_al_programar(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` La «Ubicación» de la hoja. No es la dirección del activo —esa ya
    está en su ficha—: es por dónde se entra el día de la visita."""
    visita = programar(
        cliente,
        cab,
        proyecto,
        activo,
        scheduled_date=str(date.today() + timedelta(days=7)),
        meeting_point="Entrada por el muelle 4; preguntar por el jefe de mantenimiento.",
    )
    assert visita["meeting_point"].startswith("Entrada por el muelle 4")
    assert visita["status"] == "AGENDADO"


def test_el_activo_lista_sus_propias_visitas_y_no_las_de_al_lado(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, motor_admin: Engine
) -> None:
    with motor_admin.begin() as conn:
        tipologia = conn.execute(text("SELECT id FROM asset_typology LIMIT 1")).scalar_one()
    otro = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave de al lado", "typology_id": str(tipologia)},
    ).json()["id"]
    programar(cliente, cab, proyecto, activo, meeting_point="La mía")
    programar(cliente, cab, proyecto, otro, meeting_point="La del vecino")

    r = cliente.get(f"{RUTA}/assets/{activo}/visits", headers=cab("consultor_a"))

    assert r.status_code == 200, r.text
    assert [v["meeting_point"] for v in r.json()] == ["La mía"]


def test_un_activo_admite_varias_visitas_y_la_ultima_va_primero(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """Se vuelve al edificio: con el instalador, o a ver la cubierta que llovía.
    La que se está rellenando es la última, y buscarla al final de la lista cada
    vez que se abre la ficha es exactamente el trabajo que sobra."""
    programar(cliente, cab, proyecto, activo, scheduled_date=str(date(2026, 3, 1)))
    programar(cliente, cab, proyecto, activo, scheduled_date=str(date(2026, 9, 1)))

    fechas = [
        v["scheduled_date"]
        for v in cliente.get(f"{RUTA}/assets/{activo}/visits", headers=cab("consultor_a")).json()
    ]

    assert fechas == ["2026-09-01", "2026-03-01"]


def test_el_check_de_visita_realizada_es_el_estado_visitado(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` «Check visita · marcar si la visita ha sido realizada». No hace
    falta columna nueva: es `VISITADO`, y la base ya exige fecha real para
    aceptarlo, que es lo que fecha el informe."""
    visita = programar(cliente, cab, proyecto, activo)

    r = cliente.patch(
        f"{RUTA}/visits/{visita['id']}", headers=cab("consultor_a"), json={"status": "VISITADO"}
    )

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "VISITADO"
    assert r.json()["actual_date"] == str(date.today()), "se fecha sola"


def test_un_activo_que_no_existe_no_devuelve_una_lista_vacia(cliente: TestClient, cab: Any) -> None:
    """Una lista vacía se lee como «este activo no tiene visitas» y aquí lo que
    pasa es que el activo no está."""
    r = cliente.get(f"{RUTA}/assets/{uuid.uuid4()}/visits", headers=cab("consultor_a"))
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
#  V2 · Equipo implicado
# ─────────────────────────────────────────────────────────────────────────────


def test_quien_dirige_la_visita_entra_solo_en_la_lista(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, datos_base: Any
) -> None:
    """Estuvo allí. Tenerlo solo en `led_by` obligaría a la pantalla a sumarlo
    aparte y a acordarse de no duplicarlo cuando además se le apunte a mano."""
    visita = programar(cliente, cab, proyecto, activo, led_by=str(datos_base["consultor_a"]))

    assert len(visita["asistentes"]) == 1
    asistente = visita["asistentes"][0]
    assert asistente["app_user_id"] == str(datos_base["consultor_a"])
    assert asistente["es_del_equipo"] is True
    assert asistente["role_note"] == "Responsable de la visita"


def test_la_lista_mezcla_equipo_y_acompanantes_de_fuera(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, datos_base: Any
) -> None:
    """`[REQ]` Quien acompaña no tiene cuenta y nunca la va a tener. Perderlo
    sería perder a quien abrió el cuarto de máquinas."""
    visita = programar(cliente, cab, proyecto, activo)

    r = cliente.put(
        f"{RUTA}/visits/{visita['id']}/attendees",
        headers=cab("consultor_a"),
        json={
            "asistentes": [
                {"app_user_id": str(datos_base["consultor_a"]), "role_note": "Responsable"},
                {"external_name": "Nombre Ficticio", "role_note": "Jefe de mantenimiento"},
                {"external_name": "Otro Nombre", "role_note": "Mantenedor de PCI"},
            ]
        },
    )

    assert r.status_code == 200, r.text
    asistentes = r.json()["asistentes"]
    assert len(asistentes) == 3
    # Primero el equipo y después los de fuera: así se lee un acta.
    assert [a["es_del_equipo"] for a in asistentes] == [True, False, False]
    assert asistentes[1]["nombre"] == "Nombre Ficticio"
    assert asistentes[1]["app_user_id"] is None
    # El nombre del usuario sale de su cuenta y no se teclea otra vez.
    assert asistentes[0]["nombre"]


def test_cuatro_responsables_no_es_un_tope(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` Cuatro es lo que cabía en la hoja de cálculo, no lo que va a una
    visita de un complejo de seis naves."""
    visita = programar(cliente, cab, proyecto, activo)

    r = cliente.put(
        f"{RUTA}/visits/{visita['id']}/attendees",
        headers=cab("consultor_a"),
        json={"asistentes": [{"external_name": f"Asistente {i}"} for i in range(7)]},
    )

    assert r.status_code == 200, r.text
    assert len(r.json()["asistentes"]) == 7


def test_un_asistente_es_del_equipo_o_de_fuera_pero_no_las_dos(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, datos_base: Any
) -> None:
    """Con las dos cosas no se sabe cuál manda, y el nombre tecleado acabaría
    contradiciendo al de la cuenta el día que alguien se cambie el apellido."""
    visita = programar(cliente, cab, proyecto, activo)

    ambas = cliente.put(
        f"{RUTA}/visits/{visita['id']}/attendees",
        headers=cab("consultor_a"),
        json={
            "asistentes": [
                {"app_user_id": str(datos_base["consultor_a"]), "external_name": "Y además esto"}
            ]
        },
    )
    ninguna = cliente.put(
        f"{RUTA}/visits/{visita['id']}/attendees",
        headers=cab("consultor_a"),
        json={"asistentes": [{"role_note": "Vino alguien, no sé quién"}]},
    )

    assert ambas.status_code == 422
    assert ninguna.status_code == 422
    assert "ninguna" in ninguna.json()["detail"]


def test_la_misma_persona_del_equipo_no_se_apunta_dos_veces(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, datos_base: Any
) -> None:
    visita = programar(cliente, cab, proyecto, activo)
    r = cliente.put(
        f"{RUTA}/visits/{visita['id']}/attendees",
        headers=cab("consultor_a"),
        json={
            "asistentes": [
                {"app_user_id": str(datos_base["consultor_a"])},
                {"app_user_id": str(datos_base["consultor_a"]), "role_note": "otra vez"},
            ]
        },
    )
    assert r.status_code == 422
    assert "dos veces" in r.json()["detail"]


def test_dos_acompanantes_pueden_llamarse_igual(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """Dos «Juan» de dos empresas distintas son dos personas. Lo único que los
    distingue es en calidad de qué vinieron."""
    visita = programar(cliente, cab, proyecto, activo)
    r = cliente.put(
        f"{RUTA}/visits/{visita['id']}/attendees",
        headers=cab("consultor_a"),
        json={
            "asistentes": [
                {"external_name": "Nombre Ficticio", "role_note": "Property manager"},
                {"external_name": "Nombre Ficticio", "role_note": "Mantenedor"},
            ]
        },
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["asistentes"]) == 2


def test_no_se_apunta_a_una_persona_de_otra_organizacion(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, datos_base: Any
) -> None:
    """Colar un usuario ajeno en la lista filtraría su nombre a un informe que
    no es de su organización."""
    visita = programar(cliente, cab, proyecto, activo)
    r = cliente.put(
        f"{RUTA}/visits/{visita['id']}/attendees",
        headers=cab("consultor_a"),
        json={"asistentes": [{"app_user_id": str(datos_base["admin_b"])}]},
    )
    assert r.status_code == 422
    assert "organización" in r.json()["detail"]


def test_guardar_la_lista_sustituye_a_la_anterior(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """Se manda entera porque así se rellena: se abre la visita y se apunta
    quién fue, en un gesto."""
    visita = programar(cliente, cab, proyecto, activo)
    cliente.put(
        f"{RUTA}/visits/{visita['id']}/attendees",
        headers=cab("consultor_a"),
        json={"asistentes": [{"external_name": "Se equivocó de día"}]},
    )

    r = cliente.put(
        f"{RUTA}/visits/{visita['id']}/attendees",
        headers=cab("consultor_a"),
        json={"asistentes": [{"external_name": "El que vino de verdad"}]},
    )

    assert [a["nombre"] for a in r.json()["asistentes"]] == ["El que vino de verdad"]


def test_borrar_la_visita_se_lleva_a_sus_asistentes(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, motor_admin: Engine
) -> None:
    """Una lista de asistentes de una visita que ya no existe no es un dato, es
    basura que nadie va a poder interpretar."""
    visita = programar(cliente, cab, proyecto, activo)
    cliente.put(
        f"{RUTA}/visits/{visita['id']}/attendees",
        headers=cab("consultor_a"),
        json={"asistentes": [{"external_name": "Nombre Ficticio"}]},
    )

    with motor_admin.begin() as conn:
        conn.execute(text("DELETE FROM asset_visit WHERE id = :i"), {"i": visita["id"]})
        quedan = conn.execute(
            text("SELECT count(*) FROM visit_attendee WHERE asset_visit_id = :i"),
            {"i": visita["id"]},
        ).scalar_one()

    assert quedan == 0


def test_otra_organizacion_no_ve_las_visitas_ajenas(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    programar(cliente, cab, proyecto, activo, meeting_point="Secreto")
    r = cliente.get(f"{RUTA}/assets/{activo}/visits", headers=cab("admin_b"))
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
#  El coste, y por qué no sale del encargo
# ─────────────────────────────────────────────────────────────────────────────


def test_el_coste_de_la_visita_se_guarda(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    visita = programar(cliente, cab, proyecto, activo)
    r = cliente.patch(
        f"{RUTA}/visits/{visita['id']}",
        headers=cab("consultor_a"),
        json={"cost_amount": "1250.00"},
    )
    assert r.status_code == 200, r.text
    assert Decimal(r.json()["cost_amount"]) == Decimal("1250.00")


def test_un_coste_negativo_se_rechaza(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    visita = programar(cliente, cab, proyecto, activo)
    r = cliente.patch(
        f"{RUTA}/visits/{visita['id']}",
        headers=cab("consultor_a"),
        json={"cost_amount": "-100.00"},
    )
    assert r.status_code == 422


def test_el_coste_de_la_visita_no_entra_en_el_capex_del_activo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` **Lo decidió el cliente: es coste interno del encargo.**

    Los desplazamientos y las horas del consultor no son coste del edificio, y
    colarlos en los soft costs inflaría la cifra con la que el inversor negocia
    el precio de compra. Aquí se comprueba sobre el resumen del CAPEX, que es de
    donde salen los totales que ve el cliente.
    """
    visita = programar(cliente, cab, proyecto, activo)
    cliente.patch(
        f"{RUTA}/visits/{visita['id']}",
        headers=cab("consultor_a"),
        json={"cost_amount": "1250.00"},
    )

    por_activo = cliente.get(
        f"{RUTA}/projects/{proyecto}/capex/summary/by-asset", headers=cab("consultor_a")
    ).json()

    total = sum(Decimal(str(fila["amount"])) for fila in por_activo)
    assert total == Decimal("0"), "el coste de la visita ha llegado al CAPEX del edificio"


def test_el_coste_de_la_visita_no_sale_en_el_informe(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, motor_admin: Engine
) -> None:
    """La otra mitad de la misma promesa, y la que de verdad la sostiene.

    El snapshot es lo que se congela y se entrega. Si el importe apareciera ahí,
    daría igual que el CAPEX no lo sumara: estaría en el documento del cliente.
    Se busca la cifra **en el JSON entero**, no en el trozo de las visitas: un
    campo nuevo en cualquier otra parte del snapshot se colaría igual.
    """
    visita = programar(cliente, cab, proyecto, activo, scheduled_date=str(date.today()))
    cliente.patch(
        f"{RUTA}/visits/{visita['id']}",
        headers=cab("consultor_a"),
        json={"status": "VISITADO", "cost_amount": "1250.00"},
    )

    with Session(motor_admin) as sesion:
        congelado = snapshot.construir(sesion, uuid.UUID(proyecto))

    entero = json.dumps(congelado, default=str, ensure_ascii=False)
    assert "1250" not in entero, "el coste de la visita se ha colado en el informe"
    # Y la visita sí está: lo que se comprueba es que sale SIN el importe, no
    # que el informe se haya quedado sin la visita entera.
    assert congelado["visits"], "la visita ha desaparecido del informe"
    assert "cost_amount" not in congelado["visits"][0]

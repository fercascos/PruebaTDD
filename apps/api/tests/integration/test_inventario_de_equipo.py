"""Inventario de equipo `[REQ]` §7 / P-15.

Tres cosas que solo se ven contra PostgreSQL de verdad:

* que la **vida residual se calcula y no se guarda** (P-15), de forma que un
  inventario cargado hoy siga diciendo la verdad dentro de dos años;
* que la etiqueta de campo sea única **dentro del activo** y no del sistema, que
  es lo que permite que dos edificios tengan los dos su «CL-01»;
* que la RLS aísle el inventario como cualquier otro dato de cliente.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.db

RUTA = "/api/v1"
HOY = date.today().year


@pytest.fixture
def proyecto(datos_base: dict[str, uuid.UUID]) -> str:
    return str(datos_base["proyecto_a"])


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine) -> str:
    with motor_admin.begin() as conn:
        tipologia = conn.execute(text("SELECT id FROM asset_typology LIMIT 1")).scalar_one()
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": f"Edificio {uuid.uuid4().hex[:6]}", "typology_id": str(tipologia)},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def alta(cliente: TestClient, cab: Any, proyecto: str, activo: str, **campos: Any) -> Any:
    cuerpo = {"asset_id": activo, "equipment_type": "Enfriadora", **campos}
    return cliente.post(
        f"{RUTA}/projects/{proyecto}/equipment", headers=cab("consultor_a"), json=cuerpo
    )


# ─────────────────────────────────────────────────────────────────────────────
#  El catálogo de sistemas técnicos
# ─────────────────────────────────────────────────────────────────────────────


def test_los_catorce_sistemas_tecnicos_estan_sembrados(cliente: TestClient, cab: Any) -> None:
    r = cliente.get(f"{RUTA}/catalogs/technical-systems", headers=cab("consultor_a"))
    assert r.status_code == 200, r.text
    sistemas = r.json()
    assert len(sistemas) == 14
    # El orden es el de una visita, no el alfabético: si lo fuera,
    # «Accesibilidad» iría delante de «Cubierta».
    assert sistemas[0]["name_es"] == "Fachada y envolvente"


def test_el_mapeo_a_capitulos_conserva_el_que_apunta_a_dos(cliente: TestClient, cab: Any) -> None:
    """`[REQ]` §5.8 · «Protección contra incendios» es UNA categoría y DOS
    capítulos. Por eso `capex_chapter` es texto: una clave ajena habría obligado
    a elegir uno de los dos y habría perdido justo lo que motiva la distinción.
    """
    r = cliente.get(f"{RUTA}/catalogs/technical-systems", headers=cab("consultor_a"))
    pci = next(s for s in r.json() if s["code"] == "PCI")
    assert pci["capex_chapter"] == "H06 + H10"


# ─────────────────────────────────────────────────────────────────────────────
#  Alta y vida residual
# ─────────────────────────────────────────────────────────────────────────────


def test_se_da_de_alta_un_equipo_con_su_ficha(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    r = alta(
        cliente,
        cab,
        proyecto,
        activo,
        tag="CL-01",
        manufacturer="Fabricante Ficticio",
        model="XR-300",
        serial_number="4J-00219",
        install_year=2010,
        expected_life_years=20,
        condition="ACEPTABLE",
        obsolescence="PROXIMO_A_OBSOLETO",
        criticality="ALTA",
        quantity="2",
        notes="Dos unidades en cubierta.",
    )
    assert r.status_code == 201, r.text
    equipo = r.json()
    assert equipo["tag"] == "CL-01"
    assert equipo["end_of_life_year"] == 2030
    assert equipo["remaining_life_years"] == 2030 - HOY


def test_la_vida_residual_no_se_guarda_en_ninguna_columna(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, motor_admin: Engine
) -> None:
    """`[REQ]` P-15 · «La vida residual se calcula, no se teclea.»

    Lo que la base guarda es el año en que el equipo agota su vida útil, que no
    cambia. Una columna con los años restantes valdría el día que se escribe y
    mentiría a partir del 1 de enero siguiente.
    """
    with motor_admin.begin() as conn:
        columnas = {
            f[0]
            for f in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'equipment'"
                )
            )
        }
    assert "remaining_life_years" not in columnas
    assert "end_of_life_year" in columnas


def test_no_se_admite_la_vida_residual_como_campo_de_entrada(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """Enviarla se rechaza en vez de ignorarse en silencio: un campo aceptado y
    descartado produce fichas que parecen completas y no lo están."""
    r = alta(cliente, cab, proyecto, activo, remaining_life_years=5)
    assert r.status_code == 422


def test_un_equipo_ya_vencido_lo_dice_y_lo_pone_en_el_plazo_mas_inmediato(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    r = alta(cliente, cab, proyecto, activo, install_year=1990, expected_life_years=20)
    equipo = r.json()
    assert equipo["vencido"] is True
    assert equipo["remaining_life_years"] < 0
    assert equipo["horizonte_code"] == "CORTO"
    assert "agotada" in equipo["vida_resumen"]


def test_un_equipo_sin_anos_no_finge_un_calculo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    equipo = alta(cliente, cab, proyecto, activo).json()
    assert equipo["remaining_life_years"] is None
    assert equipo["horizonte_code"] is None
    assert equipo["vencido"] is False
    assert "no se puede calcular" in equipo["vida_resumen"]


def test_media_vida_util_se_rechaza(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """El año de instalación y la vida esperada van juntos o no van. Con solo
    uno de los dos no hay nada que calcular, y guardar la mitad del dato produce
    fichas que parecen completas."""
    r = alta(cliente, cab, proyecto, activo, install_year=2010)
    assert r.status_code >= 400


# ─────────────────────────────────────────────────────────────────────────────
#  Etiqueta de campo
# ─────────────────────────────────────────────────────────────────────────────


def test_la_etiqueta_no_se_repite_dentro_del_mismo_activo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    assert alta(cliente, cab, proyecto, activo, tag="CL-01").status_code == 201
    assert alta(cliente, cab, proyecto, activo, tag="CL-01").status_code == 409


def test_dos_edificios_pueden_tener_los_dos_su_cl_01(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, motor_admin: Engine
) -> None:
    """La etiqueta identifica al equipo dentro del activo: así es como está
    rotulado en la sala, y dos edificios se rotulan igual."""
    with motor_admin.begin() as conn:
        tipologia = conn.execute(text("SELECT id FROM asset_typology LIMIT 1")).scalar_one()
    otro = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Edificio Sur", "typology_id": str(tipologia)},
    ).json()["id"]

    assert alta(cliente, cab, proyecto, activo, tag="CL-01").status_code == 201
    assert alta(cliente, cab, proyecto, otro, tag="CL-01").status_code == 201


def test_borrar_libera_la_etiqueta(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    primero = alta(cliente, cab, proyecto, activo, tag="AS-01").json()
    assert (
        cliente.delete(f"{RUTA}/equipment/{primero['id']}", headers=cab("consultor_a")).status_code
        == 204
    )
    assert alta(cliente, cab, proyecto, activo, tag="AS-01").status_code == 201


def test_el_borrado_es_logico_y_la_ficha_sigue_en_la_base(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, motor_admin: Engine
) -> None:
    """La ficha se escribió en una visita a la que no se vuelve. Borrarla de
    verdad significaría volver al edificio a por el número de serie."""
    equipo = alta(cliente, cab, proyecto, activo, serial_number="4J-00219").json()
    cliente.delete(f"{RUTA}/equipment/{equipo['id']}", headers=cab("consultor_a"))

    assert (
        cliente.get(f"{RUTA}/equipment/{equipo['id']}", headers=cab("consultor_a")).status_code
        == 404
    )
    with motor_admin.begin() as conn:
        serie = conn.execute(
            text("SELECT serial_number FROM equipment WHERE id = :i"), {"i": equipo["id"]}
        ).scalar_one()
    assert serie == "4J-00219"


# ─────────────────────────────────────────────────────────────────────────────
#  Listado, filtros y búsqueda
# ─────────────────────────────────────────────────────────────────────────────


def test_el_filtro_de_vencidos_compara_contra_el_ano_en_curso(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    alta(cliente, cab, proyecto, activo, tag="VIEJO", install_year=1990, expected_life_years=20)
    alta(cliente, cab, proyecto, activo, tag="NUEVO", install_year=HOY, expected_life_years=25)

    r = cliente.get(
        f"{RUTA}/projects/{proyecto}/equipment?asset_id={activo}&solo_vencidos=true",
        headers=cab("consultor_a"),
    )
    etiquetas = {e["tag"] for e in r.json()}
    assert "VIEJO" in etiquetas
    assert "NUEVO" not in etiquetas


def test_se_busca_por_fabricante_modelo_o_numero_de_serie(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    alta(cliente, cab, proyecto, activo, tag="B1", manufacturer="Fabricante Ficticio")
    alta(cliente, cab, proyecto, activo, tag="B2", equipment_type="Ascensor")

    r = cliente.get(
        f"{RUTA}/projects/{proyecto}/equipment?asset_id={activo}&q=ascensor",
        headers=cab("consultor_a"),
    )
    assert [e["tag"] for e in r.json()] == ["B2"]


def test_se_filtra_por_sistema_tecnico(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    sistemas = cliente.get(f"{RUTA}/catalogs/technical-systems", headers=cab("consultor_a")).json()
    clima = next(s for s in sistemas if s["code"] == "CLIMA")
    ascensores = next(s for s in sistemas if s["code"] == "ASC")

    alta(cliente, cab, proyecto, activo, tag="C1", technical_system_id=clima["id"])
    alta(cliente, cab, proyecto, activo, tag="A1", technical_system_id=ascensores["id"])

    r = cliente.get(
        f"{RUTA}/projects/{proyecto}/equipment?asset_id={activo}&technical_system_id={clima['id']}",
        headers=cab("consultor_a"),
    )
    assert [e["tag"] for e in r.json()] == ["C1"]
    assert r.json()[0]["technical_system_name"] == "Climatización"


# ─────────────────────────────────────────────────────────────────────────────
#  Correcciones y errores de usuario
# ─────────────────────────────────────────────────────────────────────────────


def test_se_corrige_un_campo_sin_reenviar_la_ficha(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    equipo = alta(
        cliente,
        cab,
        proyecto,
        activo,
        manufacturer="Mal Tecleado",
        install_year=2010,
        expected_life_years=20,
    ).json()
    r = cliente.patch(
        f"{RUTA}/equipment/{equipo['id']}",
        headers=cab("consultor_a"),
        json={"manufacturer": "Fabricante Ficticio"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["manufacturer"] == "Fabricante Ficticio"
    # Y lo que no se tocó sigue igual, con su vida recalculada.
    assert r.json()["end_of_life_year"] == 2030


def test_un_estado_inventado_se_rechaza_diciendo_los_validos(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    r = alta(cliente, cab, proyecto, activo, condition="REGULINCHI")
    assert r.status_code == 422
    assert "BUENO" in r.json()["detail"]


def test_no_se_cuelga_un_equipo_de_un_activo_de_otro_encargo(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    activo: str,
    datos_base: dict[str, uuid.UUID],
    motor_admin: Engine,
) -> None:
    """Sin esta comprobación el inventario dejaría de cuadrar por activo y nada
    avisaría: el `project_id` de la ruta y el del activo divergirían."""
    with motor_admin.begin() as conn:
        otro_proyecto = conn.execute(
            text(
                "INSERT INTO project (organization_id, client_id, internal_code, name) "
                "VALUES (:o, :c, :cod, 'Otro encargo') RETURNING id"
            ),
            {
                "o": str(datos_base["org_a"]),
                "c": str(datos_base["cliente_a"]),
                "cod": f"OTR-{uuid.uuid4().hex[:6]}",
            },
        ).scalar_one()
    r = cliente.post(
        f"{RUTA}/projects/{otro_proyecto}/equipment",
        headers=cab("consultor_a"),
        json={"asset_id": activo, "equipment_type": "Enfriadora"},
    )
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
#  Aislamiento
# ─────────────────────────────────────────────────────────────────────────────


def test_otra_organizacion_no_ve_el_inventario(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    equipo = alta(cliente, cab, proyecto, activo, tag="SECRETO").json()
    assert (
        cliente.get(f"{RUTA}/equipment/{equipo['id']}", headers=cab("admin_b")).status_code == 404
    )
    r = cliente.get(f"{RUTA}/projects/{proyecto}/equipment", headers=cab("admin_b"))
    assert r.json() == []

"""`[REQ]` La memoria técnica del activo: sus datos y sus zonas.

La memoria técnica es el documento que entrega la propiedad con todos los datos
del edificio. De ella salen dos cosas que antes no tenían dónde vivir:

* **Diez campos** que la ficha del activo no recogía. Tres se parecen a otros
  que ya existían y **no son lo mismo** —huella frente a construida, útil
  frente a alquilable, altura del edificio frente a la del almacén—, y las
  pruebas de aquí abajo comprueban justo eso: que son columnas distintas y que
  guardar una no pisa la otra.
* **La clasificación de zonas en privadas y comunes**, que el cliente pidió
  **por activo** y no por catálogo: «Aseos» es zona común en un edificio de
  oficinas multiinquilino y privada en una nave de un solo ocupante.
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
def tipologias(motor_admin: Engine) -> dict[str, str]:
    with motor_admin.begin() as conn:
        filas = conn.execute(
            text("SELECT code, id FROM asset_typology WHERE code IN ('INDUSTRIAL', 'OFICINAS')")
        ).all()
    return {code: str(id_) for code, id_ in filas}


@pytest.fixture
def proyecto(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo con memoria') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"MEM-{uuid.uuid4().hex[:6]}",
                },
            ).scalar_one()
        )


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]) -> str:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave con memoria", "typology_id": tipologias["INDUSTRIAL"]},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def zonas_de(cliente: TestClient, cab: Any, activo: str, code: str) -> str:
    """El id de una zona permitida para la tipología del activo."""
    permitidas = cliente.get(
        f"{RUTA}/assets/{activo}/allowed-zones", headers=cab("consultor_a")
    ).json()
    return str(next(z["id"] for z in permitidas if z["code"] == code))


# ─────────────────────────────────────────────────────────────────────────────
#  Los diez campos de la memoria
# ─────────────────────────────────────────────────────────────────────────────


def test_el_alta_acepta_los_datos_de_la_memoria(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={
            "name": "Nave del ejemplo",
            "typology_id": tipologias["INDUSTRIAL"],
            "cadastral_reference": "0000000XX0000X0000XX",
            "developer": "Promotora Ficticia S.L.",
            "project_date": "2003-06-30",
            "secondary_use": "Oficinas",
            "occupied_area_sqm": "9800.00",
            "urbanised_area_sqm": "14700.00",
            "usable_area_sqm": "17550.00",
            "max_height_m": "12.40",
            "loading_docks": 18,
            "parking_spaces": 240,
        },
    )
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["cadastral_reference"] == "0000000XX0000X0000XX"
    assert a["developer"] == "Promotora Ficticia S.L."
    assert a["project_date"] == "2003-06-30"
    assert a["loading_docks"] == 18
    assert a["parking_spaces"] == 240


def test_la_huella_la_util_y_la_altura_maxima_son_columnas_propias(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """`[REQ]` Es el error que este cambio existe para evitar.

    La huella no es la construida total —un edificio de cuatro alturas ocupa la
    cuarta parte—, la útil no es la alquilable —ésta lleva repercusión de zonas
    comunes— y la altura máxima no es la del almacén. Guardar una no puede
    tocar la otra.
    """
    r = cliente.patch(
        f"{RUTA}/assets/{activo}",
        headers={**cab("consultor_a"), "If-Match": "1"},
        json={
            "total_built_sqm": "18200.00",
            "occupied_area_sqm": "4550.00",
            "lettable_area_sqm": "17000.00",
            "usable_area_sqm": "16100.00",
            "warehouse_height_m": "11.50",
            "max_height_m": "13.80",
        },
    )
    assert r.status_code == 200, r.text
    a = r.json()
    assert Decimal(a["total_built_sqm"]) == Decimal("18200.00")
    assert Decimal(a["occupied_area_sqm"]) == Decimal("4550.00")
    assert Decimal(a["lettable_area_sqm"]) == Decimal("17000.00")
    assert Decimal(a["usable_area_sqm"]) == Decimal("16100.00")
    assert Decimal(a["warehouse_height_m"]) == Decimal("11.50")
    assert Decimal(a["max_height_m"]) == Decimal("13.80")


def test_un_campo_mal_escrito_se_rechaza_en_vez_de_perderse(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    """`extra="forbid"`: «superficie_util» no es un campo, y decirlo es mejor
    que guardar una ficha a la que le falta un dato que alguien creyó meter."""
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={
            "name": "Con errata",
            "typology_id": tipologias["INDUSTRIAL"],
            "superficie_util": "1000",
        },
    )
    assert r.status_code == 422


def test_los_conteos_no_admiten_negativos(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={
            "name": "Imposible",
            "typology_id": tipologias["INDUSTRIAL"],
            "loading_docks": -1,
        },
    )
    assert r.status_code == 422


def test_la_memoria_nace_sin_validar(cliente: TestClient, cab: Any, activo: str) -> None:
    """`[REQ]` El testigo de la revisión humana empieza vacío.

    Mientras lo esté, la ficha enseña los datos como **sin validar**: uno
    extraído de un documento por una máquina no puede parecerse a uno tecleado
    por un técnico.
    """
    a = cliente.get(f"{RUTA}/assets/{activo}", headers=cab("consultor_a")).json()
    assert a["memoria_validada_at"] is None
    assert a["memoria_validada_por"] is None


def test_la_fecha_de_validacion_no_va_sin_su_persona(motor_admin: Engine, activo: str) -> None:
    """La restricción vive en la base, no solo en la API: una fecha sin persona
    no vale como testigo, y por cualquier vía que entre tiene que fallar."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        with motor_admin.begin() as conn:
            conn.execute(
                text("UPDATE asset SET memoria_validada_at = now() WHERE id = :i"),
                {"i": activo},
            )


# ─────────────────────────────────────────────────────────────────────────────
#  Zonas privadas y comunes
# ─────────────────────────────────────────────────────────────────────────────


def test_se_declaran_las_zonas_del_edificio_y_su_naturaleza(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    cubierta = zonas_de(cliente, cab, activo, "CUBIERTA")
    aseos = zonas_de(cliente, cab, activo, "ASEOS")

    r = cliente.put(
        f"{RUTA}/assets/{activo}/zones",
        headers=cab("consultor_a"),
        json=[
            {"zone_id": cubierta, "tenure": "COMUN", "area_sqm": "9800.00"},
            {"zone_id": aseos, "tenure": "PRIVADA"},
        ],
    )

    assert r.status_code == 200, r.text
    por_codigo = {z["zone_code"]: z for z in r.json()}
    assert por_codigo["CUBIERTA"]["tenure"] == "COMUN"
    assert Decimal(por_codigo["CUBIERTA"]["area_sqm"]) == Decimal("9800.00")
    assert por_codigo["ASEOS"]["tenure"] == "PRIVADA"


def test_la_misma_zona_puede_ser_privada_en_un_edificio_y_comun_en_otro(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    tipologias: dict[str, str],
    activo: str,
) -> None:
    """`[REQ]` Es la razón de que la marca viva en el activo y no en el catálogo.

    Si estuviera en `zone`, esta prueba sería imposible de escribir: habría un
    único valor para toda la organización.
    """
    otro = str(
        cliente.post(
            f"{RUTA}/projects/{proyecto}/assets",
            headers=cab("consultor_a"),
            json={"name": "Edificio de oficinas", "typology_id": tipologias["OFICINAS"]},
        ).json()["id"]
    )
    aseos_nave = zonas_de(cliente, cab, activo, "ASEOS")
    aseos_oficinas = zonas_de(cliente, cab, otro, "ASEOS")
    assert aseos_nave == aseos_oficinas, "es la MISMA zona del catálogo"

    cliente.put(
        f"{RUTA}/assets/{activo}/zones",
        headers=cab("consultor_a"),
        json=[{"zone_id": aseos_nave, "tenure": "PRIVADA"}],
    )
    cliente.put(
        f"{RUTA}/assets/{otro}/zones",
        headers=cab("consultor_a"),
        json=[{"zone_id": aseos_oficinas, "tenure": "COMUN"}],
    )

    en_la_nave = cliente.get(f"{RUTA}/assets/{activo}/zones", headers=cab("consultor_a")).json()
    en_oficinas = cliente.get(f"{RUTA}/assets/{otro}/zones", headers=cab("consultor_a")).json()
    assert en_la_nave[0]["tenure"] == "PRIVADA"
    assert en_oficinas[0]["tenure"] == "COMUN"


def test_volver_a_enviar_la_lista_sustituye_y_no_duplica(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """`PUT` y no `POST` por zona: la memoria declara las zonas de una vez, y
    releerla dos veces no puede dejar el edificio con las zonas repetidas."""
    cubierta = zonas_de(cliente, cab, activo, "CUBIERTA")
    aseos = zonas_de(cliente, cab, activo, "ASEOS")

    cliente.put(
        f"{RUTA}/assets/{activo}/zones",
        headers=cab("consultor_a"),
        json=[
            {"zone_id": cubierta, "tenure": "COMUN"},
            {"zone_id": aseos, "tenure": "PRIVADA"},
        ],
    )
    segunda = cliente.put(
        f"{RUTA}/assets/{activo}/zones",
        headers=cab("consultor_a"),
        json=[{"zone_id": cubierta, "tenure": "PRIVADA"}],
    )

    assert segunda.status_code == 200
    assert [z["zone_code"] for z in segunda.json()] == ["CUBIERTA"]
    assert segunda.json()[0]["tenure"] == "PRIVADA", "la segunda lectura manda"


def test_la_misma_zona_dos_veces_en_la_misma_lista_se_rechaza(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """Y con un mensaje, no con un choque de clave única: quien manda la lista
    tiene que saber que la contradijo él, no que la base se quejó."""
    cubierta = zonas_de(cliente, cab, activo, "CUBIERTA")
    r = cliente.put(
        f"{RUTA}/assets/{activo}/zones",
        headers=cab("consultor_a"),
        json=[
            {"zone_id": cubierta, "tenure": "COMUN"},
            {"zone_id": cubierta, "tenure": "PRIVADA"},
        ],
    )
    assert r.status_code == 422
    assert "dos veces" in r.json()["detail"]


def test_una_zona_que_la_tipologia_no_admite_se_rechaza(
    cliente: TestClient, cab: Any, activo: str, motor_admin: Engine
) -> None:
    """`[REQ]` La plantilla del cliente ofrece una lista de zonas distinta por
    tipo de edificio. Una zona fuera de esa lista deja la celda vacía en el
    Excel sin que nadie se entere: mejor un 422 aquí."""
    with motor_admin.begin() as conn:
        ajena = conn.execute(
            text(
                "SELECT z.id FROM zone z WHERE z.code = 'HABITACIONES' "
                "AND NOT EXISTS (SELECT 1 FROM zone_typology zt "
                "  JOIN asset a ON a.typology_id = zt.typology_id "
                "  WHERE zt.zone_id = z.id AND a.id = :a)"
            ),
            {"a": activo},
        ).scalar_one()

    r = cliente.put(
        f"{RUTA}/assets/{activo}/zones",
        headers=cab("consultor_a"),
        json=[{"zone_id": str(ajena), "tenure": "COMUN"}],
    )
    assert r.status_code == 422
    assert "no admite" in r.json()["detail"]


def test_otra_organizacion_no_ve_las_zonas_ajenas(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    cubierta = zonas_de(cliente, cab, activo, "CUBIERTA")
    cliente.put(
        f"{RUTA}/assets/{activo}/zones",
        headers=cab("consultor_a"),
        json=[{"zone_id": cubierta, "tenure": "COMUN"}],
    )
    r = cliente.get(f"{RUTA}/assets/{activo}/zones", headers=cab("admin_b"))
    assert r.status_code == 404, "el activo entero es invisible para la otra organización"

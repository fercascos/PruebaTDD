"""`[REQ]` La memoria técnica como origen del CAPEX, y el botón que la acepta.

Dos cosas se comprueban aquí, y las dos son promesas hechas al cliente:

* **Guardar la memoria no toca el activo.** La propuesta se queda en la memoria
  hasta que alguien pulsa validar. Es lo que hace que el botón signifique algo:
  sin esto, un dato leído por una máquina y no revisado circularía por el CAPEX
  y por el informe.
* **Generar el esqueleto no pisa trabajo hecho.** Regenerar tras ampliar la
  memoria es lo normal, y que eso borrara importes ya tecleados sería
  indefendible.
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
    """Los capítulos y elementos reales del catálogo, no inventados."""
    with motor_admin.begin() as conn:
        tipologia = conn.execute(
            text("SELECT id FROM asset_typology WHERE code = 'INDUSTRIAL'")
        ).scalar_one()
        capitulos = {
            code: str(id_)
            for code, id_ in conn.execute(
                text(
                    "SELECT code, id FROM capex_code WHERE level = 2 "
                    "AND code IN ('HC.H02', 'HC.H08', 'HC.H09')"
                )
            ).all()
        }
        elemento = conn.execute(
            text("SELECT id FROM capex_code WHERE code = 'HC.H08.01'")
        ).scalar_one()
    return {
        "tipologia": str(tipologia),
        "capitulos": capitulos,
        "elemento": str(elemento),
    }


@pytest.fixture
def proyecto(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo con esqueleto') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"ESQ-{uuid.uuid4().hex[:6]}",
                },
            ).scalar_one()
        )


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any]) -> str:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave con memoria", "typology_id": catalogo["tipologia"]},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def memoria_de_ejemplo(catalogo: dict[str, Any]) -> dict[str, Any]:
    """Una memoria pequeña pero con los tres casos que importan.

    Un capítulo con dos objetos, uno con un objeto que **no está en el
    catálogo**, y uno **sin objetos**.
    """
    return {
        "origen": "MANUAL",
        "es_simulada": False,
        "propuesta": {
            "cadastral_reference": "0000000XX0000X0000XX",
            "developer": "Promotora Ficticia S.L.",
            "year_built": 2004,
            "footprint_area_sqm": "9800.00",
            "loading_docks": 18,
        },
        "categorias": [
            {
                "capex_code_id": catalogo["capitulos"]["HC.H08"],
                "objetos": [
                    {
                        "capex_code_id": catalogo["elemento"],
                        "nombre": "Enfriadora de la cubierta",
                        "cantidad": "2",
                        "unidad": "ud",
                    },
                    {"nombre": "Climatizadora de oficinas"},
                ],
            },
            {
                "capex_code_id": catalogo["capitulos"]["HC.H02"],
                "objetos": [{"nombre": "Lámina impermeabilizante de la nave"}],
            },
            {"capex_code_id": catalogo["capitulos"]["HC.H09"], "objetos": []},
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
#  La memoria se guarda, y NO toca el activo
# ─────────────────────────────────────────────────────────────────────────────


def test_la_memoria_se_guarda_con_sus_categorias_y_objetos(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    r = cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json=memoria_de_ejemplo(catalogo),
    )

    assert r.status_code == 200, r.text
    m = r.json()
    assert m["status"] == "EXTRAIDA"
    assert [c["capex_code"] for c in m["categorias"]] == ["HC.H08", "HC.H02", "HC.H09"]
    hvac = m["categorias"][0]
    assert [o["nombre"] for o in hvac["objetos"]] == [
        "Enfriadora de la cubierta",
        "Climatizadora de oficinas",
    ]
    # Un objeto que el catálogo no tiene se conserva igual: perderlo sería tirar
    # lo que el gestor necesita para acordarse de revisarlo.
    assert hvac["objetos"][1]["capex_code_id"] is None


def test_guardar_la_memoria_no_toca_el_activo(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """`[REQ]` Es la mitad que hace que el botón de validar signifique algo."""
    cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json=memoria_de_ejemplo(catalogo),
    )

    a = cliente.get(f"{RUTA}/assets/{activo}", headers=cab("consultor_a")).json()
    assert a["cadastral_reference"] is None, "la propuesta no puede haberse aplicado sola"
    assert a["developer"] is None
    assert a["memoria_validada_at"] is None


def test_una_categoria_tiene_que_ser_un_capitulo(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """Un elemento colado como categoría produce un esqueleto con la jerarquía
    del revés, y eso se ve al final, en el Excel del cliente."""
    r = cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json={"categorias": [{"capex_code_id": catalogo["elemento"], "objetos": []}]},
    )
    assert r.status_code == 422
    assert "nivel 2" in r.json()["detail"]


def test_la_memoria_no_puede_proponer_campos_que_no_son_del_edificio(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """`[REQ]` Sin este cerco, una extracción podría cambiar el nombre del activo
    o su tipología, y el botón de validar estaría aceptando mucho más de lo que
    la persona cree."""
    r = cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json={"propuesta": {"name": "Otro nombre", "typology_id": str(uuid.uuid4())}},
    )
    assert r.status_code == 422
    assert "no puede proponer" in r.json()["detail"]


def test_volver_a_leer_la_memoria_sustituye_y_deshace_la_validacion(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """Lo que se aceptó ya no es lo que hay: dejar el testigo puesto sobre un
    contenido nuevo sería exactamente la mentira que el testigo evita."""
    cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json=memoria_de_ejemplo(catalogo),
    )
    cliente.post(
        f"{RUTA}/assets/{activo}/memoria/validar",
        headers=cab("consultor_a"),
        json={"confirmar": True},
    )

    segunda = cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json={"categorias": [{"capex_code_id": catalogo["capitulos"]["HC.H02"], "objetos": []}]},
    )

    assert segunda.status_code == 200
    m = segunda.json()
    assert m["validada_at"] is None
    assert m["status"] == "EXTRAIDA"
    assert len(m["categorias"]) == 1, "la segunda lectura sustituye, no acumula"


# ─────────────────────────────────────────────────────────────────────────────
#  El botón
# ─────────────────────────────────────────────────────────────────────────────


def test_validar_vuelca_la_propuesta_al_activo_y_firma_quien_fue(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any], datos_base: Any
) -> None:
    cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json=memoria_de_ejemplo(catalogo),
    )

    r = cliente.post(
        f"{RUTA}/assets/{activo}/memoria/validar",
        headers=cab("consultor_a"),
        json={"confirmar": True},
    )

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "VALIDADA"
    a = cliente.get(f"{RUTA}/assets/{activo}", headers=cab("consultor_a")).json()
    assert a["cadastral_reference"] == "0000000XX0000X0000XX"
    assert a["developer"] == "Promotora Ficticia S.L."
    assert a["year_built"] == 2004
    assert Decimal(a["footprint_area_sqm"]) == Decimal("9800.00")
    assert a["loading_docks"] == 18
    # Los dos testigos: quien mira la ficha del edificio no tiene por qué saber
    # que hay una memoria detrás.
    assert a["memoria_validada_at"] is not None
    assert a["memoria_validada_por"] == str(datos_base["consultor_a"])


def test_validar_no_borra_lo_que_la_memoria_no_menciona(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """`[REQ]` Una memoria que no menciona la superficie de oficinas no es una
    memoria que diga que no hay."""
    cliente.patch(
        f"{RUTA}/assets/{activo}",
        headers={**cab("consultor_a"), "If-Match": "1"},
        json={"office_area_sqm": "1800.00"},
    )
    cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json={"propuesta": {"year_built": 1998}},
    )

    cliente.post(
        f"{RUTA}/assets/{activo}/memoria/validar",
        headers=cab("consultor_a"),
        json={"confirmar": True},
    )

    a = cliente.get(f"{RUTA}/assets/{activo}", headers=cab("consultor_a")).json()
    assert a["year_built"] == 1998
    assert Decimal(a["office_area_sqm"]) == Decimal("1800.00"), "no se ha borrado"


def test_validar_sin_confirmar_se_rechaza(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json=memoria_de_ejemplo(catalogo),
    )
    r = cliente.post(
        f"{RUTA}/assets/{activo}/memoria/validar",
        headers=cab("consultor_a"),
        json={"confirmar": False},
    )
    assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
#  El esqueleto del CAPEX
# ─────────────────────────────────────────────────────────────────────────────


def test_el_esqueleto_crea_una_fila_por_objeto(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, catalogo: dict[str, Any]
) -> None:
    cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json=memoria_de_ejemplo(catalogo),
    )

    r = cliente.post(f"{RUTA}/assets/{activo}/memoria/generar-capex", headers=cab("consultor_a"))

    assert r.status_code == 201, r.text
    resumen = r.json()
    # Tres objetos enumerados + la fila del capítulo que no enumera ninguno.
    assert resumen["creadas"] == 4
    assert resumen["categorias"] == 3
    assert any("no enumera objetos" in a for a in resumen["avisos"])

    hallazgos = cliente.get(
        f"{RUTA}/projects/{proyecto}/findings", headers=cab("consultor_a")
    ).json()
    titulos = sorted(h["title"] for h in hallazgos)
    assert titulos == sorted(
        [
            "Enfriadora de la cubierta",
            "Climatizadora de oficinas",
            "Lámina impermeabilizante de la nave",
            "Electricidad",
        ]
    )


def test_las_filas_nacen_en_borrador_y_sin_importe(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, catalogo: dict[str, Any]
) -> None:
    """`[LIM]` Lo decidió el cliente: BORRADOR normal, así que cuentan en los
    totales y salen en el Excel de trabajo con importe cero."""
    cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json=memoria_de_ejemplo(catalogo),
    )
    cliente.post(f"{RUTA}/assets/{activo}/memoria/generar-capex", headers=cab("consultor_a"))

    hallazgos = cliente.get(
        f"{RUTA}/projects/{proyecto}/findings", headers=cab("consultor_a")
    ).json()
    assert {h["status"] for h in hallazgos} == {"BORRADOR"}
    assert all(h["capex_lines"] == [] for h in hallazgos)


def test_regenerar_no_duplica_ni_pisa_lo_ya_rellenado(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, catalogo: dict[str, Any]
) -> None:
    """`[REQ]` Ampliar la memoria y regenerar es lo normal. Que eso borrara
    importes ya tecleados sería indefendible."""
    cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json=memoria_de_ejemplo(catalogo),
    )
    cliente.post(f"{RUTA}/assets/{activo}/memoria/generar-capex", headers=cab("consultor_a"))

    # El gestor completa una fila con su importe.
    hallazgos = cliente.get(
        f"{RUTA}/projects/{proyecto}/findings", headers=cab("consultor_a")
    ).json()
    enfriadora = next(h for h in hallazgos if h["title"] == "Enfriadora de la cubierta")
    puesto = cliente.post(
        f"{RUTA}/findings/{enfriadora['id']}/capex-items",
        headers=cab("consultor_a"),
        json={"time_horizon_code": "CORTO", "amount": "48500.00"},
    )
    assert puesto.status_code == 201, puesto.text

    # Llega una memoria ampliada y se regenera.
    ampliada = memoria_de_ejemplo(catalogo)
    ampliada["categorias"][0]["objetos"].append({"nombre": "Conductos de impulsión"})
    cliente.put(f"{RUTA}/assets/{activo}/memoria", headers=cab("consultor_a"), json=ampliada)
    segunda = cliente.post(
        f"{RUTA}/assets/{activo}/memoria/generar-capex", headers=cab("consultor_a")
    )

    assert segunda.status_code == 201
    assert segunda.json()["creadas"] == 1, "solo la nueva"
    assert segunda.json()["omitidas"] == 4

    hallazgos = cliente.get(
        f"{RUTA}/projects/{proyecto}/findings", headers=cab("consultor_a")
    ).json()
    assert len(hallazgos) == 5
    enfriadora = next(h for h in hallazgos if h["title"] == "Enfriadora de la cubierta")
    assert Decimal(enfriadora["total_amount"]) == Decimal("48500.00"), "no se ha pisado"


def test_el_objeto_sin_codigo_hereda_el_de_su_capitulo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, catalogo: dict[str, Any]
) -> None:
    """Un objeto que el catálogo no tiene cae igualmente en su capítulo: es lo
    más concreto que se sabe de él, y sin código no podría existir la fila."""
    cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json=memoria_de_ejemplo(catalogo),
    )
    cliente.post(f"{RUTA}/assets/{activo}/memoria/generar-capex", headers=cab("consultor_a"))

    hallazgos = cliente.get(
        f"{RUTA}/projects/{proyecto}/findings", headers=cab("consultor_a")
    ).json()
    sin_codigo = next(h for h in hallazgos if h["title"] == "Climatizadora de oficinas")
    assert sin_codigo["capex_code_id"] == catalogo["capitulos"]["HC.H08"]


def test_un_activo_sin_memoria_no_genera_nada(cliente: TestClient, cab: Any, activo: str) -> None:
    r = cliente.post(f"{RUTA}/assets/{activo}/memoria/generar-capex", headers=cab("consultor_a"))
    assert r.status_code == 404
    assert "memoria" in r.json()["detail"]


def test_otra_organizacion_no_ve_la_memoria_ajena(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json=memoria_de_ejemplo(catalogo),
    )
    r = cliente.get(f"{RUTA}/assets/{activo}/memoria", headers=cab("admin_b"))
    assert r.status_code == 404

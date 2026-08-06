"""Activos y equipo del proyecto.

Lo que se comprueba aquí y no en otro sitio: que **reclasificar un activo no
destruye datos** (P-02), que la tipología manda sobre las zonas disponibles, y
que el rol efectivo de una persona es el máximo entre su rol de organización y
el que tenga en el proyecto.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tdd.assets.router import rol_efectivo

pytestmark = pytest.mark.db

RUTA = "/api/v1"


@pytest.fixture(scope="module")
def proyecto(datos_base: dict[str, uuid.UUID]) -> str:
    return str(datos_base["proyecto_a"])


@pytest.fixture
def tipologias(motor_admin: Engine) -> dict[str, str]:
    with motor_admin.begin() as conn:
        filas = conn.execute(text("SELECT code, id FROM asset_typology")).all()
    return {f.code: str(f.id) for f in filas}


def crear_activo(
    cliente: TestClient, cab: Any, proyecto: str, tipologia: str, **campos: Any
) -> Any:
    cuerpo = {"name": "Nave Logística Norte", "typology_id": tipologia, **campos}
    return cliente.post(
        f"{RUTA}/projects/{proyecto}/assets", headers=cab("consultor_a"), json=cuerpo
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Alta y ficha
# ─────────────────────────────────────────────────────────────────────────────


def test_se_da_de_alta_un_activo_con_la_ficha_completa(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    r = crear_activo(
        cliente,
        cab,
        proyecto,
        next(iter(tipologias.values())),
        asset_code="NAVE-A",
        city="Getafe",
        plot_area_sqm="18500.00",
        total_built_sqm="12400.00",
        warehouse_area_sqm="11000.00",
        office_area_sqm="1400.00",
        warehouse_height_m="11.50",
        year_built=2008,
        year_last_refurb=2019,
    )
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["asset_code"] == "NAVE-A"
    assert cuerpo["warehouse_height_m"] == "11.50"


def test_reclasificar_no_destruye_los_datos_de_la_tipologia_anterior(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    """`[REQ]` P-02 · La ficha es la UNIÓN de §3.1.3 y §3.3.1. Con una tabla
    por tipología, cambiar de nave a oficinas y volver atrás habría perdido la
    altura de almacén; aquí sigue ahí."""
    codigos = list(tipologias.values())
    activo = crear_activo(
        cliente, cab, proyecto, codigos[0], warehouse_height_m="11.50", warehouse_area_sqm="9000.00"
    ).json()

    r = cliente.patch(
        f"{RUTA}/assets/{activo['id']}",
        headers=cab("consultor_a"),
        json={"typology_id": codigos[1]},
    )
    assert r.status_code == 200
    assert r.json()["typology_id"] == codigos[1]
    assert r.json()["warehouse_height_m"] == "11.50", "el dato anterior no se borra"


def test_un_campo_desconocido_se_rechaza_en_vez_de_perderse(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    """Un `superficie_almacen` mal escrito que la API ignorase en silencio
    produciría una ficha incompleta que nadie detecta hasta el informe."""
    r = crear_activo(
        cliente, cab, proyecto, next(iter(tipologias.values())), superficie_almacen=900
    )
    assert r.status_code == 422


def test_la_reforma_no_puede_ser_anterior_a_la_construccion(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    """El error de tecleo más habitual de la ficha, y falsea la vida útil que
    se estima después."""
    r = crear_activo(
        cliente,
        cab,
        proyecto,
        next(iter(tipologias.values())),
        year_built=2010,
        year_last_refurb=2004,
    )
    assert r.status_code == 422


def test_las_coordenadas_van_completas(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    r = crear_activo(cliente, cab, proyecto, next(iter(tipologias.values())), latitude="40.416775")
    assert r.status_code == 422


def test_el_almacen_no_puede_ser_mayor_que_el_edificio(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    r = crear_activo(
        cliente,
        cab,
        proyecto,
        next(iter(tipologias.values())),
        total_built_sqm="1000.00",
        warehouse_area_sqm="2000.00",
    )
    assert r.status_code == 422


def test_la_base_de_datos_tambien_rechaza_la_incoherencia(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str], motor_admin: Engine
) -> None:
    """No es duplicación: el `CHECK` impide que entre por cualquier vía, y el
    `422` de la API dice qué campo revisar."""
    activo = crear_activo(cliente, cab, proyecto, next(iter(tipologias.values()))).json()
    with motor_admin.begin() as conn, pytest.raises(Exception, match="asset_reforma_posterior"):
        conn.execute(
            text("UPDATE asset SET year_built = 2010, year_last_refurb = 2004 WHERE id = :i"),
            {"i": activo["id"]},
        )


def test_el_codigo_de_activo_no_se_repite_en_el_proyecto(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    codigo = f"REP-{uuid.uuid4().hex[:6]}"
    tip = next(iter(tipologias.values()))
    assert crear_activo(cliente, cab, proyecto, tip, asset_code=codigo).status_code == 201

    # 409 con el campo, no la excepción cruda: repetir el código del cliente es
    # un error de quien rellena la ficha, y antes salía un 500 que no lo decía.
    repetido = crear_activo(cliente, cab, proyecto, tip, asset_code=codigo)
    assert repetido.status_code == 409, repetido.text
    assert "código del cliente" in repetido.json()["detail"]


def test_el_activo_se_borra_de_forma_logica(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str], motor_admin: Engine
) -> None:
    activo = crear_activo(cliente, cab, proyecto, next(iter(tipologias.values()))).json()
    assert (
        cliente.delete(f"{RUTA}/assets/{activo['id']}", headers=cab("consultor_a")).status_code
        == 204
    )
    assert (
        cliente.get(f"{RUTA}/assets/{activo['id']}", headers=cab("consultor_a")).status_code == 404
    )

    with motor_admin.begin() as conn:
        sigue = conn.execute(
            text("SELECT deleted_at FROM asset WHERE id = :i"), {"i": activo["id"]}
        ).scalar_one()
    assert sigue is not None, "la fila sigue: los hallazgos ya redactados la referencian"


def test_otra_organizacion_no_ve_el_activo(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    activo = crear_activo(cliente, cab, proyecto, next(iter(tipologias.values()))).json()
    assert cliente.get(f"{RUTA}/assets/{activo['id']}", headers=cab("admin_b")).status_code == 404


def test_el_listado_busca_por_nombre_codigo_y_ciudad(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    marca = uuid.uuid4().hex[:8]
    crear_activo(cliente, cab, proyecto, next(iter(tipologias.values())), city=f"Ciudad{marca}")
    r = cliente.get(f"{RUTA}/projects/{proyecto}/assets?q={marca}", headers=cab("consultor_a"))
    assert r.status_code == 200
    assert len(r.json()) == 1


# ─────────────────────────────────────────────────────────────────────────────
#  Zonas por tipología
# ─────────────────────────────────────────────────────────────────────────────


def test_las_zonas_disponibles_dependen_de_la_tipologia(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    """`[REQ]` No es un adorno del catálogo: el alta de hallazgo lo comprueba, y
    ofrecer una zona que luego se rechaza es la forma más rápida de que alguien
    deje de fiarse de los desplegables."""
    por_tipologia = {}
    for codigo, tid in tipologias.items():
        activo = crear_activo(cliente, cab, proyecto, tid).json()
        r = cliente.get(f"{RUTA}/assets/{activo['id']}/allowed-zones", headers=cab("consultor_a"))
        assert r.status_code == 200
        assert r.json(), f"la tipología {codigo} no tiene ninguna zona"
        por_tipologia[codigo] = {z["code"] for z in r.json()}

    assert len(set(map(frozenset, por_tipologia.values()))) > 1, (
        "si todas las tipologías dieran las mismas zonas, la matriz no serviría de nada"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Foto principal
# ─────────────────────────────────────────────────────────────────────────────


def test_la_foto_principal_debe_ser_de_ese_activo(
    cliente: TestClient, cab: Any, proyecto: str, tipologias: dict[str, str]
) -> None:
    import io

    from tests.unit.test_imagenes import imagen

    tip = next(iter(tipologias.values()))
    a = crear_activo(cliente, cab, proyecto, tip).json()
    b = crear_activo(cliente, cab, proyecto, tip).json()

    foto = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab("consultor_a"),
        files={"file": ("p.jpg", io.BytesIO(imagen(color=(7, 77, 177))), "image/jpeg")},
        data={"asset_id": a["id"]},
    ).json()

    ok = cliente.put(
        f"{RUTA}/assets/{a['id']}/main-photo?photo_id={foto['id']}", headers=cab("consultor_a")
    )
    assert ok.status_code == 200
    assert ok.json()["main_photo_id"] == foto["id"]

    mal = cliente.put(
        f"{RUTA}/assets/{b['id']}/main-photo?photo_id={foto['id']}", headers=cab("consultor_a")
    )
    assert mal.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
#  Equipo
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def proyecto_limpio(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    """Un proyecto por prueba: el equipo tiene índices únicos y compartirlo
    haría que las pruebas dependieran del orden."""
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo de equipo') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"EQ-{uuid.uuid4().hex[:6]}",
                },
            ).scalar_one()
        )


def test_se_anade_gente_al_equipo(
    cliente: TestClient, cab: Any, proyecto_limpio: str, datos_base: dict[str, uuid.UUID]
) -> None:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto_limpio}/members",
        headers=cab("admin_a"),
        json={"user_id": str(datos_base["consultor_a"]), "role_code": "CONSULTOR"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["role_code"] == "CONSULTOR"


def test_solo_hay_un_director_y_nombrar_otro_le_cede_el_puesto(
    cliente: TestClient, cab: Any, proyecto_limpio: str, datos_base: dict[str, uuid.UUID]
) -> None:
    """Con dos directores, «el director decide» deja de ser una regla y pasa a
    ser una discusión. Nombrar a otro es una acción normal, así que se cede el
    puesto en vez de fallar."""
    for usuario in ("consultor_a", "consultor2_a"):
        r = cliente.post(
            f"{RUTA}/projects/{proyecto_limpio}/members",
            headers=cab("admin_a"),
            json={
                "user_id": str(datos_base[usuario]),
                "role_code": "DIRECTOR",
                "is_project_lead": True,
            },
        )
        assert r.status_code == 201, r.text

    equipo = cliente.get(
        f"{RUTA}/projects/{proyecto_limpio}/members", headers=cab("admin_a")
    ).json()
    directores = [m for m in equipo if m["is_project_lead"]]
    assert len(directores) == 1
    assert directores[0]["user_id"] == str(datos_base["consultor2_a"])


def test_dirigir_el_proyecto_exige_el_rol_director(
    cliente: TestClient, cab: Any, proyecto_limpio: str, datos_base: dict[str, uuid.UUID]
) -> None:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto_limpio}/members",
        headers=cab("admin_a"),
        json={
            "user_id": str(datos_base["lector_a"]),
            "role_code": "LECTOR",
            "is_project_lead": True,
        },
    )
    assert r.status_code == 422


def test_anadir_dos_veces_actualiza_el_rol_en_vez_de_duplicar(
    cliente: TestClient, cab: Any, proyecto_limpio: str, datos_base: dict[str, uuid.UUID]
) -> None:
    for rol in ("LECTOR", "REVISOR"):
        cliente.post(
            f"{RUTA}/projects/{proyecto_limpio}/members",
            headers=cab("admin_a"),
            json={"user_id": str(datos_base["lector_a"]), "role_code": rol},
        )
    equipo = cliente.get(
        f"{RUTA}/projects/{proyecto_limpio}/members", headers=cab("admin_a")
    ).json()
    assert len(equipo) == 1
    assert equipo[0]["role_code"] == "REVISOR"


def test_retirar_a_alguien_es_logico(
    cliente: TestClient,
    cab: Any,
    proyecto_limpio: str,
    datos_base: dict[str, uuid.UUID],
    motor_admin: Engine,
) -> None:
    """Lo que esa persona firmó sigue atribuido a ella."""
    miembro = cliente.post(
        f"{RUTA}/projects/{proyecto_limpio}/members",
        headers=cab("admin_a"),
        json={"user_id": str(datos_base["consultor_a"])},
    ).json()

    r = cliente.delete(
        f"{RUTA}/projects/{proyecto_limpio}/members/{miembro['id']}", headers=cab("admin_a")
    )
    assert r.status_code == 204
    assert (
        cliente.get(f"{RUTA}/projects/{proyecto_limpio}/members", headers=cab("admin_a")).json()
        == []
    )

    with motor_admin.begin() as conn:
        assert (
            conn.execute(
                text("SELECT removed_at FROM project_member WHERE id = :i"), {"i": miembro["id"]}
            ).scalar_one()
            is not None
        )


def test_se_puede_reincorporar_a_quien_se_retiro(
    cliente: TestClient, cab: Any, proyecto_limpio: str, datos_base: dict[str, uuid.UUID]
) -> None:
    """El índice único es parcial por `removed_at`, así que el histórico no
    bloquea la vuelta."""
    miembro = cliente.post(
        f"{RUTA}/projects/{proyecto_limpio}/members",
        headers=cab("admin_a"),
        json={"user_id": str(datos_base["consultor_a"])},
    ).json()
    cliente.delete(
        f"{RUTA}/projects/{proyecto_limpio}/members/{miembro['id']}", headers=cab("admin_a")
    )
    r = cliente.post(
        f"{RUTA}/projects/{proyecto_limpio}/members",
        headers=cab("admin_a"),
        json={"user_id": str(datos_base["consultor_a"])},
    )
    assert r.status_code == 201


# ── Rol efectivo (función pura) ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("org", "proyecto_", "esperado"),
    [
        ("LECTOR", "DIRECTOR", "DIRECTOR"),  # el proyecto sube
        ("ADMIN", "LECTOR", "ADMIN"),  # la organización no baja
        ("CONSULTOR", None, "CONSULTOR"),  # sin rol de proyecto
        ("DIRECTOR_PROYECTO", "LECTOR", "DIRECTOR"),  # equivalencia de nombres
        ("CONSULTOR", "REVISOR", "CONSULTOR"),
    ],
)
def test_el_rol_efectivo_es_el_maximo_de_los_dos(
    org: str, proyecto_: str | None, esperado: str
) -> None:
    """`[REQ]` §7 · Un LECTOR de la organización puede dirigir un proyecto
    concreto, y eso no le da poder sobre los demás proyectos."""
    assert rol_efectivo(org, proyecto_) == esperado


def test_el_listado_del_equipo_calcula_el_rol_efectivo(
    cliente: TestClient, cab: Any, proyecto_limpio: str, datos_base: dict[str, uuid.UUID]
) -> None:
    cliente.post(
        f"{RUTA}/projects/{proyecto_limpio}/members",
        headers=cab("admin_a"),
        json={
            "user_id": str(datos_base["lector_a"]),
            "role_code": "DIRECTOR",
            "is_project_lead": True,
        },
    )
    equipo = cliente.get(
        f"{RUTA}/projects/{proyecto_limpio}/members", headers=cab("admin_a")
    ).json()
    assert equipo[0]["effective_role"] == "DIRECTOR"


# ── Asignación por activo y especialidad ─────────────────────────────────────


def test_un_activo_tiene_varios_tecnicos_por_especialidad(
    cliente: TestClient,
    cab: Any,
    proyecto_limpio: str,
    datos_base: dict[str, uuid.UUID],
    tipologias: dict[str, str],
) -> None:
    """`[REQ]` Con una columna en `asset` no cabría ni una persona en varios
    activos ni un activo con varias especialidades."""
    activo = cliente.post(
        f"{RUTA}/projects/{proyecto_limpio}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave B", "typology_id": next(iter(tipologias.values()))},
    ).json()
    miembro = cliente.post(
        f"{RUTA}/projects/{proyecto_limpio}/members",
        headers=cab("admin_a"),
        json={"user_id": str(datos_base["consultor_a"])},
    ).json()

    for especialidad in ("Estructura", "Instalaciones"):
        r = cliente.post(
            f"{RUTA}/assets/{activo['id']}/assignments",
            headers=cab("admin_a"),
            json={"project_member_id": miembro["id"], "specialty": especialidad},
        )
        assert r.status_code == 201

    asignaciones = cliente.get(
        f"{RUTA}/assets/{activo['id']}/assignments", headers=cab("admin_a")
    ).json()
    assert {a["specialty"] for a in asignaciones} == {"Estructura", "Instalaciones"}


def test_asignar_a_alguien_de_fuera_del_equipo_se_rechaza(
    cliente: TestClient, cab: Any, proyecto_limpio: str, tipologias: dict[str, str]
) -> None:
    activo = cliente.post(
        f"{RUTA}/projects/{proyecto_limpio}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave C", "typology_id": next(iter(tipologias.values()))},
    ).json()
    r = cliente.post(
        f"{RUTA}/assets/{activo['id']}/assignments",
        headers=cab("admin_a"),
        json={"project_member_id": str(uuid.uuid4())},
    )
    assert r.status_code == 422

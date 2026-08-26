"""El árbol físico del activo `[REC]` §8.4.

Lo que se prueba aquí, en orden de importancia:

1. **Que `[Espacio]` se rellena de verdad.** Era el último token del renombrado
   en lote que se omitía siempre, porque este árbol no existía. Es la razón de
   ser de toda la tabla.
2. **Que mover una rama arrastra a sus descendientes.** El disparador recalcula
   la ruta del nodo movido, no la de sus hijos: dejarlo a medias produciría un
   árbol donde un hijo cuelga de dos sitios según se mire por `parent_id` o por
   `path`, y ese fallo no da la cara hasta mucho después.
3. **Que un ciclo se rechaza.** La clave ajena no lo impide: A puede ser padre
   de B y B de A sin violarla, y el árbol queda irrecorrible.
4. **Que un árbol no cruza edificios.** Tampoco lo impide la clave ajena.
"""

from __future__ import annotations

import io
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.unit.test_imagenes import imagen

pytestmark = pytest.mark.db

RUTA = "/api/v1"


@pytest.fixture
def proyecto(cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]) -> str:
    r = cliente.post(
        f"{RUTA}/projects",
        headers=cab("admin_a"),
        json={
            "client_id": str(datos_base["cliente_a"]),
            "internal_code": f"UBI-{uuid.uuid4().hex[:6]}",
            "name": "Encargo con árbol",
            "applicable_phases": [{"code": "VISITA"}],
        },
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine) -> str:
    with motor_admin.begin() as conn:
        tipologia = conn.execute(
            text("SELECT id FROM asset_typology ORDER BY sort_order LIMIT 1")
        ).scalar_one()
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave A", "typology_id": str(tipologia)},
    )
    return str(r.json()["id"])


def nodo(cliente: TestClient, cab: Any, activo: str, nombre: str, **extra: Any) -> dict[str, Any]:
    r = cliente.post(
        f"{RUTA}/assets/{activo}/locations",
        headers=cab("consultor_a"),
        json={"node_type": extra.pop("node_type", "ESPACIO"), "name": nombre, **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


# ─────────────────────────────────────────────────────────────────────────────
#  El árbol
# ─────────────────────────────────────────────────────────────────────────────


def test_un_arbol_de_tres_niveles_sale_en_orden_de_recorrido(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """Cada hijo justo detrás de su padre: la pantalla solo tiene que sangrar."""
    cubierta = nodo(cliente, cab, activo, "Cubierta", node_type="ZONA")
    planta = nodo(cliente, cab, activo, "Planta 1", node_type="PLANTA", parent_id=cubierta["id"])
    sala = nodo(cliente, cab, activo, "Sala de máquinas 2", parent_id=planta["id"])

    arbol = cliente.get(f"{RUTA}/assets/{activo}/locations", headers=cab("consultor_a")).json()
    assert [n["name"] for n in arbol] == ["Cubierta", "Planta 1", "Sala de máquinas 2"]
    assert [n["profundidad"] for n in arbol] == [0, 1, 2]
    assert arbol[2]["ruta_legible"] == "Cubierta › Planta 1 › Sala de máquinas 2"
    assert arbol[2]["id"] == sala["id"]


def test_dos_hermanos_con_el_mismo_nombre_se_rechazan(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """Serían indistinguibles en el desplegable y en el nombre del fichero.

    En minúsculas porque «Sala 1» y «sala 1» son el mismo sitio para quien los
    escribe.
    """
    nodo(cliente, cab, activo, "Sala 1")
    r = cliente.post(
        f"{RUTA}/assets/{activo}/locations",
        headers=cab("consultor_a"),
        json={"node_type": "ESPACIO", "name": "sala 1"},
    )
    assert r.status_code == 409


def test_el_mismo_nombre_bajo_otro_padre_si_vale(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """«Aseos» en la planta 1 y «Aseos» en la 2 son sitios distintos."""
    p1 = nodo(cliente, cab, activo, "Planta 1", node_type="PLANTA")
    p2 = nodo(cliente, cab, activo, "Planta 2", node_type="PLANTA")
    nodo(cliente, cab, activo, "Aseos", parent_id=p1["id"])
    nodo(cliente, cab, activo, "Aseos", parent_id=p2["id"])


def test_un_arbol_no_cruza_edificios(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, motor_admin: Engine
) -> None:
    """`[REQ]` La clave ajena no lo impide, y una rama de otro edificio dentro
    del árbol es indetectable después."""
    with motor_admin.begin() as conn:
        tipologia = conn.execute(text("SELECT id FROM asset_typology LIMIT 1")).scalar_one()
    otro = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave B", "typology_id": str(tipologia)},
    ).json()["id"]
    ajeno = nodo(cliente, cab, otro, "Cubierta de la B", node_type="ZONA")

    r = cliente.post(
        f"{RUTA}/assets/{activo}/locations",
        headers=cab("consultor_a"),
        json={"node_type": "ESPACIO", "name": "Intrusa", "parent_id": ajeno["id"]},
    )
    assert r.status_code == 422
    assert "otro activo" in r.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
#  Mover ramas
# ─────────────────────────────────────────────────────────────────────────────


def test_mover_una_rama_arrastra_a_sus_descendientes(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """`[REQ]` El disparador recalcula la ruta del nodo movido, **no la de sus
    hijos**. Si no se reescribieran aquí, un hijo colgaría de dos sitios según
    se mirara por `parent_id` o por `path`."""
    p1 = nodo(cliente, cab, activo, "Planta 1", node_type="PLANTA")
    p2 = nodo(cliente, cab, activo, "Planta 2", node_type="PLANTA")
    sala = nodo(cliente, cab, activo, "Sala técnica", parent_id=p1["id"])
    equipo = nodo(cliente, cab, activo, "Cuadro general", parent_id=sala["id"])

    r = cliente.patch(
        f"{RUTA}/locations/{sala['id']}",
        headers=cab("consultor_a"),
        json={"parent_id": p2["id"]},
    )
    assert r.status_code == 200
    assert r.json()["ruta_legible"] == "Planta 2 › Sala técnica"

    arbol = cliente.get(f"{RUTA}/assets/{activo}/locations", headers=cab("consultor_a")).json()
    nieto = next(n for n in arbol if n["id"] == equipo["id"])
    assert nieto["ruta_legible"] == "Planta 2 › Sala técnica › Cuadro general"
    assert nieto["profundidad"] == 2


def test_un_nodo_no_puede_meterse_dentro_de_si_mismo(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """`[REQ]` La clave ajena no lo impide y el árbol quedaría irrecorrible:
    la consulta de descendientes entraría en bucle."""
    padre = nodo(cliente, cab, activo, "Planta 1", node_type="PLANTA")
    hijo = nodo(cliente, cab, activo, "Sala", parent_id=padre["id"])

    r = cliente.patch(
        f"{RUTA}/locations/{padre['id']}",
        headers=cab("consultor_a"),
        json={"parent_id": hijo["id"]},
    )
    assert r.status_code == 422
    assert "dentro de sí mismo" in r.json()["detail"]


def test_un_nodo_no_puede_ser_su_propio_padre(cliente: TestClient, cab: Any, activo: str) -> None:
    n = nodo(cliente, cab, activo, "Sala")
    r = cliente.patch(
        f"{RUTA}/locations/{n['id']}", headers=cab("consultor_a"), json={"parent_id": n["id"]}
    )
    assert r.status_code == 422


def test_renombrar_no_cambia_la_ruta(cliente: TestClient, cab: Any, activo: str) -> None:
    """La etiqueta de `ltree` sale del `id`, no del nombre: por eso renombrar es
    barato y no toca a los descendientes."""
    padre = nodo(cliente, cab, activo, "Planta 1", node_type="PLANTA")
    hijo = nodo(cliente, cab, activo, "Sala", parent_id=padre["id"])
    cliente.patch(
        f"{RUTA}/locations/{padre['id']}",
        headers=cab("consultor_a"),
        json={"name": "Planta primera"},
    )
    arbol = cliente.get(f"{RUTA}/assets/{activo}/locations", headers=cab("consultor_a")).json()
    assert (
        next(n for n in arbol if n["id"] == hijo["id"])["ruta_legible"] == "Planta primera › Sala"
    )


def test_borrar_un_nodo_se_lleva_a_sus_descendientes(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """Dejar vivos los hijos produciría espacios sin planta que aparecen en el
    desplegable sin que se entienda de dónde salen."""
    planta = nodo(cliente, cab, activo, "Planta 1", node_type="PLANTA")
    nodo(cliente, cab, activo, "Sala", parent_id=planta["id"])

    assert (
        cliente.delete(f"{RUTA}/locations/{planta['id']}", headers=cab("consultor_a")).status_code
        == 204
    )
    arbol = cliente.get(f"{RUTA}/assets/{activo}/locations", headers=cab("consultor_a")).json()
    assert arbol == []


# ─────────────────────────────────────────────────────────────────────────────
#  Lo que da sentido a todo esto: el token `[Espacio]`
# ─────────────────────────────────────────────────────────────────────────────


def test_el_token_espacio_se_rellena_al_renombrar(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` §10 · Era el **último** token que se omitía siempre.

    Dependía de este árbol, que no existía, así que una plantilla que lo usara
    perdía el campo. Esta prueba es la razón de ser de toda la tabla.
    """
    sala = nodo(cliente, cab, activo, "Sala Máquinas 2")
    foto = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab("consultor_a"),
        files={"file": ("obra.jpg", io.BytesIO(imagen()), "image/jpeg")},
        data={"asset_id": activo, "location_node_id": sala["id"]},
    )
    assert foto.status_code == 201, foto.text
    assert foto.json()["location_node_id"] == sala["id"]

    plan = cliente.post(
        f"{RUTA}/photos/bulk-rename",
        headers=cab("consultor_a"),
        json={
            "photo_ids": [foto.json()["id"]],
            "template": "[Activo]_[Espacio]_[Numero]",
            "dry_run": True,
            "numerar_desde": 1,
        },
    )
    assert plan.status_code == 200, plan.text
    propuesto = plan.json()["cambios"][0]["despues"]
    # Saneado según §10: se quitan tildes y espacios, **y las mayúsculas se
    # respetan tal cual se escribieron**. «Sala Máquinas 2» → «SalaMaquinas2»,
    # igual que el ejemplo documentado `Cubierta Nº1` → `CubiertaN1`.
    assert "SalaMaquinas2" in propuesto
    assert "Espacio" not in plan.json()["cambios"][0]["omitidos"]


def test_sin_espacio_el_token_se_omite_como_antes(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[LIM]` Una foto sin ubicación no produce un nombre roto: el token se
    omite con su separador, que es lo que hacía cuando el árbol no existía."""
    foto = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab("consultor_a"),
        files={"file": ("obra.jpg", io.BytesIO(imagen()), "image/jpeg")},
        data={"asset_id": activo},
    ).json()
    plan = cliente.post(
        f"{RUTA}/photos/bulk-rename",
        headers=cab("consultor_a"),
        json={
            "photo_ids": [foto["id"]],
            "template": "[Activo]_[Espacio]_[Numero]",
            "dry_run": True,
            "numerar_desde": 1,
        },
    ).json()
    assert "[Espacio]" in plan["cambios"][0]["omitidos"]
    assert "__" not in plan["cambios"][0]["despues"], "el separador no se duplica"


def test_las_fotos_se_pueden_filtrar_por_espacio(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """Es para lo que sirve el árbol seis meses después: «enséñame lo de la
    sala de máquinas»."""
    sala = nodo(cliente, cab, activo, "Sala de bombas")
    dentro = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab("consultor_a"),
        files={"file": ("a.jpg", io.BytesIO(imagen()), "image/jpeg")},
        data={"asset_id": activo, "location_node_id": sala["id"]},
    ).json()
    cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab("consultor_a"),
        files={"file": ("b.jpg", io.BytesIO(imagen()), "image/jpeg")},
        data={"asset_id": activo},
    )

    filtradas = cliente.get(
        f"{RUTA}/projects/{proyecto}/photos?location_node_id={sala['id']}",
        headers=cab("consultor_a"),
    ).json()
    assert [f["id"] for f in filtradas] == [dentro["id"]]


def test_borrar_la_ubicacion_no_borra_la_foto(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, motor_admin: Engine
) -> None:
    """`[LIM]` La foto sobrevive; lo que se pierde es dónde estaba, y el token
    vuelve a omitirse. Perder la foto sería desproporcionado."""
    sala = nodo(cliente, cab, activo, "Sala efímera")
    foto = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab("consultor_a"),
        files={"file": ("c.jpg", io.BytesIO(imagen()), "image/jpeg")},
        data={"asset_id": activo, "location_node_id": sala["id"]},
    ).json()

    # Borrado físico: el lógico no dispara la clave ajena, y lo que se quiere
    # comprobar aquí es que la foto sobrevive al `ON DELETE SET NULL`.
    with motor_admin.begin() as conn:
        conn.execute(text("DELETE FROM location_node WHERE id = :i"), {"i": sala["id"]})

    sigue = cliente.get(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"))
    assert sigue.status_code == 200
    assert sigue.json()["location_node_id"] is None


# ─────────────────────────────────────────────────────────────────────────────
#  Aislamiento
# ─────────────────────────────────────────────────────────────────────────────


def test_otra_organizacion_no_ve_el_arbol(cliente: TestClient, cab: Any, activo: str) -> None:
    nodo(cliente, cab, activo, "Sala reservada")
    r = cliente.get(f"{RUTA}/assets/{activo}/locations", headers=cab("admin_b"))
    assert r.json() == []

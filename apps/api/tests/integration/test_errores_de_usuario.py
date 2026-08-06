"""Errores que comete el usuario y que salían como `500`.

Los cuatro casos de este fichero se encontraron **recorriendo la aplicación con
el servidor en marcha**, no leyendo el código. Ninguno lo veía la suite: repetir
el código de un encargo, escribir mal el nombre de un campo o mandar un valor
que no está en un enumerado de PostgreSQL son cosas que las pruebas no hacían
porque las pruebas escriben los datos bien.

La diferencia importa: con un `500` la pantalla dice «error interno», el usuario
vuelve a pulsar el mismo botón y nadie le dice qué campo cambiar.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.db

RUTA = "/api/v1"


def _cliente_id(cliente: TestClient, cab: Any) -> str:
    return cliente.post(
        f"{RUTA}/clients", headers=cab("admin_a"), json={"name": f"Fondo {uuid.uuid4().hex[:8]}"}
    ).json()["id"]


def _codigo() -> str:
    return f"2026-{uuid.uuid4().hex[:6]}"


# ─────────────────────────────────────────────────────────────────────────────
#  Unicidad: 409 con el campo, no 500
# ─────────────────────────────────────────────────────────────────────────────


def test_repetir_el_codigo_de_encargo_dice_que_esta_cogido(cliente: TestClient, cab: Any) -> None:
    """`[REQ]` Antes salía un 500 y el código repetido no se mencionaba."""
    cid, codigo = _cliente_id(cliente, cab), _codigo()
    cuerpo = {"client_id": cid, "internal_code": codigo, "name": "TDD Cartera Norte"}

    assert cliente.post(f"{RUTA}/projects", headers=cab("admin_a"), json=cuerpo).status_code == 201
    repetido = cliente.post(
        f"{RUTA}/projects", headers=cab("admin_a"), json={**cuerpo, "name": "Otro"}
    )

    assert repetido.status_code == 409
    detalle = repetido.json()["detail"]
    assert "código interno" in detalle
    # El mensaje no puede filtrar el nombre de la restricción ni el SQL.
    assert "project_organization" not in detalle
    assert "INSERT" not in detalle.upper()


def test_el_mismo_codigo_en_otra_organizacion_si_vale(cliente: TestClient, cab: Any) -> None:
    """La unicidad es **por organización**. Dos consultoras distintas pueden
    numerar sus encargos igual sin enterarse la una de la otra."""
    codigo = _codigo()
    cliente_a = _cliente_id(cliente, cab)
    cliente_b = cliente.post(
        f"{RUTA}/clients", headers=cab("admin_b"), json={"name": f"Beta {uuid.uuid4().hex[:8]}"}
    ).json()["id"]

    for cab_usuario, cid in (("admin_a", cliente_a), ("admin_b", cliente_b)):
        r = cliente.post(
            f"{RUTA}/projects",
            headers=cab(cab_usuario),
            json={"client_id": cid, "internal_code": codigo, "name": "Encargo"},
        )
        assert r.status_code == 201, r.text


def test_activar_dos_veces_la_misma_fase_no_es_un_error_interno(
    cliente: TestClient, cab: Any
) -> None:
    cid = _cliente_id(cliente, cab)
    proyecto = cliente.post(
        f"{RUTA}/projects",
        headers=cab("admin_a"),
        json={
            "client_id": cid,
            "internal_code": _codigo(),
            "name": "Con fases",
            "applicable_phases": [{"code": "VISITA"}, {"code": "VISITA"}],
        },
    )
    # Sea cual sea la decisión —ignorar el duplicado o rechazarlo—, lo que no
    # puede pasar es que el alta reviente con un error interno.
    assert proyecto.status_code in (201, 409), proyecto.text


# ─────────────────────────────────────────────────────────────────────────────
#  Campos que no existen: 422, no un dato perdido en silencio
# ─────────────────────────────────────────────────────────────────────────────


def test_un_campo_mal_escrito_en_el_alta_de_encargo_se_rechaza(
    cliente: TestClient, cab: Any
) -> None:
    """Un `fecha_entrega` que la API ignora crea un encargo sin fecha de entrega
    que nadie detecta hasta que se pasa."""
    r = cliente.post(
        f"{RUTA}/projects",
        headers=cab("admin_a"),
        json={
            "client_id": _cliente_id(cliente, cab),
            "internal_code": _codigo(),
            "name": "Con typo",
            "fecha_entrega": "2026-09-01",
        },
    )
    assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
#  Enumerados de PostgreSQL: 422 que dice qué vale, no 500
# ─────────────────────────────────────────────────────────────────────────────


def _foto(cliente: TestClient, cab: Any, project_id: str) -> str:
    import io

    from PIL import Image

    # Un color distinto en cada llamada: dos JPEG idénticos chocan con el
    # `UNIQUE (project_id, sha256)`, que es el detector de duplicados exactos.
    tinte = uuid.uuid4().int % 200
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), (tinte, 100, 110)).save(buf, format="JPEG")
    r = cliente.post(
        f"{RUTA}/projects/{project_id}/photos",
        headers=cab("consultor_a"),
        files={"file": ("IMG_0007.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_enlazar_una_foto_con_un_tipo_en_minusculas_dice_cuales_valen(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]
) -> None:
    """`entity_type` es un `ENUM` de PostgreSQL. Con un `str` suelto, escribir
    `finding` en minúsculas producía un **500**; ahora el 422 enumera los
    valores admitidos y quien integra la API sabe qué corregir."""
    foto = _foto(cliente, cab, str(datos_base["proyecto_a"]))
    r = cliente.post(
        f"{RUTA}/photos/{foto}/links",
        headers=cab("consultor_a"),
        json={"entity_type": "finding", "entity_id": str(uuid.uuid4())},
    )
    assert r.status_code == 422
    assert "FINDING" in r.text


def test_un_papel_de_foto_inventado_tambien_se_rechaza(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]
) -> None:
    foto = _foto(cliente, cab, str(datos_base["proyecto_a"]))
    r = cliente.post(
        f"{RUTA}/photos/{foto}/links",
        headers=cab("consultor_a"),
        json={
            "entity_type": "ASSET",
            "entity_id": str(uuid.uuid4()),
            "role": "PORTADA_BONITA",
        },
    )
    assert r.status_code == 422
    assert "EVIDENCIA" in r.text

"""Clientes y personas de la organización.

Dos listados pequeños sin los que no se puede dar de alta un encargo desde la
interfaz. La prueba que más importa aquí es la última: **el listado de personas
no devuelve el hash de la contraseña ni el estado de bloqueo**.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

pytestmark = pytest.mark.db

RUTA = "/api/v1"


def nombre_unico(prefijo: str = "Inversora") -> str:
    return f"{prefijo} {uuid.uuid4().hex[:8]}"


# ─────────────────────────────────────────────────────────────────────────────
#  Clientes
# ─────────────────────────────────────────────────────────────────────────────


def test_se_da_de_alta_un_cliente(cliente: TestClient, cab: Any) -> None:
    r = cliente.post(f"{RUTA}/clients", headers=cab("admin_a"), json={"name": nombre_unico()})
    assert r.status_code == 201, r.text
    assert r.json()["projects"] == 0


def test_dar_de_alta_dos_veces_devuelve_el_mismo_cliente(cliente: TestClient, cab: Any) -> None:
    """Dos consultores dando de alta «Inversora Ficticia» a la vez no es un
    error del que haya que informar, y crear un duplicado partiría la cartera
    del cliente en dos fichas que nadie volvería a juntar."""
    nombre = nombre_unico()
    primero = cliente.post(f"{RUTA}/clients", headers=cab("admin_a"), json={"name": nombre}).json()
    segundo = cliente.post(f"{RUTA}/clients", headers=cab("admin_a"), json={"name": nombre}).json()
    assert primero["id"] == segundo["id"]


def test_el_nombre_repetido_no_distingue_mayusculas(cliente: TestClient, cab: Any) -> None:
    nombre = nombre_unico()
    primero = cliente.post(f"{RUTA}/clients", headers=cab("admin_a"), json={"name": nombre}).json()
    segundo = cliente.post(
        f"{RUTA}/clients", headers=cab("admin_a"), json={"name": nombre.upper()}
    ).json()
    assert primero["id"] == segundo["id"]


def test_el_listado_dice_cuantos_encargos_sostiene_cada_cliente(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]
) -> None:
    """Evita borrar por error al que sostiene la cartera."""
    listado = cliente.get(f"{RUTA}/clients", headers=cab("consultor_a")).json()
    con_encargos = next(c for c in listado if c["id"] == str(datos_base["cliente_a"]))
    assert con_encargos["projects"] >= 1


def test_no_se_borra_un_cliente_con_encargos(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]
) -> None:
    """Es un `409` y no un borrado en cascada: los proyectos de ese cliente son
    trabajo hecho y facturado."""
    r = cliente.delete(f"{RUTA}/clients/{datos_base['cliente_a']}", headers=cab("admin_a"))
    assert r.status_code == 409
    assert "encargos" in r.json()["detail"]


def test_un_cliente_sin_encargos_si_se_borra(cliente: TestClient, cab: Any) -> None:
    nuevo = cliente.post(
        f"{RUTA}/clients", headers=cab("admin_a"), json={"name": nombre_unico("Efímera")}
    ).json()
    assert (
        cliente.delete(f"{RUTA}/clients/{nuevo['id']}", headers=cab("admin_a")).status_code == 204
    )
    listado = cliente.get(f"{RUTA}/clients", headers=cab("admin_a")).json()
    assert nuevo["id"] not in [c["id"] for c in listado]


def test_se_renombra_un_cliente(cliente: TestClient, cab: Any) -> None:
    nuevo = cliente.post(
        f"{RUTA}/clients", headers=cab("admin_a"), json={"name": nombre_unico()}
    ).json()
    otro = nombre_unico("Renombrada")
    r = cliente.patch(f"{RUTA}/clients/{nuevo['id']}", headers=cab("admin_a"), json={"name": otro})
    assert r.status_code == 200
    assert r.json()["name"] == otro


def test_otra_organizacion_no_ve_los_clientes(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]
) -> None:
    listado = cliente.get(f"{RUTA}/clients", headers=cab("admin_b")).json()
    assert str(datos_base["cliente_a"]) not in [c["id"] for c in listado]


def test_el_listado_busca_por_nombre(cliente: TestClient, cab: Any) -> None:
    marca = uuid.uuid4().hex[:8]
    cliente.post(f"{RUTA}/clients", headers=cab("admin_a"), json={"name": f"Buscable {marca}"})
    r = cliente.get(f"{RUTA}/clients?q={marca}", headers=cab("admin_a"))
    assert len(r.json()) == 1


# ─────────────────────────────────────────────────────────────────────────────
#  Personas
# ─────────────────────────────────────────────────────────────────────────────


def test_el_listado_de_personas_no_expone_el_hash_ni_el_bloqueo(
    cliente: TestClient, cab: Any
) -> None:
    """`[REQ]` Un listado que se consulta para rellenar un desplegable no tiene
    por qué exponer el estado de seguridad de las cuentas."""
    personas = cliente.get(f"{RUTA}/users", headers=cab("consultor_a")).json()
    assert personas, "debería haber al menos un usuario"
    prohibidos = {"password_hash", "failed_login_attempts", "locked_until", "last_login_at"}
    for persona in personas:
        assert set(persona) & prohibidos == set()
    assert set(personas[0]) == {"id", "full_name", "email", "org_role", "is_active"}


def test_las_personas_de_otra_organizacion_no_aparecen(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]
) -> None:
    personas = cliente.get(f"{RUTA}/users", headers=cab("admin_b")).json()
    assert str(datos_base["consultor_a"]) not in [p["id"] for p in personas]


def test_las_personas_se_buscan_por_nombre_o_correo(cliente: TestClient, cab: Any) -> None:
    r = cliente.get(f"{RUTA}/users?q=consultor", headers=cab("consultor_a"))
    assert r.status_code == 200
    assert all(
        "consultor" in p["full_name"].lower() or "consultor" in p["email"].lower() for p in r.json()
    )


def test_solo_un_administrador_da_de_alta_personas(cliente: TestClient, cab: Any) -> None:
    r = cliente.post(
        f"{RUTA}/users",
        headers=cab("consultor_a"),
        json={
            "email": f"nuevo-{uuid.uuid4().hex[:6]}@alfa.example",
            "full_name": "Persona nueva",
            "password": "cubierta invertida 2026",
        },
    )
    assert r.status_code == 403


def test_se_da_de_alta_una_persona_y_puede_entrar(cliente: TestClient, cab: Any) -> None:
    """Que el alta devuelva 201 no significa nada si esa persona no puede
    entrar. Se comprueba iniciando sesión con ella."""
    correo = f"nueva-{uuid.uuid4().hex[:6]}@alfa.example"
    clave = "fachada ventilada 2026"  # noqa: S105 — base efímera de pruebas

    alta = cliente.post(
        f"{RUTA}/users",
        headers=cab("admin_a"),
        json={
            "email": correo,
            "full_name": "Técnica de instalaciones",
            "org_role": "TECNICO_ESPECIALISTA",
            "password": clave,
        },
    )
    assert alta.status_code == 201, alta.text
    assert alta.json()["org_role"] == "TECNICO_ESPECIALISTA"

    entrada = cliente.post(f"{RUTA}/auth/login", json={"email": correo, "password": clave})
    assert entrada.status_code == 200


def test_no_se_repite_el_correo(cliente: TestClient, cab: Any) -> None:
    correo = f"repetida-{uuid.uuid4().hex[:6]}@alfa.example"
    cuerpo = {"email": correo, "full_name": "Alguien", "password": "cubierta invertida 2026"}
    assert cliente.post(f"{RUTA}/users", headers=cab("admin_a"), json=cuerpo).status_code == 201
    assert cliente.post(f"{RUTA}/users", headers=cab("admin_a"), json=cuerpo).status_code == 409


def test_una_clave_inicial_debil_se_rechaza(cliente: TestClient, cab: Any) -> None:
    r = cliente.post(
        f"{RUTA}/users",
        headers=cab("admin_a"),
        json={
            "email": f"debil-{uuid.uuid4().hex[:6]}@alfa.example",
            "full_name": "Alguien",
            "password": "aaaaaaaaaaaaaa",
        },
    )
    assert r.status_code == 422


def test_un_rol_inexistente_se_rechaza_diciendo_cuales_valen(cliente: TestClient, cab: Any) -> None:
    r = cliente.post(
        f"{RUTA}/users",
        headers=cab("admin_a"),
        json={
            "email": f"rol-{uuid.uuid4().hex[:6]}@alfa.example",
            "full_name": "Alguien",
            "org_role": "JEFE_SUPREMO",
            "password": "cubierta invertida 2026",
        },
    )
    assert r.status_code == 422
    assert "CONSULTOR" in r.json()["detail"]


def test_desactivar_a_alguien_lo_echa_ahora_y_no_en_catorce_dias(
    cliente: TestClient, cab: Any, motor_admin: Engine
) -> None:
    """Desactivar una cuenta tiene que cerrar sus sesiones abiertas. Si no, esa
    persona sigue dentro hasta que caduque su token de refresco."""
    correo = f"saliente-{uuid.uuid4().hex[:6]}@alfa.example"
    clave = "cubierta invertida 2026"  # noqa: S105
    nueva = cliente.post(
        f"{RUTA}/users",
        headers=cab("admin_a"),
        json={"email": correo, "full_name": "Saliente", "password": clave},
    ).json()

    tokens = cliente.post(f"{RUTA}/auth/login", json={"email": correo, "password": clave}).json()
    assert (
        cliente.post(
            f"{RUTA}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 200
    )

    tokens = cliente.post(f"{RUTA}/auth/login", json={"email": correo, "password": clave}).json()
    cliente.patch(f"{RUTA}/users/{nueva['id']}", headers=cab("admin_a"), json={"is_active": False})

    assert (
        cliente.post(
            f"{RUTA}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )


def test_nadie_se_desactiva_a_si_mismo(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]
) -> None:
    """Dejaría la organización potencialmente sin administrador y al usuario
    fuera en la siguiente petición."""
    r = cliente.patch(
        f"{RUTA}/users/{datos_base['admin_a']}", headers=cab("admin_a"), json={"is_active": False}
    )
    assert r.status_code == 422


def test_solo_un_administrador_cambia_roles(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]
) -> None:
    r = cliente.patch(
        f"{RUTA}/users/{datos_base['lector_a']}",
        headers=cab("consultor_a"),
        json={"org_role": "ADMIN"},
    )
    assert r.status_code == 403

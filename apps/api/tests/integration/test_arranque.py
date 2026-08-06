"""La primera cuenta.

Sin esta orden la aplicación no se puede usar sobre una base recién creada. Lo
que se comprueba aquí no es tanto que cree la fila —eso es un `INSERT`— como
las tres cosas que la hacen segura: **no inventa contraseñas**, **no reescribe
una cuenta que ya existe** y **no acepta una clave débil para la cuenta que más
manda de todo el sistema**.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Engine, text

from tdd.core.security import verify_password
from tdd.db.arranque import (
    VARIABLE_DE_CLAVE,
    ArranqueImposible,
    leer_clave,
    sembrar_administrador,
)

pytestmark = pytest.mark.db

CLAVE = "cubierta invertida 2026"  # noqa: S105 — base efímera de pruebas


def nombre_unico(prefijo: str) -> str:
    return f"{prefijo} {uuid.uuid4().hex[:8]}"


def correo_unico() -> str:
    return f"arranque-{uuid.uuid4().hex[:8]}@ejemplo.example"


def test_crea_la_organizacion_y_su_administrador(motor_admin: Engine) -> None:
    correo = correo_unico()
    with motor_admin.begin() as conn:
        r = sembrar_administrador(
            conn,
            organizacion=nombre_unico("Consultora"),
            email=correo,
            nombre="Nombre Apellido",
            clave=CLAVE,
        )
        assert r.organizacion_creada and r.usuario_creado
        rol, hash_guardado, gestiona = conn.execute(
            text(
                "SELECT CAST(org_role AS text), password_hash, can_manage_suggestions "
                "FROM app_user WHERE id = :i"
            ),
            {"i": r.user_id},
        ).one()

    assert rol == "ADMIN"
    # La contraseña se guarda cifrada y la que se pidió es la que entra.
    assert hash_guardado != CLAVE
    assert verify_password(CLAVE, hash_guardado)
    # El primer administrador atiende el buzón: si no, nadie podría hacerlo.
    assert gestiona is True


def test_repetir_la_orden_no_reescribe_la_cuenta(motor_admin: Engine) -> None:
    """Volver a ejecutarla no puede ser una forma de cambiarle la contraseña al
    administrador sin conocer la anterior."""
    org, correo = nombre_unico("Repetida"), correo_unico()
    with motor_admin.begin() as conn:
        primera = sembrar_administrador(
            conn, organizacion=org, email=correo, nombre="Nombre Apellido", clave=CLAVE
        )
        segunda = sembrar_administrador(
            conn,
            organizacion=org,
            email=correo,
            nombre="Otro Nombre",
            clave="fachada ventilada 2026",
        )
        hash_guardado = conn.execute(
            text("SELECT password_hash FROM app_user WHERE id = :i"), {"i": primera.user_id}
        ).scalar_one()

    assert segunda.user_id == primera.user_id
    assert segunda.organization_id == primera.organization_id
    assert not segunda.organizacion_creada and not segunda.usuario_creado
    assert verify_password(CLAVE, hash_guardado), "la contraseña original debe seguir valiendo"


def test_el_correo_no_distingue_mayusculas(motor_admin: Engine) -> None:
    correo = correo_unico()
    with motor_admin.begin() as conn:
        primera = sembrar_administrador(
            conn,
            organizacion=nombre_unico("Mayusculas"),
            email=correo.upper(),
            nombre="Nombre Apellido",
            clave=CLAVE,
        )
        segunda = sembrar_administrador(
            conn,
            organizacion=nombre_unico("Mayusculas"),
            email=correo,
            nombre="Nombre Apellido",
            clave=CLAVE,
        )
    assert segunda.user_id == primera.user_id


def test_una_clave_debil_no_pasa_ni_en_la_primera_cuenta(motor_admin: Engine) -> None:
    with motor_admin.begin() as conn, pytest.raises(ArranqueImposible):
        sembrar_administrador(
            conn,
            organizacion=nombre_unico("Debil"),
            email=correo_unico(),
            nombre="Nombre Apellido",
            clave="aaaaaaaaaaaaaa",
        )


def test_el_administrador_creado_puede_entrar(motor_admin: Engine, cliente) -> None:
    """`[REQ]` Que devuelva un identificador no significa nada si esa persona no
    puede iniciar sesión. Se comprueba entrando de verdad por la API."""
    correo = correo_unico()
    with motor_admin.begin() as conn:
        sembrar_administrador(
            conn,
            organizacion=nombre_unico("Entrable"),
            email=correo,
            nombre="Nombre Apellido",
            clave=CLAVE,
        )
    r = cliente.post("/api/v1/auth/login", json={"email": correo, "password": CLAVE})
    assert r.status_code == 200, r.text
    yo = cliente.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}
    ).json()
    assert yo["org_role"] == "ADMIN"


# ─────────────────────────────────────────────────────────────────────────────
#  De dónde sale la contraseña
# ─────────────────────────────────────────────────────────────────────────────


def test_la_clave_se_lee_del_entorno_y_no_de_un_argumento() -> None:
    """Un argumento acaba en el historial del intérprete y en la lista de
    procesos de la máquina, donde lo lee cualquiera."""
    assert leer_clave(entorno={VARIABLE_DE_CLAVE: CLAVE}) == CLAVE


def test_sin_variable_y_sin_terminal_se_niega_a_seguir() -> None:
    """`[REQ]` No se genera ninguna contraseña por omisión: así es como nacen
    los despliegues con «admin/admin»."""
    with pytest.raises(ArranqueImposible) as exc:
        leer_clave(entorno={}, interactivo=False)
    assert VARIABLE_DE_CLAVE in str(exc.value)

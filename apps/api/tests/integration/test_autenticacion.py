"""Autenticación punta a punta contra PostgreSQL real.

Aquí se comprueba lo que las pruebas unitarias no pueden: que el inicio de
sesión **funciona pese a la Row Level Security**, que es el problema del huevo
y la gallina del sistema —para saber la organización hay que leer el usuario, y
leerlo es justo lo que la RLS impide sin conocer la organización—.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tdd.core.security import hash_password

pytestmark = pytest.mark.db

RUTA = "/api/v1/auth"
CLAVE = "cubierta invertida 2026"  # noqa: S105 — base efímera de pruebas
CLAVE_NUEVA = "fachada ventilada 2026"  # noqa: S105


@pytest.fixture
def con_clave(motor_admin: Engine, datos_base: dict[str, uuid.UUID]):
    """Pone una contraseña real a un usuario y lo deja limpio de bloqueos.

    Es una fixture y no un dato fijo porque las pruebas de bloqueo dejan el
    contador tocado, y reutilizarlo entre pruebas las haría depender del orden.
    """

    def _preparar(usuario: str = "consultor_a", clave: str = CLAVE) -> str:
        with motor_admin.begin() as conn:
            correo = conn.execute(
                text(
                    "UPDATE app_user SET password_hash = :h, failed_login_attempts = 0, "
                    "locked_until = NULL, is_active = TRUE WHERE id = :i RETURNING email"
                ),
                {"h": hash_password(clave), "i": str(datos_base[usuario])},
            ).scalar_one()
            conn.execute(
                text("UPDATE user_session SET revoked_at = now() WHERE user_id = :i"),
                {"i": str(datos_base[usuario])},
            )
        return str(correo)

    return _preparar


def entrar(cliente: TestClient, correo: str, clave: str = CLAVE) -> Any:
    return cliente.post(f"{RUTA}/login", json={"email": correo, "password": clave})


# ─────────────────────────────────────────────────────────────────────────────
#  Inicio de sesión
# ─────────────────────────────────────────────────────────────────────────────


def test_se_inicia_sesion_pese_a_la_rls(cliente: TestClient, con_clave: Any) -> None:
    """El problema del huevo y la gallina, resuelto: la búsqueda por correo va
    por una función `SECURITY DEFINER` de alcance mínimo, y todo lo demás ya
    ocurre con contexto."""
    r = entrar(cliente, con_clave())
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["expires_in"] == 15 * 60
    assert cuerpo["access_token"] and cuerpo["refresh_token"]


def test_el_token_emitido_sirve_para_llamar_a_la_api(cliente: TestClient, con_clave: Any) -> None:
    """Que el login devuelva un token no significa nada si el token no abre
    ninguna puerta. Se comprueba usándolo."""
    tokens = entrar(cliente, con_clave()).json()
    r = cliente.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert r.status_code == 200
    assert r.json()["org_role"] == "CONSULTOR"


def test_la_respuesta_del_login_no_se_cachea(cliente: TestClient, con_clave: Any) -> None:
    r = entrar(cliente, con_clave())
    assert r.headers["cache-control"] == "no-store"


def test_la_clave_incorrecta_da_401(cliente: TestClient, con_clave: Any) -> None:
    r = entrar(cliente, con_clave(), clave="la que no es 12345")
    assert r.status_code == 401


def test_un_correo_desconocido_da_el_mismo_error_que_una_clave_mala(
    cliente: TestClient, con_clave: Any
) -> None:
    """`[REQ]` El mensaje es idéntico. Distinguirlos regalaría una lista de
    correos válidos a quien esté probando."""
    # La dirección tiene que ser sintácticamente válida: si no, la rechazaría
    # el validador del formulario con un 422 y no llegaría a compararse nada.
    mala_clave = entrar(cliente, con_clave(), clave="la que no es 12345")
    sin_cuenta = entrar(cliente, "nadie@example.com")

    assert mala_clave.status_code == sin_cuenta.status_code == 401
    assert mala_clave.json()["detail"] == sin_cuenta.json()["detail"]


def test_una_cuenta_desactivada_no_entra(
    cliente: TestClient, con_clave: Any, motor_admin: Engine, datos_base: dict[str, uuid.UUID]
) -> None:
    correo = con_clave("lector_a")
    with motor_admin.begin() as conn:
        conn.execute(
            text("UPDATE app_user SET is_active = FALSE WHERE id = :i"),
            {"i": str(datos_base["lector_a"])},
        )
    assert entrar(cliente, correo).status_code == 401


def test_el_login_correcto_pone_el_contador_a_cero(
    cliente: TestClient, con_clave: Any, motor_admin: Engine, datos_base: dict[str, uuid.UUID]
) -> None:
    correo = con_clave("consultor2_a")
    entrar(cliente, correo, clave="mal mal mal 123")
    entrar(cliente, correo)
    with motor_admin.begin() as conn:
        intentos = conn.execute(
            text("SELECT failed_login_attempts FROM app_user WHERE id = :i"),
            {"i": str(datos_base["consultor2_a"])},
        ).scalar_one()
    assert intentos == 0


# ─────────────────────────────────────────────────────────────────────────────
#  Bloqueo por intentos
# ─────────────────────────────────────────────────────────────────────────────


def test_cinco_fallos_bloquean_la_cuenta(cliente: TestClient, con_clave: Any) -> None:
    correo = con_clave("lector_a")
    for _ in range(5):
        entrar(cliente, correo, clave="no es esta 12345")

    r = entrar(cliente, correo, clave="no es esta 12345")
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_la_cuenta_bloqueada_no_entra_ni_con_la_clave_buena(
    cliente: TestClient, con_clave: Any
) -> None:
    """El bloqueo protege de la fuerza bruta: si la clave correcta lo saltara,
    no protegería de nada."""
    correo = con_clave("lector_a")
    for _ in range(5):
        entrar(cliente, correo, clave="no es esta 12345")
    assert entrar(cliente, correo).status_code == 429


def test_el_bloqueo_queda_en_la_auditoria(
    cliente: TestClient, con_clave: Any, motor_admin: Engine, datos_base: dict[str, uuid.UUID]
) -> None:
    correo = con_clave("lector_a")
    for _ in range(5):
        entrar(cliente, correo, clave="no es esta 12345")
    with motor_admin.begin() as conn:
        acciones = (
            conn.execute(
                text(
                    "SELECT action FROM audit_log WHERE entity_id = :i "
                    "AND action IN ('LOGIN_FAILED', 'LOGIN_BLOCKED')"
                ),
                {"i": str(datos_base["lector_a"])},
            )
            .scalars()
            .all()
        )
    assert "LOGIN_BLOCKED" in acciones


# ─────────────────────────────────────────────────────────────────────────────
#  Refresco y rotación
# ─────────────────────────────────────────────────────────────────────────────


def test_el_refresco_devuelve_un_par_nuevo(cliente: TestClient, con_clave: Any) -> None:
    tokens = entrar(cliente, con_clave()).json()
    r = cliente.post(f"{RUTA}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["refresh_token"] != tokens["refresh_token"], "el token rota"


def test_el_token_de_refresco_anterior_deja_de_valer(cliente: TestClient, con_clave: Any) -> None:
    tokens = entrar(cliente, con_clave()).json()
    cliente.post(f"{RUTA}/refresh", json={"refresh_token": tokens["refresh_token"]})

    r = cliente.post(f"{RUTA}/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


def test_reutilizar_un_token_rotado_revoca_la_familia_entera(
    cliente: TestClient, con_clave: Any
) -> None:
    """La protección contra el robo de tokens. Si el antiguo reaparece, alguien
    guardó una copia: como no se puede saber cuál de los dos es el legítimo,
    salen los dos y ambos vuelven a iniciar sesión."""
    primero = entrar(cliente, con_clave()).json()
    segundo = cliente.post(
        f"{RUTA}/refresh", json={"refresh_token": primero["refresh_token"]}
    ).json()

    # El ladrón usa el token viejo…
    assert (
        cliente.post(
            f"{RUTA}/refresh", json={"refresh_token": primero["refresh_token"]}
        ).status_code
        == 401
    )
    # …y el legítimo se queda fuera también.
    assert (
        cliente.post(
            f"{RUTA}/refresh", json={"refresh_token": segundo["refresh_token"]}
        ).status_code
        == 401
    )


def test_la_reutilizacion_se_registra_como_critica(
    cliente: TestClient, con_clave: Any, motor_admin: Engine, datos_base: dict[str, uuid.UUID]
) -> None:
    tokens = entrar(cliente, con_clave()).json()
    cliente.post(f"{RUTA}/refresh", json={"refresh_token": tokens["refresh_token"]})
    cliente.post(f"{RUTA}/refresh", json={"refresh_token": tokens["refresh_token"]})

    with motor_admin.begin() as conn:
        severidad = conn.execute(
            text(
                "SELECT CAST(severity AS text) FROM audit_log WHERE entity_id = :i "
                "AND action = 'REFRESH_TOKEN_REUSED' ORDER BY occurred_at DESC LIMIT 1"
            ),
            {"i": str(datos_base["consultor_a"])},
        ).scalar_one()
    assert severidad == "CRITICO"


def test_un_token_de_refresco_inventado_no_cuela(cliente: TestClient) -> None:
    r = cliente.post(f"{RUTA}/refresh", json={"refresh_token": "no-es-un-token"})
    assert r.status_code == 401


def test_el_token_de_refresco_no_se_guarda_en_claro(
    cliente: TestClient, con_clave: Any, motor_admin: Engine
) -> None:
    """`[REQ]` Se guarda solo su SHA-256. Se comprueba buscándolo en la tabla:
    si estuviera, una filtración daría sesiones a quien la leyera."""
    tokens = entrar(cliente, con_clave()).json()
    with motor_admin.begin() as conn:
        encontrado = conn.execute(
            text("SELECT count(*) FROM user_session WHERE refresh_token_hash = :t"),
            {"t": tokens["refresh_token"]},
        ).scalar_one()
    assert encontrado == 0


# ─────────────────────────────────────────────────────────────────────────────
#  Cierre de sesión
# ─────────────────────────────────────────────────────────────────────────────


def test_cerrar_sesion_invalida_el_refresco(cliente: TestClient, con_clave: Any) -> None:
    tokens = entrar(cliente, con_clave()).json()
    cab = {"Authorization": f"Bearer {tokens['access_token']}"}

    r = cliente.post(f"{RUTA}/logout", headers=cab, json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 204
    assert (
        cliente.post(f"{RUTA}/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code
        == 401
    )


def test_cerrar_todas_las_sesiones_echa_de_todos_los_dispositivos(
    cliente: TestClient, con_clave: Any
) -> None:
    correo = con_clave()
    movil = entrar(cliente, correo).json()
    portatil = entrar(cliente, correo).json()

    cliente.post(
        f"{RUTA}/logout-all", headers={"Authorization": f"Bearer {portatil['access_token']}"}
    )
    for tokens in (movil, portatil):
        assert (
            cliente.post(
                f"{RUTA}/refresh", json={"refresh_token": tokens["refresh_token"]}
            ).status_code
            == 401
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Cambio de contraseña
# ─────────────────────────────────────────────────────────────────────────────


def test_se_cambia_la_contrasena_y_la_nueva_sirve(cliente: TestClient, con_clave: Any) -> None:
    correo = con_clave()
    tokens = entrar(cliente, correo).json()

    r = cliente.post(
        f"{RUTA}/change-password",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"current_password": CLAVE, "new_password": CLAVE_NUEVA},
    )
    assert r.status_code == 204
    assert entrar(cliente, correo, clave=CLAVE_NUEVA).status_code == 200
    assert entrar(cliente, correo, clave=CLAVE).status_code == 401


def test_cambiar_la_contrasena_cierra_las_demas_sesiones(
    cliente: TestClient, con_clave: Any
) -> None:
    """Si alguien cambia su contraseña es porque sospecha. Dejar vivas las
    sesiones abiertas convertiría el cambio en un gesto vacío."""
    correo = con_clave()
    otra = entrar(cliente, correo).json()
    actual = entrar(cliente, correo).json()

    cliente.post(
        f"{RUTA}/change-password",
        headers={"Authorization": f"Bearer {actual['access_token']}"},
        json={"current_password": CLAVE, "new_password": CLAVE_NUEVA},
    )
    assert (
        cliente.post(f"{RUTA}/refresh", json={"refresh_token": otra["refresh_token"]}).status_code
        == 401
    )


def test_sin_la_contrasena_actual_no_se_cambia(cliente: TestClient, con_clave: Any) -> None:
    tokens = entrar(cliente, con_clave()).json()
    r = cliente.post(
        f"{RUTA}/change-password",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"current_password": "no es la mía 123", "new_password": CLAVE_NUEVA},
    )
    assert r.status_code == 401


def test_una_contrasena_nueva_debil_se_rechaza(cliente: TestClient, con_clave: Any) -> None:
    tokens = entrar(cliente, con_clave()).json()
    r = cliente.post(
        f"{RUTA}/change-password",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"current_password": CLAVE, "new_password": "corta"},
    )
    assert r.status_code == 422


def test_la_nueva_no_puede_ser_la_misma(cliente: TestClient, con_clave: Any) -> None:
    tokens = entrar(cliente, con_clave()).json()
    r = cliente.post(
        f"{RUTA}/change-password",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"current_password": CLAVE, "new_password": CLAVE},
    )
    assert r.status_code == 422

"""Recuperación de contraseña `[REQ]` §10.2.

Lo que se comprueba aquí no es que el flujo funcione —eso es lo fácil— sino las
cinco cosas que lo hacen seguro, y que se rompen sin que nada falle a la vista:

* que **no se pueda averiguar qué cuentas existen**;
* que el token **no esté en claro** en la base;
* que sirva **una sola vez** y caduque;
* que restablecer **cierre todas las sesiones**, incluida la de quien hubiera
  entrado con la contraseña vieja;
* que no se pueda usar la recuperación para **llenarle el buzón** a alguien.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tdd.identity import recuperacion

pytestmark = pytest.mark.db

RUTA = "/api/v1"
CLAVE_NUEVA = "cubierta invertida 2027 · lucernario"


@pytest.fixture
def buzon(cliente: TestClient):
    """El correo capturado en memoria, vacío antes de cada prueba."""
    cliente.app.state.correo.enviados.clear()
    return cliente.app.state.correo.enviados


@pytest.fixture
def usuario(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> dict[str, str]:
    """Un usuario propio por prueba: restablecer le cambia la contraseña y le
    cierra las sesiones, y eso no puede afectar a los compartidos."""
    from tdd.core.security import hash_password

    email = f"olvidadizo-{uuid.uuid4().hex[:8]}@alfa.example"
    with motor_admin.begin() as conn:
        uid = conn.execute(
            text(
                "INSERT INTO app_user (organization_id, email, full_name, password_hash, "
                "org_role) VALUES (:o, :e, 'Ana López', :h, 'CONSULTOR') RETURNING id"
            ),
            {"o": str(datos_base["org_a"]), "e": email, "h": hash_password("clave vieja de antes")},
        ).scalar_one()
    return {"id": str(uid), "email": email}


def pedir(cliente: TestClient, email: str):
    return cliente.post(f"{RUTA}/auth/password/forgot", json={"email": email})


def token_del_correo(mensaje) -> str:
    """El token viaja en el fragmento de la URL, detrás de `#`."""
    for palabra in mensaje.cuerpo.split():
        if "#" in palabra:
            return palabra.split("#", 1)[1]
    raise AssertionError(f"No hay enlace con token en el correo:\n{mensaje.cuerpo}")


# ─────────────────────────────────────────────────────────────────────────────
#  No se puede averiguar qué cuentas existen
# ─────────────────────────────────────────────────────────────────────────────


def test_la_respuesta_es_identica_exista_o_no_la_cuenta(
    cliente: TestClient, usuario: dict[str, str], buzon: list
) -> None:
    """`[REQ]` Un formulario que distingue «enviado» de «ese correo no existe»
    es un comprobador de cuentas gratuito."""
    conocida = pedir(cliente, usuario["email"])
    desconocida = pedir(cliente, f"nadie-{uuid.uuid4().hex[:8]}@ejemplo.example")

    assert conocida.status_code == desconocida.status_code == 202
    assert conocida.json() == desconocida.json()
    # Y sin embargo solo se ha mandado un correo.
    assert len(buzon) == 1


def test_a_una_cuenta_desconocida_no_se_le_manda_nada(cliente: TestClient, buzon: list) -> None:
    assert pedir(cliente, "nadie@ejemplo.example").status_code == 202
    assert buzon == []


def test_una_cuenta_desactivada_no_recibe_enlace_pero_responde_igual(
    cliente: TestClient, usuario: dict[str, str], buzon: list, motor_admin: Engine
) -> None:
    with motor_admin.begin() as conn:
        conn.execute(
            text("UPDATE app_user SET is_active = FALSE WHERE id = :i"), {"i": usuario["id"]}
        )
    assert pedir(cliente, usuario["email"]).status_code == 202
    assert buzon == []


# ─────────────────────────────────────────────────────────────────────────────
#  El token
# ─────────────────────────────────────────────────────────────────────────────


def test_el_token_no_se_guarda_en_claro(
    cliente: TestClient, usuario: dict[str, str], buzon: list, motor_admin: Engine
) -> None:
    """`[REQ]` Si la tabla se filtrara, lo que se llevaría el atacante son
    hashes inservibles, no enlaces de recuperación en funcionamiento."""
    pedir(cliente, usuario["email"])
    token = token_del_correo(buzon[0])

    with motor_admin.begin() as conn:
        guardado = conn.execute(
            text("SELECT token_hash FROM password_reset_token WHERE user_id = :u"),
            {"u": usuario["id"]},
        ).scalar_one()

    assert token not in guardado
    assert guardado == recuperacion.huella_de(token)


def test_el_enlace_lleva_el_token_en_el_fragmento(
    cliente: TestClient, usuario: dict[str, str], buzon: list
) -> None:
    """Detrás de `#` no se manda al servidor: no acaba en el registro de acceso
    del proxy ni en la cabecera `Referer`."""
    pedir(cliente, usuario["email"])
    cuerpo = buzon[0].cuerpo
    enlace = next(p for p in cuerpo.split() if "#" in p)
    assert "?" not in enlace
    assert "/restablecer#" in enlace


def test_el_correo_no_lleva_la_contrasena_ni_datos_de_mas(
    cliente: TestClient, usuario: dict[str, str], buzon: list
) -> None:
    pedir(cliente, usuario["email"])
    cuerpo = buzon[0].cuerpo
    assert "clave vieja" not in cuerpo
    # Saluda por el nombre de pila, no por el apellido ni por el correo.
    assert "Ana" in cuerpo
    assert usuario["email"] not in cuerpo


# ─────────────────────────────────────────────────────────────────────────────
#  Restablecer
# ─────────────────────────────────────────────────────────────────────────────


def test_el_flujo_completo_deja_entrar_con_la_nueva(
    cliente: TestClient, usuario: dict[str, str], buzon: list
) -> None:
    pedir(cliente, usuario["email"])
    r = cliente.post(
        f"{RUTA}/auth/password/reset",
        json={"token": token_del_correo(buzon[0]), "new_password": CLAVE_NUEVA},
    )
    assert r.status_code == 204, r.text

    entra = cliente.post(
        f"{RUTA}/auth/login", json={"email": usuario["email"], "password": CLAVE_NUEVA}
    )
    assert entra.status_code == 200, entra.text
    # Y la vieja deja de servir.
    vieja = cliente.post(
        f"{RUTA}/auth/login", json={"email": usuario["email"], "password": "clave vieja de antes"}
    )
    assert vieja.status_code == 401


def test_restablecer_cierra_las_sesiones_abiertas(
    cliente: TestClient, usuario: dict[str, str], buzon: list
) -> None:
    """`[REQ]` Es el punto entero de recuperar una cuenta perdida.

    Quien recupera su contraseña suele hacerlo porque sospecha o porque ha
    perdido el acceso. Dejar vivas las sesiones abiertas mantendría dentro
    exactamente a quien se quiere echar.
    """
    intruso = cliente.post(
        f"{RUTA}/auth/login", json={"email": usuario["email"], "password": "clave vieja de antes"}
    ).json()

    pedir(cliente, usuario["email"])
    cliente.post(
        f"{RUTA}/auth/password/reset",
        json={"token": token_del_correo(buzon[0]), "new_password": CLAVE_NUEVA},
    )

    # El token de refresco del intruso ya no se puede canjear.
    r = cliente.post(f"{RUTA}/auth/refresh", json={"refresh_token": intruso["refresh_token"]})
    assert r.status_code == 401


def test_el_enlace_sirve_una_sola_vez(
    cliente: TestClient, usuario: dict[str, str], buzon: list
) -> None:
    pedir(cliente, usuario["email"])
    token = token_del_correo(buzon[0])
    assert (
        cliente.post(
            f"{RUTA}/auth/password/reset",
            json={"token": token, "new_password": CLAVE_NUEVA},
        ).status_code
        == 204
    )
    segunda = cliente.post(
        f"{RUTA}/auth/password/reset", json={"token": token, "new_password": "otra cosa larga 2027"}
    )
    assert segunda.status_code == 400
    assert "ya se ha usado" in segunda.json()["detail"]


def test_usar_un_enlace_invalida_los_demas_pendientes(
    cliente: TestClient, usuario: dict[str, str], buzon: list
) -> None:
    """Pedirlo dos veces y usar el segundo no puede dejar el primero vivo: sería
    un enlace en circulación que ya nadie espera."""
    pedir(cliente, usuario["email"])
    pedir(cliente, usuario["email"])
    primero, segundo = token_del_correo(buzon[0]), token_del_correo(buzon[1])

    cliente.post(
        f"{RUTA}/auth/password/reset", json={"token": segundo, "new_password": CLAVE_NUEVA}
    )
    r = cliente.post(
        f"{RUTA}/auth/password/reset", json={"token": primero, "new_password": "y otra mas 2027"}
    )
    assert r.status_code == 400


def test_un_enlace_caducado_lo_dice(
    cliente: TestClient, usuario: dict[str, str], buzon: list, motor_admin: Engine
) -> None:
    """Se distingue de «no válido» a propósito: para llegar aquí hay que tener
    el token, así que no se revela nada, y evita que alguien pruebe tres veces
    creyendo que lo copió mal."""
    pedir(cliente, usuario["email"])
    # Se retrasa la emisión ENTERA, no solo la caducidad: el `CHECK`
    # `reset_caduca_despues` exige que caduque después de emitirse, y forzar
    # solo `expires_at` produciría una fila que la base no admite y que en la
    # vida real no puede existir.
    hace_rato = datetime.now(UTC) - timedelta(minutes=31)
    with motor_admin.begin() as conn:
        conn.execute(
            text(
                "UPDATE password_reset_token SET issued_at = :i, expires_at = :t WHERE user_id = :u"
            ),
            {
                "i": hace_rato,
                "t": hace_rato + timedelta(minutes=recuperacion.MINUTOS_DE_VALIDEZ),
                "u": usuario["id"],
            },
        )
    r = cliente.post(
        f"{RUTA}/auth/password/reset",
        json={"token": token_del_correo(buzon[0]), "new_password": CLAVE_NUEVA},
    )
    assert r.status_code == 400
    assert "caducado" in r.json()["detail"]


def test_un_token_inventado_se_rechaza(cliente: TestClient) -> None:
    r = cliente.post(
        f"{RUTA}/auth/password/reset", json={"token": "me-lo-invento", "new_password": CLAVE_NUEVA}
    )
    assert r.status_code == 400
    assert "no es válido" in r.json()["detail"]


def test_una_clave_debil_no_gasta_el_enlace(
    cliente: TestClient, usuario: dict[str, str], buzon: list
) -> None:
    """Gastarlo obligaría a pedir otro correo por haberse equivocado al elegir
    contraseña, que es el momento en que más se equivoca uno."""
    pedir(cliente, usuario["email"])
    token = token_del_correo(buzon[0])

    debil = cliente.post(
        f"{RUTA}/auth/password/reset", json={"token": token, "new_password": "1234"}
    )
    assert debil.status_code == 422

    buena = cliente.post(
        f"{RUTA}/auth/password/reset", json={"token": token, "new_password": CLAVE_NUEVA}
    )
    assert buena.status_code == 204, buena.text


def test_una_cuenta_desactivada_despues_de_pedirlo_no_puede_restablecer(
    cliente: TestClient, usuario: dict[str, str], buzon: list, motor_admin: Engine
) -> None:
    """Entre la petición y el uso pasa media hora, y en ese rato pueden haber
    dado de baja a la persona."""
    pedir(cliente, usuario["email"])
    token = token_del_correo(buzon[0])
    with motor_admin.begin() as conn:
        conn.execute(
            text("UPDATE app_user SET is_active = FALSE WHERE id = :i"), {"i": usuario["id"]}
        )
    r = cliente.post(
        f"{RUTA}/auth/password/reset", json={"token": token, "new_password": CLAVE_NUEVA}
    )
    assert r.status_code == 400
    assert "desactivada" in r.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
#  Abuso
# ─────────────────────────────────────────────────────────────────────────────


def test_no_se_puede_usar_para_llenar_el_buzon_de_alguien(
    cliente: TestClient, usuario: dict[str, str], buzon: list
) -> None:
    """Y la respuesta **no cambia** al llegar al tope: cambiarla volvería a
    delatar qué cuentas existen."""
    respuestas = [pedir(cliente, usuario["email"]) for _ in range(6)]

    assert {r.status_code for r in respuestas} == {202}
    assert len({r.text for r in respuestas}) == 1
    assert len(buzon) == recuperacion.MAXIMO_POR_VENTANA


def test_todo_queda_auditado(
    cliente: TestClient, usuario: dict[str, str], buzon: list, motor_admin: Engine
) -> None:
    pedir(cliente, usuario["email"])
    cliente.post(
        f"{RUTA}/auth/password/reset",
        json={"token": token_del_correo(buzon[0]), "new_password": CLAVE_NUEVA},
    )
    with motor_admin.begin() as conn:
        acciones = {
            f[0]
            for f in conn.execute(
                text("SELECT action FROM audit_log WHERE entity_id = :u"), {"u": usuario["id"]}
            )
        }
    assert {"PASSWORD_RESET_REQUESTED", "PASSWORD_RESET_COMPLETED"} <= acciones


def test_el_token_no_aparece_en_la_auditoria(
    cliente: TestClient, usuario: dict[str, str], buzon: list, motor_admin: Engine
) -> None:
    """Un registro de auditoría lo lee más gente que un buzón."""
    pedir(cliente, usuario["email"])
    token = token_del_correo(buzon[0])
    with motor_admin.begin() as conn:
        filas = conn.execute(
            text("SELECT CAST(after_data AS text), action FROM audit_log WHERE entity_id = :u"),
            {"u": usuario["id"]},
        ).all()
    assert all(token not in str(f[0]) for f in filas)

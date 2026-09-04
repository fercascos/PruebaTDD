"""Entrar con la identidad de Azure: emparejamiento, roles y altas."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from esg.core.security import emitir_token_local
from tests.conftest import SECRETO, correo_de

pytestmark = pytest.mark.db


def test_sin_credencial_no_se_entra(cliente) -> None:
    assert cliente.get("/api/v1/yo").status_code == 401


def test_un_token_firmado_con_otro_secreto_no_vale(cliente) -> None:
    token = emitir_token_local(
        secreto="otro-secreto-igual-de-largo-pero-distinto-0123456789",
        sujeto="local:x",
        email="x@y.example",
        nombre="X",
    )
    respuesta = cliente.get("/api/v1/yo", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 401
    # Sin decir por qué: distinguir «caducado» de «firma inválida» le regala
    # información a quien esté probando tokens.
    assert respuesta.json()["detail"] == "Credencial no válida"


def test_una_identidad_valida_sin_ficha_no_entra_y_se_le_dice_que_hacer(cliente) -> None:
    """403 y no 401: la credencial es buena, lo que falta es la invitación.
    Con un 401 el navegador volvería a Azure una y otra vez."""
    token = emitir_token_local(
        secreto=SECRETO,
        sujeto="local:ajeno@fuera.example",
        email="ajeno@fuera.example",
        nombre="Ajeno",
    )
    respuesta = cliente.get("/api/v1/yo", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 403
    assert "administrador" in respuesta.json()["detail"]


def test_yo_devuelve_los_permisos_calculados_no_el_rol_a_secas(cliente, cab) -> None:
    yo = cliente.get("/api/v1/yo", headers=cab("analista_a")).json()
    assert yo["rol"] == "ANALISTA"
    assert yo["escribe_datos"] is True
    assert yo["escribe_estructura"] is False
    assert yo["ve_todo"] is True

    cliente_externo = cliente.get("/api/v1/yo", headers=cab("cliente_a")).json()
    assert cliente_externo["ve_todo"] is False
    assert cliente_externo["escribe_datos"] is False


def test_el_primer_acceso_empareja_la_ficha_con_la_identidad(cliente, cab, motor_admin) -> None:
    """Se da de alta a alguien por su correo antes de que exista para nosotros;
    al entrar por primera vez, su sujeto de Azure queda fijado."""
    correo = correo_de("recien_invitado_a")
    with motor_admin.begin() as conn:
        antes = conn.execute(
            text("SELECT sub_oidc FROM usuario WHERE email = :e"), {"e": correo}
        ).scalar_one()
    assert antes is None

    token = emitir_token_local(
        secreto=SECRETO, sujeto="entra:0000-1111", email=correo, nombre="Recién Invitado"
    )
    yo = cliente.get("/api/v1/yo", headers={"Authorization": f"Bearer {token}"})
    assert yo.status_code == 200

    with motor_admin.begin() as conn:
        fila = conn.execute(
            text(
                "SELECT sub_oidc, emisor_oidc, ultimo_acceso_en, rol::text FROM usuario "
                "WHERE email = :e"
            ),
            {"e": correo},
        ).one()
    assert fila.sub_oidc == "entra:0000-1111"
    assert fila.ultimo_acceso_en is not None
    # Y el emparejamiento no ha tocado el rol: eso lo impide el trigger.
    assert fila.rol == "LECTOR"


def test_un_lector_no_puede_invitar_a_nadie(cliente, cab) -> None:
    respuesta = cliente.post(
        "/api/v1/usuarios",
        json={"email": "nuevo@alfa.example", "nombre": "Nuevo", "rol": "LECTOR"},
        headers=cab("lector_a"),
    )
    assert respuesta.status_code == 403


def test_dar_de_alta_a_un_cliente_y_abrirle_una_cartera(cliente, cab, datos) -> None:
    alta = cliente.post(
        "/api/v1/usuarios",
        json={
            "email": "gestor@fondo-cliente.example",
            "nombre": "Gestor del fondo",
            "rol": "CLIENTE",
        },
        headers=cab("admin_a"),
    )
    assert alta.status_code == 201
    nuevo = alta.json()
    assert nuevo["emparejado"] is False

    ambito = cliente.post(
        f"/api/v1/usuarios/{nuevo['id']}/ambitos",
        json={"cartera_id": str(datos["cartera_a"])},
        headers=cab("admin_a"),
    )
    assert ambito.status_code == 201
    assert ambito.json()["etiqueta"] == "Cartera Ibérica"

    # Y ese cliente, al entrar, ve exactamente esa cartera.
    token = emitir_token_local(
        secreto=SECRETO,
        sujeto="entra:fondo-1",
        email="gestor@fondo-cliente.example",
        nombre="Gestor del fondo",
    )
    carteras = cliente.get("/api/v1/carteras", headers={"Authorization": f"Bearer {token}"}).json()
    assert [c["codigo"] for c in carteras] == ["IB"]


def test_un_ambito_tiene_que_ser_una_cartera_o_un_activo_no_las_dos(cliente, cab, datos) -> None:
    respuesta = cliente.post(
        f"/api/v1/usuarios/{datos['cliente_a']}/ambitos",
        json={"cartera_id": str(datos["cartera_a"]), "activo_id": str(datos["torre"])},
        headers=cab("admin_a"),
    )
    assert respuesta.status_code == 422

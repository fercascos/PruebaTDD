"""Los factores sembrados, el arranque de la instalación y el esquema aplicado."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text

from esg.db.arranque import crear
from esg.db.sembrar import sembrar
from esg.indicadores.unidades import FACTORES_FIJOS
from tests.conftest import URL_ADMIN

pytestmark = pytest.mark.db


def test_la_tabla_de_factores_no_puede_divergir_del_codigo(motor_admin) -> None:
    """Quien audita el informe pregunta con qué factor se convirtió.

    La tabla es el reflejo del catálogo del código. Si alguien cambia uno de
    los dos y no el otro, esta prueba lo dice.
    """
    sembrar(str(URL_ADMIN))
    with motor_admin.begin() as conn:
        filas = conn.execute(
            text(
                "SELECT unidad_origen, unidad_destino, factor FROM factor_de_conversion "
                "WHERE organizacion_id IS NULL"
            )
        ).all()
    en_tabla = {(f.unidad_origen, f.unidad_destino): f.factor for f in filas}
    assert en_tabla.keys() == FACTORES_FIJOS.keys()
    for clave, factor in FACTORES_FIJOS.items():
        assert en_tabla[clave] == factor.quantize(Decimal("0.00000001"))


def test_sembrar_dos_veces_no_duplica_nada(motor_admin) -> None:
    sembrar(str(URL_ADMIN))
    assert sembrar(str(URL_ADMIN)) == 0


def test_el_arranque_crea_la_organizacion_y_su_administrador(motor_admin) -> None:
    """La API no puede hacer esto: la RLS lo impide, y está bien que lo impida."""
    crear(
        str(URL_ADMIN),
        organizacion="Consultora de Prueba",
        slug="consultora-de-prueba",
        email="jefa@consultora.example",
        nombre="Jefa de Sostenibilidad",
    )
    with motor_admin.begin() as conn:
        fila = conn.execute(
            text(
                "SELECT u.rol::text AS rol, u.sub_oidc, o.nombre FROM usuario u "
                "JOIN organizacion o ON o.id = u.organizacion_id "
                "WHERE u.email = 'jefa@consultora.example'"
            )
        ).one()
    assert fila.rol == "ADMIN"
    assert fila.nombre == "Consultora de Prueba"
    # Sin emparejar todavía: se empareja con Azure en su primer inicio de sesión.
    assert fila.sub_oidc is None


def test_repetir_el_arranque_no_rompe_nada(motor_admin) -> None:
    for _ in range(2):
        crear(
            str(URL_ADMIN),
            organizacion="Consultora de Prueba",
            slug="consultora-de-prueba",
            email="jefa@consultora.example",
            nombre="Jefa de Sostenibilidad",
        )
    with motor_admin.begin() as conn:
        cuantas = conn.execute(
            text("SELECT count(*) FROM organizacion WHERE slug = 'consultora-de-prueba'")
        ).scalar_one()
    assert cuantas == 1

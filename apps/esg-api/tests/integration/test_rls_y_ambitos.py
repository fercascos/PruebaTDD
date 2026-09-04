"""El aislamiento: por organización y por ámbito de visibilidad.

Es la prueba que decide si esto se puede abrir a un cliente algún día.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

pytestmark = pytest.mark.db


def test_cada_organizacion_ve_solo_lo_suyo(como) -> None:
    with como("admin_a") as s:
        carteras = s.execute(text("SELECT codigo FROM cartera ORDER BY codigo")).scalars().all()
    assert carteras == ["IB", "LV"]
    with como("admin_b") as s:
        carteras = s.execute(text("SELECT codigo FROM cartera")).scalars().all()
    assert carteras == ["BT"]


def test_un_cliente_ve_su_cartera_y_solo_su_cartera(como) -> None:
    with como("cliente_a") as s:
        carteras = s.execute(text("SELECT codigo FROM cartera")).scalars().all()
        activos = s.execute(text("SELECT codigo FROM activo")).scalars().all()
    assert carteras == ["IB"]
    assert activos == ["A-001"]


def test_un_cliente_sin_ambito_no_ve_nada_en_vez_de_verlo_todo(como) -> None:
    """El fallo seguro: dar de alta a alguien y olvidar su ámbito enseña un
    panel vacío, nunca los datos de otro cliente."""
    with como("cliente_sin_ambito_a") as s:
        assert s.execute(text("SELECT count(*) FROM cartera")).scalar_one() == 0
        assert s.execute(text("SELECT count(*) FROM activo")).scalar_one() == 0
        assert s.execute(text("SELECT count(*) FROM punto_de_suministro")).scalar_one() == 0


def test_el_ambito_alcanza_a_los_suministros_y_a_las_lecturas(como, datos) -> None:
    with como("gestor_a") as s:
        s.execute(
            text(
                "INSERT INTO lectura (organizacion_id, punto_id, inicio, fin, cantidad, unidad, "
                "cantidad_normalizada, unidad_normalizada, origen) VALUES "
                "(:o, :p, '2021-01-01', '2021-02-01', 100, 'kWh', 100, 'kWh', 'MANUAL')"
            ),
            {"o": datos["org_a"], "p": datos["luz_nave"]},
        )
    # La Nave está en la cartera Levante, que el cliente NO tiene en su ámbito.
    with como("cliente_a") as s:
        assert s.execute(text("SELECT count(*) FROM punto_de_suministro")).scalar_one() == 3
        assert (
            s.execute(text("SELECT count(*) FROM lectura WHERE inicio = '2021-01-01'")).scalar_one()
            == 0
        )


def test_un_lector_no_escribe_aunque_lo_vea_todo(como, datos) -> None:
    """La RLS también dice quién escribe: la API y la base tienen que coincidir."""
    with pytest.raises(DBAPIError):
        with como("lector_a") as s:
            s.execute(
                text(
                    "INSERT INTO lectura (organizacion_id, punto_id, inicio, fin, cantidad, "
                    "unidad, origen) VALUES (:o, :p, '2021-06-01', '2021-07-01', 10, 'kWh', "
                    "'MANUAL')"
                ),
                {"o": datos["org_a"], "p": datos["luz_torre"]},
            )


def test_un_analista_carga_datos_pero_no_toca_el_inventario(como, datos) -> None:
    with como("analista_a") as s:
        s.execute(
            text(
                "INSERT INTO lectura (organizacion_id, punto_id, inicio, fin, cantidad, unidad, "
                "origen) VALUES (:o, :p, '2021-07-01', '2021-08-01', 10, 'kWh', 'MANUAL')"
            ),
            {"o": datos["org_a"], "p": datos["luz_torre"]},
        )
    with pytest.raises(DBAPIError):
        with como("analista_a") as s:
            s.execute(
                text(
                    "INSERT INTO activo (organizacion_id, cartera_id, codigo, nombre) "
                    "VALUES (:o, :c, 'X-999', 'No debería entrar')"
                ),
                {"o": datos["org_a"], "c": datos["cartera_a"]},
            )


def test_sin_contexto_no_se_ve_nada(fabrica) -> None:
    """Olvidar el contexto produce una lista vacía, no una fuga."""
    s = fabrica()
    try:
        assert s.execute(text("SELECT count(*) FROM activo")).scalar_one() == 0
    finally:
        s.close()


def test_una_conexion_reutilizada_del_pool_tampoco_ve_nada(fabrica) -> None:
    """El caso real, y el que se escapó la primera vez.

    Cuando termina una transacción que hizo `SET LOCAL`, la variable no vuelve
    a «no definida»: vuelve a **cadena vacía**. Así llega la siguiente petición
    que reutiliza esa conexión, que son todas menos la primera.
    """
    s = fabrica()
    try:
        s.begin()
        for clave in ("app.organizacion_id", "app.usuario_id", "app.ve_todo"):
            s.execute(text("SELECT set_config(:k, '', TRUE)"), {"k": clave})
        assert s.execute(text("SELECT count(*) FROM activo")).scalar_one() == 0
        assert s.execute(text("SELECT count(*) FROM cartera")).scalar_one() == 0
        s.rollback()
    finally:
        s.close()


def test_el_usuario_de_aplicacion_no_puede_saltarse_la_rls(motor_app: Engine) -> None:
    """Si `esg_app` fuera propietario o tuviera BYPASSRLS, todo lo anterior
    sería decorativo: las políticas ni se le aplicarían."""
    with motor_app.connect() as conn:
        fila = conn.execute(
            text("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user")
        ).one()
        assert fila.rolbypassrls is False
        assert fila.rolsuper is False
        with pytest.raises(ProgrammingError):
            conn.execute(text("ALTER TABLE activo DISABLE ROW LEVEL SECURITY"))


def test_el_inicio_de_sesion_no_puede_cambiar_el_rol_de_nadie(fabrica, datos) -> None:
    """El emparejamiento abre una rendija de escritura sobre la propia fila.

    El trigger es lo que impide que esa rendija sirva para ascenderse a ADMIN.
    """
    s = fabrica()
    try:
        s.begin()
        for clave, valor in (
            ("app.login_emisor", "esg-local"),
            ("app.login_sujeto", "local:lector_a@org_a.example"),
            ("app.login_email", "lector_a@org_a.example"),
        ):
            s.execute(text("SELECT set_config(:k, :v, TRUE)"), {"k": clave, "v": valor})
        # Actualizar la marca de acceso: permitido.
        s.execute(
            text("UPDATE usuario SET ultimo_acceso_en = now() WHERE id = :id"),
            {"id": datos["lector_a"]},
        )
        with pytest.raises(DBAPIError):
            s.execute(
                text("UPDATE usuario SET rol = 'ADMIN' WHERE id = :id"),
                {"id": datos["lector_a"]},
            )
        s.rollback()
    finally:
        s.close()


def test_un_identificador_de_otra_organizacion_no_existe_para_mi(como, datos) -> None:
    ajeno: uuid.UUID = datos["edificio_b"]
    with como("admin_a") as s:
        cuantos = s.execute(
            text("SELECT count(*) FROM activo WHERE id = :id"), {"id": ajeno}
        ).scalar_one()
    assert cuantos == 0

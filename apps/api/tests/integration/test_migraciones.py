"""Las migraciones producen exactamente el esquema de `schema.sql`.

Esta es **la** prueba que justifica que existan dos caminos para crear la base:
`psql -f schema.sql` en desarrollo y `alembic upgrade head` en una instalación
real. Dos caminos son dos oportunidades de divergir, y la divergencia no se ve
al aplicarlos —los dos terminan sin errores—: se ve meses después, cuando una
instalación migrada resulta que no tiene una política RLS y los datos de una
organización aparecen en otra.

Se comparan las cosas que de verdad protegen los datos y que Alembic **no**
sabe autogenerar: políticas, triggers, funciones, restricciones y columnas
generadas. Comparar solo la lista de tablas dejaría fuera todo lo que importa.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.db

RAIZ_API = Path(__file__).resolve().parents[2]
ESQUEMA = RAIZ_API / "src" / "tdd" / "db" / "schema.sql"


def _url_a(base: str) -> str:
    """La misma conexión de la suite, apuntando a otra base.

    Se usa el parser de SQLAlchemy y no un `split`: la URL local lleva la forma
    `@/tdd?host=/tmp`, y partir por la última barra se lleva por delante el
    `host=/tmp` en vez del nombre de la base. Salió en la primera ejecución.
    """
    return (
        make_url(os.environ["TEST_DATABASE_URL"])
        .set(database=base)
        .render_as_string(hide_password=False)
    )


@pytest.fixture
def base_efimera(motor_admin: Engine) -> Iterator[str]:
    """Una base vacía, recién creada, que se destruye al terminar."""
    nombre = f"tdd_mig_{uuid.uuid4().hex[:8]}"
    # `AUTOCOMMIT`: CREATE DATABASE no puede ir dentro de una transacción.
    with motor_admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f'CREATE DATABASE "{nombre}"'))
    try:
        yield nombre
    finally:
        with motor_admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :n"),
                {"n": nombre},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{nombre}"'))


# ─────────────────────────────────────────────────────────────────────────────
#  Cómo se retrata un esquema
# ─────────────────────────────────────────────────────────────────────────────

CONSULTAS: dict[str, str] = {
    "tablas": (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    ),
    "columnas": (
        "SELECT table_name, column_name, data_type, is_nullable, column_default, "
        "       is_generated, generation_expression "
        "FROM information_schema.columns WHERE table_schema = 'public' "
        "ORDER BY table_name, column_name"
    ),
    # Lo que de verdad protege los datos, y lo que Alembic no autogenera.
    "politicas": (
        "SELECT tablename, policyname, permissive, cmd, qual, with_check "
        "FROM pg_policies WHERE schemaname = 'public' ORDER BY tablename, policyname"
    ),
    "rls_activada": (
        "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind = 'r' ORDER BY c.relname"
    ),
    "triggers": (
        "SELECT event_object_table, trigger_name, event_manipulation, "
        "       action_timing, action_statement "
        "FROM information_schema.triggers WHERE trigger_schema = 'public' "
        "ORDER BY event_object_table, trigger_name, event_manipulation"
    ),
    "restricciones": (
        "SELECT rel.relname, con.conname, pg_get_constraintdef(con.oid) "
        "FROM pg_constraint con JOIN pg_class rel ON rel.oid = con.conrelid "
        "JOIN pg_namespace n ON n.oid = rel.relnamespace "
        "WHERE n.nspname = 'public' ORDER BY rel.relname, con.conname"
    ),
    "indices": (
        "SELECT tablename, indexname, indexdef FROM pg_indexes "
        "WHERE schemaname = 'public' ORDER BY tablename, indexname"
    ),
    "funciones": (
        "SELECT p.proname, pg_get_functiondef(p.oid) "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'public' ORDER BY p.proname"
    ),
    "enumerados": (
        "SELECT t.typname, e.enumlabel FROM pg_type t "
        "JOIN pg_enum e ON e.enumtypid = t.oid "
        "JOIN pg_namespace n ON n.oid = t.typnamespace "
        "WHERE n.nspname = 'public' ORDER BY t.typname, e.enumsortorder"
    ),
}


#: La contabilidad del propio Alembic. Existe en la base migrada y no en la
#: creada con `psql`, y compararla haría fallar la prueba por la única
#: diferencia que es correcta que exista.
PROPIAS_DE_ALEMBIC = ("alembic_version",)


def retratar(url: str) -> dict[str, list[tuple]]:
    motor = create_engine(url, future=True)
    try:
        with motor.connect() as conn:
            return {
                nombre: [
                    tuple(f)
                    for f in conn.execute(text(sql)).all()
                    # Se filtra por el primer campo porque todas las consultas
                    # empiezan por el nombre de la tabla.
                    if f[0] not in PROPIAS_DE_ALEMBIC
                ]
                for nombre, sql in CONSULTAS.items()
            }
    finally:
        motor.dispose()


def aplicar_schema_sql(url: str) -> None:
    motor = create_engine(url, future=True)
    with motor.begin() as conn:
        conn.execute(text(ESQUEMA.read_text(encoding="utf-8")))
    motor.dispose()


def aplicar_migraciones(url: str) -> None:
    """`alembic upgrade head` como lo ejecutaría una persona."""
    entorno = {**os.environ, "DATABASE_MIGRATION_URL": url, "PYTHONPATH": "src"}
    resultado = subprocess.run(  # noqa: S603 — orden fija, sin entrada del usuario
        ["python3", "-m", "alembic", "upgrade", "head"],  # noqa: S607
        cwd=RAIZ_API,
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, (
        f"alembic upgrade head ha fallado:\n{resultado.stdout}\n{resultado.stderr}"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Las pruebas
# ─────────────────────────────────────────────────────────────────────────────


def test_migrar_desde_cero_produce_el_mismo_esquema(base_efimera: str, motor_admin: Engine) -> None:
    """`[REQ]` Los dos caminos de creación tienen que converger.

    Si divergen, la instalación real y la de desarrollo dejan de ser la misma
    cosa, y eso se descubre meses después, con datos dentro.
    """
    otra = f"{base_efimera}_ref"
    with motor_admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f'CREATE DATABASE "{otra}"'))
    try:
        aplicar_migraciones(_url_a(base_efimera))
        aplicar_schema_sql(_url_a(otra))

        migrado = retratar(_url_a(base_efimera))
        directo = retratar(_url_a(otra))

        for aspecto in CONSULTAS:
            assert migrado[aspecto] == directo[aspecto], (
                f"El esquema migrado difiere del de schema.sql en «{aspecto}». "
                "Alguien ha tocado uno de los dos caminos y no el otro."
            )
    finally:
        with motor_admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :n"),
                {"n": otra},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{otra}"'))


def test_la_base_migrada_lleva_las_politicas_rls(base_efimera: str) -> None:
    """Es lo que más importa y lo que Alembic no autogenera.

    Un esquema «migrado» sin políticas arranca sin un solo error y deja los
    datos de cada organización visibles para las demás. Se comprueba explícito
    y no solo por comparación: si un día alguien quitara las políticas de los
    dos caminos a la vez, la prueba anterior seguiría en verde.
    """
    aplicar_migraciones(_url_a(base_efimera))
    retrato = retratar(_url_a(base_efimera))

    tablas_con_politica = {fila[0] for fila in retrato["politicas"]}
    assert "suggestion" in tablas_con_politica, "falta la política del buzón de sugerencias"
    assert "project" in tablas_con_politica, "falta el aislamiento por organización"
    assert len(retrato["politicas"]) > 30, (
        f"solo {len(retrato['politicas'])} políticas: los bucles DO $$ no se han ejecutado"
    )

    # `FORCE ROW LEVEL SECURITY`: sin esto, el propietario de la tabla se salta
    # sus propias políticas y toda la protección sería decorativa.
    forzadas = {fila[0] for fila in retrato["rls_activada"] if fila[2]}
    assert "project" in forzadas
    assert "photo" in forzadas


def test_la_base_migrada_lleva_los_triggers_y_las_funciones(base_efimera: str) -> None:
    aplicar_migraciones(_url_a(base_efimera))
    retrato = retratar(_url_a(base_efimera))

    assert len(retrato["triggers"]) > 0, "sin triggers, los originales no están protegidos"
    funciones = {fila[0] for fila in retrato["funciones"]}
    # Las de la RLS y las dos de `SECURITY DEFINER` del login.
    assert {"org_actual", "usuario_actual", "login_buscar_usuario"} <= funciones


def test_una_base_recien_migrada_esta_en_la_ultima_version(base_efimera: str) -> None:
    """`alembic_version` es lo que permite saber qué tiene delante una
    instalación. Sin esa fila, la siguiente migración no sabe desde dónde va."""
    aplicar_migraciones(_url_a(base_efimera))
    motor = create_engine(_url_a(base_efimera), future=True)
    with motor.connect() as conn:
        versiones = [f[0] for f in conn.execute(text("SELECT version_num FROM alembic_version"))]
    motor.dispose()
    assert versiones == ["0001"]


def test_volver_a_migrar_no_hace_nada(base_efimera: str) -> None:
    """Ejecutar el despliegue dos veces es lo normal —un reintento, dos réplicas
    arrancando— y no puede reventar."""
    aplicar_migraciones(_url_a(base_efimera))
    antes = retratar(_url_a(base_efimera))
    aplicar_migraciones(_url_a(base_efimera))
    assert retratar(_url_a(base_efimera)) == antes


def test_deshacer_el_esquema_inicial_se_niega_en_vez_de_borrar(base_efimera: str) -> None:
    """`[REQ]` Un `downgrade` que borrara el esquema convertiría un error de
    tecleo en una pérdida total de datos."""
    aplicar_migraciones(_url_a(base_efimera))
    entorno = {
        **os.environ,
        "DATABASE_MIGRATION_URL": _url_a(base_efimera),
        "PYTHONPATH": "src",
    }
    resultado = subprocess.run(  # noqa: S603
        ["python3", "-m", "alembic", "downgrade", "base"],  # noqa: S607
        cwd=RAIZ_API,
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode != 0, "el downgrade debería negarse"

    # Y la base sigue entera: negarse no puede dejarla a medias.
    assert len(retratar(_url_a(base_efimera))["tablas"]) > 20


def test_sin_conexion_en_el_entorno_la_orden_se_niega() -> None:
    """`[REQ]` La URL no está en `alembic.ini`: una cadena con contraseña en un
    fichero versionado es una credencial en el repositorio."""
    entorno = {
        k: v for k, v in os.environ.items() if k not in ("DATABASE_MIGRATION_URL", "DATABASE_URL")
    }
    entorno["PYTHONPATH"] = "src"
    resultado = subprocess.run(  # noqa: S603
        ["python3", "-m", "alembic", "upgrade", "head"],  # noqa: S607
        cwd=RAIZ_API,
        env=entorno,
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode != 0
    assert "DATABASE_MIGRATION_URL" in resultado.stderr + resultado.stdout


def test_el_alembic_ini_no_lleva_ninguna_cadena_de_conexion() -> None:
    """Se comprueba el fichero, no el comportamiento: alguien puede añadir la
    URL «solo para probar» y que se quede ahí para siempre."""
    ini = (RAIZ_API / "alembic.ini").read_text(encoding="utf-8")
    assert "sqlalchemy.url" not in ini
    assert "postgresql" not in ini

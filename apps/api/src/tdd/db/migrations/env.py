"""Entorno de Alembic.

`[REQ]` La conexión sale del **entorno**, nunca del `alembic.ini`: una cadena
con contraseña en un fichero versionado es una credencial en el repositorio.

`[SUP]` Se usa `DATABASE_MIGRATION_URL` si está, y `DATABASE_URL` si no. Migrar
exige crear tablas, funciones y políticas, y el usuario de la aplicación
(`tdd_app`) **no es propietario de nada** a propósito: si pudiera alterar el
esquema, la Row Level Security que lo protege sería decorativa. Por eso hay dos
conexiones distintas y esta es la de administración.

**No hay `target_metadata`.** No es un olvido: en este proyecto no existe una
capa de modelos declarativos de la que autogenerar. La verdad del esquema es
`schema.sql`, y con razón — 6 políticas RLS explícitas más las de dos bucles,
9 triggers, 14 funciones, 4 columnas generadas y 57 `CHECK`, de los cuales
`--autogenerate` no sabe expresar prácticamente ninguno. Un autogenerado que
ignora en silencio las políticas y los triggers produciría migraciones que
parecen correctas y dejan la base sin protección.

Las migraciones se escriben a mano, en SQL. Es más trabajo y es lo honesto.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _url() -> str:
    url = os.environ.get("DATABASE_MIGRATION_URL") or os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "Falta la conexión de administración. Defina DATABASE_MIGRATION_URL "
            "(o DATABASE_URL). No se toma del alembic.ini a propósito: una cadena "
            "con contraseña en un fichero versionado es una credencial en el repositorio."
        )
    return url


def migrar_sin_conexion() -> None:
    """Modo `--sql`: emite el SQL sin tocar la base.

    Sirve para revisar en un *pull request* qué se va a ejecutar sobre
    producción antes de que lo ejecute nadie.
    """
    context.configure(
        url=_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def migrar_con_conexion() -> None:
    seccion = config.get_section(config.config_ini_section, {})
    seccion["sqlalchemy.url"] = _url()
    motor = engine_from_config(seccion, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with motor.connect() as conexion:
        context.configure(connection=conexion)
        # Una migración a medias es peor que ninguna: deja el esquema en un
        # estado que no corresponde a ninguna versión y que nadie sabe deshacer.
        with context.begin_transaction():
            context.run_migrations()
    motor.dispose()


if context.is_offline_mode():
    migrar_sin_conexion()
else:
    migrar_con_conexion()

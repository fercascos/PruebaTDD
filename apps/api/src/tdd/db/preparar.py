"""Deja una base lista para que la aplicación arranque contra ella.

    DATABASE_MIGRATION_URL='...' python3 -m tdd.db.preparar

Hace, en este orden y en una sola pasada:

  1. aplica las migraciones pendientes (`alembic upgrade head`);
  2. **vuelve a dar permisos** al rol de aplicación;
  3. siembra catálogos y fases.

El paso 2 no es decorativo y va **después** de migrar, no antes. Una migración
que crea una tabla la crea como administrador, y `tdd_app` —que no es
propietario— se queda sin permisos sobre ella: la tabla existe, la RLS está
puesta, y la aplicación recibe «permission denied» en cuanto la toca. Es el
mismo motivo por el que el `Makefile` encadena `db-grant` tras cada migración.

`[REQ]` Crear el rol es **opcional y explícito**: solo ocurre si se pasan
`--rol` y `--clave` (o `APP_DB_USER` y `APP_DB_PASSWORD`). En un despliegue de
verdad el rol lo crea quien administra la base, y esta herramienta no debería
conocer ninguna contraseña; en `compose` sí conviene, porque levantar el entorno
entero con un comando es justamente lo que se busca.

`[LIM]` Es idempotente pero **no** reversible: no borra nada y no baja
migraciones. Para eso está `alembic downgrade`, a mano y mirando.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from tdd.catalogs.seeding import sembrar_catalogos
from tdd.phases.seeding import sembrar_fases

#: `alembic.ini` vive en la raíz de `apps/api`, cuatro niveles por encima.
RAIZ = Path(__file__).resolve().parents[3]


def migrar(dsn: str) -> None:
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "src" / "tdd" / "db" / "migrations"))
    # `env.py` lee la conexión del entorno, no de la configuración: se le pone
    # aquí para que dé igual cómo se haya invocado esto.
    os.environ["DATABASE_MIGRATION_URL"] = dsn
    command.upgrade(cfg, "head")


def asegurar_rol(dsn: str, rol: str, clave: str) -> None:
    """Crea el rol de aplicación si no existe, y le fija la contraseña.

    `[REQ]` **Sin `BYPASSRLS` y sin `SUPERUSER`.** Si el rol de aplicación
    pudiera saltarse la Row Level Security, todo el aislamiento entre
    organizaciones de este esquema sería decorativo.
    """
    motor = create_engine(dsn, future=True, isolation_level="AUTOCOMMIT")
    with motor.connect() as conn:
        existe = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": rol}).first()
        verbo = "ALTER" if existe else "CREATE"
        # Ni el nombre del rol ni la contraseña pueden ir como parámetro: uno es
        # un identificador y la otra forma parte de la sentencia, y PostgreSQL no
        # admite parámetros en ninguna de las dos posiciones. Se citan a mano con
        # las reglas de PostgreSQL —comillas dobles duplicadas para el
        # identificador, simples para el literal—, que es lo que cierra la
        # inyección aquí.
        rol_citado = '"{}"'.format(rol.replace('"', '""'))
        clave_citada = "'{}'".format(clave.replace("'", "''"))
        conn.execute(text(f"{verbo} ROLE {rol_citado} LOGIN PASSWORD {clave_citada}"))  # noqa: S608
    motor.dispose()


def dar_permisos(dsn: str, rol: str) -> None:
    motor = create_engine(dsn, future=True)
    with motor.begin() as conn:
        for sentencia in (
            "GRANT USAGE ON SCHEMA public TO {rol}",
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {rol}",
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {rol}",
        ):
            conn.execute(text(sentencia.format(rol=f'"{rol}"')))
    motor.dispose()


def sembrar(dsn: str) -> None:
    motor = create_engine(dsn, future=True)
    with motor.begin() as conn:
        print(sembrar_catalogos(conn))
        plantillas, hitos, comprobaciones = sembrar_fases(conn)
        print(
            f"Fases: {plantillas} plantillas, {hitos} hitos, {comprobaciones} tipos de comprobación"
        )
    motor.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m tdd.db.preparar",
        description="Migra, da permisos y siembra. Idempotente.",
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_MIGRATION_URL") or os.environ.get("DATABASE_URL", ""),
        help="Conexión de ADMINISTRACIÓN. Por omisión, DATABASE_MIGRATION_URL o DATABASE_URL.",
    )
    parser.add_argument(
        "--rol",
        default=os.environ.get("APP_DB_USER", "tdd_app"),
        help="Rol de aplicación al que dar permisos.",
    )
    parser.add_argument(
        "--clave",
        default=os.environ.get("APP_DB_PASSWORD", ""),
        help="Si se indica, crea el rol o le fija la contraseña. Sin ella, el rol debe existir.",
    )
    args = parser.parse_args(argv)
    if not args.dsn:
        print("Falta la conexión: defina DATABASE_MIGRATION_URL o pase --dsn.", file=sys.stderr)
        return 2

    print(f"→ Migrando {args.dsn.rsplit('@', 1)[-1]}")
    migrar(args.dsn)
    if args.clave:
        print(f"→ Rol de aplicación «{args.rol}»")
        asegurar_rol(args.dsn, args.rol, args.clave)
    print(f"→ Permisos para «{args.rol}»")
    dar_permisos(args.dsn, args.rol)
    print("→ Sembrando")
    sembrar(args.dsn)
    print("Base lista.")
    return 0


if __name__ == "__main__":  # pragma: no cover — punto de entrada
    raise SystemExit(main())

"""Aplica el esquema sobre una base vacía.

`[LIM]` No hay migraciones todavía. El esquema se aplica entero sobre una base
nueva, que es lo que hace falta mientras no haya datos de producción que
conservar. En cuanto los haya, esto se sustituye por Alembic —como en
`apps/api`— y `schema.sql` pasa a ser el resultado, no el origen. Decirlo aquí
es más honesto que fingir un sistema de migraciones con una sola versión.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ESQUEMA = Path(__file__).with_name("schema.sql")


def aplicar(dsn: str, *, sembrar_factores: bool = True) -> None:
    motor = create_engine(dsn, future=True)
    with motor.begin() as conn:
        conn.execute(text(ESQUEMA.read_text(encoding="utf-8")))
    if sembrar_factores:
        from esg.db.sembrar import sembrar

        sembrar(dsn)
    motor.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aplica el esquema ESG sobre una base vacía")
    parser.add_argument("--dsn", required=True, help="DSN de ADMINISTRACIÓN, no el de la app")
    argumentos = parser.parse_args(argv)
    aplicar(argumentos.dsn)
    print("Esquema aplicado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

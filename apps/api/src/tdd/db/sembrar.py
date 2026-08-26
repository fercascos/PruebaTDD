"""Siembra de catálogos y fases sobre una base ya creada.

Los dos sembradores existían pero solo los llamaba la suite de pruebas: sobre
una base creada a mano el árbol de zonas, los 121 códigos de CAPEX y las fases
del proceso no aparecían por ningún sitio, y la aplicación arrancaba con todos
los desplegables vacíos.

    DATABASE_URL='...' python3 -m tdd.db.sembrar

`[SUP]` Se conecta como administrador, no como `tdd_app`: las filas del sistema
llevan `organization_id` NULL y la RLS de los catálogos no permite escribirlas.

Es **idempotente**: las semillas usan `ON CONFLICT ... DO NOTHING` sobre
`UNIQUE NULLS NOT DISTINCT (organization_id, code)`. Sin esa cláusula
—PostgreSQL considera distintos dos NULL— volver a ejecutarla duplicaba el
catálogo entero, que es justo como se descubrió.
"""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine

from tdd.catalogs.seeding import sembrar_catalogos
from tdd.phases.seeding import sembrar_fases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m tdd.db.sembrar",
        description="Siembra los catálogos del sistema y las fases del proceso.",
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_MIGRATION_URL") or os.environ.get("DATABASE_URL", ""),
        help="Conexión de administración. Por omisión, DATABASE_MIGRATION_URL o DATABASE_URL.",
    )
    args = parser.parse_args(argv)
    if not args.dsn:
        print("Falta la conexión: defina DATABASE_URL o pase --dsn.", file=sys.stderr)
        return 2

    motor = create_engine(args.dsn, future=True)
    with motor.begin() as conn:
        print(sembrar_catalogos(conn))
        plantillas, hitos, comprobaciones = sembrar_fases(conn)
        print(
            f"Fases: {plantillas} plantillas, {hitos} hitos, {comprobaciones} tipos de comprobación"
        )
    motor.dispose()
    return 0


if __name__ == "__main__":  # pragma: no cover — punto de entrada
    raise SystemExit(main())

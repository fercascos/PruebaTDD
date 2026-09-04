"""La primera organización y su administrador.

Esto **no** se puede hacer desde la API, y no es un descuido: la RLS impide
escribir la primera organización —no hay contexto todavía— y el primer
administrador no puede darse de alta a sí mismo. Se hace desde aquí, con el DSN
de administración, una sola vez por instalación.

No se pide contraseña: no hay contraseñas. La identidad la pone Entra ID; lo
que se da de alta es la **ficha**, y se empareja con Azure la primera vez que
esa persona entra.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine, text


def crear(dsn: str, *, organizacion: str, slug: str, email: str, nombre: str) -> None:
    motor = create_engine(dsn, future=True)
    with motor.begin() as conn:
        org = conn.execute(
            text(
                "INSERT INTO organizacion (nombre, slug) VALUES (:n, :s) "
                "ON CONFLICT (slug) DO UPDATE SET nombre = EXCLUDED.nombre RETURNING id"
            ),
            {"n": organizacion, "s": slug},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO usuario (organizacion_id, email, nombre, rol) "
                "VALUES (:o, :e, :n, 'ADMIN') "
                "ON CONFLICT (organizacion_id, lower(email)) DO UPDATE SET rol = 'ADMIN'"
            ),
            {"o": org, "e": email, "n": nombre},
        )
    motor.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crea la organización y su administrador")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--org", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--nombre", required=True)
    a = parser.parse_args(argv)
    crear(a.dsn, organizacion=a.org, slug=a.slug, email=a.email, nombre=a.nombre)
    print(
        f"Organización «{a.org}» lista, con {a.email} como administrador.\n"
        "Esa persona entra con su cuenta de Azure: la ficha se empareja sola la primera vez."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

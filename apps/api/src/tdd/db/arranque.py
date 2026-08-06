"""`[REQ]` Alta de la primera organización y su primer administrador.

Sin esto la aplicación no se puede usar: sobre una base recién creada no hay
ninguna organización ni ninguna cuenta, y `POST /users` exige un administrador
ya autenticado. Es el problema del huevo y la gallina, y la única salida
razonable es una orden fuera de la API, ejecutada por quien tiene acceso a la
base de datos.

    TDD_BOOTSTRAP_PASSWORD='...' python3 -m tdd.db.arranque \\
        --org "Consultora Ejemplo" --email admin@ejemplo.example --nombre "Nombre Apellido"

`[REQ]` La contraseña **no se pasa por argumento**: se lee de
`TDD_BOOTSTRAP_PASSWORD` o se pide por consola sin eco. Un argumento acaba en
el historial del intérprete de órdenes y en la lista de procesos de la máquina,
donde lo lee cualquiera.

`[REQ]` No hay ninguna credencial escrita aquí. Si la variable no está y la
entrada no es interactiva, el programa se niega a seguir en vez de inventarse
una clave por omisión —que es como nacen los despliegues con `admin/admin`.

La orden es **idempotente**: si la organización ya existe la reutiliza, y si el
correo ya tiene cuenta no la toca ni cambia su contraseña. Volver a ejecutarla
no es destructivo.

`[SUP]` Se conecta como el usuario propietario de la base (`DATABASE_URL` de
administración), no como `tdd_app`: la RLS exige un contexto de organización que
todavía no existe cuando se está creando la primera.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import create_engine, text

from tdd.core.security import hash_password
from tdd.identity.service import ClaveDebil, comprobar_fortaleza

VARIABLE_DE_CLAVE = "TDD_BOOTSTRAP_PASSWORD"  # noqa: S105 — el nombre, no el valor


class ArranqueImposible(Exception):  # noqa: N818 — el dominio está en español
    """No se dan las condiciones para crear la primera cuenta."""


@dataclass(frozen=True, slots=True)
class Resultado:
    organization_id: uuid.UUID
    user_id: uuid.UUID
    organizacion_creada: bool
    usuario_creado: bool

    def __str__(self) -> str:
        org = "creada" if self.organizacion_creada else "ya existía"
        usr = "creado" if self.usuario_creado else "ya existía (sin tocar)"
        return f"Organización {self.organization_id} ({org})\nAdministrador {self.user_id} ({usr})"


def _slug(nombre: str) -> str:
    """Identificador legible y estable a partir del nombre."""
    limpio = "".join(c.lower() if c.isalnum() else "-" for c in nombre.strip())
    while "--" in limpio:
        limpio = limpio.replace("--", "-")
    return limpio.strip("-")[:60] or "organizacion"


def leer_clave(*, entorno: dict[str, str] | None = None, interactivo: bool | None = None) -> str:
    """La contraseña, del entorno o de la consola. Nunca de un argumento."""
    entorno = os.environ if entorno is None else entorno
    clave = entorno.get(VARIABLE_DE_CLAVE, "")
    if clave:
        return clave
    if interactivo is None:
        interactivo = sys.stdin.isatty()
    if not interactivo:
        raise ArranqueImposible(
            f"No hay contraseña. Defina {VARIABLE_DE_CLAVE} o ejecute la orden desde "
            "una terminal interactiva. No se genera ninguna por omisión a propósito."
        )
    primera = getpass.getpass("Contraseña del administrador: ")
    if primera != getpass.getpass("Repítala: "):
        raise ArranqueImposible("Las dos contraseñas no coinciden")
    return primera


def sembrar_administrador(
    conn, *, organizacion: str, email: str, nombre: str, clave: str
) -> Resultado:
    """Crea (o reutiliza) la organización y su primer administrador.

    Recibe la conexión ya abierta para que la orden y las pruebas compartan
    exactamente el mismo camino, sin un `create_engine` escondido dentro.
    """
    correo = email.strip().lower()
    try:
        comprobar_fortaleza(clave, email=correo)
    except ClaveDebil as exc:
        # La primera cuenta es la que más manda de todo el sistema: es la peor
        # posible para saltarse la comprobación de fortaleza «solo esta vez».
        raise ArranqueImposible(str(exc)) from exc

    fila = conn.execute(
        text("SELECT id FROM organization WHERE lower(name) = lower(:n) OR slug = :s"),
        {"n": organizacion.strip(), "s": _slug(organizacion)},
    ).first()
    organizacion_creada = fila is None
    if fila is None:
        org_id = conn.execute(
            text("INSERT INTO organization (name, slug) VALUES (:n, :s) RETURNING id"),
            {"n": organizacion.strip(), "s": _slug(organizacion)},
        ).scalar_one()
    else:
        org_id = fila[0]

    ya = conn.execute(
        text("SELECT id FROM app_user WHERE lower(email) = lower(:e)"), {"e": correo}
    ).first()
    if ya is not None:
        # No se le cambia la contraseña ni el rol: volver a ejecutar la orden no
        # puede ser una forma de reescribir una cuenta existente.
        return Resultado(org_id, ya[0], organizacion_creada, usuario_creado=False)

    user_id = conn.execute(
        text(
            "INSERT INTO app_user (organization_id, email, full_name, password_hash, org_role, "
            "can_manage_suggestions) VALUES (:o, :e, :n, :h, 'ADMIN', TRUE) RETURNING id"
        ),
        {"o": org_id, "e": correo, "n": nombre.strip(), "h": hash_password(clave)},
    ).scalar_one()
    conn.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, severity) VALUES (:o, :u, 'BOOTSTRAP_ADMIN_CREATED', 'app_user', :u, "
            "'AVISO')"
        ),
        {"o": org_id, "u": user_id},
    )
    return Resultado(org_id, user_id, organizacion_creada, usuario_creado=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m tdd.db.arranque",
        description="Crea la primera organización y su administrador.",
        epilog=f"La contraseña se lee de {VARIABLE_DE_CLAVE} o por consola, nunca de un argumento.",
    )
    parser.add_argument("--org", required=True, help="Nombre de la organización")
    parser.add_argument("--email", required=True, help="Correo del administrador")
    parser.add_argument("--nombre", required=True, help="Nombre y apellidos del administrador")
    parser.add_argument(
        "--dsn",
        default=os.environ.get("DATABASE_MIGRATION_URL") or os.environ.get("DATABASE_URL", ""),
        help="Conexión de administración. Por omisión, DATABASE_MIGRATION_URL o DATABASE_URL.",
    )
    args = parser.parse_args(argv)

    if not args.dsn:
        print("Falta la conexión: defina DATABASE_URL o pase --dsn.", file=sys.stderr)
        return 2
    try:
        clave = leer_clave()
        motor = create_engine(args.dsn, future=True)
        with motor.begin() as conn:
            resultado = sembrar_administrador(
                conn, organizacion=args.org, email=args.email, nombre=args.nombre, clave=clave
            )
        motor.dispose()
    except ArranqueImposible as exc:
        print(f"No se pudo crear la cuenta: {exc}", file=sys.stderr)
        return 1
    print(resultado)
    return 0


if __name__ == "__main__":  # pragma: no cover — punto de entrada
    raise SystemExit(main())

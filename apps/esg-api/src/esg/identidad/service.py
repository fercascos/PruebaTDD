"""Del token de Azure a un usuario de esta aplicación.

Azure dice **quién eres**. En qué organización estás, con qué rol y qué
carteras ves lo dice esta base de datos, y por eso hay un emparejamiento: no se
crean usuarios solos. Que alguien tenga cuenta en el directorio corporativo no
significa que deba ver los consumos de una cartera de un cliente.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from esg.core.security import Identidad
from esg.identidad.permisos import Permisos, permisos_de


class UsuarioDesconocido(Exception):
    """Identidad válida en Azure, sin ficha aquí. **No se da de alta sola.**"""


@dataclass(frozen=True, slots=True)
class UsuarioActual:
    id: uuid.UUID
    organizacion_id: uuid.UUID
    email: str
    nombre: str
    rol: str

    @property
    def permisos(self) -> Permisos:
        return permisos_de(self.rol)


def emparejar(session: Session, identidad: Identidad) -> UsuarioActual:
    """Busca la ficha del usuario y, si es su primer acceso, fija su sujeto.

    La sesión que entra aquí **no tiene contexto de organización** —todavía no
    se sabe cuál es—, así que la lectura pasa por la política
    `usuario_emparejamiento`, que solo deja ver la fila de la identidad
    presentada. Ver el comentario del esquema: es la única rendija de lectura
    sin organización de toda la aplicación, y tiene el tamaño justo.
    """
    for clave, valor in (
        ("app.login_emisor", identidad.emisor),
        ("app.login_sujeto", identidad.sujeto),
        ("app.login_email", identidad.email),
    ):
        session.execute(text("SELECT set_config(:k, :v, TRUE)"), {"k": clave, "v": valor})

    fila = session.execute(
        text(
            "SELECT id, organizacion_id, email, nombre, rol::text, sub_oidc "
            "FROM usuario "
            # Primero el emparejado por sujeto; el de correo solo si no lo hay.
            # Sin este orden, una ficha nueva creada con el mismo correo se
            # colaría por delante de la ya emparejada.
            "ORDER BY (sub_oidc IS NULL) ASC, creado_en ASC "
            "LIMIT 1"
        )
    ).first()
    if fila is None:
        raise UsuarioDesconocido(identidad.email or identidad.sujeto)

    if fila.sub_oidc is None:
        session.execute(
            text(
                "UPDATE usuario SET emisor_oidc = :emisor, sub_oidc = :sujeto, "
                "ultimo_acceso_en = now() WHERE id = :id"
            ),
            {"emisor": identidad.emisor, "sujeto": identidad.sujeto, "id": fila.id},
        )
    else:
        session.execute(
            text("UPDATE usuario SET ultimo_acceso_en = now() WHERE id = :id"), {"id": fila.id}
        )

    return UsuarioActual(
        id=fila.id,
        organizacion_id=fila.organizacion_id,
        email=fila.email,
        nombre=fila.nombre,
        rol=fila.rol,
    )

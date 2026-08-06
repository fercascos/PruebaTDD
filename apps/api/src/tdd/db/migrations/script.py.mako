"""${message}

Revisión: ${up_revision}
Anterior: ${down_revision | comma,n}
Creada:   ${create_date}

Escriba aquí QUÉ cambia y POR QUÉ. Dentro de seis meses, quien lea esto durante
una incidencia no tiene el contexto que usted tiene ahora.

Si la migración toca datos y no solo estructura, dígalo: es la diferencia entre
poder repetirla sin miedo y no poder.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "raise NotImplementedError"}


def downgrade() -> None:
    # Si esta migración no se puede deshacer, dígalo con un `raise` explicando
    # por qué. Un `pass` silencioso hace creer que hay vuelta atrás cuando no la
    # hay, y eso se descubre en el peor momento posible.
    ${downgrades if downgrades else "raise NotImplementedError"}

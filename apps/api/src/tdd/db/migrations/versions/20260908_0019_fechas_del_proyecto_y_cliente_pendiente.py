"""Las fechas del proyecto, y el cliente que nace pendiente de validar.

Revisión: 0019
Anterior: 0018

Las dos salen de la revisión del primer prototipo, y las dos son de la pantalla
de entrada.

**1 · `project` tenía una sola fecha, y la lista pide dos.**

Había `report_due_date`, que es el compromiso de entrega del informe. La lista
de proyectos enseña otra cosa: **cuándo arrancó el trabajo y cuándo se cerró**,
que es lo que permite ordenar la cartera y ver qué sigue vivo. Son tres cosas
distintas y por eso son tres columnas: un proyecto puede haber arrancado en
enero, comprometer el informe para marzo y cerrarse en mayo.

El `CHECK` de que el cierre no puede ser anterior al arranque no es celo: la
lista se ordena por fecha, y un error de tecleo en una fecha que ya está escrita
no lo vuelve a mirar nadie.

**2 · `client.pending_validation`: el cliente que no estaba en la lista.**

El cliente se elige de una lista que mantiene la administración. Escribir uno
que no está **no puede bloquear** el alta —quien la hace suele tener el proyecto
por correo y el alta del cliente va por otro circuito—, pero tampoco puede
entrar al catálogo como si lo hubiera validado alguien.

Así que nace **pendiente**, y el aviso al administrador no es un correo ni una
tabla nueva: es una sugerencia de tipo `CATALOGO` en el buzón que ya existe y
que **solo ven los administradores**, con RLS y no con un filtro de servicio.
Reutilizarlo es lo que evita un segundo mecanismo de avisos que mantener.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan en
#: `test_migraciones.py`, así que esto no puede ser una versión parecida.
FECHAS = """\
ALTER TABLE project
    ADD COLUMN start_date DATE,
    ADD COLUMN close_date DATE,
    ADD CONSTRAINT project_cierre_despues_del_arranque
        CHECK (close_date IS NULL OR start_date IS NULL OR close_date >= start_date)
"""

CLIENTE = """\
ALTER TABLE client
    ADD COLUMN pending_validation BOOLEAN NOT NULL DEFAULT FALSE
"""


def upgrade() -> None:
    op.execute(FECHAS)
    op.execute(CLIENTE)


def downgrade() -> None:
    op.execute("ALTER TABLE client DROP COLUMN pending_validation")
    op.execute(
        "ALTER TABLE project "
        "DROP CONSTRAINT project_cierre_despues_del_arranque, "
        "DROP COLUMN close_date, DROP COLUMN start_date"
    )

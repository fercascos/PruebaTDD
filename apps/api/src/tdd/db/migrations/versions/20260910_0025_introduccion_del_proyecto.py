"""La introducción del proyecto, que abre el informe final.

Revisión: 0025
Anterior: 0024

`[REQ]` §3.1 · Revisando el prototipo, el cliente pidió que el Resumen del
proyecto lleve **«un cuadro de texto que recoja la información básica del
proyecto, que sirva como introducción en el informe final»**.

Es **texto y no una ficha de campos**. Lo que se pide es un párrafo de contexto
—qué se compra, para qué, con qué alcance se revisa—, y trocearlo en campos
obligaría a inventarse una plantilla que nadie ha pedido y que además tendría
que volver a unirse en prosa para el informe.

Y **lo escribe una persona**: sale tal cual en el documento que se entrega al
cliente, así que no se genera ni se propone. Es la diferencia con los datos de
la memoria técnica, que sí se leen de un documento y por eso nacen marcados
«sin validar».

Es una columna anulable en una tabla que ya existe: se aplica sobre una base con
proyectos en marcha sin tocar una sola fila.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan en
#: `test_migraciones.py`, así que esto no puede ser una versión parecida.
INTRODUCCION = """\
ALTER TABLE project ADD COLUMN summary_text TEXT
"""


def upgrade() -> None:
    op.execute(INTRODUCCION)


def downgrade() -> None:
    """`[LIM]` Se pierde la introducción redactada de cada proyecto.

    No hay dónde guardarla: es el único sitio donde vive. Se avisa en vez de
    fingir que la vuelta atrás es gratis.
    """
    op.execute("ALTER TABLE project DROP COLUMN summary_text")

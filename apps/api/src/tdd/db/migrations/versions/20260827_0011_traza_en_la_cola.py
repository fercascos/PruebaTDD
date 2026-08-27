"""La petición que encargó cada tarea.

Es la correlación que faltaba para poder operar esto. Un informe se pide en una
petición HTTP y se genera **minutos después, en otro proceso**: sin guardar de
dónde vino, «el informe de las 11:04 salió mal» no se puede atar a ningún
registro, ni al revés —ver qué pasó después de una petición que el usuario dice
que falló—.

Va como columna y no dentro de `payload` porque no es un dato de la tarea, es
metadato de quién la pidió: mezclarlo con el contenido obligaría a filtrarlo
antes de pasárselo al manejador, y algún día alguien no lo filtraría.

`TEXT` y no `UUID`: el identificador puede venir del balanceador con el formato
que él use, y rechazar el suyo para inventar otro rompería la traza justo en el
salto que se quiere seguir.

Revision ID: 0011
Revises: 0010
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Sin `COMMENT ON`: `schema.sql` no usa ninguno, y añadirlo aquí haría que los
#: dos caminos de creación produjeran esquemas distintos, que es exactamente lo
#: que `test_migrar_desde_cero_produce_el_mismo_esquema` existe para impedir.
COLUMNA = """
ALTER TABLE job ADD COLUMN request_id TEXT;
"""


def upgrade() -> None:
    op.execute(COLUMNA)


def downgrade() -> None:
    # Bajar pierde la traza de las tareas ya encoladas, y no hay forma de
    # recuperarla. No es una pérdida grave —es diagnóstico, no negocio— pero se
    # dice en vez de dejarlo implícito.
    op.execute("ALTER TABLE job DROP COLUMN IF EXISTS request_id;")

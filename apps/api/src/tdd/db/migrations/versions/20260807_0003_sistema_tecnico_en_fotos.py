"""Sistema técnico en las fotografías.

Revisión: 0003
Anterior: 0002

`[REQ]` §3.2 · La clasificación transversal por sistema técnico.

Cierra un defecto que llevaba tiempo a la vista sin que nadie lo mirase: la
plantilla de renombrado por defecto es
`[Proyecto]_[Activo]_[Sistema]_[Zona]_[Numero]`, pero la fotografía no guardaba
el sistema en ninguna parte. El token no tenía de dónde salir, así que **todo
renombrado en lote escribía «SinSistema»**.

La columna es anulable a propósito: en campo se dispara antes de clasificar, y
`photo` ya trata el activo igual —preferible, no obligatorio—. Exigirla ahora
habría dejado sin poder guardar las fotos que ya están sin clasificar.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE photo ADD COLUMN technical_system_id UUID REFERENCES technical_system(id)"
    )
    op.execute("CREATE INDEX photo_sistema_idx ON photo (project_id, technical_system_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS photo_sistema_idx")
    op.execute("ALTER TABLE photo DROP COLUMN IF EXISTS technical_system_id")

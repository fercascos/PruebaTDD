"""Concurrencia optimista: que dos personas no se pisen en silencio.

Revisión: 0008
Anterior: 0007

`[REQ]` Hasta aquí no había ningún control de concurrencia. El escenario, con
nombres: Marta abre un hallazgo, Luis abre el mismo hallazgo, Marta corrige la
descripción y guarda, Luis guarda su cambio de riesgo treinta segundos después.
**La corrección de Marta desaparece y nadie se entera.** Queda en `audit_log`,
pero solo la encuentra quien ya sospecha que pasó.

Esta revisión añade a las seis tablas que se editan en paralelo —`finding`,
`capex_item`, `asset`, `project`, `doc_request_item` y `equipment`— dos
columnas y un disparador:

* `row_version`, que **incrementa el disparador y no la aplicación**. Un
  `UPDATE` que se olvide de subirlo no existe, incluidos los que se escriban
  mañana. El número no es un dato editable: es el estado de la fila.
* `updated_by`, que se rellena solo desde `usuario_actual()`, la misma función
  que ya sostiene la RLS. Sin ella el mensaje de conflicto solo podría decir
  «alguien lo cambió», que no ayuda a resolverlo.

`[SUP]` Las filas que ya existan arrancan en la versión 1. Es correcto: nadie
tiene todavía un ETag anterior con el que comparar, así que no hay conflicto
que perder.

`[LIM]` Las fotografías, los documentos y las rondas de Q&A **no** entran. No
es un olvido: sus operaciones son añadir versiones y adjuntar, no reescribir
un mismo campo desde dos sitios, y el original ya está protegido por sus
propios disparadores. Meterlas habría añadido cabeceras a rutas donde la
carrera no existe.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Las seis tablas que dos personas pueden editar a la vez.
TABLAS: tuple[str, ...] = (
    "finding",
    "capex_item",
    "asset",
    "project",
    "doc_request_item",
    "equipment",
)

#: Copia literal de la función en `schema.sql`. Ver el comentario de `upgrade`.
FUNCION = """CREATE OR REPLACE FUNCTION marcar_version_y_autor() RETURNS TRIGGER AS $$
BEGIN
    NEW.row_version := OLD.row_version + 1;
    -- `COALESCE` porque las migraciones y la siembra escriben sin sesión de
    -- usuario: ahí se conserva el autor anterior en vez de borrarlo.
    NEW.updated_by := COALESCE(usuario_actual(), OLD.updated_by);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;"""


def upgrade() -> None:
    for tabla in TABLAS:
        op.execute(
            f"""
            ALTER TABLE {tabla}
                ADD COLUMN row_version INTEGER NOT NULL DEFAULT 1,
                ADD COLUMN updated_by  UUID REFERENCES app_user(id)
            """
        )

    # El cuerpo va SIN sangrar y carácter a carácter igual que en `schema.sql`:
    # `test_migrar_desde_cero_produce_el_mismo_esquema` compara el texto que
    # PostgreSQL guarda de cada función, y una sangría distinta ya es una
    # diferencia. Es a propósito: obliga a que los dos caminos digan lo mismo.
    op.execute(FUNCION)

    for tabla in TABLAS:
        op.execute(
            f"CREATE TRIGGER {tabla}_version BEFORE UPDATE ON {tabla} "
            "FOR EACH ROW EXECUTE FUNCTION marcar_version_y_autor()"
        )


def downgrade() -> None:
    """Se deshace entero. Perder el contador no pierde ningún dato del encargo:
    solo la capacidad de detectar una edición simultánea."""
    for tabla in TABLAS:
        op.execute(f"DROP TRIGGER IF EXISTS {tabla}_version ON {tabla}")
    op.execute("DROP FUNCTION IF EXISTS marcar_version_y_autor()")
    for tabla in TABLAS:
        op.execute(
            f"ALTER TABLE {tabla} "
            "DROP COLUMN IF EXISTS updated_by, "
            "DROP COLUMN IF EXISTS row_version"
        )

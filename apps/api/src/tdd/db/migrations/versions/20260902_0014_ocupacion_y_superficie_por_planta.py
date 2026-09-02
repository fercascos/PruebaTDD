"""«Ocupación» en vez de «huella», y la superficie útil dividida por planta.

Revisión: 0014
Anterior: 0013

Las dos cosas salen de leer una memoria técnica de verdad, y ninguna se habría
descubierto sin ella.

**1 · `footprint_area_sqm` pasa a `occupied_area_sqm`.** El concepto estaba
bien —lo que el edificio ocupa en la parcela, frente a la construida que suma
todas las plantas— pero el nombre no era el del oficio. La memoria lo llama
**Ocupación**, y el consultor que revisa la ficha busca esa palabra. Que el
código y el documento usen el mismo término deja de ser cosmético en cuanto
alguien tiene que cuadrar una cifra con el original.

**2 · `asset_floor`: la útil, por planta.** La memoria no da solo el total; lo
da dividido:

    Útil planta baja      6.023 m²
    Útil planta primera   1.234 m²
    Útil total            7.257 m²

Guardar solo el total tiraba el desglose, que es lo que hace falta para
repartir un CAPEX de oficinas entre plantas.

`[REC]` El total se queda en `asset.usable_area_sqm` y **no** se calcula
sumando la tabla. La memoria lo da explícito, y las dos cifras pueden no
cuadrar: una puede itemizar solo las plantas de oficinas y dar un total que
incluye el altillo. Derivar el total de la suma haría que la aplicación
contradijera al documento del que salió sin decírselo a nadie.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan.
PLANTAS = """\
CREATE TABLE asset_floor (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    asset_id        UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    label           VARCHAR(60) NOT NULL,
    level           SMALLINT,
    usable_area_sqm NUMERIC(14, 2),
    built_area_sqm  NUMERIC(14, 2),
    notes           TEXT,
    orden           SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (asset_id, label),
    CONSTRAINT asset_floor_superficies_no_negativas
        CHECK (COALESCE(usable_area_sqm, 0) >= 0 AND COALESCE(built_area_sqm, 0) >= 0)
);

CREATE INDEX asset_floor_activo_idx ON asset_floor (asset_id, orden);
"""


def upgrade() -> None:
    # El `CHECK` nombra la columna, así que se cae y se rehace: renombrar la
    # columna no reescribe la expresión de una restricción ya creada.
    op.execute("ALTER TABLE asset DROP CONSTRAINT asset_superficies_memoria_no_negativas")
    op.execute("ALTER TABLE asset RENAME COLUMN footprint_area_sqm TO occupied_area_sqm")
    op.execute(
        "ALTER TABLE asset ADD CONSTRAINT asset_superficies_memoria_no_negativas "
        "CHECK (COALESCE(occupied_area_sqm, 0) >= 0 AND COALESCE(urbanised_area_sqm, 0) >= 0 "
        "AND COALESCE(usable_area_sqm, 0) >= 0 AND COALESCE(max_height_m, 0) >= 0)"
    )

    op.execute(PLANTAS)
    op.execute("ALTER TABLE asset_floor ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE asset_floor FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY asset_floor_aislamiento_org ON asset_floor "
        "USING (organization_id = org_actual()) "
        "WITH CHECK (organization_id = org_actual())"
    )


def downgrade() -> None:
    """Bajar esta revisión pierde el desglose de superficie por planta.

    El renombrado sí se deshace sin pérdida: es la misma columna con el nombre
    anterior, y los valores no se tocan.
    """
    op.execute("DROP TABLE IF EXISTS asset_floor")
    op.execute("ALTER TABLE asset DROP CONSTRAINT asset_superficies_memoria_no_negativas")
    op.execute("ALTER TABLE asset RENAME COLUMN occupied_area_sqm TO footprint_area_sqm")
    op.execute(
        "ALTER TABLE asset ADD CONSTRAINT asset_superficies_memoria_no_negativas "
        "CHECK (COALESCE(footprint_area_sqm, 0) >= 0 AND COALESCE(urbanised_area_sqm, 0) >= 0 "
        "AND COALESCE(usable_area_sqm, 0) >= 0 AND COALESCE(max_height_m, 0) >= 0)"
    )

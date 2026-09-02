"""Los datos que aporta la memoria técnica, y las zonas privadas y comunes.

Revisión: 0012
Anterior: 0011

`[REQ]` La **memoria técnica** es el documento que entrega la propiedad con
todos los datos del edificio. Hasta aquí la ficha del activo tenía la mitad de
lo que esa memoria trae: faltaban la referencia catastral, el promotor, la
fecha del proyecto, el uso secundario, la huella del edificio, la superficie
urbanizada, la útil total, la altura máxima, los muelles de carga y las plazas
de aparcamiento.

Tres de esos campos se parecen a otros que ya existían y **no son lo mismo**.
Se añaden aparte en vez de reutilizar los de al lado, que es lo que produce
números que cuadran mal y nadie sabe por qué:

* `footprint_area_sqm` (huella) no es `total_built_sqm`: ésta suma todas las
  plantas, y un edificio de cuatro alturas ocupa la cuarta parte de su
  construida.
* `usable_area_sqm` (útil) no es `lettable_area_sqm` (alquilable): la segunda
  suele llevar repercusión de zonas comunes, y confundirlas descuadra el €/m².
* `max_height_m` (del edificio) no es `warehouse_height_m` (del almacén): en
  una nave con oficinas en altillo no coinciden.

`[REQ]` Y las **zonas privadas y comunes**, que el cliente pidió por activo y
no por catálogo: «Aseos» es zona común en un edificio de oficinas
multiinquilino y privada en una nave de un solo ocupante. En el catálogo habría
un único valor para toda la organización.

`[REQ]` `memoria_validada_at` / `memoria_validada_por` son el testigo de la
revisión humana. Un dato extraído de un documento por una máquina y no revisado
**no puede parecerse** a uno tecleado por un técnico, y sin esta marca en la
base la pantalla no tendría cómo distinguirlos.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`. `test_migrar_desde_cero_produce_el_mismo_
#: esquema` compara los dos caminos de creación, así que cualquier diferencia
#: —incluido el orden de las columnas— hace fallar la suite. Es a propósito.
COLUMNAS = """\
ALTER TABLE asset
    ADD COLUMN cadastral_reference VARCHAR(30),
    ADD COLUMN developer           VARCHAR(200),
    ADD COLUMN project_date        DATE,
    ADD COLUMN secondary_use       VARCHAR(120),
    ADD COLUMN footprint_area_sqm  NUMERIC(14, 2),
    ADD COLUMN urbanised_area_sqm  NUMERIC(14, 2),
    ADD COLUMN usable_area_sqm     NUMERIC(14, 2),
    ADD COLUMN max_height_m        NUMERIC(6, 2),
    ADD COLUMN loading_docks       SMALLINT,
    ADD COLUMN parking_spaces      INTEGER,
    ADD COLUMN memoria_validada_at TIMESTAMPTZ,
    ADD COLUMN memoria_validada_por UUID REFERENCES app_user(id);
"""

RESTRICCIONES = """\
ALTER TABLE asset
    ADD CONSTRAINT asset_superficies_memoria_no_negativas
        CHECK (COALESCE(footprint_area_sqm, 0) >= 0 AND COALESCE(urbanised_area_sqm, 0) >= 0
               AND COALESCE(usable_area_sqm, 0) >= 0 AND COALESCE(max_height_m, 0) >= 0),
    ADD CONSTRAINT asset_conteos_no_negativos
        CHECK (COALESCE(loading_docks, 0) >= 0 AND COALESCE(parking_spaces, 0) >= 0),
    ADD CONSTRAINT asset_memoria_validada_completa
        CHECK ((memoria_validada_at IS NULL) = (memoria_validada_por IS NULL));
"""

ZONAS = """\
CREATE TYPE zone_tenure AS ENUM ('PRIVADA', 'COMUN');

CREATE TABLE asset_zone (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    asset_id        UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    zone_id         UUID NOT NULL REFERENCES zone(id),
    tenure          zone_tenure NOT NULL,
    area_sqm        NUMERIC(14, 2),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (asset_id, zone_id),
    CONSTRAINT asset_zone_superficie_no_negativa
        CHECK (COALESCE(area_sqm, 0) >= 0)
);

CREATE INDEX asset_zone_activo_idx ON asset_zone (asset_id);
"""


def upgrade() -> None:
    op.execute(COLUMNAS)
    op.execute(RESTRICCIONES)
    op.execute(ZONAS)
    op.execute("ALTER TABLE asset_zone ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE asset_zone FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY asset_zone_aislamiento_org ON asset_zone "
        "USING (organization_id = org_actual()) "
        "WITH CHECK (organization_id = org_actual())"
    )


def downgrade() -> None:
    """Bajar esta revisión **pierde datos del edificio**, no solo estructura.

    Se van la referencia catastral, el promotor, las superficies de la memoria
    y la clasificación de zonas privadas y comunes. Los activos siguen ahí y el
    CAPEX también; lo que desaparece es de dónde salían sus datos.
    """
    op.execute("DROP TABLE IF EXISTS asset_zone")
    op.execute("DROP TYPE IF EXISTS zone_tenure")
    op.execute(
        "ALTER TABLE asset "
        "DROP CONSTRAINT IF EXISTS asset_superficies_memoria_no_negativas, "
        "DROP CONSTRAINT IF EXISTS asset_conteos_no_negativos, "
        "DROP CONSTRAINT IF EXISTS asset_memoria_validada_completa"
    )
    op.execute(
        "ALTER TABLE asset "
        "DROP COLUMN IF EXISTS cadastral_reference, "
        "DROP COLUMN IF EXISTS developer, "
        "DROP COLUMN IF EXISTS project_date, "
        "DROP COLUMN IF EXISTS secondary_use, "
        "DROP COLUMN IF EXISTS footprint_area_sqm, "
        "DROP COLUMN IF EXISTS urbanised_area_sqm, "
        "DROP COLUMN IF EXISTS usable_area_sqm, "
        "DROP COLUMN IF EXISTS max_height_m, "
        "DROP COLUMN IF EXISTS loading_docks, "
        "DROP COLUMN IF EXISTS parking_spaces, "
        "DROP COLUMN IF EXISTS memoria_validada_at, "
        "DROP COLUMN IF EXISTS memoria_validada_por"
    )

"""Inventario de equipo y catálogo de sistemas técnicos.

Revisión: 0002
Anterior: 0001

Primera migración incremental del proyecto, y por eso conviene decir qué forma
tienen: **escritas a mano y en SQL**, no autogeneradas.

`schema.sql` sigue siendo la verdad del esquema. Esta migración lleva a una base
ya creada a ese mismo estado, y `test_migraciones.py` compara las dos rutas —
migrar desde cero contra aplicar `schema.sql`— y falla si divergen. Es decir:
**tocar `schema.sql` sin escribir aquí lo mismo rompe la suite**, que es
exactamente lo que se quiere que pase.

Qué añade:

* `technical_system`, los 14 sistemas de §3.2. Con su política de catálogo: las
  filas del sistema las ve todo el mundo, las propias solo su organización.
* `equipment` (§7 / P-15), ficha **opcional** de inventario, con aislamiento por
  organización como cualquier otra tabla con datos de cliente.

`downgrade` sí existe aquí, al contrario que en 0001: deshacer esto tira dos
tablas que nadie más referencia, no la base entera.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CATALOGO = """
CREATE TABLE technical_system (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    code            VARCHAR(40) NOT NULL,
    name_es         VARCHAR(120) NOT NULL,
    capex_chapter   VARCHAR(40),
    sort_order      INT NOT NULL DEFAULT 0,
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE NULLS NOT DISTINCT (organization_id, code)
);

ALTER TABLE technical_system ENABLE ROW LEVEL SECURITY;
ALTER TABLE technical_system FORCE ROW LEVEL SECURITY;
CREATE POLICY technical_system_catalogo ON technical_system
    USING (organization_id IS NULL OR organization_id = org_actual())
    WITH CHECK (organization_id = org_actual());
"""


INVENTARIO = """
CREATE TYPE equipment_condition AS ENUM (
    'BUENO', 'ACEPTABLE', 'DEFICIENTE', 'MUY_DEFICIENTE', 'FUERA_DE_SERVICIO'
);
CREATE TYPE equipment_obsolescence AS ENUM (
    'ACTUAL', 'PROXIMO_A_OBSOLETO', 'OBSOLETO', 'SIN_REPUESTOS'
);
CREATE TYPE equipment_criticality AS ENUM ('ALTA', 'MEDIA', 'BAJA');

CREATE TABLE equipment (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organization(id),
    project_id          UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    asset_id            UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    technical_system_id UUID REFERENCES technical_system(id),
    zone_id             UUID REFERENCES zone(id),

    tag                 VARCHAR(40),
    equipment_type      VARCHAR(120) NOT NULL CHECK (length(trim(equipment_type)) > 0),
    manufacturer        VARCHAR(120),
    model               VARCHAR(120),
    serial_number       VARCHAR(120),

    install_year        SMALLINT CHECK (install_year IS NULL OR install_year BETWEEN 1800 AND 2200),
    expected_life_years SMALLINT CHECK (expected_life_years IS NULL OR expected_life_years > 0),
    end_of_life_year    SMALLINT GENERATED ALWAYS AS (install_year + expected_life_years) STORED,

    condition           equipment_condition,
    obsolescence        equipment_obsolescence,
    criticality         equipment_criticality,

    quantity            NUMERIC(12, 2) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit                VARCHAR(20) NOT NULL DEFAULT 'ud',
    has_documentation   BOOLEAN NOT NULL DEFAULT FALSE,
    notes               TEXT,

    search_vector       TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('spanish'::regconfig,
            coalesce(tag, '') || ' ' || equipment_type || ' ' ||
            coalesce(manufacturer, '') || ' ' || coalesce(model, '') || ' ' ||
            coalesce(serial_number, '') || ' ' || coalesce(notes, ''))
    ) STORED,

    created_by          UUID NOT NULL REFERENCES app_user(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ,

    CONSTRAINT vida_util_completa_o_ausente CHECK (
        (install_year IS NULL AND expected_life_years IS NULL)
        OR (install_year IS NOT NULL AND expected_life_years IS NOT NULL)
    )
);
CREATE INDEX equipment_activo_idx ON equipment (project_id, asset_id);
CREATE INDEX equipment_sistema_idx ON equipment (asset_id, technical_system_id);
CREATE INDEX equipment_busqueda_idx ON equipment USING GIN (search_vector);
CREATE UNIQUE INDEX equipment_etiqueta_uniq
    ON equipment (asset_id, tag) WHERE tag IS NOT NULL AND deleted_at IS NULL;

ALTER TABLE equipment ENABLE ROW LEVEL SECURITY;
ALTER TABLE equipment FORCE ROW LEVEL SECURITY;
CREATE POLICY equipment_aislamiento_org ON equipment
    USING (organization_id = org_actual())
    WITH CHECK (organization_id = org_actual());
"""


def upgrade() -> None:
    """Crea las dos tablas.

    **Los permisos no se dan aquí.** El nombre del rol de aplicación es una
    decisión del despliegue, no del esquema, y escribirlo en una migración la
    ataría a un entorno concreto: en la base de pruebas, donde todo corre como
    superusuario, ese `GRANT` fallaría. De los permisos se encarga `make
    db-grant`, que `db-migrate` invoca al terminar.
    """
    op.execute(CATALOGO)
    op.execute(INVENTARIO)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS equipment")
    op.execute("DROP TYPE IF EXISTS equipment_criticality")
    op.execute("DROP TYPE IF EXISTS equipment_obsolescence")
    op.execute("DROP TYPE IF EXISTS equipment_condition")
    op.execute("DROP TABLE IF EXISTS technical_system")

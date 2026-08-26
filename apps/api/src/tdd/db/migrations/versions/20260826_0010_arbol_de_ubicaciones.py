"""El árbol físico del edificio: `location_node`.

Revisión: 0010
Anterior: 0009

`[REC]` §8.4 · Para asociar una fotografía a su planta y a su sala hace falta
un árbol. Hasta aquí solo existía `zone`, el catálogo normalizado, y eso deja
sin responder la pregunta que se hace seis meses después: **¿dónde estaba
exactamente esto?**

`zone` y `location_node` son cosas distintas y las dos hacen falta. `zone` es la
clasificación que exige el CAPEX —«Cubierta», «Cuartos Técnicos»—, común a todos
los proyectos, y es lo que permite agregar en el informe. `location_node` es la
ubicación concreta de **este** edificio: «Cubierta / Sala de máquinas 2».
Fundirlas obligaría a elegir entre agregar por zona o localizar una foto.

Es un árbol y no tres tablas rígidas porque los edificios no se dejan: una nave
tiene muelles sin planta, y un hotel tiene plantas dentro de plantas.

`[REQ]` §10 · `photo.location_node_id` es lo que rellena el token `[Espacio]`
del renombrado en lote, que hasta ahora se omitía **siempre**: la plantilla por
defecto lo pide y no había de dónde sacarlo.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`. `test_migrar_desde_cero_produce_el_mismo_
#: esquema` compara el texto que PostgreSQL guarda de cada función, así que una
#: sangría distinta ya es una diferencia. Es a propósito.
ARBOL = """\
CREATE TYPE location_node_type AS ENUM ('ZONA', 'PLANTA', 'ESPACIO');

CREATE TABLE location_node (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    asset_id        UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    parent_id       UUID REFERENCES location_node(id) ON DELETE CASCADE,
    node_type       location_node_type NOT NULL,

    -- El enlace con el catálogo, opcional. Un nodo de tipo ZONA suele apuntar
    -- a su `zone`; una sala concreta no tiene por qué.
    zone_id         UUID REFERENCES zone(id),
    code            VARCHAR(60),
    name            VARCHAR(160) NOT NULL,
    level_order     SMALLINT NOT NULL DEFAULT 0,

    -- La ruta la calcula el disparador `location_node_ruta`, nunca la
    -- aplicación: una ruta escrita a mano que no case con `parent_id` produce
    -- un árbol que se lee distinto según por dónde se mire.
    path            LTREE NOT NULL,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,

    CONSTRAINT location_node_no_es_su_propio_padre CHECK (parent_id IS DISTINCT FROM id),
    CONSTRAINT location_node_con_nombre CHECK (length(trim(name)) > 0)
);

CREATE INDEX location_node_activo_idx ON location_node (asset_id, node_type);
CREATE INDEX location_node_path_idx ON location_node USING GIST (path);
-- Dos espacios con el mismo nombre bajo el mismo padre serían indistinguibles
-- en el desplegable y en el nombre del fichero. `lower` porque «Sala 1» y
-- «sala 1» son el mismo sitio para quien los escribe.
-- `NULLS NOT DISTINCT` es imprescindible, igual que en `asset_assignment`:
-- sin él, dos raíces tienen `parent_id` NULL, dos NULL se consideran distintos
-- y el mismo activo admitiría dos «Cubierta» de primer nivel.
CREATE UNIQUE INDEX location_node_hermanos_uniq
    ON location_node (asset_id, parent_id, lower(name))
    NULLS NOT DISTINCT
    WHERE deleted_at IS NULL;

--  La etiqueta de `ltree` sale del `id`: solo admite [A-Za-z0-9_], así que un
--  nombre como «Sala de máquinas 2» no vale, y el `code` es opcional. Con el
--  `id` la ruta es estable aunque se renombre el nodo.
CREATE OR REPLACE FUNCTION location_node_ruta() RETURNS TRIGGER AS $$
DECLARE ruta_padre LTREE;
BEGIN
    IF NEW.parent_id IS NULL THEN
        NEW.path := text2ltree(replace(NEW.id::TEXT, '-', '_'));
    ELSE
        SELECT path INTO ruta_padre FROM location_node WHERE id = NEW.parent_id;
        IF ruta_padre IS NULL THEN
            RAISE EXCEPTION 'El nodo padre % no existe', NEW.parent_id
                USING ERRCODE = 'foreign_key_violation';
        END IF;
        -- Un ciclo dejaría el árbol irrecorrible y la consulta de descendientes
        -- en un bucle infinito. La clave ajena no lo impide: A puede ser padre
        -- de B y B de A sin violarla.
        IF ruta_padre OPERATOR(public.<@) text2ltree(replace(NEW.id::TEXT, '-', '_')) THEN
            RAISE EXCEPTION 'Ese movimiento metería el nodo dentro de sí mismo'
                USING ERRCODE = 'raise_exception';
        END IF;
        NEW.path := ruta_padre OPERATOR(public.||) text2ltree(replace(NEW.id::TEXT, '-', '_'));
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER location_node_ruta
    BEFORE INSERT OR UPDATE OF parent_id ON location_node
    FOR EACH ROW EXECUTE FUNCTION location_node_ruta();
"""


def upgrade() -> None:
    op.execute(ARBOL)
    op.execute(
        "ALTER TABLE photo ADD COLUMN location_node_id UUID "
        "REFERENCES location_node(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE location_node ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE location_node FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY location_node_aislamiento_org ON location_node "
        "USING (organization_id = org_actual()) "
        "WITH CHECK (organization_id = org_actual())"
    )


def downgrade() -> None:
    """Bajar esta revisión pierde el árbol y la ubicación de cada foto.

    Las fotos no se tocan: lo que se pierde es en qué sala estaba cada una, y
    el token `[Espacio]` vuelve a omitirse como antes.
    """
    op.execute("ALTER TABLE photo DROP COLUMN IF EXISTS location_node_id")
    op.execute("DROP TRIGGER IF EXISTS location_node_ruta ON location_node")
    op.execute("DROP FUNCTION IF EXISTS location_node_ruta()")
    op.execute("DROP TABLE IF EXISTS location_node")
    op.execute("DROP TYPE IF EXISTS location_node_type")

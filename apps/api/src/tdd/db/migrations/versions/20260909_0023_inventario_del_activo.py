"""El inventario del activo: «pasa a CAPEX», la foto del equipo y los descriptivos.

Revisión: 0023
Anterior: 0022

Las tres piezas de §3.2 d de `docs/23`, y las tres son **añadir**: ninguna
columna existente cambia de tipo ni de significado, así que esto se aplica sobre
una base con datos sin tocar una sola fila.

**1 · `equipment.pasa_a_capex`.** La casilla que pidió el cliente por equipo o
sistema. Es una marca del inventario y **no crea nada al marcarla**: el gestor
marca lo que ve durante la visita y después genera de una vez las actuaciones de
todo lo marcado. Crear el hallazgo al pulsar habría llenado el CAPEX de filas
vacías cada vez que alguien se equivoca de casilla, y borrarlas después es peor
que no haberlas creado.

**2 · `photo.equipment_id`.** Vincular las fotografías de la visita a cada
equipo. `ON DELETE SET NULL` y no `CASCADE`: borrar un equipo del inventario no
puede borrar la fotografía que lo documenta, que es evidencia de la visita y
puede estar ya en un informe emitido.

**3 · `descriptivo_objeto`.** El descriptivo de cada objeto de Hard Cost que se
encuentre en la documentación, pendiente de validar por el gestor técnico,
editable y con su casilla de validado.

Tabla propia y no un campo de `memoria_objeto`, aunque ahí es de donde sale el
texto la primera vez. Son dos cosas con dos ciclos de vida: `memoria_objeto` es
**lo que la memoria enumeró** y se rehace entera cada vez que se vuelve a
extraer el documento; el descriptivo es **texto del gestor técnico**, que lo
corrige y lo firma. Guardarlo en la misma fila significaría perder el trabajo de
una persona cada vez que se refresca el de una máquina.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan en
#: `test_migraciones.py`, así que esto no puede ser una versión parecida.
PASA_A_CAPEX = """\
ALTER TABLE equipment
    ADD COLUMN pasa_a_capex BOOLEAN NOT NULL DEFAULT FALSE
"""

FOTO_DEL_EQUIPO = """\
ALTER TABLE photo
    ADD COLUMN equipment_id UUID REFERENCES equipment(id) ON DELETE SET NULL
"""

INDICE_DE_FOTO = "CREATE INDEX photo_equipo_idx   ON photo (equipment_id)"

DESCRIPTIVOS = """\
CREATE TABLE descriptivo_objeto (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    asset_id        UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    -- Nivel 3 del árbol. Que lo sea lo comprueba la API y lo cubre una prueba,
    -- igual que en `memoria_categoria`: un CHECK aquí exigiría un disparador
    -- que consulte otra tabla en cada escritura.
    capex_code_id   UUID NOT NULL REFERENCES capex_code(id),

    -- El texto. Arranca con lo que se encontró en la documentación y lo edita
    -- quien valida.
    texto           TEXT NOT NULL DEFAULT '',

    -- [REQ] De dónde salió, y si la extracción fue de mentira. Misma regla que
    -- en la memoria y en la revisión documental: una extracción simulada no
    -- puede pasar por una de verdad ni en la base ni en la pantalla.
    document_id     UUID REFERENCES document(id) ON DELETE SET NULL,
    origen          VARCHAR(60),
    es_simulada     BOOLEAN NOT NULL DEFAULT TRUE,

    -- [REQ] La validación del gestor técnico. Mientras `validado_at` sea nulo,
    -- la pantalla lo dice y el texto no se puede dar por bueno.
    validado_at     TIMESTAMPTZ,
    validado_por    UUID REFERENCES app_user(id),

    created_by      UUID NOT NULL REFERENCES app_user(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_version     INTEGER NOT NULL DEFAULT 1,
    updated_by      UUID REFERENCES app_user(id),

    UNIQUE (asset_id, capex_code_id),
    -- Ni validado sin testigo ni testigo sin validación: son la misma
    -- afirmación dicha dos veces y tienen que coincidir.
    CONSTRAINT descriptivo_validado_completo
        CHECK ((validado_at IS NULL) = (validado_por IS NULL)),
    -- Un descriptivo validado y vacío no significa nada: alguien habría firmado
    -- una casilla en blanco.
    CONSTRAINT descriptivo_validado_no_vacio
        CHECK (validado_at IS NULL OR length(trim(texto)) > 0)
);
"""

INDICE_DESCRIPTIVOS = "CREATE INDEX descriptivo_objeto_activo_idx ON descriptivo_objeto (asset_id)"

#: La misma política de aislamiento y el mismo disparador de versión que llevan
#: las demás tablas con `organization_id`. Van aquí y no en un `FOREACH` como en
#: `schema.sql` porque aquí solo hay una tabla que tratar.
RLS = """\
ALTER TABLE descriptivo_objeto ENABLE ROW LEVEL SECURITY;
ALTER TABLE descriptivo_objeto FORCE ROW LEVEL SECURITY;
CREATE POLICY descriptivo_objeto_aislamiento_org ON descriptivo_objeto
    USING (organization_id = org_actual())
    WITH CHECK (organization_id = org_actual());
CREATE TRIGGER descriptivo_objeto_version
    BEFORE UPDATE ON descriptivo_objeto
    FOR EACH ROW EXECUTE FUNCTION marcar_version_y_autor()
"""


def upgrade() -> None:
    op.execute(PASA_A_CAPEX)
    op.execute(FOTO_DEL_EQUIPO)
    op.execute(INDICE_DE_FOTO)
    op.execute(DESCRIPTIVOS)
    op.execute(INDICE_DESCRIPTIVOS)
    op.execute(RLS)


def downgrade() -> None:
    op.execute("DROP TABLE descriptivo_objeto")
    op.execute("ALTER TABLE photo DROP COLUMN equipment_id")
    op.execute("ALTER TABLE equipment DROP COLUMN pasa_a_capex")

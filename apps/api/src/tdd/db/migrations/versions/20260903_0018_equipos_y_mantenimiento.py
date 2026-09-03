"""El mantenimiento preventivo, y los medios que declara un documento.

Revisión: 0018
Anterior: 0017

Dos cosas que van juntas porque salen del mismo documento.

**1 · A `equipment` le faltaba el mantenimiento preventivo.**

La ficha de equipo llevaba año de instalación, vida esperada, estado,
obsolescencia y criticidad. No llevaba **cada cuánto se revisa ni cuándo se
revisó por última vez**, que es lo primero que se pregunta de una instalación de
protección contra incendios: no «cuántos extintores hay» sino «cuándo se
revisaron». Sin eso, el inventario describe el edificio y no dice nada sobre si
está mantenido.

En **meses** y no un enumerado de periodicidades. Un plan de autoprotección
habla de revisiones trimestrales, semestrales, anuales y quinquenales —3, 6, 12
y 60—, pero un contrato de mantenimiento puede decir «cada cuatro meses», y un
enumerado obligaría a redondear al valor de al lado o a ampliarlo cada vez que
apareciera uno nuevo. Un entero ordena solo y admite cualquiera.

`next_maintenance_due` se **genera**, igual que `end_of_life_year` y por la
misma razón: lo que se guarda no caduca y lo derivado no se teclea. Lo que **no**
se genera es «está vencido», porque eso depende del día de hoy: se compara con
`current_date` en la consulta.

**2 · `propuesta_de_equipo`: los medios que un documento enumera.**

El capítulo 4 de la Norma Básica lista los medios del edificio. Teclearlos a
mano después de que un documento los liste es el trabajo repetido que el cliente
pidió evitar.

No lleva activo: un plan cubre un complejo de seis naves y dice «dieciséis
hidrantes distribuidos por el perímetro» sin decir de cuál son. El activo lo
elige **quien acepta**. Y la cantidad puede ser nula, porque «rociadores sobre
la superficie de almacenamiento» no trae número y poner un 1 por omisión metería
un uno en un inventario que alguien va a leer como cierto.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan.
MANTENIMIENTO = """\
ALTER TABLE equipment
    ADD COLUMN maintenance_months SMALLINT
        CHECK (maintenance_months IS NULL OR maintenance_months > 0),
    ADD COLUMN last_maintenance_date DATE
        CHECK (last_maintenance_date IS NULL OR last_maintenance_date <= CURRENT_DATE + 1),
    ADD COLUMN next_maintenance_due DATE GENERATED ALWAYS AS (
        (last_maintenance_date + make_interval(months => maintenance_months))::date
    ) STORED;
"""

PROPUESTAS_DE_EQUIPO = """\
CREATE TABLE propuesta_de_equipo (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    project_id      UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,

    technical_system_id UUID REFERENCES technical_system(id),
    equipment_type  VARCHAR(120) NOT NULL CHECK (length(trim(equipment_type)) > 0),
    quantity        NUMERIC(12, 2) CHECK (quantity IS NULL OR quantity > 0),
    unit            VARCHAR(20) NOT NULL DEFAULT 'ud',
    descripcion     TEXT,

    document_id     UUID REFERENCES document(id) ON DELETE SET NULL,
    doc_type        doc_type NOT NULL,
    seccion         VARCHAR(160),
    evidencia       TEXT,
    extractor       VARCHAR(60) NOT NULL,
    es_simulada     BOOLEAN NOT NULL DEFAULT TRUE,

    estado          propuesta_estado NOT NULL DEFAULT 'PENDIENTE',
    decidida_at     TIMESTAMPTZ,
    decidida_por    UUID REFERENCES app_user(id),
    equipment_id    UUID REFERENCES equipment(id) ON DELETE SET NULL,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE NULLS NOT DISTINCT (document_id, equipment_type),

    CONSTRAINT propuesta_equipo_decidida_completa
        CHECK ((decidida_at IS NULL) = (decidida_por IS NULL)),
    CONSTRAINT propuesta_equipo_resuelta_tiene_testigo
        CHECK (estado = 'PENDIENTE' OR decidida_at IS NOT NULL),
    CONSTRAINT propuesta_equipo_aceptada_tiene_equipo
        CHECK ((estado = 'ACEPTADA') = (equipment_id IS NOT NULL))
);

CREATE INDEX propuesta_equipo_encargo_idx ON propuesta_de_equipo (project_id, estado);
CREATE INDEX propuesta_equipo_documento_idx ON propuesta_de_equipo (document_id);
"""


def upgrade() -> None:
    op.execute(MANTENIMIENTO)
    op.execute(PROPUESTAS_DE_EQUIPO)
    op.execute("ALTER TABLE propuesta_de_equipo ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE propuesta_de_equipo FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY propuesta_de_equipo_aislamiento_org ON propuesta_de_equipo "
        "USING (organization_id = org_actual()) "
        "WITH CHECK (organization_id = org_actual())"
    )


def downgrade() -> None:
    """Bajar esta revisión pierde el mantenimiento de los equipos.

    Las tres columnas se van con sus datos: cada cuánto se revisa un equipo y
    cuándo se revisó por última vez son datos que alguien tecleó y que no se
    pueden reconstruir. Se dice aquí en vez de fingir que la bajada es inocua.
    """
    op.execute("DROP TABLE IF EXISTS propuesta_de_equipo")
    op.execute(
        "ALTER TABLE equipment "
        "DROP COLUMN IF EXISTS next_maintenance_due, "
        "DROP COLUMN IF EXISTS last_maintenance_date, "
        "DROP COLUMN IF EXISTS maintenance_months"
    )

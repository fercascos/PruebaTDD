"""La visita del activo: punto de encuentro, coste y quién fue.

Revisión: 0024
Anterior: 0023

§3.2 c de `docs/23`, con la hoja del cliente delante. Casi todo lo que pide esa
sección **ya existía** en `asset_visit` —estado, fecha prevista, fecha real,
quién la dirigió, limitaciones de acceso y resumen—, así que esto es lo poco que
faltaba. Todo es **añadir**: ninguna columna existente cambia, y se aplica sobre
una base con visitas ya registradas sin tocar una fila.

**1 · `asset_visit.meeting_point`.** La «Ubicación» de la hoja. No repite la
dirección del activo, que ya está en `asset` con sus coordenadas y su mapa: es
el punto de encuentro y lo que hace falta saber el día de la visita —«entrada
por el muelle 4, preguntar por el jefe de mantenimiento»—.

**2 · `asset_visit.cost_amount`.** «Costes visita: indicar monto económico total
de la visita si es que tiene».

Es **coste interno del encargo**, decidido por el cliente: no entra en el CAPEX
ni sale en el informe. Los desplazamientos y las horas del consultor no son
coste del edificio, y colarlos en los soft costs inflaría la cifra con la que el
inversor negocia el precio de compra. Que no salga lo fija una prueba sobre el
snapshot del informe, no solo este comentario.

**3 · `visit_attendee`.** El «Equipo implicado», que en la hoja son cuatro
casillas de «Responsable». Cuatro es lo que cabía en una hoja de cálculo, no lo
que va a una visita: aquí es una lista sin tope.

Y son dos cosas en la misma lista. El **equipo** son usuarios de la aplicación,
con clave ajena, que es lo que permite preguntar «qué activos visitó cada uno» y
firmar lo que cada uno escribe. Quien **acompaña** —el jefe de mantenimiento, el
property manager, el mantenedor de PCI— no tiene cuenta y nunca la va a tener, y
perderlo sería perder a quien abrió el cuarto de máquinas: justo la persona a la
que se vuelve a llamar seis meses después. Un `CHECK` obliga a que cada fila sea
una cosa o la otra, nunca las dos ni ninguna.

**`asset_visit` gana además `updated_at`**, que no tenía. Hasta ahora la tabla
solo se leía y se actualizaba a mano; con el coste y el punto de encuentro
editables desde la pantalla, no saber cuándo se tocó una visita por última vez
es perder el rastro de un dato que va al informe.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan en
#: `test_migraciones.py`, así que esto no puede ser una versión parecida.
COLUMNAS_DE_VISITA = """\
ALTER TABLE asset_visit
    ADD COLUMN meeting_point TEXT,
    ADD COLUMN cost_amount   NUMERIC(12,2) CHECK (cost_amount IS NULL OR cost_amount >= 0),
    ADD COLUMN updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
"""

INDICE_POR_ACTIVO = """\
CREATE INDEX asset_visit_activo_idx ON asset_visit (asset_id, scheduled_date DESC)
"""

ASISTENTES = """\
CREATE TABLE visit_attendee (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    asset_visit_id  UUID NOT NULL REFERENCES asset_visit(id) ON DELETE CASCADE,

    -- Una de las dos y solo una. Un asistente es del equipo o es de fuera.
    app_user_id     UUID REFERENCES app_user(id),
    external_name   VARCHAR(200),

    -- En calidad de qué vino. Vale para los dos: «responsable de la visita»,
    -- «jefe de mantenimiento», «mantenedor de PCI».
    role_note       VARCHAR(200),
    display_order   SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT asistente_es_del_equipo_o_de_fuera
        CHECK ((app_user_id IS NULL) <> (external_name IS NULL)),
    -- Un nombre en blanco deja una fila que ocupa sitio y no dice nada.
    CONSTRAINT asistente_externo_con_nombre
        CHECK (external_name IS NULL OR length(trim(external_name)) > 0)
);
"""

INDICES_DE_ASISTENTE = """\
CREATE UNIQUE INDEX visit_attendee_usuario_uniq
    ON visit_attendee (asset_visit_id, app_user_id) WHERE app_user_id IS NOT NULL;
CREATE INDEX visit_attendee_visita_idx ON visit_attendee (asset_visit_id, display_order);
"""

#: La misma política de aislamiento que llevan las demás tablas con
#: `organization_id`. Sin disparador de versión: `visit_attendee` no tiene
#: `row_version` —una línea de asistente se añade y se quita, no se edita en
#: concurrencia—, igual que `asset_visit`.
RLS = """\
ALTER TABLE visit_attendee ENABLE ROW LEVEL SECURITY;
ALTER TABLE visit_attendee FORCE ROW LEVEL SECURITY;
CREATE POLICY visit_attendee_aislamiento_org ON visit_attendee
    USING (organization_id = org_actual())
    WITH CHECK (organization_id = org_actual())
"""


def upgrade() -> None:
    op.execute(COLUMNAS_DE_VISITA)
    op.execute(INDICE_POR_ACTIVO)
    op.execute(ASISTENTES)
    op.execute(INDICES_DE_ASISTENTE)
    op.execute(RLS)


def downgrade() -> None:
    """`[LIM]` Se pierde quién fue a cada visita y cuánto costó.

    No hay forma de conservarlo: los asistentes viven solo en la tabla que se
    borra. Se avisa en vez de fingir que la vuelta atrás es gratis.
    """
    op.execute("DROP TABLE visit_attendee")
    op.execute("DROP INDEX asset_visit_activo_idx")
    op.execute(
        "ALTER TABLE asset_visit "
        "  DROP COLUMN meeting_point, DROP COLUMN cost_amount, DROP COLUMN updated_at"
    )

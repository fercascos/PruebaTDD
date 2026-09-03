"""Lo que la documentación propone, con su procedencia.

Revisión: 0016
Anterior: 0015

`[REQ]` La idea del cliente, con sus palabras: **según se va subiendo
documentación, el cuadro de CAPEX se va completando solo, y el gestor de la due
diligence valida después**.

Eso obliga a un cambio que con un solo documento no se veía. Hasta aquí la
propuesta vivía en `memoria_tecnica.propuesta`, un JSONB plano. Con la memoria
técnica sola bastaba. Con dos documentos, no:

* el segundo **pisaba** al primero, sin dejar rastro de que había habido otro;
* y una vez pisado, nadie podía saber **de qué documento salió cada cifra**.

Un número huérfano en la ficha de un activo no se puede defender ante el
cliente. El gestor tendría que volver a comprobarlo todo contra los PDF, que es
justo el trabajo que la extracción venía a ahorrar.

Así que una propuesta pasa a ser una fila con:

* **de dónde sale**: documento, tipo, sección y el fragmento **literal**;
* **quién la produjo** y si era simulado;
* **en qué estado está**: pendiente, aceptada o descartada, con su testigo.

Y dos documentos pueden proponer valores distintos para el mismo campo. No es
un caso raro: una memoria de proyecto y un plan de autoprotección redactados
con años de diferencia dan superficies que no coinciden, y **el desacuerdo es
información**, no un error que haya que resolver en silencio.

`[LIM]` Esta revisión **no migra** el contenido de `memoria_tecnica.propuesta`.
Se queda donde está y se sigue leyendo: la ruta antigua funciona igual. Vaciarlo
exigiría inventarle una procedencia a datos que se guardaron sin ella, y una
procedencia inventada es peor que ninguna.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan.
PROPUESTAS = """\
CREATE TYPE propuesta_estado AS ENUM ('PENDIENTE', 'ACEPTADA', 'DESCARTADA');

CREATE TABLE propuesta_de_dato (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    asset_id        UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,

    campo           VARCHAR(60) NOT NULL,
    valor           TEXT NOT NULL,

    document_id     UUID REFERENCES document(id) ON DELETE SET NULL,
    doc_type        doc_type NOT NULL,
    seccion         VARCHAR(160),
    evidencia       TEXT,
    extractor       VARCHAR(60) NOT NULL,
    es_simulada     BOOLEAN NOT NULL DEFAULT TRUE,

    estado          propuesta_estado NOT NULL DEFAULT 'PENDIENTE',
    decidida_at     TIMESTAMPTZ,
    decidida_por    UUID REFERENCES app_user(id),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE NULLS NOT DISTINCT (asset_id, campo, document_id),

    CONSTRAINT propuesta_decidida_completa
        CHECK ((decidida_at IS NULL) = (decidida_por IS NULL)),
    CONSTRAINT propuesta_resuelta_tiene_testigo
        CHECK (estado = 'PENDIENTE' OR decidida_at IS NOT NULL)
);

CREATE INDEX propuesta_activo_idx ON propuesta_de_dato (asset_id, estado);
CREATE INDEX propuesta_documento_idx ON propuesta_de_dato (document_id);
"""


def upgrade() -> None:
    op.execute(PROPUESTAS)
    op.execute("ALTER TABLE propuesta_de_dato ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE propuesta_de_dato FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY propuesta_de_dato_aislamiento_org ON propuesta_de_dato "
        "USING (organization_id = org_actual()) "
        "WITH CHECK (organization_id = org_actual())"
    )


def downgrade() -> None:
    """Bajar esta revisión pierde las propuestas y su procedencia.

    Lo que ya se hubiera **aceptado** sigue en el activo: eso son columnas de
    `asset` y no se tocan. Lo que desaparece es de qué documento salió cada
    dato, que es exactamente lo que esta revisión venía a conservar.
    """
    op.execute("DROP TABLE IF EXISTS propuesta_de_dato")
    op.execute("DROP TYPE IF EXISTS propuesta_estado")

"""Lo que un documento dice sobre su propia fiabilidad.

Revisión: 0017
Anterior: 0016

`[REQ]` La **tercera clase de limitación** del informe, y la que faltaba.

Las dos que ya había salen de lo que **no llegó**: una línea de la checklist sin
recibir y una pregunta sin respuesta del cliente. Las dos comparten forma —falta
algo— y las dos se calculaban solas.

Ésta es lo contrario. El documento **llegó**, la casilla está marcada, el
expediente parece completo, y el documento dice que no se puede confiar en él.

El caso que lo hizo evidente, leyendo uno de verdad: un plan de autoprotección
redactado **con las naves vacías** define los recorridos de evacuación
suponiendo espacios diáfanos. En cuanto entra un inquilino con estanterías, esas
longitudes, salidas y capacidades dejan de ser las que dice el plan. El
documento está entregado y completo. La limitación solo la ve quien se lo lee
entero, y en un encargo con doscientos documentos eso no ocurre.

Dos decisiones que no son evidentes:

* **Cuelga del encargo, no del activo.** Un plan cubre un complejo de seis
  naves; una reserva sobre la evacuación no es de una nave concreta. El alcance
  del informe es el encargo, y ahí es donde la limitación tiene que aparecer.
  `asset_id` queda como opcional para cuando sí se sepa.
* **Nada llega al informe sin que una persona lo acepte.** Mismo ciclo que una
  propuesta de dato. Una limitación inventada por una máquina y colada en un
  entregable es peor que una que falte: la que falta se echa en falta; la
  inventada se firma.

Y se añade `PLAN_AUTOPROTECCION` al enumerado de tipos de documento. `[LIM]`
Añadir un valor a un `ENUM` de PostgreSQL **no se puede deshacer** sin recrear
el tipo: ver `downgrade()`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: `[REQ]` El valor se añade **al final** del enumerado. Insertarlo en medio con
#: `BEFORE` cambiaría el orden de clasificación del tipo, y `schema.sql` lo crea
#: en el orden en que están escritos: los dos caminos de creación dejarían de
#: coincidir y `test_migraciones` lo diría.
TIPO_NUEVO = "ALTER TYPE doc_type ADD VALUE IF NOT EXISTS 'PLAN_AUTOPROTECCION'"

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan.
LIMITACIONES = """\
CREATE TYPE limitacion_motivo AS ENUM (
    'CADUCADO',
    'INCOMPLETO',
    'NO_VIGENTE',
    'DECLARADA',
    'INCONSISTENTE'
);

CREATE TABLE limitacion_de_documento (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    project_id      UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    asset_id        UUID REFERENCES asset(id) ON DELETE SET NULL,

    texto           TEXT NOT NULL,
    motivo          limitacion_motivo NOT NULL,

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

    UNIQUE NULLS NOT DISTINCT (document_id, texto),

    CONSTRAINT limitacion_decidida_completa
        CHECK ((decidida_at IS NULL) = (decidida_por IS NULL)),
    CONSTRAINT limitacion_resuelta_tiene_testigo
        CHECK (estado = 'PENDIENTE' OR decidida_at IS NOT NULL)
);

CREATE INDEX limitacion_encargo_idx ON limitacion_de_documento (project_id, estado);
CREATE INDEX limitacion_documento_idx ON limitacion_de_documento (document_id);
"""


def upgrade() -> None:
    # `ALTER TYPE ... ADD VALUE` va en su propia transacción implícita en las
    # versiones antiguas de PostgreSQL. Desde la 12 se puede en la misma, y la
    # aplicación exige 16, así que no hace falta trocearlo.
    op.execute(TIPO_NUEVO)
    op.execute(LIMITACIONES)
    op.execute("ALTER TABLE limitacion_de_documento ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE limitacion_de_documento FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY limitacion_de_documento_aislamiento_org ON limitacion_de_documento "
        "USING (organization_id = org_actual()) "
        "WITH CHECK (organization_id = org_actual())"
    )


def downgrade() -> None:
    """Bajar esta revisión pierde las limitaciones documentales.

    `[LIM]` **El valor del enumerado se queda.** PostgreSQL no sabe quitar un
    valor de un `ENUM`: haría falta recrear el tipo y reescribir todas las
    columnas que lo usan, con la base parada, y si algún documento ya está
    clasificado como `PLAN_AUTOPROTECCION` habría que decidir qué hacer con él.
    Un `downgrade` que borre documentos del cliente para poder completarse no es
    un `downgrade`: es una pérdida de datos con otro nombre. Se deja el valor,
    que es inocuo, y se dice aquí en vez de fingir que la bajada es simétrica.
    """
    op.execute("DROP TABLE IF EXISTS limitacion_de_documento")
    op.execute("DROP TYPE IF EXISTS limitacion_motivo")

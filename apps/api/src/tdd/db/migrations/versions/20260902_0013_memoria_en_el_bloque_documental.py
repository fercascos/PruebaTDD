"""La memoria técnica como pieza del bloque de documentación.

Revisión: 0013
Anterior: 0012

`[REQ]` La 0012 añadió al activo los datos que la memoria aporta. Ésta añade la
memoria **como documento**: de dónde salieron esos datos, quién los dio por
buenos, y el listado de categorías del CAPEX con sus objetos que es lo que
después genera el esqueleto.

Tres decisiones que conviene tener escritas:

1. **`MEMORIA_TECNICA` es un tipo de documento propio**, no una `FICHA_TECNICA`
   más. Es el único documento del que la aplicación extrae datos hacia la ficha
   del activo y hacia el CAPEX, y distinguirlo por tipo es lo que permite
   ofrecer la extracción solo donde tiene sentido.

2. **Lo que se guarda es lo que dice la memoria, no lo que acabe siendo el
   CAPEX.** Son cosas distintas: el gestor añade objetos que la memoria no
   contemplaba y descarta otros que sí venían. Fundirlas dejaría sin respuesta
   la pregunta que se hace en la defensa del informe: «¿esto estaba en la
   memoria del edificio o lo viste tú en la visita?».

3. **Nada se da por bueno solo.** `validada_at` / `validada_por` son el testigo
   de que una persona miró lo que la extracción propuso. Es la regla que puso
   el cliente: se extrae, se previsualiza y se acepta con un botón. Un clic, no
   un tecleo — pero un clic de alguien.

`[LIM]` La extracción todavía **no está construida**: falta el proveedor y falta
un ejemplo real de memoria contra el que escribirla. Lo que entra aquí es dónde
guardar el resultado y el estado que lo describe.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copia literal de `schema.sql`: los dos caminos de creación se comparan.
MEMORIA = """\
CREATE TYPE memoria_status AS ENUM ('SIN_DOCUMENTO', 'EXTRAIDA', 'VALIDADA');

CREATE TABLE memoria_tecnica (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    asset_id        UUID NOT NULL UNIQUE REFERENCES asset(id) ON DELETE CASCADE,
    document_id     UUID REFERENCES document(id) ON DELETE SET NULL,
    status          memoria_status NOT NULL DEFAULT 'SIN_DOCUMENTO',

    origen          VARCHAR(60),
    es_simulada     BOOLEAN NOT NULL DEFAULT TRUE,
    extraida_at     TIMESTAMPTZ,

    propuesta       JSONB NOT NULL DEFAULT '{}'::jsonb,

    validada_at     TIMESTAMPTZ,
    validada_por    UUID REFERENCES app_user(id),

    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_version     INTEGER NOT NULL DEFAULT 1,
    updated_by      UUID REFERENCES app_user(id),

    CONSTRAINT memoria_validada_completa
        CHECK ((validada_at IS NULL) = (validada_por IS NULL)),
    CONSTRAINT memoria_estado_coherente
        CHECK (status <> 'VALIDADA' OR validada_at IS NOT NULL),
    CONSTRAINT memoria_extraida_tiene_fecha
        CHECK (status = 'SIN_DOCUMENTO' OR extraida_at IS NOT NULL)
);

CREATE TABLE memoria_categoria (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    memoria_id      UUID NOT NULL REFERENCES memoria_tecnica(id) ON DELETE CASCADE,
    capex_code_id   UUID NOT NULL REFERENCES capex_code(id),
    notes           TEXT,
    orden           SMALLINT NOT NULL DEFAULT 0,
    UNIQUE (memoria_id, capex_code_id)
);

CREATE INDEX memoria_categoria_memoria_idx ON memoria_categoria (memoria_id, orden);

CREATE TABLE memoria_objeto (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id      UUID NOT NULL REFERENCES organization(id),
    memoria_categoria_id UUID NOT NULL REFERENCES memoria_categoria(id) ON DELETE CASCADE,
    capex_code_id        UUID REFERENCES capex_code(id),
    nombre               VARCHAR(240) NOT NULL,
    cantidad             NUMERIC(14, 2),
    unidad               VARCHAR(20),
    notes                TEXT,
    orden                SMALLINT NOT NULL DEFAULT 0,
    UNIQUE (memoria_categoria_id, nombre),
    CONSTRAINT memoria_objeto_cantidad_no_negativa
        CHECK (COALESCE(cantidad, 0) >= 0)
);

CREATE INDEX memoria_objeto_categoria_idx ON memoria_objeto (memoria_categoria_id, orden);
"""

TABLAS = ("memoria_tecnica", "memoria_categoria", "memoria_objeto")


def upgrade() -> None:
    # `ALTER TYPE ... ADD VALUE` va suelto y ANTES de usarse: PostgreSQL no deja
    # emplear un valor de enumeración nuevo en la misma transacción que lo crea.
    # Aquí no se usa, pero dejarlo aparte evita que un cambio futuro lo haga.
    op.execute("ALTER TYPE doc_type ADD VALUE IF NOT EXISTS 'MEMORIA_TECNICA'")
    op.execute(MEMORIA)

    for tabla in TABLAS:
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {tabla}_aislamiento_org ON {tabla} "
            "USING (organization_id = org_actual()) "
            "WITH CHECK (organization_id = org_actual())"
        )

    # El mismo disparador de versión que llevan `asset`, `finding` y compañía.
    op.execute(
        "CREATE TRIGGER memoria_tecnica_version "
        "BEFORE UPDATE ON memoria_tecnica "
        "FOR EACH ROW EXECUTE FUNCTION marcar_version_y_autor()"
    )


def downgrade() -> None:
    """Bajar esta revisión pierde la memoria de cada activo.

    Los datos que la memoria ya volcó al activo **se quedan**: están en las
    columnas que añadió la 0012. Lo que desaparece es de qué documento salieron
    y quién los validó, además del listado de categorías y objetos.

    `[LIM]` El valor `MEMORIA_TECNICA` del tipo `doc_type` **no se quita**:
    PostgreSQL no sabe borrar un valor de una enumeración, y recrear el tipo
    exigiría reescribir la tabla `document` entera. Los documentos que ya lo
    lleven se quedan con él, que es inofensivo.
    """
    op.execute("DROP TRIGGER IF EXISTS memoria_tecnica_version ON memoria_tecnica")
    op.execute("DROP TABLE IF EXISTS memoria_objeto")
    op.execute("DROP TABLE IF EXISTS memoria_categoria")
    op.execute("DROP TABLE IF EXISTS memoria_tecnica")
    op.execute("DROP TYPE IF EXISTS memoria_status")

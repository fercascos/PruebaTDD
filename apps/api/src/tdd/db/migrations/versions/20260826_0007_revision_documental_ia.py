"""Revisión de documentación asistida por IA: opt-in, propuestas y evidencia.

Revisión: 0007
Anterior: 0006

`[REQ]` Un módulo en la fase «Solicitud de documentación» donde la IA lee los
documentos subidos e identifica si algo es **no conforme** o **falta**.

Tres decisiones del cliente están grabadas en el esquema, no en el código,
porque son exactamente las que no deben poder saltarse por descuido:

1. **Opt-in por encargo, apagado de fábrica.** `project.ai_doc_review_enabled`
   nace en `FALSE`, y la restricción `project_revision_ia_con_autoria` impide
   que esté encendido sin que consten **quién** lo encendió y **cuándo**. La
   restricción del cliente pedía «autorización expresa y verificable»: sin esa
   comprobación el interruptor sería un ajuste, no una autorización.

2. **La IA propone, una persona decide.** Una observación no sale de
   `PROPUESTA` sin `decided_by` y `decided_at`
   (`doc_finding_decidida_con_persona`). Aunque mañana alguien escriba un
   proceso que acepte propuestas en lote, la base lo rechaza.

3. **`doc_request_item.status` no se toca desde aquí.** Un documento puede
   estar `RECIBIDA` y ser no conforme a la vez. Colapsar los dos ejes habría
   obligado a inventar un estado que la checklist del cliente no tiene.

`[PDV]` Los criterios exactos de revisión están pendientes de acordar, así que
viven en `doc_check_type` —una fila por criterio— y no en constantes. Cambiar
qué se revisa no debería requerir una migración.

`[LIM]` Esta migración **no elige proveedor de IA**. Crea la estructura y deja
`is_simulated` en `TRUE` por defecto: mientras no haya proveedor, toda revisión
es simulada y se muestra como tal.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1 · El interruptor por encargo, con su autoría ────────────────────────
    op.execute(
        """
        ALTER TABLE project
            ADD COLUMN ai_doc_review_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN ai_doc_review_enabled_at TIMESTAMPTZ,
            ADD COLUMN ai_doc_review_enabled_by UUID REFERENCES app_user(id),
            ADD CONSTRAINT project_revision_ia_con_autoria
                CHECK (NOT ai_doc_review_enabled
                       OR (ai_doc_review_enabled_at IS NOT NULL
                           AND ai_doc_review_enabled_by IS NOT NULL))
        """
    )

    # ── 2 · Qué se comprueba, como catálogo ──────────────────────────────────
    op.execute(
        """
        CREATE TABLE doc_check_type (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID REFERENCES organization(id),
            code            VARCHAR(40) NOT NULL,
            name_es         VARCHAR(120) NOT NULL,
            description_es  TEXT NOT NULL,
            display_order   SMALLINT NOT NULL DEFAULT 0,
            is_system       BOOLEAN NOT NULL DEFAULT TRUE,
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE NULLS NOT DISTINCT (organization_id, code)
        )
        """
    )

    # ── 3 · Una revisión por documento analizado ─────────────────────────────
    op.execute(
        """
        CREATE TYPE doc_review_status AS ENUM (
            'PENDIENTE', 'EN_CURSO', 'COMPLETADA', 'FALLIDA', 'CANCELADA'
        )
        """
    )
    op.execute(
        """
        CREATE TABLE doc_review (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id     UUID NOT NULL REFERENCES organization(id),
            project_id          UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
            document_id         UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE,
            doc_request_item_id UUID REFERENCES doc_request_item(id) ON DELETE SET NULL,
            status              doc_review_status NOT NULL DEFAULT 'PENDIENTE',

            provider            VARCHAR(40) NOT NULL,
            model               VARCHAR(80),
            is_simulated        BOOLEAN NOT NULL DEFAULT TRUE,
            document_sha256     CHAR(64) NOT NULL,

            requested_by        UUID NOT NULL REFERENCES app_user(id),
            requested_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at          TIMESTAMPTZ,
            finished_at         TIMESTAMPTZ,
            error_message       TEXT,

            CONSTRAINT doc_review_fallida_con_motivo
                CHECK (status <> 'FALLIDA'
                       OR (error_message IS NOT NULL AND length(trim(error_message)) > 0)),
            CONSTRAINT doc_review_terminada_con_fecha
                CHECK (status NOT IN ('COMPLETADA', 'FALLIDA') OR finished_at IS NOT NULL)
        )
        """
    )
    op.execute(
        "CREATE INDEX doc_review_documento_idx ON doc_review (document_id, requested_at DESC)"
    )
    op.execute("CREATE INDEX doc_review_proyecto_idx ON doc_review (project_id, status)")

    # ── 4 · Cada observación, con su evidencia y su decisión humana ──────────
    op.execute(
        "CREATE TYPE doc_finding_verdict AS ENUM ('CONFORME', 'NO_CONFORME', 'FALTA', 'DUDOSO')"
    )
    op.execute("CREATE TYPE doc_finding_decision AS ENUM ('PROPUESTA', 'ACEPTADA', 'RECHAZADA')")
    op.execute(
        """
        CREATE TABLE doc_review_finding (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organization(id),
            doc_review_id   UUID NOT NULL REFERENCES doc_review(id) ON DELETE CASCADE,
            check_type_id   UUID NOT NULL REFERENCES doc_check_type(id),
            verdict         doc_finding_verdict NOT NULL,
            summary         TEXT NOT NULL,

            evidence_text   TEXT,
            evidence_page   INT,
            confidence      NUMERIC(4, 3),

            decision        doc_finding_decision NOT NULL DEFAULT 'PROPUESTA',
            decided_by      UUID REFERENCES app_user(id),
            decided_at      TIMESTAMPTZ,
            decision_note   TEXT,

            CONSTRAINT doc_finding_decidida_con_persona
                CHECK (decision = 'PROPUESTA'
                       OR (decided_by IS NOT NULL AND decided_at IS NOT NULL)),
            CONSTRAINT doc_finding_confianza_valida
                CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
            CONSTRAINT doc_finding_pagina_valida
                CHECK (evidence_page IS NULL OR evidence_page >= 1)
        )
        """
    )
    op.execute(
        "CREATE INDEX doc_finding_revision_idx ON doc_review_finding (doc_review_id, decision)"
    )

    # ── 5 · RLS. Sin esto, las propuestas de una organización serían visibles
    #        para las demás, que es justo lo contrario de lo que hace falta
    #        cuando lo revisado es documentación confidencial de un cliente.
    for tabla in ("doc_review", "doc_review_finding"):
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {tabla}_aislamiento_org ON {tabla} "
            "USING (organization_id = org_actual()) "
            "WITH CHECK (organization_id = org_actual())"
        )

    op.execute("ALTER TABLE doc_check_type ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE doc_check_type FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY doc_check_type_catalogo ON doc_check_type "
        "USING (organization_id IS NULL OR organization_id = org_actual()) "
        "WITH CHECK (organization_id = org_actual())"
    )


def downgrade() -> None:
    """Se deshace entero, en orden inverso.

    Bajar esta revisión **borra las propuestas y las decisiones tomadas sobre
    ellas**. Es aceptable porque ninguna de las dos es una conclusión del
    informe: lo que una persona acepta se traslada a la checklist o al hallazgo
    correspondiente, que viven en tablas anteriores y sobreviven.
    """
    op.execute("DROP TABLE IF EXISTS doc_review_finding")
    op.execute("DROP TYPE IF EXISTS doc_finding_decision")
    op.execute("DROP TYPE IF EXISTS doc_finding_verdict")
    op.execute("DROP TABLE IF EXISTS doc_review")
    op.execute("DROP TYPE IF EXISTS doc_review_status")
    op.execute("DROP TABLE IF EXISTS doc_check_type")
    op.execute(
        """
        ALTER TABLE project
            DROP CONSTRAINT IF EXISTS project_revision_ia_con_autoria,
            DROP COLUMN IF EXISTS ai_doc_review_enabled_by,
            DROP COLUMN IF EXISTS ai_doc_review_enabled_at,
            DROP COLUMN IF EXISTS ai_doc_review_enabled
        """
    )

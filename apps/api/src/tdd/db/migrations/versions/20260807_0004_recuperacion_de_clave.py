"""Recuperación de contraseña.

Revisión: 0004
Anterior: 0003

`[REQ]` §10.2 · Hasta ahora, quien olvidaba su contraseña dependía de que un
administrador se la repusiera a mano.

Tres decisiones que se ven en el SQL:

* **Se guarda la huella del token, nunca el token.** Si esta tabla se filtrara,
  lo que se llevaría el atacante son hashes inservibles, no enlaces vivos.
* **Las funciones son `SECURITY DEFINER`** porque los dos endpoints son
  anónimos: sin sesión no hay `app.current_org_id` y la RLS lo ocultaría todo.
  Se acotan a una operación cada una en vez de dar `BYPASSRLS` al usuario de
  aplicación, que anularía el aislamiento entero.
* **`reset_consumir` hace las cuatro cosas juntas**: cambia la clave, marca el
  token, invalida los demás y revoca las sesiones. Separarlas dejaría ventanas
  donde el enlace ya usado sigue sirviendo, o donde la sesión de quien robó la
  cuenta sobrevive al cambio de contraseña.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLA = """
-- [REQ] §10.2 · Recuperación de contraseña.
--
-- **Se guarda la HUELLA, nunca el token.** Es la misma regla que en
-- `user_session`: si esta tabla se filtrara, lo que se llevaría el atacante no
-- serían enlaces de recuperación en funcionamiento, sino hashes inservibles.
-- Un token de recuperación en claro en la base es una llave maestra guardada
-- junto a la cerradura.
CREATE TABLE password_reset_token (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    user_id         UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    token_hash      CHAR(64) NOT NULL UNIQUE,
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    -- De un solo uso. Sin esto, un enlace reenviado o dejado en el historial
    -- del navegador sirve tantas veces como quiera quien lo encuentre.
    used_at         TIMESTAMPTZ,
    -- Con qué se pidió. No identifica a nadie por sí solo y permite investigar
    -- una tanda de peticiones.
    requested_ip    INET,
    requested_user_agent VARCHAR(300),

    CONSTRAINT reset_caduca_despues CHECK (expires_at > issued_at)
);
CREATE INDEX password_reset_usuario_idx ON password_reset_token (user_id, used_at);

ALTER TABLE password_reset_token ENABLE ROW LEVEL SECURITY;
ALTER TABLE password_reset_token FORCE ROW LEVEL SECURITY;
CREATE POLICY password_reset_token_aislamiento_org ON password_reset_token
    USING (organization_id = org_actual())
    WITH CHECK (organization_id = org_actual());
"""


FUNCIONES = """
CREATE OR REPLACE FUNCTION reset_buscar_usuario(p_email TEXT)
RETURNS TABLE (id UUID, organization_id UUID, full_name TEXT, is_active BOOLEAN)
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT u.id, u.organization_id, u.full_name::TEXT, u.is_active
    FROM app_user u
    JOIN organization o ON o.id = u.organization_id
    WHERE lower(u.email) = lower(p_email) AND o.is_active;
$$;

-- Cuántas peticiones sin usar tiene abiertas ya. Es el freno contra usar la
-- recuperación como forma de bombardear el buzón de alguien.
CREATE OR REPLACE FUNCTION reset_peticiones_recientes(p_user UUID, p_desde TIMESTAMPTZ)
RETURNS BIGINT
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT count(*) FROM password_reset_token
    WHERE user_id = p_user AND issued_at >= p_desde;
$$;

CREATE OR REPLACE FUNCTION reset_crear(
    p_org UUID, p_user UUID, p_hash TEXT, p_expira TIMESTAMPTZ,
    p_ip TEXT, p_agente TEXT
) RETURNS VOID
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    INSERT INTO password_reset_token (
        organization_id, user_id, token_hash, expires_at, requested_ip, requested_user_agent
    ) VALUES (
        p_org, p_user, p_hash, p_expira, CAST(NULLIF(p_ip, '') AS inet), left(p_agente, 300)
    );
$$;

CREATE OR REPLACE FUNCTION reset_buscar_token(p_hash TEXT)
RETURNS TABLE (
    id UUID, user_id UUID, organization_id UUID, email TEXT,
    expires_at TIMESTAMPTZ, used_at TIMESTAMPTZ, is_active BOOLEAN
)
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT t.id, t.user_id, t.organization_id, u.email::TEXT,
           t.expires_at, t.used_at, u.is_active
    FROM password_reset_token t
    JOIN app_user u ON u.id = t.user_id
    WHERE t.token_hash = p_hash;
$$;

-- Consumir es una sola operación, y hace las cuatro cosas juntas a propósito:
-- cambia la clave, marca el token usado, invalida los DEMÁS tokens del usuario
-- y revoca sus sesiones. Separarlas dejaría ventanas donde el enlace ya usado
-- sigue valiendo, o donde la sesión del que robó la cuenta sobrevive al
-- cambio de contraseña.
CREATE OR REPLACE FUNCTION reset_consumir(p_token_id UUID, p_hash_clave TEXT)
RETURNS VOID
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    WITH usado AS (
        UPDATE password_reset_token SET used_at = now()
        WHERE id = p_token_id AND used_at IS NULL
        RETURNING user_id
    ), demas AS (
        UPDATE password_reset_token SET used_at = now()
        WHERE user_id = (SELECT user_id FROM usado) AND used_at IS NULL
        RETURNING 1
    ), clave AS (
        UPDATE app_user SET password_hash = p_hash_clave, password_changed_at = now(),
               failed_login_attempts = 0, locked_until = NULL, updated_at = now()
        WHERE id = (SELECT user_id FROM usado)
        RETURNING 1
    )
    UPDATE user_session SET revoked_at = now(), revoked_reason = 'CAMBIO_DE_CLAVE'
    WHERE user_id = (SELECT user_id FROM usado) AND revoked_at IS NULL;
$$;
"""


def upgrade() -> None:
    op.execute(TABLA)
    op.execute(FUNCIONES)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS reset_consumir(UUID, TEXT)")
    op.execute("DROP FUNCTION IF EXISTS reset_buscar_token(TEXT)")
    op.execute("DROP FUNCTION IF EXISTS reset_crear(UUID, UUID, TEXT, TIMESTAMPTZ, TEXT, TEXT)")
    op.execute("DROP FUNCTION IF EXISTS reset_peticiones_recientes(UUID, TIMESTAMPTZ)")
    op.execute("DROP FUNCTION IF EXISTS reset_buscar_usuario(TEXT)")
    op.execute("DROP TABLE IF EXISTS password_reset_token")

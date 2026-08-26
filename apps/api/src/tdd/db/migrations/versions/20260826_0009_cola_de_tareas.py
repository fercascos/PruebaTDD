"""Cola de tareas en PostgreSQL: nada bloquea la interfaz más de 3 s.

Revisión: 0009
Anterior: 0008

`[REQ]` §17 · «Cualquier operación que pase de 3 s pasa a cola asíncrona con
progreso.» Hasta aquí generar un informe y enviar un correo iban en el hilo de
la petición: la pantalla se quedaba esperando a que el PPTX estuviera hecho.

Además cierra un agujero declarado en el propio código de
`POST /auth/password/forgot`: la respuesta tardaba distinto según existiera o
no la cuenta, porque la rama que existe hablaba con el servidor SMTP. Encolar
el envío hace que las dos ramas tarden lo mismo.

**La cola vive en esta base y no en un broker aparte.** Dos razones, y la
segunda es la que importa:

1. No añade un servicio a producción. Con la carga real —un puñado de informes
   al día— un broker dedicado sería una pieza más que vigilar sin ganar nada.
2. **El encolado es transaccional.** La tarea solo existe si la transacción que
   la creó confirma. Con un broker externo se puede encolar la generación de un
   informe cuya fila acaba revirtiendo.

`[REC]` El reparto usa `FOR UPDATE SKIP LOCKED` dentro de funciones
`SECURITY DEFINER`. El worker necesita ver las tareas de todas las
organizaciones —ese es su trabajo—, pero darle BYPASSRLS al usuario de
aplicación dejaría decorativas todas las políticas del esquema. Se resuelve
igual que la recuperación de contraseña, que tenía el mismo problema.

`[LIM]` Esto **no** trae Celery ni Redis. Si algún día la carga lo justifica,
lo que hay que cambiar es el adaptador de `tdd.cola`, no los endpoints ni las
tareas.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Copias literales de `schema.sql`. `test_migrar_desde_cero_produce_el_mismo_
#: esquema` compara el texto que PostgreSQL guarda de cada función, así que una
#: sangría distinta ya es una diferencia. Es a propósito: obliga a que los dos
#: caminos digan exactamente lo mismo.
TABLAS = """\
CREATE TYPE job_status AS ENUM ('PENDIENTE', 'EN_CURSO', 'HECHA', 'FALLIDA', 'CANCELADA');

CREATE TABLE job (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    kind             VARCHAR(40) NOT NULL,
    queue            VARCHAR(20) NOT NULL DEFAULT 'io',
    payload          JSONB NOT NULL DEFAULT '{}'::jsonb,
    status           job_status NOT NULL DEFAULT 'PENDIENTE',

    -- Cuándo se puede coger. Es lo que implementa la espera entre reintentos:
    -- un fallo la empuja hacia adelante en vez de reintentar en bucle contra
    -- un servidor SMTP que está caído.
    run_after        TIMESTAMPTZ NOT NULL DEFAULT now(),
    attempts         SMALLINT NOT NULL DEFAULT 0,
    max_attempts     SMALLINT NOT NULL DEFAULT 3,

    -- Quién la tiene cogida. Sirve para diagnosticar un worker que murió a
    -- mitad: la tarea se queda EN_CURSO con su nombre y su hora.
    locked_by        TEXT,
    locked_at        TIMESTAMPTZ,
    last_error       TEXT,

    created_by       UUID REFERENCES app_user(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at       TIMESTAMPTZ,
    finished_at      TIMESTAMPTZ,

    CONSTRAINT job_intentos_validos CHECK (max_attempts >= 1 AND attempts >= 0),
    -- Una tarea fallida sin motivo no se puede diagnosticar, y diagnosticarla
    -- es lo único que se puede hacer con ella.
    CONSTRAINT job_fallida_con_motivo
        CHECK (status <> 'FALLIDA'
               OR (last_error IS NOT NULL AND length(trim(last_error)) > 0)),
    CONSTRAINT job_terminada_con_fecha
        CHECK (status NOT IN ('HECHA', 'FALLIDA') OR finished_at IS NOT NULL)
);

-- El índice que hace barata la consulta de reparto: solo indexa lo pendiente,
-- así que no crece con el histórico de tareas ya hechas.
CREATE INDEX job_reparto_idx ON job (queue, run_after, created_at)
    WHERE status = 'PENDIENTE';
CREATE INDEX job_seguimiento_idx ON job (organization_id, kind, created_at DESC);
"""

FUNCIONES = """\
CREATE OR REPLACE FUNCTION job_coger(p_cola TEXT, p_worker TEXT)
RETURNS job
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    UPDATE job SET
        status     = 'EN_CURSO',
        attempts   = attempts + 1,
        locked_by  = p_worker,
        locked_at  = now(),
        started_at = COALESCE(started_at, now())
    WHERE id = (
        SELECT id FROM job
        WHERE status = 'PENDIENTE' AND queue = p_cola AND run_after <= now()
        ORDER BY run_after, created_at
        -- El corazón del reparto: cada worker se lleva una tarea distinta sin
        -- bloquear a los demás y sin necesitar ningún coordinador.
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING *;
$$;

CREATE OR REPLACE FUNCTION job_hecha(p_id UUID)
RETURNS VOID
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    UPDATE job SET status = 'HECHA', finished_at = now(), locked_by = NULL
    WHERE id = p_id;
$$;

--  Un fallo no es definitivo hasta agotar los intentos. `p_espera` empuja la
--  tarea hacia adelante: reintentar en bucle contra un SMTP caído no arregla
--  nada y llena la tabla de intentos inútiles.
CREATE OR REPLACE FUNCTION job_fallada(p_id UUID, p_error TEXT, p_espera INTERVAL)
RETURNS VOID
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    UPDATE job SET
        status      = CASE WHEN attempts >= max_attempts THEN 'FALLIDA'::job_status
                           ELSE 'PENDIENTE'::job_status END,
        run_after   = CASE WHEN attempts >= max_attempts THEN run_after
                           ELSE now() + p_espera END,
        finished_at = CASE WHEN attempts >= max_attempts THEN now() ELSE NULL END,
        last_error  = COALESCE(NULLIF(trim(p_error), ''), 'sin detalle'),
        locked_by   = NULL
    WHERE id = p_id;
$$;

--  Un worker que muere a mitad deja su tarea EN_CURSO para siempre. Esto la
--  devuelve a la cola pasado un tiempo, contando el intento que ya gastó: sin
--  esto, matar un worker perdería silenciosamente el informe que tenía entre
--  manos, que es justo el fallo que nadie relaciona con la causa.
CREATE OR REPLACE FUNCTION job_rescatar(p_limite INTERVAL)
RETURNS INTEGER
LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
    WITH rescatadas AS (
        UPDATE job SET
            status     = CASE WHEN attempts >= max_attempts THEN 'FALLIDA'::job_status
                              ELSE 'PENDIENTE'::job_status END,
            last_error = 'El worker que la tenía cogida no terminó',
            finished_at = CASE WHEN attempts >= max_attempts THEN now() ELSE NULL END,
            locked_by  = NULL
        WHERE status = 'EN_CURSO' AND locked_at < now() - p_limite
        RETURNING 1
    )
    SELECT COUNT(*)::INTEGER FROM rescatadas;
$$;
"""


def upgrade() -> None:
    op.execute(TABLAS)
    op.execute(FUNCIONES)
    # La cola entra en la RLS de organización como cualquier otra tabla con
    # `organization_id`: un usuario solo ve las tareas de la suya. Lo que ve el
    # worker pasa por las funciones de arriba, no por la tabla.
    op.execute("ALTER TABLE job ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE job FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY job_aislamiento_org ON job "
        "USING (organization_id = org_actual()) "
        "WITH CHECK (organization_id = org_actual())"
    )


def downgrade() -> None:
    """Bajar esta revisión pierde las tareas pendientes.

    Es aceptable y hay que decirlo: lo que se pierde es el encargo de generar
    un informe, no el informe. Se vuelve a pedir desde la pantalla.
    """
    for f in ("job_rescatar(INTERVAL)", "job_fallada(UUID, TEXT, INTERVAL)",
              "job_hecha(UUID)", "job_coger(TEXT, TEXT)"):
        op.execute(f"DROP FUNCTION IF EXISTS {f}")
    op.execute("DROP TABLE IF EXISTS job")
    op.execute("DROP TYPE IF EXISTS job_status")

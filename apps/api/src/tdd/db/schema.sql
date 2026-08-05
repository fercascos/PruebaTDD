-- =============================================================================
--  Esquema inicial · TDD inmobiliaria
--
--  Cuatro cosas se hacen cumplir AQUÍ, en la base de datos, y no solo en la
--  capa de aplicación. Un servicio nuevo que olvide una comprobación no puede
--  saltárselas:
--
--   1. Aislamiento entre organizaciones ......... Row Level Security
--   2. Visibilidad de las sugerencias [REQ] ..... Row Level Security
--   3. Los originales nunca se sobrescriben ..... trigger
--   4. Reglas del CAPEX y de los precios ........ CHECK
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS ltree;

-- ── Identidad y organización ────────────────────────────────────────────────

CREATE TABLE organization (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(160) NOT NULL,
    slug         VARCHAR(80)  NOT NULL UNIQUE,
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TYPE org_role AS ENUM (
    'ADMIN', 'DIRECTOR_PROYECTO', 'CONSULTOR', 'TECNICO_ESPECIALISTA', 'REVISOR', 'LECTOR'
);

CREATE TABLE app_user (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    email            VARCHAR(320) NOT NULL,
    full_name        VARCHAR(160) NOT NULL,
    password_hash    TEXT NOT NULL,
    org_role         org_role NOT NULL DEFAULT 'LECTOR',
    -- [REC] P-41 · permiso separable: atender el buzón de sugerencias sin ser
    -- ADMIN, que además gestiona usuarios, catálogos y organización.
    can_manage_suggestions BOOLEAN NOT NULL DEFAULT FALSE,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    -- Bloqueo por intentos fallidos. El contador vive aquí y no en memoria
    -- para que reiniciar el proceso no regale intentos a quien esté probando.
    failed_login_attempts SMALLINT NOT NULL DEFAULT 0,
    locked_until     TIMESTAMPTZ,
    last_login_at    TIMESTAMPTZ,
    password_changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, email)
);

-- ── Catálogos del sistema ───────────────────────────────────────────────────
-- organization_id NULL = fila del sistema, no editable por nadie.

CREATE TABLE asset_typology (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    code            VARCHAR(40) NOT NULL,
    name_es         VARCHAR(120) NOT NULL,
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order      INT NOT NULL DEFAULT 0,
    UNIQUE (organization_id, code)
);

CREATE TABLE zone (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    code            VARCHAR(40) NOT NULL,
    name_es         VARCHAR(120) NOT NULL,
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order      INT NOT NULL DEFAULT 0,
    UNIQUE (organization_id, code)
);

-- La matriz de §5.2: 86 relaciones. Es lo que hace que el selector de zona
-- dependa de la tipología del activo, con la regla en un solo sitio.
CREATE TABLE zone_typology (
    zone_id     UUID NOT NULL REFERENCES zone(id) ON DELETE CASCADE,
    typology_id UUID NOT NULL REFERENCES asset_typology(id) ON DELETE CASCADE,
    PRIMARY KEY (zone_id, typology_id)
);

CREATE TABLE capex_code (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    code            VARCHAR(40) NOT NULL,
    name_es         VARCHAR(200) NOT NULL,
    level           SMALLINT NOT NULL CHECK (level BETWEEN 1 AND 3),
    parent_id       UUID REFERENCES capex_code(id),
    path            LTREE,
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    deprecated_at   TIMESTAMPTZ,
    UNIQUE (organization_id, code),
    -- Un nodo de nivel 1 no tiene padre; los demás, sí. Sin esto, un árbol
    -- puede quedarse con capítulos huérfanos que no aparecen en el selector.
    CONSTRAINT capex_code_parent_coherente
        CHECK ((level = 1 AND parent_id IS NULL) OR (level > 1 AND parent_id IS NOT NULL))
);
CREATE INDEX capex_code_path_idx ON capex_code USING GIST (path);
CREATE INDEX capex_code_parent_idx ON capex_code (parent_id);

CREATE TABLE risk_level (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    code            VARCHAR(4) NOT NULL,
    name_es         VARCHAR(60) NOT NULL,
    score           SMALLINT NOT NULL CHECK (score BETWEEN 1 AND 4),
    -- [REQ] La definición íntegra vive en base de datos, no en el frontend:
    -- se muestra al clasificar y se vuelca al informe como leyenda.
    definition_es   TEXT NOT NULL,
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (organization_id, code)
);

CREATE TABLE capex_concept (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    code            VARCHAR(40) NOT NULL,
    name_es         VARCHAR(120) NOT NULL,
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (organization_id, code)
);

CREATE TABLE time_horizon (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID REFERENCES organization(id),
    code              VARCHAR(20) NOT NULL,
    name_es           VARCHAR(60) NOT NULL,
    year_from         SMALLINT,
    year_to           SMALLINT,
    is_execution_term BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order        INT NOT NULL DEFAULT 0,
    is_system         BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (organization_id, code),
    CONSTRAINT horizonte_rango_coherente
        CHECK (year_from IS NULL OR year_to IS NULL OR year_from <= year_to)
);

-- Traducciones de catálogo. [REQ] El informe se emite en el idioma de la
-- plantilla, y las definiciones de riesgo están traducidas palabra por palabra
-- en las plantillas reales: por eso viven en tabla, no en una columna única.
CREATE TABLE catalog_i18n (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    catalog      VARCHAR(40) NOT NULL,
    row_id       UUID NOT NULL,
    locale       VARCHAR(10) NOT NULL,
    name         VARCHAR(200) NOT NULL,
    definition   TEXT,
    UNIQUE (catalog, row_id, locale)
);

-- ── Cliente, proyecto y activo ──────────────────────────────────────────────

-- Los nombres son los de docs/02 §5.1. El `estado` describe el ciclo
-- administrativo del encargo; las **fases** describen el trabajo real y son un
-- eje independiente (ver `project_phase`). Mezclarlos en un solo campo sería el
-- error de modelado más caro de este proyecto.
CREATE TYPE project_status AS ENUM (
    'BORRADOR', 'EN_PREPARACION', 'VISITA_PROGRAMADA', 'VISITA_REALIZADA',
    'EN_ANALISIS', 'EN_REVISION', 'INFORME_EMITIDO', 'CERRADO', 'ARCHIVADO'
);

CREATE TABLE client (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    name            VARCHAR(200) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE project (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    client_id        UUID NOT NULL REFERENCES client(id),
    internal_code    VARCHAR(40) NOT NULL,
    name             VARCHAR(200) NOT NULL,
    status           project_status NOT NULL DEFAULT 'BORRADOR',
    currency         CHAR(3) NOT NULL DEFAULT 'EUR',
    report_due_date  DATE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at       TIMESTAMPTZ,
    UNIQUE (organization_id, internal_code)
);

CREATE TABLE asset (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL REFERENCES organization(id),
    project_id        UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    typology_id       UUID NOT NULL REFERENCES asset_typology(id),
    name              VARCHAR(200) NOT NULL,
    asset_code        VARCHAR(60),
    main_use          VARCHAR(120),
    address_line      VARCHAR(240),
    city              VARCHAR(120),
    province          VARCHAR(120),
    postal_code       VARCHAR(20),
    country_code      CHAR(2) NOT NULL DEFAULT 'ES',
    latitude          NUMERIC(9, 6),
    longitude         NUMERIC(9, 6),
    -- [REC] De dónde salen las coordenadas. Sin esto, nadie sabe si las tecleó
    -- una persona o las adivinó un geocodificador, y el aviso de «foto lejos
    -- del activo» acusaría al consultor por un error del mapa.
    geocode_source    VARCHAR(40),
    geocoded_at       TIMESTAMPTZ,
    description       TEXT,
    notes             TEXT,
    -- [REQ] P-02 · La UNIÓN de los campos de §3.1.3 y §3.3.1 en una sola ficha.
    -- Se muestran según tipología y NO se borran al reclasificar.
    plot_area_sqm       NUMERIC(14, 2),
    total_built_sqm     NUMERIC(14, 2),
    lettable_area_sqm   NUMERIC(14, 2),
    warehouse_area_sqm  NUMERIC(14, 2),
    office_area_sqm     NUMERIC(14, 2),
    warehouse_height_m  NUMERIC(6, 2),
    floors_above        SMALLINT,
    floors_below        SMALLINT,
    year_built          SMALLINT,
    year_last_refurb    SMALLINT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at        TIMESTAMPTZ,
    -- La clave foránea se añade más abajo: `photo` todavía no existe aquí, y
    -- reordenar el esquema por una columna opcional no compensa.
    main_photo_id     UUID,

    CONSTRAINT asset_coordenadas_completas
        CHECK ((latitude IS NULL) = (longitude IS NULL)),
    CONSTRAINT asset_coordenadas_en_rango
        CHECK (latitude IS NULL
               OR (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)),
    -- La reforma no puede ser anterior a la construcción. Es el error de
    -- tecleo más habitual de la ficha y falsea la vida útil que se estima
    -- después.
    CONSTRAINT asset_reforma_posterior
        CHECK (year_last_refurb IS NULL OR year_built IS NULL OR year_last_refurb >= year_built),
    CONSTRAINT asset_anos_verosimiles
        CHECK (year_built IS NULL OR year_built BETWEEN 1500 AND 2100),
    -- [REC] El almacén no puede ser mayor que el edificio entero.
    CONSTRAINT asset_almacen_cabe
        CHECK (warehouse_area_sqm IS NULL OR total_built_sqm IS NULL
               OR warehouse_area_sqm <= total_built_sqm),
    CONSTRAINT asset_superficies_no_negativas
        CHECK (COALESCE(plot_area_sqm, 0) >= 0 AND COALESCE(total_built_sqm, 0) >= 0
               AND COALESCE(lettable_area_sqm, 0) >= 0)
);

CREATE UNIQUE INDEX asset_codigo_uniq
    ON asset (project_id, asset_code) WHERE asset_code IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX asset_proyecto_idx ON asset (project_id) WHERE deleted_at IS NULL;

-- ── Equipo del proyecto ─────────────────────────────────────────────────────
--
-- [REQ] §7 · El permiso efectivo de una persona es el MÁXIMO entre su rol de
-- organización y su rol en el proyecto. Un LECTOR de la organización puede ser
-- director de un proyecto concreto; no al revés.

CREATE TYPE project_role AS ENUM (
    'DIRECTOR', 'CONSULTOR', 'TECNICO_ESPECIALISTA', 'REVISOR', 'LECTOR'
);

CREATE TABLE project_member (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    project_id      UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    role_code       project_role NOT NULL DEFAULT 'CONSULTOR',
    is_project_lead BOOLEAN NOT NULL DEFAULT FALSE,
    assigned_by     UUID REFERENCES app_user(id),
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_at      TIMESTAMPTZ,

    -- Quien dirige el proyecto no puede figurar como LECTOR: sería un permiso
    -- que se contradice a sí mismo.
    CONSTRAINT project_member_director_coherente
        CHECK (NOT is_project_lead OR role_code = 'DIRECTOR')
);

CREATE UNIQUE INDEX project_member_uniq
    ON project_member (project_id, user_id) WHERE removed_at IS NULL;
-- Un solo responsable por proyecto. Con dos, «el director decide» deja de ser
-- una regla y pasa a ser una discusión.
CREATE UNIQUE INDEX project_member_un_solo_director
    ON project_member (project_id) WHERE is_project_lead AND removed_at IS NULL;
CREATE INDEX project_member_usuario_idx ON project_member (user_id) WHERE removed_at IS NULL;

-- [REQ] Una persona en varios activos y un activo con varios técnicos por
-- especialidad. Con una columna en `asset` no cabría ninguna de las dos cosas.
CREATE TABLE asset_assignment (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL REFERENCES organization(id),
    asset_id          UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    project_member_id UUID NOT NULL REFERENCES project_member(id) ON DELETE CASCADE,
    specialty         VARCHAR(60),
    assigned_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    assigned_by       UUID REFERENCES app_user(id),

    -- `NULLS NOT DISTINCT` es imprescindible: sin él, «sin especialidad» es
    -- NULL, dos NULL se consideran distintos y la misma persona podría
    -- asignarse al mismo activo tantas veces como quisiera.
    UNIQUE NULLS NOT DISTINCT (asset_id, project_member_id, specialty)
);

-- ── Fases del proceso [REQ] §3.1.5 ──────────────────────────────────────────
--
-- El otro eje del proyecto. Se crean SOLO las fases que el usuario marca al dar
-- de alta el encargo: un proyecto sin Q&A no arrastra una fase vacía.

CREATE TYPE phase_status AS ENUM (
    'NO_APLICA', 'PENDIENTE', 'EN_CURSO', 'COMPLETADA', 'BLOQUEADA'
);

CREATE TABLE phase_definition (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code               VARCHAR(40) NOT NULL UNIQUE,
    name_es            VARCHAR(120) NOT NULL,
    display_order      SMALLINT NOT NULL,
    has_checklist      BOOLEAN NOT NULL DEFAULT FALSE,
    has_external_link  BOOLEAN NOT NULL DEFAULT FALSE,
    has_visit_tracking BOOLEAN NOT NULL DEFAULT FALSE,
    has_file_rounds    BOOLEAN NOT NULL DEFAULT FALSE,
    -- [REC] Si el estado es derivado, la API NO lo acepta: lo calcula el motor
    -- de fases a partir del trabajo real. Una lista de verificación que se puede
    -- marcar a mano cuando el trabajo no está hecho es peor que no tenerla: da
    -- una falsa sensación de avance justo en el punto donde más cuesta.
    status_is_derived  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE project_phase (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organization(id),
    project_id          UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    phase_definition_id UUID NOT NULL REFERENCES phase_definition(id),
    is_applicable       BOOLEAN NOT NULL DEFAULT TRUE,
    status              phase_status NOT NULL DEFAULT 'PENDIENTE',
    owner_user_id       UUID REFERENCES app_user(id),
    planned_start_date  DATE,
    planned_end_date    DATE,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    notes               TEXT,
    display_order       SMALLINT NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, phase_definition_id),
    CONSTRAINT completada_deja_fecha
        CHECK (status <> 'COMPLETADA' OR completed_at IS NOT NULL),
    CONSTRAINT no_aplica_es_coherente
        CHECK (is_applicable OR status = 'NO_APLICA')
);
CREATE INDEX project_phase_orden_idx ON project_phase (project_id, display_order);
CREATE INDEX project_phase_estado_idx ON project_phase (organization_id, status);

CREATE TABLE doc_request_category (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    code            VARCHAR(40) NOT NULL,
    name_es         VARCHAR(120) NOT NULL,
    display_order   SMALLINT NOT NULL DEFAULT 0,
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (organization_id, code)
);

CREATE TYPE doc_request_status AS ENUM (
    'SOLICITADA', 'RECIBIDA', 'PARCIAL', 'NO_DISPONIBLE', 'NO_APLICA'
);

CREATE TABLE doc_request_item (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES organization(id),
    project_phase_id   UUID NOT NULL REFERENCES project_phase(id) ON DELETE CASCADE,
    asset_id           UUID REFERENCES asset(id) ON DELETE CASCADE,
    category_id        UUID NOT NULL REFERENCES doc_request_category(id),
    title              VARCHAR(240) NOT NULL,
    description        TEXT,
    status             doc_request_status NOT NULL DEFAULT 'SOLICITADA',
    requested_at       TIMESTAMPTZ,
    received_at        TIMESTAMPTZ,
    unavailable_reason TEXT,
    -- [REC] Alimenta automáticamente el apartado de limitaciones del informe.
    -- Declarar qué no se ha podido revisar es una obligación profesional en una
    -- TDD, y hoy suele reconstruirse de memoria al final del encargo.
    affects_report_limitations BOOLEAN
        GENERATED ALWAYS AS (status IN ('NO_DISPONIBLE', 'PARCIAL')) STORED,
    display_order      SMALLINT NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Decir «no disponible» sin decir por qué deja el informe sin poder
    -- explicar la limitación, que es exactamente para lo que sirve el campo.
    CONSTRAINT no_disponible_exige_motivo
        CHECK (status <> 'NO_DISPONIBLE'
               OR (unavailable_reason IS NOT NULL AND length(trim(unavailable_reason)) > 0))
);
CREATE INDEX doc_request_fase_idx ON doc_request_item (project_phase_id, display_order);

CREATE TABLE vdr_link (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    project_phase_id UUID NOT NULL REFERENCES project_phase(id) ON DELETE CASCADE,
    provider         VARCHAR(120),
    url              TEXT NOT NULL,
    -- [REC] NO hay columna de credenciales, y es deliberado: guardar la
    -- contraseña de un repositorio de terceros multiplicaría la superficie de
    -- riesgo sin aportar nada. El enlace y a quién pedir acceso bastan.
    access_notes     TEXT,
    granted_at       TIMESTAMPTZ,
    expires_at       TIMESTAMPTZ,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX vdr_link_activo_uniq ON vdr_link (project_phase_id) WHERE is_active;

CREATE TYPE visit_status AS ENUM ('PENDIENTE_DEFINIR', 'AGENDADO', 'VISITADO');

CREATE TABLE asset_visit (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES organization(id),
    project_id         UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    asset_id           UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    status             visit_status NOT NULL DEFAULT 'PENDIENTE_DEFINIR',
    scheduled_date     DATE,
    actual_date        DATE,
    led_by             UUID REFERENCES app_user(id),
    access_limitations TEXT,
    summary            TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT agendado_exige_fecha
        CHECK (status <> 'AGENDADO' OR scheduled_date IS NOT NULL),
    CONSTRAINT visitado_exige_fecha_real
        CHECK (status <> 'VISITADO' OR actual_date IS NOT NULL)
);
CREATE INDEX asset_visit_proyecto_idx ON asset_visit (project_id, status);

CREATE TYPE qa_round_status AS ENUM ('ABIERTA', 'ENVIADA', 'RESPONDIDA', 'CERRADA');

CREATE TABLE qa_round (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    project_phase_id UUID NOT NULL REFERENCES project_phase(id) ON DELETE CASCADE,
    round_number     SMALLINT NOT NULL,
    title            VARCHAR(240),
    status           qa_round_status NOT NULL DEFAULT 'ABIERTA',
    sent_at          TIMESTAMPTZ,
    answered_at      TIMESTAMPTZ,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_phase_id, round_number)
);

-- Las preguntas de la ronda. Van en su propia tabla y no en un JSONB de
-- `qa_round` porque cada una tiene su estado, su responsable y su respuesta, y
-- porque la limitación del informe se declara por pregunta sin responder, no
-- por ronda.
CREATE TYPE qa_question_status AS ENUM ('ABIERTA', 'RESPONDIDA', 'SIN_RESPUESTA', 'RETIRADA');

CREATE TABLE qa_question (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    qa_round_id     UUID NOT NULL REFERENCES qa_round(id) ON DELETE CASCADE,
    asset_id        UUID REFERENCES asset(id) ON DELETE SET NULL,
    number          SMALLINT NOT NULL,
    question        TEXT NOT NULL,
    answer          TEXT,
    status          qa_question_status NOT NULL DEFAULT 'ABIERTA',
    answered_at     TIMESTAMPTZ,
    -- [REC] Igual que en el checklist documental: alimenta el apartado de
    -- limitaciones del informe sin que nadie tenga que reconstruirlo de memoria.
    affects_report_limitations BOOLEAN
        GENERATED ALWAYS AS (status = 'SIN_RESPUESTA') STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (qa_round_id, number),
    -- Marcar «respondida» sin respuesta dejaría la ronda cerrada en falso.
    CONSTRAINT respondida_exige_respuesta
        CHECK (status <> 'RESPONDIDA'
               OR (answer IS NOT NULL AND length(trim(answer)) > 0))
);

CREATE INDEX qa_question_ronda_idx ON qa_question (qa_round_id, number);

CREATE TABLE phase_event (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    project_phase_id UUID NOT NULL REFERENCES project_phase(id) ON DELETE CASCADE,
    event_date       DATE NOT NULL,
    counterparty     VARCHAR(200),
    attendees        JSONB,
    outcome          TEXT,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX phase_event_fase_idx ON phase_event (project_phase_id, event_date);


-- ── Perfil de costes ────────────────────────────────────────────────────────

CREATE TABLE cost_profile (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    name             VARCHAR(120) NOT NULL,
    -- [REQ] P-05b · De los seis porcentajes, SOLO el impuesto se aplica a todas
    -- las líneas. Los otros cinco son la preconfiguración de la calculadora de
    -- medición y NO recalculan ningún importe ya tecleado.
    tax_pct          NUMERIC(7, 4) NOT NULL DEFAULT 0.2100,
    indirect_pct     NUMERIC(7, 4) NOT NULL DEFAULT 0.0800,
    overhead_pct     NUMERIC(7, 4) NOT NULL DEFAULT 0.1300,
    profit_pct       NUMERIC(7, 4) NOT NULL DEFAULT 0.0600,
    fees_pct         NUMERIC(7, 4) NOT NULL DEFAULT 0.0600,
    contingency_pct  NUMERIC(7, 4) NOT NULL DEFAULT 0.1000,
    -- [REQ] P-16 · La estructura de la cascada: sobre qué base se aplica cada
    -- porcentaje. Cambiarla es configuración, no despliegue.
    cascade_config   JSONB NOT NULL,
    is_default       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, name)
);

-- ── Precios ─────────────────────────────────────────────────────────────────

CREATE TYPE price_source_type AS ENUM (
    'MANUAL', 'CATALOGO_INTERNO', 'BASE_PRECIOS_LICENCIADA', 'API_OFICIAL', 'CATALOGO_FABRICANTE'
);

CREATE TABLE price_source (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organization(id),
    code                VARCHAR(60) NOT NULL,
    name                VARCHAR(160) NOT NULL,
    source_type         price_source_type NOT NULL,
    is_enabled          BOOLEAN NOT NULL DEFAULT FALSE,
    tos_reviewed        BOOLEAN NOT NULL DEFAULT FALSE,
    tos_reviewed_by     UUID REFERENCES app_user(id),
    tos_reviewed_at     TIMESTAMPTZ,
    tos_url             TEXT,
    license_reference   VARCHAR(160),
    license_expires_at  DATE,
    disabled_reason     TEXT,
    UNIQUE (organization_id, code),
    -- [REQ] Una fuente externa NO puede habilitarse sin revisión documentada de
    -- sus condiciones de uso. En la base de datos, para que no dependa de que
    -- una pantalla recuerde comprobarlo.
    CONSTRAINT fuente_exige_revision_de_condiciones CHECK (
        is_enabled = FALSE
        OR source_type = 'MANUAL'
        OR (tos_reviewed = TRUE AND tos_reviewed_by IS NOT NULL AND tos_reviewed_at IS NOT NULL)
    )
);

CREATE TABLE price_reference (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id       UUID NOT NULL REFERENCES organization(id),
    price_source_id       UUID NOT NULL REFERENCES price_source(id),
    description           TEXT NOT NULL,
    unit                  VARCHAR(20) NOT NULL,
    unit_price            NUMERIC(18, 4) NOT NULL,
    currency              CHAR(3) NOT NULL DEFAULT 'EUR',
    source_url            TEXT,
    retrieved_at          TIMESTAMPTZ,
    price_date            DATE,
    geo_scope             VARCHAR(40),
    includes_tax          BOOLEAN,
    includes_installation BOOLEAN,
    scope_included        TEXT,
    scope_excluded        TEXT,
    -- [REQ] P-06 · Nota de procedencia OPCIONAL. Los precios se teclean a mano
    -- y exigir un párrafo en cada línea no produce trazabilidad, produce ruido.
    -- La trazabilidad real la da audit_log, que no depende de que nadie escriba.
    provenance_note       TEXT,
    created_by            UUID NOT NULL REFERENCES app_user(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Diagnóstico y CAPEX ─────────────────────────────────────────────────────

CREATE TYPE tenant_recoverable AS ENUM ('SI', 'NO', 'NA');
CREATE TYPE price_status AS ENUM ('SIN_PRECIO', 'PENDIENTE_VALIDACION', 'VALIDADO');
CREATE TYPE amount_source AS ENUM ('MANUAL', 'MEDICION');

-- El ciclo de vida de un hallazgo. `DESCARTADO` existe para que lo que se
-- decide no incluir deje rastro: sin él, la única forma de quitar un hallazgo
-- del informe sería borrarlo, y nadie sabría después que se llegó a valorar.
CREATE TYPE finding_status AS ENUM ('BORRADOR', 'EN_REVISION', 'VALIDADO', 'DESCARTADO');

CREATE TABLE finding (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES organization(id),
    project_id         UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    asset_id           UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    capex_code_id      UUID NOT NULL REFERENCES capex_code(id),
    zone_id            UUID NOT NULL REFERENCES zone(id),
    risk_level_id      UUID REFERENCES risk_level(id),
    capex_concept_id   UUID REFERENCES capex_concept(id),
    title              VARCHAR(240) NOT NULL,
    description        TEXT NOT NULL DEFAULT '',
    comments           TEXT,
    -- La actuación propuesta. Va en el hallazgo y no en la línea de CAPEX
    -- porque una actuación recurrente (P-44) tiene varias líneas y una sola
    -- recomendación: repetirla en cada línea garantizaría que divergieran.
    recommendation     TEXT,
    tenant_recoverable tenant_recoverable NOT NULL DEFAULT 'NA',
    status             finding_status NOT NULL DEFAULT 'BORRADOR',
    owner_user_id      UUID REFERENCES app_user(id),
    created_by         UUID NOT NULL REFERENCES app_user(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at         TIMESTAMPTZ
);

CREATE TABLE capex_item (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    project_id       UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    finding_id       UUID NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
    cost_profile_id  UUID NOT NULL REFERENCES cost_profile(id),

    -- [REQ] P-05 · UN horizonte y UN importe. No cinco columnas: así es
    -- imposible que una línea quede repartida entre dos plazos por descuido.
    time_horizon_id  UUID NOT NULL REFERENCES time_horizon(id),
    -- [REQ] P-05b · Es la BASE IMPONIBLE FINAL: lleva dentro indirectos,
    -- honorarios y contingencia. La cascada nunca se aplica encima.
    amount           NUMERIC(18, 4) NOT NULL DEFAULT 0 CHECK (amount >= 0),
    tax_pct          NUMERIC(7, 4) NOT NULL DEFAULT 0 CHECK (tax_pct >= 0),
    tax_amount       NUMERIC(18, 4) GENERATED ALWAYS AS (ROUND(amount * tax_pct, 2)) STORED,
    total_cost       NUMERIC(18, 4) GENERATED ALWAYS AS (amount + ROUND(amount * tax_pct, 2)) STORED,
    amount_source    amount_source NOT NULL DEFAULT 'MANUAL',

    -- Desglose por medición: opcional [SUP] S-10
    measurement_unit       VARCHAR(20),
    measurement_quantity   NUMERIC(18, 4) CHECK (measurement_quantity IS NULL OR measurement_quantity >= 0),
    measurement_unit_price NUMERIC(18, 4) CHECK (measurement_unit_price IS NULL OR measurement_unit_price >= 0),
    computed_base          NUMERIC(18, 4),
    cascade_breakdown      JSONB,

    -- Trazabilidad del precio
    selected_price_reference_id UUID REFERENCES price_reference(id),
    price_status         price_status NOT NULL DEFAULT 'SIN_PRECIO',
    price_validated_by   UUID REFERENCES app_user(id),
    price_validated_at   TIMESTAMPTZ,
    price_validation_note TEXT,

    calc_version     SMALLINT NOT NULL DEFAULT 1,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- [REQ] La validación es SIEMPRE humana: no hay ruta de código que pueda
    -- dejar VALIDADO sin usuario identificado y sin nota.
    CONSTRAINT validado_exige_persona_y_nota CHECK (
        price_status <> 'VALIDADO'
        OR (price_validated_by IS NOT NULL
            AND price_validated_at IS NOT NULL
            AND price_validation_note IS NOT NULL
            AND length(trim(price_validation_note)) >= 10)
    ),
    -- [REQ] Una partida con precio conserva su procedencia.
    CONSTRAINT precio_exige_referencia CHECK (
        price_status = 'SIN_PRECIO' OR selected_price_reference_id IS NOT NULL
    ),
    -- La medición es todo o nada: media medición no se puede recalcular ni
    -- explicar en el panel «cómo se calcula».
    CONSTRAINT medicion_completa_o_ausente CHECK (
        (measurement_unit IS NULL AND measurement_quantity IS NULL AND measurement_unit_price IS NULL)
        OR (measurement_unit IS NOT NULL AND measurement_quantity IS NOT NULL
            AND measurement_unit_price IS NOT NULL)
    )
);
CREATE INDEX capex_item_project_idx ON capex_item (organization_id, project_id);
CREATE INDEX capex_item_horizon_idx ON capex_item (project_id, time_horizon_id);
-- [REQ] P-44 · Un hallazgo puede generar VARIAS líneas, una por plazo.
--
-- Es el caso de las actuaciones recurrentes: la limpieza de lucernarios hace
-- falta ahora Y otra vez dentro del horizonte de diez años, y así aparece en la
-- tabla real del cliente. Antes había un índice único por `finding_id` que lo
-- impedía; se sustituye por este, que sigue evitando lo que sí es un error:
-- dos líneas del mismo hallazgo en el MISMO plazo, que serían un duplicado.
--
-- P-05 sigue intacta: una LÍNEA tiene un horizonte y un importe. Lo que puede
-- tener varias líneas es la ACTUACIÓN.
CREATE UNIQUE INDEX capex_item_hallazgo_plazo_uniq
    ON capex_item (finding_id, time_horizon_id);

-- ── Sugerencias [REQ] ───────────────────────────────────────────────────────

CREATE TYPE suggestion_type AS ENUM ('CATALOGO', 'PRECIO', 'PLANTILLA', 'APLICACION');
CREATE TYPE suggestion_status AS ENUM (
    'NUEVA', 'EN_REVISION', 'ACEPTADA', 'RECHAZADA', 'DUPLICADA', 'APLICADA'
);

CREATE TABLE suggestion (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    type            suggestion_type NOT NULL,
    status          suggestion_status NOT NULL DEFAULT 'NUEVA',
    title           VARCHAR(160) NOT NULL CHECK (length(trim(title)) > 0),
    body            TEXT NOT NULL,
    payload         JSONB,
    created_by      UUID NOT NULL REFERENCES app_user(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- [REC] El contexto se guarda POR REFERENCIA, nunca copiado. El
    -- administrador ve «sugerencia sobre el proyecto X»; para ver el dato tiene
    -- que entrar en el proyecto, con la auditoría de siempre. Sin esto, el
    -- buzón sería una vía lateral para sacar datos confidenciales.
    context_project_id  UUID REFERENCES project(id) ON DELETE SET NULL,
    context_entity_type VARCHAR(40),
    context_entity_id   UUID,
    context_screen      VARCHAR(60),

    duplicate_of_id     UUID REFERENCES suggestion(id),
    resolved_by         UUID REFERENCES app_user(id),
    resolved_at         TIMESTAMPTZ,
    resolution_note     TEXT,
    applied_entity_type VARCHAR(40),
    applied_entity_id   UUID,

    -- Rechazar exige explicarse. En la base de datos, no solo en la interfaz:
    -- es la única regla que impide que el buzón se convierta en un cementerio.
    CONSTRAINT rechazo_exige_motivo CHECK (
        status <> 'RECHAZADA'
        OR (resolution_note IS NOT NULL AND length(trim(resolution_note)) >= 10)
    ),
    CONSTRAINT resuelta_deja_quien_y_cuando CHECK (
        status IN ('NUEVA', 'EN_REVISION')
        OR (resolved_by IS NOT NULL AND resolved_at IS NOT NULL)
    ),
    CONSTRAINT duplicada_apunta_a_otra CHECK (
        status <> 'DUPLICADA' OR (duplicate_of_id IS NOT NULL AND duplicate_of_id <> id)
    ),
    CONSTRAINT aplicada_apunta_a_lo_creado CHECK (
        status <> 'APLICADA' OR applied_entity_id IS NOT NULL
    )
);
CREATE INDEX suggestion_bandeja_idx ON suggestion (organization_id, status, created_at DESC);
CREATE INDEX suggestion_autor_idx ON suggestion (created_by, created_at DESC);
CREATE INDEX suggestion_duplicado_idx ON suggestion (duplicate_of_id);

CREATE TABLE suggestion_comment (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    suggestion_id UUID NOT NULL REFERENCES suggestion(id) ON DELETE CASCADE,
    author_id     UUID NOT NULL REFERENCES app_user(id),
    body          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Auditoría: solo se añade, nunca se modifica ─────────────────────────────

CREATE TYPE audit_severity AS ENUM ('INFO', 'AVISO', 'CRITICO');

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organization(id),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_user_id   UUID REFERENCES app_user(id),
    action          TEXT NOT NULL,
    entity_type     VARCHAR(60),
    entity_id       UUID,
    project_id      UUID,
    before_data     JSONB,
    after_data      JSONB,
    ip_address      INET,
    severity        audit_severity NOT NULL DEFAULT 'INFO'
);
CREATE INDEX audit_log_org_idx ON audit_log (organization_id, occurred_at DESC);
CREATE INDEX audit_log_entidad_idx ON audit_log (entity_type, entity_id);

-- =============================================================================
--  Barrera 3 · El original nunca se sobrescribe
-- =============================================================================

CREATE TABLE stored_object (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    project_id      UUID REFERENCES project(id) ON DELETE CASCADE,
    kind            VARCHAR(40) NOT NULL,       -- PHOTO_ORIGINAL, DOCUMENT, TEMPLATE…
    storage_key     TEXT NOT NULL UNIQUE,
    sha256          CHAR(64) NOT NULL,
    byte_size       BIGINT NOT NULL,
    mime_type       VARCHAR(120) NOT NULL,
    is_original     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION impedir_sobrescritura_de_original() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.is_original THEN
        IF NEW.storage_key IS DISTINCT FROM OLD.storage_key
           OR NEW.sha256 IS DISTINCT FROM OLD.sha256
           OR NEW.byte_size IS DISTINCT FROM OLD.byte_size THEN
            RAISE EXCEPTION
                'Un objeto original no se sobrescribe: cree un derivado (objeto %)', OLD.id
                USING ERRCODE = 'raise_exception';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER stored_object_original_inmutable
    BEFORE UPDATE ON stored_object
    FOR EACH ROW EXECUTE FUNCTION impedir_sobrescritura_de_original();

CREATE OR REPLACE FUNCTION impedir_borrado_de_original() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.is_original THEN
        RAISE EXCEPTION 'Un objeto original no se borra (objeto %)', OLD.id
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER stored_object_original_no_borrable
    BEFORE DELETE ON stored_object
    FOR EACH ROW EXECUTE FUNCTION impedir_borrado_de_original();

-- La auditoría solo crece.
CREATE OR REPLACE FUNCTION auditoria_solo_se_anade() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'El registro de auditoría no se modifica ni se borra'
        USING ERRCODE = 'raise_exception';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_inmutable
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION auditoria_solo_se_anade();

-- =============================================================================
--  Evidencia fotográfica [REQ] §15
--
--  La invariante del bloque: «mantener siempre el archivo original». La
--  separación que lo hace posible es que el NOMBRE VISIBLE y el OBJETO
--  ALMACENADO son cosas distintas:
--
--    stored_object_id  → el binario. Inmutable, con su propio disparador.
--    original_filename → cómo llegó. Inmutable: es trazabilidad.
--    display_name      → lo que el usuario ve y edita. Un UPDATE de texto.
--    file_extension    → derivada del MIME real. El usuario nunca la escribe.
--
--  Consecuencia: renombrar cuesta O(1), no mueve un solo byte y es imposible
--  perder la extensión porque nadie la escribe.
-- =============================================================================

CREATE TYPE photo_status AS ENUM (
    'SUBIENDO', 'PROCESANDO', 'LISTA', 'CUARENTENA', 'ERROR', 'PAPELERA', 'PURGADA'
);

-- [REQ] Los tres orígenes que el cliente pidió expresamente. Se guarda porque
-- condiciona qué se puede esperar del fichero: el carrete trae HEIC y GPS, la
-- cámara en directo trae orientación EXIF, el ordenador trae volumen.
CREATE TYPE photo_origin AS ENUM ('ORDENADOR', 'CARRETE', 'CAMARA', 'IMPORTACION');

CREATE TYPE photo_version_type AS ENUM (
    'ORIGINAL', 'RENOMBRADA', 'ANOTADA', 'EDITADA', 'EXPORTADA_SIN_METADATOS'
);

CREATE TYPE photo_link_entity AS ENUM (
    'ASSET', 'ZONE', 'FINDING', 'CAPEX_ITEM', 'REPORT_SECTION', 'ASSET_VISIT',
    'DOC_REQUEST_ITEM'
);

CREATE TYPE photo_role AS ENUM ('EVIDENCIA', 'GENERAL', 'DETALLE', 'ANTES', 'DESPUES');

CREATE TYPE photo_derivative_kind AS ENUM (
    'MINIATURA_320', 'VISTA_1600', 'WEB', 'ANOTADA_RASTER'
);

CREATE TABLE photo (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL REFERENCES organization(id),
    project_id        UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    -- [REQ] El activo es PREFERIBLE, no obligatorio: en campo se fotografía
    -- antes de saber a qué activo corresponde. Se avisa, no se bloquea.
    asset_id          UUID REFERENCES asset(id) ON DELETE SET NULL,
    zone_id           UUID REFERENCES zone(id),
    capex_code_id     UUID REFERENCES capex_code(id),

    stored_object_id  UUID NOT NULL REFERENCES stored_object(id),
    origin            photo_origin NOT NULL DEFAULT 'ORDENADOR',
    status            photo_status NOT NULL DEFAULT 'SUBIENDO',
    status_reason     TEXT,

    original_filename VARCHAR(260) NOT NULL,
    display_name      VARCHAR(200) NOT NULL,
    file_extension    VARCHAR(12)  NOT NULL,
    mime_type         VARCHAR(120) NOT NULL,
    sha256            CHAR(64) NOT NULL,
    phash             CHAR(16),
    byte_size         BIGINT NOT NULL,
    width_px          INT,
    height_px         INT,

    -- [REQ] Si no hay EXIF, estos campos quedan VACÍOS. No se infiere la fecha
    -- del sistema de archivos ni la ubicación del activo: un dato inventado en
    -- una evidencia técnica es peor que un dato ausente.
    taken_at          TIMESTAMPTZ,
    gps_latitude      NUMERIC(9, 6),
    gps_longitude     NUMERIC(9, 6),
    gps_altitude_m    NUMERIC(8, 2),
    camera_make       VARCHAR(80),
    camera_model      VARCHAR(120),
    orientation       SMALLINT,
    exif_raw          JSONB,

    photo_category    VARCHAR(60),
    caption           TEXT,
    description       TEXT,
    tags              TEXT[] NOT NULL DEFAULT '{}',

    duplicate_of_photo_id UUID REFERENCES photo(id),

    include_in_report BOOLEAN NOT NULL DEFAULT FALSE,
    report_order      INT,
    report_section    VARCHAR(60),

    uploaded_by       UUID NOT NULL REFERENCES app_user(id),
    uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at        TIMESTAMPTZ,
    purged_at         TIMESTAMPTZ,

    CONSTRAINT photo_gps_completo
        CHECK ((gps_latitude IS NULL) = (gps_longitude IS NULL)),
    CONSTRAINT photo_gps_en_rango
        CHECK (gps_latitude IS NULL
               OR (gps_latitude BETWEEN -90 AND 90 AND gps_longitude BETWEEN -180 AND 180)),
    -- La extensión se guarda SIN punto: el punto lo pone quien compone el
    -- nombre de descarga. Guardarlo a veces sí y a veces no produce `foto..jpg`.
    CONSTRAINT photo_extension_sin_punto CHECK (file_extension NOT LIKE '.%'),
    CONSTRAINT photo_extension_no_vacia  CHECK (length(file_extension) > 0),
    -- [REQ] §15.1 · El nombre visible no lleva extensión: la fija el servidor
    -- desde el MIME real, y el usuario no puede cambiarla renombrando.
    CONSTRAINT photo_nombre_sin_extension
        CHECK (lower(display_name) NOT LIKE '%.' || lower(file_extension)),
    CONSTRAINT photo_papelera_coherente
        CHECK ((status IN ('PAPELERA', 'PURGADA')) = (deleted_at IS NOT NULL)),
    CONSTRAINT photo_purga_coherente
        CHECK ((status = 'PURGADA') = (purged_at IS NOT NULL)),
    CONSTRAINT photo_duplicado_de_otra
        CHECK (duplicate_of_photo_id IS DISTINCT FROM id)
);

-- [REQ] §15.5 · El mismo fichero no entra dos veces en el mismo proyecto, pero
-- sí puede existir en dos proyectos: dos encargos sobre el mismo edificio es
-- legítimo. Parcial por `deleted_at` para que la papelera no bloquee una
-- resubida.
CREATE UNIQUE INDEX photo_sha256_uniq
    ON photo (project_id, sha256) WHERE deleted_at IS NULL;

CREATE INDEX photo_activo_idx   ON photo (project_id, asset_id);
CREATE INDEX photo_informe_idx  ON photo (project_id, include_in_report, report_order);
CREATE INDEX photo_phash_idx    ON photo (project_id, phash) WHERE phash IS NOT NULL;
CREATE INDEX photo_exif_idx     ON photo USING GIN (exif_raw);
CREATE INDEX photo_etiquetas_idx ON photo USING GIN (tags);

-- ── Barrera 3 aplicada a la fotografía ──────────────────────────────────────
-- El disparador de `stored_object` ya protege el binario. Este protege la
-- FICHA: sin él, se podría reapuntar una foto a otro objeto y el original
-- seguiría intacto pero ya no sería el original *de esta foto*.
CREATE OR REPLACE FUNCTION impedir_sobrescritura_de_foto() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.stored_object_id  IS DISTINCT FROM OLD.stored_object_id
       OR NEW.sha256         IS DISTINCT FROM OLD.sha256
       OR NEW.byte_size      IS DISTINCT FROM OLD.byte_size
       OR NEW.original_filename IS DISTINCT FROM OLD.original_filename
       OR NEW.file_extension IS DISTINCT FROM OLD.file_extension THEN
        RAISE EXCEPTION
            'El original de una fotografía no se sobrescribe: renombre display_name (foto %)',
            OLD.id
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER photo_original_inmutable
    BEFORE UPDATE ON photo
    FOR EACH ROW EXECUTE FUNCTION impedir_sobrescritura_de_foto();

-- [REQ] §15.9 · El borrado siempre es lógico. Solo desaparece de la tabla lo
-- que ya se purgó con autorización, y el registro de auditoría sobrevive.
CREATE OR REPLACE FUNCTION impedir_borrado_fisico_de_foto() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status <> 'PURGADA' THEN
        RAISE EXCEPTION
            'Una fotografía no se borra físicamente: pásela a la papelera (foto %)', OLD.id
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER photo_borrado_logico
    BEFORE DELETE ON photo
    FOR EACH ROW EXECUTE FUNCTION impedir_borrado_fisico_de_foto();

-- ── Versiones ───────────────────────────────────────────────────────────────
CREATE TABLE photo_version (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    photo_id         UUID NOT NULL REFERENCES photo(id) ON DELETE CASCADE,
    version_number   INT NOT NULL,
    version_type     photo_version_type NOT NULL,
    -- [REC] NULL cuando la versión solo cambia metadatos. Con 1.500 fotos por
    -- proyecto y renombrados en lote, duplicar el binario por un cambio de
    -- nombre multiplicaría el coste sin aportar nada.
    stored_object_id UUID REFERENCES stored_object(id),
    display_name     VARCHAR(200) NOT NULL,
    annotations      JSONB,
    notes            TEXT,
    is_current       BOOLEAN NOT NULL DEFAULT TRUE,
    created_by       UUID NOT NULL REFERENCES app_user(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (photo_id, version_number),
    CONSTRAINT photo_version_numero_valido CHECK (version_number >= 1),
    -- La v1 es siempre ORIGINAL y siempre lleva binario.
    CONSTRAINT photo_version_primera_es_original
        CHECK ((version_number = 1) = (version_type = 'ORIGINAL')),
    CONSTRAINT photo_version_original_con_binario
        CHECK (version_type <> 'ORIGINAL' OR stored_object_id IS NOT NULL),
    CONSTRAINT photo_version_renombrada_sin_binario
        CHECK (version_type <> 'RENOMBRADA' OR stored_object_id IS NULL),
    CONSTRAINT photo_version_anotada_con_capa
        CHECK (version_type <> 'ANOTADA' OR annotations IS NOT NULL)
);

CREATE UNIQUE INDEX photo_version_vigente_uniq
    ON photo_version (photo_id) WHERE is_current;

-- [REQ] §15.2 · «La v1 es siempre ORIGINAL y no se puede borrar ni modificar.»
-- Restaurar una versión anterior crea una versión nueva; no reescribe la
-- historia. Se permite el único cambio que no reescribe nada: dejar de ser la
-- vigente cuando aparece una versión posterior.
CREATE OR REPLACE FUNCTION proteger_version_original() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.version_type = 'ORIGINAL' THEN
            RAISE EXCEPTION 'La versión original no se borra (foto %)', OLD.photo_id
                USING ERRCODE = 'raise_exception';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.version_type = 'ORIGINAL' THEN
        IF NEW.version_type     IS DISTINCT FROM OLD.version_type
           OR NEW.stored_object_id IS DISTINCT FROM OLD.stored_object_id
           OR NEW.display_name  IS DISTINCT FROM OLD.display_name
           OR NEW.version_number IS DISTINCT FROM OLD.version_number THEN
            RAISE EXCEPTION 'La versión original no se modifica (foto %)', OLD.photo_id
                USING ERRCODE = 'raise_exception';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER photo_version_original_protegida
    BEFORE UPDATE OR DELETE ON photo_version
    FOR EACH ROW EXECUTE FUNCTION proteger_version_original();

-- ── Derivados ───────────────────────────────────────────────────────────────
-- Desechables y regenerables: si se pierden, se vuelven a construir desde el
-- original. Por eso su `stored_object` va con `is_original = FALSE` y sí se
-- puede borrar.
CREATE TABLE photo_derivative (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    photo_id         UUID NOT NULL REFERENCES photo(id) ON DELETE CASCADE,
    kind             photo_derivative_kind NOT NULL,
    stored_object_id UUID NOT NULL REFERENCES stored_object(id),
    width_px         INT,
    height_px        INT,
    byte_size        BIGINT NOT NULL,
    -- [REQ] §15.6 · Los derivados que se insertan en el PPTX no arrastran EXIF.
    has_metadata     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (photo_id, kind)
);

-- ── Asociaciones múltiples ──────────────────────────────────────────────────
-- [LIM] Polimórfica: no lleva FK real. La integridad se verifica en la
-- aplicación. Compromiso aceptado a cambio de asociar una foto a diez tipos de
-- entidad sin diez columnas anulables.
CREATE TABLE photo_link (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    photo_id         UUID NOT NULL REFERENCES photo(id) ON DELETE CASCADE,
    entity_type      photo_link_entity NOT NULL,
    entity_id        UUID NOT NULL,
    role             photo_role NOT NULL DEFAULT 'EVIDENCIA',
    sort_order       INT NOT NULL DEFAULT 0,
    created_by       UUID NOT NULL REFERENCES app_user(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (photo_id, entity_type, entity_id)
);

CREATE INDEX photo_link_entidad_idx ON photo_link (entity_type, entity_id, sort_order);

-- La foto principal del activo, ahora que `photo` existe. `SET NULL` y no
-- `CASCADE`: mandar una foto a la papelera no puede borrar el activo.
ALTER TABLE asset
    ADD CONSTRAINT asset_foto_principal_fk
    FOREIGN KEY (main_photo_id) REFERENCES photo(id) ON DELETE SET NULL;

-- =============================================================================
--  Documentos [REQ] §15.11
--
--  Comparten con las fotografías todo lo que importa —original inmutable, MIME
--  real, hash, borrado lógico, descarga auditada— y se diferencian en cuatro
--  cosas: no llevan derivados de imagen, tienen nivel de confidencialidad,
--  tienen versionado explícito y se clasifican solos desde la línea del
--  checklist a la que se adjuntan.
-- =============================================================================

CREATE TYPE doc_type AS ENUM (
    'LICENCIA_URBANISTICA', 'PROYECTO', 'CONTRATO_MANTENIMIENTO', 'LEGALIZACION',
    'CERTIFICADO', 'GARANTIA', 'PLANO', 'QA', 'INFORME_PREVIO', 'FICHA_TECNICA', 'OTRO'
);

CREATE TYPE doc_confidentiality AS ENUM ('INTERNO', 'CONFIDENCIAL', 'RESTRINGIDO');

CREATE TYPE doc_status AS ENUM ('PROCESANDO', 'LISTO', 'CUARENTENA', 'ERROR', 'PAPELERA');

CREATE TABLE document (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id       UUID NOT NULL REFERENCES organization(id),
    project_id            UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    asset_id              UUID REFERENCES asset(id) ON DELETE SET NULL,
    doc_request_item_id   UUID REFERENCES doc_request_item(id) ON DELETE SET NULL,
    qa_round_id           UUID REFERENCES qa_round(id) ON DELETE SET NULL,

    stored_object_id      UUID NOT NULL REFERENCES stored_object(id),
    original_filename     VARCHAR(260) NOT NULL,
    display_name          VARCHAR(200) NOT NULL,
    file_extension        VARCHAR(12) NOT NULL,
    mime_type             VARCHAR(120) NOT NULL,
    sha256                CHAR(64) NOT NULL,
    byte_size             BIGINT NOT NULL,

    doc_type              doc_type NOT NULL DEFAULT 'OTRO',
    confidentiality       doc_confidentiality NOT NULL DEFAULT 'INTERNO',
    status                doc_status NOT NULL DEFAULT 'LISTO',
    -- [REC] Versionado explícito: las rondas de Q&A y la documentación recibida
    -- se sustituyen con frecuencia, y hay que saber cuál era la vigente EN LA
    -- FECHA DEL INFORME. Sin esto, un informe firmado sobre la versión 2 de un
    -- plano parecería basarse en la 5.
    version_number        SMALLINT NOT NULL DEFAULT 1,
    supersedes_document_id UUID REFERENCES document(id),

    notes                 TEXT,
    uploaded_by           UUID NOT NULL REFERENCES app_user(id),
    uploaded_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at            TIMESTAMPTZ,

    CONSTRAINT document_version_valida CHECK (version_number >= 1),
    CONSTRAINT document_no_se_sustituye_a_si_mismo
        CHECK (supersedes_document_id IS DISTINCT FROM id),
    CONSTRAINT document_extension_sin_punto CHECK (file_extension NOT LIKE '.%'),
    CONSTRAINT document_papelera_coherente
        CHECK ((status = 'PAPELERA') = (deleted_at IS NOT NULL))
);

-- El mismo fichero no entra dos veces en el mismo proyecto.
CREATE UNIQUE INDEX document_sha256_uniq
    ON document (project_id, sha256) WHERE deleted_at IS NULL;
CREATE INDEX document_tipo_idx ON document (project_id, doc_type);
CREATE INDEX document_solicitud_idx ON document (doc_request_item_id);
CREATE INDEX document_qa_idx ON document (qa_round_id, version_number);

-- Misma barrera que en las fotografías: la ficha no puede reapuntarse a otro
-- binario. El original de `stored_object` ya está protegido por su disparador.
CREATE OR REPLACE FUNCTION impedir_sobrescritura_de_documento() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.stored_object_id IS DISTINCT FROM OLD.stored_object_id
       OR NEW.sha256 IS DISTINCT FROM OLD.sha256
       OR NEW.original_filename IS DISTINCT FROM OLD.original_filename
       OR NEW.file_extension IS DISTINCT FROM OLD.file_extension THEN
        RAISE EXCEPTION 'El original de un documento no se sobrescribe (documento %)', OLD.id
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER document_original_inmutable
    BEFORE UPDATE ON document
    FOR EACH ROW EXECUTE FUNCTION impedir_sobrescritura_de_documento();

-- =============================================================================
--  Sesiones de refresco
--
--  Del token de refresco se guarda **solo su SHA-256**, nunca el token. Una
--  filtración de esta tabla no permite iniciar sesión como nadie, que es
--  exactamente lo que un token guardado en claro sí permitiría.
-- =============================================================================

CREATE TABLE user_session (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES organization(id),
    user_id            UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    refresh_token_hash CHAR(64) NOT NULL UNIQUE,
    -- Todas las sesiones nacidas del mismo inicio comparten familia. Si se
    -- reutiliza un token ya rotado, se revoca la familia entera: es la señal
    -- de que alguien copió el token, y no hay forma de saber quién de los dos
    -- es el legítimo.
    family_id          UUID NOT NULL,
    issued_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at         TIMESTAMPTZ NOT NULL,
    revoked_at         TIMESTAMPTZ,
    revoked_reason     VARCHAR(40),
    replaced_by_id     UUID REFERENCES user_session(id),
    user_agent         VARCHAR(300),
    ip_address         INET,

    CONSTRAINT user_session_caduca_despues CHECK (expires_at > issued_at)
);

CREATE INDEX user_session_usuario_idx ON user_session (user_id, issued_at DESC);
CREATE INDEX user_session_familia_idx ON user_session (family_id) WHERE revoked_at IS NULL;

-- ── El problema del huevo y la gallina del inicio de sesión ─────────────────
--
-- La RLS decide qué filas se ven a partir de `app.current_org_id`. Al iniciar
-- sesión **todavía no se sabe la organización**: se averigua leyendo el
-- usuario, que es justo lo que la RLS impide. Sin resolverlo, el login sería
-- imposible... o habría que dar `BYPASSRLS` al usuario de aplicación, que
-- convertiría toda la seguridad del esquema en decoración.
--
-- Se resuelven **solo las dos búsquedas** que tienen ese problema, con
-- funciones `SECURITY DEFINER` de alcance mínimo. Todo lo demás —incluidos los
-- contadores de intentos y la creación de la sesión— ocurre después, ya con
-- contexto, bajo las políticas normales.
--
-- `SET search_path` es obligatorio en una función `SECURITY DEFINER`: sin él,
-- quien pueda crear objetos en otro esquema podría secuestrar la resolución de
-- nombres y ejecutar su código con los privilegios del propietario.

CREATE OR REPLACE FUNCTION login_buscar_usuario(p_email TEXT)
RETURNS TABLE (
    id UUID, organization_id UUID, password_hash TEXT, org_role org_role,
    can_manage_suggestions BOOLEAN, is_active BOOLEAN,
    failed_login_attempts SMALLINT, locked_until TIMESTAMPTZ
)
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT u.id, u.organization_id, u.password_hash, u.org_role,
           u.can_manage_suggestions, u.is_active,
           u.failed_login_attempts, u.locked_until
    FROM app_user u
    JOIN organization o ON o.id = u.organization_id
    WHERE lower(u.email) = lower(p_email) AND o.is_active;
$$;

CREATE OR REPLACE FUNCTION login_buscar_sesion(p_hash TEXT)
RETURNS TABLE (
    id UUID, user_id UUID, organization_id UUID, family_id UUID,
    expires_at TIMESTAMPTZ, revoked_at TIMESTAMPTZ,
    org_role org_role, can_manage_suggestions BOOLEAN, is_active BOOLEAN
)
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT s.id, s.user_id, s.organization_id, s.family_id,
           s.expires_at, s.revoked_at,
           u.org_role, u.can_manage_suggestions, u.is_active
    FROM user_session s
    JOIN app_user u ON u.id = s.user_id
    WHERE s.refresh_token_hash = p_hash;
$$;

-- =============================================================================
--  Barreras 1 y 2 · Row Level Security
--
--  El usuario de aplicación NO es propietario de estas tablas y NO tiene
--  BYPASSRLS: si lo fuera, las políticas no se le aplicarían y todo esto sería
--  decorativo. La prueba `test_rls` lo comprueba.
-- =============================================================================

CREATE OR REPLACE FUNCTION org_actual() RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.current_org_id', TRUE), '')::UUID;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION usuario_actual() RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.current_user_id', TRUE), '')::UUID;
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION puede_gestionar_sugerencias() RETURNS BOOLEAN AS $$
    SELECT COALESCE(NULLIF(current_setting('app.can_manage_suggestions', TRUE), ''), 'false')::BOOLEAN;
$$ LANGUAGE sql STABLE;

-- Aislamiento por organización: la misma política en todas las tablas con
-- organization_id. Se aplica también a INSERT/UPDATE (WITH CHECK), no solo a
-- SELECT: sin eso, un usuario podría escribir filas en otra organización.
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'app_user', 'client', 'project', 'asset', 'cost_profile',
        'price_source', 'price_reference', 'finding', 'capex_item',
        'stored_object', 'audit_log', 'suggestion_comment',
        'project_phase', 'doc_request_item', 'vdr_link', 'asset_visit',
        'qa_round', 'phase_event',
        'photo', 'photo_version', 'photo_derivative', 'photo_link',
        'user_session', 'project_member', 'asset_assignment', 'qa_question', 'document'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format($f$
            CREATE POLICY %1$I_aislamiento_org ON %1$I
            USING (organization_id = org_actual())
            WITH CHECK (organization_id = org_actual())
        $f$, t);
    END LOOP;
END $$;

-- Catálogos: las filas del sistema (organization_id IS NULL) las ve todo el
-- mundo; las propias, solo su organización.
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'asset_typology', 'zone', 'capex_code', 'risk_level',
        'capex_concept', 'time_horizon', 'doc_request_category'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format($f$
            CREATE POLICY %1$I_catalogo ON %1$I
            USING (organization_id IS NULL OR organization_id = org_actual())
            WITH CHECK (organization_id = org_actual())
        $f$, t);
    END LOOP;
END $$;

-- =============================================================================
--  [REQ] «Solo el administrador ve las propuestas»
--
--  El requisito del cliente vive AQUÍ, y solo aquí. Si mañana alguien escribe
--  una consulta nueva y olvida filtrar por autor, la fila sigue sin aparecer.
--  Implementarlo en el servicio habría dejado el requisito a merced de que
--  nadie se despiste.
-- =============================================================================

ALTER TABLE suggestion ENABLE ROW LEVEL SECURITY;
ALTER TABLE suggestion FORCE ROW LEVEL SECURITY;

CREATE POLICY suggestion_lectura ON suggestion FOR SELECT
    USING (
        organization_id = org_actual()
        AND (
            created_by = usuario_actual()      -- [REQ] P-40 · el autor ve las suyas
            OR puede_gestionar_sugerencias()   -- [REQ] el administrador, todas
        )
    );

-- Crear puede cualquiera, pero solo en su organización y a su propio nombre:
-- así un cuerpo malicioso con created_by ajeno no cuela.
CREATE POLICY suggestion_alta ON suggestion FOR INSERT
    WITH CHECK (organization_id = org_actual() AND created_by = usuario_actual());

-- Resolver es exclusivo de quien gestiona el buzón.
CREATE POLICY suggestion_resolucion ON suggestion FOR UPDATE
    USING (organization_id = org_actual() AND puede_gestionar_sugerencias())
    WITH CHECK (organization_id = org_actual());

-- El hilo de comentarios sigue la visibilidad de su sugerencia.
DROP POLICY IF EXISTS suggestion_comment_aislamiento_org ON suggestion_comment;
CREATE POLICY suggestion_comment_visibilidad ON suggestion_comment
    USING (
        organization_id = org_actual()
        AND EXISTS (
            SELECT 1 FROM suggestion s
            WHERE s.id = suggestion_comment.suggestion_id
              AND (s.created_by = usuario_actual() OR puede_gestionar_sugerencias())
        )
    )
    WITH CHECK (organization_id = org_actual() AND author_id = usuario_actual());

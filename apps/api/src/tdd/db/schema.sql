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
--
-- `UNIQUE NULLS NOT DISTINCT` no es un detalle. En PostgreSQL, por defecto,
-- dos NULL se consideran **distintos** en un índice único: con un
-- `UNIQUE (organization_id, code)` a secas, las filas del sistema —que son
-- justo las que llevan `organization_id` NULL— no estarían protegidas por
-- nada, y `ON CONFLICT (organization_id, code) DO NOTHING` no dispararía
-- jamás para ellas. Volver a ejecutar la semilla duplicaría el catálogo
-- entero, y el árbol de códigos quedaría con dos padres del mismo código.

CREATE TABLE asset_typology (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    code            VARCHAR(40) NOT NULL,
    name_es         VARCHAR(120) NOT NULL,
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order      INT NOT NULL DEFAULT 0,
    UNIQUE NULLS NOT DISTINCT (organization_id, code)
);

CREATE TABLE zone (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    code            VARCHAR(40) NOT NULL,
    name_es         VARCHAR(120) NOT NULL,
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order      INT NOT NULL DEFAULT 0,
    UNIQUE NULLS NOT DISTINCT (organization_id, code)
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
    UNIQUE NULLS NOT DISTINCT (organization_id, code),
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
    UNIQUE NULLS NOT DISTINCT (organization_id, code)
);

CREATE TABLE capex_concept (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    code            VARCHAR(40) NOT NULL,
    name_es         VARCHAR(120) NOT NULL,
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE NULLS NOT DISTINCT (organization_id, code)
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
    UNIQUE NULLS NOT DISTINCT (organization_id, code),
    CONSTRAINT horizonte_rango_coherente
        CHECK (year_from IS NULL OR year_to IS NULL OR year_from <= year_to)
);

-- [REQ] §3.2 · Los 14 sistemas técnicos. Son el eje transversal: clasifican la
-- fotografía en campo y agrupan el inventario de equipo.
--
-- No se funden con los capítulos de coste, y la razón está en §5.8 del
-- documento: «Protección contra incendios» es UNA categoría fotográfica y DOS
-- capítulos (pasiva y activa). Por eso `capex_chapter` es texto —«H06 + H10»—
-- y no una clave ajena: forzarla obligaría a elegir uno de los dos y perdería
-- justo el dato que motiva la distinción.
CREATE TABLE technical_system (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    code            VARCHAR(40) NOT NULL,
    name_es         VARCHAR(120) NOT NULL,
    capex_chapter   VARCHAR(40),
    sort_order      INT NOT NULL DEFAULT 0,
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE NULLS NOT DISTINCT (organization_id, code)
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

    -- [REQ] La revisión de documentación con IA es OPT-IN POR ENCARGO y nace
    -- apagada. La restricción del cliente exige «autorización expresa y
    -- verificable»: la restricción de abajo es lo que la hace verificable, al
    -- impedir que el interruptor esté encendido sin que conste quién lo
    -- encendió y cuándo. Un BOOLEAN suelto no habría sido una autorización,
    -- sino un ajuste.
    ai_doc_review_enabled     BOOLEAN NOT NULL DEFAULT FALSE,
    ai_doc_review_enabled_at  TIMESTAMPTZ,
    ai_doc_review_enabled_by  UUID REFERENCES app_user(id),

    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- [REQ] Control de concurrencia optimista. Lo incrementa el disparador
    -- `project_version`, nunca la aplicación: así no hay forma de que un UPDATE
    -- se salte el contador por olvido.
    row_version      INTEGER NOT NULL DEFAULT 1,
    updated_by       UUID REFERENCES app_user(id),
    deleted_at       TIMESTAMPTZ,
    UNIQUE (organization_id, internal_code),

    CONSTRAINT project_revision_ia_con_autoria
        CHECK (NOT ai_doc_review_enabled
               OR (ai_doc_review_enabled_at IS NOT NULL
                   AND ai_doc_review_enabled_by IS NOT NULL))
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
    -- [REQ] Los datos que aporta la MEMORIA TÉCNICA del activo. Se separan de
    -- los de arriba porque tienen otro origen: los de arriba los teclea quien
    -- da de alta el encargo; éstos salen del documento que entrega la
    -- propiedad, y por eso llevan `memoria_validada_at` como testigo de que
    -- alguien los miró antes de darlos por buenos.
    cadastral_reference VARCHAR(30),
    developer           VARCHAR(200),
    project_date        DATE,
    secondary_use       VARCHAR(120),
    -- La OCUPACIÓN: lo que el edificio ocupa en la parcela, que es como lo
    -- llama la memoria técnica. NO es `total_built_sqm`, que suma
    -- todas las plantas: un edificio de cuatro alturas ocupa la cuarta parte.
    occupied_area_sqm  NUMERIC(14, 2),
    urbanised_area_sqm  NUMERIC(14, 2),
    -- Útil, no alquilable: `lettable_area_sqm` es lo que se factura y suele
    -- llevar repercusión de zonas comunes. Confundirlas descuadra el € / m².
    usable_area_sqm     NUMERIC(14, 2),
    -- Del edificio entero. `warehouse_height_m` es la del almacén, que en una
    -- nave con oficinas en altillo no es la misma.
    max_height_m        NUMERIC(6, 2),
    loading_docks       SMALLINT,
    parking_spaces      INTEGER,
    -- Quién y cuándo dio por buenos los datos extraídos de la memoria. NULL
    -- significa «nadie todavía», y la ficha lo dice en pantalla: un dato
    -- extraído por una máquina y no revisado no puede parecerse a uno tecleado
    -- por un técnico.
    memoria_validada_at TIMESTAMPTZ,
    memoria_validada_por UUID REFERENCES app_user(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- [REQ] Control de concurrencia optimista. Lo incrementa el disparador
    -- `asset_version`, nunca la aplicación: así no hay forma de que un UPDATE
    -- se salte el contador por olvido.
    row_version      INTEGER NOT NULL DEFAULT 1,
    updated_by       UUID REFERENCES app_user(id),
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
               AND COALESCE(lettable_area_sqm, 0) >= 0),
    -- Las superficies de la memoria, con la misma vara de medir que las de
    -- arriba. No se comprueba que la ocupación quepa en la parcela ni que la útil
    -- sea menor que la construida: son ciertas casi siempre, pero una parcela
    -- con edificación fuera de linderos o una útil mal medida existen, y un
    -- CHECK que rechaza el dato real obliga a mentirle a la aplicación.
    CONSTRAINT asset_superficies_memoria_no_negativas
        CHECK (COALESCE(occupied_area_sqm, 0) >= 0 AND COALESCE(urbanised_area_sqm, 0) >= 0
               AND COALESCE(usable_area_sqm, 0) >= 0 AND COALESCE(max_height_m, 0) >= 0),
    CONSTRAINT asset_conteos_no_negativos
        CHECK (COALESCE(loading_docks, 0) >= 0 AND COALESCE(parking_spaces, 0) >= 0),
    -- La validación de la memoria es de quien la firma: o están las dos cosas
    -- o no está ninguna. Una fecha sin persona no vale como testigo.
    CONSTRAINT asset_memoria_validada_completa
        CHECK ((memoria_validada_at IS NULL) = (memoria_validada_por IS NULL))
);

CREATE UNIQUE INDEX asset_codigo_uniq
    ON asset (project_id, asset_code) WHERE asset_code IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX asset_proyecto_idx ON asset (project_id) WHERE deleted_at IS NULL;

-- ── Zonas del activo: privadas y comunes ────────────────────────────────────
--
-- [REQ] La memoria técnica declara qué zonas tiene el edificio y cuáles son
-- privadas y cuáles comunes.
--
-- La marca vive AQUÍ y no en el catálogo `zone` a propósito, y es una decisión
-- del cliente: la misma zona cambia de naturaleza según el edificio. «Aseos»
-- es zona común en un edificio de oficinas multiinquilino y privada en una
-- nave de un solo ocupante. Puesta en el catálogo habría un único valor para
-- toda la organización y no admitiría excepciones.
--
-- [REC] Es lo que permite responder «¿cuánto del CAPEX recae sobre la
-- propiedad y cuánto es repercutible?» sin teclearlo línea a línea: la
-- recuperabilidad de un hallazgo puede proponerse desde la zona en la que
-- está. Proponerse, no decidirse: `finding.tenant_recoverable` se sigue
-- pudiendo cambiar a mano, porque el contrato de arrendamiento manda sobre
-- cualquier regla general.

CREATE TYPE zone_tenure AS ENUM ('PRIVADA', 'COMUN');

CREATE TABLE asset_zone (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    asset_id        UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    zone_id         UUID NOT NULL REFERENCES zone(id),
    tenure          zone_tenure NOT NULL,
    -- Opcional: la memoria a veces da la superficie de cada zona y a veces no.
    area_sqm        NUMERIC(14, 2),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Una zona se clasifica UNA vez por activo. Sin esto, dos importaciones de
    -- la misma memoria dejarían la misma zona declarada privada y común a la
    -- vez, y la propuesta de recuperabilidad dependería del orden de lectura.
    UNIQUE (asset_id, zone_id),
    CONSTRAINT asset_zone_superficie_no_negativa
        CHECK (COALESCE(area_sqm, 0) >= 0)
);

CREATE INDEX asset_zone_activo_idx ON asset_zone (asset_id);

-- ── Superficie útil por planta ──────────────────────────────────────────────
--
-- [REQ] La memoria técnica no da solo la útil total: la da DIVIDIDA por planta
-- —«Útil planta baja 6.023 m², Útil planta primera 1.234 m², Útil total
-- 7.257 m²»—. Guardar solo el total tiraba ese desglose, que es justo lo que
-- hace falta para repartir un CAPEX de oficinas entre plantas.
--
-- [REC] El total se queda en `asset.usable_area_sqm` y NO se calcula sumando
-- esta tabla. La memoria lo da explícito, y las dos cifras pueden no cuadrar:
-- una memoria puede itemizar solo las plantas de oficinas y dar un total que
-- incluye el altillo. Derivar el total de la suma haría que la aplicación
-- contradijera al documento del que salió, sin decírselo a nadie.

CREATE TABLE asset_floor (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    asset_id        UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    -- Con las palabras de la memoria: «Planta baja», «Altillo», «Sótano -1».
    -- No se normaliza a un catálogo porque cada edificio las llama a su modo y
    -- forzar un vocabulario común perdería el nombre que usa el documento.
    label           VARCHAR(60) NOT NULL,
    -- Para ordenarlas: 0 baja, 1 primera, -1 sótano. Nulo cuando la memoria no
    -- deja deducirlo —«Altillo» no tiene número— y entonces manda `orden`.
    level           SMALLINT,
    usable_area_sqm NUMERIC(14, 2),
    built_area_sqm  NUMERIC(14, 2),
    notes           TEXT,
    orden           SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (asset_id, label),
    CONSTRAINT asset_floor_superficies_no_negativas
        CHECK (COALESCE(usable_area_sqm, 0) >= 0 AND COALESCE(built_area_sqm, 0) >= 0)
);

CREATE INDEX asset_floor_activo_idx ON asset_floor (asset_id, orden);

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

-- ── El árbol físico del edificio [REC] §8.4 ─────────────────────────────────
--
--  `zone` y `location_node` son cosas distintas y las dos hacen falta:
--
--  * `zone` es la **clasificación normalizada** que exige el CAPEX
--    («Cubierta», «Cuartos Técnicos»): común a todos los proyectos y
--    dependiente de la tipología. Es lo que permite agregar por zona en el
--    informe y comparar entre encargos.
--  * `location_node` es la **ubicación concreta de este edificio**
--    («Cubierta / Sala de máquinas 2»). Es lo que permite volver a encontrar
--    algo seis meses después.
--
--  Fundirlas obligaría a elegir entre agregar por zona o localizar una foto, y
--  las dos cosas se usan. Una línea de CAPEX usa `zone`; una fotografía puede
--  usar las dos.
--
--  Es un árbol y no tres tablas rígidas —zona, planta, espacio— porque los
--  edificios no se dejan: una nave puede tener muelles sin planta, y un hotel
--  tiene plantas dentro de plantas. `node_type` dice qué es cada nodo sin
--  imponer cuántos niveles hay.

CREATE TYPE location_node_type AS ENUM ('ZONA', 'PLANTA', 'ESPACIO');

CREATE TABLE location_node (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    asset_id        UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    parent_id       UUID REFERENCES location_node(id) ON DELETE CASCADE,
    node_type       location_node_type NOT NULL,

    -- El enlace con el catálogo, opcional. Un nodo de tipo ZONA suele apuntar
    -- a su `zone`; una sala concreta no tiene por qué.
    zone_id         UUID REFERENCES zone(id),
    code            VARCHAR(60),
    name            VARCHAR(160) NOT NULL,
    level_order     SMALLINT NOT NULL DEFAULT 0,

    -- La ruta la calcula el disparador `location_node_ruta`, nunca la
    -- aplicación: una ruta escrita a mano que no case con `parent_id` produce
    -- un árbol que se lee distinto según por dónde se mire.
    path            LTREE NOT NULL,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,

    CONSTRAINT location_node_no_es_su_propio_padre CHECK (parent_id IS DISTINCT FROM id),
    CONSTRAINT location_node_con_nombre CHECK (length(trim(name)) > 0)
);

CREATE INDEX location_node_activo_idx ON location_node (asset_id, node_type);
CREATE INDEX location_node_path_idx ON location_node USING GIST (path);
-- Dos espacios con el mismo nombre bajo el mismo padre serían indistinguibles
-- en el desplegable y en el nombre del fichero. `lower` porque «Sala 1» y
-- «sala 1» son el mismo sitio para quien los escribe.
-- `NULLS NOT DISTINCT` es imprescindible, igual que en `asset_assignment`:
-- sin él, dos raíces tienen `parent_id` NULL, dos NULL se consideran distintos
-- y el mismo activo admitiría dos «Cubierta» de primer nivel.
CREATE UNIQUE INDEX location_node_hermanos_uniq
    ON location_node (asset_id, parent_id, lower(name))
    NULLS NOT DISTINCT
    WHERE deleted_at IS NULL;

--  La etiqueta de `ltree` sale del `id`: solo admite [A-Za-z0-9_], así que un
--  nombre como «Sala de máquinas 2» no vale, y el `code` es opcional. Con el
--  `id` la ruta es estable aunque se renombre el nodo.
CREATE OR REPLACE FUNCTION location_node_ruta() RETURNS TRIGGER AS $$
DECLARE ruta_padre LTREE;
BEGIN
    IF NEW.parent_id IS NULL THEN
        NEW.path := text2ltree(replace(NEW.id::TEXT, '-', '_'));
    ELSE
        SELECT path INTO ruta_padre FROM location_node WHERE id = NEW.parent_id;
        IF ruta_padre IS NULL THEN
            RAISE EXCEPTION 'El nodo padre % no existe', NEW.parent_id
                USING ERRCODE = 'foreign_key_violation';
        END IF;
        -- Un ciclo dejaría el árbol irrecorrible y la consulta de descendientes
        -- en un bucle infinito. La clave ajena no lo impide: A puede ser padre
        -- de B y B de A sin violarla.
        IF ruta_padre OPERATOR(public.<@) text2ltree(replace(NEW.id::TEXT, '-', '_')) THEN
            RAISE EXCEPTION 'Ese movimiento metería el nodo dentro de sí mismo'
                USING ERRCODE = 'raise_exception';
        END IF;
        NEW.path := ruta_padre OPERATOR(public.||) text2ltree(replace(NEW.id::TEXT, '-', '_'));
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER location_node_ruta
    BEFORE INSERT OR UPDATE OF parent_id ON location_node
    FOR EACH ROW EXECUTE FUNCTION location_node_ruta();

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
    UNIQUE NULLS NOT DISTINCT (organization_id, code)
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
    -- [REQ] Control de concurrencia optimista. Lo incrementa el disparador
    -- `doc_request_item_version`, nunca la aplicación: así no hay forma de que un UPDATE
    -- se salte el contador por olvido.
    row_version      INTEGER NOT NULL DEFAULT 1,
    updated_by       UUID REFERENCES app_user(id),
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
    UNIQUE NULLS NOT DISTINCT (organization_id, code),
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
    -- [REQ] Control de concurrencia optimista. Lo incrementa el disparador
    -- `finding_version`, nunca la aplicación: así no hay forma de que un UPDATE
    -- se salte el contador por olvido.
    row_version      INTEGER NOT NULL DEFAULT 1,
    updated_by       UUID REFERENCES app_user(id),
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
    -- [REQ] Control de concurrencia optimista. Lo incrementa el disparador
    -- `capex_item_version`, nunca la aplicación: así no hay forma de que un UPDATE
    -- se salte el contador por olvido.
    row_version      INTEGER NOT NULL DEFAULT 1,
    updated_by       UUID REFERENCES app_user(id),

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

-- ── Inventario de equipo [REQ] §7 / P-15 ────────────────────────────────────
--
-- Ficha OPCIONAL (decisión P-15): quien la quiera, la usa; quien no, no la ve.
-- Ningún hallazgo, línea de CAPEX ni informe la exige. Está aquí porque en una
-- visita a un edificio con instalaciones se apunta el fabricante, el modelo y
-- el año de la enfriadora en una libreta, y esa libreta acaba siendo la única
-- fuente para justificar por qué se propone sustituirla.

CREATE TYPE equipment_condition AS ENUM (
    'BUENO', 'ACEPTABLE', 'DEFICIENTE', 'MUY_DEFICIENTE', 'FUERA_DE_SERVICIO'
);
-- Obsolescencia y estado NO son lo mismo, y confundirlos es un error caro: una
-- caldera de 1998 en perfecto estado de conservación sigue siendo obsoleta
-- —no hay repuestos y no cumple el reglamento vigente— y hay que sustituirla.
CREATE TYPE equipment_obsolescence AS ENUM (
    'ACTUAL', 'PROXIMO_A_OBSOLETO', 'OBSOLETO', 'SIN_REPUESTOS'
);
CREATE TYPE equipment_criticality AS ENUM ('ALTA', 'MEDIA', 'BAJA');

CREATE TABLE equipment (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organization(id),
    project_id          UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    asset_id            UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    technical_system_id UUID REFERENCES technical_system(id),
    zone_id             UUID REFERENCES zone(id),

    -- Etiqueta de campo: «CL-01», «AS-Norte». Es como el equipo aparece
    -- rotulado en la sala, y por eso es única dentro del activo.
    tag                 VARCHAR(40),
    equipment_type      VARCHAR(120) NOT NULL CHECK (length(trim(equipment_type)) > 0),
    manufacturer        VARCHAR(120),
    model               VARCHAR(120),
    serial_number       VARCHAR(120),

    install_year        SMALLINT CHECK (install_year IS NULL OR install_year BETWEEN 1800 AND 2200),
    expected_life_years SMALLINT CHECK (expected_life_years IS NULL OR expected_life_years > 0),

    -- [LIM] La especificación pide `remaining_life_years` como columna
    -- GENERATED. No es implementable: PostgreSQL exige que la expresión de una
    -- columna generada sea IMMUTABLE, y la vida residual depende del año en
    -- curso, que cambia. Una columna así valdría el día que se escribe y
    -- mentiría a partir del 1 de enero siguiente.
    --
    -- Lo que SÍ es inmutable es el año en que el equipo agota su vida útil, y
    -- de ahí sale la vida residual restando el año actual en la lectura. El
    -- dato guardado no caduca y el calculado siempre está al día. P-15 se
    -- respeta igual: la vida residual se calcula, no se teclea.
    end_of_life_year    SMALLINT GENERATED ALWAYS AS (install_year + expected_life_years) STORED,

    condition           equipment_condition,
    obsolescence        equipment_obsolescence,
    criticality         equipment_criticality,

    quantity            NUMERIC(12, 2) NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit                VARCHAR(20) NOT NULL DEFAULT 'ud',
    has_documentation   BOOLEAN NOT NULL DEFAULT FALSE,
    notes               TEXT,

    -- Búsqueda por texto sobre lo que de verdad se busca: «la enfriadora
    -- Carrier», «el ascensor con el número de serie que empieza por 4J». La
    -- forma de dos argumentos de `to_tsvector` es IMMUTABLE, así que aquí sí
    -- se puede generar la columna.
    search_vector       TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('spanish'::regconfig,
            coalesce(tag, '') || ' ' || equipment_type || ' ' ||
            coalesce(manufacturer, '') || ' ' || coalesce(model, '') || ' ' ||
            coalesce(serial_number, '') || ' ' || coalesce(notes, ''))
    ) STORED,

    created_by          UUID NOT NULL REFERENCES app_user(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- [REQ] Control de concurrencia optimista. Lo incrementa el disparador
    -- `equipment_version`, nunca la aplicación: así no hay forma de que un UPDATE
    -- se salte el contador por olvido.
    row_version      INTEGER NOT NULL DEFAULT 1,
    updated_by       UUID REFERENCES app_user(id),
    deleted_at          TIMESTAMPTZ,

    -- El año de instalación y la vida esperada van juntos o no van: con solo
    -- uno de los dos no hay vida residual que calcular, y guardar la mitad del
    -- dato produce fichas que parecen completas y no lo están.
    CONSTRAINT vida_util_completa_o_ausente CHECK (
        (install_year IS NULL AND expected_life_years IS NULL)
        OR (install_year IS NOT NULL AND expected_life_years IS NOT NULL)
    )
);
CREATE INDEX equipment_activo_idx ON equipment (project_id, asset_id);
CREATE INDEX equipment_sistema_idx ON equipment (asset_id, technical_system_id);
CREATE INDEX equipment_busqueda_idx ON equipment USING GIN (search_vector);
-- La etiqueta identifica al equipo DENTRO del activo: dos edificios pueden
-- tener los dos su «CL-01». Se ignora lo borrado para que reutilizar una
-- etiqueta liberada no choque con una ficha que ya no existe.
CREATE UNIQUE INDEX equipment_etiqueta_uniq
    ON equipment (asset_id, tag) WHERE tag IS NOT NULL AND deleted_at IS NULL;

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
    -- [REQ] §10 · La ubicación física concreta. Es lo que rellena el token
    -- `[Espacio]` del renombrado en lote, que hasta ahora se omitía siempre
    -- porque este árbol no existía.
    location_node_id  UUID REFERENCES location_node(id) ON DELETE SET NULL,
    capex_code_id     UUID REFERENCES capex_code(id),
    -- [REQ] §3.2 · La clasificación transversal por sistema técnico. Es lo que
    -- alimenta el token `[Sistema]` del renombrado en lote, que hasta ahora
    -- escribía siempre «SinSistema» porque este dato no se guardaba en ningún
    -- sitio: la plantilla por defecto lo pide y no había de dónde sacarlo.
    --
    -- Es distinto de `photo_category`, que es texto libre (§15.4 lo separa a
    -- propósito): uno clasifica contra el catálogo de 14 y el otro es una
    -- etiqueta suelta del equipo.
    technical_system_id UUID REFERENCES technical_system(id),

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
-- Filtrar «las fotos de climatización de este encargo» es lo primero que se
-- hace al montar el informe, y en una visita de 400 fotos sin índice se nota.
CREATE INDEX photo_sistema_idx  ON photo (project_id, technical_system_id);

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
    'CERTIFICADO', 'GARANTIA', 'PLANO', 'QA', 'INFORME_PREVIO', 'FICHA_TECNICA', 'OTRO',
    -- [REQ] La MEMORIA TÉCNICA es un tipo propio y no una `FICHA_TECNICA` más:
    -- es el único documento del que la aplicación **extrae datos** hacia la
    -- ficha del activo y hacia la estructura del CAPEX. Distinguirlo por tipo
    -- es lo que permite ofrecer la extracción solo donde tiene sentido.
    'MEMORIA_TECNICA'
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
--  Revisión de documentación asistida por IA [REQ]
--
--  Lo que la IA produce son PROPUESTAS, nunca decisiones. La separación es
--  deliberada y está sostenida por el esquema, no por el código:
--
--   1. `doc_request_item.status` NO se toca desde aquí. Un documento puede
--      estar RECIBIDA y ser no conforme a la vez: son dos ejes distintos, y
--      colapsarlos habría obligado a inventar un estado «RECIBIDA pero mal»
--      que la checklist del cliente no tiene.
--   2. Una observación no sale de PROPUESTA sin que conste QUIÉN la aceptó o
--      rechazó (`doc_finding_decidida_con_persona`). Es la traducción a SQL de
--      «la IA sugiere, una persona confirma»: si mañana alguien escribe un
--      proceso que acepta propuestas en lote sin usuario, la base lo rechaza.
--   3. Cada revisión congela el `sha256` del documento analizado. Si el
--      documento se sustituye por una versión nueva, la revisión sigue
--      diciendo con exactitud sobre qué bytes se pronunció, en vez de
--      aparentar que opinó sobre el fichero de hoy.
--
--  `[LIM]` Qué se revisa vive en `doc_check_type`, no en el código. Los
--  criterios exactos están pendientes de definir con el cliente `[PDV]`, así
--  que añadir o quitar uno tiene que ser una fila, no una migración.
-- =============================================================================

CREATE TABLE doc_check_type (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    code            VARCHAR(40) NOT NULL,
    name_es         VARCHAR(120) NOT NULL,
    -- Lo que se le pide comprobar, en castellano llano. No es documentación:
    -- es el texto que alimenta la instrucción enviada al proveedor, y por eso
    -- vive en la base y no en una constante de Python.
    description_es  TEXT NOT NULL,
    display_order   SMALLINT NOT NULL DEFAULT 0,
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE NULLS NOT DISTINCT (organization_id, code)
);

CREATE TYPE doc_review_status AS ENUM (
    'PENDIENTE', 'EN_CURSO', 'COMPLETADA', 'FALLIDA', 'CANCELADA'
);

CREATE TABLE doc_review (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organization(id),
    project_id          UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    document_id         UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    doc_request_item_id UUID REFERENCES doc_request_item(id) ON DELETE SET NULL,
    status              doc_review_status NOT NULL DEFAULT 'PENDIENTE',

    -- Qué produjo la propuesta. Sin esto no se puede auditar ni reproducir, y
    -- `is_simulated` impide que una revisión de mentira pase por una de verdad:
    -- mientras no haya proveedor elegido, TODAS son simuladas y se ven así.
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
);
CREATE INDEX doc_review_documento_idx ON doc_review (document_id, requested_at DESC);
CREATE INDEX doc_review_proyecto_idx ON doc_review (project_id, status);

CREATE TYPE doc_finding_verdict  AS ENUM ('CONFORME', 'NO_CONFORME', 'FALTA', 'DUDOSO');
CREATE TYPE doc_finding_decision AS ENUM ('PROPUESTA', 'ACEPTADA', 'RECHAZADA');

CREATE TABLE doc_review_finding (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    doc_review_id   UUID NOT NULL REFERENCES doc_review(id) ON DELETE CASCADE,
    check_type_id   UUID NOT NULL REFERENCES doc_check_type(id),
    verdict         doc_finding_verdict NOT NULL,
    summary         TEXT NOT NULL,

    -- [REQ] La evidencia es lo que hace verificable la propuesta. Quien la
    -- confirma tiene que poder ir a la página y leerlo, en vez de creerse un
    -- veredicto sin respaldo. `evidence_page` es 1-indexado como el visor.
    evidence_text   TEXT,
    evidence_page   INT,
    confidence      NUMERIC(4, 3),

    decision        doc_finding_decision NOT NULL DEFAULT 'PROPUESTA',
    decided_by      UUID REFERENCES app_user(id),
    decided_at      TIMESTAMPTZ,
    decision_note   TEXT,

    -- El corazón del requisito: sin persona, la observación se queda en
    -- propuesta. No hay forma de aceptarla «desde el sistema».
    CONSTRAINT doc_finding_decidida_con_persona
        CHECK (decision = 'PROPUESTA'
               OR (decided_by IS NOT NULL AND decided_at IS NOT NULL)),
    CONSTRAINT doc_finding_confianza_valida
        CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    CONSTRAINT doc_finding_pagina_valida
        CHECK (evidence_page IS NULL OR evidence_page >= 1)
);
CREATE INDEX doc_finding_revision_idx ON doc_review_finding (doc_review_id, decision);

-- =============================================================================
--  La memoria técnica del activo [REQ]
--
--  Es el documento que entrega la propiedad con todos los datos del edificio y
--  el listado de categorías del CAPEX con sus objetos. Sirve para dos cosas, y
--  las dos son las que justifican que tenga tablas propias:
--
--   1. **Completa la ficha del activo** sin volver a teclearla.
--   2. **Genera el esqueleto del CAPEX**: una fila por categoría presente y una
--      subfila por objeto, que el gestor técnico va completando.
--
--  Lo que se guarda aquí es lo que dice LA MEMORIA, no lo que acabe siendo el
--  CAPEX. Son cosas distintas y separarlas importa: el gestor añade objetos que
--  la memoria no contemplaba, y descarta otros que sí venían. Fundirlas dejaría
--  sin respuesta la pregunta que se hace en la defensa del informe: «¿esto
--  estaba en la memoria del edificio o lo viste tú en la visita?».
--
--  [REQ] Nada de esto se da por bueno solo. `validada_at` / `validada_por` son
--  el testigo de que una persona miró lo que la extracción propuso. La regla
--  del cliente es explícita: se extrae, se previsualiza y se acepta con un
--  botón. Un clic, no un tecleo — pero un clic de alguien.
-- =============================================================================

CREATE TYPE memoria_status AS ENUM ('SIN_DOCUMENTO', 'EXTRAIDA', 'VALIDADA');

CREATE TABLE memoria_tecnica (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    -- Una por activo. Un edificio tiene una memoria técnica; si llegan dos
    -- versiones, se sustituye el documento y se vuelve a extraer.
    asset_id        UUID NOT NULL UNIQUE REFERENCES asset(id) ON DELETE CASCADE,
    -- El documento del que salió. NULL cuando la memoria se está rellenando a
    -- mano porque la propiedad no la ha entregado: el caso existe y no puede
    -- bloquear el trabajo.
    document_id     UUID REFERENCES document(id) ON DELETE SET NULL,
    status          memoria_status NOT NULL DEFAULT 'SIN_DOCUMENTO',

    -- Quién produjo la extracción y si fue de mentira. Igual que en la revisión
    -- documental: una extracción simulada no puede pasar por una de verdad ni
    -- en la base ni en la pantalla.
    origen          VARCHAR(60),
    es_simulada     BOOLEAN NOT NULL DEFAULT TRUE,
    extraida_at     TIMESTAMPTZ,

    -- [REQ] LA PROPUESTA, sin aplicar. Es la mitad que hace que el botón de
    -- validación signifique algo: los datos extraídos del documento se quedan
    -- AQUÍ y no en `asset` hasta que una persona los acepta. Escribirlos
    -- directamente en el activo y marcarlos «sin validar» habría dejado un dato
    -- sin revisar circulando por el CAPEX y por el informe, que es justo lo que
    -- el botón existe para impedir.
    --
    -- JSONB y no columnas porque esto es un borrador, no un registro: su forma
    -- es la de `asset` y cambiará con ella, y una propuesta a la que le falta
    -- la mitad de los campos es normal —la memoria no siempre los trae todos—.
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
    -- No se puede estar VALIDADA sin que conste quién la validó. El estado y el
    -- testigo son la misma afirmación dicha dos veces, y tienen que coincidir.
    CONSTRAINT memoria_estado_coherente
        CHECK (status <> 'VALIDADA' OR validada_at IS NOT NULL),
    CONSTRAINT memoria_extraida_tiene_fecha
        CHECK (status = 'SIN_DOCUMENTO' OR extraida_at IS NOT NULL)
);

-- Las categorías del CAPEX que la memoria declara presentes en el edificio.
-- Son los 15 capítulos de Hard Costs —`HC.H01` a `HC.H15`— aunque nada impide
-- que la memoria declare también las de otro tipo de coste.
CREATE TABLE memoria_categoria (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    memoria_id      UUID NOT NULL REFERENCES memoria_tecnica(id) ON DELETE CASCADE,
    -- Un capítulo del catálogo: nivel 2. Que sea de nivel 2 lo comprueba la API
    -- y lo cubre una prueba; un CHECK aquí exigiría un disparador que consulte
    -- otra tabla, y eso encarece cada escritura para una regla que no cambia.
    capex_code_id   UUID NOT NULL REFERENCES capex_code(id),
    notes           TEXT,
    orden           SMALLINT NOT NULL DEFAULT 0,
    UNIQUE (memoria_id, capex_code_id)
);

CREATE INDEX memoria_categoria_memoria_idx ON memoria_categoria (memoria_id, orden);

-- Los objetos que la memoria enumera dentro de cada categoría.
CREATE TABLE memoria_objeto (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id      UUID NOT NULL REFERENCES organization(id),
    memoria_categoria_id UUID NOT NULL REFERENCES memoria_categoria(id) ON DELETE CASCADE,
    -- El elemento del catálogo (nivel 3) al que corresponde, SI corresponde a
    -- alguno. Nulo a propósito: una memoria nombra cosas que el catálogo no
    -- tiene, y perderlas por no encajar sería tirar justo la información que el
    -- gestor necesita para no olvidarse de revisarlas.
    capex_code_id        UUID REFERENCES capex_code(id),
    -- Lo que dice la memoria, con sus palabras. Se conserva aunque haya código:
    -- «Enfriadora Marca X de 450 kW» es más útil que «Producción de
    -- climatización» cuando alguien vuelve al informe seis meses después.
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

-- ── Secciones de memoria técnica → capítulos CAPEX [REQ] §5.9 ──────────────
--
-- Una memoria técnica NO trae la lista de las 15 categorías del CAPEX. Se
-- comprobó leyendo una de verdad: trae una memoria constructiva del Código
-- Técnico, con sus propias secciones y los elementos en prosa dentro de cada
-- una. Las categorías se DEDUCEN de esas secciones.
--
-- La correspondencia no es uno a uno en ninguna dirección: `MC.2 Cimentación`
-- y `MC.3 Sistema estructural` caen las dos en `H01`, y `MC.6 Instalaciones`
-- reparte sus elementos entre seis capítulos. Por eso es una tabla y no un
-- diccionario en el código: la segunda memoria traerá otra numeración, y
-- corregirlo tiene que ser editar una fila, no desplegar.
--
-- `capex_code_id` nulo significa «esta sección no mapea a ningún capítulo, y
-- está decidido». `MC.0 Trabajos previos` es coste de obra, no del activo que
-- se compra. Sin la fila, no se distinguiría de una sección olvidada.

CREATE TABLE memoria_seccion (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organization(id),
    seccion_code    VARCHAR(10) NOT NULL,
    name_es         VARCHAR(160) NOT NULL,
    capex_code_id   UUID REFERENCES capex_code(id),
    is_system       BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE NULLS NOT DISTINCT (organization_id, seccion_code, capex_code_id)
);

CREATE INDEX memoria_seccion_codigo_idx ON memoria_seccion (seccion_code);

-- ── Lo que la documentación PROPONE sobre el activo [REQ] ───────────────────
--
-- «Según se va subiendo documentación, el cuadro se va completando solo, y el
-- gestor de la due diligence valida después». Eso obliga a que una propuesta
-- no sea un valor suelto sino un valor CON SU PROCEDENCIA, y a que dos
-- documentos puedan proponer cosas distintas para el mismo campo sin que el
-- segundo borre al primero.
--
-- Antes esto vivía en `memoria_tecnica.propuesta`, un JSONB plano. Con un solo
-- documento bastaba; con dos, el segundo pisaba al primero y nadie podía saber
-- de cuál salió cada cifra. Un número huérfano en una ficha de activo no se
-- puede defender ante el cliente, así que el gestor tendría que volver a
-- comprobarlo todo: justo el trabajo que la extracción venía a ahorrar.
--
-- `evidencia` es el fragmento LITERAL del documento. Que sea literal es la
-- diferencia entre poder comprobar si la máquina se equivocó y tener que
-- creerle: un resumen de lo que la máquina creyó leer no sirve para eso.

CREATE TYPE propuesta_estado AS ENUM ('PENDIENTE', 'ACEPTADA', 'DESCARTADA');

CREATE TABLE propuesta_de_dato (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organization(id),
    asset_id        UUID NOT NULL REFERENCES asset(id) ON DELETE CASCADE,

    campo           VARCHAR(60) NOT NULL,
    -- Como texto. El tipo lo pone el destino al aceptarla: aquí no se sabe si
    -- «8134» acabará en un NUMERIC o en un VARCHAR, y convertirlo antes
    -- obligaría al extractor a conocer el esquema del activo.
    valor           TEXT NOT NULL,

    -- La procedencia. `document_id` se pone a NULL si el documento se borra,
    -- pero el resto sobrevive: una propuesta ya aceptada tiene que poder
    -- explicarse aunque el fichero original ya no esté.
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

    -- Un documento propone un valor por campo. Volver a extraer el mismo
    -- documento sustituye su propuesta; no acumula duplicados.
    -- NULLS NOT DISTINCT para que dos propuestas manuales del mismo campo
    -- —ambas sin documento— choquen en vez de multiplicarse.
    UNIQUE NULLS NOT DISTINCT (asset_id, campo, document_id),

    CONSTRAINT propuesta_decidida_completa
        CHECK ((decidida_at IS NULL) = (decidida_por IS NULL)),
    -- Una propuesta resuelta lleva quién la resolvió. Sin esto, «aceptada por
    -- nadie» sería un estado posible, y el testigo de la revisión humana
    -- dejaría de significar nada.
    CONSTRAINT propuesta_resuelta_tiene_testigo
        CHECK (estado = 'PENDIENTE' OR decidida_at IS NOT NULL)
);

CREATE INDEX propuesta_activo_idx ON propuesta_de_dato (asset_id, estado);
CREATE INDEX propuesta_documento_idx ON propuesta_de_dato (document_id);

-- =============================================================================
--  Bloque 4 · Informes PPTX [REQ] §17
--
--  La garantía que estructura todo el bloque: **un informe emitido debe seguir
--  siendo reproducible años después**. Eso exige dos cosas que no son
--  evidentes:
--
--   1. La generación lee de un SNAPSHOT, no de la base de datos viva. Un
--      cambio concurrente no puede producir un informe incoherente, y dentro
--      de dos años el informe se puede reconstruir aunque el proyecto haya
--      seguido cambiando.
--   2. El snapshot incluye LOS CATÁLOGOS USADOS. Sin ello, retirar un código
--      CAPEX dos años después dejaría huecos en un informe ya entregado. Es la
--      diferencia entre archivar un PDF y poder reconstruir el informe.
-- =============================================================================

CREATE TABLE report_template (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    name             VARCHAR(160) NOT NULL,
    language         CHAR(2) NOT NULL DEFAULT 'es',
    -- La plantilla es material confidencial del cliente y vive en el almacén
    -- como cualquier otro original: inmutable y con su hash.
    stored_object_id UUID NOT NULL REFERENCES stored_object(id),
    sha256           CHAR(64) NOT NULL,
    slide_count      SMALLINT,
    -- Resultado del análisis: marcadores encontrados, fuentes del tema, avisos.
    analysis         JSONB,
    analyzed_at      TIMESTAMPTZ,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_by       UUID NOT NULL REFERENCES app_user(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (organization_id, name, language)
);

-- El mapeo: qué dato del proyecto alimenta cada marcador de la plantilla.
CREATE TABLE template_mapping (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organization(id),
    template_id      UUID NOT NULL REFERENCES report_template(id) ON DELETE CASCADE,
    name             VARCHAR(160) NOT NULL,
    -- {marcador: expresión}. Se valida antes de guardar: un marcador que
    -- apunta a un campo inexistente es un aviso BLOQUEANTE en la generación,
    -- y descubrirlo al generar es tarde.
    bindings         JSONB NOT NULL DEFAULT '{}'::jsonb,
    photo_rules      JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_default       BOOLEAN NOT NULL DEFAULT FALSE,
    version          SMALLINT NOT NULL DEFAULT 1,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (template_id, name)
);

CREATE TYPE report_status AS ENUM (
    'GENERANDO', 'GENERADO', 'EN_REVISION', 'APROBADO', 'EMITIDO', 'ERROR'
);

CREATE TABLE report_version (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL REFERENCES organization(id),
    project_id        UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    version_number    SMALLINT NOT NULL,
    status            report_status NOT NULL DEFAULT 'GENERANDO',

    template_id       UUID NOT NULL REFERENCES report_template(id),
    template_sha256   CHAR(64) NOT NULL,
    mapping_id        UUID REFERENCES template_mapping(id),

    -- [REQ] §9 · «Las partidas del informe deben corresponder a una versión
    -- concreta de los datos.» El snapshot ES esa versión.
    data_snapshot        JSONB NOT NULL,
    data_snapshot_sha256 CHAR(64) NOT NULL,

    stored_object_id  UUID REFERENCES stored_object(id),
    pptx_sha256       CHAR(64),
    xlsx_object_id    UUID REFERENCES stored_object(id),

    warnings          JSONB NOT NULL DEFAULT '[]'::jsonb,
    supersedes_version_id UUID REFERENCES report_version(id),

    -- [REQ] §9 · «Un informe emitido debe quedar bloqueado.»
    is_locked         BOOLEAN NOT NULL DEFAULT FALSE,
    generated_by      UUID NOT NULL REFERENCES app_user(id),
    generated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_by       UUID REFERENCES app_user(id),
    approved_at       TIMESTAMPTZ,
    issued_by         UUID REFERENCES app_user(id),
    issued_at         TIMESTAMPTZ,

    UNIQUE (project_id, version_number),
    -- Bloqueado y emitido van siempre juntos: cualquiera de los dos sin el
    -- otro sería un estado que nadie sabría interpretar.
    CONSTRAINT report_emitido_bloqueado
        CHECK ((status = 'EMITIDO') = is_locked),
    CONSTRAINT report_emitido_con_firma
        CHECK (status <> 'EMITIDO' OR (issued_by IS NOT NULL AND issued_at IS NOT NULL)),
    CONSTRAINT report_aprobado_con_firma
        CHECK (status NOT IN ('APROBADO', 'EMITIDO')
               OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)),
    -- Un informe generado sin fichero no es un informe.
    CONSTRAINT report_generado_con_fichero
        CHECK (status IN ('GENERANDO', 'ERROR')
               OR (stored_object_id IS NOT NULL AND pptx_sha256 IS NOT NULL))
);

CREATE INDEX report_version_proyecto_idx
    ON report_version (project_id, version_number DESC);

-- [REQ] Un informe EMITIDO es inmutable. No es una convención de código: si
-- alguien escribe un UPDATE nuevo dentro de seis meses, esto sigue en pie.
CREATE OR REPLACE FUNCTION impedir_cambio_de_informe_emitido() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.is_locked THEN
        RAISE EXCEPTION
            'El informe v% está emitido y es inmutable: genere una versión nueva',
            OLD.version_number
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER report_version_emitido_inmutable
    BEFORE UPDATE ON report_version
    FOR EACH ROW EXECUTE FUNCTION impedir_cambio_de_informe_emitido();

CREATE OR REPLACE FUNCTION impedir_borrado_de_informe_emitido() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.is_locked THEN
        RAISE EXCEPTION 'Un informe emitido no se borra (v%)', OLD.version_number
            USING ERRCODE = 'raise_exception';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER report_version_emitido_no_borrable
    BEFORE DELETE ON report_version
    FOR EACH ROW EXECUTE FUNCTION impedir_borrado_de_informe_emitido();

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


-- =============================================================================
--  Cola de tareas · §17 · nada bloquea la interfaz más de 3 s
--
--  La cola vive **en esta base de datos** y no en un broker aparte. Dos razones,
--  y la segunda es la que importa:
--
--   1. No añade un servicio a producción. Con la carga real de la aplicación
--      —un puñado de informes al día y los correos de recuperación— un broker
--      dedicado sería una pieza más que vigilar sin ganar nada.
--   2. **El encolado es transaccional.** La tarea solo existe si la
--      transacción que la creó confirma. Con un broker externo se puede
--      encolar la generación de un informe cuya fila acaba revirtiendo, y el
--      worker se encuentra trabajo sobre algo que no existe.
--
--  `[REC]` El reparto entre workers usa `FOR UPDATE SKIP LOCKED`: cada uno se
--  lleva una tarea distinta sin bloquear a los demás y sin necesitar ningún
--  coordinador. Es el patrón estándar para esto desde PostgreSQL 9.5.
--
--  `queue` separa `heavy` (informes) de `io` (correo), que es lo que pide E-10:
--  una cola de informes saturada no puede retrasar un correo de recuperación
--  de contraseña.
-- =============================================================================

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
    -- La petición que la encargó. Es la correlación que hace falta para operar
    -- esto: un informe se pide en una petición y se genera minutos después en
    -- otro proceso, así que sin esto «el informe de las 11:04 salió mal» no se
    -- puede atar a nada. Es texto y no UUID a propósito: puede venir del
    -- balanceador con el formato que él use.
    request_id       TEXT,
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


-- ── El reparto, en funciones acotadas ────────────────────────────────────────
--
--  El worker tiene que ver las tareas de TODAS las organizaciones: ese es su
--  trabajo. Pero darle BYPASSRLS al usuario de aplicación dejaría decorativas
--  todas las políticas de arriba.
--
--  Se resuelve igual que la recuperación de contraseña, que tenía el mismo
--  problema: **funciones `SECURITY DEFINER` que hacen exactamente una cosa.**
--  El usuario de aplicación sigue sin poder leer la tabla `job` de otra
--  organización; lo único que puede hacer es pedir «dame la siguiente tarea de
--  esta cola», que es la operación del worker y de nadie más.
--
--  `[REC]` En producción conviene además que el worker conecte con su propio
--  rol. No es imprescindible —la superficie ya está acotada aquí— pero separa
--  en los registros quién hizo qué.

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


-- =============================================================================
--  Recuperación de contraseña · SECURITY DEFINER
--
--  Los dos endpoints son ANÓNIMOS: quien ha olvidado su contraseña no tiene
--  sesión, así que no hay `app.current_org_id` y la RLS lo ocultaría todo. Es
--  el mismo problema que el inicio de sesión, y se resuelve igual: funciones
--  acotadas que hacen exactamente una cosa, en vez de dar BYPASSRLS al usuario
--  de aplicación.
--
--  Ninguna de las dos acepta un correo ni devuelve nada que permita averiguar
--  si una cuenta existe: se busca por HUELLA del token, que solo tiene quien
--  recibió el correo.
-- =============================================================================

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

-- =============================================================================
--  Concurrencia optimista · que dos personas no se pisen en silencio
--
--  El problema que resuelve, con nombres: Marta abre un hallazgo, Luis abre el
--  mismo hallazgo, Marta corrige la descripción y guarda, Luis guarda su
--  cambio de riesgo treinta segundos después. Sin esto **la corrección de
--  Marta desaparece y nadie se entera**: es recuperable desde `audit_log`,
--  pero solo si alguien sospecha que pasó.
--
--  Dos decisiones que hacen que no dependa de la disciplina de nadie:
--
--   1. **El contador lo lleva el disparador, no la aplicación.** Un `UPDATE`
--      que se olvide de incrementar `row_version` no existe: la base lo hace
--      en todos, incluidos los que se escriban mañana.
--   2. **`updated_by` se rellena solo** desde `usuario_actual()`, la misma
--      función que ya sostiene la RLS. Sin eso el mensaje de conflicto podría
--      decir «alguien lo cambió», que no ayuda a resolverlo; con eso dice
--      quién, y quien lo lee sabe con quién hablar.
--
--  `NEW.row_version` se pisa **siempre**, se mande lo que se mande en el
--  `UPDATE`: el número no es un dato editable, es el estado de la fila.
-- =============================================================================

CREATE OR REPLACE FUNCTION marcar_version_y_autor() RETURNS TRIGGER AS $$
BEGIN
    NEW.row_version := OLD.row_version + 1;
    -- `COALESCE` porque las migraciones y la siembra escriben sin sesión de
    -- usuario: ahí se conserva el autor anterior en vez de borrarlo.
    NEW.updated_by := COALESCE(usuario_actual(), OLD.updated_by);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'finding', 'capex_item', 'asset', 'project', 'doc_request_item', 'equipment',
        'memoria_tecnica'
    ] LOOP
        EXECUTE format($f$
            CREATE TRIGGER %1$I_version
                BEFORE UPDATE ON %1$I
                FOR EACH ROW EXECUTE FUNCTION marcar_version_y_autor()
        $f$, t);
    END LOOP;
END $$;

-- Aislamiento por organización: la misma política en todas las tablas con
-- organization_id. Se aplica también a INSERT/UPDATE (WITH CHECK), no solo a
-- SELECT: sin eso, un usuario podría escribir filas en otra organización.
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'app_user', 'client', 'project', 'asset', 'asset_zone', 'asset_floor',
        'cost_profile',
        'price_source', 'price_reference', 'finding', 'capex_item', 'equipment',
        'stored_object', 'audit_log', 'suggestion_comment',
        'project_phase', 'doc_request_item', 'vdr_link', 'asset_visit',
        'qa_round', 'phase_event',
        'photo', 'photo_version', 'photo_derivative', 'photo_link', 'location_node',
        'user_session', 'project_member', 'asset_assignment', 'qa_question', 'document',
        'password_reset_token', 'doc_review', 'doc_review_finding', 'job',
        'report_template', 'template_mapping', 'report_version',
        'memoria_tecnica', 'memoria_categoria', 'memoria_objeto',
        'propuesta_de_dato'
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
        'capex_concept', 'time_horizon', 'doc_request_category', 'technical_system',
        'doc_check_type', 'memoria_seccion'
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

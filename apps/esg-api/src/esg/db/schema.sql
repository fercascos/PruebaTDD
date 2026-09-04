-- ============================================================================
--  Esquema del dashboard ESG de activos inmobiliarios.
--
--  Este fichero es LA VERDAD del esquema. Se aplica entero sobre una base
--  vacía; `tests/conftest.py` lo ejecuta en cada arranque de la suite contra
--  PostgreSQL real, porque lo que aquí se declara —RLS, CHECK, EXCLUDE— no
--  existe fuera de PostgreSQL y no se puede probar contra un doble.
--
--  El porqué de cada decisión, en docs/esg/02-modelo-de-datos.md.
-- ============================================================================

-- El solape de periodos de la tabla `lectura` se impide con un EXCLUDE que
-- combina igualdad (punto_id) y solape de rangos (&&). GiST no sabe de
-- igualdad por sí solo: eso lo aporta btree_gist.
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ─────────────────────────────────────────────────────────────────────────────
--  Enumerados: conjuntos cerrados. Lo ampliable (factores) va en tablas.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE rol_usuario AS ENUM ('ADMIN', 'GESTOR', 'ANALISTA', 'LECTOR', 'CLIENTE');
CREATE TYPE vector_esg AS ENUM ('AGUA', 'ELECTRICIDAD', 'GAS', 'RESIDUOS');
CREATE TYPE ambito_suministro AS ENUM ('COMUN', 'PRIVATIVO', 'TOTAL');
CREATE TYPE calidad_lectura AS ENUM ('MEDIDO', 'ESTIMADO');
CREATE TYPE origen_lectura AS ENUM ('FICHERO', 'FACTURA_IA', 'API', 'MANUAL');
CREATE TYPE estado_lectura AS ENUM ('CONFIRMADA', 'PENDIENTE_REVISION', 'DESCARTADA');
CREATE TYPE tipologia_activo AS ENUM (
    'OFICINAS', 'COMERCIAL', 'LOGISTICO', 'RESIDENCIAL', 'HOTELERO', 'INDUSTRIAL', 'OTROS'
);
CREATE TYPE fraccion_residuo AS ENUM (
    'RESTO', 'PAPEL', 'ENVASES', 'ORGANICO', 'VIDRIO', 'PELIGROSO', 'OTROS'
);
CREATE TYPE superficie_referencia AS ENUM ('BRUTA', 'ALQUILABLE', 'OCUPADA');
CREATE TYPE tipo_carga AS ENUM ('FICHERO', 'CONECTOR');
CREATE TYPE estado_carga AS ENUM ('SIMULADA', 'APLICADA', 'FALLIDA');

-- ─────────────────────────────────────────────────────────────────────────────
--  Organización e identidad
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE organizacion (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre          TEXT NOT NULL,
    slug            TEXT NOT NULL UNIQUE,
    pais            CHAR(2) NOT NULL DEFAULT 'ES',
    moneda          CHAR(3) NOT NULL DEFAULT 'EUR',
    zona_horaria    TEXT NOT NULL DEFAULT 'Europe/Madrid',
    creada_en       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE usuario (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id   UUID NOT NULL REFERENCES organizacion(id),
    email             TEXT NOT NULL,
    nombre            TEXT NOT NULL,
    rol               rol_usuario NOT NULL DEFAULT 'LECTOR',
    -- Identidad de Entra ID. `sub_oidc` llega VACÍO al dar de alta a alguien y
    -- se fija en su primer inicio de sesión: así se puede invitar a una persona
    -- antes de que exista para nosotros. El emparejamiento inicial es por
    -- correo; a partir de ahí manda el par (emisor, sub), que no cambia aunque
    -- la persona se case y le cambien el buzón.
    emisor_oidc       TEXT,
    sub_oidc          TEXT,
    activo            BOOLEAN NOT NULL DEFAULT TRUE,
    ultimo_acceso_en  TIMESTAMPTZ,
    creado_en         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX usuario_email_unico ON usuario (organizacion_id, lower(email));
-- Único GLOBAL y no por organización: el mismo sujeto de Entra ID no puede
-- estar en dos organizaciones de esta instalación. Si algún día hace falta,
-- será una decisión explícita, no un descuido de índice.
CREATE UNIQUE INDEX usuario_oidc_unico ON usuario (emisor_oidc, sub_oidc)
    WHERE sub_oidc IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
--  Estructura: cliente → cartera → activo
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE cliente (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id UUID NOT NULL REFERENCES organizacion(id),
    nombre          TEXT NOT NULL,
    codigo          TEXT,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    borrado_en      TIMESTAMPTZ
);
CREATE UNIQUE INDEX cliente_codigo_unico ON cliente (organizacion_id, codigo)
    WHERE codigo IS NOT NULL AND borrado_en IS NULL;

CREATE TABLE cartera (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id          UUID NOT NULL REFERENCES organizacion(id),
    cliente_id               UUID REFERENCES cliente(id),
    nombre                   TEXT NOT NULL,
    codigo                   TEXT NOT NULL,
    superficie_de_referencia superficie_referencia NOT NULL DEFAULT 'ALQUILABLE',
    creada_en                TIMESTAMPTZ NOT NULL DEFAULT now(),
    borrado_en               TIMESTAMPTZ
);
CREATE UNIQUE INDEX cartera_codigo_unico ON cartera (organizacion_id, lower(codigo))
    WHERE borrado_en IS NULL;

CREATE TABLE activo (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id          UUID NOT NULL REFERENCES organizacion(id),
    cartera_id               UUID NOT NULL REFERENCES cartera(id),
    codigo                   TEXT NOT NULL,
    nombre                   TEXT NOT NULL,
    direccion                TEXT,
    municipio                TEXT,
    pais                     CHAR(2) NOT NULL DEFAULT 'ES',
    latitud                  NUMERIC(9,6),
    longitud                 NUMERIC(9,6),
    tipologia                tipologia_activo NOT NULL DEFAULT 'OTROS',
    superficie_bruta_m2      NUMERIC(12,2),
    superficie_alquilable_m2 NUMERIC(12,2),
    superficie_ocupada_m2    NUMERIC(12,2),
    -- NULL = se hereda la de la cartera. Es distinto de repetir aquí el valor
    -- de la cartera: cambiar el criterio de la cartera debe arrastrar a sus
    -- activos, salvo a los que lo tengan fijado a propósito.
    superficie_de_referencia superficie_referencia,
    anio_construccion        SMALLINT,
    incorporado_en           DATE,
    creado_en                TIMESTAMPTZ NOT NULL DEFAULT now(),
    borrado_en               TIMESTAMPTZ,
    CONSTRAINT superficies_positivas CHECK (
        coalesce(superficie_bruta_m2, 1) > 0
        AND coalesce(superficie_alquilable_m2, 1) > 0
        AND coalesce(superficie_ocupada_m2, 1) > 0
    )
);
CREATE UNIQUE INDEX activo_codigo_unico ON activo (organizacion_id, lower(codigo))
    WHERE borrado_en IS NULL;
CREATE INDEX activo_por_cartera ON activo (cartera_id) WHERE borrado_en IS NULL;

CREATE TABLE ocupacion (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id  UUID NOT NULL REFERENCES organizacion(id),
    activo_id        UUID NOT NULL REFERENCES activo(id),
    -- Día 1 del mes, garantizado por el CHECK: sin él, «marzo» acabaría siendo
    -- el 1, el 15 y el 31 según quién cargara el dato, y el emparejamiento con
    -- el consumo mensual fallaría en silencio.
    mes              DATE NOT NULL,
    ocupantes_medios NUMERIC(10,2) NOT NULL,
    superficie_ocupada_m2 NUMERIC(12,2),
    CONSTRAINT ocupacion_dia_primero CHECK (date_trunc('month', mes)::date = mes),
    CONSTRAINT ocupantes_no_negativos CHECK (ocupantes_medios >= 0)
);
CREATE UNIQUE INDEX ocupacion_unica ON ocupacion (activo_id, mes);

-- ─────────────────────────────────────────────────────────────────────────────
--  Suministros y lecturas
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE punto_de_suministro (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id     UUID NOT NULL REFERENCES organizacion(id),
    activo_id           UUID NOT NULL REFERENCES activo(id),
    vector              vector_esg NOT NULL,
    codigo              TEXT NOT NULL,
    descripcion         TEXT,
    ambito              ambito_suministro NOT NULL DEFAULT 'TOTAL',
    comercializadora    TEXT,
    unidad_de_factura   TEXT NOT NULL,
    fraccion            fraccion_residuo,
    alta_en             DATE,
    baja_en             DATE,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT now(),
    borrado_en          TIMESTAMPTZ,
    -- La fracción es de residuos y solo de residuos. Un contador de agua con
    -- fracción PAPEL es un dato que alguien cargó mal, y saldría sumado.
    CONSTRAINT fraccion_solo_en_residuos CHECK (
        (vector = 'RESIDUOS') OR (fraccion IS NULL)
    )
);
-- El mismo CUPS/contador dos veces es la causa número uno de duplicar un
-- consumo entero sin que nada avise.
CREATE UNIQUE INDEX suministro_codigo_unico
    ON punto_de_suministro (organizacion_id, vector, lower(codigo))
    WHERE borrado_en IS NULL;
CREATE INDEX suministro_por_activo ON punto_de_suministro (activo_id) WHERE borrado_en IS NULL;

CREATE TABLE carga (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id  UUID NOT NULL REFERENCES organizacion(id),
    tipo             tipo_carga NOT NULL,
    nombre           TEXT NOT NULL,
    hash_sha256      TEXT,
    hoja             TEXT,
    mapeo            JSONB,
    usuario_id       UUID REFERENCES usuario(id),
    estado           estado_carga NOT NULL DEFAULT 'SIMULADA',
    filas_totales    INTEGER NOT NULL DEFAULT 0,
    filas_aceptadas  INTEGER NOT NULL DEFAULT 0,
    filas_rechazadas INTEGER NOT NULL DEFAULT 0,
    creada_en        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX carga_por_hash ON carga (organizacion_id, hash_sha256)
    WHERE hash_sha256 IS NOT NULL;

CREATE TABLE incidencia_de_carga (
    id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    carga_id  UUID NOT NULL REFERENCES carga(id) ON DELETE CASCADE,
    organizacion_id UUID NOT NULL REFERENCES organizacion(id),
    fila      INTEGER,
    columna   TEXT,
    codigo    TEXT NOT NULL,
    mensaje   TEXT NOT NULL,
    valor     TEXT
);
CREATE INDEX incidencia_por_carga ON incidencia_de_carga (carga_id);

CREATE TABLE lectura (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id      UUID NOT NULL REFERENCES organizacion(id),
    punto_id             UUID NOT NULL REFERENCES punto_de_suministro(id),
    inicio               DATE NOT NULL,
    fin                  DATE NOT NULL,
    cantidad             NUMERIC(18,4) NOT NULL,
    unidad               TEXT NOT NULL,
    -- NULL a propósito cuando no hubo factor aplicable (gas en m³ sin PCS del
    -- periodo). Un 0 habría sumado bien y mentido; un NULL no suma y sale en
    -- la cobertura como lo que es: un dato que aún no se puede agregar.
    cantidad_normalizada NUMERIC(18,4),
    unidad_normalizada   TEXT,
    factor_de_conversion NUMERIC(18,8),
    calidad              calidad_lectura NOT NULL DEFAULT 'MEDIDO',
    origen               origen_lectura NOT NULL,
    estado               estado_lectura NOT NULL DEFAULT 'CONFIRMADA',
    confianza            NUMERIC(4,3),
    importe              NUMERIC(18,4),
    moneda               CHAR(3),
    carga_id             UUID REFERENCES carga(id),
    fila_origen          INTEGER,
    referencia_externa   TEXT,
    nota                 TEXT,
    creado_en            TIMESTAMPTZ NOT NULL DEFAULT now(),
    creado_por           UUID REFERENCES usuario(id),
    CONSTRAINT periodo_valido CHECK (fin > inicio),
    CONSTRAINT cantidad_no_negativa CHECK (cantidad >= 0),
    CONSTRAINT confianza_en_rango CHECK (confianza IS NULL OR (confianza >= 0 AND confianza <= 1)),
    -- Dos lecturas del mismo suministro no pueden solaparse. Cargar dos veces
    -- el mismo Excel, o la factura y además el resumen anual, duplica el
    -- consumo sin que nada avise: aquí avisa la base de datos. Lo descartado
    -- queda fuera para poder corregir sin borrar el histórico.
    CONSTRAINT sin_solape_por_suministro EXCLUDE USING gist (
        punto_id WITH =,
        daterange(inicio, fin, '[)') WITH &&
    ) WHERE (estado <> 'DESCARTADA')
);
CREATE INDEX lectura_por_punto_y_periodo ON lectura (punto_id, inicio, fin)
    WHERE estado = 'CONFIRMADA';
-- La misma factura no se importa dos veces desde el conector.
CREATE UNIQUE INDEX lectura_referencia_externa_unica
    ON lectura (organizacion_id, referencia_externa)
    WHERE referencia_externa IS NOT NULL AND estado <> 'DESCARTADA';

CREATE TABLE factor_de_conversion (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- NULL = factor global de la instalación (kWh↔MWh, kg↔t…). Con valor, es
    -- un factor de esa organización: el PCS del gas de su comercializadora.
    organizacion_id  UUID REFERENCES organizacion(id),
    vector           vector_esg,
    unidad_origen    TEXT NOT NULL,
    unidad_destino   TEXT NOT NULL,
    factor           NUMERIC(18,8) NOT NULL,
    comercializadora TEXT,
    vigente_desde    DATE NOT NULL DEFAULT DATE '1900-01-01',
    vigente_hasta    DATE,
    fuente           TEXT NOT NULL,
    CONSTRAINT factor_positivo CHECK (factor > 0),
    CONSTRAINT vigencia_valida CHECK (vigente_hasta IS NULL OR vigente_hasta > vigente_desde)
);
CREATE INDEX factor_busqueda
    ON factor_de_conversion (unidad_origen, unidad_destino, vigente_desde);

CREATE TABLE ambito_de_visibilidad (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizacion_id UUID NOT NULL REFERENCES organizacion(id),
    usuario_id      UUID NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    cartera_id      UUID REFERENCES cartera(id),
    activo_id       UUID REFERENCES activo(id),
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Una cosa o la otra, nunca las dos ni ninguna: un ámbito vacío no
    -- significaría nada y un ámbito doble significaría dos cosas distintas.
    CONSTRAINT ambito_exactamente_uno CHECK (
        (cartera_id IS NOT NULL AND activo_id IS NULL)
        OR (cartera_id IS NULL AND activo_id IS NOT NULL)
    )
);
CREATE UNIQUE INDEX ambito_unico_cartera ON ambito_de_visibilidad (usuario_id, cartera_id)
    WHERE cartera_id IS NOT NULL;
CREATE UNIQUE INDEX ambito_unico_activo ON ambito_de_visibilidad (usuario_id, activo_id)
    WHERE activo_id IS NOT NULL;
CREATE INDEX ambito_por_usuario ON ambito_de_visibilidad (usuario_id);

-- ═════════════════════════════════════════════════════════════════════════════
--  Row Level Security
--
--  Cuatro variables de sesión, fijadas con SET LOCAL en cada petición:
--
--    app.organizacion_id          quién es el inquilino
--    app.usuario_id               quién pregunta
--    app.ve_todo                  false solo para el rol CLIENTE
--    app.escribe_estructura       ADMIN y GESTOR
--    app.escribe_datos            ADMIN, GESTOR y ANALISTA
--
--  Sin fijarlas, las consultas no devuelven NADA. Ese es el fallo seguro:
--  olvidarse produce una lista vacía, no una fuga.
--
--  Las dos de escritura existen para que la API y la base de datos digan LO
--  MISMO. Cuando el permiso se calcula en dos sitios, el usuario acaba viendo
--  un 500 —«new row violates row-level security policy»— donde debía ver un
--  403 con su motivo.
-- ═════════════════════════════════════════════════════════════════════════════

-- `nullif(..., '')` y no un cast a secas, y esto costó dos pruebas en rojo:
-- cuando una transacción que hizo `SET LOCAL` termina, la variable NO vuelve a
-- «no definida», vuelve a **cadena vacía**. Con el cast directo, la siguiente
-- consulta de esa misma conexión del pool —sin contexto todavía— no devolvía
-- cero filas: reventaba con «invalid input syntax for type uuid: ""». Un error
-- donde tenía que haber una lista vacía, y encima en la conexión reutilizada,
-- que es el caso de todas las peticiones menos la primera.
CREATE OR REPLACE FUNCTION esg_org() RETURNS UUID
    LANGUAGE sql STABLE AS $$
    SELECT nullif(current_setting('app.organizacion_id', TRUE), '')::uuid $$;
CREATE OR REPLACE FUNCTION esg_usuario() RETURNS UUID
    LANGUAGE sql STABLE AS $$
    SELECT nullif(current_setting('app.usuario_id', TRUE), '')::uuid $$;
CREATE OR REPLACE FUNCTION esg_ve_todo() RETURNS BOOLEAN
    LANGUAGE sql STABLE AS $$
    SELECT coalesce(nullif(current_setting('app.ve_todo', TRUE), '')::boolean, FALSE) $$;
CREATE OR REPLACE FUNCTION esg_escribe_estructura() RETURNS BOOLEAN
    LANGUAGE sql STABLE AS $$
    SELECT coalesce(nullif(current_setting('app.escribe_estructura', TRUE), '')::boolean, FALSE) $$;
CREATE OR REPLACE FUNCTION esg_escribe_datos() RETURNS BOOLEAN
    LANGUAGE sql STABLE AS $$
    SELECT coalesce(nullif(current_setting('app.escribe_datos', TRUE), '')::boolean, FALSE) $$;

-- Un activo es visible si es de mi organización Y (lo veo todo, O tengo un
-- ámbito que lo alcanza, directamente o por su cartera).
CREATE OR REPLACE FUNCTION esg_activo_visible(p_activo UUID, p_cartera UUID) RETURNS BOOLEAN
    LANGUAGE sql STABLE AS $$
    SELECT esg_ve_todo() OR EXISTS (
        SELECT 1 FROM ambito_de_visibilidad a
        WHERE a.usuario_id = esg_usuario()
          AND (a.activo_id = p_activo OR a.cartera_id = p_cartera)
    )
$$;

ALTER TABLE organizacion ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizacion FORCE ROW LEVEL SECURITY;
CREATE POLICY organizacion_propia ON organizacion FOR SELECT USING (id = esg_org());

ALTER TABLE usuario ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuario FORCE ROW LEVEL SECURITY;
CREATE POLICY usuario_lectura ON usuario FOR SELECT
    USING (organizacion_id = esg_org() AND (esg_ve_todo() OR id = esg_usuario()));
CREATE POLICY usuario_escritura ON usuario FOR ALL
    USING (organizacion_id = esg_org() AND esg_escribe_estructura())
    WITH CHECK (organizacion_id = esg_org() AND esg_escribe_estructura());

ALTER TABLE ambito_de_visibilidad ENABLE ROW LEVEL SECURITY;
ALTER TABLE ambito_de_visibilidad FORCE ROW LEVEL SECURITY;
CREATE POLICY ambito_lectura ON ambito_de_visibilidad FOR SELECT
    USING (organizacion_id = esg_org() AND (esg_ve_todo() OR usuario_id = esg_usuario()));
CREATE POLICY ambito_escritura ON ambito_de_visibilidad FOR ALL
    USING (organizacion_id = esg_org() AND esg_escribe_estructura())
    WITH CHECK (organizacion_id = esg_org() AND esg_escribe_estructura());

ALTER TABLE cliente ENABLE ROW LEVEL SECURITY;
ALTER TABLE cliente FORCE ROW LEVEL SECURITY;
CREATE POLICY cliente_lectura ON cliente FOR SELECT
    USING (organizacion_id = esg_org() AND (
        esg_ve_todo() OR EXISTS (
            SELECT 1 FROM cartera c
            WHERE c.cliente_id = cliente.id
              AND esg_activo_visible(NULL, c.id)
        )
    ));
CREATE POLICY cliente_escritura ON cliente FOR ALL
    USING (organizacion_id = esg_org() AND esg_escribe_estructura())
    WITH CHECK (organizacion_id = esg_org() AND esg_escribe_estructura());

ALTER TABLE cartera ENABLE ROW LEVEL SECURITY;
ALTER TABLE cartera FORCE ROW LEVEL SECURITY;
CREATE POLICY cartera_lectura ON cartera FOR SELECT
    USING (organizacion_id = esg_org() AND (
        esg_ve_todo() OR EXISTS (
            SELECT 1 FROM ambito_de_visibilidad a
            WHERE a.usuario_id = esg_usuario()
              AND (a.cartera_id = cartera.id
                   OR a.activo_id IN (SELECT id FROM activo WHERE cartera_id = cartera.id))
        )
    ));
CREATE POLICY cartera_escritura ON cartera FOR ALL
    USING (organizacion_id = esg_org() AND esg_escribe_estructura())
    WITH CHECK (organizacion_id = esg_org() AND esg_escribe_estructura());

ALTER TABLE activo ENABLE ROW LEVEL SECURITY;
ALTER TABLE activo FORCE ROW LEVEL SECURITY;
CREATE POLICY activo_lectura ON activo FOR SELECT
    USING (organizacion_id = esg_org() AND esg_activo_visible(activo.id, activo.cartera_id));
CREATE POLICY activo_escritura ON activo FOR ALL
    USING (organizacion_id = esg_org() AND esg_escribe_estructura())
    WITH CHECK (organizacion_id = esg_org() AND esg_escribe_estructura());

ALTER TABLE ocupacion ENABLE ROW LEVEL SECURITY;
ALTER TABLE ocupacion FORCE ROW LEVEL SECURITY;
CREATE POLICY ocupacion_lectura ON ocupacion FOR SELECT
    USING (organizacion_id = esg_org() AND EXISTS (
        SELECT 1 FROM activo a WHERE a.id = ocupacion.activo_id
    ));
CREATE POLICY ocupacion_escritura ON ocupacion FOR ALL
    USING (organizacion_id = esg_org() AND esg_escribe_datos())
    WITH CHECK (organizacion_id = esg_org() AND esg_escribe_datos());

ALTER TABLE punto_de_suministro ENABLE ROW LEVEL SECURITY;
ALTER TABLE punto_de_suministro FORCE ROW LEVEL SECURITY;
-- El EXISTS sobre `activo` se apoya en la política de `activo`: un suministro
-- de un activo que no veo no existe para mí, sin repetir aquí la regla del
-- ámbito. Cuando la regla cambie, cambiará en un solo sitio.
CREATE POLICY suministro_lectura ON punto_de_suministro FOR SELECT
    USING (organizacion_id = esg_org() AND EXISTS (
        SELECT 1 FROM activo a WHERE a.id = punto_de_suministro.activo_id
    ));
CREATE POLICY suministro_escritura ON punto_de_suministro FOR ALL
    USING (organizacion_id = esg_org() AND esg_escribe_estructura())
    WITH CHECK (organizacion_id = esg_org() AND esg_escribe_estructura());

ALTER TABLE lectura ENABLE ROW LEVEL SECURITY;
ALTER TABLE lectura FORCE ROW LEVEL SECURITY;
CREATE POLICY lectura_lectura ON lectura FOR SELECT
    USING (organizacion_id = esg_org() AND EXISTS (
        SELECT 1 FROM punto_de_suministro p WHERE p.id = lectura.punto_id
    ));
CREATE POLICY lectura_escritura ON lectura FOR ALL
    USING (organizacion_id = esg_org() AND esg_escribe_datos())
    WITH CHECK (organizacion_id = esg_org() AND esg_escribe_datos());

ALTER TABLE carga ENABLE ROW LEVEL SECURITY;
ALTER TABLE carga FORCE ROW LEVEL SECURITY;
CREATE POLICY carga_lectura ON carga FOR SELECT
    USING (organizacion_id = esg_org() AND esg_ve_todo());
CREATE POLICY carga_escritura ON carga FOR ALL
    USING (organizacion_id = esg_org() AND esg_escribe_datos())
    WITH CHECK (organizacion_id = esg_org() AND esg_escribe_datos());

ALTER TABLE incidencia_de_carga ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidencia_de_carga FORCE ROW LEVEL SECURITY;
CREATE POLICY incidencia_lectura ON incidencia_de_carga FOR SELECT
    USING (organizacion_id = esg_org() AND esg_ve_todo());
CREATE POLICY incidencia_escritura ON incidencia_de_carga FOR ALL
    USING (organizacion_id = esg_org() AND esg_escribe_datos())
    WITH CHECK (organizacion_id = esg_org() AND esg_escribe_datos());

ALTER TABLE factor_de_conversion ENABLE ROW LEVEL SECURITY;
ALTER TABLE factor_de_conversion FORCE ROW LEVEL SECURITY;
-- Los factores globales (organizacion_id NULL) los lee todo el mundo: son el
-- catálogo de la instalación. Escribirlos exige estructura Y organización
-- propia: nadie edita el catálogo global desde la aplicación.
CREATE POLICY factor_lectura ON factor_de_conversion FOR SELECT
    USING (organizacion_id IS NULL OR organizacion_id = esg_org());
CREATE POLICY factor_escritura ON factor_de_conversion FOR ALL
    USING (organizacion_id = esg_org() AND esg_escribe_estructura())
    WITH CHECK (organizacion_id = esg_org() AND esg_escribe_estructura());

-- ─────────────────────────────────────────────────────────────────────────────
--  Iniciar sesión: el único hueco por el que se lee sin contexto de organización
--
--  Con Entra ID, el token dice quién eres en Azure, no en qué organización de
--  esta aplicación estás ni con qué rol: eso hay que ir a buscarlo. Y en ese
--  momento todavía no se puede fijar `app.organizacion_id`, porque es justo lo
--  que se está averiguando.
--
--  En vez de darle al rol de aplicación un permiso general de lectura sobre
--  `usuario` —que es lo cómodo, y deja la RLS de esa tabla en nada—, se abre
--  una rendija del tamaño exacto: durante el emparejamiento se pueden leer LAS
--  FILAS QUE CORRESPONDEN A LA IDENTIDAD PRESENTADA, y ninguna otra. Quien no
--  traiga un token válido de Azure no puede fijar esas variables con nada útil.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE POLICY usuario_emparejamiento ON usuario FOR SELECT USING (
    current_setting('app.login_sujeto', TRUE) IS NOT NULL
    AND current_setting('app.login_sujeto', TRUE) <> ''
    AND activo
    AND (
        (emisor_oidc = current_setting('app.login_emisor', TRUE)
         AND sub_oidc = current_setting('app.login_sujeto', TRUE))
        -- Primer inicio de sesión de alguien dado de alta por su correo: aún
        -- no tiene sujeto fijado. Se empareja UNA vez y a partir de ahí manda
        -- el par (emisor, sujeto).
        OR (sub_oidc IS NULL
            AND lower(email) = lower(coalesce(current_setting('app.login_email', TRUE), '')))
    )
);

CREATE POLICY usuario_primer_acceso ON usuario FOR UPDATE USING (
    current_setting('app.login_sujeto', TRUE) IS NOT NULL
    AND current_setting('app.login_sujeto', TRUE) <> ''
    AND activo
    AND (
        (emisor_oidc = current_setting('app.login_emisor', TRUE)
         AND sub_oidc = current_setting('app.login_sujeto', TRUE))
        OR (sub_oidc IS NULL
            AND lower(email) = lower(coalesce(current_setting('app.login_email', TRUE), '')))
    )
);

-- La política de arriba deja actualizar **esa fila**, y una fila se actualiza
-- entera: sin esto, el emparejamiento del inicio de sesión podría cambiar el
-- rol o la organización del propio usuario. La restricción de columnas no la
-- sabe expresar una política; la sabe expresar un trigger.
CREATE OR REPLACE FUNCTION usuario_solo_marcas_de_acceso() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- Por la función y no por `current_setting` a pelo: la variable vale ''
    -- —no NULL— en una conexión reutilizada del pool, y el cast directo aquí
    -- reventaba el inicio de sesión de todo el mundo menos el primero.
    IF esg_escribe_estructura() THEN
        RETURN NEW;  -- un administrador sí edita la ficha entera
    END IF;
    IF NEW.rol IS DISTINCT FROM OLD.rol
       OR NEW.organizacion_id IS DISTINCT FROM OLD.organizacion_id
       OR NEW.email IS DISTINCT FROM OLD.email
       OR NEW.activo IS DISTINCT FROM OLD.activo THEN
        RAISE EXCEPTION
            'El inicio de sesión solo fija emisor_oidc, sub_oidc, nombre y ultimo_acceso_en';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER usuario_login_acotado
    BEFORE UPDATE ON usuario
    FOR EACH ROW EXECUTE FUNCTION usuario_solo_marcas_de_acceso();

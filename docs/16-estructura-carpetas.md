# 23. Estructura inicial de carpetas del proyecto

> Este documento **describe** la estructura que se creará al ejecutar el entregable 24 (código inicial
> del MVP). Se presenta ahora para su validación, conforme a §16 del encargo. Todavía no existe en el
> repositorio.

---

## 23.1. Decisión: monorepo

| Opción | A favor | En contra | Veredicto |
|---|---|---|---|
| **Monorepo** | Un `commit` cambia API y cliente de forma coherente; el contrato OpenAPI se verifica en el mismo ciclo; un `docker-compose` para todo | Requiere disciplina de límites entre módulos | ✅ **Recomendado** |
| Repositorios separados | Ciclos de despliegue independientes | Con tres personas, coordinar dos repositorios para un cambio de contrato es fricción pura | ❌ |

`[REC]` La separación importante no es de repositorios: es de **módulos de dominio dentro del
backend**, con dependencias explícitas verificadas en CI.

---

## 23.2. Árbol de primer nivel

```
tdd-inmobiliaria/
├── README.md                       Qué es, cómo se arranca, dónde está la documentación
├── CLAUDE.md                       Convenciones del proyecto para agentes de IA
├── LICENSE · .gitignore · .editorconfig
├── .pre-commit-config.yaml         lint, tipos, formato, escaneo de secretos
├── Makefile                        make up · test · migrate · seed · lint · security
├── docker-compose.yml              Entorno local completo
├── .env.example                    TODAS las variables, SIN un solo valor real
│
├── docs/                           ← Esta documentación de diseño
│   ├── 01-resumen-supuestos-preguntas.md … 17-requisitos-no-funcionales.md
│   ├── adr/                        Decisiones arquitectónicas registradas
│   │   ├── 0001-monolito-modular.md
│   │   ├── 0002-python-por-python-pptx.md
│   │   ├── 0003-rls-para-multi-tenancy.md
│   │   ├── 0004-original-inmutable-cuatro-barreras.md
│   │   ├── 0005-contrato-de-plantilla-pptx.md
│   │   ├── 0006-estado-y-fases-como-ejes-independientes.md
│   │   ├── 0007-catalogos-como-datos.md
│   │   ├── 0008-horizonte-unico-y-medicion-opcional.md
│   │   └── 0009-zona-normalizada-frente-a-location-node.md
│   ├── plantilla-pptx/
│   │   ├── contrato-de-plantilla.md
│   │   ├── catalogo-de-marcadores.md
│   │   └── Plantilla_Referencia_TDD.pptx
│   ├── catalogos/                  Fuente de verdad de la semilla, en CSV revisable
│   │   ├── tipologias.csv
│   │   ├── zonas.csv
│   │   ├── zonas_por_tipologia.csv        ← la matriz de §5.2
│   │   ├── codigos_capex.csv              ← los 121 elementos
│   │   ├── riesgos.csv                    ← con la definición íntegra
│   │   ├── conceptos.csv · horizontes.csv
│   │   ├── sistemas_tecnicos.csv
│   │   └── fases.csv · categorias_documentacion.csv
│   └── operacion/
│       ├── despliegue.md · copias-y-restauracion.md
│       ├── respuesta-a-incidentes.md · runbook-purga-de-datos.md
│       └── habilitar-fuente-de-precios.md    ← procedimiento legal + técnico
│
├── apps/
│   ├── api/                        Backend FastAPI + workers
│   └── web/                        Frontend React + TypeScript
│
├── packages/
│   └── api-client/                 Cliente TS generado desde OpenAPI (comprometido)
│
├── infra/
│   ├── docker/                     Dockerfiles por servicio
│   ├── terraform/                  Infraestructura como código (fase 2)
│   └── k8s/                        Manifiestos (opcional)
│
├── scripts/
│   ├── seed_demo_data.py           Datos ficticios reproducibles
│   ├── seed_catalogs.py            Carga los CSV de docs/catalogos/
│   ├── generate_api_client.sh · check_api_client_drift.sh
│   ├── verify_audit_chain.py
│   └── make_test_templates.py      Genera el corpus T1-T20
│
└── .github/workflows/
    ├── ci.yml                      Ciclo bloqueante (< 15 min)
    ├── nightly.yml                 Mutación, ZAP, corpus PPTX, rendimiento
    └── deploy.yml
```

`[REC]` **Los catálogos viven en CSV dentro de `docs/`, no incrustados en una migración de Python.**
Motivos: son 121 códigos y 86 relaciones que el cliente debe poder revisar sin leer código; un CSV se
abre en Excel y se comenta; y el `diff` de un cambio en el árbol es legible en una revisión de código.
La migración los lee; la fuente de verdad es el CSV.

---

## 23.3. Backend: `apps/api/`

```
apps/api/
├── pyproject.toml · alembic.ini
├── Dockerfile
├── Dockerfile.worker               Con LibreOffice, libheif, libmagic, fuentes
│
├── src/tdd/
│   ├── main.py                     Composición de la aplicación
│   ├── celery_app.py               Colas io / heavy, Beat
│   │
│   ├── core/                       ── Infraestructura transversal ──
│   │   ├── config.py               Pydantic Settings (12-factor)
│   │   ├── db.py                   Motor, sesión, SET LOCAL app.current_org_id
│   │   ├── security.py             Argon2id, JWT, TOTP
│   │   ├── deps.py                 Dependencias: usuario, sesión, organización
│   │   ├── errors.py               Excepciones de dominio → RFC 9457
│   │   ├── logging.py              Logs estructurados con redacción
│   │   ├── telemetry.py · pagination.py · idempotency.py
│   │   └── money.py                Decimal, redondeo, formateo
│   │
│   ├── models/                     ── SQLAlchemy 2 ──
│   │   ├── base.py                 Mixins: auditoría, soft delete, tenant, versión
│   │   ├── organization.py · user.py · role.py
│   │   ├── client.py · project.py
│   │   ├── phase.py                ⚠ phase_definition · project_phase · doc_request
│   │   │                             vdr_link · asset_visit · qa_round · phase_event
│   │   ├── asset.py · location.py
│   │   ├── catalog.py              ⚠ typology · zone · zone_typology · capex_code
│   │   │                             risk_level · concept · horizon · technical_system
│   │   ├── finding.py · recommendation.py · equipment.py
│   │   ├── capex.py · price.py · cost_profile.py
│   │   ├── photo.py · document.py
│   │   ├── report.py · template.py
│   │   └── audit.py · comment.py · notification.py · approval.py · task.py
│   │
│   ├── schemas/                    ── Pydantic v2: entrada ≠ salida ──
│   │
│   ├── modules/                    ══ MÓDULOS DE DOMINIO ══
│   │   │
│   │   ├── identity/               router · service · identity_provider · password_policy
│   │   │
│   │   ├── authz/                  ⚠ Núcleo de autorización
│   │   │   ├── permissions.py      Catálogo de permisos declarativos
│   │   │   ├── policies.py         Rol efectivo, alcance por activo, estado
│   │   │   ├── guards.py           require_permission(...)
│   │   │   └── rls.py              Contexto de organización por petición
│   │   │
│   │   ├── catalogs/               ⚠ Estructura del bloque de CAPEX
│   │   │   ├── router.py · service.py
│   │   │   ├── zone_rules.py       ⚠ PURO: qué zona aplica a qué tipología
│   │   │   ├── code_tree.py        ⚠ PURO: árbol, seleccionabilidad, retirada
│   │   │   └── seeding.py          Carga desde docs/catalogos/*.csv
│   │   │
│   │   ├── projects/
│   │   │   ├── router.py · service.py · repository.py
│   │   │   ├── state_machine.py    ⚠ PURO: transiciones y guardas
│   │   │   ├── duplication.py      Duplicado selectivo
│   │   │   └── search.py           FTS en español
│   │   │
│   │   ├── phases/                 ⚠ Bloque nuevo
│   │   │   ├── router.py · service.py
│   │   │   ├── engine.py           ⚠ PURO: estados derivados
│   │   │   ├── doc_requests.py     Checklist y limitaciones del informe
│   │   │   ├── vdr.py              Enlace externo (nunca credenciales)
│   │   │   ├── visits.py           Visitas por activo y agregado
│   │   │   └── qa.py               Rondas versionadas
│   │   │
│   │   ├── assets/
│   │   │   ├── router.py · service.py
│   │   │   ├── typology_change.py  ⚠ Previsualización de impacto
│   │   │   ├── location_tree.py
│   │   │   └── map_provider.py     Interfaz + adaptadores
│   │   │
│   │   ├── evidence/
│   │   │   ├── router.py · service.py · upload.py
│   │   │   ├── naming.py           ⚠ PURO: plantilla de nombres y saneado
│   │   │   ├── exif.py · hashing.py · derivatives.py
│   │   │   ├── annotations.py · versions.py · trash.py
│   │   │
│   │   ├── diagnosis/
│   │   │   ├── router.py · service.py
│   │   │   ├── finding_state.py
│   │   │   ├── equipment_import.py XLSX con informe de errores
│   │   │   └── risk_matrix.py
│   │   │
│   │   ├── capex/                  ⚠ Motor de cálculo
│   │   │   ├── router.py · service.py
│   │   │   ├── engine.py           ⚠⚠ PURO: sin E/S, sin base de datos, sin reloj
│   │   │   ├── horizons.py         Un horizonte por línea · pivote a columnas
│   │   │   ├── cascade.py          Cascada configurable (solo desglose por medición)
│   │   │   ├── rounding.py · scenarios.py · indices.py
│   │   │   ├── views.py            Las diez vistas agregadas
│   │   │   └── export.py           XLSX con trazabilidad y catálogos · CSV
│   │   │
│   │   ├── prices/
│   │   │   ├── router.py · resolver.py · normalization.py
│   │   │   ├── compliance.py       robots.txt, ToS, licencia, límite, autodeshabilitado
│   │   │   ├── base.py             PriceSourceAdapter (Protocol)
│   │   │   ├── registry.py
│   │   │   └── adapters/
│   │   │       ├── manual.py            ✅ real
│   │   │       ├── internal_catalog.py  ✅ real
│   │   │       └── precio_centro.py     ⚠️ ANDAMIO · NotImplementedError
│   │   │
│   │   ├── reporting/              ⚠ PPTX
│   │   │   ├── router.py · service.py
│   │   │   ├── analyzer.py         Lectura (solo lectura)
│   │   │   ├── tokens.py · directives.py · mapping.py
│   │   │   ├── renderer.py         ⚠ Generación
│   │   │   ├── repeat.py · tables.py · images.py
│   │   │   ├── overflow.py         Estimación con fontTools
│   │   │   ├── preview.py          LibreOffice headless
│   │   │   ├── snapshot.py         Congelación de datos y catálogos + hash
│   │   │   ├── versioning.py · warnings.py
│   │   │
│   │   ├── collaboration/
│   │   └── audit/
│   │       ├── router.py · logger.py · hash_chain.py
│   │       ├── change_history.py · redaction.py
│   │
│   ├── adapters/                   ── Infraestructura tras interfaz ──
│   │   ├── storage/ · malware/ · mailer/ · maps/ · office/
│   │
│   ├── workers/
│   │   ├── photos.py · reports.py · exports.py
│   │   ├── prices.py               refresh_index · check_licences
│   │   ├── phases.py               recalc_derived_status
│   │   └── maintenance.py          purge · verify_audit_chain · notify
│   │
│   └── migrations/versions/
│       ├── 0001_initial_schema.py
│       ├── 0002_rls_policies.py            ⚠ Políticas de TODAS las tablas
│       ├── 0003_immutability_triggers.py   ⚠ Original y emitido inmutables
│       ├── 0004_capex_total_and_recalc.py  ⚠ Columna generada + cascada
│       ├── 0005_zone_typology_check.py     ⚠ Coherencia zona/tipología
│       ├── 0006_phase_derived_status.py
│       ├── 0007_audit_partitions.py
│       ├── 0008_search_vectors.py
│       └── 0009_seed_catalogs.py           Lee docs/catalogos/*.csv
│
└── tests/
    ├── conftest.py                 testcontainers: PostgreSQL + MinIO reales
    ├── factories/
    ├── fixtures/
    │   ├── permission_matrix.yaml  ⚠ La matriz de §11.3 como datos
    │   ├── capex_golden_cases.yaml Casos dorados verificados a mano
    │   ├── zone_typology_matrix.yaml  ⚠ Las 86 combinaciones
    │   ├── templates/              Corpus T1-T20
    │   ├── images/                 Válidas, corruptas, maliciosas, EXIF variado
    │   └── expected_renders/
    ├── unit/
    │   ├── capex/                  ⚠ Mayor densidad del proyecto
    │   ├── catalogs/               ⚠ Zona × tipología, árbol, retirada
    │   ├── phases/                 ⚠ Estados derivados
    │   ├── evidence/naming/
    │   ├── reporting/
    │   └── state_machines/
    ├── integration/
    │   ├── test_constraints.py · test_immutability.py
    │   ├── test_rls_isolation.py   ⚠ Paramétrica sobre TODAS las tablas
    │   ├── test_generated_totals.py
    │   ├── test_audit_transactional.py
    │   └── test_api_*.py
    ├── permissions/
    │   ├── test_matrix.py
    │   └── test_router_coverage.py ⚠ Falla si un endpoint no declara política
    ├── security/
    │   └── test_no_calls_to_disabled_sources.py  ⚠ Red interceptada
    └── performance/
```

### Reglas de dependencia entre módulos `[REC]`

```mermaid
flowchart TD
    R["routers"] --> S["services"]
    S --> D["dominio puro:<br/>capex/engine · phases/engine<br/>catalogs/zone_rules · evidence/naming<br/>projects/state_machine"]
    S --> RE["repositories"]
    S --> AD["adapters (interfaces)"]
    RE --> M["models"]
    AD -.->|implementaciones| EXT["S3 · ClamAV · SMTP · mapas"]

    X1["capex/engine.py"] -.->|"❌ PROHIBIDO"| M
    X2["phases/engine.py"] -.->|"❌ PROHIBIDO"| AD

    style D fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style X1 fill:#fde7e9,stroke:#c62828
    style X2 fill:#fde7e9,stroke:#c62828
```

Cinco reglas verificadas con `import-linter` en CI:

1. Los módulos puros (`capex/engine`, `capex/cascade`, `capex/horizons`, `phases/engine`,
   `catalogs/zone_rules`, `catalogs/code_tree`, `evidence/naming`, `projects/state_machine`) **no
   importan** modelos, sesión de base de datos ni adaptadores.
2. Los módulos de dominio no se importan entre sí: se comunican por servicios de aplicación o eventos.
   **Excepción explícita:** `capex` y `diagnosis` pueden importar `catalogs` (solo lectura de tipos).
3. Los `router` no acceden a `models` directamente.
4. `adapters/` define interfaces; las implementaciones se instancian solo en la composición.
5. `prices/adapters/` no puede importarse desde `capex/`: el núcleo del cálculo no conoce ninguna
   fuente.

---

## 23.4. Frontend: `apps/web/`

```
apps/web/
├── package.json · vite.config.ts · tsconfig.json
├── tailwind.config.ts · playwright.config.ts
├── public/manifest.webmanifest     PWA
└── src/
    ├── main.tsx · App.tsx · router.tsx
    │
    ├── lib/
    │   ├── api.ts                  Cliente generado + interceptores
    │   ├── auth.ts                 Token en memoria, refresco silencioso
    │   ├── query.ts                TanStack Query
    │   ├── catalogs.ts             ⚠ Caché de catálogos con huella de versión
    │   ├── offline/
    │   │   ├── db.ts               Dexie / IndexedDB
    │   │   ├── upload-queue.ts     ⚠ Cola persistente con idempotencia
    │   │   └── sync.ts
    │   ├── money.ts · i18n.ts · a11y.ts
    │
    ├── design-system/
    │   ├── Button · Input · Select · Dialog · Toast · Table · Tabs
    │   ├── SaveIndicator.tsx       «Guardado 12:04» / «3 pendientes»
    │   ├── RiskSelector.tsx        ⚠ Con la definición del grado visible
    │   ├── ZoneSelector.tsx        ⚠ Filtrado por tipología del activo
    │   ├── CapexCodePicker.tsx     ⚠ Árbol de 3 niveles con búsqueda
    │   ├── PhaseChip.tsx           ● ◐ ○ con etiqueta textual
    │   └── EmptyState · ErrorState · LoadingState
    │
    ├── features/
    │   ├── auth/                   Pantalla 1
    │   ├── dashboard/              Pantalla 2
    │   ├── projects/               Pantallas 3, 4, 5
    │   │   ├── PhaseSelectionStep.tsx   ⚠ Paso ④ del asistente
    │   │   └── PhasePanel.tsx           ⚠ Panel de la ficha
    │   ├── phases/                 Fases: doc, VDR, visitas, Q&A, eventos
    │   ├── assets/                 Pantalla 6 (+ MapView, TypologyChangeDialog)
    │   ├── team/                   Pantalla 7 (+ matriz de cobertura)
    │   ├── photos/                 Pantallas 8, 9
    │   │   ├── PhotoGrid.tsx       Virtualizada
    │   │   ├── AnnotationCanvas.tsx  Konva
    │   │   ├── BulkRenameDialog.tsx  ⚠ Previsualización obligatoria
    │   │   ├── CameraCapture.tsx · ContextBar.tsx  ⚠ Contexto persistente
    │   ├── equipment/              Pantalla 10
    │   ├── findings/               Pantallas 11, 12
    │   ├── capex/                  Pantallas 13, 14
    │   │   ├── CapexTable.tsx      TanStack Table, columnas por horizonte
    │   │   ├── HorizonPicker.tsx   ⚠ Un horizonte + un importe
    │   │   ├── CascadePanel.tsx    ⚠ «Cómo se calcula»
    │   │   └── PriceComparator.tsx ⚠ Con skipped_sources visibles
    │   ├── reports/                Pantallas 15, 16, 17, 18
    │   ├── admin/                  Pantalla 19
    │   └── audit/
    │
    └── tests/unit · tests/e2e      E1-E12 de §19.10
```

---

## 23.5. Ficheros clave

### `.env.example` — sin un solo valor real `[REQ]`

```bash
# ── Aplicación ──────────────────────────────────────────────
APP_ENV=local                      # local | staging | production
APP_SECRET_KEY=                    # generar: openssl rand -hex 32
APP_BASE_URL=http://localhost:5173
LOG_LEVEL=INFO

# ── Base de datos ───────────────────────────────────────────
DATABASE_URL=                      # postgresql+psycopg://usuario:clave@host:5432/base
DATABASE_MIGRATION_URL=            # usuario con DDL, distinto del de aplicación

# ── Redis y colas ───────────────────────────────────────────
REDIS_URL= · CELERY_BROKER_URL= · CELERY_RESULT_BACKEND=

# ── Almacenamiento de objetos (compatible S3) ───────────────
STORAGE_ENDPOINT_URL= · STORAGE_REGION= · STORAGE_BUCKET=
STORAGE_ACCESS_KEY_ID= · STORAGE_SECRET_ACCESS_KEY=
STORAGE_SIGNED_URL_TTL_SECONDS=300
STORAGE_ENABLE_OBJECT_LOCK=true    # WORM sobre originals/ y templates/

# ── Autenticación ───────────────────────────────────────────
JWT_PRIVATE_KEY_PEM= · JWT_PUBLIC_KEY_PEM=
JWT_PREVIOUS_PUBLIC_KEY_PEM=       # permite rotar sin cerrar sesiones
ACCESS_TOKEN_TTL_MINUTES=15
REFRESH_TOKEN_TTL_DAYS=14
FIELD_ENCRYPTION_KEY=              # AES-256-GCM para secretos TOTP

# ── Correo ──────────────────────────────────────────────────
SMTP_HOST= · SMTP_PORT= · SMTP_USER= · SMTP_PASSWORD= · MAIL_FROM=

# ── Antimalware y conversión ────────────────────────────────
CLAMAV_HOST= · CLAMAV_PORT=3310
LIBREOFFICE_BIN=/usr/bin/soffice
PPTX_MAX_UNCOMPRESSED_MB=200
PPTX_RENDER_TIMEOUT_SECONDS=180

# ── Límites de archivo ──────────────────────────────────────
MAX_UPLOAD_MB=50 · MAX_BATCH_UPLOAD_MB=500

# ── Mapas (adaptador configurable) ──────────────────────────
MAP_PROVIDER= · MAP_TILE_URL_TEMPLATE= · MAP_API_KEY=
GEOCODER_PROVIDER= · GEOCODER_API_KEY=

# ── Fuentes de precios ──────────────────────────────────────
# Ninguna fuente externa se habilita por configuración: se habilita en la
# aplicación, y solo tras registrar licencia vigente y revisión de las
# condiciones de uso por un administrador. Precio Centro NO está integrado.
PRICE_SOURCE_HTTP_TIMEOUT_SECONDS=10
PRICE_SOURCE_USER_AGENT=           # identificación honesta + URL de contacto

# ── Observabilidad ──────────────────────────────────────────
OTEL_EXPORTER_OTLP_ENDPOINT= · SENTRY_DSN=

# ── Retención ───────────────────────────────────────────────
DEFAULT_RETENTION_MONTHS=84 · TRASH_PURGE_DAYS=30 · EXPORT_EXPIRY_DAYS=7
```

### `Makefile`

```makefile
up:             ## Levanta el entorno local completo
	docker compose up -d --build
	$(MAKE) migrate seed-catalogs seed-demo
	@echo "API  → http://localhost:8000/docs"
	@echo "Web  → http://localhost:5173"
	@echo "MinIO→ http://localhost:9001   Mail → http://localhost:8025"

migrate:        ## Aplica migraciones
seed-catalogs:  ## Carga los catálogos desde docs/catalogos/*.csv
seed-demo:      ## Datos ficticios reproducibles
test:           ## Suite completa
test-unit:      ## Unitarias (~35 s)
test-catalogs:  ## Las 86 combinaciones zona × tipología
test-perms:     ## Matriz de permisos y aislamiento RLS
test-pptx:      ## Corpus T1-T20
lint:           ## ruff · mypy · eslint · tsc · import-linter
security:       ## bandit · semgrep · pip-audit · npm audit · secretos
api-client:     ## Regenera el cliente TypeScript desde OpenAPI
down:           ## Detiene y limpia
```

### `CLAUDE.md` — convenciones que no se negocian

```markdown
# Convenciones del proyecto

## Invariantes que nunca se rompen
1. Nunca se sobrescribe un objeto original (fotografía, documento, plantilla).
2. Nunca se usa `float` para dinero. Solo `Decimal` y `NUMERIC`.
3. Una línea de CAPEX tiene UN horizonte y UN importe, y ese importe lo incluye todo.
   La cascada NUNCA se aplica sobre un importe tecleado: se traslada con acción explícita.
   Del perfil de costes, solo `tax_pct` afecta a todas las líneas.
4. Nunca se marca un precio como validado sin un usuario identificado.
5. Nunca se modifica una versión de informe emitida.
6. Nunca se escribe a mano el estado de una fase derivada.
7. Nunca se borra la zona de una línea al cambiar la tipología del activo.
8. Nunca se ejecuta `DELETE` desde la aplicación: borrado lógico.
9. Nunca se realiza una petición de red a una fuente de precios deshabilitada.
10. Nunca se registra ni se devuelve un secreto, una traza o una ruta interna.
11. Todo endpoint declara su política de autorización.
12. Toda operación crítica escribe auditoría en la misma transacción.

## Reglas de importación
- Los módulos puros no importan modelos, sesión ni adaptadores.
- Los módulos de dominio no se importan entre sí (excepto `catalogs`, solo lectura).
- `prices/adapters/` no se importa desde `capex/`.
- Verificado por `import-linter` en CI.

## Catálogos
- La fuente de verdad son los CSV de `docs/catalogos/`. La migración los lee.
- Un código nunca se borra: se retira con `deprecated_at`.
- Las filas del sistema (`organization_id IS NULL`) no son editables desde la aplicación.

## Convenciones de código
- Nombres de dominio en español en la interfaz; identificadores en inglés en el código
  (`finding`, `asset`, `zone`). Documentado en `docs/adr/0010-idioma-del-codigo.md`.
- Migraciones: una por cambio lógico, con `downgrade` funcional.
- Mensajes de error de usuario en español, desde el catálogo de i18n.
```

---

## 23.6. Ejecución en local

```bash
git clone <repo> && cd tdd-inmobiliaria
cp .env.example .env
# Generar los secretos locales (el fichero indica cómo)
make up
```

Levanta ocho servicios (API, worker `io`, worker `heavy`, PostgreSQL, Redis, MinIO, ClamAV, MailHog,
LibreOffice), aplica migraciones, **carga los catálogos** y siembra datos ficticios.

`[REC]` **`make up` debe funcionar a la primera en una máquina limpia.** Es el indicador más honesto de
la salud de un proyecto: si el entorno local cuesta media tarde de montar, cada persona nueva pierde
esa media tarde y nadie ejecuta las pruebas de integración.

---

## 23.7. Marcado de lo pendiente

`[REQ]` §15: «Marca claramente los mocks, prototipos y funcionalidades pendientes.»

| Convención | Uso |
|---|---|
| `# SCAFFOLD:` | Andamio no funcional. Lanza `NotImplementedError` fuera de las pruebas |
| `# MOCK:` | Doble de prueba. **Prohibido en `src/`**, verificado en CI |
| `# TODO(fase-N):` | Pendiente planificado, con la fase que lo aborda |
| `# LIMITATION:` | Límite técnico conocido, con enlace al documento que lo explica |
| `# ASSUMPTION(P-nn):` | Supuesto ligado a una pregunta abierta concreta `[REC]` |
| Distintivo en la interfaz | Toda función incompleta lo muestra al usuario |
| `docs/PENDIENTE.md` | Índice único de todo lo marcado, generado en CI |

Ejemplo del único andamio previsto en el MVP:

```python
class PrecioCentroSource:
    """SCAFFOLD: adaptador NO FUNCIONAL para Precio Centro.

    Existe para demostrar que añadir una fuente de precios no requiere
    tocar el núcleo de CAPEX. No consulta ningún servicio real, y no se
    realiza ninguna extracción automatizada del sitio web.

    Para convertirlo en un adaptador operativo hacen falta cuatro pasos,
    y los dos primeros NO son técnicos:
      1. Confirmar licencia vigente y a nombre de quién (P-06).
      2. Revisar y registrar sus condiciones de uso (rol ADMIN).
      3. Determinar el modo de acceso: API oficial, exportación licenciada,
         o ninguno. La vía preferente es la importación del catálogo
         exportado, no la consulta en línea (ver docs/11 §16.5).
      4. Implementar y probar contra la fuente real.

    LIMITATION: ver docs/11-capex-precios.md §16.5 y §16.11.
    """

    def search(self, query: PriceQuery) -> list[PriceCandidate]:
        raise NotImplementedError(
            "Adaptador no implementado. Use la entrada manual o importe "
            "el catálogo licenciado desde Administración › Fuentes de precios."
        )
```

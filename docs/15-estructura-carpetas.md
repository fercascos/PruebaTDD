# 23. Estructura inicial de carpetas del proyecto

> Este documento **describe** la estructura que se creará al ejecutar el entregable 24 (código
> inicial del MVP). Se presenta ahora para su validación, conforme a §16 del encargo. Todavía no
> existe en el repositorio.

---

## 23.1. Decisión: monorepo

| Opción | A favor | En contra | Veredicto |
|---|---|---|---|
| **Monorepo** | Un solo `commit` cambia API y cliente de forma coherente; el contrato OpenAPI se verifica en CI en el mismo ciclo; un `docker-compose` para todo; una sola versión del proyecto | Requiere disciplina de límites entre módulos | ✅ **Recomendado** |
| Repositorios separados | Ciclos de despliegue independientes | Con un equipo de tres personas, coordinar dos repositorios para un cambio de contrato es fricción pura | ❌ |

`[REC]` Con el tamaño de equipo supuesto (S-07), el monorepo es claramente superior. La separación
importante no es de repositorios: es de **módulos de dominio dentro del backend**, con dependencias
explícitas.

---

## 23.2. Árbol de primer nivel

```
tdd-inmobiliaria/
├── README.md                       Qué es, cómo se arranca, dónde está la documentación
├── CLAUDE.md                       Convenciones del proyecto para agentes de IA
├── LICENSE
├── .gitignore                      .env incluido explícitamente
├── .editorconfig
├── .pre-commit-config.yaml         lint, tipos, formato, escaneo de secretos
├── Makefile                        make up · make test · make migrate · make seed · make lint
├── docker-compose.yml              Entorno local completo
├── docker-compose.override.yml.example
├── .env.example                    TODAS las variables, SIN un solo valor real
│
├── docs/                           ← Esta documentación de diseño
│   ├── 01-resumen-supuestos-preguntas.md
│   ├── … (16 documentos)
│   ├── adr/                        Decisiones arquitectónicas registradas
│   │   ├── 0001-monolito-modular.md
│   │   ├── 0002-python-por-python-pptx.md
│   │   ├── 0003-rls-para-multi-tenancy.md
│   │   ├── 0004-original-inmutable-cuatro-barreras.md
│   │   ├── 0005-contrato-de-plantilla-pptx.md
│   │   └── 0006-cascada-capex-configurable.md
│   ├── plantilla-pptx/             Contrato de plantilla + plantilla de referencia
│   │   ├── contrato-de-plantilla.md
│   │   ├── catalogo-de-marcadores.md
│   │   └── Plantilla_Referencia_TDD.pptx
│   └── operacion/
│       ├── despliegue.md
│       ├── copias-y-restauracion.md
│       ├── respuesta-a-incidentes.md
│       └── runbook-purga-de-datos.md
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
│   └── k8s/                        Manifiestos (opcional, fase 2)
│
├── scripts/
│   ├── seed_demo_data.py           Datos ficticios reproducibles
│   ├── generate_api_client.sh      OpenAPI → TypeScript
│   ├── check_api_client_drift.sh   Puerta de CI
│   ├── verify_audit_chain.py       Verificación de la cadena hash
│   └── make_test_templates.py      Genera el corpus T1–T18
│
└── .github/
    └── workflows/
        ├── ci.yml                  Ciclo bloqueante (< 15 min)
        ├── nightly.yml             Mutación, ZAP, corpus PPTX, rendimiento
        └── deploy.yml
```

---

## 23.3. Backend: `apps/api/`

```
apps/api/
├── pyproject.toml                  Dependencias y configuración de herramientas
├── alembic.ini
├── Dockerfile
├── Dockerfile.worker               Con LibreOffice, libheif, libmagic, fuentes
│
├── src/tdd/
│   ├── main.py                     Composición de la aplicación FastAPI
│   ├── celery_app.py               Colas io / heavy, Celery Beat
│   │
│   ├── core/                       ── Infraestructura transversal ──
│   │   ├── config.py               Ajustes con Pydantic Settings (12-factor)
│   │   ├── db.py                   Motor, sesión, SET LOCAL app.current_org_id
│   │   ├── security.py             Argon2id, JWT, TOTP
│   │   ├── deps.py                 Dependencias FastAPI: usuario actual, sesión, organización
│   │   ├── errors.py               Excepciones de dominio → RFC 9457
│   │   ├── logging.py              Logs estructurados con redacción de secretos
│   │   ├── telemetry.py            OpenTelemetry
│   │   ├── pagination.py           Cursor
│   │   ├── idempotency.py          Idempotency-Key
│   │   └── money.py                Decimal, redondeo, formateo
│   │
│   ├── models/                     ── SQLAlchemy 2, un fichero por área ──
│   │   ├── base.py                 Mixins: auditoría, soft delete, tenant, versión
│   │   ├── organization.py · user.py · role.py
│   │   ├── client.py · project.py · asset.py · location.py
│   │   ├── technical_system.py · equipment.py · inspection.py
│   │   ├── finding.py · recommendation.py
│   │   ├── capex.py · price.py
│   │   ├── photo.py · document.py
│   │   ├── report.py · template.py
│   │   └── audit.py · comment.py · notification.py · approval.py · task.py
│   │
│   ├── schemas/                    ── Pydantic v2: entrada ≠ salida ──
│   │   └── (un módulo por área, con *Create, *Update, *Read, *List)
│   │
│   ├── modules/                    ══ MÓDULOS DE DOMINIO ══
│   │   │
│   │   ├── identity/
│   │   │   ├── router.py           /auth, /me, /users
│   │   │   ├── service.py
│   │   │   ├── identity_provider.py  Interfaz (OIDC-ready)
│   │   │   └── password_policy.py
│   │   │
│   │   ├── authz/                  ⚠ Núcleo de autorización
│   │   │   ├── permissions.py      Catálogo de permisos declarativos
│   │   │   ├── policies.py         Rol efectivo, alcance por activo, estado
│   │   │   ├── guards.py           Dependencias FastAPI: require_permission(...)
│   │   │   └── rls.py              Contexto de organización por petición
│   │   │
│   │   ├── projects/
│   │   │   ├── router.py · service.py · repository.py
│   │   │   ├── state_machine.py    Transiciones y guardas
│   │   │   ├── duplication.py      Duplicado selectivo
│   │   │   └── search.py           FTS en español
│   │   │
│   │   ├── assets/
│   │   │   ├── router.py · service.py
│   │   │   ├── location_tree.py    Árbol zona/planta/espacio
│   │   │   └── map_provider.py     Interfaz MapProvider + adaptadores
│   │   │
│   │   ├── evidence/               ── Fotografías y documentos ──
│   │   │   ├── router.py · service.py
│   │   │   ├── upload.py           Intención, confirmación, idempotencia
│   │   │   ├── naming.py           ⚠ Plantilla de nombres y saneado
│   │   │   ├── exif.py             Extracción y eliminación de metadatos
│   │   │   ├── hashing.py          SHA-256 + hash perceptual
│   │   │   ├── derivatives.py      Miniaturas y previsualizaciones
│   │   │   ├── annotations.py      Capa vectorial
│   │   │   ├── versions.py
│   │   │   └── trash.py
│   │   │
│   │   ├── diagnosis/              ── Inventario e incidencias ──
│   │   │   ├── router.py · service.py
│   │   │   ├── equipment_import.py XLSX con informe de errores
│   │   │   ├── risk_matrix.py
│   │   │   └── finding_state.py
│   │   │
│   │   ├── capex/                  ⚠ Motor de cálculo
│   │   │   ├── router.py · service.py
│   │   │   ├── engine.py           ⚠⚠ PURO: sin E/S, sin base de datos, sin reloj
│   │   │   ├── cascade.py          Cascada configurable
│   │   │   ├── rounding.py
│   │   │   ├── scenarios.py
│   │   │   ├── indices.py          Actualización temporal y geográfica
│   │   │   ├── views.py            Las siete vistas agregadas
│   │   │   └── export.py           XLSX con hoja de trazabilidad · CSV
│   │   │
│   │   ├── prices/                 ── Adaptadores de precios ──
│   │   │   ├── router.py
│   │   │   ├── resolver.py         Orquestador: fan-out, normalización
│   │   │   ├── normalization.py    Unidad, moneda, impuestos, ámbito
│   │   │   ├── compliance.py       robots.txt, ToS, límite de tasa, autodeshabilitado
│   │   │   ├── base.py             PriceSourceAdapter (Protocol)
│   │   │   ├── registry.py         Registro de adaptadores
│   │   │   └── adapters/
│   │   │       ├── manual.py               ✅ real
│   │   │       ├── internal_catalog.py     ✅ real
│   │   │       └── open_data_api.py        ⚠️ ANDAMIO · NotImplementedError
│   │   │
│   │   ├── reporting/              ⚠ PPTX
│   │   │   ├── router.py · service.py
│   │   │   ├── analyzer.py         Lectura de plantilla (solo lectura)
│   │   │   ├── tokens.py           Catálogo cerrado de marcadores
│   │   │   ├── directives.py       Directivas @ de las notas
│   │   │   ├── mapping.py          Validación y resolución del mapeo
│   │   │   ├── renderer.py         ⚠ Generación
│   │   │   ├── repeat.py           Repetición por diseño
│   │   │   ├── tables.py           Partición y clonado de formato de fila
│   │   │   ├── images.py           Encaje conservando proporción
│   │   │   ├── overflow.py         Estimación con fontTools
│   │   │   ├── preview.py          LibreOffice headless
│   │   │   ├── snapshot.py         Congelación de datos + hash
│   │   │   ├── versioning.py       Linaje, bloqueo, comparación
│   │   │   └── warnings.py         Catálogo de avisos y severidades
│   │   │
│   │   ├── collaboration/          Comentarios, menciones, notificaciones, aprobaciones
│   │   └── audit/
│   │       ├── router.py
│   │       ├── logger.py           Escritura transaccional
│   │       ├── hash_chain.py       Cadena de integridad
│   │       ├── change_history.py
│   │       └── redaction.py        Filtro de datos sensibles
│   │
│   ├── adapters/                   ── Infraestructura externa, tras interfaz ──
│   │   ├── storage/                ObjectStorage (S3/MinIO) + URLs firmadas
│   │   ├── malware/                MalwareScanner (ClamAV)
│   │   ├── mailer/                 Mailer (SMTP)
│   │   ├── maps/                   MapProvider (teselas + geocodificación)
│   │   └── office/                 Conversión a PDF/PNG
│   │
│   ├── workers/                    ── Tareas Celery ──
│   │   ├── photos.py               process_photo, build_derivatives, scan_malware
│   │   ├── reports.py              analyze_template, render_report, render_preview
│   │   ├── exports.py              build_zip, export_xlsx
│   │   ├── prices.py               refresh_price_index
│   │   └── maintenance.py          purge_expired_data, verify_audit_chain, notify
│   │
│   └── migrations/                 ── Alembic ──
│       ├── env.py                  Usuario de migraciones (con DDL)
│       └── versions/
│           ├── 0001_initial_schema.py
│           ├── 0002_rls_policies.py            ⚠ Políticas RLS de todas las tablas
│           ├── 0003_immutability_triggers.py   ⚠ Original y emitido inmutables
│           ├── 0004_capex_recalc_trigger.py
│           ├── 0005_audit_partitions.py
│           ├── 0006_search_vectors.py
│           └── 0007_seed_catalogs.py           Sistemas técnicos, especialidades
│
└── tests/
    ├── conftest.py                 testcontainers: PostgreSQL + MinIO reales
    ├── factories/                  factory_boy, datos ficticios
    ├── fixtures/
    │   ├── permission_matrix.yaml  ⚠ La matriz de §11.3 como datos
    │   ├── capex_golden_cases.yaml Casos dorados verificados a mano
    │   ├── templates/              Corpus T1–T18
    │   ├── images/                 Válidas, corruptas, maliciosas, EXIF variado
    │   └── expected_renders/        Referencias de regresión visual
    ├── unit/
    │   ├── capex/                  ⚠ Mayor densidad de pruebas del proyecto
    │   ├── evidence/naming/        Saneado, extensión, colisiones
    │   ├── reporting/
    │   └── state_machines/
    ├── integration/
    │   ├── test_constraints.py     Restricciones e imposibles
    │   ├── test_immutability.py    Disparadores
    │   ├── test_rls_isolation.py   ⚠ Paramétrica sobre TODAS las tablas
    │   ├── test_audit_transactional.py
    │   └── test_api_*.py
    ├── permissions/
    │   ├── test_matrix.py          Recorre permission_matrix.yaml
    │   └── test_router_coverage.py ⚠ Falla si un endpoint no declara política
    ├── security/
    └── performance/
```

### Reglas de dependencia entre módulos `[REC]`

```mermaid
flowchart TD
    R["routers"] --> S["services"]
    S --> D["dominio puro:<br/>engine · state_machine · naming"]
    S --> RE["repositories"]
    S --> AD["adapters (interfaces)"]
    RE --> M["models"]
    AD -.->|"implementaciones"| EXT["S3 · ClamAV · SMTP · mapas"]

    X1["capex/engine.py"] -.->|"❌ PROHIBIDO"| M
    X2["capex/engine.py"] -.->|"❌ PROHIBIDO"| AD

    style D fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style X1 fill:#fde7e9,stroke:#c62828
    style X2 fill:#fde7e9,stroke:#c62828
```

Cuatro reglas, verificadas con `import-linter` en CI:

1. `engine.py`, `state_machine.py`, `naming.py`, `cascade.py` **no importan** modelos, sesión de base
   de datos ni adaptadores. Son funciones puras.
2. Los módulos de dominio no se importan entre sí: se comunican por servicios de aplicación o eventos.
3. Los `router` no acceden a `models` directamente.
4. `adapters/` define interfaces; las implementaciones concretas solo se instancian en la composición
   de la aplicación.

---

## 23.4. Frontend: `apps/web/`

```
apps/web/
├── package.json · vite.config.ts · tsconfig.json
├── tailwind.config.ts · playwright.config.ts
├── public/
│   ├── manifest.webmanifest        PWA
│   └── icons/
└── src/
    ├── main.tsx · App.tsx · router.tsx
    │
    ├── lib/
    │   ├── api.ts                  Cliente generado + interceptores
    │   ├── auth.ts                 Token en memoria, refresco silencioso
    │   ├── query.ts                TanStack Query: caché, reintentos
    │   ├── offline/
    │   │   ├── db.ts               Dexie / IndexedDB
    │   │   ├── upload-queue.ts     ⚠ Cola persistente con idempotencia
    │   │   └── sync.ts             Reintento con espera creciente
    │   ├── money.ts                Formateo decimal en español
    │   ├── i18n.ts                 Catálogo de traducción
    │   └── a11y.ts
    │
    ├── design-system/              ── Primitivas accesibles (Radix) ──
    │   ├── Button · Input · Select · Dialog · Toast · Table · Tabs
    │   ├── SaveIndicator.tsx       «Guardado 12:04» / «3 pendientes»
    │   ├── SeverityBadge.tsx       Color + etiqueta textual, nunca solo color
    │   └── EmptyState · ErrorState · LoadingState
    │
    ├── features/                   ── Un directorio por pantalla o dominio ──
    │   ├── auth/                   Pantalla 1
    │   ├── dashboard/              Pantalla 2
    │   ├── projects/               Pantallas 3, 4, 5
    │   ├── assets/                 Pantalla 6 (+ MapView con MapLibre)
    │   ├── team/                   Pantalla 7 (+ matriz de cobertura)
    │   ├── photos/                 Pantallas 8, 9
    │   │   ├── PhotoGrid.tsx       Virtualizada
    │   │   ├── PhotoViewer.tsx
    │   │   ├── AnnotationCanvas.tsx  Konva
    │   │   ├── BulkRenameDialog.tsx  ⚠ Previsualización obligatoria
    │   │   ├── CameraCapture.tsx     Flujo móvil
    │   │   └── ContextBar.tsx        ⚠ Contexto persistente
    │   ├── equipment/              Pantalla 10
    │   ├── findings/               Pantallas 11, 12
    │   ├── capex/                  Pantallas 13, 14
    │   │   ├── CapexTable.tsx      TanStack Table
    │   │   ├── CascadePanel.tsx    ⚠ «Cómo se calcula»
    │   │   └── PriceComparator.tsx
    │   ├── reports/                Pantallas 15, 16, 17, 18
    │   │   ├── TemplateStructure.tsx
    │   │   ├── MappingEditor.tsx
    │   │   ├── ReportPreview.tsx
    │   │   ├── WarningsPanel.tsx
    │   │   └── VersionHistory.tsx
    │   ├── admin/                  Pantalla 19
    │   └── audit/
    │
    └── tests/
        ├── unit/
        └── e2e/                    E1–E10 de §19.10
```

---

## 23.5. Ficheros clave

### `.env.example` — sin un solo valor real `[REQ]`

```bash
# ── Aplicación ──────────────────────────────────────────────
APP_ENV=local                      # local | staging | production
APP_SECRET_KEY=                    # generar: openssl rand -hex 32
APP_BASE_URL=http://localhost:5173
API_BASE_URL=http://localhost:8000
LOG_LEVEL=INFO

# ── Base de datos ───────────────────────────────────────────
DATABASE_URL=                      # postgresql+psycopg://usuario:clave@host:5432/base
DATABASE_MIGRATION_URL=            # usuario con DDL, distinto del de aplicación

# ── Redis y colas ───────────────────────────────────────────
REDIS_URL=
CELERY_BROKER_URL=
CELERY_RESULT_BACKEND=

# ── Almacenamiento de objetos (compatible S3) ───────────────
STORAGE_ENDPOINT_URL=
STORAGE_REGION=
STORAGE_BUCKET=
STORAGE_ACCESS_KEY_ID=
STORAGE_SECRET_ACCESS_KEY=
STORAGE_SIGNED_URL_TTL_SECONDS=300
STORAGE_ENABLE_OBJECT_LOCK=true    # WORM sobre originals/ y templates/

# ── Autenticación ───────────────────────────────────────────
JWT_PRIVATE_KEY_PEM=
JWT_PUBLIC_KEY_PEM=
JWT_PREVIOUS_PUBLIC_KEY_PEM=       # permite rotar sin cerrar sesiones
ACCESS_TOKEN_TTL_MINUTES=15
REFRESH_TOKEN_TTL_DAYS=14
FIELD_ENCRYPTION_KEY=              # AES-256-GCM para secretos TOTP

# ── Correo ──────────────────────────────────────────────────
SMTP_HOST= · SMTP_PORT= · SMTP_USER= · SMTP_PASSWORD=
MAIL_FROM=

# ── Antimalware ─────────────────────────────────────────────
CLAMAV_HOST= · CLAMAV_PORT=3310

# ── Conversión de documentos ────────────────────────────────
LIBREOFFICE_BIN=/usr/bin/soffice
PPTX_MAX_UNCOMPRESSED_MB=200
PPTX_RENDER_TIMEOUT_SECONDS=180

# ── Límites de archivo ──────────────────────────────────────
MAX_UPLOAD_MB=50
MAX_BATCH_UPLOAD_MB=500

# ── Mapas (adaptador configurable) ──────────────────────────
MAP_PROVIDER=                      # clave del adaptador registrado
MAP_TILE_URL_TEMPLATE=
MAP_API_KEY=
GEOCODER_PROVIDER=
GEOCODER_API_KEY=

# ── Fuentes de precios ──────────────────────────────────────
# Ninguna fuente externa se habilita por configuración: se habilita
# en la aplicación, y solo tras registrar la revisión de sus condiciones
# de uso por un administrador.
PRICE_SOURCE_HTTP_TIMEOUT_SECONDS=10
PRICE_SOURCE_USER_AGENT=           # identificación honesta + URL de contacto

# ── Observabilidad ──────────────────────────────────────────
OTEL_EXPORTER_OTLP_ENDPOINT=
SENTRY_DSN=

# ── Retención ───────────────────────────────────────────────
DEFAULT_RETENTION_MONTHS=84
TRASH_PURGE_DAYS=30
EXPORT_EXPIRY_DAYS=7
```

### `Makefile`

```makefile
up:            ## Levanta el entorno local completo
	docker compose up -d --build
	$(MAKE) migrate seed
	@echo "API  → http://localhost:8000/docs"
	@echo "Web  → http://localhost:5173"
	@echo "MinIO→ http://localhost:9001"
	@echo "Mail → http://localhost:8025"

migrate:       ## Aplica migraciones
seed:          ## Siembra datos ficticios reproducibles
test:          ## Suite completa
test-unit:     ## Unitarias (~30 s)
test-perms:    ## Matriz de permisos y aislamiento RLS
test-pptx:     ## Corpus T1–T18
lint:          ## ruff · mypy · eslint · tsc · import-linter
security:      ## bandit · semgrep · pip-audit · npm audit · secretos
api-client:    ## Regenera el cliente TypeScript desde OpenAPI
down:          ## Detiene y limpia
```

### `CLAUDE.md` — convenciones que no se negocian

```markdown
# Convenciones del proyecto

## Invariantes que nunca se rompen
1. Nunca se sobrescribe un objeto original (fotografía, documento, plantilla).
2. Nunca se usa `float` para dinero. Solo `Decimal` y `NUMERIC`.
3. Nunca se marca un precio como validado sin un usuario identificado.
4. Nunca se modifica una versión de informe emitida.
5. Nunca se ejecuta `DELETE` desde la aplicación: borrado lógico.
6. Nunca se registra ni se devuelve un secreto, una traza o una ruta interna.
7. Todo endpoint declara su política de autorización.
8. Toda operación crítica escribe auditoría en la misma transacción.

## Reglas de importación
- `capex/engine.py` no importa modelos, sesión ni adaptadores.
- Los módulos de dominio no se importan entre sí.
- Verificado por `import-linter` en CI.

## Convenciones de código
- Nombres de dominio en español (`incidencia`, `activo`) en la interfaz;
  identificadores en inglés en el código (`finding`, `asset`). Documentado en
  `docs/adr/0007-idioma-del-codigo.md`.
- Migraciones: una por cambio lógico, con `downgrade` funcional.
- Mensajes de error de usuario en español, desde el catálogo de i18n.
```

---

## 23.6. Cómo se ejecutará en local

```bash
git clone <repo> && cd tdd-inmobiliaria
cp .env.example .env
# Generar los secretos locales (el fichero indica cómo)
make up
```

Levanta ocho servicios: API, worker `io`, worker `heavy`, PostgreSQL, Redis, MinIO, ClamAV, MailHog y
LibreOffice; aplica migraciones y siembra datos ficticios. Se accede con las credenciales de
demostración que imprime `make seed`.

`[REC]` **`make up` debe funcionar a la primera en una máquina limpia.** Es el indicador más honesto
de la salud de un proyecto: si el entorno local cuesta media tarde de montar, cada persona nueva pierde
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
| Etiqueta en la interfaz | Toda función incompleta muestra un distintivo visible al usuario |
| `docs/PENDIENTE.md` | Índice único de todo lo marcado, generado automáticamente en CI |

Ejemplo del único andamio previsto en el MVP:

```python
class OpenDataApiSource:
    """SCAFFOLD: adaptador de ejemplo, NO FUNCIONAL.

    Existe para demostrar que añadir una fuente de precios no requiere
    tocar el núcleo de CAPEX. No consulta ninguna API real.

    Para convertirlo en un adaptador operativo hacen falta cuatro pasos,
    y los dos primeros no son técnicos:
      1. Identificar la fuente concreta con el cliente (P-03).
      2. Revisar y registrar sus condiciones de uso (rol ADMIN).
      3. Implementar `search` contra su API real.
      4. Probarlo contra la fuente real.

    LIMITATION: ver docs/10-capex-precios.md §16.9.
    """

    def search(self, query: PriceQuery) -> list[PriceCandidate]:
        raise NotImplementedError(
            "Adaptador de ejemplo no implementado. "
            "Use la entrada manual o el catálogo interno."
        )
```

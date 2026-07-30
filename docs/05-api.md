# 10. Diseño de APIs principales

---

## 10.1. Principios de diseño

| Aspecto | Decisión |
|---|---|
| Estilo | **REST sobre JSON**, recursos en plural, versionado por prefijo `/api/v1` |
| Por qué no GraphQL | `[REC]` El consumidor es un único cliente propio. GraphQL añadiría complejidad de autorización por campo, control de coste de consulta y caché sin beneficio proporcional. Descartado, no por moda: por relación coste/valor |
| Contrato | **OpenAPI 3.1 generado automáticamente** desde los esquemas Pydantic. El cliente TypeScript se genera en CI y su desfase rompe la build |
| Autenticación | `Authorization: Bearer <access_token>` (15 min) + refresh token en cookie `HttpOnly`, `Secure`, `SameSite=Lax` |
| Idempotencia | Cabecera `Idempotency-Key` obligatoria en `POST` de creación y de operaciones costosas. **Imprescindible** para el modo de baja conectividad: reintentar una subida no debe duplicar la foto `[REC]` |
| Concurrencia | `If-Match: <etag>` en `PATCH`/`PUT`; `409 Conflict` con el estado del servidor si la versión no coincide |
| Paginación | Basada en cursor (`?cursor=&limit=`, máx. 200). Se evita `offset` porque degrada con volúmenes grandes de fotos |
| Filtrado | Parámetros explícitos, tipados y validados. **Nunca** filtros arbitrarios interpretados dinámicamente |
| Ordenación | `?sort=-created_at,name` sobre lista blanca de campos |
| Campos parciales | `?fields=` sobre lista blanca, para listados de fotos |
| Errores | RFC 9457 (`application/problem+json`) |
| Trazabilidad | `X-Request-Id` propagado a logs, trazas y `audit_log` |
| Límite de tasa | Por usuario y por IP; más estricto en autenticación, búsqueda de precios y generación de informes |
| Trabajos asíncronos | `202 Accepted` + `Location: /api/v1/tasks/{id}` + sondeo o SSE |
| Zona horaria | ISO 8601 con desplazamiento; el servidor persiste en UTC |
| Localización | `Accept-Language` para mensajes de error legibles |

**Formato de error:**

```json
{
  "type": "https://api.tdd.example/errors/validation-error",
  "title": "Datos de entrada no válidos",
  "status": 422,
  "detail": "La cantidad no puede ser negativa.",
  "instance": "/api/v1/capex-items",
  "request_id": "9f3c...",
  "errors": [
    { "field": "quantity", "code": "GREATER_THAN_OR_EQUAL", "message": "Debe ser ≥ 0" }
  ]
}
```

`[REQ]` Los mensajes de error **nunca** incluyen SQL, rutas de fichero, trazas de pila, nombres de
bucket ni datos de cliente. El detalle técnico va al log correlacionado por `request_id`.

---

## 10.2. Autenticación e identidad

| Método | Ruta | Descripción | Notas |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | Email + contraseña (+ TOTP si procede) | Límite estricto; retardo progresivo; respuesta genérica ante credenciales inválidas |
| `POST` | `/api/v1/auth/refresh` | Rota el refresh token | Detección de reutilización ⇒ revocación de toda la familia de tokens `[REC]` |
| `POST` | `/api/v1/auth/logout` | Revoca la sesión | |
| `POST` | `/api/v1/auth/password/forgot` | Solicita recuperación | Responde `202` **siempre**, exista o no el email |
| `POST` | `/api/v1/auth/password/reset` | Aplica nueva contraseña con token | Token de un solo uso, 30 min |
| `POST` | `/api/v1/auth/mfa/enroll` · `/verify` · `/disable` | Gestión de TOTP | |
| `GET` | `/api/v1/me` | Perfil, roles, permisos efectivos, preferencias | El frontend construye su UI desde aquí |
| `PATCH` | `/api/v1/me` | Idioma, zona horaria, notificaciones | |

## 10.3. Organización, usuarios y catálogos

| Método | Ruta | Rol mínimo |
|---|---|---|
| `GET`/`PATCH` | `/api/v1/organization` | `ADMIN` |
| `GET` | `/api/v1/users` | `DIRECTOR_PROYECTO` |
| `POST` | `/api/v1/users/invitations` | `ADMIN` |
| `PATCH` | `/api/v1/users/{id}` | `ADMIN` |
| `POST` | `/api/v1/users/{id}/suspend` · `/reactivate` | `ADMIN` |
| `GET`/`POST`/`PATCH` | `/api/v1/technical-systems` | lectura: todos · escritura: `ADMIN` |
| `GET`/`POST` | `/api/v1/specialties` | idem |
| `GET`/`POST`/`PATCH` | `/api/v1/cost-profiles` | `DIRECTOR_PROYECTO` |
| `GET`/`POST`/`PATCH` | `/api/v1/price-sources` | `ADMIN` |
| `POST` | `/api/v1/price-sources/{id}/review-tos` | `ADMIN` — registra la revisión legal que habilita la activación |

## 10.4. Clientes y proyectos

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/v1/clients?q=&status=&cursor=` | Listado con búsqueda |
| `POST`/`GET`/`PATCH`/`DELETE` | `/api/v1/clients[/{id}]` | `DELETE` = borrado lógico |
| `GET`/`POST`/`PATCH` | `/api/v1/clients/{id}/contacts[/{cid}]` | |
| `GET` | `/api/v1/projects` | **Filtros** `[REQ]`: `q`, `client_id`, `status[]`, `owner_user_id`, `member_user_id`, `asset_city`, `asset_country`, `typology[]`, `created_from`, `created_to`, `due_from`, `due_to`, `archived`, `sort`, `cursor` |
| `POST` | `/api/v1/projects` | Crea en `BORRADOR` |
| `GET` | `/api/v1/projects/{id}` | Ficha con contadores agregados |
| `PATCH` | `/api/v1/projects/{id}` | `If-Match` obligatorio |
| `POST` | `/api/v1/projects/{id}/transitions` | `{ "to_status": "EN_PREPARACION" }` → `422` con la lista de guardas incumplidas si no procede |
| `POST` | `/api/v1/projects/{id}/duplicate` | Cuerpo con qué copiar (§4.8); **nunca** fotos ni incidencias |
| `POST` | `/api/v1/projects/{id}/archive` · `/unarchive` | |
| `DELETE` | `/api/v1/projects/{id}` | Borrado lógico |
| `GET` | `/api/v1/projects/recent` | Panel de recientes, por actividad del usuario |
| `GET` | `/api/v1/projects/{id}/activity?cursor=` | Registro de actividad legible |
| `GET` | `/api/v1/projects/{id}/history?entity=&field=` | Historial de cambios campo a campo |
| `POST` | `/api/v1/projects/{id}/exports` | `{format: "json"\|"xlsx"}` → `202` + tarea |

## 10.5. Activos, ubicaciones y equipo

| Método | Ruta | Descripción |
|---|---|---|
| `GET`/`POST` | `/api/v1/projects/{id}/assets` | |
| `GET`/`PATCH`/`DELETE` | `/api/v1/assets/{id}` | |
| `POST` | `/api/v1/assets/{id}/geocode` | Adaptador `MapProvider`; devuelve candidatos, **no** fija coordenadas automáticamente `[REC]` |
| `PUT` | `/api/v1/assets/{id}/main-photo` | `{photo_id}` |
| `GET`/`POST` | `/api/v1/assets/{id}/locations` | Árbol zona/planta/espacio |
| `PATCH`/`DELETE` | `/api/v1/locations/{id}` | |
| `GET`/`POST` | `/api/v1/projects/{id}/members` | `{user_id, role_code, specialty_ids[], asset_ids[]}` |
| `PATCH`/`DELETE` | `/api/v1/project-members/{id}` | `DELETE` marca `removed_at` |
| `PUT` | `/api/v1/project-members/{id}/assets` | Reasigna activos en bloque |

## 10.6. Fotografías — el flujo crítico

```mermaid
sequenceDiagram
    participant C as Cliente
    participant API
    participant OBJ as Object Storage
    C->>API: POST /photos/upload-intents<br/>[{filename, size, mime, sha256?}]
    Note over API: Valida cuota, tipo declarado,<br/>tamaño; detecta sha256 ya conocido
    API-->>C: [{photo_id, upload_url, expires_at, duplicate_of?}]
    C->>OBJ: PUT upload_url (binario)
    C->>API: POST /photos/commit<br/>[{photo_id, asset_id, system_id, ...}]
    API-->>C: 202 + task_id (EXIF, AV, derivados)
    C->>API: GET /photos?ids=... (o SSE)
    API-->>C: status: LISTA + urls de miniatura
```

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/projects/{id}/photos/upload-intents` | Lote de hasta 50. Devuelve URLs firmadas de subida directa. Si el `sha256` ya existe en el proyecto, lo indica **antes** de subir (ahorra datos móviles) `[REC]` |
| `POST` | `/api/v1/projects/{id}/photos/commit` | Confirma metadatos y encola procesado. Idempotente por `Idempotency-Key` |
| `GET` | `/api/v1/projects/{id}/photos` | Filtros: `asset_id`, `location_node_id`, `technical_system_id`, `equipment_id`, `finding_id`, `category`, `tag[]`, `taken_from/to`, `has_gps`, `include_in_report`, `duplicates_only`, `status`, `trash`, `q`, `sort`, `cursor` |
| `GET` | `/api/v1/photos/{id}` | Metadatos + EXIF + versiones + enlaces |
| `PATCH` | `/api/v1/photos/{id}` | `display_name`, `caption`, `description`, clasificación, `include_in_report`, `report_order`. **`storage_key` y `sha256` no son escribibles: `422`** |
| `POST` | `/api/v1/photos/bulk-rename` | `{photo_ids[], template, dry_run}`. Con `dry_run: true` devuelve la previsualización nombre actual → nuevo y las colisiones detectadas, **sin escribir nada** `[REQ]` |
| `POST` | `/api/v1/photos/bulk-update` | Clasificación y etiquetas en lote |
| `GET` | `/api/v1/photos/{id}/download?version=` | `302` a URL firmada de 5 min. **Auditado** |
| `POST` | `/api/v1/projects/{id}/photos/download-batch` | `{photo_ids[], strip_metadata: true, use_display_names: true}` → `202` + ZIP asíncrono `[REQ]` |
| `GET`/`POST` | `/api/v1/photos/{id}/versions` | Crear versión anotada o editada |
| `POST` | `/api/v1/photos/{id}/versions/{vid}/restore` | Vuelve a una versión anterior |
| `GET`/`POST`/`DELETE` | `/api/v1/photos/{id}/links` | Asocia a activo, zona, sistema, equipo, incidencia, partida, sección |
| `POST`/`DELETE` | `/api/v1/photos/{id}/tags` | |
| `DELETE` | `/api/v1/photos/{id}` | A papelera |
| `POST` | `/api/v1/photos/{id}/restore` | Recuperar de papelera `[REQ]` |
| `GET` | `/api/v1/projects/{id}/photos/duplicates` | Grupos por `sha256` y por `phash` |

**Reglas de la API de fotos** (`[REQ]`):
1. No existe ningún endpoint capaz de sobrescribir el objeto original. Ninguno.
2. `display_name` se recibe **sin extensión**; la extensión la fija el servidor desde el MIME real.
   Es imposible perder la extensión porque el cliente nunca la controla.
3. Toda descarga genera un `audit_log` con actor, recurso, IP y agente de usuario.
4. Una foto sin `asset_id` se acepta con aviso `PHOTO_WITHOUT_ASSET` en la respuesta, no con error.

## 10.7. Inventario, incidencias y recomendaciones

| Método | Ruta | Descripción |
|---|---|---|
| `GET`/`POST` | `/api/v1/projects/{id}/equipment` | Filtros por activo, sistema, criticidad, estado, obsolescencia, vida residual |
| `GET`/`PATCH`/`DELETE` | `/api/v1/equipment/{id}` | |
| `POST` | `/api/v1/projects/{id}/equipment/import` | CSV/XLSX → `202`. Informe de errores por fila, sin abortar el lote `[REC]` |
| `GET`/`POST` | `/api/v1/projects/{id}/inspections` | |
| `GET`/`POST` | `/api/v1/projects/{id}/findings` | Filtros: `asset_id`, `technical_system_id`, `criticality[]`, `action[]`, `time_horizon[]`, `status[]`, `owner_user_id`, `has_capex`, `has_photos`, `q` |
| `GET`/`PATCH`/`DELETE` | `/api/v1/findings/{id}` | |
| `POST` | `/api/v1/findings/{id}/transitions` | Cambio de estado con guardas |
| `GET`/`POST` | `/api/v1/findings/{id}/recommendations` | |
| `POST` | `/api/v1/findings/{id}/from-photo` | Atajo de campo: crea incidencia heredando activo, ubicación y sistema de la foto `[REC]` |
| `GET` | `/api/v1/projects/{id}/risk-matrix` | Agregado probabilidad × consecuencia con recuentos y enlaces |

## 10.8. CAPEX y precios

| Método | Ruta | Descripción |
|---|---|---|
| `GET`/`POST` | `/api/v1/projects/{id}/capex-items` | |
| `GET`/`PATCH`/`DELETE` | `/api/v1/capex-items/{id}` | Cualquier cambio en cantidad, precio o porcentaje devuelve la **cascada completa recalculada** en la respuesta `[REQ]` |
| `POST` | `/api/v1/capex-items/{id}/recalculate` | Fuerza recálculo (p. ej. tras cambiar el perfil de costes) |
| `POST` | `/api/v1/capex/preview-calculation` | **Sin persistir**: entrada de cantidades y porcentajes → desglose paso a paso. Alimenta el panel «cómo se calcula esto» de la interfaz `[REC]` |
| `POST` | `/api/v1/capex-items/bulk-update` | Cambio masivo de porcentajes, año, prioridad |
| `GET` | `/api/v1/projects/{id}/capex/summary?group_by=asset\|system\|priority\|year\|time_horizon\|risk` | **Las siete vistas exigidas** `[REQ]` |
| `GET` | `/api/v1/projects/{id}/capex/scenarios` | Totales bajo / probable / alto |
| `POST` | `/api/v1/projects/{id}/capex/exports` | `{format: "xlsx"\|"csv", group_by, include_traceability}` → `202` |
| `GET`/`POST` | `/api/v1/capex-items/{id}/price-references` | Alta manual de referencia (exige `manual_justification`) |
| `POST` | `/api/v1/capex-items/{id}/price-references/search` | Consulta a adaptadores habilitados. **Devuelve N candidatos sin seleccionar ninguno** `[REQ]` |
| `POST` | `/api/v1/price-references/{id}/validate` | Acto humano explícito: fija `selected_price_reference_id`, `price_status=VALIDADO`, `price_validated_by/at` y audita `PRICE_VALIDATED` |
| `POST` | `/api/v1/price-references/{id}/discard` | Con motivo |
| `POST` | `/api/v1/capex-items/{id}/apply-index` | `{index_code, from_period, to_period, geo_factor}` → devuelve el precio actualizado **con el cálculo explicado**, para revisión antes de aplicar |
| `GET`/`POST` | `/api/v1/price-indices` | Gestión de índices |
| `POST` | `/api/v1/price-catalog/import` | Importa catálogo propio licenciado (CSV/XLSX) |

**Respuesta de búsqueda de precios** — obsérvese que no hay ningún campo `selected`:

```json
{
  "query": { "description": "Sustitución de enfriadora 300 kW", "unit": "ud", "region": "ES-MAD" },
  "results": [
    {
      "price_reference_id": "…", "source": { "code": "CATALOGO_INTERNO", "type": "CATALOGO_INTERNO" },
      "unit_price": "48500.0000", "currency": "EUR", "unit": "ud",
      "retrieved_at": "2026-07-30T09:14:00Z", "price_date": "2025-11-01",
      "geo_scope": "ES-MAD", "includes_tax": false, "includes_installation": true,
      "scope_included": "Suministro, montaje y puesta en marcha",
      "scope_excluded": "Obra civil, desmontaje del equipo existente, grúa",
      "confidence": "MEDIA", "status": "PENDIENTE_VALIDACION",
      "normalization_notes": "Sin conversión de unidad. Índice no aplicado."
    }
  ],
  "warnings": [
    { "code": "NO_OFFICIAL_SOURCE_AVAILABLE",
      "message": "No hay fuentes oficiales habilitadas para esta partida. Introduzca un precio manual justificado." }
  ],
  "requires_human_validation": true
}
```

## 10.9. Plantillas e informes

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/v1/projects/{id}/report-templates` | Sube PPTX (multipart o URL firmada). Guarda **original inmutable** y encola análisis |
| `GET` | `/api/v1/report-templates/{id}` | Metadatos + estado de análisis |
| `GET` | `/api/v1/report-templates/{id}/structure` | Diapositivas, diseños, formas, tablas, imágenes, notas, marcadores y directivas detectadas `[REQ]` |
| `GET` | `/api/v1/report-templates/{id}/placeholders?status=REQUIERE_MAPEO` | Lo que el usuario debe resolver |
| `POST` | `/api/v1/report-templates/{id}/reanalyze` | |
| `GET`/`POST` | `/api/v1/report-templates/{id}/mappings` | |
| `PUT` | `/api/v1/template-mappings/{id}` | Guarda el mapeo reutilizable |
| `POST` | `/api/v1/template-mappings/{id}/clone` | Reutilizar mapeo en otro proyecto `[REQ]` |
| `POST` | `/api/v1/template-mappings/{id}/validate` | Comprueba mapeo contra datos actuales **sin generar**: campos vacíos, tokens sin origen, fotos sin seleccionar |
| `GET`/`POST` | `/api/v1/projects/{id}/reports` | |
| `POST` | `/api/v1/reports/{id}/preview` | `202` → PPTX temporal + PDF/PNG + avisos. **No** crea `ReportVersion` |
| `POST` | `/api/v1/reports/{id}/generate` | `202` → crea `ReportVersion` con snapshot y hash |
| `GET` | `/api/v1/reports/{id}/versions` | Historial `[REQ]` |
| `GET` | `/api/v1/report-versions/{id}` | Detalle + avisos + snapshot |
| `GET` | `/api/v1/report-versions/{id}/download` | URL firmada. Auditado |
| `GET` | `/api/v1/report-versions/{id}/preview` | Miniaturas de diapositivas |
| `GET` | `/api/v1/report-versions/{id}/diff/{other_id}` | `[REC]` Diferencias entre snapshots: qué dato cambió entre v1 y v2. Muy útil en revisión |
| `POST` | `/api/v1/report-versions/{id}/submit-review` | → `EN_REVISION` + notificación |
| `POST` | `/api/v1/report-versions/{id}/approve` · `/reject` | Registra `Approval` |
| `POST` | `/api/v1/report-versions/{id}/issue` | → `EMITIDO` + `is_locked = true`. **Toda modificación posterior devuelve `409` con `code: REPORT_LOCKED`** `[REQ]` |

**Respuesta de previsualización con avisos:**

```json
{
  "task_id": "…", "status": "COMPLETADA",
  "preview_url": "…", "slide_count": 47,
  "warnings": [
    { "severity": "BLOQUEANTE", "code": "UNMAPPED_PLACEHOLDER",
      "slide_index": 12, "token": "{{esg_summary}}",
      "message": "El marcador no tiene origen de datos asignado. Debe mapearlo manualmente." },
    { "severity": "ALTA", "code": "TEXT_OVERFLOW",
      "slide_index": 8, "shape_name": "Cuerpo 2", "estimated_overflow_pct": 34,
      "message": "El texto excede el marco estimado en un 34 %.",
      "note": "Estimación por métricas de fuente; verifique en la previsualización." },
    { "severity": "ALTA", "code": "TABLE_DOES_NOT_FIT",
      "slide_index": 21, "rows": 62, "rows_per_slide": 18,
      "message": "La tabla se dividirá en 4 diapositivas." },
    { "severity": "MEDIA", "code": "MISSING_PHOTO",
      "slide_index": 30, "message": "El activo «Nave B» no tiene fotos seleccionadas." },
    { "severity": "BAJA", "code": "EMPTY_FIELD",
      "token": "{{asset.year_last_refurb}}", "message": "Campo vacío; se omitirá." }
  ],
  "can_generate": false,
  "blocking_count": 1
}
```

`[REQ]` `can_generate: false` cuando hay avisos `BLOQUEANTE`. El endpoint `/generate` los rechaza
con `422`, salvo `force: true` acompañado de un motivo que queda auditado.

## 10.10. Colaboración, búsqueda, tareas y auditoría

| Método | Ruta | Descripción |
|---|---|---|
| `GET`/`POST` | `/api/v1/comments?entity_type=&entity_id=` | Menciones `@usuario` resueltas en el servidor |
| `POST` | `/api/v1/comments/{id}/resolve` | |
| `GET` | `/api/v1/notifications?unread=true` | |
| `POST` | `/api/v1/notifications/{id}/read` · `/read-all` | |
| `GET` | `/api/v1/search?q=&types[]=&project_id=` | Búsqueda global (PostgreSQL FTS español). **Respeta permisos: nunca devuelve lo que el usuario no puede ver** |
| `GET` | `/api/v1/tasks/{id}` | Estado de trabajo asíncrono |
| `GET` | `/api/v1/tasks?project_id=&status=` | |
| `POST` | `/api/v1/tasks/{id}/cancel` | |
| `GET` | `/api/v1/audit-logs?project_id=&actor_user_id=&action=&entity_type=&from=&to=&severity=&cursor=` | Solo `ADMIN` y `DIRECTOR_PROYECTO`. **Solo lectura**: no existe `PATCH` ni `DELETE` `[REQ]` |
| `POST` | `/api/v1/audit-logs/exports` | Exportación CSV firmada, ella misma auditada |
| `GET` | `/api/v1/health` · `/ready` · `/metrics` | Sondas y métricas Prometheus |

## 10.11. Endpoints de soporte al modo de baja conectividad `[REC]`

Preparados en el MVP, explotados a fondo en la fase de offline:

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/v1/projects/{id}/sync-bundle` | Paquete compacto para precargar antes de la visita: activos, ubicaciones, sistemas, equipos, catálogos |
| `POST` | `/api/v1/projects/{id}/sync-batch` | Lote de operaciones creadas en el dispositivo, cada una con su UUID generado en cliente e `Idempotency-Key`. Devuelve resultado por operación y **conflictos detectados**, sin abortar el lote |
| `GET` | `/api/v1/projects/{id}/changes?since=` | Cambios desde una marca temporal, para reconciliar |

**Resolución de conflictos en el MVP** `[LIM]`: última escritura gana **a nivel de campo**, con
registro del valor descartado en `change_history` y aviso al usuario. La fusión asistida se
posterga. Se documenta como limitación conocida, no como comportamiento deseable.

## 10.12. Cabeceras y códigos de estado

| Código | Cuándo |
|---|---|
| `200` / `201` / `204` | Éxito |
| `202` | Trabajo asíncrono aceptado (+ `Location`) |
| `400` | JSON malformado |
| `401` | Sin autenticar o token expirado |
| `403` | Autenticado, sin permiso **dentro de su organización** |
| `404` | No existe **o pertenece a otra organización** (indistinguible a propósito) |
| `409` | Conflicto de versión (`If-Match`), o `REPORT_LOCKED`, o transición de estado no permitida |
| `413` | Archivo por encima del límite |
| `415` | Tipo real de archivo no admitido (verificado con libmagic, no por extensión) |
| `422` | Validación de negocio (guardas de estado, avisos bloqueantes) |
| `429` | Límite de tasa (+ `Retry-After`) |
| `5xx` | Error interno: mensaje genérico + `request_id` |

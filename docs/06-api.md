# 10. Diseño de APIs principales

---

## 10.1. Principios

| Aspecto | Decisión |
|---|---|
| Estilo | **REST sobre JSON**, recursos en plural, versionado `/api/v1` |
| Por qué no GraphQL | `[REC]` Un único cliente propio. GraphQL añadiría autorización por campo, control de coste de consulta y caché sin beneficio proporcional |
| Contrato | **OpenAPI 3.1 generado** desde los esquemas Pydantic. El cliente TypeScript se genera en CI y su desfase rompe la build |
| Autenticación | `Authorization: Bearer` (15 min) + refresh en cookie `HttpOnly`, `Secure`, `SameSite=Lax` |
| Idempotencia | `Idempotency-Key` obligatoria en `POST` de creación y operaciones costosas. **Imprescindible** para el trabajo de campo: reintentar una subida no puede duplicar la foto `[REC]` |
| Concurrencia | `If-Match: <version>` en `PATCH`/`PUT`; `409` con el estado del servidor |
| Paginación | Cursor (`?cursor=&limit=`, máx. 200). Se evita `offset`: degrada con volúmenes grandes de fotos |
| Filtrado | Parámetros explícitos y tipados. **Nunca** filtros arbitrarios interpretados dinámicamente |
| Ordenación | `?sort=-created_at,name` sobre lista blanca |
| Errores | RFC 9457 (`application/problem+json`) |
| Trazabilidad | `X-Request-Id` propagado a logs, trazas y `audit_log` |
| Límite de tasa | Por usuario e IP; más estricto en autenticación, búsqueda de precios y generación de informes |
| Trabajos asíncronos | `202 Accepted` + `Location: /api/v1/tasks/{id}` |

**Formato de error:**

```json
{
  "type": "https://api.tdd.example/errors/validation-error",
  "title": "Datos de entrada no válidos",
  "status": 422,
  "detail": "La zona seleccionada no está disponible para la tipología del activo.",
  "instance": "/api/v1/findings",
  "request_id": "9f3c…",
  "errors": [
    { "field": "zone_id", "code": "ZONE_NOT_ALLOWED_FOR_TYPOLOGY",
      "message": "«Almacén» no aplica a un activo de tipología Comercial.",
      "allowed_values_url": "/api/v1/catalogs/zones?typology_id=…" }
  ]
}
```

`[REQ]` Ningún error incluye SQL, rutas, trazas de pila ni nombres de bucket. El detalle técnico va al
log correlacionado por `request_id`.

---

## 10.2. Autenticación e identidad

| Método | Ruta | Notas |
|---|---|---|
| `POST` | `/auth/login` | Límite estricto; retardo progresivo; respuesta genérica |
| `POST` | `/auth/refresh` | Rotación; reutilización detectada ⇒ revocación de la familia `[REC]` |
| `POST` | `/auth/logout` | Revoca en servidor |
| `POST` | `/auth/password/forgot` | Responde `202` **siempre**, exista o no el email |
| `POST` | `/auth/password/reset` | Token de un solo uso, 30 min |
| `POST` | `/auth/mfa/enroll` · `/verify` · `/disable` | TOTP |
| `GET`/`PATCH` | `/me` | Perfil, roles, **permisos efectivos**, preferencias |

---

## 10.3. Catálogos

Un grupo propio, porque en esta aplicación los catálogos son estructura, no configuración menor.

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/catalogs/asset-typologies` | Con los indicadores de qué campos muestra cada una |
| `GET` | `/catalogs/zones?typology_id=` | **Zonas filtradas por tipología** `[REQ]` §3.3.2. Sin el parámetro, devuelve todas con su matriz de disponibilidad |
| `GET` | `/catalogs/capex-codes?level=&parent_id=&q=` | Árbol de códigos. Con `q`, búsqueda por texto sobre todo el árbol |
| `GET` | `/catalogs/capex-codes/tree` | Árbol completo en una llamada, para precargar el selector en cliente |
| `GET` | `/catalogs/risk-levels` | **Incluye la definición íntegra de cada grado** `[REQ]` |
| `GET` | `/catalogs/capex-concepts` · `/time-horizons` · `/technical-systems` · `/specialties` · `/doc-request-categories` | |
| `POST`/`PATCH` | `/catalogs/{tipo}` | Solo `ADMIN`. Las filas del sistema no son editables |
| `POST` | `/catalogs/capex-codes/{id}/deprecate` | Retira un código sin borrarlo: deja de ofrecerse, sigue resolviéndose en informes antiguos |
| `GET` | `/catalogs/version` | Huella del catálogo, para que el cliente sepa si debe refrescar su caché `[REC]` |

`[REC]` `GET /catalogs/zones?typology_id=` es el endpoint que hace posible el desplegable dependiente
sin lógica duplicada en el frontend. La regla de qué zona aplica a qué tipología vive en un solo sitio.

---

## 10.4. Clientes y proyectos

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/clients?q=&status=&cursor=` | |
| `POST`/`GET`/`PATCH`/`DELETE` | `/clients[/{id}]` · `/clients/{id}/contacts` | `DELETE` = borrado lógico |
| `GET` | `/projects` | **Filtros** `[REQ]`: `q`, `client_id`, `status[]`, `owner_user_id`, `member_user_id`, `asset_city`, `asset_country`, `typology_id[]`, `phase_code`, `phase_status`, `created_from/to`, `due_from/to`, `archived`, `sort`, `cursor` |
| `POST` | `/projects` | Crea en `BORRADOR`. **El cuerpo incluye `applicable_phases[]`** `[REQ]` §3.1.5 |
| `GET` | `/projects/{id}` | Ficha con contadores y estado de fases |
| `PATCH` | `/projects/{id}` | `If-Match` obligatorio |
| `POST` | `/projects/{id}/transitions` | `{to_status}` → `422` con las guardas incumplidas si no procede |
| `POST` | `/projects/{id}/duplicate` | Cuerpo con qué copiar (§4.6); **nunca** fotos ni importes |
| `POST` | `/projects/{id}/archive` · `/unarchive` | |
| `GET` | `/projects/recent` | Por actividad del usuario, no solo por fecha |
| `GET` | `/projects/{id}/activity?cursor=` | Registro de actividad legible |
| `GET` | `/projects/{id}/history?entity=&field=` | Historial de cambios campo a campo |
| `POST` | `/projects/{id}/exports` | `{format:"xlsx"\|"csv"}` → `202` `[REQ]` §3.1.6 |

**Alta de proyecto con fases:**

```json
POST /api/v1/projects
{
  "name": "TDD Cartera Logística Norte",
  "internal_code": "2026-014",
  "dd_type": "TECNICA",
  "currency": "EUR",
  "report_due_date": "2026-09-30",
  "applicable_phases": [
    { "code": "SOLICITUD_DOCUMENTACION", "owner_user_id": "…" },
    { "code": "VDR" },
    { "code": "VISITA" },
    { "code": "RED_FLAG_CAPEX" },
    { "code": "FULL_REPORT" },
    { "code": "PRESENTACION_CLIENTE" }
  ]
}
```

Las fases no incluidas quedan como `NO_APLICA` y pueden activarse después. `[SUP]` S-07

---

## 10.5. Fases del proceso

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/projects/{id}/phases` | Todas, con estado, responsable y progreso |
| `PATCH` | `/project-phases/{id}` | Responsable, fechas, notas, estado. **`422` si la fase tiene estado derivado** |
| `POST` | `/project-phases/{id}/activate` · `/deactivate` | Marca o desmarca la fase como aplicable |
| `GET` | `/projects/{id}/phases/summary` | Vista compacta para la ficha y el listado |

### Solicitud de documentación

| Método | Ruta | Descripción |
|---|---|---|
| `GET`/`POST` | `/project-phases/{id}/doc-requests` | Checklist. Al crear la fase se siembra con las 5 categorías de §3.1.5 |
| `PATCH` | `/doc-requests/{id}` | Estado, fechas, motivo. `422` si `NO_DISPONIBLE` sin motivo |
| `POST` | `/doc-requests/{id}/documents` | Adjunta documentos; clasifica automáticamente por categoría |
| `POST` | `/project-phases/{id}/doc-requests/export` | Genera el XLSX de solicitud para enviar al cliente `[REC]` |
| `GET` | `/projects/{id}/report-limitations` | Líneas en `NO_DISPONIBLE` o `PARCIAL`, listas para volcar al informe `[REC]` |

### Virtual Data Room

| Método | Ruta | Descripción |
|---|---|---|
| `GET`/`POST`/`PATCH` | `/project-phases/{id}/vdr-links` | Enlace externo, proveedor, notas, caducidad |

`[REC]` No hay endpoint para almacenar credenciales del VDR: no se guardan.

### Visitas

| Método | Ruta | Descripción |
|---|---|---|
| `GET`/`POST` | `/projects/{id}/visits` | Una por activo, varias posibles |
| `PATCH` | `/visits/{id}` | Estado (`PENDIENTE_DEFINIR`/`AGENDADO`/`VISITADO`), fechas, limitaciones de acceso |
| `POST` | `/visits/{id}/start` · `/complete` | Atajos de campo: fijan `started_at`/`actual_date` |

### Q&A

| Método | Ruta | Descripción |
|---|---|---|
| `GET`/`POST` | `/project-phases/{id}/qa-rounds` | Rondas numeradas |
| `POST` | `/qa-rounds/{id}/documents` | Sube el XLSX; versiona sobre el anterior |
| `PATCH` | `/qa-rounds/{id}` | Estado y fechas |

### Presentación y defensa

| Método | Ruta | Descripción |
|---|---|---|
| `GET`/`POST`/`PATCH` | `/project-phases/{id}/events` | Fecha, contraparte, asistentes, versión de informe presentada, resultado |

---

## 10.6. Activos, ubicaciones y equipo

| Método | Ruta | Descripción |
|---|---|---|
| `GET`/`POST` | `/projects/{id}/assets` | |
| `GET`/`PATCH`/`DELETE` | `/assets/{id}` | |
| `POST` | `/assets/{id}/typology` | **Cambio de tipología con previsualización de impacto**: devuelve las líneas cuya zona dejaría de ser válida antes de aplicar `[REC]` |
| `POST` | `/assets/{id}/geocode` | Devuelve candidatos; **no fija coordenadas automáticamente** |
| `PUT` | `/assets/{id}/main-photo` | |
| `GET`/`POST` | `/assets/{id}/locations` | Árbol zona/planta/espacio |
| `GET`/`POST` | `/projects/{id}/members` | `{user_id, role_code, specialty_ids[], asset_ids[]}` |
| `PATCH`/`DELETE` | `/project-members/{id}` | `DELETE` marca `removed_at` |
| `GET` | `/projects/{id}/coverage` | Matriz especialidad × activo, para ver qué queda sin cubrir `[REC]` |

---

## 10.7. Fotografías

```mermaid
sequenceDiagram
    participant C as Cliente
    participant API
    participant OBJ as Object Storage
    C->>API: POST /photos/upload-intents<br/>[{filename, size, mime, sha256?}]
    Note over API: Valida cuota, tipo, tamaño;<br/>detecta sha256 ya conocido
    API-->>C: [{photo_id, upload_url, expires_at, duplicate_of?}]
    C->>OBJ: PUT upload_url (binario)
    C->>API: POST /photos/commit [{photo_id, asset_id, zone_id, …}]
    API-->>C: 202 + task_id (EXIF, antivirus, derivados)
```

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/projects/{id}/photos/upload-intents` | Lote ≤ 50. Si el `sha256` ya existe, lo indica **antes** de subir (ahorra datos móviles) `[REC]` |
| `POST` | `/projects/{id}/photos/commit` | Confirma metadatos y encola. Idempotente |
| `GET` | `/projects/{id}/photos` | Filtros: `asset_id`, `zone_id`, `location_node_id`, `technical_system_id`, `finding_id`, `capex_item_id`, `category`, `tag[]`, `taken_from/to`, `has_gps`, `include_in_report`, `duplicates_only`, `status`, `trash`, `q` |
| `GET`/`PATCH` | `/photos/{id}` | **`storage_key` y `sha256` no son escribibles: `422`** |
| `POST` | `/photos/bulk-rename` | `{photo_ids[], template, dry_run}`. Con `dry_run` devuelve la previsualización y las colisiones **sin escribir nada** `[REQ]` |
| `POST` | `/photos/bulk-update` | Clasificación y etiquetas en lote |
| `GET` | `/photos/{id}/download?version=` | `302` a URL firmada de 5 min. **Auditado** |
| `POST` | `/projects/{id}/photos/download-batch` | `{photo_ids[], strip_metadata, use_display_names}` → `202` ZIP `[REQ]` |
| `GET`/`POST` | `/photos/{id}/versions` · `POST /versions/{vid}/restore` | |
| `GET`/`POST`/`DELETE` | `/photos/{id}/links` | Asociación múltiple `[REQ]` |
| `DELETE`/`POST` | `/photos/{id}` · `/photos/{id}/restore` | Papelera y recuperación |
| `GET` | `/projects/{id}/photos/duplicates` | Grupos por `sha256` y por `phash` |

**Reglas** `[REQ]`:
1. **No existe ningún endpoint capaz de sobrescribir el objeto original.**
2. `display_name` se recibe **sin extensión**; la fija el servidor desde el MIME real.
3. Toda descarga genera `audit_log`.
4. Una foto sin `asset_id` se acepta **con aviso**, no con error.

---

## 10.8. Hallazgos y CAPEX

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/projects/{id}/findings` | **Crea hallazgo y línea de CAPEX en una operación** (1:1 por defecto) `[REC]` |
| `GET` | `/projects/{id}/findings` | Filtros: `asset_id`, `zone_id`, `capex_code_id` (con subárbol), `risk_level_id[]`, `capex_concept_id[]`, `tenant_recoverable`, `status[]`, `owner_user_id`, `has_photos`, `q` |
| `GET`/`PATCH`/`DELETE` | `/findings/{id}` | |
| `POST` | `/findings/{id}/transitions` | Cambio de estado con guardas |
| `POST` | `/findings/from-photo` | **Atajo de campo**: hereda activo, zona y sistema de la foto `[REC]` |
| `GET`/`POST` | `/findings/{id}/recommendations` | |
| `GET`/`POST` | `/projects/{id}/capex-items` | |
| `GET`/`PATCH`/`DELETE` | `/capex-items/{id}` | Cualquier cambio devuelve **los totales recalculados** `[REQ]` |
| `POST` | `/capex-items/bulk-update` | Cambio masivo de porcentajes, año, prioridad, recuperabilidad |
| `POST` | `/capex/preview-calculation` | **Sin persistir**: entradas → desglose paso a paso. Alimenta el panel «cómo se calcula» `[REC]` |
| `GET` | `/projects/{id}/capex/summary?group_by=` | `asset` · `capex_code` · `zone` · `risk` · `concept` · `horizon` · `year` · `priority` · `tenant_recoverable` `[REQ]` |
| `GET` | `/projects/{id}/capex/scenarios` | Totales bajo / probable / alto |
| `POST` | `/projects/{id}/capex/exports` | `{format:"xlsx"\|"csv", group_by, include_traceability}` → `202` `[REQ]` |

**Cuerpo de creación de una línea** — refleja la fila que rellena el consultor:

```json
POST /api/v1/projects/{id}/findings
{
  "asset_id": "…",
  "capex_code_id": "…",             // HC.H08.01 Producción de climatización
  "zone_id": "…",                   // validada contra la tipología del activo
  "title": "Corrosión en enfriadora",
  "description": "Corrosión generalizada en carrocería y batería…",
  "comments": "Se recomienda sustitución completa.",
  "risk_level_id": "…",             // 03 Alto
  "capex_concept_id": "…",          // Vida útil
  "tenant_recoverable": "NO",
  "amounts": {
    "short": "48500.00", "mid": "0", "long": "0",
    "improvements": "0", "other": "0"
  },
  "measurement": {                   // opcional [SUP] S-10
    "unit": "ud", "quantity": "1", "unit_price": "48500.00"
  }
}
```

Respuesta: el hallazgo, la línea de CAPEX creada, los totales recalculados y los avisos
(`PRICE_NOT_VALIDATED`, `ZONE_REVIEW_REQUIRED`…).

---

## 10.9. Precios

| Método | Ruta | Descripción |
|---|---|---|
| `GET`/`POST` | `/capex-items/{id}/price-references` | Alta manual (exige `manual_justification`) |
| `POST` | `/capex-items/{id}/price-references/search` | Consulta a adaptadores habilitados. **Devuelve N candidatos sin seleccionar ninguno** `[REQ]` |
| `POST` | `/price-references/{id}/validate` | Acto humano explícito. Audita `PRICE_VALIDATED` |
| `POST` | `/price-references/{id}/discard` | Con motivo |
| `POST` | `/capex-items/{id}/apply-index` | Devuelve el precio actualizado **con el cálculo explicado**, para revisar antes de aplicar |
| `GET`/`POST`/`PATCH` | `/price-sources` | Solo `ADMIN` |
| `POST` | `/price-sources/{id}/review-tos` | Registra la revisión legal que habilita la activación `[REQ]` |
| `POST` | `/price-catalog/import` | Importa catálogo propio licenciado (XLSX/CSV) → `202` |
| `GET`/`POST` | `/price-indices` | |

**Respuesta de búsqueda** — obsérvese que no hay ningún campo `selected` ni `recommended`:

```json
{
  "query": { "description": "Sustitución de enfriadora 300 kW", "unit": "ud", "region": "ES-MAD" },
  "results": [
    {
      "price_reference_id": "…",
      "source": { "code": "CATALOGO_INTERNO", "type": "CATALOGO_INTERNO" },
      "unit_price": "48500.0000", "currency": "EUR", "unit": "ud",
      "retrieved_at": "2026-07-30T09:14:00Z", "price_date": "2025-11-01",
      "geo_scope": "ES-MAD",
      "includes_tax": false, "includes_installation": true,
      "scope_included": "Suministro, montaje y puesta en marcha",
      "scope_excluded": "Obra civil, desmontaje del equipo existente, grúa",
      "confidence": "MEDIA", "status": "PENDIENTE_VALIDACION",
      "normalization_notes": "Sin conversión de unidad. Índice no aplicado."
    }
  ],
  "skipped_sources": [
    { "code": "PRECIO_CENTRO", "reason": "SOURCE_NOT_ENABLED",
      "message": "Fuente no habilitada: condiciones de uso pendientes de revisión." }
  ],
  "warnings": [
    { "code": "NO_OFFICIAL_SOURCE_AVAILABLE",
      "message": "No hay fuentes oficiales habilitadas. Introduzca un precio manual justificado." }
  ],
  "requires_human_validation": true
}
```

`[REC]` `skipped_sources` es deliberado: el consultor debe saber **qué no se ha consultado y por qué**.
Una lista de resultados sin esa información sugiere que se ha buscado en todas partes.

---

## 10.10. Plantillas e informes

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/projects/{id}/report-templates` | Sube PPTX; guarda original inmutable; encola análisis |
| `GET` | `/report-templates/{id}/structure` | Diapositivas, diseños, formas, tablas, notas, marcadores, directivas `[REQ]` |
| `GET` | `/report-templates/{id}/placeholders?status=REQUIERE_MAPEO` | Lo que el usuario debe resolver |
| `POST` | `/report-templates/{id}/reanalyze` | |
| `GET`/`POST`/`PUT` | `/report-templates/{id}/mappings` · `/template-mappings/{id}` | |
| `POST` | `/template-mappings/{id}/clone` | Reutilizar en otro proyecto `[REQ]` |
| `POST` | `/template-mappings/{id}/validate` | Comprueba el mapeo **sin generar** |
| `GET`/`POST` | `/projects/{id}/reports` | `report_type`: `RED_FLAG` o `FULL_REPORT` |
| `POST` | `/reports/{id}/preview` | `202` → PPTX temporal + PDF/PNG + avisos. **No** crea versión |
| `POST` | `/reports/{id}/generate` | `202` → crea `ReportVersion` con snapshot y hash |
| `GET` | `/reports/{id}/versions` · `/report-versions/{id}` | |
| `GET` | `/report-versions/{id}/download` · `/preview` | URL firmada. Auditado |
| `GET` | `/report-versions/{id}/diff/{other_id}` | **Qué dato cambió entre v1 y v2** `[REC]` |
| `POST` | `/report-versions/{id}/submit-review` · `/approve` · `/reject` · `/issue` | `issue` → bloqueo. Toda modificación posterior: `409 REPORT_LOCKED` `[REQ]` |

**Respuesta de previsualización:**

```json
{
  "task_id": "…", "status": "COMPLETADA", "preview_url": "…", "slide_count": 47,
  "warnings": [
    { "severity": "BLOQUEANTE", "code": "UNMAPPED_PLACEHOLDER",
      "slide_index": 12, "token": "{{esg_summary}}",
      "message": "El marcador no tiene origen de datos asignado." },
    { "severity": "ALTA", "code": "TEXT_OVERFLOW",
      "slide_index": 8, "shape_name": "Cuerpo 2", "estimated_overflow_pct": 34,
      "message": "El texto excede el marco estimado en un 34 %.",
      "note": "Estimación por métricas de fuente; verifique en la previsualización." },
    { "severity": "ALTA", "code": "TABLE_DOES_NOT_FIT",
      "slide_index": 21, "rows": 62, "rows_per_slide": 18 },
    { "severity": "MEDIA", "code": "UNVALIDATED_PRICES", "count": 12,
      "message": "12 líneas con precio sin validar por importe de 248.000 €." }
  ],
  "can_generate": false,
  "blocking_count": 1
}
```

---

## 10.11. Colaboración, búsqueda, tareas y auditoría

| Método | Ruta | Descripción |
|---|---|---|
| `GET`/`POST` | `/comments?entity_type=&entity_id=` | Menciones resueltas en el servidor |
| `GET`/`POST` | `/notifications` · `/notifications/{id}/read` | |
| `GET` | `/search?q=&types[]=&project_id=` | Global (FTS español). **Respeta permisos** |
| `GET` | `/tasks/{id}` · `/tasks?project_id=` · `POST /tasks/{id}/cancel` | Progreso de trabajos |
| `GET` | `/audit-logs?project_id=&actor_user_id=&action=&from=&to=&severity=` | Solo `ADMIN` y `DIRECTOR_PROYECTO`. **Solo lectura** `[REQ]` |
| `POST` | `/audit-logs/exports` | La propia exportación queda auditada |
| `GET` | `/health` · `/ready` · `/metrics` | |

---

## 10.12. Soporte al modo de baja conectividad `[REC]`

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/projects/{id}/sync-bundle` | Paquete de precarga antes de la visita: activos, zonas aplicables, árbol de códigos, riesgos, conceptos, ubicaciones |
| `POST` | `/projects/{id}/sync-batch` | Lote de operaciones con UUID de cliente e `Idempotency-Key`. Devuelve resultado por operación y conflictos, **sin abortar el lote** |
| `GET` | `/projects/{id}/changes?since=` | Reconciliación |

`[LIM]` Resolución de conflictos en el MVP: última escritura gana **a nivel de campo**, con el valor
descartado registrado en `change_history` y aviso al usuario. La fusión asistida se pospone. Se
documenta como limitación conocida, no como comportamiento deseable.

---

## 10.13. Códigos de estado

| Código | Cuándo |
|---|---|
| `200`/`201`/`204` | Éxito |
| `202` | Trabajo asíncrono aceptado |
| `401` | Sin autenticar o token expirado |
| `403` | Autenticado, sin permiso **dentro de su organización** |
| `404` | No existe **o pertenece a otra organización** (indistinguible a propósito) |
| `409` | Conflicto de versión, `REPORT_LOCKED`, o transición no permitida |
| `413` | Archivo por encima del límite |
| `415` | Tipo real no admitido (verificado con `libmagic`, no por extensión) |
| `422` | Validación de negocio: guardas de estado, zona no válida para la tipología, código no seleccionable, avisos bloqueantes |
| `429` | Límite de tasa (+ `Retry-After`) |
| `5xx` | Mensaje genérico + `request_id` |

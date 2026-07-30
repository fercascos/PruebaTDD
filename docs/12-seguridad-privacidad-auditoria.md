# 18. Seguridad, privacidad y auditoría

---

## 18.1. Modelo de amenazas resumido

Antes de las medidas, qué se protege y de quién. `[REC]`

| Activo | Amenaza principal | Consecuencia si falla |
|---|---|---|
| Fotografías y documentos de un edificio | Acceso de otra organización o de un tercero mediante URL adivinada | Fuga de información confidencial de un cliente. Daño reputacional grave y posible incumplimiento contractual |
| Datos de contacto de clientes | Acceso indebido; exfiltración | Incumplimiento del RGPD |
| Informe emitido | Alteración posterior | Pérdida de valor probatorio del entregable |
| Precios y CAPEX | Manipulación no trazable | Un informe indefendible ante el cliente |
| Registro de auditoría | Borrado o alteración | Imposibilidad de demostrar lo ocurrido |
| Plantilla PPTX corporativa | Sobrescritura o pérdida | Pérdida de un activo de la consultora |
| Credenciales | Robo, reutilización, fuerza bruta | Acceso completo suplantando a un usuario |
| Infraestructura | Subida de archivo malicioso; ataque XML | Ejecución de código en el servidor |

**Actores considerados:** usuario legítimo con exceso de curiosidad (el más frecuente); usuario de
otra organización; atacante externo no autenticado; atacante con una cuenta válida de baja
privilegio; y **administrador propio**, que es el actor que más sistemas olvidan modelar.

---

## 18.2. Cifrado

| Ámbito | Medida | Nota |
|---|---|---|
| **En tránsito** | TLS 1.3 obligatorio (1.2 como mínimo). HSTS con `max-age` de un año e `includeSubDomains`. Redirección de HTTP a HTTPS. Sin cifrados obsoletos | `[REQ]` |
| **En reposo · base de datos** | Cifrado de volumen del proveedor; backups cifrados con clave gestionada | `[REQ]` |
| **En reposo · objetos** | Cifrado del lado del servidor (SSE) en el almacenamiento | `[REQ]` |
| **En reposo · campos sensibles** | Cifrado adicional a nivel de aplicación (AES-256-GCM) para el secreto TOTP y los tokens de integración. Clave en el gestor de secretos, rotable | `[REC]` La capa de volumen no protege frente a un volcado de base de datos |
| **Contraseñas** | **Argon2id**, parámetros según las recomendaciones actuales de OWASP, con margen de coste revisable | `[REQ]` No SHA, no bcrypt heredado |
| **Interno entre servicios** | Red privada; TLS entre servicios si el proveedor no garantiza aislamiento | `[REC]` |
| **Hashes de integridad** | SHA-256 sobre originales, PPTX generados y snapshots de datos | `[REQ]` |

---

## 18.3. Autenticación

| Control | Decisión |
|---|---|
| Contraseñas | Mínimo 12 caracteres; comprobación contra listas de contraseñas comprometidas; sin reglas de composición absurdas (favorecen contraseñas peores) `[REC]` |
| MFA | TOTP opcional por usuario, exigible por política de organización. Códigos de recuperación de un solo uso |
| Bloqueo | Retardo progresivo tras 3 intentos; bloqueo temporal tras 8; aviso por correo al usuario legítimo `[SUP]` |
| Enumeración de usuarios | Mensaje de error idéntico ante usuario inexistente y contraseña incorrecta; tiempo de respuesta uniformado; recuperación de contraseña responde `202` siempre |
| Tokens de acceso | JWT de 15 min, firmado (algoritmo asimétrico, clave rotable). **En memoria del cliente, nunca en `localStorage`** `[REC]` |
| Tokens de refresco | Opacos, en cookie `HttpOnly`, `Secure`, `SameSite=Lax`, con rotación en cada uso. **Detección de reutilización ⇒ revocación de toda la familia de tokens** `[REC]` Es la defensa efectiva ante un token robado |
| Cierre de sesión | Revocación del refresco en servidor, no solo borrado en cliente |
| Recuperación de contraseña | Token de un solo uso, 30 min, ligado al usuario, invalidado al usarse o al cambiar la contraseña. Cambiar la contraseña **revoca todas las sesiones** |
| Sesiones activas | El usuario puede ver y cerrar sus sesiones desde su perfil `[REC]` |
| SSO | Interfaz `IdentityProvider` preparada; OIDC en fase posterior (P-06) |

---

## 18.4. Autorización

Cuatro capas, detalladas en [`06-roles-permisos.md`](./06-roles-permisos.md):

1. **Row Level Security** en PostgreSQL por `organization_id`. El usuario de aplicación **no tiene
   `BYPASSRLS`**. Un `WHERE` olvidado deja de ser una fuga entre clientes.
2. **Pertenencia al proyecto** verificada en el servidor.
3. **Permiso de acción** declarado como dependencia en cada endpoint. Una prueba recorre el router y
   **falla si algún endpoint no declara política**. `[REC]`
4. **Reglas de estado**: informe bloqueado, proyecto archivado, guardas de transición.

`[REQ]` «Implementa autorización en backend, no solo ocultación visual.» Se cumple literalmente: la
interfaz oculta lo que el servidor ya deniega, y la suite de pruebas verifica cada denegación
llamando directamente a la API sin pasar por la interfaz.

**Principio de mínimo privilegio aplicado a la infraestructura** `[REC]`:

| Componente | Privilegios |
|---|---|
| Usuario de aplicación en PostgreSQL | `SELECT`/`INSERT`/`UPDATE` en tablas de negocio; **solo `INSERT` y `SELECT` en `audit_log`**; sin `DDL`; sin `BYPASSRLS` |
| Usuario de migraciones | `DDL`, usado solo por el pipeline, nunca por la aplicación |
| Worker de PPTX y LibreOffice | **Sin salida a Internet**; acceso solo a las claves de objeto que recibe |
| API | Sin acceso al sistema de archivos del host más allá de un directorio temporal |
| Contenedores | Usuario no root, sistema de archivos raíz de solo lectura, sin capacidades añadidas |

---

## 18.5. Protección de archivos

| Control | Implementación | Requisito |
|---|---|---|
| Validación del **tipo real**, no de la extensión | `libmagic` sobre los primeros bytes; se compara con el MIME declarado y con una lista blanca. Discrepancia ⇒ `415` | `[REQ]` |
| Antivirus | ClamAV en contenedor propio, antes de que el archivo sea accesible. Positivo ⇒ `CUARENTENA` + alerta | `[REQ]` |
| Límites de tamaño | 50 MB por archivo, 500 MB por lote, cuota por proyecto y organización configurable | `[REQ]` |
| Lista blanca de extensiones | Imágenes: jpg, jpeg, png, webp, heic, heif. Documentos: pdf, docx, xlsx, dwg. Plantillas: pptx. **Nada más** | `[REC]` |
| Bloqueo de ejecutables y macros | Rechazo de `.exe`, `.dll`, `.js`, `.sh`, `.bat`, `.pptm`, `.docm`, `.xlsm`; se comprueba también el contenido del paquete OOXML | `[REQ]` |
| Bombas de descompresión | Límite de tamaño descomprimido, de número de entradas y de ratio de compresión, comprobados antes de descomprimir | `[REC]` |
| Ataques XML | Entidades externas y DTD deshabilitadas en todo análisis XML | `[REC]` |
| Nombres de archivo | Nunca se usan para construir rutas. La ruta es `{org}/{project}/originals/{uuid}.{ext}`; el nombre del usuario vive solo en la base de datos | `[REC]` Elimina de raíz el recorrido de rutas |
| Servido de archivos | **Nunca** desde la aplicación. Siempre URL firmada, un recurso, 5 minutos, generada tras verificar autorización | `[REQ]` |
| Prevención de XSS por archivo | Los objetos se sirven desde un dominio distinto al de la aplicación, con `Content-Disposition: attachment` y `X-Content-Type-Options: nosniff` para los tipos no visualizables | `[REC]` Un SVG malicioso servido desde el dominio principal sería XSS almacenado |

---

## 18.6. Vulnerabilidades web

| Riesgo | Medida |
|---|---|
| **Inyección SQL** | ORM con consultas parametrizadas. Prohibición de SQL construido por concatenación, verificada por análisis estático (`bandit`, `semgrep`) en CI `[REQ]` |
| **XSS** | React escapa por defecto; `dangerouslySetInnerHTML` prohibido por regla de lint; sanitización en servidor de todo texto libre; **Content-Security-Policy** estricta sin `unsafe-inline` `[REQ]` |
| **CSRF** | Tokens de acceso en cabecera `Authorization` (no en cookie), lo que elimina el vector principal; el refresco usa cookie `SameSite=Lax` y su endpoint exige cabecera personalizada. CORS restringido a orígenes conocidos `[REQ]` |
| **Acceso directo a objetos** (IDOR) | UUID no adivinables + verificación de autorización en cada acceso + RLS. **`404` en lugar de `403`** para no confirmar existencia `[REQ]` |
| **SSRF** | Ninguna URL suministrada por el usuario se solicita desde el servidor. Los adaptadores de precios solo llaman a URLs de una lista blanca por fuente. Los workers que procesan ficheros no tienen red saliente `[REC]` |
| **Redirecciones abiertas** | Solo rutas relativas internas |
| **Fijación de sesión** | Rotación de token en cada autenticación y en cada refresco |
| **Denegación de servicio** | Límite de tasa por usuario e IP, más estricto en autenticación, búsqueda de precios y generación de informes; límites de recursos en workers; tamaño máximo de cuerpo de petición |
| **Deserialización insegura** | Solo JSON con esquemas Pydantic estrictos. **Nunca `pickle`** para datos de usuario |
| **Cabeceras de seguridad** | CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` restrictiva |
| **Dependencias** | `pip-audit` y `npm audit` en CI, con fallo de build ante vulnerabilidades altas o críticas; actualización automatizada de dependencias |
| **Secretos en el repositorio** | Escaneo de secretos en CI y en un hook de pre-commit; `.env` en `.gitignore`; **solo `.env.example` sin valores reales** `[REQ]` |

---

## 18.7. Gestión de secretos

| Regla | Detalle |
|---|---|
| Nunca en el código | Sin credenciales, claves ni cadenas de conexión en el repositorio `[REQ]` |
| Nunca en la imagen | Se inyectan como variables de entorno en tiempo de ejecución, no en el `Dockerfile` |
| Origen | Gestor de secretos del proveedor o HashiCorp Vault |
| Rotación | Documentada y ensayada para: credenciales de base de datos, claves de firma de JWT, claves de acceso al almacenamiento, clave de cifrado de campos. La clave de firma admite **dos claves activas** para rotar sin cerrar sesiones `[REC]` |
| Nunca en logs | Filtro que redacta valores sensibles por nombre de clave antes de escribir cualquier log |
| Nunca en errores | Ningún mensaje de error incluye cadenas de conexión, rutas ni nombres de bucket |
| `.env.example` | Todas las variables documentadas, **sin un solo valor real** `[REQ]` |

---

## 18.8. Privacidad y RGPD

`[REQ]` «Cumplimiento del RGPD en los aspectos aplicables.»

### Datos personales tratados

| Categoría | Datos | Base jurídica probable `[PDV]` |
|---|---|---|
| Usuarios de la plataforma | Nombre, correo, teléfono, cargo, registros de acceso | Ejecución de contrato / interés legítimo |
| Contactos de cliente | Nombre, cargo, correo, teléfono | Interés legítimo (contacto profesional) |
| Contenido de fotografías | Puede captar personas presentes en el edificio | Interés legítimo, **con minimización** |
| Metadatos EXIF | GPS, dispositivo | Interés legítimo |

`[PDV]` La determinación de bases jurídicas, el registro de actividades de tratamiento y el análisis
de si procede una evaluación de impacto son decisiones del responsable del tratamiento. Aquí se
aportan los **medios técnicos** para cumplir, no el asesoramiento jurídico.

### Principios aplicados por diseño

| Principio | Implementación técnica |
|---|---|
| **Minimización** | No se piden datos personales que el negocio no necesita. Las fotos de personas no son un objetivo del sistema; la interfaz recuerda evitar rostros identificables cuando no sean necesarios `[REC]` |
| **Limitación de la finalidad** | Los datos de un proyecto no se usan para otro fin. **No se emplean para entrenar modelos** (§18.10) |
| **Limitación del plazo** | `organization.retention_months`; purga programada; papelera con caducidad |
| **Exactitud** | Historial de cambios y corrección trazable |
| **Integridad y confidencialidad** | Todo lo descrito en este documento |
| **Responsabilidad proactiva** | Registro de auditoría completo y exportable |

### Derechos de los interesados

| Derecho | Cómo se atiende |
|---|---|
| Acceso | Exportación de todos los datos de un usuario o contacto (JSON + archivos), mediante función de administración |
| Rectificación | Edición directa, con historial |
| **Supresión** | Borrado autorizado con doble confirmación y motivo. Se elimina el contenido y **se conserva un registro sin datos personales** que acredita el cumplimiento `[REQ]` |
| Limitación | Suspensión de usuario; proyecto archivado en solo lectura |
| Portabilidad | Exportación en formatos interoperables (JSON, XLSX, CSV) |
| Oposición | Gestionada por el responsable del tratamiento, con los medios técnicos anteriores |

`[REC]` **Tensión real que conviene explicitar:** el derecho de supresión choca con la necesidad de que
un informe emitido siga siendo reproducible y con las obligaciones de conservación contractual. La
resolución propuesta: los datos personales *accesorios* (contacto de cliente, autoría) pueden
seudonimizarse conservando la integridad del informe; el contenido técnico del informe emitido se
conserva durante el plazo de retención pactado. **Esta decisión debe validarla el responsable del
tratamiento** (P-15), no el equipo técnico.

### Transferencias y subencargados

`[SUP]` S-15: residencia en la UE. Todo proveedor de infraestructura debe ser subencargado con
contrato y ubicación documentada. `[REC]` Se mantiene en el repositorio un inventario de
subencargados y de los datos que trata cada uno; con la arquitectura propuesta la lista es corta:
proveedor de cómputo y almacenamiento, proveedor de correo transaccional, y proveedor de teselas de
mapa (que **no recibe datos de proyecto**, solo coordenadas).

---

## 18.9. Auditoría

### Qué se audita

`[REQ]` §9: «Toda aprobación, modificación relevante o descarga de documentación confidencial debe
quedar auditada.»

| Categoría | Acciones | Severidad |
|---|---|---|
| **Sesión** | `LOGIN_SUCCESS`, `LOGIN_FAILED`, `LOGOUT`, `MFA_ENROLLED`, `PASSWORD_RESET`, `SESSION_REVOKED` | INFO / AVISO |
| **Autorización** | `ACCESS_DENIED`, `ADMIN_ACCESS_GRANT` | AVISO / **CRÍTICO** |
| **Proyecto** | `PROJECT_CREATED/UPDATED/STATUS_CHANGED/ARCHIVED/DELETED/DUPLICATED` | INFO / AVISO |
| **Equipo** | `MEMBER_ASSIGNED/ROLE_CHANGED/REMOVED` | INFO |
| **Evidencia** | `PHOTO_UPLOADED/RENAMED/ANNOTATED/TRASHED/RESTORED`, `FILE_DOWNLOAD`, `BATCH_DOWNLOAD`, `MALWARE_DETECTED` | INFO / **CRÍTICO** |
| **Diagnóstico** | `FINDING_CREATED/UPDATED/VALIDATED/DISCARDED` | INFO |
| **CAPEX** | `CAPEX_CREATED/UPDATED`, `PRICE_VALIDATED`, `PRICE_CHANGED`, `INDEX_APPLIED`, `COST_PROFILE_CHANGED`, `CAPEX_APPROVED` | INFO / AVISO |
| **Precios** | `PRICE_SOURCE_ENABLED/DISABLED`, `PRICE_SOURCE_TOS_REVIEWED`, `PRICE_SOURCE_AUTO_DISABLED` | **CRÍTICO** |
| **Informe** | `TEMPLATE_UPLOADED`, `MAPPING_SAVED`, `REPORT_GENERATED`, `REPORT_FORCED_GENERATION`, `REPORT_SUBMITTED`, `REPORT_APPROVED/REJECTED`, `REPORT_ISSUED`, `REPORT_DOWNLOADED` | INFO / **CRÍTICO** |
| **Datos** | `EXPORT_CREATED`, `HARD_DELETE`, `RETENTION_PURGE_EXECUTED`, `GDPR_EXPORT`, `GDPR_ERASURE` | **CRÍTICO** |
| **Administración** | `USER_INVITED/SUSPENDED/DELETED`, `ROLE_PERMISSIONS_CHANGED`, `ORG_SETTINGS_CHANGED`, `RETENTION_POLICY_CHANGED` | AVISO / **CRÍTICO** |

### Cómo se garantiza la integridad

| Garantía | Mecanismo |
|---|---|
| **Solo se añade** | El usuario de aplicación tiene únicamente `INSERT` y `SELECT` sobre `audit_log`. No existe endpoint de modificación ni de borrado `[REQ]` |
| **Evidencia de manipulación** | `[REC]` Cadena hash: `record_hash = SHA256(prev_hash ‖ campos canónicos)`. Un trabajo diario verifica la cadena y alerta si se rompe. No impide la manipulación por alguien con acceso directo a la base de datos, pero la hace **detectable**, que es lo alcanzable sin un servicio externo de sellado |
| **Escritura garantizada** | El evento se escribe en la **misma transacción** que la operación auditada. Si falla el registro, falla la operación `[REC]` Es la única forma de que «no puede completarse sin dejar registro» sea cierto |
| **Sin datos sensibles** | Filtro de redacción por nombre de campo antes de persistir: contraseñas, secretos, tokens `[REQ]` |
| **Correlación** | `request_id` común a auditoría, logs y trazas |
| **Volumen** | Tabla particionada por mes; retención configurable y superior a la de los datos de negocio |
| **Sobrevive al dato** | La purga de un proyecto conserva un registro sin contenido personal `[REQ]` |

### Historial de cambios frente a auditoría

Dos cosas distintas que el encargo pide por separado, y se implementan por separado `[REC]`:

| | `audit_log` | `change_history` |
|---|---|---|
| Pregunta que responde | «¿Quién hizo qué y cuándo?» | «¿Cómo ha evolucionado este campo?» |
| Grano | Una operación | Un campo |
| Visible para | Admin y director de proyecto | Todo el equipo del proyecto |
| Inmutable | Sí, estrictamente | Sí |
| Uso típico | Investigación, cumplimiento | Trabajo diario: «¿quién cambió esta cantidad?» |

---

## 18.10. Inteligencia artificial: política explícita

`[REQ]` «No utilizar fotografías, documentos o datos del cliente para entrenar modelos de IA sin
autorización expresa y verificable. Informar al usuario cuando una función utilice IA y permitir
revisión humana.»

| Regla | Implementación |
|---|---|
| **Ninguna función de IA en el MVP** | No hay ninguna llamada a servicios de IA en el alcance del MVP. Lo que no existe no puede filtrar datos `[REC]` |
| **Sin entrenamiento con datos de cliente** | Política escrita y verificable: no hay ruta de código que envíe fotografías, documentos ni datos de proyecto a un servicio de terceros. Se comprueba en revisión de código y en el inventario de dependencias de red |
| **Consentimiento explícito y verificable** | Si en el futuro se incorpora IA, requerirá: interruptor **desactivado por defecto** a nivel de organización, aceptación registrada con usuario y fecha, y posibilidad de revocarla |
| **Transparencia** | Toda salida generada por IA se marcará visualmente como tal, con indicación del modelo y la fecha |
| **Revisión humana obligatoria** | Ninguna salida de IA se persistirá como dato validado sin aprobación explícita de un usuario, exactamente igual que los precios |
| **Registro** | Cada uso de una función de IA generará un evento de auditoría con la entrada resumida y el usuario que la solicitó |
| **Minimización** | Si se usa IA, se enviará el mínimo contexto necesario, nunca el proyecto completo |

`[REC]` La postura recomendada para las fases 7+ del plan: si se incorpora IA (por ejemplo, redacción
asistida de descripciones de incidencias), hacerlo con un modelo desplegado en infraestructura propia
o con un proveedor con compromiso contractual explícito de no entrenamiento, y siempre como
**sugerencia editable**, nunca como dato validado.

---

## 18.11. Copias de seguridad y recuperación

| Aspecto | Decisión | Verificación |
|---|---|---|
| Base de datos | Copia completa diaria + WAL continuo (recuperación a un punto en el tiempo) | `[SUP]` RPO 15 min |
| Objetos | Versionado de bucket + replicación a otra región o cuenta | RPO cercano a cero |
| Retención de copias | 30 días de diarias + 12 mensuales `[SUP]` | |
| Cifrado | Copias cifradas; claves separadas de las de producción | |
| Aislamiento | Copias en **otra cuenta o proyecto** del proveedor, para que un compromiso de producción no las alcance `[REC]` | |
| **Ensayo de restauración** | **Trimestral, documentado, con medición del tiempo real** `[REC]` | Una copia no verificada no es una copia |
| RTO objetivo | 4 h `[SUP]` S-17 | Medido en el ensayo |
| Coherencia entre base de datos y objetos | El ensayo verifica que no queden referencias a objetos inexistentes tras restaurar a un punto en el tiempo `[REC]` | Es el fallo silencioso más probable de este diseño |

`[REC]` Ese último punto merece énfasis: restaurar la base de datos a hace dos horas mientras el
almacenamiento de objetos sigue en el presente produce un sistema incoherente. El procedimiento de
recuperación incluye un paso de reconciliación que detecta filas apuntando a objetos ausentes y las
marca para revisión manual, en lugar de dejar errores dispersos apareciendo durante semanas.

---

## 18.12. Observabilidad y detección

| Elemento | Herramienta | Uso de seguridad |
|---|---|---|
| Trazas y métricas | OpenTelemetry → Prometheus / Grafana | Anomalías de latencia y volumen |
| Logs estructurados | JSON → Loki, con `request_id` y `organization_id`, **sin datos personales ni secretos** | Investigación |
| Errores | Sentry con depuración de datos personales activada | Detección temprana |
| Alertas de seguridad | `MALWARE_DETECTED`, ráfaga de `ACCESS_DENIED`, ráfaga de `LOGIN_FAILED`, `ADMIN_ACCESS_GRANT`, descarga masiva inusual, `PRICE_SOURCE_AUTO_DISABLED`, rotura de la cadena hash de auditoría | Respuesta a incidentes |
| Sondas | `/health` (proceso vivo), `/ready` (dependencias disponibles) | Disponibilidad |

`[REC]` La alerta por **descarga masiva inusual** (por ejemplo, un usuario descargando 800
fotografías en diez minutos cuando su media es 20) es la que detecta el escenario más probable de
fuga real: no un atacante externo, sino una persona con acceso legítimo llevándose la información de
un cliente. Umbral configurable, y la alerta avisa, no bloquea.

---

## 18.13. Verificación continua

| Control | Frecuencia | Fase |
|---|---|---|
| Análisis estático de seguridad (`bandit`, `semgrep`) | Cada `commit` | MVP |
| Auditoría de dependencias (`pip-audit`, `npm audit`) | Cada `commit` + diaria | MVP |
| Escaneo de secretos | Pre-commit + CI | MVP |
| Pruebas de la matriz de permisos | Cada `commit` | MVP |
| Prueba de que todo endpoint declara autorización | Cada `commit` | MVP |
| Pruebas de aislamiento entre organizaciones | Cada `commit` | MVP |
| Escaneo de vulnerabilidades de imágenes de contenedor | En cada construcción | MVP |
| Escaneo dinámico básico (ZAP baseline) | Nocturno en `staging` | Fase 2 |
| Verificación de la cadena hash de auditoría | Diaria | MVP |
| Ensayo de restauración de copias | Trimestral | Fase 2 |
| Revisión de accesos y usuarios inactivos | Trimestral | Fase 2 |
| Prueba de penetración externa | Antes del primer cliente real | `[REC]` Fase 6 |

---

## 18.14. Resumen: requisitos de §5 del encargo y su implementación

| Requisito | Dónde se cumple |
|---|---|
| Cifrado en tránsito y en reposo | §18.2 |
| Control de acceso basado en roles | §18.4 + [`06-roles-permisos.md`](./06-roles-permisos.md) |
| Principio de mínimo privilegio | §18.4, incluida la infraestructura |
| URLs firmadas para acceder a archivos | §18.5, 5 min, un recurso, tras autorizar |
| Registro de accesos y descargas | §18.9, `FILE_DOWNLOAD` y `ACCESS_DENIED` |
| Separación entre clientes y organizaciones | RLS + `404` en lugar de `403` + claves de objeto por organización |
| Protección frente a archivos maliciosos | §18.5, antivirus + tipo real + listas blancas |
| Validación del tipo real de archivo | §18.5, `libmagic` |
| Antivirus | §18.5, ClamAV |
| Límites de tamaño | §18.5 |
| Gestión segura de secretos | §18.7 |
| Prevención de inyección, XSS, CSRF, accesos directos | §18.6 |
| Cumplimiento del RGPD | §18.8 |
| Exportar y eliminar datos conforme a políticas | §18.8 + §8.9 del modelo de datos |
| No usar datos de cliente para entrenar IA | §18.10 |
| Informar cuando una función use IA y permitir revisión humana | §18.10 |

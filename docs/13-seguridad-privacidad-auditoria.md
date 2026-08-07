# 18. Seguridad, privacidad y auditoría

---

## 18.1. Modelo de amenazas

Antes de las medidas: qué se protege y de quién. `[REC]`

| Activo | Amenaza principal | Consecuencia |
|---|---|---|
| Fotografías y documentos del edificio | Acceso de otra organización o URL adivinada | Fuga confidencial de un cliente. Daño reputacional grave |
| **Enlace y credenciales del VDR** | Acceso indebido al repositorio del cliente | Fuga masiva: el VDR contiene *toda* la documentación de la operación |
| Datos de contacto de clientes | Exfiltración | Incumplimiento del RGPD |
| Informe emitido | Alteración posterior | Pérdida de valor probatorio del entregable |
| CAPEX y precios | Manipulación no trazable | Informe indefendible ante el cliente |
| Registro de auditoría | Borrado o alteración | Imposibilidad de demostrar lo ocurrido |
| Plantilla PPTX corporativa | Sobrescritura o pérdida | Pérdida de un activo de la consultora |
| Credenciales | Robo, reutilización, fuerza bruta | Acceso completo suplantando a un usuario |
| Infraestructura | Archivo malicioso, ataque XML | Ejecución de código en el servidor |
| **Buzón de sugerencias** `[REC]` | Que se use como **vía lateral** para sacar datos de un proyecto: un usuario pega un importe o un nombre de cliente, y el administrador lo lee sin dejar rastro de acceso a ese proyecto | Se rodea, sin querer, el control que audita el acceso de administrador al contenido. Mitigado en [`19`](./19-sugerencias.md) §19.4: el contexto se guarda **por referencia**, se avisa en el formulario, y abrir una sugerencia con contexto de proyecto **se audita** |

**Actores considerados:** usuario legítimo con exceso de curiosidad (el más frecuente); usuario de
otra organización; atacante externo no autenticado; atacante con cuenta válida de baja privilegio; y
**administrador propio**, que es el actor que más sistemas olvidan modelar.

`[REC]` La fila del **VDR** es específica de este producto. El enlace al Virtual Data Room es la puerta
a toda la documentación confidencial de la operación. Por eso: **no se almacenan sus credenciales**,
solo `DIRECTOR_PROYECTO` puede modificar el enlace, y todo cambio y toda consulta quedan auditados.

---

## 18.2. Cifrado

| Ámbito | Medida |
|---|---|
| **En tránsito** | TLS 1.3 obligatorio (1.2 mínimo). HSTS con `max-age` de un año e `includeSubDomains`. Sin cifrados obsoletos `[REQ]` |
| **En reposo · base de datos** | Cifrado de volumen; backups cifrados con clave gestionada `[REQ]` |
| **En reposo · objetos** | Cifrado del lado del servidor (SSE) `[REQ]` |
| **Campos sensibles** | AES-256-GCM a nivel de aplicación para el secreto TOTP y tokens de integración; clave en el gestor de secretos, rotable `[REC]` La capa de volumen no protege frente a un volcado de base de datos |
| **Contraseñas** | **Argon2id** con parámetros según recomendaciones actuales de OWASP `[REQ]` |
| **Entre servicios** | Red privada; TLS si el proveedor no garantiza aislamiento |
| **Integridad** | SHA-256 sobre originales, PPTX generados y snapshots |

---

## 18.3. Autenticación

| Control | Decisión |
|---|---|
| Contraseñas | Mínimo 12 caracteres; comprobación contra listas comprometidas; sin reglas de composición absurdas (favorecen contraseñas peores) `[REC]` |
| MFA | TOTP opcional por usuario, exigible por política de organización. Códigos de recuperación de un solo uso |
| Bloqueo | Retardo progresivo tras 3 intentos; bloqueo temporal tras 8; aviso por correo al usuario legítimo `[SUP]` |
| Enumeración de usuarios | Error idéntico ante usuario inexistente y contraseña incorrecta; tiempo de respuesta uniformado; recuperación responde `202` siempre |
| Tokens de acceso | JWT de 15 min, firma asimétrica con clave rotable. **En memoria del cliente, nunca en `localStorage`** `[REC]` |
| Tokens de refresco | Opacos, cookie `HttpOnly`, `Secure`, `SameSite=Lax`, con rotación. **Reutilización detectada ⇒ revocación de toda la familia** `[REC]` Es la defensa efectiva ante un token robado |
| Cierre de sesión | Revocación en servidor, no solo borrado en cliente |
| Recuperación | Token de un solo uso, 30 min, invalidado al usarse. Cambiar la contraseña **revoca todas las sesiones** |
| Sesiones activas | El usuario puede ver y cerrar sus sesiones `[REC]` |
| SSO | Interfaz `IdentityProvider` preparada; OIDC en fase posterior (P-17) |

---

## 18.4. Autorización

Cuatro capas (detalle en [`07-roles-permisos.md`](./07-roles-permisos.md)):

1. **RLS** en PostgreSQL por `organization_id`. El usuario de aplicación **no tiene `BYPASSRLS`**.
2. **Pertenencia al proyecto** verificada en el servidor.
3. **Permiso de acción** declarado como dependencia en cada endpoint. Una prueba recorre el router y
   **falla si algún endpoint no declara política**. `[REC]`
4. **Reglas de estado**: informe bloqueado, proyecto archivado, fase con estado derivado, zona no
   válida para la tipología.

`[REQ]` «Implementa autorización en backend, no solo ocultación visual.» La suite verifica cada
denegación llamando directamente a la API, sin pasar por la interfaz.

**Mínimo privilegio en la infraestructura** `[REC]`:

| Componente | Privilegios |
|---|---|
| Usuario de aplicación en PostgreSQL | `SELECT`/`INSERT`/`UPDATE` en tablas de negocio; **solo `INSERT` y `SELECT` en `audit_log`**; sin DDL; sin `BYPASSRLS` |
| Usuario de migraciones | DDL, usado solo por el pipeline |
| Workers de PPTX y LibreOffice | **Sin salida a Internet**; acceso solo a las claves recibidas |
| API | Sin acceso al sistema de archivos del host más allá de un temporal |
| Contenedores | Usuario no root, raíz de solo lectura, sin capacidades añadidas |

---

## 18.5. Protección de archivos

| Control | Implementación | Req. |
|---|---|---|
| Validación del **tipo real** | `libmagic` sobre los primeros bytes, contrastado con el MIME declarado y una lista blanca. Discrepancia ⇒ `415` | `[REQ]` |
| Recuperación de contraseña | Token de 256 bits, **guardado en huella**, un solo uso, 30 minutos, en el fragmento de la URL. Respuesta idéntica exista o no la cuenta; tope de 3 por hora. Restablecer **revoca todas las sesiones**. `[LIM]` queda una diferencia de tiempo entre las dos ramas hasta que el envío se encole | `[REQ]` |
| Antivirus | ClamAV por `INSTREAM`, **antes de escribir nada** y antes de interpretar el fichero: fotografías, documentos y plantillas. Positivo ⇒ se rechaza la subida y queda en `audit_log` con severidad `CRITICO`. Desactivado por defecto; sin él el veredicto es `NO_ANALIZADO`, nunca `LIMPIO`. `[LIM]` sin probar contra un ClamAV real | `[REQ]` |
| Límites de tamaño | 50 MB por archivo, 500 MB por lote, cuota por proyecto y organización | `[REQ]` |
| Lista blanca | Imágenes: jpg, jpeg, png, webp, heic, heif. Documentos: pdf, docx, xlsx, dwg. Plantillas: pptx. **Nada más** | `[REC]` |
| Bloqueo de ejecutables y macros | `.exe`, `.dll`, `.js`, `.sh`, `.bat`, `.pptm`, `.docm`, `.xlsm`; se comprueba también el contenido del paquete OOXML | `[REQ]` |
| Bombas de descompresión | Límite de tamaño descomprimido, de entradas y de ratio, antes de descomprimir | `[REC]` |
| Ataques XML | Entidades externas y DTD deshabilitadas en todo análisis | `[REC]` |
| Nombres de archivo | Nunca se usan para construir rutas: la ruta es `{org}/{project}/originals/{uuid}.{ext}`. El nombre del usuario vive solo en la base de datos | `[REC]` Elimina de raíz el recorrido de rutas |
| Servido de archivos | **Nunca** desde la aplicación. URL firmada, un recurso, 5 minutos, tras verificar autorización | `[REQ]` |
| XSS por archivo | Objetos servidos desde un dominio distinto, con `Content-Disposition: attachment` y `X-Content-Type-Options: nosniff` | `[REC]` Un SVG malicioso servido desde el dominio principal sería XSS almacenado |

---

## 18.6. Vulnerabilidades web

| Riesgo | Medida |
|---|---|
| **Inyección SQL** | ORM con consultas parametrizadas. SQL concatenado prohibido y verificado por `bandit` y `semgrep` en CI `[REQ]` |
| **XSS** | React escapa por defecto; `dangerouslySetInnerHTML` prohibido por lint; sanitización en servidor; **CSP estricta sin `unsafe-inline`** `[REQ]` |
| **CSRF** | Token de acceso en cabecera `Authorization` (no en cookie), lo que elimina el vector principal; el refresco usa `SameSite=Lax` y exige cabecera personalizada; CORS restringido `[REQ]` |
| **Acceso directo a objetos (IDOR)** | UUID no adivinables + autorización en cada acceso + RLS. **`404` en lugar de `403`** `[REQ]` |
| **SSRF** | Ninguna URL suministrada por el usuario se solicita desde el servidor. **Ni siquiera el enlace del VDR**: se guarda y se muestra, nunca se resuelve desde el backend `[REC]` Los adaptadores de precios solo llaman a URLs de lista blanca |
| **Redirecciones abiertas** | Solo rutas relativas internas |
| **Fijación de sesión** | Rotación de token en cada autenticación y refresco |
| **Denegación de servicio** | Límite de tasa por usuario e IP, más estricto en autenticación, precios y generación; límites de recursos en workers; tamaño máximo de cuerpo |
| **Deserialización insegura** | Solo JSON con esquemas Pydantic estrictos. **Nunca `pickle`** para datos de usuario |
| **Cabeceras** | CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` |
| **Dependencias** | `pip-audit` y `npm audit` en CI con fallo ante vulnerabilidades altas o críticas |
| **Secretos en el repositorio** | Escaneo en CI y pre-commit; `.env` en `.gitignore`; **solo `.env.example` sin valores reales** `[REQ]` |

---

## 18.7. Gestión de secretos

| Regla | Detalle |
|---|---|
| Nunca en el código | Sin credenciales, claves ni cadenas de conexión en el repositorio `[REQ]` |
| Nunca en la imagen | Variables de entorno en ejecución, no en el `Dockerfile` |
| Origen | Gestor de secretos del proveedor o Vault |
| Rotación | Documentada y ensayada para: base de datos, clave de firma JWT, acceso al almacenamiento, clave de cifrado de campos. La clave de firma admite **dos activas** para rotar sin cerrar sesiones `[REC]` |
| Nunca en logs | Filtro que redacta por nombre de clave antes de escribir |
| Nunca en errores | Ningún mensaje incluye cadenas de conexión, rutas ni nombres de bucket |
| `.env.example` | Todas las variables documentadas, **sin un solo valor real** `[REQ]` |
| **Credenciales de terceros** | **No se almacenan las del VDR ni las de Precio Centro.** Si en el futuro se integra una fuente que las exija, irán al gestor de secretos, nunca a la base de datos `[REC]` |

---

## 18.8. Privacidad y RGPD

`[REQ]` «Cumplimiento del RGPD en los aspectos aplicables.»

### Datos personales tratados

| Categoría | Datos | Base jurídica probable `[PDV]` |
|---|---|---|
| Usuarios de la plataforma | Nombre, correo, teléfono, cargo, registros de acceso | Ejecución de contrato / interés legítimo |
| Contactos de cliente | Nombre, cargo, correo, teléfono | Interés legítimo (contacto profesional) |
| **Asistentes a visitas y presentaciones** | Nombre y organización | Interés legítimo `[REC]` Campo nuevo con las fases: conviene minimizarlo |
| Contenido de fotografías | Puede captar personas presentes en el edificio | Interés legítimo, **con minimización** |
| Metadatos EXIF | GPS, dispositivo | Interés legítimo |

`[PDV]` Las bases jurídicas, el registro de actividades de tratamiento y la procedencia de una
evaluación de impacto son decisiones del responsable del tratamiento. Aquí se aportan los **medios
técnicos** para cumplir, no asesoramiento jurídico.

### Principios por diseño

| Principio | Implementación |
|---|---|
| **Minimización** | No se piden datos personales que el negocio no necesita. Las fotos de personas no son un objetivo; la interfaz recuerda evitar rostros identificables cuando no sean necesarios `[REC]` |
| **Limitación de la finalidad** | Los datos de un proyecto no se usan para otro fin. **No se emplean para entrenar modelos** (§18.10) |
| **Limitación del plazo** | `retention_months`; purga programada; papelera con caducidad |
| **Exactitud** | Historial de cambios y corrección trazable |
| **Integridad y confidencialidad** | Todo lo descrito en este documento |
| **Responsabilidad proactiva** | Registro de auditoría completo y exportable |

### Derechos de los interesados

| Derecho | Cómo se atiende |
|---|---|
| Acceso | Exportación de todos los datos de un usuario o contacto (JSON + archivos) |
| Rectificación | Edición directa, con historial |
| **Supresión** | Borrado autorizado con doble confirmación y motivo. Se elimina el contenido y **se conserva un registro sin datos personales** que acredita el cumplimiento `[REQ]` |
| Limitación | Suspensión de usuario; proyecto archivado en solo lectura |
| Portabilidad | Exportación en JSON, XLSX y CSV |
| Oposición | Gestionada por el responsable, con los medios anteriores |

`[REC]` **Tensión que conviene explicitar:** el derecho de supresión choca con la necesidad de que un
informe emitido siga siendo reproducible y con las obligaciones de conservación contractual.
Resolución propuesta: los datos personales *accesorios* (contacto, autoría, asistentes) pueden
seudonimizarse conservando la integridad del informe; el contenido técnico del informe emitido se
conserva durante el plazo pactado. **Esta decisión la valida el responsable del tratamiento** (P-24),
no el equipo técnico.

`[SUP]` S-16: residencia UE. Se mantiene un inventario de subencargados; con esta arquitectura la lista
es corta: cómputo y almacenamiento, correo transaccional, y proveedor de teselas (que **no recibe
datos de proyecto**, solo coordenadas).

---

## 18.9. Auditoría

`[REQ]` §9: «Toda aprobación, modificación relevante o descarga de documentación confidencial debe
quedar auditada.»

| Categoría | Acciones | Severidad |
|---|---|---|
| **Sesión** | `LOGIN_SUCCESS/FAILED`, `LOGOUT`, `MFA_ENROLLED`, `PASSWORD_RESET`, `SESSION_REVOKED` | INFO / AVISO |
| **Autorización** | `ACCESS_DENIED`, `ADMIN_ACCESS_GRANT` | AVISO / **CRÍTICO** |
| **Proyecto** | `PROJECT_CREATED/UPDATED/STATUS_CHANGED/ARCHIVED/DELETED/DUPLICATED` | INFO / AVISO |
| **Fases** `[REC]` | `PHASE_ACTIVATED/DEACTIVATED`, `PHASE_STATUS_CHANGED`, `PHASE_OWNER_CHANGED`, **`VDR_LINK_SET/CHANGED/REMOVED`**, `DOC_REQUEST_STATUS_CHANGED`, `VISIT_SCHEDULED/COMPLETED`, `QA_ROUND_UPLOADED` | INFO / **CRÍTICO** (VDR) |
| **Equipo** | `MEMBER_ASSIGNED/ROLE_CHANGED/REMOVED` | INFO |
| **Activos** | `ASSET_CREATED/UPDATED`, **`ASSET_TYPOLOGY_CHANGED`** (con las líneas afectadas) | INFO / AVISO |
| **Evidencia** | `PHOTO_UPLOADED/RENAMED/ANNOTATED/TRASHED/RESTORED`, `FILE_DOWNLOAD`, `BATCH_DOWNLOAD`, `MALWARE_DETECTED` | INFO / **CRÍTICO** |
| **Diagnóstico** | `FINDING_CREATED/UPDATED/VALIDATED/DISCARDED` | INFO |
| **CAPEX** | `CAPEX_CREATED/UPDATED`, `PRICE_VALIDATED`, `PRICE_CHANGED`, `INDEX_APPLIED`, `COST_PROFILE_CHANGED`, `CAPEX_APPROVED` | INFO / AVISO |
| **Precios** | `PRICE_SOURCE_ENABLED/DISABLED`, `PRICE_SOURCE_TOS_REVIEWED`, `PRICE_SOURCE_AUTO_DISABLED`, `PRICE_SOURCE_LICENCE_EXPIRED` | **CRÍTICO** |
| **Catálogos** | `CATALOG_ITEM_CREATED`, `CAPEX_CODE_DEPRECATED` | AVISO |
| **Informe** | `TEMPLATE_UPLOADED`, `MAPPING_SAVED`, `REPORT_GENERATED`, `REPORT_FORCED_GENERATION`, `REPORT_SUBMITTED`, `REPORT_APPROVED/REJECTED`, `REPORT_ISSUED`, `REPORT_DOWNLOADED` | INFO / **CRÍTICO** |
| **Datos** | `EXPORT_CREATED`, `HARD_DELETE`, `RETENTION_PURGE_EXECUTED`, `GDPR_EXPORT`, `GDPR_ERASURE` | **CRÍTICO** |
| **Sugerencias** `[REQ]` | `SUGGESTION_CREATED`, **`SUGGESTION_VIEWED`** (solo si lleva contexto de proyecto), `SUGGESTION_STATUS_CHANGED`, `SUGGESTION_APPLIED` | INFO / **AVISO** |
| **Administración** | `USER_INVITED/SUSPENDED/DELETED`, `ROLE_PERMISSIONS_CHANGED`, `ORG_SETTINGS_CHANGED`, `RETENTION_POLICY_CHANGED` | AVISO / **CRÍTICO** |

### Integridad

| Garantía | Mecanismo |
|---|---|
| **Solo se añade** | El usuario de aplicación tiene únicamente `INSERT` y `SELECT`. No existe endpoint de modificación ni borrado `[REQ]` |
| **Evidencia de manipulación** | `[REC]` Cadena hash `record_hash = SHA256(prev_hash ‖ campos canónicos)`. Un trabajo diario la verifica y alerta si se rompe. No impide la manipulación por alguien con acceso directo a la base de datos, pero la hace **detectable**, que es lo alcanzable sin un servicio externo de sellado |
| **Escritura garantizada** | El evento se escribe en la **misma transacción** que la operación. Si falla el registro, falla la operación `[REC]` Es lo único que hace cierto «no puede completarse sin dejar registro» |
| **Sin datos sensibles** | Filtro de redacción por nombre de campo antes de persistir `[REQ]` |
| **Correlación** | `request_id` común a auditoría, logs y trazas |
| **Volumen** | Tabla particionada por mes; retención superior a la de negocio |
| **Sobrevive al dato** | La purga conserva un registro sin contenido personal `[REQ]` |

### Historial de cambios frente a auditoría

Dos cosas distintas que la especificación pide por separado (§3.1.6), y se implementan por separado:

| | `audit_log` | `change_history` |
|---|---|---|
| Responde | «¿Quién hizo qué y cuándo?» | «¿Cómo ha evolucionado este campo?» |
| Grano | Una operación | Un campo |
| Visible para | Admin y director | Todo el equipo del proyecto |
| Uso típico | Cumplimiento, investigación | Día a día: «¿quién cambió este importe?» |

---

## 18.10. Inteligencia artificial: política explícita

`[REQ]` «No utilizar fotografías, documentos o datos del cliente para entrenar modelos de IA sin
autorización expresa y verificable. Informar al usuario cuando una función utilice IA y permitir
revisión humana.»

| Regla | Implementación |
|---|---|
| **Ninguna función de IA en el MVP** | No hay ninguna llamada a servicios de IA en el alcance. Lo que no existe no puede filtrar datos `[REC]` |
| **Sin entrenamiento con datos de cliente** | No hay ruta de código que envíe fotografías, documentos ni datos de proyecto a un tercero. Se comprueba en revisión de código y en el inventario de dependencias de red |
| **Consentimiento explícito y verificable** | Si se incorpora IA: interruptor **desactivado por defecto** a nivel de organización, aceptación registrada con usuario y fecha, y revocable |
| **Transparencia** | Toda salida generada por IA se marcará como tal, con modelo y fecha |
| **Revisión humana obligatoria** | Ninguna salida se persistirá como dato validado sin aprobación explícita, igual que los precios |
| **Registro** | Cada uso generará un evento de auditoría |
| **Minimización** | Se enviaría el mínimo contexto necesario, nunca el proyecto completo |

`[REC]` Postura recomendada para fases posteriores: si se incorpora IA (por ejemplo, redacción asistida
de descripciones de hallazgos), hacerlo con un modelo en infraestructura propia o con compromiso
contractual explícito de no entrenamiento, y siempre como **sugerencia editable**, nunca como dato
validado.

---

## 18.11. Copias de seguridad y recuperación

| Aspecto | Decisión | Verificación |
|---|---|---|
| Base de datos | Copia completa diaria + WAL continuo (PITR) | `[SUP]` RPO 15 min |
| Objetos | Versionado + replicación a otra región o cuenta | RPO cercano a cero |
| Retención | 30 diarias + 12 mensuales `[SUP]` | |
| Cifrado | Copias cifradas; claves separadas de producción | |
| Aislamiento | Copias en **otra cuenta** del proveedor, para que un compromiso de producción no las alcance `[REC]` | |
| **Ensayo de restauración** | **Trimestral, documentado, cronometrado** `[REC]` | Una copia no verificada no es una copia |
| RTO objetivo | 4 h `[SUP]` S-20 | Medido en el ensayo |
| Coherencia base de datos ↔ objetos | El ensayo verifica que no queden referencias a objetos inexistentes tras un PITR `[REC]` | Es el fallo silencioso más probable de este diseño |

`[REC]` Ese último punto merece énfasis: restaurar la base de datos a hace dos horas mientras el
almacenamiento sigue en el presente produce un sistema incoherente. El procedimiento incluye un paso
de reconciliación que detecta filas apuntando a objetos ausentes y las marca para revisión manual, en
lugar de dejar errores dispersos apareciendo durante semanas.

---

## 18.12. Observabilidad y detección

| Elemento | Herramienta | Uso de seguridad |
|---|---|---|
| Trazas y métricas | OpenTelemetry → Prometheus / Grafana | Anomalías de latencia y volumen |
| Logs estructurados | JSON → Loki, con `request_id` y `organization_id`, **sin datos personales ni secretos** | Investigación |
| Errores | Sentry con depuración de datos personales | Detección temprana |
| Alertas | `MALWARE_DETECTED`, ráfaga de `ACCESS_DENIED`, ráfaga de `LOGIN_FAILED`, `ADMIN_ACCESS_GRANT`, **`VDR_LINK_CHANGED`**, descarga masiva inusual, `PRICE_SOURCE_AUTO_DISABLED`, rotura de la cadena hash | Respuesta a incidentes |
| Sondas | `/health` (proceso vivo), `/ready` (dependencias) | Disponibilidad |

`[REC]` La alerta por **descarga masiva inusual** (un usuario descargando 800 fotografías en diez
minutos cuando su media es 20) es la que detecta el escenario más probable de fuga real: no un
atacante externo, sino una persona con acceso legítimo llevándose la información de un cliente.
Umbral configurable; la alerta avisa, no bloquea.

---

## 18.13. Verificación continua

| Control | Frecuencia | Fase |
|---|---|---|
| Análisis estático (`bandit`, `semgrep`) | Cada `commit` | MVP |
| Auditoría de dependencias | Cada `commit` + diaria | MVP |
| Escaneo de secretos | Pre-commit + CI | MVP |
| Pruebas de la matriz de permisos | Cada `commit` | MVP |
| Prueba de que todo endpoint declara autorización | Cada `commit` | MVP |
| Aislamiento entre organizaciones | Cada `commit` | MVP |
| Escaneo de imágenes de contenedor | En cada construcción | MVP |
| Verificación de la cadena hash de auditoría | Diaria | MVP |
| Caducidad de licencias de fuentes de precios | Diaria | MVP |
| Escaneo dinámico (ZAP baseline) | Nocturno en `staging` | Fase 2 |
| Ensayo de restauración | Trimestral | Fase 2 |
| Revisión de accesos y usuarios inactivos | Trimestral | Fase 2 |
| Prueba de penetración externa | Antes del primer cliente real | `[REC]` |

---

## 18.14. Resumen: requisitos de §5 y su implementación

| Requisito | Dónde |
|---|---|
| Cifrado en tránsito y en reposo | §18.2 |
| Control de acceso basado en roles | §18.4 + [`07`](./07-roles-permisos.md) |
| Principio de mínimo privilegio | §18.4, incluida la infraestructura |
| URLs firmadas para archivos | §18.5, 5 min, un recurso, tras autorizar |
| Registro de accesos y descargas | §18.9 |
| Separación entre clientes y organizaciones | RLS + `404` + claves por organización |
| Protección frente a archivos maliciosos | §18.5 |
| Validación del tipo real de archivo | §18.5, `libmagic` |
| Antivirus | §18.5, ClamAV |
| Límites de tamaño | §18.5 |
| Gestión segura de secretos | §18.7 |
| Prevención de inyección, XSS, CSRF, accesos directos | §18.6 |
| Cumplimiento del RGPD | §18.8 |
| Exportar y eliminar datos conforme a políticas | §18.8 + modelo §8.11 |
| No usar datos de cliente para entrenar IA | §18.10 |
| Informar del uso de IA y permitir revisión humana | §18.10 |

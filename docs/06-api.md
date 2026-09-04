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
| `POST` | `/auth/password/forgot` | Responde `202` y **el mismo cuerpo** siempre, exista o no la dirección: distinguir «enviado» de «no existe» es un comprobador de cuentas gratuito. Tope de 3 por hora y usuario, sin que la respuesta cambie. `[LIM]` queda una diferencia de **tiempo** —hablar con el SMTP tarda— que solo desaparece encolando el envío, y el worker de §17 no está construido |
| `POST` | `/auth/password/reset` | Token de un solo uso, 30 min. Se guarda la **huella**, nunca el token, y viaja en el **fragmento** de la URL para no acabar en el log del proxy ni en el `Referer`. Al restablecer se **revocan todas las sesiones** y se invalidan los demás enlaces pendientes, en una sola sentencia. Una contraseña débil da `422` y **no gasta el enlace** |
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
| `GET` | `/catalogs/capex-codes/tree` | `[LIM]` **No está construido.** Se diseñó para precargar el selector en una llamada; hoy `/capex-codes` devuelve la lista plana con `level` y `parent_id`, y el cliente arma el árbol. Pedir esta ruta da un `404`, y se dice aquí en vez de dejar la fila como si existiera |
| `GET` | `/catalogs/risk-levels` | **Incluye la definición íntegra de cada grado** `[REQ]` |
| `GET` | `/catalogs/capex-concepts` · `/time-horizons` · `/specialties` · `/doc-request-categories` | `time-horizons` devuelve los cinco valores con su rango de años |
| `GET` | `/catalogs/technical-systems` | Los 14 sistemas de §3.2, en el orden de una visita. `capex_chapter` es **texto**: «Protección contra incendios» mapea a `H06 + H10`, dos capítulos (§5.8) |
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
| `GET`/`POST` | `/project-phases/{id}/doc-requests` | Checklist. Al crear la fase se siembra con las 6 categorías de §3.1.5, y la primera es la **memoria técnica** |
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
| `GET`/`PUT` | `/assets/{id}/zones` | **Zonas privadas y comunes**, por activo. El `PUT` manda la lista entera y sustituye: la memoria las declara de una vez. `422` si la tipología no admite alguna |
| `GET`/`PUT` | `/assets/{id}/memoria` | La **memoria técnica**: la propuesta de datos del edificio y las categorías del CAPEX con sus objetos. Guardar **no toca el activo** |
| `POST` | `/assets/{id}/memoria/validar` | **El botón.** Vuelca la propuesta al activo y firma quién y cuándo. `422` sin `confirmar: true` |
| `POST` | `/assets/{id}/memoria/generar-capex` | El **esqueleto**: un hallazgo en BORRADOR por objeto. Idempotente: no duplica ni pisa lo ya rellenado |
| `GET`/`POST` | `/projects/{id}/members` | `{user_id, role_code, specialty_ids[], asset_ids[]}` |

### Extracción documental `[REQ]`

Con las palabras del cliente: *«dependiendo de la documentación que se suba se
pueda ir completando el cuadro de CAPEX automáticamente para que después el
gestor de la due diligence valide la información»*.

El extractor lo elige **el tipo del documento**, no el que llama. Hoy solo se
lee `MEMORIA_TECNICA`; `/extraccion/tipos-soportados` dice cuáles, para que la
pantalla ofrezca el botón únicamente donde va a funcionar.

**Nada se aplica solo.** Extraer deja **propuestas pendientes**, cada una con
el documento, la sección y el fragmento **literal** del que salió. Entre la
propuesta y el dato hay siempre una persona pulsando `…/propuestas/decidir`.
Por eso una propuesta es una fila con procedencia y no un JSON plano: dos
documentos —una memoria de proyecto y una de reforma redactadas con años de
diferencia— pueden dar superficies distintas para el mismo campo, y **el
desacuerdo es información**; el segundo no puede pisar al primero.

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/extraccion/tipos-soportados` | Los `doc_type` que hay lector para leer hoy |
| `POST` | `/documents/{id}/extraer` | Lee el documento con el extractor de su tipo y **propone**. `422` si su tipo todavía no se lee, con la lista de los que sí. `409` solo si el documento propone **campos del edificio** y no está asignado a ningún activo. Volver a extraer **sustituye las pendientes** de ese documento y **no reabre las ya decididas** |
| `GET` | `/assets/{id}/propuestas?estado=` | Lo propuesto sobre el activo, sin aplicar. Cada fila trae `valor_actual` —lo que el activo tiene hoy— al lado: sin eso no se distingue «completa un hueco» de «contradice lo que había» |
| `POST` | `/assets/{id}/propuestas/decidir` | **El botón.** `{aceptar: [...], descartar: [...]}`. Se decide propuesta a propuesta: aceptar dos del **mismo campo** en la misma llamada es `422`, porque aplicarlas en orden dejaría ganando a la última por azar |

`[REQ]` Aceptar aquí **no toca `memoria_validada_at`**. Ese testigo dice «alguien
ha revisado la memoria de este edificio» y la ficha del activo lo enseña como
«validada»; aceptar una superficie suelta —que mañana puede salir de un plan de
autoprotección— no es eso. Quién aceptó qué, y de qué documento, queda en cada
fila de `propuesta_de_dato`, que es más fino y además es cierto. Para validar la
memoria entera sigue estando `POST /assets/{id}/memoria/validar`.

`[LIM]` La extracción de la memoria técnica es **determinista y sin red**: lee
las dos tablas y el esqueleto de epígrafes. Los **objetos del CAPEX no salen de
aquí** —la memoria los enumera en prosa y una sola sección reparte sus
elementos entre seis capítulos—: eso es clasificación semántica y sigue
pendiente de proveedor. Cada propuesta declara en `es_simulada` si la produjo
un lector de verdad o un simulacro.

#### Limitaciones que aporta la documentación `[REQ]`

La **tercera clase** de limitación del informe. Las dos que ya había salen de lo
que **no llegó** —una línea del checklist sin recibir, una pregunta sin
respuesta— y se calculan solas. Ésta es lo contrario: **el documento llegó, la
casilla está marcada, el expediente parece completo, y el documento dice que no
se puede confiar en él.**

El caso que lo hizo evidente: un plan de autoprotección redactado con las naves
vacías define los recorridos de evacuación suponiendo espacios diáfanos. En
cuanto entra un inquilino con estanterías, esas longitudes, salidas y
capacidades dejan de ser las que dice el plan. El documento está entregado y
completo; sin esto, la limitación solo la ve quien se lo lea entero, y en un
encargo con doscientos documentos eso no ocurre.

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/projects/{id}/limitaciones-documentales?estado=` | Lo que la documentación del encargo dice sobre su propia fiabilidad, con su motivo, su documento y su epígrafe |
| `POST` | `/projects/{id}/limitaciones-documentales/decidir` | `{aceptar: [...], descartar: [...]}`. **Solo las aceptadas llegan al informe**; descartar deja la fila con su testigo, no la borra |

`motivo` es un enumerado cerrado —`CADUCADO`, `INCOMPLETO`, `NO_VIGENTE`,
`DECLARADA`, `INCONSISTENTE`—. Una lista abierta acabaría con quince
redacciones del mismo motivo y sin forma de agruparlas en el informe.

**Cuelgan del encargo, no del activo.** Un plan cubre un complejo de seis naves
y una reserva sobre la evacuación no es de una nave concreta; el alcance del
informe es el encargo. `asset_id` queda opcional para cuando sí se sepa.

`GET /projects/{id}/report-limitations` devuelve **las tres clases juntas**, con
un campo `origen` (`CHECKLIST`, `PREGUNTA`, `DOCUMENTO`) que las distingue: «no
nos lo dieron» y «nos lo dieron y dice que no vale» no se redactan igual. El
snapshot del informe congela las tres, y de la tercera **solo las aceptadas**.

##### El lector de planes de autoprotección

Su trabajo principal **no es rellenar campos**: es producir limitaciones. Sus
reglas son las que se sostienen sobre cualquier plan y no las de un documento
concreto:

| Regla | Motivo | Por qué se puede sin IA |
|---|---|---|
| Fecha del plan + 3 años < hoy | `CADUCADO` | El RD 393/2007 obliga a revisar el plan al menos cada tres años. Es aritmética de fechas |
| No se lee la fecha | `INCOMPLETO` | Sin ella no se puede comprobar lo anterior, y «no consta» no es «está vigente» |
| El documento se declara resumen, borrador o copia | `NO_VIGENTE` | Un puñado de fórmulas cerradas que un redactor escribe cuando el documento no es el bueno |
| Casillas vacías o anonimizadas | `INCOMPLETO` | Se cuentan y se nombran las primeras; una limitación por etiqueta llenaría el informe de párrafos iguales |
| Una sección de salvedades, **si la trae** | `DECLARADA` | Se recoge **literal**. Parafrasearla cambiaría el alcance de una salvedad técnica por el de un resumen automático |

`[LIM]` La última regla no se puede dar por hecha: la Norma Básica fija
capítulos 1 a 9 y anexos, y **ninguno es «limitaciones»**. Se lee cuando está y
no se cuenta con ella. Hay tope —25— y al pasarse **se avisa**: un documento que
produce cincuenta limitaciones no tiene cincuenta, significa que el corte por
epígrafes ha fallado.

##### Los medios del capítulo 4, al inventario de equipo `[REQ]`

El capítulo 4 de la Norma Básica enumera los medios de protección contra
incendios del edificio. Teclearlos a mano después de que un documento los liste
es el trabajo repetido que el cliente pidió evitar.

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/projects/{id}/propuestas-de-equipo?estado=` | Los medios que la documentación declara, con su sistema técnico y su procedencia |
| `POST` | `/projects/{id}/propuestas-de-equipo/decidir` | `{aceptar: [{id, asset_id, zone_id?, quantity?, maintenance_months?}], descartar: [...]}`. **Aceptar crea la ficha de equipo** |

Es la **única de las tres decisiones que escribe una fila nueva** en vez de
actualizar una existente, y por eso pide el activo: el documento no lo dice. Un
plan cubre un complejo de seis naves y habla de «dieciséis hidrantes
distribuidos por el perímetro»; adivinar la nave lo haría pasar por sabido, y un
equipo en la nave equivocada es una visita perdida. La propuesta aceptada guarda
`equipment_id`, que cierra la trazabilidad al revés: desde la ficha del equipo
se llega al documento que lo declaró.

`[REQ]` **La cantidad puede venir vacía.** «Dieciséis hidrantes» son dieciséis;
«rociadores sobre la superficie de almacenamiento» son rociadores sin número.
Poner un 1 por omisión metería un uno en un inventario que alguien lee después
como cierto, así que se deja vacío y se dice cuántos vienen así.

`[REQ]` **La periodicidad de mantenimiento no se propone.** El plan declara
revisiones «trimestrales, semestrales, anuales y quinquenales **según el tipo de
equipo**» y no dice cuál le toca a cuál; repartirlas por analogía sería
inventarse el plan de mantenimiento del edificio. La pone quien acepta, o queda
vacía. `[PDV]` El RIPCI (RD 513/2017) fija periodicidades por tipo y podría
sembrar valores por omisión: exigiría transcribir una tabla reglamentaria que
nadie de este proyecto ha validado.

##### El mantenimiento preventivo en la ficha de equipo `[REQ]`

Faltaba, y de una instalación de protección contra incendios es lo primero que
se pregunta: no «cuántos extintores hay» sino «cuándo se revisaron».

`equipment` gana `maintenance_months` y `last_maintenance_date`, y
`next_maintenance_due` **se genera** a partir de las dos —igual que
`end_of_life_year`, y por lo mismo: lo que se guarda no caduca y lo derivado no
se teclea—. En **meses** y no un enumerado de periodicidades, porque un contrato
de mantenimiento puede decir «cada cuatro meses» y un enumerado obligaría a
redondear al valor de al lado.

`GET /projects/{id}/equipment` gana `solo_mantenimiento_vencido`, que es **otra
pregunta** que `solo_vencidos`: un extintor de dos años sin revisar desde hace
dieciocho meses no está al final de su vida útil y sí está fuera de norma. Son
dos hallazgos con presupuestos distintos —uno se sustituye, el otro se revisa—,
y un filtro único escondería justo el caso que se busca. Se compara con
`current_date` en SQL, no contra un valor guardado.

#### Confidencialidad por tipo de documento `[REQ]`

Un `PLAN_AUTOPROTECCION` nace con confidencialidad **`RESTRINGIDO`** y no
`INTERNO` —lo pone `CONFIDENCIALIDAD_POR_OMISION`—: lleva procedimientos de
emergencia, puntos de reunión, ubicaciones de medios y datos de las personas con
responsabilidad en una emergencia. Es un valor por omisión, no una imposición:
quien sube puede mandar otro.

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/documents/confidencialidad-por-tipo` | Qué tipos nacen por encima de `INTERNO`, **con el motivo escrito** |

Se expone para que la pantalla de subida lo diga **antes** de subir. Un nivel que
aparece solo en la ficha, ya guardado, no informa la decisión de quien sube:
informa la sorpresa de quien intenta descargarlo. Y solo salen las excepciones:
enumerar catorce tipos para decir lo mismo de trece haría que la excepción no se
viera.

`[REQ]` **Un documento `RESTRINGIDO` no se envía a ningún proveedor de IA**, ni
con la revisión del encargo activada. Esto faltaba: la comprobación de
confidencialidad estaba en `descargar()` y no en la revisión, así que un
documento que un consultor del equipo no puede ni abrir sí se podía mandar a un
tercero con solo el interruptor del encargo encendido. `POST
/documents/{id}/ai-review` responde `403` diciendo qué hacer.

`[REC]` **No hay un segundo interruptor.** Si en un encargo concreto hay que
revisarlo, se baja su clasificación a mano —lo cual queda en `audit_log` con
quién y cuándo— y entonces se revisa. Una decisión así tiene que dejar rastro; un
interruptor más lo convertiría en un clic sin memoria.

### Resumen del CAPEX `[REQ]`

Cuatro preguntas distintas, cuatro consultas. La rejilla de hallazgos contesta
«qué hay que hacer»; estos cortes contestan lo que se pregunta en la reunión y
que hasta ahora se sumaba a mano.

| Método | Ruta | Pregunta que contesta |
|---|---|---|
| `GET` | `/projects/{id}/capex/summary/by-concept?asset_id=` | **En qué se va el dinero.** Ordenado de mayor a menor. Los conceptos sin importe no salen; las líneas sin concepto salen como `SIN_CONCEPTO` |
| `GET` | `/projects/{id}/capex/summary/by-horizon?asset_id=` | **Cuándo hay que pagarlo.** En orden de plazo, no de importe. Los cinco plazos salen siempre, con ceros |
| `GET` | `/projects/{id}/capex/summary/by-chapter?asset_id=` | **Qué parte del edificio.** Un hallazgo codificado en un objeto (nivel 3) suma en su **capítulo** (nivel 2) |
| `GET` | `/projects/{id}/capex/summary/by-asset` | **Qué edificio.** Un activo por fila aunque no tenga actuaciones, con ceros. **Sin `asset_id`: es el índice, no un corte** |

`[REQ]` **Los cuatro suman lo mismo, y hay una prueba que lo impone.** Cuatro
gráficos en la misma pantalla que no cuadran destruyen la confianza en los
cuatro, y el descuadre no lo ve nadie hasta que el cliente suma con la
calculadora.

Esa prueba encontró uno: `by-horizon` **no excluía los hallazgos borrados**. El
borrado es lógico —`deleted_at`, porque borrar del informe algo que se llegó a
valorar deja a nadie sabiendo que existió—, así que sus líneas siguen en la
tabla; la consulta unía `capex_item` con `time_horizon` sin pasar por `finding`
y las contaba. El mismo encargo sumaba una cosa por horizonte y otra por activo.
No se veía porque nada ponía los dos cortes en la misma pantalla.

`[REQ]` `asset_id` está **en los tres cortes que reparten, y no en el cuarto**.
Son dos preguntas que se hacen en la misma reunión: agregado dice cómo se
comporta el parque —si el problema es mantenimiento diferido o normativa—; por
activo dice qué le pasa a **ese** edificio, que es sobre el que se negocia el
precio. Un parque con un 40 % de normativa puede tenerlo concentrado en una sola
nave, y agregado eso no se ve. El filtro alcanza los tres a la vez porque las
tres preguntas se hacen del mismo edificio: no sirve de nada saber en qué se va
el dinero de una nave si el «cuándo hay que pagarlo» de al lado sigue siendo el
del parque entero. Los tres cortes filtrados **suman lo mismo entre sí**, y hay
una prueba que lo impone.

`[REQ]` **`by-asset` no acepta `asset_id`, a propósito.** Es el corte que
contesta «qué edificio», y filtrarlo por un edificio lo dejaría con una fila:
deja de ser un reparto. Además es el que da la lista con la que la pantalla
construye el desplegable y el total del encargo contra el que se calcula «qué
parte del CAPEX es este activo», de modo que tiene que seguir viéndose entero
mientras los otros tres están filtrados. En la pantalla, el bloque «Qué
edificio» **desaparece** cuando hay un activo elegido, en vez de quedarse con
una sola barra al 100 %.

El activo se filtra por el **hallazgo**, no por la línea: `[REQ]` P-44, una
actuación recurrente tiene varias líneas y un solo edificio.

`[REC]` `asset_id` **solo filtra**, como en la matriz de riesgos: un activo de
otro encargo devuelve una lista vacía, no un `404`. Es la convención de la casa
para los filtros de lectura, y la pantalla construye el desplegable con los
activos del propio encargo.

`[LIM]` `SIN_CONCEPTO` **no es un código del catálogo**: es la etiqueta con la
que se agrupa lo que nadie clasificó. Que nadie lo haya clasificado es un dato,
no un hueco, y si desapareciera del reparto la suma no cuadraría con el total.

### Inventario de equipo `[REQ]` §7 / P-15

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/projects/{id}/equipment?asset_id=&technical_system_id=&q=&solo_vencidos=&solo_mantenimiento_vencido=` | `q` busca sobre etiqueta, tipo, fabricante, modelo, nº de serie y notas (GIN sobre `search_vector`). `solo_vencidos` compara contra el **año en curso en SQL**, no contra un valor guardado |
| `POST` | `/projects/{id}/equipment` | El activo debe pertenecer al encargo: si no, `404` |
| `GET`/`PATCH`/`DELETE` | `/equipment/{id}` | `DELETE` es lógico: la ficha se escribió en una visita a la que no se vuelve |
| `GET` | `/projects/{id}/equipment/import/plantilla.xlsx` | Libro vacío **con los activos del encargo y los 14 sistemas dentro**, en una hoja aparte |
| `POST` | `/projects/{id}/equipment/import/preview` | Sube la hoja y devuelve fila a fila qué va a pasar. **No escribe nada** |
| `POST` | `/projects/{id}/equipment/import` | Aplica. Exige `confirmar=true` y **reanaliza la hoja** en vez de fiarse de lo previsualizado |

Cada respuesta incluye, **calculados en la lectura y nunca almacenados** (P-15):
`end_of_life_year`, `remaining_life_years` (puede ser negativo), `vencido`, `horizonte_code`,
`horizonte_name` y `vida_resumen`, una frase lista para mostrar. `remaining_life_years` **se rechaza
como campo de entrada** (`extra="forbid"`) en vez de ignorarse: un campo aceptado y descartado
produce fichas que parecen completas y no lo están. Ver la `[LIM]` de
[`04-modelo-de-datos`](./04-modelo-de-datos.md) sobre por qué no puede ser una columna generada.

El plazo de reposición sale de los rangos de `time_horizon`, no de umbrales propios del módulo.

**La importación no sobrescribe nada por su cuenta.** Una fila cuya etiqueta ya existe en ese activo
sale como `YA_EXISTE` y se omite; actualizarla exige `actualizar_existentes=true`, que es una casilla
que alguien marca. Un activo que no está en el encargo es un **error de fila**, no una invitación a
crearlo, y un sistema técnico que no casa con el catálogo **no se aproxima al más parecido**: el
equipo entra sin clasificar y el aviso lo cuenta. Las columnas que no se reconocen se enumeran en la
respuesta en vez de ignorarse: una cabecera mal escrita perdería el dato sin que nadie se enterase.

`[LIM]` Solo se lee la primera hoja del libro; la respuesta dice cuántas tenía.
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
| `GET` | `/photos/{id}/download?variante=` | `302` a URL firmada **si el almacén sabe firmar**; el binario si no (adaptador de disco: desarrollo y suite). La autorización se comprueba **antes** de firmar. `403` si la foto está en `CUARENTENA` o `PURGADA`. Se audita `PHOTO_URL_ISSUED`, no `PHOTO_DOWNLOADED`: con la redirección el servidor sabe que **autorizó**, no que el binario saliera |
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
| `POST` | `/projects/{id}/findings` | **Crea hallazgo y línea de CAPEX en una operación** `[REC]`. Para una actuación **recurrente**, se añaden más líneas al mismo hallazgo, una por plazo `[REQ]` P-44 |
| `GET` | `/projects/{id}/findings` | Filtros: `asset_id`, `zone_id`, `capex_code_id` (con subárbol), `risk_level_id[]`, `capex_concept_id[]`, `tenant_recoverable`, `status[]`, `owner_user_id`, `has_photos`, `q` |
| `GET`/`PATCH`/`DELETE` | `/findings/{id}` | |
| `POST` | `/findings/{id}/transitions` | Cambio de estado con guardas |
| `POST` | `/findings/from-photo` | **Atajo de campo**: hereda activo, zona y sistema de la foto `[REC]` |
| `GET`/`POST` | `/findings/{id}/recommendations` | |
| `GET`/`POST` | `/projects/{id}/capex-items` | |
| `GET`/`PATCH`/`DELETE` | `/capex-items/{id}` | Cualquier cambio devuelve **los totales recalculados** `[REQ]` |
| `POST` | `/capex-items/bulk-update` | Cambio masivo de porcentajes, año, prioridad, recuperabilidad |
| `POST` | `/capex/preview-calculation` | **Sin persistir**: entradas → desglose paso a paso. Alimenta el panel «cómo se calcula» `[REC]` |
| `GET` | `/projects/{id}/capex/summary?group_by=` | `asset` · `capex_code` · `zone` · `risk` · `concept` · **`horizon`** · `year` · `priority` · `tenant_recoverable` `[REQ]`. Con `horizon` devuelve las cinco categorías, cada línea en una sola |
| `GET` | `/projects/{id}/capex/scenarios` | Totales bajo / probable / alto |
| `POST` | `/projects/{id}/capex/exports` | Exportación del CAPEX. Detalle abajo → `202` `[REQ]` P-31 |
| `GET` | `/capex/exports/{id}` | Estado del trabajo y, al terminar, URL firmada de descarga con caducidad |

### Exportación del CAPEX a XLSX `[REQ]` P-31

El cliente ha pedido este endpoint con un uso concreto —**adjuntar el fichero en envíos fuera de la
plataforma**—, de modo que la hoja `CAPEX` reproduce el layout de la tabla del informe
([`11`](./11-capex-precios.md) §16.8bis) y no un volcado plano.

```json
POST /api/v1/projects/{id}/capex/exports
{
  "format": "xlsx",                    // xlsx | csv
  "scope": "PROJECT",                  // PROJECT | FILTERED | REPORT_VERSION
  "report_version_id": null,           // obligatorio si scope = REPORT_VERSION
  "filters": null,                     // los mismos que /capex-items, si scope = FILTERED
  "sheets": ["CAPEX", "RESUMEN", "CAPEX_DETALLE",
             "TRAZABILIDAD", "AGREGADOS", "CATALOGOS"],
  "include_other_horizon": true,       // la quinta columna. Por defecto TRUE [REQ] P-37
  "include_taxes": true,
  "locale": "es-ES",                   // rige encabezados, catálogos y formato de número
  "filename_template": "[Proyecto]_CAPEX_[Fecha]_v[N].xlsx"
}
→ 202 { "export_id": "…", "status": "QUEUED" }
```

| Regla | Comportamiento |
|---|---|
| `scope = REPORT_VERSION` | Los datos salen del **`data_snapshot` congelado**, no de las tablas vivas: el XLSX cuadra con el PPTX emitido `[REC]` |
| `scope = FILTERED` sin `filters` | `422`. No se exporta «lo visible» a ciegas |
| Líneas con `price_status <> VALIDADO` | **Se exportan, marcadas** en una columna propia. Ocultarlas falsearía el total |
| Auditoría | Toda respuesta `202` genera `EXPORT_CREATED` con actor, alcance, nº de líneas e importe total `[REC]` |
| Descarga | URL firmada con caducidad corta; la descarga en sí también se audita |
| Asíncrono | Cola `io`. Es un trabajo de segundos, pero con seis hojas y agregados no se resuelve dentro de la petición `[LIM]` |

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
  "time_horizon_code": "CORTO",     // uno solo: CORTO|MEDIO|LARGO|MEJORAS|OTRO
  "amount": "48500.00",             // base imponible; los impuestos van encima
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

### Sugerencias `[REQ]` — ver [`19`](./19-sugerencias.md)

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/suggestions` | **Cualquier usuario autenticado**, incluido `LECTOR` |
| `GET` | `/suggestions/mine` | Las del usuario, con su estado y la respuesta recibida `[REQ]` P-40 |
| `GET` | `/suggestions?status=&type=&project_id=` | **Solo con `GESTIONAR_SUGERENCIAS`**. Para el resto, `403` |
| `GET` | `/suggestions/{id}` | La RLS decide. Si lleva contexto de proyecto, abrirla audita `SUGGESTION_VIEWED` |
| `POST` | `/suggestions/{id}/transitions` | `{to, resolution_note, duplicate_of_id}`. `RECHAZADA` sin motivo → `422` |
| `POST` | `/suggestions/{id}/apply` | Solo desde `ACEPTADA`, si no `409`. Crea el cambio y enlaza `applied_entity_id` |
| `GET`/`POST` | `/suggestions/{id}/comments` | Hilo autor ↔ administrador |
| `GET` | `/suggestions/summary` | Contadores para la insignia del menú |

`[REC]` **`POST /suggestions` ignora `organization_id` y `created_by` si vienen en el cuerpo**: se
toman siempre del token. Es el fallo clásico de un endpoint abierto a todos los roles, y hay una
prueba que lo cubre.

`[REQ]` Un usuario sin permiso que pida una sugerencia ajena recibe **`404`, no `403`**: no se
confirma que exista, igual que entre organizaciones.

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

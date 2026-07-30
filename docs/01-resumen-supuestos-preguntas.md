# 1. Resumen ejecutivo · 2. Supuestos · 3. Preguntas abiertas

> **Convención de etiquetas usada en toda la documentación**
>
> | Etiqueta | Significado |
> |---|---|
> | `[REQ]` | Requisito solicitado explícitamente por el cliente |
> | `[SUP]` | Supuesto adoptado por falta de información. Modificable |
> | `[REC]` | Recomendación técnica propia, no solicitada |
> | `[LIM]` | Limitación técnica real, conocida y verificable |
> | `[PDV]` | Pendiente de validar (legal, técnica o de negocio) |

---

## 1. Resumen ejecutivo

### 1.1. Qué se propone

Una aplicación web empresarial, multi-organización, para gestionar el ciclo completo de una
**due diligence técnica inmobiliaria (TDD)**: desde la apertura del proyecto y la planificación de
la visita, hasta la emisión de un informe PowerPoint generado a partir de la plantilla corporativa
del propio proyecto.

El producto se articula en cuatro dominios funcionales que corresponden a los cuatro bloques
solicitados:

| Dominio | Función | Valor para el consultor |
|---|---|---|
| **Proyecto** | Cliente, activos, equipo, estados, trazabilidad | Un único lugar de verdad por encargo |
| **Evidencia** | Fotografías y documentos, clasificados y versionados | Se acaba el «carpetas en el escritorio + WhatsApp» |
| **Diagnóstico y CAPEX** | Inventario, incidencias, partidas y precios trazables | El CAPEX deja de ser un Excel huérfano y auditable a mano |
| **Informe** | Plantilla PPTX propia, mapeo, generación versionada | Horas de maquetación manual convertidas en minutos |

### 1.2. Tesis del diseño

Cuatro decisiones estructurales sostienen toda la propuesta:

1. **El original nunca se toca.** Fotografías, documentos y plantillas PPTX se almacenan como
   objetos inmutables. Renombrar, editar, anotar o generar produce *siempre* un derivado nuevo con
   su propio linaje. Esto no es una funcionalidad: es una invariante del sistema, garantizada en
   la capa de almacenamiento y no solo en la interfaz. `[REQ]`

2. **El precio es un dato con procedencia, no un número.** Cada importe de CAPEX arrastra su
   fuente, URL, fecha de consulta, ámbito geográfico, alcance incluido/excluido, tratamiento fiscal
   y el usuario que lo validó. Un precio externo entra al sistema en estado
   `pendiente_validacion` y **ningún proceso automático lo promueve a validado**. `[REQ]`

3. **El informe es una fotografía inmutable de los datos.** Emitir un informe congela un
   *snapshot* de los datos usados (JSONB) más el hash SHA-256 del PPTX resultante. Cambiar datos
   después no altera lo emitido: crea una versión nueva. Esto es lo que hace el informe defendible
   frente a un cliente o un tribunal. `[REQ]`

4. **Las fuentes de precios son adaptadores, no código del núcleo.** El motor de CAPEX conoce una
   interfaz `PriceSourceAdapter` y nada más. Añadir, desactivar o sustituir una fuente es
   registrar/desregistrar un adaptador, sin tocar el cálculo. `[REQ]`

### 1.3. Arquitectura en una frase

Monolito modular en **Python/FastAPI** (dominio + API) sobre **PostgreSQL** con *Row Level
Security* por organización, **almacenamiento de objetos compatible S3** para binarios,
**workers Celery** para trabajos pesados (derivados de imagen, EXIF, antivirus, generación PPTX,
previsualización) y un **frontend React + TypeScript** como PWA responsive.

La justificación completa —y las alternativas descartadas— está en
[`03-arquitectura.md`](./03-arquitectura.md). El resumen del porqué de Python: la generación de
PPTX conservando el formato corporativo es **el riesgo número uno del proyecto**, y la biblioteca
más madura y con licencia permisiva para esa tarea (`python-pptx`) es Python. Elegir Python en el
backend evita mantener dos runtimes solo por ese servicio.

### 1.4. Qué entra en el MVP y qué no

**MVP (≈14–18 semanas con el equipo supuesto en §2):** autenticación, clientes, proyectos,
activos, equipo, repositorio fotográfico con renombrado no destructivo, inventario, incidencias,
CAPEX con precio manual y referencias registradas, carga de plantilla PPTX, mapeo básico de
marcadores, generación de informe, versionado y auditoría de operaciones críticas.

**Fuera del MVP, por decisión consciente:** consulta automatizada multi-fuente de precios, modo
offline completo, anotación avanzada de imágenes, cualquier función de IA, integraciones
corporativas y analítica avanzada. Detalle y razones en
[`14-mvp-plan-riesgos.md`](./14-mvp-plan-riesgos.md).

### 1.5. Los tres riesgos que hay que mirar de frente

| Riesgo | Por qué importa | Mitigación |
|---|---|---|
| **Fidelidad del PPTX** | Si el informe sale «descuadrado», el producto no se usa | Corpus de plantillas reales desde la semana 1; contrato de plantilla documentado; previsualización obligatoria; plan B comercial identificado |
| **Legalidad de las fuentes de precios** | El scraping puede ser ilícito o violar condiciones de uso | Ninguna fuente se activa sin validación legal previa. MVP = manual + catálogo propio licenciado |
| **Detección de desbordamiento de texto** | `python-pptx` no renderiza; no hay «verdad» sobre si un texto cabe | Estimación por métricas de fuente (`fontTools`) + previsualización real vía LibreOffice headless. Se declara como heurística, no como garantía `[LIM]` |

---

## 2. Supuestos adoptados

Todos son modificables. Cada uno indica el impacto de cambiarlo.

### 2.1. Negocio y organización

| # | Supuesto | Impacto si cambia |
|---|---|---|
| S-01 | El producto es **SaaS multi-organización** con separación lógica de datos. `[SUP]` | Alto. Si es mono-organización on-premise, se simplifica RLS, facturación y onboarding |
| S-02 | Volumen inicial: **≤ 20 organizaciones, ≤ 50 usuarios concurrentes, ≤ 300 proyectos/año** | Medio. Dimensionamiento de infraestructura y decisión de sharding |
| S-03 | Un proyecto típico contiene **1–15 activos**, **300–1.500 fotografías**, **50–300 incidencias** y **30–200 partidas CAPEX** | Alto para la estrategia de fotografías y paginación |
| S-04 | Peso medio por fotografía **3–8 MB** (móvil moderno). Límite duro por archivo: **50 MB** | Medio. Afecta a coste de almacenamiento y tiempos de carga |
| S-05 | Mercado principal **España**, moneda **EUR**, IVA español configurable; arquitectura preparada para otros países | Medio. Multi-país exige modelo fiscal más rico |
| S-06 | Idioma de interfaz **español**, con i18n desde el día uno (claves, no cadenas incrustadas) | Bajo si se prepara desde el inicio; alto si se pospone |
| S-07 | Equipo de desarrollo: **1 tech lead + 2 full stack + 1 diseñador a media jornada + 1 QA a media jornada** | Alto sobre el calendario del plan por fases |

### 2.2. Producto y flujo de trabajo

| # | Supuesto | Impacto si cambia |
|---|---|---|
| S-08 | El flujo de aprobación es de **un solo nivel**: un revisor aprueba antes de emitir | Medio. Multi-nivel o firma electrónica requiere motor de workflow |
| S-09 | La **plantilla PPTX se prepara siguiendo un contrato documentado** (marcadores `{{...}}` en el cuerpo y directivas en las notas del orador). No se soporta plantilla arbitraria sin preparación | **Muy alto.** Es la asunción que hace viable el Bloque 4. Ver [`11-pptx.md`](./11-pptx.md) |
| S-10 | Formatos de imagen aceptados en MVP: **JPEG, PNG, WebP, HEIC/HEIF** (conversión a JPEG para derivados). RAW y TIFF fuera de MVP | Medio. RAW multiplica coste de proceso y almacenamiento |
| S-11 | Durante la visita hay **conectividad intermitente pero existente** (4G en la mayoría de edificios). El offline completo es fase posterior | **Alto.** Si hay sótanos/plantas técnicas sin cobertura y es crítico, el offline sube a MVP |
| S-12 | El cliente **no dispone hoy** de una base de precios licenciada integrable por API | Alto. Si la tiene, el importador de catálogo propio se prioriza y el CAPEX gana valor inmediato |
| S-13 | No se requiere firma electrónica cualificada (eIDAS) sobre el informe emitido | Medio-alto. La firma cualificada implica proveedor externo y cambios en el flujo de emisión |

### 2.3. Técnicos y de explotación

| # | Supuesto | Impacto si cambia |
|---|---|---|
| S-14 | Despliegue **contenedorizado** (Docker/OCI) sobre un único proveedor cloud europeo, **una región**, con posibilidad de migrar | Medio. Multi-región cambia disponibilidad y coste |
| S-15 | Residencia de datos en la **UE** | Alto en la elección de proveedor |
| S-16 | Autenticación propia (email + contraseña + TOTP opcional) en MVP, con interfaz preparada para **OIDC/SSO** | Medio. SSO obligatorio desde el inicio adelanta la integración de un IdP |
| S-17 | Objetivos de continuidad: **RPO 15 min, RTO 4 h**, disponibilidad **99,5 %** mensual en MVP | Medio-alto. 99,9 % exige redundancia activa y encarece la infraestructura |
| S-18 | Retención de datos de proyecto: **7 años** desde el cierre, salvo instrucción contractual distinta | Medio. Afecta a coste de almacenamiento y a la política de purga |
| S-19 | Navegadores objetivo: **dos últimas versiones** de Chrome, Edge, Firefox y Safari; **iOS ≥ 16**, **Android ≥ 11** | Bajo-medio |
| S-20 | Los importes se calculan con **decimal exacto** (`NUMERIC`), nunca con coma flotante, y se redondean solo en presentación y en el total de partida | Bajo, pero no negociable para la integridad del CAPEX |

> Las cifras de rendimiento, disponibilidad y volumen de los requisitos no funcionales son
> **supuestos justificados**, no compromisos contractuales. Ver
> [`16-requisitos-no-funcionales.md`](./16-requisitos-no-funcionales.md), donde se distingue
> explícitamente lo confirmado de lo recomendado.

---

## 3. Preguntas abiertas

Ordenadas por impacto sobre la arquitectura y el calendario. **Ninguna bloquea el inicio del
trabajo**: para cada una hay un supuesto operativo en §2 con el que se puede avanzar.

### Impacto crítico — condicionan decisiones estructurales

| # | Pregunta | Por qué es crítica | Se avanza mientras con |
|---|---|---|---|
| P-01 | ¿Pueden facilitarse **2–3 plantillas PPTX reales** ya usadas en informes emitidos, incluyendo la más compleja? | Determina la viabilidad del Bloque 4 y el esfuerzo real. Sin ellas, el mayor riesgo del proyecto queda sin medir | Plantillas sintéticas propias que imitan estructuras habituales de TDD |
| P-02 | ¿**SaaS multi-cliente** o instalación única para una sola consultora? | Cambia multi-tenancy, RLS, onboarding, facturación y el modelo de permisos | S-01: SaaS multi-organización |
| P-03 | ¿Se dispone de **licencia de alguna base de precios** (o de un catálogo propio histórico) y en qué formato? | Es la diferencia entre un CAPEX con precios reales y un formulario vacío | S-12: solo entrada manual en MVP |
| P-04 | ¿Cuál es el **nivel real de conectividad** durante las visitas y se considera el offline un requisito de aceptación? | El offline con resolución de conflictos es el componente más caro del backlog. Meterlo tarde es rehacer el frontend | S-11: conectividad intermitente, PWA con reintentos |
| P-05 | ¿**Proveedor cloud y región** obligatorios? ¿Hay restricciones de residencia por contrato con clientes finales? | Condiciona almacenamiento, backups y compromisos con el cliente final | S-14/S-15: contenedores, cloud UE, una región |

### Impacto alto — condicionan alcance del MVP

| # | Pregunta | Por qué importa | Se avanza mientras con |
|---|---|---|---|
| P-06 | ¿Es obligatorio **SSO corporativo** (Azure AD/Entra, Google Workspace, Okta) desde el primer despliegue? | Adelanta o retrasa la integración con un IdP y afecta al alta de usuarios | S-16: auth propia + interfaz OIDC-ready |
| P-07 | ¿Cuántos **niveles de revisión y aprobación** existen y quién tiene la última firma? ¿Se exige firma electrónica? | Un workflow de varios niveles no se improvisa sobre uno de un nivel | S-08/S-13: un nivel, sin firma cualificada |
| P-08 | ¿Existe una **taxonomía corporativa de sistemas técnicos** (codificación propia, o basada en un estándar como Uniclass/Omniclass/UNE)? | Si existe, se carga como catálogo maestro; si no, hay que diseñarla y luego migrar datos | Taxonomía propia editable, basada en la clasificación del Bloque 2 |
| P-09 | ¿Qué **convención de nomenclatura** de fotografías se usa hoy y es obligatorio reproducirla? | La plantilla de nombres es configurable, pero conviene arrancar con la real | `[Proyecto]_[Activo]_[Sistema]_[Zona]_[NNN].[ext]` |
| P-10 | ¿El **modelo de costes CAPEX** (indirectos, honorarios, contingencia, impuestos) sigue una fórmula ya establecida, y en qué orden se aplican los porcentajes? | El orden de aplicación cambia el total. Debe coincidir con lo que el cliente ya usa | Cascada documentada en [`10-capex-precios.md`](./10-capex-precios.md) §2 |

### Impacto medio — refinan el diseño

| # | Pregunta | Se avanza mientras con |
|---|---|---|
| P-11 | ¿Se requiere **multi-moneda dentro de un mismo proyecto** o basta una moneda por proyecto? | Una moneda por proyecto, con campo de moneda por partida para el futuro |
| P-12 | ¿Formatos de foto a soportar? ¿Llegan **HEIC** de iPhone o **RAW** de cámara réflex? | S-10: JPEG/PNG/WebP/HEIC |
| P-13 | ¿Qué **proveedor de mapas y geocodificación** se prefiere y con qué presupuesto? | Adaptador `MapProvider` con MapLibre + teselas configurables |
| P-14 | ¿Existen **integraciones corporativas** previstas (ERP, CRM, GMAO/CMMS, gestor documental, SharePoint)? | Ninguna en MVP; API REST documentada como punto de extensión |
| P-15 | ¿**Periodos de retención** y obligaciones de borrado pactadas con clientes finales? | S-18: 7 años, purga lógica configurable |
| P-16 | ¿Se prevé exportar/importar contra **Excel corporativos existentes** con formato fijo? | Exportación XLSX/CSV con esquema propio |
| P-17 | ¿Debe el sistema soportar **subcontratistas externos** con acceso limitado a un solo activo? | Rol `LECTOR` con permisos por proyecto; el alcance por activo se modela pero se pospone |
| P-18 | ¿Hay **identidad visual / design system** corporativo que deba respetar el frontend? | Sistema propio sobre primitivas accesibles, tematizable |

### Impacto bajo — no afectan al diseño, sí a la puesta en marcha

| # | Pregunta |
|---|---|
| P-19 | ¿Presupuesto y fecha objetivo de la primera visita real usando la herramienta? |
| P-20 | ¿Idiomas adicionales previstos y en qué plazo (inglés para clientes internacionales)? |
| P-21 | ¿Existe una política corporativa de contraseñas/MFA que deba replicarse? |
| P-22 | ¿Quién asume el rol de *product owner* y con qué disponibilidad para validar entregas por fase? |

---

## Índice de la documentación

| Doc | Contenido | Entregables cubiertos |
|---|---|---|
| [`01-resumen-supuestos-preguntas.md`](./01-resumen-supuestos-preguntas.md) | Este documento | 1, 2, 3 |
| [`02-alcance-y-flujos.md`](./02-alcance-y-flujos.md) | Alcance funcional y flujos de usuario | 4, 5 |
| [`03-arquitectura.md`](./03-arquitectura.md) | Arquitectura recomendada, alternativas y diagrama | 6, 7 |
| [`04-modelo-de-datos.md`](./04-modelo-de-datos.md) | Entidades, relaciones, índices y diagrama ER | 8, 9 |
| [`05-api.md`](./05-api.md) | Diseño de APIs principales | 10 |
| [`06-roles-permisos.md`](./06-roles-permisos.md) | Matriz de roles y permisos | 11 |
| [`07-historias-y-criterios.md`](./07-historias-y-criterios.md) | Historias de usuario y criterios Given/When/Then | 12, 13 |
| [`08-ux-pantallas.md`](./08-ux-pantallas.md) | Bocetos textuales de las 19 pantallas | 14 |
| [`09-fotografias.md`](./09-fotografias.md) | Estrategia de fotografías | 15 |
| [`10-capex-precios.md`](./10-capex-precios.md) | Motor de CAPEX y normalización de precios | 16 |
| [`11-pptx.md`](./11-pptx.md) | Lectura, mapeo y generación de PPTX | 17 |
| [`12-seguridad-privacidad-auditoria.md`](./12-seguridad-privacidad-auditoria.md) | Seguridad, privacidad, RGPD y auditoría | 18 |
| [`13-pruebas.md`](./13-pruebas.md) | Estrategia de pruebas | 19 |
| [`14-mvp-plan-riesgos.md`](./14-mvp-plan-riesgos.md) | MVP, plan por fases y riesgos | 20, 21, 22 |
| [`15-estructura-carpetas.md`](./15-estructura-carpetas.md) | Estructura inicial del proyecto | 23 |
| [`16-requisitos-no-funcionales.md`](./16-requisitos-no-funcionales.md) | Objetivos verificables (§10 del encargo) | — |

El entregable **24 (código inicial del MVP)** se aborda en la siguiente iteración, tras la
validación de este diseño, conforme a §16 del encargo.

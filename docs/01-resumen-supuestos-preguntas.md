# 1. Resumen ejecutivo · 2. Supuestos · 3. Preguntas abiertas

> **Convención de etiquetas usada en toda la documentación**
>
> | Etiqueta | Significado |
> |---|---|
> | `[REQ]` | Requisito solicitado explícitamente |
> | `[SUP]` | Supuesto adoptado por falta de información. Modificable |
> | `[REC]` | Recomendación propia, no solicitada |
> | `[LIM]` | Limitación técnica real, conocida y verificable |
> | `[PDV]` | Pendiente de validar (legal, técnica o de negocio) |

---

## 1. Resumen ejecutivo

### 1.1. Qué se propone

Una aplicación web empresarial, multi-organización, para gestionar el ciclo completo de una
**due diligence técnica inmobiliaria (TDD)**: desde la apertura del encargo y la solicitud de
documentación, hasta la defensa del informe frente a la otra parte.

El producto se articula en cinco dominios:

| Dominio | Función | Valor para el consultor |
|---|---|---|
| **Encargo** | Proyecto, cliente, activos, equipo y **fases del proceso** | Un único lugar de verdad, con el estado real del trabajo a la vista |
| **Evidencia** | Fotografías y documentos clasificados y versionados | Se acaba el «carpetas en el escritorio + WhatsApp» |
| **Diagnóstico y CAPEX** | Hallazgos codificados por zona, riesgo, concepto y horizonte | La tabla de CAPEX deja de ser un Excel huérfano y sin trazabilidad |
| **Precios** | Referencias con procedencia y validación humana | Cada importe se puede defender ante el cliente |
| **Informe** | Plantilla PPTX propia, mapeo, generación versionada | Horas de maquetación convertidas en minutos |

### 1.2. Las cinco decisiones que sostienen el diseño

1. **Estado y fases son ejes distintos.** El `estado` del proyecto (borrador → archivado) describe el
   ciclo administrativo del encargo. Las **fases** (§3.1.5: solicitud de documentación, VDR, visita,
   Q&A, Red Flag/CAPEX, Full Report, presentación, defensa) describen el trabajo real, **se eligen a
   la carta al dar de alta el proyecto** y avanzan en paralelo. Mezclarlas en un solo campo sería el
   error de modelado más caro de este proyecto. `[REC]`

2. **La fila que rellena el consultor es una sola cosa.** En la especificación revisada, el hallazgo
   y la partida CAPEX son la misma línea de trabajo: código, zona, descripción, riesgo, comentarios,
   **horizonte e importe**, concepto y recuperabilidad. La interfaz presenta **una fila**; por debajo
   se persisten `Finding` y `CapexItem`. `[REQ]` **P-44** confirmó que la relación es **1:N**: una
   actuación recurrente —que hace falta ahora y otra vez a diez años— genera **una línea por plazo**,
   y la tabla la muestra como una sola fila con dos columnas rellenas. `[REC]`

3. **Los catálogos son datos, no código.** Seis tipologías, veinte zonas dependientes de ellas, un
   árbol de 125 códigos, cuatro grados de riesgo con definición escrita y cinco horizontes. Todo vive
   en tablas versionadas y editables, no en enumerados compilados: cambiar un capítulo del árbol no
   puede exigir un despliegue, y tres categorías siguen pendientes de desglose.

4. **El original nunca se toca.** Fotografías, documentos y plantillas PPTX son objetos inmutables.
   Renombrar, anotar o generar produce siempre un derivado nuevo. `[REQ]`

5. **El precio es un dato con procedencia, no un número.** Fuente, URL, fecha de consulta, ámbito,
   alcance incluido y excluido, tratamiento fiscal, y el usuario que lo validó. Ningún proceso
   automático promueve un precio a validado. `[REQ]`

### 1.3. Arquitectura en una frase

Monolito modular en **Python/FastAPI** sobre **PostgreSQL 16** con *Row Level Security* por
organización, **almacenamiento de objetos compatible S3** para binarios, **workers Celery** para
trabajos pesados y **React + TypeScript** como PWA responsive. Justificación y alternativas
descartadas en [`03-arquitectura.md`](./03-arquitectura.md).

### 1.4. Los tres riesgos que hay que mirar de frente

| Riesgo | Por qué importa | Mitigación |
|---|---|---|
| **Fidelidad del PPTX** | Si el informe sale descuadrado, el producto no se usa | **Riesgo ya medido** sobre las plantillas reales (doc 18 §18.7): baja de *alta* a *media* porque no hay gráficos, SmartArt ni OLE, y hay una sola estructura. Sube por la ausencia de marcadores de posición y las fuentes Gotham |
| **Precios que se desfasan** | `[REQ]` P-06 cerrada sin fuente externa: los precios se mantienen a mano, y **nada los actualiza solo** | Catálogo interno importable y reutilizable entre proyectos, más el módulo de **Sugerencias** tipo `PRECIO`, que es la vía por la que una corrección detectada en campo llega al catálogo del resto del equipo |
| **Desglose del árbol de códigos** | Tres categorías (Medioambiental, ESG & Energía, Soft Costs) quedan pendientes de desarrollar | Catálogos como datos: se siembran con «General», son utilizables desde el día uno y se amplían sin migración. Las cinco cuestiones de catálogo están **resueltas** (§3.1) |

---

## 2. Supuestos adoptados

Todos son modificables. Se indica el impacto de cambiarlos.

### 2.1. Negocio

| # | Supuesto | Impacto si cambia |
|---|---|---|
| S-01 | Producto **SaaS multi-organización** con separación lógica de datos | Alto: si es instalación única, se simplifican RLS y onboarding |
| S-02 | Volumen: ≤ 20 organizaciones, ≤ 50 usuarios concurrentes, ≤ 300 proyectos/año | Medio: dimensionamiento |
| S-03 | Proyecto típico: 1-15 activos, 300-1.500 fotografías, 50-300 líneas de CAPEX | Alto: estrategia de fotografías y paginación |
| S-04 | Mercado principal **España**, moneda **EUR**, IVA configurable | Medio |
| S-05 | Interfaz en **español**, con i18n desde el día uno | Bajo si se prepara ya; alto si se pospone |
| S-06 | Equipo: 1 tech lead + 2 full stack + diseñador y QA a media jornada | Alto sobre el calendario |

### 2.2. Modelo de trabajo (derivados de la especificación revisada)

| # | Supuesto | Impacto si cambia |
|---|---|---|
| S-07 | **Las fases de §3.1.5 se seleccionan por proyecto** y cada una tiene estado propio (pendiente / en curso / completada / no aplica). No son secuenciales estrictas: pueden solaparse | Alto: es la interpretación que estructura toda la ficha de proyecto |
| S-08 | **Una línea de CAPEX pertenece a un activo y a una zona**, y la zona depende de la tipología del edificio | Alto: condiciona los catálogos dependientes |
| S-09 | ~~Importe por horizonte con varias columnas~~ → **Resuelto (P-05): una línea tiene UN horizonte y UN importe** | Cerrado |
| S-10 | El desglose por medición (cantidad × precio unitario + cascada) es **opcional** y, cuando existe, se traslada al importe con una acción explícita | Alto: si fuera obligatorio, cambia la interfaz de captura |
| S-10b | ~~El importe es la base imponible final~~ → **Confirmado por el cliente (P-05b)**: el importe incluye indirectos, honorarios y contingencia. Solo el impuesto se aplica encima | Cerrado |
| S-11 | La **visita** se registra por activo, con estado y fecha propios, y la fase «Visita al activo» del proyecto refleja el agregado | Medio |
| S-12 | El **VDR es externo**: se guarda el enlace y quién lo facilitó, no se replica el contenido | Medio: replicarlo multiplicaría el almacenamiento y la responsabilidad sobre datos del cliente |
| S-13 | El **Q&A** es un repositorio de ficheros XLSX versionados, no un gestor de preguntas dentro de la aplicación | Medio-alto: convertirlo en gestor estructurado es un módulo entero |
| S-14 | Aprobación de **un solo nivel**: un revisor aprueba antes de emitir | Medio |
| S-15 | La plantilla PPTX se prepara siguiendo un **contrato documentado** | **Muy alto**: es lo que hace viable el bloque de informes. Coste **medido** sobre las plantillas reales: ~1,5 jornadas por plantilla, ~2 en total (doc 18 §18.6) |
| S-15b | El informe se genera en **el idioma de la plantilla elegida** (ES o EN), y ese idioma se guarda en la versión y se congela en el snapshot | Alto: obliga a traducir los catálogos (doc 18 C-5) |

### 2.3. Técnicos

| # | Supuesto | Impacto si cambia |
|---|---|---|
| S-16 | Despliegue contenedorizado, cloud europeo, una región, residencia UE | Medio-alto |
| S-17 | Autenticación propia (email + contraseña + TOTP opcional), interfaz preparada para OIDC | Medio |
| S-18 | Formatos de imagen: JPEG, PNG, WebP, HEIC/HEIF. RAW y TIFF fuera del MVP | Medio |
| S-19 | Conectividad intermitente pero existente en visita. Offline completo, fase posterior | **Alto** (P-11) |
| S-20 | RPO 15 min · RTO 4 h · disponibilidad 99,5 % en MVP | Medio-alto: 99,9 % encarece la infraestructura |
| S-21 | Retención de datos: 7 años desde el cierre, salvo instrucción contractual | Medio |
| S-22 | Importes con **decimal exacto** (`NUMERIC`), nunca coma flotante | No negociable para la integridad del CAPEX |

---

## 3. Preguntas abiertas

Ordenadas por impacto. **Ninguna bloquea el inicio**: para cada una hay un supuesto operativo.

### 3.1. Decisiones cerradas por el cliente ✅

Doce cuestiones que estaban abiertas y **ya están resueltas**. Se registran aquí con su consecuencia,
porque son las que estructuran el modelo de datos y condicionan la semilla de catálogos.

| # | Cuestión | **Decisión** | Consecuencia |
|---|---|---|---|
| **P-01** ✅ | Las tipologías de activo no coincidían entre §3.1.3 y §3.3.1 | **Se sustituyen los valores de §3.1.3 por los de §3.3.1**, que es la lista correcta | Catálogo de **6 tipologías**: Industrial, Oficinas, Hotel, Comercial, Sanitario, Otros. Desaparecen *logística* y *residencial*: los activos logísticos se clasifican como **Industrial** (es la única tipología con *Almacén* y *Vestuarios*) y los residenciales caen en **Otros**. Los campos de almacén se muestran **solo** en Industrial. Ver [`05`](./05-catalogos-y-taxonomias.md) §5.1 |
| **P-02** ✅ | Los datos del activo aparecían en dos sitios con campos distintos | **Aceptada la propuesta**: una sola entidad `Asset` con la **unión** de ambos conjuntos | Parcela, total, alquilable, almacén, oficinas, altura de almacén, plantas y años, en una ficha. Los campos se muestran según tipología y **no se borran** al reclasificar |
| **P-03** ✅ | El árbol de códigos solo estaba desarrollado para Hard Costs | **Aceptada la propuesta**: las tres categorías restantes se siembran con un capítulo y un elemento «General» | `MA`, `ESG` y `SC` utilizables desde el primer día. Cuando llegue su desglose se añade **sin migración**: las líneas como `MA.General` siguen siendo válidas `[PDV]` queda pendiente recibir ese desglose |
| **P-04** ✅ | El rango del horizonte corto no cuadraba (0-2 frente a 1-2) | **Aceptada la propuesta**: se adopta **1-2 años**, configurable | El plan de inversión por años del informe cuadra con el catálogo |
| **P-44** ✅ | En la tabla real, 5 de 19 filas llevan importe en dos plazos. ¿Contradice P-05? | **No: son actuaciones recurrentes** (opción A). Una actuación que hace falta ahora y otra vez a diez años genera **dos líneas**, una por plazo, y se muestra en **una sola fila** con dos columnas rellenas | **P-05 sigue intacta a nivel de línea.** El índice único por `finding_id` pasa a `(finding_id, time_horizon_id)`: la recurrencia se permite, el duplicado no. Ver [`20`](./20-poc-pptx.md) §20.4 |
| **P-05** ✅ | ¿Importe por horizonte en varias columnas, o un solo horizonte por línea? | **Una sola columna**: cada línea pertenece a **un único horizonte** —corto, medio, largo, mejora potencial u otro tipo de petición—, y las categorías son mutuamente excluyentes | El modelo es `time_horizon_id` + `amount`, no cinco columnas. La rejilla y el informe **pivotan** a cinco columnas para leerse como la hoja de cálculo de siempre, pero es imposible que una línea quede repartida entre dos plazos. Ver [`11`](./11-capex-precios.md) §16.2 |
| **P-05b** ✅ | ¿El importe tecleado ya incluye indirectos, honorarios y contingencia, o es un coste directo al que aplicar la cascada? | **Lo incluye todo**: el importe es la **base imponible final** de la línea | La aplicación **nunca** aplica la cascada por encima de un importe tecleado. El desglose por medición es una **calculadora opcional** cuyo resultado se traslada con un botón. Del perfil de costes, **solo el impuesto se aplica a todas las líneas**; indirectos, honorarios, gastos generales, beneficio industrial y contingencia se usan únicamente dentro de esa calculadora |
| **P-31** ✅ | ¿La tabla de CAPEX del informe sigue siendo una **imagen pegada desde Excel** o pasa a ser **tabla nativa**? | **Tabla nativa respetando el formato del Excel**, y además un **botón de exportar el CAPEX a XLSX** para adjuntarlo en los envíos que el equipo haga fuera de la plataforma | La estructura de la tabla se ha recuperado de los propios metarchivos de las plantillas y está especificada en [`11`](./11-capex-precios.md) §16.8bis. El generador de PPTX y el exportador de XLSX **comparten una misma estructura intermedia**, para que no puedan divergir. La exportación queda auditada como `EXPORT_CREATED` |

| **P-32** ✅ | ¿Pueden facilitarse los **ficheros de las fuentes Gotham**? | **Facilitadas las seis familias**: Light, Book, Medium, Bold, Black y Ultra | Verificadas una a una: OTF válidas, 1000 upm, 637 glifos, cobertura completa del español, y nombre de familia coincidente con el `typeface` de las plantillas. **La medición del desbordamiento ya no usa sustitutas para nada**: `Gotham Light` mide 0,4971 em y `Gotham Ultra` 0,6326 em sobre titulares reales |
| **P-37** ✅ | La imagen de la plantilla tenía **cuatro** columnas de plazo. ¿Se muestra «Otro tipo de petición» como quinta? | **Sí, se deja «Otro»**: el Excel de trabajo la tiene y es la versión más actualizada | La tabla lleva **cinco columnas de plazo** en el informe y en el XLSX. El desfase entre la imagen pegada y la hoja real es el mejor argumento para la tabla nativa: **se genera desde el dato, no desde una captura** |
| **P-38** ✅ | La tabla original venía en **Century Gothic**. ¿Se respeta o se unifica? | **Todo en Gotham**: hay que unificar tipografías | Medido sobre 3.769 caracteres reales de las tablas, Gotham es un **4,9 % más ancha** con la variante Light. Se absorbe usando `Gotham Light` en el cuerpo y trasvasando un 5 % de anchura de `Comments` a `Description`. Ver [`18`](./18-analisis-plantillas-reales.md) §18.7bis |

| **P-06** ✅ | ¿Hay licencia de una base de precios externa? | **No, y no se espera.** *«A falta de conectar una base de datos de precios externa, deja esos campos editables para que cada uno modifique a mano esa parte»* | **Ninguna integración externa**, ni en el MVP ni planificada. El precio se teclea y se edita **en la propia rejilla, sin fricción**: la justificación escrita deja de bloquear y solo se exige al marcar un precio como `VALIDADO`. La trazabilidad se conserva **sin pedir nada**, vía auditoría e historial de campo. `[LIM]` Contrapartida asumida: el catálogo se desfasará, y por eso llega a la vez el módulo de Sugerencias |
| **P-42** ✅ | *(nuevo)* Módulo de **Sugerencias** | **Se añade**: cualquier usuario propone cambios y **solo los administradores ven las propuestas** | Documento propio: [`19-sugerencias.md`](./19-sugerencias.md). Cuatro tipos, contexto capturado por referencia, visibilidad impuesta por **RLS** y no por filtro de servicio, respuesta obligatoria al rechazar. **Añade 1,5 semanas al MVP** en su alcance mínimo (F10bis) |

Con estas doce decisiones, **el bloque 3 queda cerrado a nivel de modelo de datos**: no hay ninguna
cuestión estructural pendiente sobre cómo se captura y se calcula una línea de CAPEX. Lo único que
quedaba abierto en materia de costes era **P-16**, ya cerrado también: la base sobre la que se aplica
cada porcentaje *dentro* de la
calculadora de medición, que afecta a una herramienta de apoyo y no al dato que se almacena.

### 3.2. Impacto crítico

| # | Pregunta | Por qué es crítica | Se avanza con |
|---|---|---|---|
| ~~**P-06**~~ ✅ | ~~¿Disponen de licencia vigente de Precio Centro?~~ **CERRADA:** no hay fuente externa. Los precios se **editan a mano** | Ya no bloquea nada. Ver §3.1 | Ver §3.1 y [`11`](./11-capex-precios.md) §16.5 |
| ~~**P-07**~~ ✅ | ~~¿Pueden facilitarse plantillas PPTX reales?~~ **RESUELTA**: el cliente ha facilitado las **cuatro** plantillas de Full Report (Modelo A y B, en español e inglés) | El mayor riesgo del proyecto ya está **medido** | Analizadas en [`18-analisis-plantillas-reales.md`](./18-analisis-plantillas-reales.md). Abre P-30 a P-36 |
| **P-08** | ¿Es obligatorio el **desglose por medición** (cantidad × precio) o basta el importe a tanto alzado por línea? | Si fuera obligatorio, la captura en campo se ralentiza mucho. *(La parte sobre qué incluye el importe ya está resuelta: P-05b)* | S-10: opcional |
| **P-09** | ¿**SaaS multi-cliente** o instalación única para una consultora? | Multi-tenancy, RLS, onboarding y permisos | S-01: SaaS multi-organización |

### 3.3. Impacto alto

| # | Pregunta | Se avanza con |
|---|---|---|
| **P-10** | ¿La **visita** es por proyecto o por activo? ¿Puede haber varias visitas al mismo activo? | S-11: por activo, con varias visitas posibles y agregado a nivel de fase |
| **P-11** | ¿Qué **conectividad** real hay en las visitas? ¿El offline es criterio de aceptación? | S-19: intermitente; PWA con cola de subida |
| **P-12** | ¿El **Q&A** debe ser un gestor de preguntas y respuestas dentro de la aplicación, o basta adjuntar el Excel? | S-13: repositorio de ficheros versionados |
| **P-13** | ¿Qué **VDR** se usa y hace falta más que guardar el enlace (por ejemplo, control de qué se ha subido)? | S-12: enlace + notas |
| **P-14** | ¿Los **conceptos** (mantenimiento, reparación, normativa…) y los grados de riesgo son cerrados o el cliente los amplía? ¿Y el solapamiento entre concepto y categoría del árbol (*Soft Cost*, *Medioambiental*, *ESG*) se mantiene? | Catálogo editable con los valores dados como semilla; ambos campos se conservan con una regla de coherencia que avisa sin bloquear |
| **P-15** | ¿Se sigue queriendo **inventario de equipos** con ficha propia (fabricante, modelo, nº de serie, vida útil)? La especificación revisada ya no detalla sus campos, pero §7 mantiene la entidad `Equipment` | Se conserva `Equipment` como ficha **opcional**, enlazable desde la línea de CAPEX |
| ~~**P-16**~~ ✅ | ~~¿Sobre qué base se aplica cada porcentaje de la cascada de costes?~~ **CERRADA:** *«se queda así»*. Se adopta la convención española PEM → PEC → honorarios → contingencia | Ver §3.1 y [`11`](./11-capex-precios.md) §16.3 |
| **P-17** | ¿Es obligatorio **SSO corporativo** desde el primer despliegue? | S-17: auth propia, interfaz OIDC-ready |

### 3.4. Impacto medio

| # | Pregunta | Se avanza con |
|---|---|---|
| P-18 | ¿Qué proveedor de **mapas y geocodificación** se prefiere? | Adaptador `MapProvider` con MapLibre + teselas configurables |
| P-19 | ¿Multi-moneda dentro de un mismo proyecto o una moneda por proyecto? | Una por proyecto, con campo por línea para el futuro |
| P-20 | ¿Formatos de foto a soportar? ¿Llegan HEIC de iPhone o RAW? | S-18 |
| P-21 | ¿Qué **convención de nomenclatura** de fotografías se usa hoy? | `[Proyecto]_[Activo]_[Sistema]_[Zona]_[NNN].[ext]` |
| P-22 | ¿Cuántos **niveles de revisión** hay y se exige firma electrónica? | S-14: un nivel, sin firma cualificada |
| P-23 | ¿Hay **integraciones corporativas** previstas (ERP, CRM, gestor documental)? | Ninguna en MVP; API REST como punto de extensión |
| P-24 | ¿**Periodos de retención** pactados con clientes finales? | S-21: 7 años |
| P-25 | ¿Existe **identidad visual** corporativa que deba respetar el frontend? | Sistema propio sobre primitivas accesibles, tematizable |

### 3.5. Impacto bajo

| # | Pregunta |
|---|---|
| P-26 | ¿Presupuesto y fecha objetivo de la primera visita real con la herramienta? |
| P-27 | ¿Idiomas adicionales previstos y en qué plazo? |
| P-28 | ¿Política corporativa de contraseñas y MFA que deba replicarse? |
| P-29 | ¿Quién asume el rol de *product owner* para validar cada fase? |

### 3.6. Preguntas abiertas por el análisis de las plantillas reales

Surgen del análisis del doc [`18`](./18-analisis-plantillas-reales.md). **Cuatro de las nueve ya están
cerradas** —P-31, P-32, P-37 y P-38— y han pasado a §3.1. Queda esto:

| # | Pregunta | Impacto | Propuesta / estado |
|---|---|---|---|
| **P-30** | Tres capítulos del árbol (`H11` fontanería, `H13` seguridad/CCTV/BMS, `H15` otros) **no tienen sección en la plantilla**. ¿Se añaden, se agrupan o solo se generan si hay hallazgos? | Alto | Generarlas solo si hay hallazgos, sin tocar la plantilla |
| **P-33** | Los idiomas confirmados son **español e inglés**. ¿Habrá más? | Medio | Traducción por catálogo, con `locale` abierto |
| **P-34** | El informe agrupa **Cimentación y Estructura** en una diapositiva y desglosa `H04` en tres. ¿Se mantiene o se normaliza al árbol? | Medio | Mantener la plantilla; la agrupación se resuelve en el mapeo |
| **P-36** | ¿Qué diferencia funcional hay entre **Modelo A y Modelo B**, y cuándo se usa cada uno? | Medio | Se tratan como dos variantes de portada del mismo mapeo |
| **P-35** | Las diapositivas de **Mediciones AEO** y **Disclaimer** son contenido fijo. ¿Se marcan como intocables? | Bajo | Sí, con `@keep` |
| **P-39** 🟡 | `[PDV]` ¿Permite el **contrato de licencia de Gotham** incrustar las fuentes en los PPTX enviados? **Aplazada: el cliente no localiza el contrato.** Los ficheros lo admiten (`fsType = Preview & Print`); el contrato, sin verificar | Bajo | **Queda desactivado** (`PPTX_EMBED_FONTS=false`), que es exactamente lo que hacen hoy las plantillas del cliente. **No bloquea nada** y se puede reabrir cuando aparezca el contrato, sin tocar nada de lo construido |

### 3.7. Preguntas del módulo de Sugerencias

Ninguna bloquea: las dos tienen respuesta por defecto y se construye con ella salvo indicación
contraria. Detalle en [`19`](./19-sugerencias.md) §19.4.

| # | Pregunta | Impacto | Propuesta |
|---|---|---|---|
| ~~**P-40**~~ ✅ | ~~¿El autor vuelve a ver la sugerencia que escribió?~~ | — | **CERRADA: sí.** El autor ve las suyas con su estado y la respuesta. La pantalla «Mis sugerencias» entra en el alcance mínimo |
| **P-41** | Ver las sugerencias exige hoy ser `ADMIN`, que además gestiona usuarios, catálogos y organización. ¿Hace falta que alguien atienda el buzón **sin** esas llaves? | Bajo | Permiso separable `GESTIONAR_SUGERENCIAS`, asignable a un `DIRECTOR_PROYECTO`. Media jornada, y evita repartir cuentas de administrador por un motivo menor |

---

## Índice de la documentación

| Doc | Contenido | Entregables |
|---|---|:--:|
| [`01`](./01-resumen-supuestos-preguntas.md) | Resumen ejecutivo · supuestos · preguntas abiertas | 1-3 |
| [`02`](./02-alcance-y-flujos.md) | Alcance funcional · flujos de usuario | 4-5 |
| [`03`](./03-arquitectura.md) | Arquitectura recomendada, alternativas y diagramas | 6-7 |
| [`04`](./04-modelo-de-datos.md) | Modelo de datos · diagramas entidad-relación | 8-9 |
| [`05`](./05-catalogos-y-taxonomias.md) | Tipologías, zonas, árbol de códigos, riesgo, concepto, horizontes | 8 (complemento) |
| [`06`](./06-api.md) | Diseño de las APIs principales | 10 |
| [`07`](./07-roles-permisos.md) | Matriz de roles y permisos | 11 |
| [`08`](./08-historias-y-criterios.md) | Historias de usuario y criterios Given/When/Then | 12-13 |
| [`09`](./09-ux-pantallas.md) | Bocetos textuales de las 19 pantallas | 14 |
| [`10`](./10-fotografias.md) | Estrategia de fotografías | 15 |
| [`11`](./11-capex-precios.md) | Motor de CAPEX y normalización de precios | 16 |
| [`12`](./12-pptx.md) | Lectura, mapeo y generación de PPTX | 17 |
| [`13`](./13-seguridad-privacidad-auditoria.md) | Seguridad, privacidad, RGPD y auditoría | 18 |
| [`14`](./14-pruebas.md) | Estrategia de pruebas | 19 |
| [`15`](./15-mvp-plan-riesgos.md) | Alcance del MVP · plan por fases · riesgos | 20-22 |
| [`16`](./16-estructura-carpetas.md) | Estructura inicial del proyecto | 23 |
| [`17`](./17-requisitos-no-funcionales.md) | Objetivos no funcionales verificables | §10 |
| [`18`](./18-analisis-plantillas-reales.md) | Análisis de las 4 plantillas PPTX reales | 17 (rev.) |
| [`19`](./19-sugerencias.md) | **Módulo de Sugerencias** | añadido |

El entregable **24 (código inicial del MVP)** se aborda tras la validación de este diseño,
conforme a §16 del encargo.

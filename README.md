# Aplicación de gestión de due diligence técnica inmobiliaria

Diseño y plan de implementación de una aplicación web empresarial para gestionar de principio a fin
proyectos de **due diligence técnica (TDD) de activos inmobiliarios**: gestión del encargo y de sus
fases, repositorio fotográfico, elaboración del CAPEX con trazabilidad, y generación de informes
PowerPoint desde la plantilla PPTX de cada proyecto.

> **Estado actual: diseño cerrado y MVP construido.**
> Los entregables 1 a 23 (análisis funcional, arquitectura, modelo de datos y plan) están en `docs/`.
> El **entregable 24 está completo en sus cuatro bloques**: `apps/api/` con **1.227 pruebas en verde
> contra PostgreSQL real** y `apps/web/` con la interfaz React. La aplicación se ha recorrido de
> punta a punta con el servidor en marcha: crear la primera cuenta, iniciar sesión, dar de alta el
> encargo con sus fases y un activo, **hacer una foto desde la cámara**, clasificarla, registrar el
> hallazgo con su CAPEX, exportarlo a Excel, subir la plantilla, mapearla, generar el informe y
> emitirlo. Qué está construido y qué no, sin adornos, en
> [`apps/api/README.md`](apps/api/README.md) y [`apps/web/README.md`](apps/web/README.md).
>
> Y una vez construido, se ha abierto **sin conexión en un navegador de verdad**: el armazón carga,
> la cola de fotos sigue en el dispositivo y la API no se sirve desde caché. Eso también destapó un
> fallo —`Vary: Origin` impedía encontrar el JavaScript precacheado, y la aplicación abría en blanco
> sin red— que con cobertura no se ve.
>
> Ese recorrido no es decorativo: **seis defectos reales salieron de ahí** y de ningún otro sitio.
> Un `500` al repetir el código de un encargo en vez de decir que estaba cogido; el botón de
> exportar el CAPEX a XLSX sin ninguna ruta que lo sirviera; las miniaturas pidiendo el original de
> cada foto y devolviendo `401` porque un `<img src>` no lleva credencial; el permiso del buzón de
> sugerencias calculado de tres formas distintas; un desplegable ofreciendo tipos que la API
> rechaza; y `make test` borrando la base de desarrollo. Cada uno se arregló con la prueba que lo
> habría cazado antes.

---

## Las seis decisiones que sostienen el diseño

| # | Decisión | Por qué importa |
|---|---|---|
| 1 | **Estado y fases son ejes distintos** | El `estado` del proyecto describe el ciclo administrativo; las **fases** (documentación, VDR, visita, Q&A, Red Flag/CAPEX, Full Report, presentación, defensa) describen el trabajo real, se eligen a la carta al dar de alta y avanzan en paralelo. Un encargo puede tener la documentación pendiente, la visita hecha y el Q&A en curso a la vez |
| 2 | **La fila que rellena el consultor es una sola cosa** | Hallazgo y partida CAPEX son la misma línea: código, zona, riesgo, concepto, **un horizonte y un importe**. La interfaz muestra una fila; por debajo se persisten `Finding` y `CapexItem` con relación 1:1, para conservar el modelo exigido y permitir que un hallazgo genere varias partidas |
| 3 | **Los catálogos son datos, no código** | 6 tipologías, 20 zonas dependientes de ellas, 125 códigos CAPEX en árbol de tres niveles, cuatro grados de riesgo con su definición íntegra, cinco horizontes. Todo en tablas versionadas y ampliables: corregir el árbol no puede exigir un despliegue |
| 4 | **El original nunca se toca** | Fotografías, documentos y plantillas son objetos inmutables, garantizado por cuatro barreras independientes: API, dominio, base de datos y almacenamiento WORM |
| 5 | **El precio es un dato con procedencia** | Fuente, URL, fecha de consulta, ámbito, alcance incluido y excluido, tratamiento fiscal, y el usuario que lo validó. Ningún proceso automático valida un precio |
| 6 | **La tabla de CAPEX se diseña una sola vez** | La tabla nativa del informe y la hoja `CAPEX` del Excel exportado salen de la **misma estructura intermedia**. Añadir una columna en un solo sitio hace fallar la suite. Sin esa pieza, en seis meses el PPTX y el Excel que viajan en el mismo correo tendrían columnas distintas |

## Levantarlo entero, con un comando

```bash
make up                                     # base, objetos, correo, API, workers y frontend
make up-admin ORG='Consultora Ejemplo' EMAIL='admin@ejemplo.example' NOMBRE='Nombre Apellido'
```

| | |
|---|---|
| Aplicación | http://localhost:8080 |
| API | http://localhost:8000/docs |
| Correo capturado | http://localhost:8025 |
| Almacén de objetos | http://localhost:9001 |

`make down` para, `make destroy` borra también los volúmenes, `make logs` sigue los registros.

Lo que este entorno aporta —y por lo que existe— es que aquí se habla con un **S3 de verdad**
(MinIO con Object Lock) y con un **SMTP de verdad** (Mailpit con STARTTLS). Los dos adaptadores
estaban escritos y probados contra simuladores en proceso; sacarlos de ahí destapó cinco defectos
reales, entre ellos que la rejilla de fotografías salía vacía con S3 y que nginx dejaba la
aplicación en `502` después de cada despliegue de la API.

**Antes de dar por buena una instalación**, contra el bucket de verdad:

```bash
python3 tools/comprobar_almacen.py --escribir   # versionado, Object Lock, CORS y borrado
```

Cómo crear ese bucket y **qué permisos exactos** necesita el rol de la aplicación, en
[`docs/21-bucket-s3.md`](docs/21-bucket-s3.md). Dos avisos de ahí que cuestan caro: Object Lock
**solo se puede activar al crear el bucket**, y `s3:PutObjectRetention` es un permiso **aparte** de
`s3:PutObject` —sin él fallan los originales y no los derivados, que parece un fallo intermitente y
no lo es—.

**Cuando algo falle**, el error que ve el usuario lleva su identificador:

```json
{"title": "Error interno", "status": 500, "request_id": "3f2a9c…"}
```

Ese mismo identificador está en el registro con la traza completa, y —si la petición encargó una
tarea— en `job.request_id` y en las líneas del worker, aunque lo haya generado otro proceso cinco
minutos después. `/metrics` da peticiones, latencias y **la profundidad de la cola**, que es lo que
avisa de que el worker ha muerto: la interfaz sigue respondiendo rápido y lo único que se notaría es
que los informes «tardan».

`[LIM]` Lo que el `compose` **no** resuelve y hace falta para producción: TLS de entrada, secretos
fuera del fichero, copias de seguridad, límites de recursos y las tipografías corporativas
—comerciales, no van en la imagen—. Está declarado en `compose.yml`.

---

## Arquitectura en una frase

Monolito modular en **Python/FastAPI** sobre **PostgreSQL 16** con *Row Level Security* por
organización, **almacenamiento de objetos compatible S3**, **workers Celery** para trabajos pesados y
**React + TypeScript** como PWA responsive. Justificación y alternativas descartadas en
[`docs/03-arquitectura.md`](docs/03-arquitectura.md).

---

## Documentación

Empiece por [`docs/01-resumen-supuestos-preguntas.md`](docs/01-resumen-supuestos-preguntas.md).

| Doc | Contenido | Entregables |
|---|---|:--:|
| [01](docs/01-resumen-supuestos-preguntas.md) | Resumen ejecutivo · supuestos · preguntas abiertas | 1-3 |
| [02](docs/02-alcance-y-flujos.md) | Alcance funcional · flujos de usuario | 4-5 |
| [03](docs/03-arquitectura.md) | Arquitectura recomendada, alternativas y diagramas | 6-7 |
| [04](docs/04-modelo-de-datos.md) | Modelo de datos · diagramas entidad-relación | 8-9 |
| [05](docs/05-catalogos-y-taxonomias.md) | Tipologías, matriz de zonas, árbol de códigos, riesgo, conceptos, horizontes | 8 (compl.) |
| [06](docs/06-api.md) | Diseño de las APIs principales | 10 |
| [07](docs/07-roles-permisos.md) | Matriz de roles y permisos | 11 |
| [08](docs/08-historias-y-criterios.md) | 17 historias de usuario con criterios Given/When/Then | 12-13 |
| [09](docs/09-ux-pantallas.md) | Bocetos textuales de las 19 pantallas | 14 |
| [10](docs/10-fotografias.md) | Estrategia de fotografías | 15 |
| [11](docs/11-capex-precios.md) | Motor de CAPEX y normalización de precios | 16 |
| [12](docs/12-pptx.md) | Lectura, mapeo y generación de PPTX | 17 |
| [13](docs/13-seguridad-privacidad-auditoria.md) | Seguridad, privacidad, RGPD y auditoría | 18 |
| [14](docs/14-pruebas.md) | Estrategia de pruebas | 19 |
| [15](docs/15-mvp-plan-riesgos.md) | Alcance del MVP · plan por fases · riesgos | 20-22 |
| [16](docs/16-estructura-carpetas.md) | Estructura inicial del proyecto | 23 |
| [17](docs/17-requisitos-no-funcionales.md) | Objetivos no funcionales verificables | §10 |
| **[18](docs/18-analisis-plantillas-reales.md)** | **Análisis de las 4 plantillas PPTX reales** · corrige el bloque 4 | 17 (rev.) |
| **[19](docs/19-sugerencias.md)** | **Módulo de Sugerencias** · propuestas de usuario visibles solo para administradores | añadido |
| **[20](docs/20-poc-pptx.md)** | **Prueba de concepto del bloque 4** · resultados medidos, y lo que corrigen | añadido |
| **[20b](docs/18-analisis-plantillas-reales.md#generación-a-volumen-con-las-tipografías-puestas)** | **Generación a volumen medida** · 105 diapositivas en 3,1 s, y las tres cosas que solo se ven a ese tamaño | añadido |
| **[21](docs/21-bucket-s3.md)** | **El bucket de S3** · cómo crearlo y los permisos exactos del rol. Sin ejecutar contra AWS todavía | añadido |
| **[apps/api](apps/api/README.md)** | **Backend del MVP**: qué está construido, qué falta y cómo arrancarlo | **24** |
| **[apps/web](apps/web/README.md)** | **Frontend del MVP**: pantallas, los tres orígenes de foto y lo que falta | **24** |

### Convención de etiquetas

| Etiqueta | Significado |
|---|---|
| `[REQ]` | Requisito solicitado explícitamente |
| `[SUP]` | Supuesto adoptado por falta de información. Modificable |
| `[REC]` | Recomendación propia, no solicitada |
| `[LIM]` | Limitación técnica real, conocida y verificable |
| `[PDV]` | Pendiente de validar (legal, técnica o de negocio) |

---

## Decisiones ya cerradas por el cliente ✅

Diez cuestiones que estaban abiertas y que estructuran el modelo de datos y el informe:

| # | Decisión | Consecuencia |
|---|---|---|
| **P-01** | Las tipologías de §3.1.3 se sustituyen por las de **§3.3.1** | **6 tipologías**: Industrial, Oficinas, Hotel, Comercial, Sanitario, Otros. Los activos logísticos se clasifican como **Industrial** (la única con *Almacén* y *Vestuarios*); los residenciales, como **Otros**. Los campos de almacén se muestran solo en Industrial |
| **P-02** | Una sola entidad `Asset` con la **unión** de los campos de ambos apartados | Parcela, total, alquilable, almacén, oficinas y altura en una ficha; se muestran según tipología y no se borran al reclasificar |
| **P-03** | Las tres categorías sin desarrollar se siembran con capítulo y elemento «General» | `MA`, `ESG` y `SC` utilizables desde el día uno; su desglose se añade sin migración |
| **P-04** | Horizonte corto = **1-2 años** | El plan de inversión por años cuadra con el catálogo |
| **P-05** | **Una línea, un horizonte, un importe** | Corto, medio, largo, mejora potencial u otro tipo de petición son **mutuamente excluyentes**. El modelo es `time_horizon_id` + `amount`; la rejilla y el informe pivotan a cinco columnas para leerse como la hoja de siempre, pero una línea no puede quedar repartida entre dos plazos |
| **P-05b** | El importe tecleado **lo incluye todo** | Es la base imponible final: lleva dentro indirectos, honorarios y contingencia. La aplicación **nunca** aplica la cascada por encima. Del perfil de costes, solo el impuesto afecta a todas las líneas; el resto de porcentajes son la preconfiguración de la calculadora de medición |

| **P-07** | Facilitadas las **4 plantillas reales** de Full Report | Analizadas en [`docs/18`](docs/18-analisis-plantillas-reales.md). Son **una sola estructura** × 2 portadas × 2 idiomas: 67 diapositivas, 4:3, 14 sistemas, 56 marcos de foto. **Corrige cinco decisiones del bloque 4** |
| **P-31** | La tabla de CAPEX pasa a ser **nativa, respetando el formato del Excel**, y la aplicación incorpora un **botón de exportar el CAPEX a XLSX** | Hoy son imágenes EMF pegadas desde Excel. Su estructura se ha **recuperado de los propios metarchivos** y está especificada en [`docs/11`](docs/11-capex-precios.md) §16.8bis. El generador de PPTX y el exportador de XLSX **comparten una misma pieza** para que no puedan divergir. El XLSX existe para adjuntarlo en los envíos que el equipo haga fuera de la plataforma, y por eso **queda auditado** |
| **P-32** | Facilitadas las **seis familias Gotham** | Verificadas una a una. El desbordamiento se mide con las fuentes reales, texto y titulares, **sin sustitutas** |
| **P-37** | La tabla lleva **cinco columnas de plazo**, «Otro» incluida | La imagen pegada en la plantilla solo tenía cuatro: estaba desfasada respecto del Excel de trabajo. La tabla nativa se genera **desde el dato**, así que no puede volver a quedarse atrás |
| **P-38** | **Toda la tipografía unificada en Gotham** | La tabla deja Century Gothic. Cuesta un **+4,9 %** de anchura de texto —medido sobre 3.769 caracteres reales—, absorbido con `Gotham Light` en el cuerpo y un reajuste de columnas |

Con esto, **el bloque de CAPEX queda cerrado a nivel de modelo de datos** y el riesgo del bloque 4
pasa de *alto* a *medio*, ya medido sobre las plantillas reales.

---

## El diseño está cerrado

**No queda ninguna decisión pendiente que condicione el diseño.** Las quince cuestiones que
estructuraban el modelo están resueltas por el cliente, y las últimas —P-06, P-16 y P-40— cerraron con
la aplicación de las decisiones ya propagada a toda la documentación.

Queda **una sola cuestión aplazada**, y no bloquea nada:

- 🟡 **`P-39` · ¿Permite el contrato de licencia de Gotham incrustar las fuentes en los PPTX enviados?**
  El cliente no localiza el contrato. Los ficheros lo admiten (`fsType = Preview & Print`), pero eso no
  sustituye al contrato. **La incrustación queda desactivada** (`PPTX_EMBED_FONTS=false`), que es
  exactamente lo que hacen hoy las plantillas de la consultora: ninguna de las cuatro incrusta fuentes.
  Se puede reabrir cuando aparezca el contrato, sin tocar nada de lo construido.

> **Siguiente paso: entregable 24** — el código inicial del MVP, que conforme a §16 del encargo se
> aborda tras la validación de este diseño.

Las demás preguntas, ordenadas por impacto, están en
[`docs/01`](docs/01-resumen-supuestos-preguntas.md) §3.

---

## Limitaciones declaradas por adelantado

Aquí, y no enterradas en un anexo, porque condicionan expectativas:

- `[LIM]` La biblioteca de PPTX con licencia permisiva más madura **no ofrece duplicado oficial de
  diapositivas ni renderizado**. Se resuelve con un contrato de plantilla documentado y previsualización
  con LibreOffice, cuyo resultado **no es idéntico** al de PowerPoint. Planes alternativos valorados en
  [`docs/12`](docs/12-pptx.md) §17.9.
- ✅ **Resuelta:** el análisis de las plantillas ya **no** es solo estructural. La prueba de concepto
  ([`docs/20`](docs/20-poc-pptx.md)) las ha renderizado y comparado; faltaba un paquete de LibreOffice,
  no era un problema de fondo. Ver el render **corrigió cuatro afirmaciones** del doc 18.
- `[LIM]` La detección de textos que desbordan es una **estimación** por métricas de fuente, con margen
  de ±10-15 %. El aviso lo dice explícitamente al usuario. Ya se mide con las **fuentes Gotham reales**,
  texto y titulares, sin sustitutas.
- `[LIM]` **Un PPTX no contiene tipografías, contiene nombres de tipografía.** Que el destinatario vea
  el informe en Gotham depende de que tenga Gotham instalada, no de esta aplicación. Es el mismo
  comportamiento que hoy: las cuatro plantillas facilitadas **no incrustan** las fuentes. Incrustarlas
  es posible y está valorado en [`docs/18`](docs/18-analisis-plantillas-reales.md) §18.7bis, pero
  **no entra en el MVP**.
- `[LIM]` **La fidelidad de la tabla nativa de CAPEX no está verificada.** Su estructura —columnas,
  cabecera de dos niveles, formato— se recuperó de los metarchivos EMF de las plantillas, que son
  exactos, pero los anchos son una reconstrucción y no se ha visto ningún render. La comparación lado a
  lado con la imagen original es criterio de salida de la prueba de concepto. Tras P-38 esa comparación
  **no busca identidad**: la tabla irá en Gotham y no en Century Gothic, con un **4,9 % más de anchura
  de texto** ya medido y compensado en los anchos de columna.
- `[LIM]` **Las fuentes corporativas no están en el repositorio y no deben estarlo.** Gotham es
  comercial y licenciada; versionarla sería redistribuirla. Se provisionan en el contenedor desde un
  artefacto privado, con verificación en el arranque.
- `[LIM]` **No hay ninguna fuente de precios externa, ni está prevista** `[REQ]` P-06. Los precios se
  teclean y se editan a mano, sin fricción. La contrapartida, asumida a conciencia: **el catálogo de
  precios se irá desfasando**, porque nada lo actualiza solo. Por eso el módulo de Sugerencias llega en
  el mismo paso — su tipo `PRECIO` es el mecanismo por el que una corrección detectada en un proyecto
  llega al catálogo que usan los demás.
- `[LIM]` La resolución de conflictos del MVP es *última escritura gana a nivel de campo*, con registro
  del valor descartado y aviso. El modo offline completo es fase posterior.
- `[LIM]` **Ninguna función de IA en el MVP.** Y si se incorpora, será con consentimiento explícito,
  marcado visible, revisión humana obligatoria y sin usar datos de cliente para entrenamiento.

---

## Alcance del MVP en una línea

> Un consultor debe poder llevar a cabo una due diligence técnica real de principio a fin —desde abrir
> el encargo y pedir la documentación hasta emitir el PPTX— **sin salirse de la herramienta ni una sola
> vez.**

Estimación: **19,5 semanas** con el equipo supuesto (1 tech lead + 2 full stack + diseñador y QA a media
jornada), en 12 fases. Eran 18 antes de añadir el **módulo de Sugerencias** (F10bis, 1,5 semanas en su
alcance mínimo): se planifica dentro del MVP porque el canal vale más cuando la herramienta es nueva,
que es cuando aparecen los códigos que faltan y los precios desfasados. **Es la única pieza del plan
que se puede mover a después sin arrastrar ninguna otra**, si las 18 semanas fuesen un compromiso
firme. Incluye una **fase dedicada a catálogos antes que a proyectos**: zonas, códigos,
riesgos y conceptos son la estructura sobre la que se apoya todo el CAPEX, y sembrarlos mal obliga a
migrar datos reales después.

Detalle por fases, hitos y los catorce criterios de aceptación en
[`docs/15`](docs/15-mvp-plan-riesgos.md).

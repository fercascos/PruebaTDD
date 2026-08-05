# Aplicación de gestión de due diligence técnica inmobiliaria

Diseño y plan de implementación de una aplicación web empresarial para gestionar de principio a fin
proyectos de **due diligence técnica (TDD) de activos inmobiliarios**: gestión del encargo y de sus
fases, repositorio fotográfico, elaboración del CAPEX con trazabilidad, y generación de informes
PowerPoint desde la plantilla PPTX de cada proyecto.

> **Estado actual: fase de diseño.**
> Este repositorio contiene el análisis funcional, la arquitectura, el modelo de datos y el plan de
> implementación (entregables 1 a 23). **Todavía no contiene código de aplicación**: el código inicial
> del MVP (entregable 24) se desarrolla tras la validación de este diseño, conforme a §16 del encargo.

---

## Las seis decisiones que sostienen el diseño

| # | Decisión | Por qué importa |
|---|---|---|
| 1 | **Estado y fases son ejes distintos** | El `estado` del proyecto describe el ciclo administrativo; las **fases** (documentación, VDR, visita, Q&A, Red Flag/CAPEX, Full Report, presentación, defensa) describen el trabajo real, se eligen a la carta al dar de alta y avanzan en paralelo. Un encargo puede tener la documentación pendiente, la visita hecha y el Q&A en curso a la vez |
| 2 | **La fila que rellena el consultor es una sola cosa** | Hallazgo y partida CAPEX son la misma línea: código, zona, riesgo, concepto, **un horizonte y un importe**. La interfaz muestra una fila; por debajo se persisten `Finding` y `CapexItem` con relación 1:1, para conservar el modelo exigido y permitir que un hallazgo genere varias partidas |
| 3 | **Los catálogos son datos, no código** | 6 tipologías, 20 zonas dependientes de ellas, 121 códigos CAPEX en árbol de tres niveles, cuatro grados de riesgo con su definición íntegra, cinco horizontes. Todo en tablas versionadas y ampliables: corregir el árbol no puede exigir un despliegue |
| 4 | **El original nunca se toca** | Fotografías, documentos y plantillas son objetos inmutables, garantizado por cuatro barreras independientes: API, dominio, base de datos y almacenamiento WORM |
| 5 | **El precio es un dato con procedencia** | Fuente, URL, fecha de consulta, ámbito, alcance incluido y excluido, tratamiento fiscal, y el usuario que lo validó. Ningún proceso automático valida un precio |
| 6 | **La tabla de CAPEX se diseña una sola vez** | La tabla nativa del informe y la hoja `CAPEX` del Excel exportado salen de la **misma estructura intermedia**. Añadir una columna en un solo sitio hace fallar la suite. Sin esa pieza, en seis meses el PPTX y el Excel que viajan en el mismo correo tendrían columnas distintas |

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

Seis cuestiones que estaban abiertas y que estructuran el modelo de datos:

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

Con esto, **el bloque de CAPEX queda cerrado a nivel de modelo de datos** y el riesgo del bloque 4
pasa de *alto* a *medio*, ya medido sobre las plantillas reales.

---

## Lo que falta para avanzar

**Un fichero concreto** — y no es una decisión, es un envío:

> 🟡 **Falta `Gotham Ultra`.** De las cinco fuentes recibidas (Light, Book, Medium, Bold, Black), la que
> la plantilla usa para **todos los titulares** no está. Es la mitad del uso de Gotham en el informe:
> 86-94 apariciones por plantilla, frente a 86-130 de Gotham Light. Mientras no llegue, los titulares se
> medirán y se renderizarán con una sustituta. **No se sustituye en silencio**: Gotham Black es la más
> próxima en peso pero no es métricamente equivalente, y el aviso de desbordamiento lo declarará.

**Y tres decisiones:**

1. **`P-06` · ¿Hay licencia vigente de Precio Centro, y qué permiten sus condiciones?** Es la
   diferencia entre un CAPEX con precios reales y un formulario. **No es una decisión técnica.**
2. **`P-16` · ¿Cuál es la cascada de costes real?** Debe coincidir con los Excel que la consultora ya
   usa. Tras P-05b su alcance está acotado a la calculadora de medición.
3. **`P-37` · ¿Sale «Otro tipo de petición» como quinta columna del informe?** La tabla real del Excel
   solo tiene cuatro plazos. Se propone ocultarla por defecto en el PPTX y mantenerla siempre en el XLSX.

Las demás preguntas, ordenadas por impacto, están en
[`docs/01`](docs/01-resumen-supuestos-preguntas.md) §3.

---

## Limitaciones declaradas por adelantado

Aquí, y no enterradas en un anexo, porque condicionan expectativas:

- `[LIM]` La biblioteca de PPTX con licencia permisiva más madura **no ofrece duplicado oficial de
  diapositivas ni renderizado**. Se resuelve con un contrato de plantilla documentado y previsualización
  con LibreOffice, cuyo resultado **no es idéntico** al de PowerPoint. Planes alternativos valorados en
  [`docs/12`](docs/12-pptx.md) §17.9.
- `[LIM]` **El análisis de las plantillas es estructural, no visual.** LibreOffice no arranca en el
  entorno donde se hizo, de modo que **no se ha visto ninguna plantilla renderizada**. Todo lo afirmado
  en [`docs/18`](docs/18-analisis-plantillas-reales.md) procede del fichero, que es exacto y
  verificable; la validación visual es parte de la prueba de concepto.
- `[LIM]` La detección de textos que desbordan es una **estimación** por métricas de fuente, con margen
  de ±10-15 %. El aviso lo dice explícitamente al usuario. Medida ya con `Gotham Light` real, la
  desviación de la heurística resultó del **2,8 %**; para los titulares en `Gotham Ultra` seguirá siendo
  una estimación con sustituta **mientras no llegue el fichero**, y el aviso lo declarará.
- `[LIM]` **La fidelidad de la tabla nativa de CAPEX no está verificada.** Su estructura —columnas,
  cabecera de dos niveles, formato— se recuperó de los metarchivos EMF de las plantillas, que son
  exactos, pero los anchos son una reconstrucción y no se ha visto ningún render. La comparación lado a
  lado con la imagen original es criterio de salida de la prueba de concepto.
- `[LIM]` **Las fuentes corporativas no están en el repositorio y no deben estarlo.** Gotham es
  comercial y licenciada; versionarla sería redistribuirla. Se provisionan en el contenedor desde un
  artefacto privado, con verificación en el arranque.
- `[LIM]` **Precio Centro no está integrado, y no se afirma que vaya a funcionar.** No se realiza
  extracción automatizada del sitio: es una base de precios comercial protegida y su uso requiere
  licencia y revisión de condiciones. La vía preferente es la **importación del catálogo exportado**,
  no la consulta en línea. El MVP incluye entrada manual con justificación obligatoria e importación de
  catálogo propio.
- `[LIM]` La resolución de conflictos del MVP es *última escritura gana a nivel de campo*, con registro
  del valor descartado y aviso. El modo offline completo es fase posterior.
- `[LIM]` **Ninguna función de IA en el MVP.** Y si se incorpora, será con consentimiento explícito,
  marcado visible, revisión humana obligatoria y sin usar datos de cliente para entrenamiento.

---

## Alcance del MVP en una línea

> Un consultor debe poder llevar a cabo una due diligence técnica real de principio a fin —desde abrir
> el encargo y pedir la documentación hasta emitir el PPTX— **sin salirse de la herramienta ni una sola
> vez.**

Estimación: **18 semanas** con el equipo supuesto (1 tech lead + 2 full stack + diseñador y QA a media
jornada), en 11 fases. Incluye una **fase dedicada a catálogos antes que a proyectos**: zonas, códigos,
riesgos y conceptos son la estructura sobre la que se apoya todo el CAPEX, y sembrarlos mal obliga a
migrar datos reales después.

Detalle por fases, hitos y los catorce criterios de aceptación en
[`docs/15`](docs/15-mvp-plan-riesgos.md).

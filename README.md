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

## Las cinco decisiones que sostienen el diseño

| # | Decisión | Por qué importa |
|---|---|---|
| 1 | **Estado y fases son ejes distintos** | El `estado` del proyecto describe el ciclo administrativo; las **fases** (documentación, VDR, visita, Q&A, Red Flag/CAPEX, Full Report, presentación, defensa) describen el trabajo real, se eligen a la carta al dar de alta y avanzan en paralelo. Un encargo puede tener la documentación pendiente, la visita hecha y el Q&A en curso a la vez |
| 2 | **La fila que rellena el consultor es una sola cosa** | Hallazgo y partida CAPEX son la misma línea de trabajo. La interfaz muestra una fila; por debajo se persisten `Finding` y `CapexItem` con relación 1:1, para conservar el modelo exigido y permitir que un hallazgo genere varias partidas |
| 3 | **Los catálogos son datos, no código** | Zonas dependientes de la tipología, 121 códigos CAPEX en árbol de tres niveles, cuatro grados de riesgo con su definición íntegra. Todo en tablas versionadas y ampliables: corregir el árbol no puede exigir un despliegue |
| 4 | **El original nunca se toca** | Fotografías, documentos y plantillas son objetos inmutables, garantizado por cuatro barreras independientes: API, dominio, base de datos y almacenamiento WORM |
| 5 | **El precio es un dato con procedencia** | Fuente, URL, fecha de consulta, ámbito, alcance incluido y excluido, tratamiento fiscal, y el usuario que lo validó. Ningún proceso automático valida un precio |

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

### Convención de etiquetas

| Etiqueta | Significado |
|---|---|
| `[REQ]` | Requisito solicitado explícitamente |
| `[SUP]` | Supuesto adoptado por falta de información. Modificable |
| `[REC]` | Recomendación propia, no solicitada |
| `[LIM]` | Limitación técnica real, conocida y verificable |
| `[PDV]` | Pendiente de validar (legal, técnica o de negocio) |

---

## Cuatro incoherencias detectadas en la especificación

No son objeciones: son cosas que conviene cerrar **antes** de sembrar los catálogos, porque migrarlos
después es caro. Cada una tiene una propuesta provisional con la que se puede avanzar ya.

1. **`P-01` · Las tipologías de activo no coinciden entre apartados.** §3.1.3 propone oficinas,
   logística, retail, hotel, residencial e industrial; §3.3.1 propone Industrial, Oficinas, Hotel,
   Comercial y Sanitario. Faltan *logística* y *residencial* en la segunda, falta *sanitario* en la
   primera, y *retail* y *Comercial* parecen lo mismo.
2. **`P-02` · Los datos del activo aparecen en dos sitios con campos distintos.** §3.1.3 pide
   superficie construida, alquilable y plantas; §3.3.1 pide parcela, almacén, oficinas y altura de
   almacén.
3. **`P-03` · El árbol de códigos solo está desarrollado para Hard Costs.** «Medioambiental»,
   «ESG & Energía» y «Soft Costs» se nombran como categorías hermanas, pero sin capítulos ni elementos.
4. **`P-04` · El rango del horizonte corto no cuadra.** El literal dice «0-2 años» y la glosa dice
   «1 a 2 años».

Además, tres valores —*Soft Cost*, *Medioambiental* y *ESG*— aparecen a la vez como **concepto**
(§3.3.3) y como **categoría del árbol de códigos** (§3.3.4). La propuesta es mantener ambos campos,
porque miden cosas distintas, con una regla de coherencia que avisa sin bloquear.

Detalle y propuestas en [`docs/01`](docs/01-resumen-supuestos-preguntas.md) §3.1 y
[`docs/05`](docs/05-catalogos-y-taxonomias.md).

---

## Las cuatro decisiones que hay que tomar para avanzar

1. **`P-05` · ¿El importe se introduce por horizonte (varias columnas) o cada línea tiene un solo
   horizonte?** Cambia la tabla de CAPEX, las vistas, la exportación y el informe. Se ha modelado la
   opción **más general** (cinco columnas con total calculado) porque reducirla es trivial y lo
   contrario obligaría a partir líneas ya introducidas.
2. **`P-06` · ¿Hay licencia vigente de Precio Centro, y qué permiten sus condiciones?** Es la
   diferencia entre un CAPEX con precios reales y un formulario. **No es una decisión técnica.**
3. **`P-07` · ¿Pueden facilitarse 2-3 plantillas PPTX reales?** La pregunta más urgente: la generación
   conservando el formato corporativo es el riesgo número uno, y sin plantillas reales queda sin medir.
   El plan reserva las semanas 2-3 para una prueba de concepto dedicada.
4. **`P-08` · ¿Es obligatorio el desglose por medición o basta el importe a tanto alzado?** Si es
   obligatorio, la captura en campo se ralentiza mucho.

Las 29 preguntas ordenadas por impacto están en
[`docs/01`](docs/01-resumen-supuestos-preguntas.md) §3.

---

## Limitaciones declaradas por adelantado

Aquí, y no enterradas en un anexo, porque condicionan expectativas:

- `[LIM]` La biblioteca de PPTX con licencia permisiva más madura **no ofrece duplicado oficial de
  diapositivas ni renderizado**. Se resuelve con un contrato de plantilla documentado y previsualización
  con LibreOffice, cuyo resultado **no es idéntico** al de PowerPoint. Planes alternativos valorados en
  [`docs/12`](docs/12-pptx.md) §17.9.
- `[LIM]` La detección de textos que desbordan es una **estimación** por métricas de fuente, con margen
  de ±10-15 %. El aviso lo dice explícitamente al usuario.
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

# Aplicación de gestión de due diligence técnica inmobiliaria

Diseño y plan de implementación de una aplicación web empresarial para gestionar de principio a fin
proyectos de **due diligence técnica (TDD) de activos inmobiliarios**: creación y gestión de
proyectos, repositorio fotográfico, elaboración de estimaciones CAPEX trazables y generación de
informes PowerPoint a partir de la plantilla PPTX de cada proyecto.

> **Estado actual: fase de diseño.**
> Este repositorio contiene el análisis funcional, la arquitectura, el modelo de datos y el plan de
> implementación (entregables 1 a 23 del encargo). **Todavía no contiene código de aplicación**: el
> código inicial del MVP (entregable 24) se desarrolla tras la validación de este diseño, conforme a
> §16 del encargo.

---

## Los cuatro pilares del diseño

| # | Decisión | Por qué importa |
|---|---|---|
| 1 | **El original nunca se toca** | Fotografías, documentos y plantillas se almacenan como objetos inmutables. Renombrar, anotar o generar produce siempre un derivado nuevo. Garantizado por cuatro barreras independientes: API, dominio, base de datos y almacenamiento WORM |
| 2 | **El precio es un dato con procedencia, no un número** | Cada importe arrastra fuente, URL, fecha de consulta, alcance, tratamiento fiscal y el usuario que lo validó. Ningún proceso automático valida un precio |
| 3 | **El informe es una fotografía inmutable de los datos** | Emitir congela un *snapshot* de los datos y el hash del PPTX. Cambiar datos después no altera lo emitido: crea una versión nueva |
| 4 | **Las fuentes de precios son adaptadores** | El motor de CAPEX conoce una interfaz y nada más. Añadir, desactivar o sustituir una fuente no toca el cálculo |

## Arquitectura en una frase

Monolito modular en **Python/FastAPI** sobre **PostgreSQL 16** con *Row Level Security* por
organización, **almacenamiento de objetos compatible S3** para binarios, **workers Celery** para
trabajos pesados y **React + TypeScript** como PWA responsive. La justificación completa y las
alternativas descartadas están en [`docs/03-arquitectura.md`](docs/03-arquitectura.md).

---

## Documentación

Empiece por [`docs/01-resumen-supuestos-preguntas.md`](docs/01-resumen-supuestos-preguntas.md).

| Doc | Contenido | Entregables |
|---|---|:--:|
| [01](docs/01-resumen-supuestos-preguntas.md) | Resumen ejecutivo · supuestos · preguntas abiertas priorizadas | 1–3 |
| [02](docs/02-alcance-y-flujos.md) | Alcance funcional · flujos de usuario | 4–5 |
| [03](docs/03-arquitectura.md) | Arquitectura recomendada, alternativas comparadas y diagramas | 6–7 |
| [04](docs/04-modelo-de-datos.md) | Modelo de datos completo · diagramas entidad-relación | 8–9 |
| [05](docs/05-api.md) | Diseño de las APIs principales | 10 |
| [06](docs/06-roles-permisos.md) | Matriz de roles y permisos | 11 |
| [07](docs/07-historias-y-criterios.md) | 16 historias de usuario con criterios Given/When/Then | 12–13 |
| [08](docs/08-ux-pantallas.md) | Bocetos textuales de las 19 pantallas | 14 |
| [09](docs/09-fotografias.md) | Estrategia de fotografías | 15 |
| [10](docs/10-capex-precios.md) | Motor de CAPEX y normalización de precios | 16 |
| [11](docs/11-pptx.md) | Lectura, mapeo y generación de PPTX | 17 |
| [12](docs/12-seguridad-privacidad-auditoria.md) | Seguridad, privacidad, RGPD y auditoría | 18 |
| [13](docs/13-pruebas.md) | Estrategia de pruebas | 19 |
| [14](docs/14-mvp-plan-riesgos.md) | Alcance del MVP · plan por fases · riesgos | 20–22 |
| [15](docs/15-estructura-carpetas.md) | Estructura inicial del proyecto | 23 |
| [16](docs/16-requisitos-no-funcionales.md) | Objetivos no funcionales verificables | §10 |

### Convención de etiquetas

| Etiqueta | Significado |
|---|---|
| `[REQ]` | Requisito solicitado explícitamente |
| `[SUP]` | Supuesto adoptado por falta de información. Modificable |
| `[REC]` | Recomendación técnica propia, no solicitada |
| `[LIM]` | Limitación técnica real, conocida y verificable |
| `[PDV]` | Pendiente de validar (legal, técnica o de negocio) |

---

## Las tres cosas que hay que decidir para avanzar

Ninguna bloquea el inicio del trabajo —hay un supuesto operativo para cada una—, pero las tres
condicionan decisiones difíciles de revertir:

1. **`P-01` · ¿Pueden facilitarse 2–3 plantillas PPTX reales?** Es la pregunta más urgente. La
   generación de informes conservando el formato corporativo es el riesgo número uno del proyecto, y
   sin plantillas reales queda sin medir. El plan reserva las semanas 2–3 para una prueba de concepto
   dedicada precisamente a esto.
2. **`P-02` · ¿SaaS multi-cliente o instalación única?** Cambia el aislamiento de datos, el
   onboarding y el modelo de permisos. Se asume SaaS multi-organización con RLS, que es la opción
   menos costosa de simplificar después.
3. **`P-03` · ¿Se dispone de licencia de alguna base de precios?** Es la diferencia entre un CAPEX
   con precios reales y un formulario. El MVP funciona sin ella (entrada manual y catálogo propio),
   pero su valor sube mucho con ella.

El listado completo, con las 22 preguntas ordenadas por impacto, está en
[`docs/01`](docs/01-resumen-supuestos-preguntas.md) §3.

---

## Limitaciones declaradas por adelantado

Se enumeran aquí, y no enterradas en un anexo, porque condicionan expectativas:

- `[LIM]` La biblioteca de PPTX con licencia permisiva más madura **no ofrece duplicado oficial de
  diapositivas ni renderizado**. Se resuelve con un contrato de plantilla documentado y con
  previsualización mediante LibreOffice, cuyo resultado **no es idéntico** al de PowerPoint. Planes
  alternativos identificados y valorados en [`docs/11`](docs/11-pptx.md) §17.9.
- `[LIM]` La detección de textos que desbordan es una **estimación** por métricas de fuente, con un
  margen esperado de ±10–15 %. El aviso lo dice explícitamente al usuario.
- `[LIM]` **Ninguna fuente externa de precios está integrada ni probada.** No se nombra ninguna API
  ni base de datos concreta: activarlas exige decisiones legales del cliente. El MVP incluye entrada
  manual con justificación obligatoria e importación de catálogo propio licenciado.
- `[LIM]` La resolución de conflictos del MVP es *última escritura gana a nivel de campo*, con
  registro del valor descartado y aviso. La fusión asistida y el modo offline completo son fase
  posterior.
- `[LIM]` **Ninguna función de IA en el MVP.** Y si se incorpora, será con consentimiento explícito,
  marcado visible, revisión humana obligatoria y sin usar datos de cliente para entrenamiento.

---

## Alcance del MVP en una línea

> Un consultor debe poder llevar a cabo una due diligence técnica real de principio a fin —desde
> abrir el proyecto hasta emitir el PPTX— **sin salirse de la herramienta ni una sola vez.**

Estimación: **16 semanas** con el equipo supuesto (1 tech lead + 2 full stack + diseñador y QA a
media jornada). Detalle por fases, hitos y criterios de aceptación en
[`docs/14`](docs/14-mvp-plan-riesgos.md).

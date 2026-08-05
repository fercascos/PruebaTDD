# 20. Prueba de concepto del bloque 4 (PPTX)

> **Qué es este documento.** El resultado de la prueba de concepto que
> [`15`](./15-mvp-plan-riesgos.md) §21.3 planificaba para las semanas 2-3. Responde a sus preguntas con
> **números medidos sobre la plantilla real del cliente**, y **corrige cuatro afirmaciones** del
> análisis anterior que no resistieron el contacto con el render.

---

## 20.0. Lo primero: la limitación que declaré ya no existe

`[LIM]` En [`18`](./18-analisis-plantillas-reales.md) §18.0 declaré que **no había visto ninguna
plantilla renderizada** porque LibreOffice no arrancaba. Esa limitación **queda resuelta**, y el motivo
era más simple de lo que parecía: el entorno tenía `libreoffice-core` pero **no el módulo Impress**, de
modo que el filtro de importación de PPTX sencillamente no existía. Sin Impress, LibreOffice tampoco
podía abrir un `.txt`, que fue la pista.

Instalado el paquete, las cuatro plantillas se convierten a PDF sin incidencias:

| Medición | Valor |
|---|---|
| Plantilla A_ES, 67 diapositivas → PDF | **5,8 s** |
| Tamaño del PDF | 3,4 MB |
| Diapositivas perdidas o dañadas | **0** |

`[REC]` **Consecuencia para el plan:** la previsualización dentro de la aplicación es viable y rápida.
Seis segundos para un informe completo es tiempo de trabajo asíncrono cómodo, no un problema.

---

## 20.1. Lo que la prueba de concepto ha construido

Código real, no un prototipo desechable: los módulos quedan en `apps/api/src/tdd/reporting/` y
`exports/`, y son los que usará el MVP.

| Módulo | Qué hace |
|---|---|
| `reporting/fonts.py` | Métricas reales de las familias instaladas. **Si una falta, lo declara**: nunca mide en silencio con una sustituta |
| `reporting/overflow.py` | Estimación de desbordamiento con esas métricas |
| `reporting/capex_layout.py` | **`CapexTableLayout`**: el diseño de la tabla, en un solo sitio `[REQ]` P-31 |
| `reporting/pptx_table.py` | Tabla **nativa** de PowerPoint desde ese diseño |
| `exports/capex_xlsx.py` | Hoja `CAPEX` del Excel, **desde el mismo diseño** |
| `reporting/clone.py` | Clonado de diapositivas y sustitución de marcadores |
| `tools/poc_pptx.py` | El guion que lo ejecuta punta a punta |

---

## 20.2. Respuestas a las preguntas de §21.3

### ✅ ¿El clonado produce diapositivas indistinguibles del original?

**Sí.** Se clonó la diapositiva 13 (Cimentación + Estructura) tres veces y se renderizó. Conservados:
cabecera con el número de sección y el color corporativo, **marca de agua «DRAFT»**, logo, pie con
numeración, y los estilos de párrafo (negrita subrayada en los títulos de bloque, cursiva en
«Valoración», justificado en el cuerpo).

`[LIM]` El clonado usa `_add_relationship`, **API interna de `python-pptx`**: la biblioteca no
contempla duplicar diapositivas y no hay equivalente público. Funciona, y las cuatro plantillas reales
lo ejercen en el corpus, pero **una actualización de la biblioteca puede romperlo**. Queda anotado.

### ✅ ¿La sustitución de marcadores conserva el formato?

**Sí, y la cadena completa funciona.** Se preparó una copia de la plantilla convirtiendo sus huecos
`XXXX` en marcadores `{{...}}`, se clonó y se rellenó con texto real de informe. Resultado: cero
marcadores sin resolver, **cero literales `{{...}}` en la salida** y formato intacto.

`[REQ]` **Dato importante para el calendario: la plantilla del cliente NO tiene marcadores.** Tiene
huecos `XXXX`. Prepararla es trabajo real —el que estimé en ~1,5 jornadas— y **es requisito previo a
generar nada**. La prueba de concepto lo confirma: sin preparar, el clonado funciona pero la
sustitución no tiene dónde escribir.

### ✅ ¿La tabla nativa reproduce el formato del Excel? `[REQ]` P-31

**Sí, y con mucha fidelidad.** Puestas al lado la imagen EMF original y la tabla generada, se
reproducen: banda de título verde a todo lo ancho, cabecera de dos niveles con `CAPEX ESTIMADO`
combinado sobre las columnas de plazo, columna `Grupo` con fondo oro, **un color por plazo** (rosa,
amarillo, verde, azul), filas de sección en gris con sus subtotales, numeración jerárquica (`1.`,
`1.1`, `2.`, `2.1`…), importes alineados a la derecha y **celdas en blanco cuando no hay importe**.

| Medición | Original | Generada |
|---|:--:|:--:|
| Ancho total | 9,06 in | **9,37 in** (con la quinta columna de P-37) |
| Columnas | 10 | **11** |
| Filas por diapositiva | ~18 | 18, con partición y arrastre de sección |

### ✅ ¿El XLSX cuadra con la tabla del informe?

**Sí, por construcción.** Ambos consumen el mismo `CapexTableLayout`. La prueba de contrato compara
encabezados, número de columnas, orden y valores celda a celda, y falla si alguien añade una columna
en un solo generador.

### 🟡 ¿La estimación de desbordamiento es útil?

**Sí, y mejor de lo previsto — con una salvedad.** Sobre el render real:

| | Valor |
|---|:--:|
| Primera línea renderizada del cuerpo | **117 caracteres** |
| Estimación del motor | **119 caracteres** |
| Desviación | **1,7 %** |

`[LIM]` **La salvedad importa:** el render sustituyó la fuente (ver §20.3), de modo que esos 117
caracteres no se compusieron con la tipografía que el motor midió. La coincidencia valida **el método**
—medir avances reales y aplicar un factor de ajuste de línea— pero **no** el emparejamiento concreto de
fuente. El margen declarado de ±10-15 % sigue siendo el compromiso honesto.

### ✅ ¿Cuánto tarda?

| Operación | Tiempo |
|---|---|
| Abrir plantilla de 67 diapositivas, clonar 3, generar tabla y guardar | **482 ms** |
| Render completo a PDF (71 diapositivas) | 5,8 s |

Muy holgado frente al objetivo P-14.

---

## 20.3. Lo que el render corrige del análisis anterior

Cuatro afirmaciones de [`18`](./18-analisis-plantillas-reales.md) eran **incorrectas**. Todas venían de
haber reconstruido la tabla a partir de los registros de texto del metarchivo, que dan el texto pero no
la rejilla. Verlo renderizado lo resolvió en un minuto.

### C-6 · La tabla tiene **10 columnas**, no 8, y en otro orden

La estructura real es:

```
┌────┬──────────────┬─────────┬─────────────┬───────┬──────────┬───────────────────────────┐
│Nº  │Affected area │ Purpose │ Description │ Group │ Comments │     ESTIMATED CAPEX       │
│    │              │         │             │       │          ├──────┬─────┬─────┬───────┤
│    │              │         │             │       │          │Short │Mid  │Long │Improv.│
└────┴──────────────┴─────────┴─────────────┴───────┴──────────┴──────┴─────┴─────┴───────┘
```

Dos columnas que no había detectado —**`Nº`** y **`Group`**— y **`Comments` va ANTES de las columnas de
plazo**, no después. Ya está corregido en `capex_layout.py`.

### C-7 · Sí lleva riesgo: es la columna `Group`

Afirmé que «la tabla no lleva ni código ni riesgo». **Es falso.** La columna `Group` contiene
`High` / `Moderate` / `Low`: **es el grado de riesgo**, con su propio fondo oro para destacarla.

`[PDV]` **P-42 · La tabla usa tres niveles y el catálogo tiene cuatro.** El catálogo de §5.4 define
`01 Bajo`, `02 Moderado`, `03 Alto` y `04 Extremo`, con sus definiciones íntegras. La tabla real solo
muestra tres. ¿Se agrupan Alto y Extremo al presentar, o el Excel simplemente no ha usado Extremo en
este ejemplo? Se genera con los cuatro hasta que se aclare.

### C-8 · El cuerpo de las diapositivas de sistema es **Century Gothic**, no Gotham

La diapositiva 13 declara `Century Gothic` en sus **32** ejecuciones de texto. El tema, por su parte,
declara `Calibri`. Gotham aparece en otras diapositivas, pero **la mezcla tipográfica es más profunda
de lo que dije**: no es «Gotham en el informe y Century Gothic en las tablas», son tres familias
repartidas.

`[REC]` Esto **amplía el alcance de P-38**, no lo cambia. La decisión de unificar en Gotham sigue
siendo la correcta y el `+4,9 %` de anchura medido sigue valiendo, pero afecta a **todo el cuerpo del
informe**, no solo a la tabla de CAPEX. Conviene saberlo antes de preparar la plantilla piloto.

### C-9 · Hay una marca de agua «DRAFT»

Diagonal, gris, sobre todas las diapositivas. El análisis estructural no la distinguió de otra
autoforma. `[PDV]` **P-43:** ¿debe retirarse al emitir la versión definitiva? Lo natural es que sí, y
sería una directiva `@watermark: remove_on_issue` en el contrato de plantilla.

---

## 20.4. El hallazgo que **contradice una decisión cerrada**

Y por eso va en su propio apartado.

`[REQ]` **P-05 quedó decidida así:** *«una línea, un horizonte, un importe. Corto, medio, largo, mejora
potencial u otro tipo de petición son mutuamente excluyentes.»*

**Los datos reales de la plantilla no cumplen esa regla.** Extraídos los importes de la tabla de
CAPEX con sus posiciones de columna:

| Tabla | Filas con importe | **Con importe en MÁS DE UN plazo** |
|---|:--:|:--:|
| Arquitectura (`image24`) | 20 | **6** (una es el subtotal de sección) |
| Resumen (`image27`) | 5 | 5 *(son filas de totales)* |
| Instalaciones (`image31`) | 24 | 11 |

En la tabla de detalle de Arquitectura, **5 de 19 filas de datos** —un 26 %— llevan importe en dos
columnas de plazo. Y el patrón es constante: **el mismo importe repetido en «Largo plazo»**.

```
2.1  Limpieza de lucernarios      Corto  2.300,00 €   ·  Largo  2.300,00 €
2.2  Renovación impermeabilización Medio 83.407,50 €  ·  Largo 83.407,50 €
2.5  Sellado de fachadas          Corto 32.970,00 €   ·  Largo 32.970,00 €
```

**Dos lecturas posibles**, y no me corresponde elegir:

| Lectura | Qué implicaría |
|---|---|
| **A · Son actuaciones recurrentes.** La limpieza de lucernarios hace falta ahora **y otra vez** dentro del horizonte de 10 años | P-05 se mantiene para el dato, pero una **actuación** puede generar **varias líneas**, una por plazo. El modelo ya lo permite: `Finding` 1 → N `CapexItem` |
| **B · «Largo plazo» es una columna acumulada** a diez años, no un plazo excluyente | Cambiaría el significado de la columna en el informe. El modelo no cambia; el pivote sí |

> **P-44 · DECIDIDO por el cliente: opción A.** Son **actuaciones recurrentes**. Una actuación que
> hace falta ahora y otra vez dentro del horizonte de diez años genera **dos líneas de CAPEX**, una
> por plazo, y se presenta como **una sola fila de la tabla con dos columnas rellenas**.

### Qué ha cambiado, y qué no

`[REQ]` **P-05 sigue intacta.** Una **línea** tiene un horizonte y un importe: eso no se ha tocado. Lo
que puede tener varias líneas es la **actuación**. La distinción no es un tecnicismo: mantiene la
garantía que P-05 buscaba —que un importe no quede repartido por descuido entre dos plazos— y a la vez
recoge lo que sus datos hacen.

| Nivel | Regla |
|---|---|
| **Línea** (`capex_item`) | Un horizonte, un importe. **P-05** |
| **Actuación** (`finding`) | Puede tener varias líneas, **una por plazo**. **P-44** |
| **Fila de la tabla** | Una por actuación, con tantas columnas rellenas como plazos tenga |

**Un cambio en el esquema.** Tenía un índice único por `finding_id` que impedía justo esto —venía de
leer «relación 1:1» en el diseño—. Se sustituye por `UNIQUE (finding_id, time_horizon_id)`, que sigue
impidiendo lo que sí es un error: dos líneas de la misma actuación en el **mismo** plazo, que serían un
duplicado y no una recurrencia.

**Los totales suman las dos líneas**, y no es doble contabilidad: son dos desembolsos reales en dos
momentos distintos.

---

## 20.5. Riesgo R1, reevaluado por tercera vez

| Momento | Probabilidad | Impacto | Por qué |
|---|:--:|:--:|---|
| Diseño inicial | Alta | Crítico | Sin plantillas, todo eran supuestos |
| Tras el análisis estructural (doc 18) | Media | Crítico | Sin gráficos ni SmartArt; una sola estructura |
| **Tras esta prueba de concepto** | **Baja** | **Alto** | **Clonado, sustitución, tabla nativa y render verificados sobre la plantilla real** |

`[REC]` **El bloque 4 deja de ser el mayor riesgo del proyecto.** Lo que queda no es incertidumbre
técnica, es trabajo conocido: preparar las plantillas (~1,5 jornadas cada una) y decidir P-44.

**Lo que sigue sin verificarse**, y conviene no darlo por bueno:

- `[LIM]` **No se ha abierto nada en PowerPoint.** Todo el render es de LibreOffice, que no compone
  igual. La comparación LibreOffice ↔ PowerPoint sigue pendiente y **necesita una máquina con Office**.
- `[LIM]` **Century Gothic no está instalada** en el entorno de prueba, de modo que el render la
  sustituyó. Las longitudes de línea del render son aproximadas por ese motivo.
- No se han probado las **fotografías**: el bloque de evidencia todavía no existe.

---

## 20.6. Preguntas nuevas

| # | Pregunta | Impacto | Propuesta |
|---|---|---|---|
| ~~**P-44**~~ | ~~¿Una actuación puede tener importe en dos plazos?~~ | — | ✅ **CERRADA: opción A.** Actuaciones recurrentes. Un hallazgo genera varias líneas, una por plazo, y se presentan en una sola fila. **P-05 sigue intacta a nivel de línea** |
| **P-42** | La tabla muestra **tres** niveles de riesgo y el catálogo tiene **cuatro**. ¿Se agrupan Alto y Extremo al presentar? | Medio | Generar con los cuatro; agrupar es una regla del mapeo |
| **P-43** | ¿La marca de agua **DRAFT** se retira al emitir la versión definitiva? | Bajo | Sí, con `@watermark: remove_on_issue` |

---

## 20.7. Material del cliente

`[REQ]` Las cuatro plantillas y los renders generados **no están en el repositorio**, y no deben
estarlo: llevan la identidad corporativa de la consultora y datos de un activo identificable. El
`.gitignore` excluye `tests/fixtures/real/`, y `tools/poc_pptx.py` recibe la plantilla **por ruta**,
nunca desde el árbol de código.

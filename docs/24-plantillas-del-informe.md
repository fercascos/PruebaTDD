# 24 · Cómo preparar una plantilla del informe

`[REQ]` El cliente lo pidió así: *«que te suba yo unas plantillas en PPT y tú
vayas rellenando con los textos que aparecen en la aplicación las distintas
slides del informe, de tal modo que se pueda luego exportar en PPT y terminar de
editar o corregir cualquier defecto por fuera de la aplicación»*.

Esta página es lo que hay que saber para preparar una de esas plantillas. No
hace falta leer [`12`](./12-pptx.md), que es la especificación técnica.

---

## 1 · La idea en una frase

Se escribe **`{{algo}}`** dentro de un cuadro de texto de tu PowerPoint, y la
aplicación lo cambia por el dato **sin tocar nada más**: la tipografía, el
cuerpo, el color, la posición y el fondo siguen siendo los tuyos. Lo que sale es
tu plantilla con los datos dentro, y se abre en PowerPoint como cualquier otro
fichero.

```
        TU PLANTILLA                        EL INFORME GENERADO
┌──────────────────────────┐       ┌──────────────────────────────┐
│  {{asset.name}}          │       │  Nave A · Getafe Norte        │
│  Superficie: {{asset.    │  ──►  │  Superficie: 12.450 m²        │
│  total_built_sqm}} m²    │       │                               │
│  CAPEX: {{asset.capex_   │       │  CAPEX: 211.707,50 €          │
│  total}}                 │       │                               │
└──────────────────────────┘       └──────────────────────────────┘
```

`[REQ]` **La plantilla original no se toca jamás.** Se abre, se trabaja sobre una
copia en memoria y se guarda en un fichero nuevo. Hay una prueba que comprueba
el hash del fichero antes y después.

---

## 2 · Una diapositiva por activo, o por hallazgo

Un proyecto de cartera tiene seis activos y cuarenta hallazgos, y tu plantilla
tiene **una** diapositiva de activo. En las **notas del orador** de esa
diapositiva se escribe una línea:

```
@repeat: asset
```

y la aplicación la duplica una vez por activo, rellenando cada copia con **sus**
datos. Lo mismo con `@repeat: finding` para los hallazgos.

Van en las notas y no en el cuerpo **porque no se imprimen**: la diapositiva se
ve igual en la plantilla y en el informe, y la instrucción no se cuela en un
entregable si alguien se olvida de borrarla.

| En las notas | Qué hace |
|---|---|
| `@repeat: asset` | Una diapositiva por activo del proyecto |
| `@repeat: finding` | Una diapositiva por hallazgo |
| `@max: 20` | Tope, por si un proyecto se dispara. Lo que quede fuera se avisa |

Tres cosas que conviene saber:

- **Las copias van en el sitio del modelo**, no al final. Un informe cuyas
  diapositivas de activo aparecen detrás de las conclusiones no es el informe
  que se diseñó.
- **La diapositiva modelo desaparece** del informe. Si se quedara, saldría con
  los `{{marcadores}}` a la vista.
- `[LIM]` **Una colección vacía retira la diapositiva.** Un proyecto sin
  hallazgos no produce una diapositiva de hallazgo en blanco, que es lo que
  delata un informe hecho a máquina. Si lo que se quería era ver el hueco, se
  quita el `@repeat`.

---

## 3 · Los 70 marcadores

`[REQ]` **Cualquier marcador fuera de esta lista se queda sin resolver**, y la
generación lo dice por su nombre en vez de dejarlo escrito en el informe.

### Proyecto y cliente · valen en cualquier diapositiva

| Marcador | Qué escribe |
|---|---|
| `{{project.code}}` | `2026-014` |
| `{{project.name}}` | Nombre del encargo |
| `{{project.status}}` | Borrador, en curso… |
| `{{project.currency}}` | `EUR` |
| `{{project.asset_count}}` | Cuántos activos |
| `{{project.finding_count}}` | Cuántos hallazgos |
| `{{client.name}}` | Nombre del cliente. `{{project.client}}` es el nombre antiguo del mismo dato y sigue valiendo |
| `{{report.date}}` | Fecha del informe, `AAAA-MM-DD` |
| `{{report.generated_at}}` | Fecha y hora completas |

### CAPEX · agregados del proyecto

| Marcador | Qué escribe |
|---|---|
| `{{capex.total}}` | El total |
| `{{capex.corto}}` `{{capex.medio}}` `{{capex.largo}}` `{{capex.mejoras}}` `{{capex.otro}}` | Por plazo |
| `{{capex.propiedad}}` | Lo que asume la propiedad `[REQ]` §3.3 |
| `{{capex.inquilino}}` | Lo repercutible al inquilino |
| `{{capex.sin_determinar}}` | Lo que nadie ha decidido todavía |

### Riesgo

| Marcador | Qué escribe |
|---|---|
| `{{risk.01}}` … `{{risk.04}}` | Importe de cada grado |
| `{{risk.legend}}` | La leyenda con la **definición íntegra** de los cuatro grados. Sin ella, «Alto» es una palabra sin criterio detrás |

### Limitaciones y visitas

| Marcador | Qué escribe |
|---|---|
| `{{report.limitations}}` | Todas, una por línea. `[REQ]` Declarar qué no se ha podido revisar es obligación profesional en una TDD |
| `{{report.limitations_docs}}` | Solo las de documentación que no llegó |
| `{{report.limitations_qa}}` | Solo las preguntas sin respuesta |
| `{{report.limitations_content}}` | Solo las que salen del contenido de un documento recibido |
| `{{report.limitations_count}}` | Cuántas son |
| `{{visit.dates}}` · `{{visit.count}}` | Cuándo se visitó y cuántas veces |
| `{{visit.access_limitations}}` | A dónde no se pudo entrar |

### Activo · en una diapositiva con `@repeat: asset`, el suyo

`{{asset.name}}` · `{{asset.code}}` · `{{asset.typology}}` · `{{asset.address}}` ·
`{{asset.city}}` · `{{asset.year_built}}` · `{{asset.year_last_refurb}}` ·
`{{asset.total_built_sqm}}` · `{{asset.plot_area_sqm}}` ·
`{{asset.warehouse_area_sqm}}` · `{{asset.office_area_sqm}}` ·
`{{asset.warehouse_height_m}}` · `{{asset.floors_above}}` ·
`{{asset.floors_below}}` · `{{asset.finding_count}}` · `{{asset.capex_total}}` ·
`{{asset.capex_propiedad}}` · `{{asset.capex_inquilino}}` ·
`{{asset.visit_date}}` · `{{asset.access_limitations}}`

Y los dos que son **texto escrito por el gestor técnico** `[REQ]` §3.2 d:

| Marcador | Qué escribe |
|---|---|
| `{{asset.descriptivo}}` | El descriptivo de cada objeto: *qué hay*. Sale de la memoria técnica |
| `{{asset.valoracion}}` | La valoración de cada objeto: *en qué estado está*. La escribe quien fue a verlo |

`[REQ]` Los dos traen **solo lo validado**. Un descriptivo pendiente de validar
es un borrador, y colarlo en un entregable firmado le quitaría a esa casilla
todo su sentido.

`[SUP]` Fuera de una diapositiva repetida, `{{asset.*}}` enseña **el primer
activo**. En un proyecto de un edificio —la mayoría— es lo correcto y no obliga
a marcar nada.

### Hallazgo · en una diapositiva con `@repeat: finding`, el suyo

`{{finding.title}}` · `{{finding.description}}` · `{{finding.comments}}` ·
`{{finding.recommendation}}` · `{{finding.zone}}` · `{{finding.capex_code}}` ·
`{{finding.capex_type}}` · `{{finding.capex_chapter}}` · `{{finding.capex_item}}` ·
`{{finding.risk_code}}` · `{{finding.risk_name}}` · `{{finding.risk_definition}}` ·
`{{finding.concept}}` · `{{finding.amount}}` · `{{finding.horizons}}` ·
`{{finding.payer}}`

---

## 3 bis · Las secciones del Full Report, atadas a su código

`[REQ]` §3.2 · Es lo que pide la plantilla real del cliente, y no se vio hasta
abrirla. Su Full Report tiene **quince secciones de sistema ya maquetadas a
mano** —«CUBIERTA», «FACHADAS», «ELECTRICIDAD Y ILUMINACIÓN»…—, cada una con su
pareja de diapositivas: una de texto y otra de cuatro fotos.

**No son una repetición.** Están escritas, numeradas y ordenadas en las 67
diapositivas, y el índice las enumera. Repetir una diapositiva modelo produciría
otro informe, no el suyo. Lo que hace falta es **atar cada sección a su código
del árbol**, y para eso el marcador lleva el código dentro:

```
{{descriptivo:HC.H02}}      el descriptivo de todo el capítulo «Cubierta»
{{valoracion:HC.H04.03}}    la valoración del objeto «Suelos y techos»
{{capex:HC.H09}}            el importe de los hallazgos de Electricidad
{{hallazgos:HC.H09}}        sus títulos, uno por línea
```

Un código de **capítulo** agrega lo de todos sus objetos; uno de **objeto** trae
solo lo suyo. La correspondencia no es de un solo nivel: «CUBIERTA» es el
capítulo `HC.H02` entero, pero «SUELOS Y TECHOS» es el objeto `HC.H04.03`,
porque el informe desglosa interiores en tres secciones.

`[REQ]` **Una sección sin datos sale en blanco**, no con el marcador a la vista.
Un edificio sin nada de telecomunicaciones deja esa diapositiva vacía, que es lo
que el consultor rellenaría a mano; el marcador escrito saldría impreso delante
del cliente. La respuesta de generación los lista aparte: no son «un marcador
que no existe», son «una sección de la que este edificio no tiene nada».

### No hace falta escribirlos a mano

    python3 tools/marcar_plantilla.py original.pptx marcada.pptx

Lee los títulos de la plantilla, los ata a su código y escribe los marcadores
**conservando el formato**. El original no se toca. Si algún marcador queda en
mal sitio, se corrige en PowerPoint.

`[SUP]` La correspondencia título → código está deducida comparando los títulos
de la plantilla con el árbol de §5.3 y **no está validada con el cliente**. Tres
entradas son discutibles y se señalan en la tabla del propio fichero.

---

## 4 · Lo que todavía NO hace

`[LIM]` Se dice porque el informe es un entregable firmado y conviene saber
dónde está el límite hoy:

- **Las fotografías no se insertan.** Cada sección del Full Report tiene su
  diapositiva con cuatro marcos 3,15 × 2,36 in y sus cuatro pies «Descripción»:
  se quedan vacíos. Es la pieza más visible de las que faltan.
- **La tabla del CAPEX se añade en diapositivas en blanco al final**, con el
  diseño de la aplicación y no con el tuyo. La plantilla tiene su propia sección
  07 CAPEX con seis diapositivas de imágenes EMF, y ahí es donde debería ir.
- **No hay filas repetibles dentro de una tabla** (`{{#row ...}}` de
  [`12`](./12-pptx.md) §17.2). Una tabla de la plantilla se queda como está.
- **No se insertan imágenes por marcador** (`{{@asset.main_photo}}`).
- **No hay formatos ni valores por omisión** en el marcador
  (`{{capex.total|#,##0 €}}`, `{{asset.year|default:No consta}}`). Los importes
  salen ya formateados en euros y las fechas en `AAAA-MM-DD`.
- **No hay `@filter`, `@sort` ni `@group_by`.** Los activos salen por nombre y
  los hallazgos por código de CAPEX, que es el orden del snapshot.

---

## 5 · Cómo se comprueba antes de generar

1. Se sube la plantilla en **Plantillas**. Se analiza al subirla: dice cuántas
   diapositivas tiene, qué marcadores ha encontrado, qué tipografías usa y si
   trae marca de agua.
2. Al generar, la respuesta trae **qué marcadores no se han podido resolver**,
   **qué textos probablemente no caben en su marco** —medido con la tipografía
   real de la plantilla, no con una sustituta— y **qué ha pasado con las
   repeticiones**.
3. `[REQ]` La marca de agua de borrador **se retira** de lo generado (P-43), y
   se avisa de que estaba.

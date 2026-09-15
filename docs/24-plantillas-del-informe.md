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
de la plantilla con el árbol de §5.3. La mayoría es literal. Las dos que no lo
son van marcadas `[PDV]` en la tabla del propio fichero.

`[REQ]` **«Protección contra incendios» es la ACTIVA, y va en instalaciones.**
Lo pidió el cliente con estas palabras: *«sobre Protección contra Incendios,
esto debe ir en el análisis técnico de instalaciones»*. Es donde su propia
plantilla la tiene —diapositiva 38, bajo la cabecera «ANÁLISIS TÉCNICO ·
INSTALACIONES»— y se ata a `HC.H10`. La **pasiva** es obra —sectorización,
resistencia al fuego de la estructura— y se queda en su sección de
ARQUITECTURA, atada a `HC.H06`.

---

## 3 ter · Las fotografías y la tabla de CAPEX, en su sitio de la plantilla

Las dos van en las **notas del orador**, que no se imprimen, y las escribe
`marcar_plantilla.py` sin que nadie teclee nada.

### `@fotos: <códigos>` · los recuadros azules

`[REQ]` Con las palabras del cliente: *«todas las fotos que vayamos adjuntando
en la parte de inventario deberán aparecer en cada recuadro azul y el pie de
cada foto, lo que aparece en la plantilla como "Descripción", es el título de
esa foto»*.

La diapositiva siguiente a la de texto de cada sección recibe la directiva con
el código de esa sección. Entonces:

- Van sus fotografías, **las del árbol de esa sección**: una foto de `HC.H02.01`
  cae en la diapositiva de `@fotos: HC.H02`, porque el capítulo recoge lo de sus
  objetos.
- Cada foto **conserva su proporción** dentro del marco y el marco desaparece:
  no se deforma para rellenar el hueco.
- El pie «Descripción» se sustituye por el **título de la foto** (`caption`).
- Los marcos que sobran **se vacían**. Un recuadro azul con «Descripción»
  debajo, impreso y vacío, delata el hueco.

Una diapositiva compartida por dos secciones lleva las dos, separadas por comas:
`@fotos: HC.H12, HC.H11` es la de ascensores y fontanería.

Solo entran las fotografías marcadas para el informe: subirlas no es elegirlas.
Y llevan su **objeto del árbol**, que es lo que las lleva a su sección; una foto
sin objeto se añade al final y se avisa.

### `@capex: <tablas>` · las cinco tablas de la sección 07

`[REQ]` *«En vez de la tabla que aparece ahí deberá ir la tabla pegada de CAPEX
de nuestra herramienta.»*

La sección 07 **no tiene una tabla: tiene cinco**, y las cinco venían pegadas
desde Excel como imagen, con los números de otro proyecto. Cada diapositiva
declara en sus notas cuál le toca:

| En las notas | Qué recibe |
|---|---|
| `@capex: detalle:arquitectura` | La valoración de las actuaciones de obra, capítulos `HC.H01`–`HC.H07` |
| `@capex: riesgos:arquitectura` | Su matriz de grado de riesgo × plazo |
| `@capex: detalle:instalaciones` | Lo mismo para `HC.H08`–`HC.H15` |
| `@capex: riesgos:instalaciones` | Su matriz |
| `@capex: capitulos, riesgos` | El resumen por capítulo y la matriz del proyecto entero, apilados |
| `@capex: costes` | El presupuesto: costes duros, blandos y total sin IVA |

`@capex` a secas sigue significando `@capex: detalle`, la tabla completa sin
partir por bloques: una plantilla marcada antes de esto genera lo mismo que
generaba.

**Cada tabla ocupa el hueco de la imagen que sustituye.** Eso es lo que permite
que en la página de la matriz de riesgo **la leyenda se quede**: los cuatro
grados y la escala de plazos son otras dos imágenes, más pequeñas, y no se
tocan. Si dos tablas comparten una sola imagen —el resumen por capítulo y la
matriz vienen juntas en una— la segunda se apila debajo de la primera.

Si una tabla no cabe en una diapositiva, se parte: cada trozo se lleva su copia
de la diapositiva de la plantilla —con su cabecera y su pie— y salen
**seguidas**, numeradas «(1/2)», «(2/2)».

`[REQ]` **Nada se pierde entre las dos tablas de detalle.** Lo que no es obra
—costes blandos, licencias, imprevistos— no cabe en la «valoración de las
actuaciones necesarias en el inmueble» y sale en el resumen por capítulo y en el
presupuesto, que es donde el total del proyecto se ve entero. Y un capítulo de
obra que alguien añada al árbol y no esté repartido entre los dos bloques
**produce un aviso al generar**: sumaría en los resúmenes sin salir en ninguna
tabla de detalle, y esa diferencia no se ve salvo cuadrando las cifras a mano.

`[SUP]` Que la matriz que va **detrás** de cada tabla de detalle sea la de *ese*
bloque, y no la del proyecto entero, es lectura nuestra: la plantilla trae las
dos con las mismas cifras, que es lo que pasa cuando un ejemplo se copia y no se
actualiza. Si se quieren globales, se le quita el bloque a la directiva en las
notas —`@capex: riesgos`— y no hay que tocar nada más.

`[SUP]` El desglose de **costes blandos** de la plantilla lista siete conceptos
—dirección facultativa, DEO, project monitoring, PRL, ECLU, ICIO y otras
licencias—. Nuestro árbol tiene cuatro capítulos de coste blando, y **no** esos
siete: se enseñan los nuestros. Inventar sus siete etiquetas y repartir importes
entre ellas sería fabricar un desglose.

---

## 3 quater · La cabecera y la portada

### El nombre del proyecto vive en el **patrón**, no en las diapositivas

`[REQ]` La plantilla del cliente pone «NOMBRE DEL PROYECTO» debajo del título de
sección en lo alto de cada página. Ese rótulo **no está en ninguna de sus
sesenta y siete diapositivas**: está en **once patrones**, uno por sección
—«ANÁLISIS TÉCNICO ARQUITECTURA», «ESTIMACIÓN ECONÓMICA - CAPEX»…—, y es el
patrón el que lo pinta en todas.

Por eso la generación sustituye marcadores **también en los patrones**. Un
`{{project.name}}` escrito ahí rellena el informe entero de una vez; escrito
diapositiva a diapositiva habría que ponerlo sesenta y siete veces.

`[LIM]` **En un patrón no caben los marcadores de activo ni de hallazgo.** El
patrón es uno para todas sus páginas, así que `{{asset.name}}` saldría igual en
todas, con los datos del primero. Se avisa al generar en vez de dejarlo pasar,
porque desde fuera parece que la repetición no funciona.

El análisis de la plantilla los lista aparte, en `master_placeholders`: quien
mire el análisis no los encontrará abriendo las páginas.

### La portada

| Lo que pone la plantilla | Lo que recibe |
|---|---|
| El hueco de debajo del título | `{{project.name}}` |
| «Febrero 2026» | `{{report.month}}` |

`{{report.month}}` es la fecha del informe escrita como la escribe una portada
—«Septiembre 2026»—, no `AAAA-MM-DD`. Es el mismo dato con otro formato, no un
dato nuevo.

`[REQ]` La fecha de la plantilla **no es un relleno**: es una fecha de verdad, de
otro encargo. Se sustituye igual, porque dejarla puesta sacaría el informe con la
fecha de otro proyecto.

`[SUP]` Que el hueco de debajo del título sea el **nombre del proyecto** es
lectura nuestra: la plantilla pone «XXX» y no dice de qué. Si ahí va la dirección
del inmueble, se cambia el marcador a mano en PowerPoint.

### La ficha del edificio

| Título en la plantilla | Lo que recibe |
|---|---|
| EMPLAZAMIENTO · LOCATION | `{{asset.address}}` |
| DESCRIPCIÓN · DESCRIPTION | `{{asset.descriptivo}}` |

Estas dos diapositivas reciben además **`@repeat: asset`**: son datos de **un
edificio**, y un proyecto de cartera tiene varios. Sin repetirse, el informe
enseñaría la ficha del primero y callaría las demás.

`[LIM]` Con varios activos las fichas salen **agrupadas por diapositiva**, no por
edificio: primero todos los emplazamientos y después todas las descripciones. Es
consecuencia de que la plantilla las tenga en dos páginas distintas.

### Lo que **no** se rellena, y por qué

`[LIM]` Cuatro huecos de la plantilla se quedan con su relleno «XXXX»:

- **Resumen ejecutivo de arquitectura** y **de instalaciones**
- **Análisis de licencias**
- **Documentación consultada**

La aplicación **no tiene ese dato**. Inventar un marcador para ellos daría un
informe con apartados vacíos y aire de estar terminado; dejar el relleno hace
visible que ahí le toca escribir a una persona.

---

## 4 · Lo que todavía NO hace

`[LIM]` Se dice porque el informe es un entregable firmado y conviene saber
dónde está el límite hoy:

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

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
| `{{project.summary}}` | La introducción que redacta el gestor: qué se compra, para qué y con qué alcance |
| `{{client.name}}` | Nombre del cliente. `{{project.client}}` es el nombre antiguo del mismo dato y sigue valiendo |
| `{{report.date}}` | Fecha del informe, `AAAA-MM-DD` |
| `{{report.month}}` | «Septiembre 2026», que es como lo escribe una portada |
| `{{report.generated_at}}` | Fecha y hora completas |
| `{{docs.consultados}}` | La documentación aportada, con el código de su nodo |
| `{{docs.consultados_count}}` | Cuántos documentos se consultaron |
| `{{docs.licencias}}` | El estado de la rama urbanística, agrupado por estado |

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
{{resumen:HC.H09}}          sus cifras: cuántas deficiencias, de qué riesgo y cuánto CAPEX
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

### `@rotulo: <marcador> = <texto>` · el rótulo que cae con su marcador

`[REQ]` El cliente lo pidió al ver el informe generado: *«quita el rótulo si no
hay valoración»*. Su plantilla escribe **«Valoración»** en un párrafo aparte,
encima del hueco, y ese párrafo no es un marcador: cuando no había valoración
que poner, el hueco se vaciaba —como debe— y el rótulo se quedaba solo,
encabezando media página en blanco. Un rótulo sin nada debajo se lee como un
fallo del informe.

`marcar_plantilla.py` lo ata: el párrafo del rótulo pasa a ser
`{{rotulo:valoracion:HC.H02}}` —conservando su formato, así que se sigue viendo
igual— y en las notas queda la línea que dice qué ponía:

    @rotulo: valoracion:HC.H02 = Valoración

Al generar, el rótulo sale con su texto si el marcador al que acompaña tiene
valor, y se vacía con él si no. No hace falta nada más: a partir de ahí lo
sustituye la maquinaria normal de marcadores.

`[REQ]` **El texto viaja en la directiva y no en una constante nuestra.** Es
palabra del cliente y cambia con el idioma: sus plantillas castellanas ponen
«Valoración» y las inglesas **«Valuation»**. Escribirlo en el código sería
traducirle el informe sin permiso, y además habría que acertar con la palabra
que usa cada corporativa.

`[LIM]` Un rótulo atado **no es un marcador que haya que mapear**. La
comprobación previa lo sabe: `rotulo:X` se da por resuelto si se resuelve `X`.
Sin eso, poner el rótulo en la plantilla **bloqueaba la generación entera**, que
es lo contrario de lo que venía a hacer —y así salió la primera vez que se probó
contra la plantilla real.

---

## 3 quater · La cabecera y la portada

### El nombre del proyecto vive en el **patrón**, no en las diapositivas

`[REQ]` La plantilla del cliente pone «NOMBRE DEL PROYECTO» debajo del título de
sección en lo alto de cada página. Ese rótulo **no está en ninguna de sus
sesenta y siete diapositivas**: está en **once patrones**, uno por sección
—«ANÁLISIS TÉCNICO ARQUITECTURA», «ESTIMACIÓN ECONÓMICA - CAPEX»…—, y es el
patrón el que lo pinta en todas.

`[REQ]` **Y no lo escriben igual las cuatro.** Hay tres grafías, y hay que
haberlas abierto para saberlo:

| Plantilla | Cómo rotula la cabecera |
|---|---|
| Modelo A · castellano | `NOMBRE DEL PROYECTO` |
| Modelo B · castellano | `NOMBRE PROYECTO` —sin el «DEL»— |
| Modelo A y B · inglés | `PROJECT NAME` |

La segunda faltaba, y la consecuencia era concreta: el Modelo B castellano
generaba **once páginas con el rótulo literal en la cabecera**.

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
| El hueco de debajo del título: `XXX`, `PROYECTO` o `PROJECT` | `{{project.name}}` |
| «Febrero 2026», `FECHA` o `Date` | `{{report.month}}` |

`[REQ]` **Tres formas de dejar el hueco, y solo una estaba contemplada.** El
Modelo A castellano pone un relleno de equis y una fecha; las otras tres ponen
**el nombre del campo**. Con solo la primera, tres de cada cuatro informes salían
titulados «PROJECT» y sin fecha. Y las dos inglesas ni siquiera se reconocían
como portada, porque escriben *«Technical Due Dilligence»* con la misma errata de
dos eles que las castellanas y la errata estaba contemplada solo en castellano.

`[REC]` **El resaltado amarillo del hueco no llega al informe.** Tres de las
cuatro lo marcan así —es su forma de decir «esto hay que rellenarlo», igual que
las equis— y conservarlo sacaba la portada con el nombre del cliente en
fosforito. Es la **única** excepción a conservar el formato del cliente, y se
aplica solo en la portada y solo al `run` que se reescribe: cuerpo, color y
tipografía se mantienen.

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

### El resumen ejecutivo

La sección 01 de la plantilla son **dos diapositivas**: «Arquitectura:» y
«Instalaciones:», cada una con un párrafo debajo. Reciben `{{resumen:ARQUITECTURA}}`
y `{{resumen:INSTALACIONES}}`.

`[REQ]` Con las palabras del cliente, ahí va *«un resumen más extenso de la
información que salga de la Memoria Técnica»*. Eso es el **descriptivo** de cada
objeto del bloque, y las cifras van detrás, de cierre:

```
· Cimentación: Cimentación por zapatas aisladas de hormigón armado — Según memoria…
· Estructura: Estructura de pórticos prefabricados de hormigón (42 ud) — Luz de 24 m…
· Cubierta: Cubierta deck con lámina impermeabilizante de PVC (16400 ud) — Instalada…
· Fachadas: Fachada de panel prefabricado de hormigón con acabado liso (3800 ud) — …

4 deficiencias detectadas: 1 de riesgo extremo, 1 de riesgo alto y 2 de riesgo moderado.
CAPEX estimado: 113.757,50 € (87.707,50 € a corto plazo y 26.050,00 € a medio plazo).
```

**El descriptivo y no la valoración**, y la diferencia importa: el esquema define
el descriptivo como «dato leído de un documento» —la memoria técnica— y la
valoración como algo que «no lo dice ningún documento: la escribe quien ha ido a
verlo». Si además se quiere el estado, se añade `{{valoracion:ARQUITECTURA}}` en
esa misma diapositiva.

Las cifras cuadran con la sección 07: ese total es el mismo que el de su tabla de
detalle y el de su matriz de riesgo, porque sale de los mismos datos.

`[REQ]` En las cifras van **los hechos** y no un juicio. Nada de «el edificio está
en buen estado», que es una opinión y la firma una persona. Todo se edita en
PowerPoint como cualquier otro texto, que es para lo que se exporta.

Un bloque **sin nada** no emite el marcador, así que la diapositiva sale en
blanco. Imprimir «0 deficiencias detectadas» afirmaría algo que nadie ha
comprobado: puede ser que esa parte no se revisara.

### Un bloque de obra vale como ámbito

`ARQUITECTURA` e `INSTALACIONES` funcionan como un código más del árbol, y valen
para **los cinco marcadores de sección**:

```
{{resumen:ARQUITECTURA}}       las cifras del bloque
{{valoracion:INSTALACIONES}}   las valoraciones de sus capítulos, seguidas
{{capex:ARQUITECTURA}}         solo el importe
{{hallazgos:INSTALACIONES}}    sus títulos, uno por línea
```

El bloque sale del **código del capítulo**, igual que el capítulo sale del
código del objeto: `HC.H02.01` → `HC.H02` → `HC` → `ARQUITECTURA`. Es la misma
división que el informe hace en su sección 04 y en las dos tablas de detalle de
la 07, así que está escrita una vez. Lo que no es obra —costes blandos,
licencias— no pertenece a ningún bloque: su sitio es el resumen de presupuesto.

### La introducción del proyecto

`[REQ]` §3.1 · `{{project.summary}}` es la introducción que redacta el gestor en
la ficha del proyecto: qué se compra, para qué y con qué alcance. El esquema
decía de ella «sale tal cual en el informe» y **no salía**: no estaba en el
snapshot ni tenía marcador, así que alguien la escribía y se perdía.

`[PDV]` Ya está disponible, pero **no se coloca sola**: la plantilla del cliente
no tiene un hueco declarado para ella. Dónde la quiere —abriendo el resumen
ejecutivo, en la descripción del inmueble— es decisión suya, y se escribe el
marcador en esa diapositiva.

### La documentación consultada y el análisis de licencias

Salen de la **checklist documental**, que la aplicación ya tenía y el informe no
usaba: el snapshot solo llevaba el negativo —las limitaciones, lo que no se pudo
revisar— y faltaba el positivo.

| Marcador | Qué escribe |
|---|---|
| `{{docs.consultados}}` | Lo aportado, con el código de su nodo. Lo parcial se marca como tal |
| `{{docs.consultados_count}}` | Cuántos |
| `{{docs.licencias}}` | El estado de la rama `S1`, agrupado por estado |

`{{docs.licencias}}` sale así:

```
Aportadas:
· Licencia de Obras de nueva planta y modificaciones
· Licencia de Primera Ocupación
No disponibles:
· Licencia de Funcionamiento — El ayuntamiento no la emitió en su día…
Pendientes de recibir:
· Licencia de Actividad
```

Una línea por documento y no una frase con puntos y coma: el motivo de una no
disponible es un párrafo entero, y encadenado dentro de una frase deja la
enumeración ilegible.

`[REQ]` **«Consultado» es lo aportado, entero o en parte.** Una casilla en
«solicitada» no se ha consultado —se pidió y no llegó—, y decir lo contrario en
un entregable firmado es exactamente lo que no puede pasar. «No aplica» tampoco
sale: no es ni una ausencia ni un hallazgo.

#### Cuál manda cuando hay dos filas del mismo documento

`[REQ]` §3.2 b · `doc_request_item` alberga **dos cosas**: la casilla del árbol
de un activo, única por nodo, y la checklist libre del proyecto, donde dos
informes previos distintos son dos líneas legítimas. Las dos pueden hablar del
mismo nodo y **decir cosas distintas**.

Pasa en cuanto un documento llega: se pidió al inicio y quedó anotado como no
disponible; después apareció y alguien marcó la casilla del árbol —que es la
pantalla que se usa— y la línea de la petición se quedó como estaba. El informe
salía diciendo que la Licencia de Primera Ocupación estaba **aportada y no
disponible a la vez**.

**Manda el árbol del activo**, porque es el estado del nodo para ese edificio y
es lo que la aplicación mantiene al día. Las líneas libres de un nodo sin casilla
en ningún activo se quedan: ahí siguen siendo la única fuente.

`[LIM]` Con **varios edificios**, cada línea dice de cuál es, entre corchetes.
Sin eso, dos edificios con la misma licencia en estados distintos volverían a
producir dos líneas que se contradicen.

#### Dónde se declara el hueco de las licencias

Esa diapositiva **no tiene título propio**: es un párrafo de relleno y nada más,
y «ANÁLISIS DE LICENCIAS» vive en el **patrón**. Por eso `marcar_plantilla.py`
lo busca también ahí (`CAMPOS_POR_PATRON`), y solo lo aplica a una diapositiva en
la que no haya caído ningún otro marcador: un patrón lo comparten muchas páginas
—el de arquitectura, hasta dieciocho— y esto tiene que alcanzar a la que va
suelta, no a todas.

`[LIM]` **Cada plantilla lo escribe a su manera, y aquí una letra cuesta una
sección**: el Modelo A inglés pone `LICENSE ANALYSIS` y el B inglés
`LICENSES ANALYSIS`, en plural. Lo mismo con la dirección del inmueble, que las
dos inglesas titulan `PLOT LOCATION` y no `LOCATION`. Estas variantes no se
adivinan: salen de abrir las cuatro plantillas y contar los marcadores del
informe generado con cada una.

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

# El rediseño tras el primer prototipo

`[REQ]` Lo que el cliente pidió cambiar después de recorrer el prototipo
navegable, punto por punto, con lo que ya está hecho, lo que queda y lo que
todavía no se puede construir porque falta definirlo.

No es una lista de deseos: **cambia la arquitectura de información**. La
aplicación pasa de nueve pestañas planas colgando del proyecto a cuatro, con el
**activo** como sitio donde ocurre todo. Es el cambio de fondo de esta revisión
y conviene leerlo entero antes de tocar nada.

> **Vocabulario.** El cliente ha decidido que se diga **proyecto** y no
> «encargo» en toda la aplicación. Ya está aplicado a todo el texto que ve el
> usuario. `[LIM]` Quedan identificadores internos —`EstadoDelEncargo`, la
> columna `context_project_id`, algún parámetro de la API— que siguen diciendo
> encargo: renombrarlos es una migración con su riesgo y ninguno se ve desde la
> pantalla. Ver §5.
>
> `[LIM]` Los documentos `docs/01` a `docs/22` **conservan la palabra
> «encargo»**: son el registro de decisiones tomadas cuando ese era el término,
> y reescribirlos haría que las citas del cliente dejaran de coincidir con lo
> que dijo. Del `README` en adelante —lo que alguien lee para entender el
> producto hoy— sí está cambiado.

---

## 1. Pantalla inicial de proyectos ✅ hecho

| Qué | Estado |
|---|---|
| Columnas **Código · Proyecto · Cliente · Arranque · Cierre · Estado**, en ese orden | ✅ |
| El botón pasa a llamarse **«Nuevo proyecto»** | ✅ |
| El código se **genera solo**, único por organización | ✅ |
| La columna «Moneda» desaparece | ✅ |

`AAAA-NNN`, por organización y año, calculado sobre los códigos que ya existen y
no sobre un contador aparte: un contador se desincroniza en cuanto alguien borra
un proyecto o importa una tanda con códigos propios. Cuenta **solo los de tres
cifras**, que son los que genera él mismo; un código traído de otro sistema
—`2026-123456`— dispararía la serie y dejaría los siguientes ilegibles.

`[LIM]` Dos altas simultáneas pueden calcular el mismo número: lo impide el
`UNIQUE (organization_id, internal_code)` y la API reintenta con el siguiente.
Es más simple que un bloqueo y falla del lado seguro.

## 2. Pantalla «Nuevo proyecto» ✅ hecho

| Qué | Estado |
|---|---|
| Filas alineadas **por arriba** | ✅ `align-items: start` |
| Código interno **bloqueado**, con el aviso de que es único e inalterable | ✅ |
| «Nombre del encargo» → **«Nombre del proyecto»** | ✅ |
| Cliente **de una lista** que mantiene la administración | ✅ |
| Un cliente que no está **no bloquea**: avisa al administrador | ✅ |
| **Fecha de arranque** y **fecha de cierre** | ✅ |
| «Nombre de cliente nuevo» y «Moneda» fuera | ✅ |
| Fases aplicables, igual | ✅ sin tocar |

Estaban alineadas por abajo, y por eso un campo con texto de ayuda empujaba a
sus vecinos: las etiquetas de una misma fila quedaban a tres alturas distintas.

**El aviso al administrador no es un mecanismo nuevo.** El cliente escrito a
mano nace `pending_validation` y se crea una sugerencia de tipo `CATALOGO` en el
buzón que ya existe y que **solo ven los administradores, por RLS**. Un correo
se archiva; una tabla nueva es otro sitio donde mirar, y nadie mira dos. Que el
cliente está sin validar se ve además **en la lista y en la cabecera**: si no,
el aviso se queda en el buzón y en la lista parece un cliente como los demás.

`[PDV]` **Quién puede añadir clientes al catálogo según su rol** queda por
definir, como dijo el cliente. Hoy cualquiera puede escribir uno y queda
pendiente de validación; nadie lo valida todavía desde la pantalla —falta el
panel de administración de clientes—.

`[LIM]` Los tres campos de fecha usan `<input type="date">`, que **se pinta en el
formato del navegador**, no en el de la aplicación: en un navegador en inglés
aparece `mm/dd/yyyy`. Cambiarlo exige un selector de fecha propio, que es una
pieza con su propia accesibilidad y su propio teclado. No parece que compense.

## 3. Pantalla de proyecto · la reestructuración

Lo hecho hasta ahora es **la cabecera y el nombre de la primera pestaña**. Lo
demás es el trabajo grande y está descrito aquí para que se pueda empezar sin
volver a preguntar.

| Qué | Estado |
|---|---|
| La cabecera añade el **nombre del cliente** | ✅ |
| «Fases» pasa a llamarse **«Resumen»** | ✅ solo el nombre |
| Las cuatro pestañas: Resumen · Activos · Dashboard · Informes | 🟡 |

🟡 **Dashboard ya es una pestaña** (§3.3). Las otras tres siguen conviviendo con
las seis que quedan —Documentación, Fotografías, Mapa, Inventario, Hallazgos y
CAPEX, Riesgos—, porque reducirlas a cuatro es mover esas seis **dentro del
activo**, que es §3.2 y el trabajo grande. Añadir la pestaña ahora y recolocarla
después no cuesta nada; hacerlo al revés habría dejado el dashboard escondido
hasta el final.

### 3.1. Resumen ⬜

Hoy es la lista de fases con su estado. Tiene que pasar a ser **el resumen del
proyecto**: las fases de la due diligence y en qué punto está cada una.
`[PDV]` Qué más lleva —cifras del proyecto, avisos, próximos hitos— está sin
definir.

### 3.2. Activos ⬜ · el cambio de fondo

**Todo pasa a ocurrir dentro del activo.** Hoy documentación, fotografías,
inventario y CAPEX son pestañas del proyecto y se filtran por activo; pasan a
ser secciones **de cada activo**. Cinco:

| Sección | Qué lleva | Estado |
|---|---|---|
| **a) Detalle** | La ficha que ya existe | ✅ existe, se mueve |
| **b) Documentación** | La del activo | `[PDV]` **estructura por revisar** |
| **c) Visita** | Fecha de la visita y sus fotografías | `[PDV]` **por definir** |
| **d) Inventario** | Vuelca la memoria técnica si la hay; casilla de **«pasa a CAPEX»** por equipo o sistema; **vincular fotos** de la visita a cada equipo | ⬜ |
| **e) CAPEX** | Árbol Tipo de coste → Categoría → Objeto, y la ficha del objeto | ⬜ |

**La ficha de cada objeto del CAPEX** lleva: descripción, zona afectada, riesgo,
comentarios del gestor técnico, CAPEX estimado por plazo —corto, medio, largo,
mejoras, otro— con su total, el concepto según la clasificación, y si es
repercutible a inquilinos.

> `[REQ]` **Todos esos campos existen ya** en `finding` y `capex_item`, incluida
> la columna de repercutible (`tenant_recoverable`) y los cinco plazos. Lo que
> cambia **no es el modelo, es la presentación**: hoy es una rejilla plana por
> proyecto y pasa a ser un árbol por activo. Eso abarata mucho este punto.

`[REQ]` **El árbol de categorías ya está cambiado** ✅. El cliente mandó su hoja
y el catálogo se ha regenerado desde ella: **6 tipos de coste · 28 categorías ·
141 objetos = 175 nodos**, con **sus** códigos. El listado completo está en
[`05`](./05-catalogos-y-taxonomias.md) §5.3, que es de donde se generan los CSV
de siembra —no al revés—, y la migración `0020` renombra los códigos viejos.

Costó menos de lo presupuestado, y por un motivo concreto: **no hubo que
remapear ningún hallazgo**. Se renombra la fila en vez de crear una nueva, así
que conserva su `id` y todo lo que apuntaba a ella —`finding`, `photo`, las dos
tablas de memoria— sigue apuntando a lo mismo. Se dan por buenas las 28
categorías que trae la hoja frente a las 23 que se anunciaron por teléfono: cada
tipo de coste acaba con una categoría «Otros», y cada categoría con un objeto
«Otros», que es la salida que necesita un consultor cuando lo que ve no está en
la lista. En la hoja del cliente ese cajón se escribe `-`.

`[REQ]` **La plantilla de Excel ya tiene el tramo de `SC.S04 «Otros»`** ✅. No
lo tenía —su total de soft costs sumaba exactamente las otras tres categorías—,
el cliente confirmó que su plantilla puede cambiar y se le dieron las filas
256-266, justo detrás de `S03`. Operativos e Imprevistos bajan doce filas para
dejarle sitio: una cuarta categoría de soft costs al final de la hoja se leería
como una sección aparte.

`[REQ]` **Las dos erratas del árbol, corregidas** ✅. La hoja traía `Placas
fotovoltáicas` y `Bies`; el cliente pidió arreglarlas y se han arreglado **en los
dos lados a la vez** —catálogo con la migración `0021`, plantilla española con
`tools/corregir_erratas_plantillas.py`—, que es la única forma de que el
desplegable y la base de datos sigan diciendo lo mismo.

`[LIM]` Lo que queda abierto no bloquea nada: los tramos añadidos **no traen
desplegable en la columna «Categoría»**, igual que las diez filas de `S03` en la
plantilla original. No afecta a lo que exporta la aplicación, que escribe la
etiqueta; afecta a quien rellene esas filas a mano.

### 3.3. Dashboard ✅ hecho

El desglose económico del CAPEX, con **cinco cortes**, en su propia pestaña:

| Título en pantalla | Corte | Forma | Estado |
|---|---|---|---|
| Distribución por concepto de gasto | concepto | tarta | ✅ |
| Perfil temporal de la inversión | plazo | barras, en orden de plazo | ✅ |
| Exposición por grado de riesgo | riesgo | barras, en orden de gravedad | ✅ nuevo |
| Desglose por categoría y objeto | categoría y objeto | **barras apiladas**: cada categoría es una barra y dentro van sus objetos | ✅ nuevo |
| Distribución por activo | activo | barras | ✅ |

`[REQ]` **Los títulos van en el registro de una due diligence técnica**, a
petición del cliente: es el del informe que sale de aquí. La pregunta coloquial
que contesta cada corte —«en qué se va el dinero», «cuánto de esto es grave»—
sigue estando en el texto de ayuda de cada bloque, donde explica; el encabezado,
que es lo que se imprime y lo que ve el cliente del cliente, dice lo que dice un
informe.

Y el selector pasa de un activo a **uno, varios o toda la cartera** ✅. En la API
es el mismo parámetro repetido —`?asset_id=…&asset_id=…`—, escrito una sola vez
para los cuatro cortes filtrables: tenerlo en un sitio es lo que impide que uno
filtre por el activo de la línea y otro por el del hallazgo, que es el descuadre
que ya apareció una vez.

**Era la vista «Resumen» de Hallazgos y CAPEX y sube a pestaña propia.** En la
rejilla queda un enlace, no una copia: las dos se consultan una detrás de otra
—se mira el reparto, se ve que «Normativa» pesa demasiado y se va a la rejilla a
comprobar de qué hallazgos sale— y con dos copias del mismo gráfico una acabaría
quedándose atrás.

`[REQ]` **La decisión de color del apilado, tomada.** La paleta está medida para
cuatro tonos más «Otros», y una categoría del CAPEX puede traer dieciséis
objetos: no existe una paleta de dieciséis que pase las comprobaciones de
daltonismo. Así que en las apiladas **el color no identifica, separa**: una sola
familia de tono en cuatro claridades que se alternan, con dos píxeles de hueco
entre tramos. Lo que distingue dos tramos contiguos es la **luminosidad**, que
sobrevive a los tres tipos de daltonismo y a una impresión en blanco y negro.
Quién es cada tramo lo dicen su nombre escrito dentro cuando cabe, su título al
pasar por encima y la tabla de debajo, que los lista todos con su importe y su
parte. En un móvil el nombre de dentro se quita: en una barra de cuarenta
píxeles salía como «Cu…».

`[REQ]` **Los cinco cortes suman lo mismo**, y hay pruebas que lo imponen: en la
API se comparan entre sí con varios activos elegidos, `by-risk` se compara además
contra la matriz de riesgos —que calcula lo mismo por otro camino—, y
`herramientas/comprobar-dashboard.mjs` lo vuelve a comprobar **sobre la pantalla
ya pintada**, incluido que «Distribución por activo» siga enseñando la cartera entera con el
filtro puesto.

`[PDV]` El corte por riesgo y la matriz de riesgos enseñan ahora el mismo reparto
en dos pestañas. No se ha unificado: la matriz cruza riesgo × plazo y es otra
lectura. Conviene decidir con el cliente si la matriz se absorbe en el dashboard
o se queda aparte.

### 3.4. Informes ⬜

Se queda como está, pendiente de revisar. Sin cambios en esta tanda.

---

## 4. Lo que esto cuesta `[SUP]`

Con una persona a tiempo completo que ya conoce el código.

| Bloque | Esfuerzo |
|---|---|
| §1 y §2 · pantallas de entrada | ✅ hecho |
| ~~§3.3 · Dashboard completo~~ | ✅ hecho |
| §3.2 · el activo con sus cinco secciones | 10-12 días |
| ~~Resembrar el catálogo, con remapeo~~ | ✅ hecho · **1 día**, no los 3-4 estimados |
| §3.1 · Resumen del proyecto | 2-3 días **desde que se defina** |
| Documentación y visita del activo | por definir |

**≈ 4 semanas** para lo definido, sin contar lo que está `[PDV]`.

`[REC]` **Por este orden**: Dashboard primero —enseña resultado pronto y no
mueve nada de sitio—, el árbol del CAPEX después, y el activo entero al final,
que es lo que obliga a mover documentación, fotos e inventario de pestaña. El
Dashboard ✅ y el árbol del CAPEX ✅ ya están; queda el activo con sus cinco
secciones.

## 5. Lo que hace falta del cliente

- ~~El listado de los 6 tipos de coste y sus categorías~~ ✅ **recibido y
  sembrado**: 28 categorías y 141 objetos. Ya no bloquea nada.
- ~~Si su plantilla de Excel puede cambiar~~ ✅ **confirmado y aplicado**:
  `SC.S04 «Otros»` ya tiene su tramo. `[PDV]` Queda **abrir el fichero en Excel
  y comprobarlo**: aquí solo se puede verificar el XML.
- **Qué estructura sigue la documentación del activo** (§3.2 b).
- **Qué lleva la visita** además de fecha y fotos (§3.2 c).
- **Qué roles pueden añadir clientes al catálogo** (§2).
- Qué más enseña el Resumen del proyecto además de las fases (§3.1).

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
| Las cuatro pestañas: Resumen · Activos · Dashboard · Informes | ⬜ |

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

`[PDV]` **El árbol de categorías cambia.** El catálogo actual tiene 4 tipos de
coste y 18 capítulos. El cliente ha precisado que son **6 tipos de coste** —Hard
Cost, Soft Cost, Operativos, Medioambiente, ESG Energía e Imprevistos— con
**15 categorías en Hard Cost, 3 en Soft Cost, 2 en Operativos, 1 en
Medioambiente, 1 en ESG Energía y 1 en Imprevistos**: 23 en total. **Falta el
listado completo**, que el cliente ha ofrecido. Sin él no se puede resembrar el
catálogo, y con él hace falta además **remapear los hallazgos existentes**: los
códigos viejos no desaparecen solos.

### 3.3. Dashboard ⬜

El desglose económico del CAPEX, con **cinco cortes**:

| Corte | Forma | Estado |
|---|---|---|
| Por **concepto** | tarta | ✅ existe |
| Por **plazo** | barras | ✅ existe |
| Por **categoría y objeto** | **barras apiladas**: cada categoría es una barra y dentro van sus objetos | ⬜ |
| Por **riesgo** | ⬜ | la matriz de riesgos ya tiene el dato |
| Por **activo** acumulado | barras | ✅ existe |

Y el selector pasa de **un activo** a **uno, varios o toda la cartera**.

> `[REC]` Esta pestaña es la actual vista «Resumen» de Hallazgos y CAPEX,
> ascendida a pestaña propia. Los cuatro gráficos que ya existen se mueven tal
> cual; lo nuevo es el corte por riesgo, el apilado por categoría y la selección
> múltiple. Es el punto con mejor relación entre lo que se ve y lo que cuesta.

`[REC]` El apilado por categoría **necesita una decisión de color**: la paleta
está medida para **cuatro tonos más «Otros»** y una barra apilada con quince
objetos dentro no se puede colorear de quince maneras distinguibles. Lo honesto
es apilar con una sola familia de tono y separar por hueco, o enseñar el detalle
de objetos al desplegar la categoría en vez de dentro de la barra.

### 3.4. Informes ⬜

Se queda como está, pendiente de revisar. Sin cambios en esta tanda.

---

## 4. Lo que esto cuesta `[SUP]`

Con una persona a tiempo completo que ya conoce el código.

| Bloque | Esfuerzo |
|---|---|
| §1 y §2 · pantallas de entrada | ✅ hecho |
| §3.3 · Dashboard completo | 5-6 días |
| §3.2 · el activo con sus cinco secciones | 10-12 días |
| Resembrar el catálogo a 6 tipos y 23 categorías, con remapeo | 3-4 días **desde que llegue el listado** |
| §3.1 · Resumen del proyecto | 2-3 días **desde que se defina** |
| Documentación y visita del activo | por definir |

**≈ 4 semanas** para lo definido, sin contar lo que está `[PDV]`.

`[REC]` **Por este orden**: Dashboard primero —enseña resultado pronto y no
mueve nada de sitio—, el árbol del CAPEX después, y el activo entero al final,
que es lo que obliga a mover documentación, fotos e inventario de pestaña.

## 5. Lo que hace falta del cliente

- **El listado de los 6 tipos de coste y sus 23 categorías**, con sus objetos si
  los hay. Bloquea el árbol del CAPEX y el corte por categoría del Dashboard.
- **Qué estructura sigue la documentación del activo** (§3.2 b).
- **Qué lleva la visita** además de fecha y fotos (§3.2 c).
- **Qué roles pueden añadir clientes al catálogo** (§2).
- Qué más enseña el Resumen del proyecto además de las fases (§3.1).

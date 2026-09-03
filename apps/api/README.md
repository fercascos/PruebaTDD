# Backend · API de due diligence técnica

Backend del MVP (entregable 24). Los **cuatro bloques funcionales están
construidos** y se han recorrido de punta a punta contra la API en marcha. Lo
que hay está implementado y probado; lo que falta está listado abajo sin
adornos.

## Arrancar en local

```bash
make install     # dependencias
make db-up       # PostgreSQL 16
make db-init     # crea las bases, MIGRA el esquema y siembra catálogos y fases
make test        # 1.264 pruebas
```

Sobre una base recién creada **no hay ninguna cuenta**, y `POST /users` exige un
administrador ya autenticado: es el problema del huevo y la gallina. La primera
se crea desde fuera de la API, con acceso a la base de datos:

```bash
TDD_BOOTSTRAP_PASSWORD='…' make db-admin \
  ORG="Consultora Ejemplo" EMAIL="admin@ejemplo.example" NOMBRE="Nombre Apellido"

make run         # http://localhost:8000/docs
```

La contraseña **no se pasa por argumento**: se lee de `TDD_BOOTSTRAP_PASSWORD` o
se pide por consola. Un argumento acaba en el historial del intérprete y en la
lista de procesos, donde lo lee cualquiera. Si no hay ninguna de las dos, la
orden se niega a seguir en vez de inventarse una por omisión, que es como nacen
los despliegues con `admin/admin`.

Dos detalles del `Makefile` que no son cosméticos:

* **`make run` arranca como `tdd_app`**, no como el superusuario que crea el
  esquema. PostgreSQL no aplica la RLS a un superusuario: arrancar la API con la
  conexión de administración dejaría las políticas sin efecto y **todo parecería
  funcionar igual**, que es la peor forma de que falle.
* **La suite corre sobre otra base** (`tdd_test`). Su `conftest` hace un
  `DROP SCHEMA public CASCADE` en cada arranque: compartiendo base, bastaba un
  `make test` para perder los datos de desarrollo —el administrador incluido— y
  volver a una aplicación en la que no se puede entrar.

## Qué hay construido y verificado

| Pieza | Estado | Dónde se comprueba |
|---|---|---|
| **Motor de CAPEX** con la cascada de P-16 | ✅ Completo | `tests/unit/test_capex_engine.py` · 17 |
| **Motor de fases** · estados derivados y sugeridos | ✅ Completo | `tests/unit/test_fases.py` · 33 |
| **Máquina de estados del proyecto** con sus guardas | ✅ Completo | `tests/unit/test_maquina_de_estados.py` · 18 |
| **Esquema con RLS**, triggers y `CHECK` | ✅ Completo | `tests/integration/test_rls_y_restricciones.py` · 21 |
| **Semilla de catálogos** desde el documento de diseño | ✅ Completo | `tests/integration/test_catalogos.py` · 32 |
| **Ciclo de vida de sugerencias** | ✅ Completo | `tests/unit/test_sugerencias.py` · 19 |
| **Fases y proyectos** punta a punta | ✅ Completo | `tests/integration/test_fases_y_proyectos.py` · 23 |
| **API**: catálogos, proyectos, fases, CAPEX y sugerencias | ✅ Parcial | `tests/integration/test_api.py` · 27 |
| **Primera cuenta** · arranque sin API | ✅ Completo | `tests/integration/test_arranque.py` · 7 |
| **Migraciones** · el esquema versionado | ✅ Completo | `tests/integration/test_migraciones.py` · 8 |
| **Mapa de fotografías** `[REQ]` §15.9 | ✅ Completo | `tests/integration/test_mapa.py` · 10 |
| **Matriz de riesgo × horizonte** `[REQ]` §12 | ✅ Completo | `test_riesgos.py` · 15 + `test_matriz_de_riesgos.py` · 14 |
| **Comparador de precios** `[REQ]` §14 | ✅ Completo | `test_precios.py` · 23 + `test_precios_y_fuentes.py` · 19 |
| **Directorio** · clientes y personas | ✅ Completo | `tests/integration/test_directorio.py` · 16 |
| **Exportación del CAPEX a XLSX** `[REQ]` P-31 | ✅ Completo | `tests/integration/test_exportacion_capex.py` · 8 |
| **Errores de usuario** · 409 y 422 donde había 500 | ✅ Completo | `tests/integration/test_errores_de_usuario.py` · 6 |
| **Tabla de CAPEX** · diseño único para PPTX y XLSX | ✅ Completo | `tests/unit/test_capex_layout.py` · 25 |
| **Fuentes y desbordamiento** con métricas reales | ✅ Completo | `tests/unit/test_fuentes_y_desbordamiento.py` · 14 |
| **Retirada de la marca de agua** `[REQ]` P-43 | ✅ Completo | `tests/unit/test_marca_de_agua.py` · 10 |
| **Nombres de fotografía** · 13 tokens y 8 reglas | ✅ Completo | `tests/unit/test_nombres_de_foto.py` · 33 |
| **Lectura de imágenes** · EXIF, GPS, HEIC, derivados | ✅ Completo | `tests/unit/test_imagenes.py` · 24 |
| **Reglas de evidencia** · duplicados, papelera, avisos | ✅ Completo | `tests/unit/test_evidencia.py` · 37 |
| **Fotografías punta a punta** · los tres orígenes | ✅ Completo | `tests/integration/test_fotografias.py` · 39 |
| **Fotografías avanzado** · versiones, ZIP y purga | ✅ Completo | `tests/integration/test_fotografias_avanzado.py` · 23 |
| **Anotaciones** `[REQ]` §15.2 · capa vectorial y rasterizado | ✅ Completo | `tests/unit/test_anotaciones.py` · 23 |
| **Autenticación** · login, rotación y bloqueo | ✅ Completo | `test_identidad.py` · 20 + `test_autenticacion.py` · 23 |
| **Activos y equipo del proyecto** | ✅ Completo | `tests/integration/test_activos_y_equipo.py` · 27 |
| **Hallazgos y CAPEX** · P-44 y el traslado explícito de P-05b | ✅ Completo | `test_hallazgos.py` · 12 + `test_hallazgos_y_capex.py` · 28 |
| **Trabajo de las fases** · checklist, VDR, visitas, Q&A | ✅ Completo | `tests/integration/test_trabajo_de_fases.py` · 30 |
| **Documentos** (§15.11) | ✅ Completo | `tests/integration/test_documentos.py` · 28 |
| **Informes PPTX** · snapshot, avisos, emisión | ✅ Completo | `test_avisos_de_informe.py` · 22 + `test_informes.py` · 28 |
| **Memoria técnica** · lectura determinista del PDF | ✅ Completo | `test_extraccion_de_memoria.py` · 16 + `test_memoria_tecnica.py` · 12 |
| **Esqueleto del CAPEX** desde la memoria | ✅ Completo | `tests/integration/test_memoria_y_esqueleto.py` · 14 |
| **Extracción por tipo de documento** · propuesta con procedencia | ⚠️ Dos lectores | `tests/integration/test_extraccion_por_documento.py` · 12 |
| **Limitaciones que aporta la documentación** · la tercera clase | ✅ Completo | `test_limitaciones_del_plan.py` · 19 + `test_limitaciones_documentales.py` · 16 |
| **Medios del plan al inventario** · capítulo 4 de la Norma Básica | ✅ Completo | `test_medios_del_plan.py` · 14 + `test_equipos_y_confidencialidad.py` · 15 |
| **Mantenimiento preventivo** · periodicidad y próxima revisión | ✅ Completo | `tests/integration/test_equipos_y_confidencialidad.py` |
| **Confidencialidad por tipo** · un RESTRINGIDO no va a ninguna IA | ✅ Completo | `tests/integration/test_equipos_y_confidencialidad.py` |
| **Resumen del CAPEX** · los cuatro cortes, y que cuadren entre sí | ✅ Completo | `tests/integration/test_resumen_capex.py` · 8 |

## El esquema se versiona con Alembic

```bash
make db-migrate                        # alembic upgrade head
make db-version                        # qué versión tiene la base
make db-sql                            # el SQL pendiente, SIN ejecutarlo
make db-revision M="añade la columna X"  # una migración nueva, vacía
```

Tres decisiones que se notan:

**La migración inicial ejecuta `schema.sql` tal cual**, no lo reescribe en
llamadas de Alembic. El esquema tiene 6 políticas RLS explícitas más las que
crean dos bucles `DO $$`, 9 triggers, 14 funciones, 4 columnas generadas y 57
`CHECK`, y **Alembic no sabe expresar la mayor parte**: acabarían todas en
`op.execute()` con el mismo SQL. Un esquema «migrado» al que le faltaran las
políticas arrancaría sin un solo error y dejaría los datos de cada organización
visibles para las demás.

**`schema.sql` sigue siendo la verdad, y hay una prueba que lo impone.**
`test_migraciones.py` crea dos bases —una migrando, otra con `schema.sql`— y
compara tablas, columnas, políticas, `FORCE ROW LEVEL SECURITY`, triggers,
restricciones, índices, funciones y enumerados. Si alguien escribe una
migración y no actualiza `schema.sql`, la suite lo dice y señala en qué aspecto.
Se comprobó añadiendo una migración que cambia una columna a espaldas del
fichero: la prueba falla, como debe.

**No hay `--autogenerate` ni `target_metadata`.** No existe capa de modelos
declarativos de la que generar, y un autogenerado que ignora en silencio
políticas y triggers produciría migraciones que parecen correctas y dejan la
base sin protección. Las migraciones se escriben a mano, en SQL.

`[REQ]` La conexión sale del entorno (`DATABASE_MIGRATION_URL`), **nunca del
`alembic.ini`**: una cadena con contraseña en un fichero versionado es una
credencial en el repositorio. Hay una prueba que lee el `.ini` y falla si
aparece una. Y se migra con la conexión de **administración**, no con
`tdd_app`: si el usuario de la aplicación pudiera alterar el esquema, la RLS
que lo protege sería decorativa.

`[LIM]` El `downgrade` del esquema inicial **se niega**. Deshacerlo es borrar la
base entera: automatizarlo convertiría un error de tecleo en una pérdida total.

## El comparador de precios no consulta nada

`[REQ]` §14. Y es la parte que más se nota en el código, porque las reglas las
fijó el cliente por escrito:

* **«No inventes APIs ni fuentes de precios.»** No hay ni un cliente HTTP de
  precios en el proyecto. Una prueba lee el fichero del servicio y **falla si
  aparece `requests`, `httpx`, `urllib` o `socket`**: es lo único que garantiza
  que nadie añada una llamada de aquí a seis meses sin enterarse. Otra revisa el
  OpenAPI en busca de rutas que sugieran consulta remota.
* **«Nunca selecciones automáticamente un precio como definitivo.»** No existe
  ninguna función que elija. Lo que hay rechaza validar sin las condiciones
  puestas, y la base de datos lo respalda: su `CHECK` exige revisor, fecha y
  nota de al menos diez caracteres para que una fila llegue a `VALIDADO`.
* **P-06 · No hay ninguna fuente externa habilitada.** Una fuente nace siempre
  deshabilitada, y habilitarla exige declarar que se han revisado sus
  condiciones de uso; queda con nombre y fecha. También lo impide un `CHECK`,
  así que ni saltándose la API se consigue.

Lo que se enseña **no es una lista de resultados**: es la lista de lo que hay
más **las fuentes que no se han consultado, con su motivo**. Una lista sin esa
columna sugiere que se ha buscado en todas partes. Y las referencias salen por
fecha, no por importe: ordenarlas por precio insinuaría preferencia por el más
barato, que es justo lo que no se puede insinuar.

`[LIM]` **No hay catálogo de índices.** La actualización por índice es una
calculadora en la que el usuario introduce los dos valores; publicar una cifra
del INE que nadie ha verificado sería exactamente inventar una fuente de
precios. Devuelve la fórmula con sus operandos y no aplica nada.

## Los dos ejes del proyecto

Es la decisión que más se nota al usar la aplicación, y está construida así:

| | **Estado** del encargo | **Fases** del proceso |
|---|---|---|
| Qué describe | El ciclo administrativo | El trabajo real |
| Valores | Borrador → … → Archivado | Ocho, elegidas a la carta al dar de alta |
| Cómo avanza | Una a una, con guardas | **En paralelo** |
| Dónde está | `projects/state_machine.py` | `phases/engine.py` |

Un encargo puede tener la documentación pendiente, la visita hecha y el Q&A en
curso **a la vez**. Mezclar ambos ejes en un solo campo habría sido el error de
modelado más caro del proyecto.

**Dos fases no se marcan a mano.** Red Flag/CAPEX y Full Report se calculan del
trabajo que hay debajo: 63 líneas con 12 precios sin validar dan `EN_CURSO`, y no
hay forma de marcarlas `COMPLETADA` desde la API (`422`). Una lista de
verificación que se puede marcar cuando el trabajo no está hecho es peor que no
tenerla.

**Las guardas explican qué falta.** `GET /projects/{id}/transitions` devuelve
cada destino con su lista de impedimentos —«queda 1 activo por visitar (2 de 3
realizadas)»— para que la interfaz muestre el botón **deshabilitado con su
motivo** en vez de ocultarlo.

## Las cuatro garantías, y dónde viven

Ninguna de estas cuatro depende de que un servicio recuerde comprobarlas. Si
mañana alguien escribe una consulta nueva y se despista, siguen en pie.

| Garantía | Mecanismo | Prueba |
|---|---|---|
| Una organización no ve datos de otra | **RLS** con `USING` y `WITH CHECK` | `test_una_organizacion_no_ve_los_proyectos_de_otra` |
| **Solo el administrador ve las propuestas** `[REQ]` | **RLS** sobre `suggestion` | `test_un_consultor_no_ve_las_de_sus_companeros` |
| El original nunca se sobrescribe | Trigger en `stored_object` | `test_un_original_no_se_sobrescribe` |
| Un precio validado tiene persona y nota | `CHECK` en `capex_item` | `test_un_precio_validado_exige_persona_y_nota` |

**El usuario de aplicación no tiene `BYPASSRLS` ni es propietario de las tablas**
—si lo fuera, las políticas no se le aplicarían y todo lo anterior sería
decorativo—. Hay una prueba que lo verifica: `test_el_usuario_de_aplicacion_no_
puede_saltarse_la_rls`.

## Los catálogos salen del documento de diseño

`tools/generar_catalogos.py` lee `docs/05-catalogos-y-taxonomias.md` y produce
los CSV de `data/catalogos/`. `make catalogs-check` falla si se han desfasado.

No es un capricho: son 86 relaciones zona × tipología y 125 códigos que el
cliente revisa en el documento. Mantener dos copias a mano garantiza que
divergirán, y una zona mal sembrada obliga a migrar datos reales meses después.

```
6 tipologías · 20 zonas · 86 relaciones
árbol CAPEX: 4 categorías + 18 capítulos + 103 elementos = 125 nodos
4 grados de riesgo (con su definición íntegra) · 10 conceptos · 5 horizontes
```

## Lo que NO está construido todavía

Se dice aquí, y no enterrado en una nota, porque condiciona expectativas:

- **Todo lo que depende de infraestructura externa.** El antivirus (ClamAV) no
  está integrado: **ninguna foto pasa hoy por `CUARENTENA`**, el estado existe
  y la máquina de estados lo contempla, pero nada lo activa. El almacén S3 con
  Object Lock tampoco: solo hay adaptador sobre disco y otro en memoria, así
  que la **barrera 4** (WORM) no se ha probado contra ningún bucket. Faltan
  también las URLs firmadas y el worker asíncrono; el ZIP en lote se construye
  hoy en la propia petición, que §15.7 pide mover al worker.
- **Recuperación de contraseña por correo.** Hay login, refresco con rotación,
  cierre de sesión y cambio de contraseña; falta el flujo de «he olvidado mi
  contraseña», que necesita SMTP.
- **Inventario de equipos** desde la API.
- **Los objetos del CAPEX no se extraen de la memoria.** Los datos del edificio
  sí, con reglas y sin red. Los objetos no: la memoria los enumera en prosa
  dentro de sus secciones constructivas, y una sola —`MC.6 Instalaciones`—
  reparte los suyos entre seis capítulos. Eso es clasificación semántica y
  **falta elegir proveedor**; el adaptador que hay hoy (`PorSeccion`) declara
  `es_simulado` y sirve para demostrar que el puerto encaja, no para sembrar un
  CAPEX. Y **solo hay dos lectores** —memoria técnica y plan de
  autoprotección—: los demás tipos responden `422` diciendo que aún no se leen.
- **Las periodicidades de mantenimiento no se deducen de ningún documento.** La
  columna existe y la rellena una persona. Un plan de autoprotección declara
  revisiones «trimestrales, semestrales, anuales y quinquenales según el tipo de
  equipo» **sin decir cuál le toca a cuál**, y repartirlas por analogía sería
  inventarse el plan de mantenimiento del edificio. `[PDV]` El RIPCI (RD
  513/2017) fija una tabla por tipo de equipo que podría sembrarlas: exigiría
  transcribir una norma que nadie de este proyecto ha validado.
- **Los dos extractores están escritos contra UN documento cada uno**, y el del
  plan contra un *resumen* de uno. Que leen ésos está medido; que generalicen,
  no. Hace falta un segundo ejemplar de cada tipo para poder afirmarlo.
- **Frontend:** lo construido y lo que falta, en
  [`apps/web/README.md`](../web/README.md).

## Decisiones que se notan al leer el código

**El dominio está en español.** Nombres de función, excepciones y mensajes de
error. La documentación que revisa el cliente está en español y el vocabulario
del negocio también: `TransicionInvalida` y `RespuestaObligatoria` se entienden
sin traducir. Las tablas y columnas van en inglés, por convención de SQL.

**El motor de CAPEX es una función pura.** No toca base de datos, ni red, ni
reloj. Por eso sus 17 pruebas corren en 60 milisegundos y comprueban importes al
céntimo.

**Las guardas están dos veces.** El ciclo de vida de una sugerencia se valida en
Python —para devolver un `422` legible— y como `CHECK` en la base de datos —para
que nadie pueda saltárselo por otra vía—. No es duplicación: son dos capas con
propósitos distintos.

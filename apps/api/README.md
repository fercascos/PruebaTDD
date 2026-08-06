# Backend · API de due diligence técnica

Backend del MVP (entregable 24). Los **cuatro bloques funcionales están
construidos** y se han recorrido de punta a punta contra la API en marcha. Lo
que hay está implementado y probado; lo que falta está listado abajo sin
adornos.

## Arrancar en local

```bash
make install     # dependencias
make db-up       # PostgreSQL 16
make db-init     # crea las bases, aplica el esquema, siembra catálogos y fases
make test        # 651 pruebas
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
| **Fotografías avanzado** · versiones, ZIP y purga | ✅ Completo | `tests/integration/test_fotografias_avanzado.py` · 21 |
| **Autenticación** · login, rotación y bloqueo | ✅ Completo | `test_identidad.py` · 20 + `test_autenticacion.py` · 23 |
| **Activos y equipo del proyecto** | ✅ Completo | `tests/integration/test_activos_y_equipo.py` · 27 |
| **Hallazgos y CAPEX** · P-44 por ambos lados | ✅ Completo | `test_hallazgos.py` · 12 + `test_hallazgos_y_capex.py` · 23 |
| **Trabajo de las fases** · checklist, VDR, visitas, Q&A | ✅ Completo | `tests/integration/test_trabajo_de_fases.py` · 30 |
| **Documentos** (§15.11) | ✅ Completo | `tests/integration/test_documentos.py` · 28 |
| **Informes PPTX** · snapshot, avisos, emisión | ✅ Completo | `test_avisos_de_informe.py` · 22 + `test_informes.py` · 28 |

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
- **Alembic.** El esquema se aplica desde `schema.sql`. La migración inicial se
  genera cuando el modelo deje de moverse: versionar migraciones de un esquema
  que cambia cada día produce un historial inútil.
- **Inventario de equipos, comparador de precios y administración de usuarios**
  desde la API.
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

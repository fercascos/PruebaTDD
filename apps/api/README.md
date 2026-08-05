# Backend · API de due diligence técnica

Código inicial del MVP (entregable 24). **Es un punto de partida, no el MVP
completo**: lo que hay está implementado y probado; lo que falta está listado
abajo sin adornos.

## Arrancar en local

```bash
make install     # dependencias
make db-up       # PostgreSQL 16
make db-init     # crea la base, aplica el esquema y el rol de aplicación
make test        # 205 pruebas
make run         # http://localhost:8000/docs
```

## Qué hay construido y verificado

| Pieza | Estado | Dónde se comprueba |
|---|---|---|
| **Motor de CAPEX** con la cascada de P-16 | ✅ Completo | `tests/unit/test_capex_engine.py` · 17 |
| **Motor de fases** · estados derivados y sugeridos | ✅ Completo | `tests/unit/test_fases.py` · 32 |
| **Máquina de estados del proyecto** con sus guardas | ✅ Completo | `tests/unit/test_maquina_de_estados.py` · 21 |
| **Esquema con RLS**, triggers y `CHECK` | ✅ Completo | `tests/integration/test_rls_y_restricciones.py` · 19 |
| **Semilla de catálogos** desde el documento de diseño | ✅ Completo | `tests/integration/test_catalogos.py` · 26 |
| **Ciclo de vida de sugerencias** | ✅ Completo | `tests/unit/test_sugerencias.py` · 18 |
| **Fases y proyectos** punta a punta | ✅ Completo | `tests/integration/test_fases_y_proyectos.py` · 18 |
| **API**: catálogos, proyectos, fases, CAPEX y sugerencias | ✅ Parcial | `tests/integration/test_api.py` · 22 |
| **Tabla de CAPEX** · diseño único para PPTX y XLSX | ✅ Completo | `tests/unit/test_capex_layout.py` · 20 |
| **Fuentes y desbordamiento** con métricas reales | ✅ Completo | `tests/unit/test_fuentes_y_desbordamiento.py` · 14 |

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

- **Fotografías y documentos.** El modelo de `stored_object` y sus triggers
  están; la carga, los derivados, EXIF, duplicados y el renombrado, no.
- **Generación de PPTX, el resto del bloque 4.** La prueba de concepto está
  **superada** ([`docs/20`](../../docs/20-poc-pptx.md)): clonado, sustitución de
  marcadores, tabla nativa y render verificados sobre la plantilla real. Falta
  el mapeo persistido, las fotografías, el versionado y los avisos.
- **Frontend.** No hay nada de `apps/web`.
- **Equipo del proyecto** (miembros, roles por proyecto, alcance por activo).
- **Q&A y eventos de fase**: las tablas existen y el motor los cuenta, pero no
  hay endpoints para gestionarlos.
- **Alembic.** El esquema se aplica desde `schema.sql`. La migración inicial se
  genera cuando el modelo deje de moverse: versionar migraciones de un esquema
  que cambia cada día produce un historial inútil.
- **Autenticación completa.** Hay hash Argon2id, emisión y validación de tokens;
  faltan los endpoints de login, refresh y recuperación.

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

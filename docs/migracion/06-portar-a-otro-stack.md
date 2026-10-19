# 6 · Portar a otro stack: qué hay y qué se reaprovecha

Para responder a *«¿tenemos el código del TDD para portarlo, o lo rehacemos a
partir de la funcionalidad?»*.

---

## 6.1 · La respuesta corta

**El código existe, está completo y está probado.** No es un prototipo ni un
esqueleto: es un MVP recorrido de punta a punta con el servidor en marcha.

| | |
|---|---|
| Dónde | `github.com/fercascos/PruebaTDD` |
| Rama | `claude/real-estate-due-diligence-app-onq7x3` |
| Estado | 1.505 pruebas en verde contra PostgreSQL real, 11 saltadas |

Así que la pregunta **no es «portar o rehacer»**. Es: *¿qué partes sobreviven
al stack de la fábrica y cuáles hay que reescribir?* Y eso depende de una cosa
que desde aquí no se sabe —§6.5.

## 6.2 · El inventario, medido

| | Líneas |
|---|---:|
| API, código | 33.621 |
| API, pruebas | 28.658 |
| Interfaz, código | 17.169 |
| Comprobaciones con navegador | 5.987 |
| Guiones de `tools/` | 6.934 |
| Documentación de diseño | 14.839 |

Y por dentro: **62 tablas**, **178 rutas HTTP**, **30 migraciones**, **22
módulos** en la API.

## 6.3 · Lo que se reaprovecha sea cual sea el stack

Esto **no se rehace nunca**, ni aunque la fábrica imponga otro lenguaje. Es la
mayor parte del valor y lo que más caro saldría repetir:

| | Qué es | Por qué no se repite |
|---|---|---|
| **`docs/01` a `docs/24`** | 14.839 líneas de diseño cerrado | Son las decisiones y sus porqués, con las preguntas al cliente ya respondidas. Volver a deducirlas cuesta semanas y sale distinto |
| **`docs/18` y `docs/24`** | El análisis de las cuatro plantillas PPTX reales | **Irrepetible sin los ficheros del cliente.** Geometría medida, inventario de marcadores, lo que corrige del diseño previo |
| **`data/catalogos/`** | 6 tipologías, 20 zonas, 86 combinaciones zona × tipología, 125 códigos CAPEX en árbol de tres niveles, riesgos, conceptos, horizontes | Es la taxonomía del dominio en CSV. Datos, no código: se cargan en cualquier parte |
| **Las traducciones** | 337 filas de catálogo, 356 de frases de la API, 962 rótulos de interfaz | **El inglés es el del propio cliente**, sacado de sus plantillas. «Objeto» es `Item` porque en su informe pone `Item`. Reinventarlo daría un inglés correcto y equivocado |
| **Las 1.505 pruebas** | Como especificación ejecutable | Aunque haya que reescribirlas en otro lenguaje, dicen **qué** tiene que cumplirse. Son el contrato |
| **El esquema de PostgreSQL** | 62 tablas, 28 políticas RLS, 222 `CHECK`, 24 disparadores, 14 columnas generadas, 52 funciones | Si la fábrica mantiene PostgreSQL, esto se porta **tal cual**, con independencia del lenguaje de la aplicación |

## 6.4 · Lo que está atado a este stack

| | Coste de cambiarlo |
|---|---|
| **FastAPI + Pydantic v2** (178 rutas) | Mecánico pero voluminoso. Los contratos están en `docs/06-api.md` |
| **React 18 + Vite** (17.169 líneas) | La interfaz entera. Lo caro no son los componentes: es la cola de fotografías que sobrevive sin red y los tres orígenes de foto |
| **`python-pptx`** | **El más arriesgado de rehacer.** Generar el informe desde la plantilla del cliente, con `@repeat`, marcadores y estimación de desbordamiento, es donde más defectos sutiles aparecieron |
| **Playwright** (5.987 líneas) | Las comprobaciones que abren la aplicación de verdad. Son las que han encontrado la mayoría de los defectos reales |

### Una advertencia que vale más que el código

De los defectos reales de este repositorio, **la mayoría salieron de abrir la
aplicación, no de la suite**: un `500` al repetir el código de un proyecto, un
botón de exportar sin ruta que lo sirviera, miniaturas devolviendo `401`
porque un `<img src>` no lleva credencial, `Vary: Origin` dejando la aplicación
en blanco sin red, cinco rótulos en castellano con el extractor en verde.

Rehacer desde la funcionalidad **vuelve a pagar todos esos peajes**, uno por
uno, porque ninguno está en la descripción funcional: aparecen al construir.
Están contados en el `README.md` de la raíz y en `CLAUDE.md` §4, que es la
parte que conviene leer antes de decidir.

## 6.5 · Lo que decide la respuesta

Tres preguntas. Con ellas se puede recomendar; sin ellas, cualquier respuesta
es una corazonada:

1. **¿Qué stack impone la fábrica?** Si es Python y PostgreSQL, esto se porta
   casi entero. Si es otro lenguaje pero mantiene PostgreSQL, se conserva el
   esquema —que son las garantías de aislamiento y de integridad— y se
   reescribe la capa de aplicación. Si además cambia de base, hay que decidir
   qué pasa con RLS, los `CHECK` y los disparadores, que hoy **son la mitad de
   las garantías del producto** y no existen fuera de PostgreSQL.

2. **¿Qué es «el satélite»?** ¿Una copia del TDD dentro de la fábrica, un
   servicio que consume el TDD, o una aplicación nueva que reutiliza su
   dominio? Las tres llevan a repartos muy distintos.

3. **¿Qué dice `TDD-en-la-fabrica.md`?** Ese documento no está aquí. Lo que
   diga sobre despliegue, autenticación, multi-tenencia y almacenamiento puede
   chocar con decisiones que aquí están tomadas y probadas —la RLS y el
   almacenamiento WORM, sobre todo—, y conviene cruzarlo antes de escribir
   código.

## 6.6 · Lo que yo propondría mientras tanto

Sin esperar a esas respuestas, hay dos cosas que son buena idea en cualquier
escenario:

- **Clonar el repositorio y levantarlo** siguiendo
  [`02-arrancar-desde-cero.md`](02-arrancar-desde-cero.md). Decidir entre
  portar y rehacer sin haber visto funcionar lo que se va a tirar es decidir a
  ciegas, y se tarda diez minutos con Docker.
- **No escribir el `CLAUDE.md` del satélite desde cero.** El de aquí
  (`CLAUDE.md`) ya lleva las reglas del cliente, que no cambian al cambiar de
  stack: nada de datos reales, el original nunca se sobrescribe, ningún precio
  se elige solo, no se inventan fuentes de precios. Esas mandan sobre cualquier
  guía de fábrica, porque las fijó el cliente por escrito. Lo que hay que
  cruzar con la fábrica es el resto.

---

`[LIM]` Este documento lo escribe quien conoce **este** repositorio y no la
fábrica: de los dos lados de la comparación, sólo uno se ha medido. Las cifras
de §6.2 y §6.3 están contadas sobre el código; todo lo que se diga aquí sobre
el encaje con la fábrica es una pregunta, no una recomendación.

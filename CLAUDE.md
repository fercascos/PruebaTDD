# Cómo se trabaja en este proyecto

Esto lo lee Claude Code al abrir el repositorio. No es documentación del
producto —esa está en `docs/`— sino **las reglas de la casa**: lo que hay que
hacer, lo que no se puede hacer, y los errores que ya se han cometido aquí para
no repetirlos.

---

## 1 · Reglas del cliente. No son negociables

Las fijó el cliente por escrito y mandan sobre cualquier criterio técnico.

| | |
|---|---|
| **Nada de datos reales** | No se usan datos personales ni confidenciales reales en pruebas, semillas, grabaciones ni capturas. Todo lo que hay en `data/demo/` es ficticio a propósito |
| **Nada de IA sin autorización** | No se usan fotografías, documentos ni datos del cliente para entrenar modelos, sin autorización expresa y verificable |
| **El original nunca se sobrescribe** | Fotografías, documentos y plantillas son inmutables. Cuatro barreras independientes lo sostienen: API, dominio, base de datos y almacenamiento WORM |
| **Ningún precio se elige solo** | No existe `elegir_recomendada`. Ningún proceso automático valida un precio: lo valida una persona, y queda registrado quién |
| **No se inventan fuentes de precios** | Ni APIs, ni catálogos, ni índices. Si el dato no está registrado con su procedencia, no está |
| **Nada de scraping prohibido** | No se extrae de un sitio cuyas condiciones de uso o controles técnicos lo impidan |
| **Ni un secreto en el código** | Ni claves, ni credenciales, ni tokens. `.env.example` lleva la plantilla **sin un solo valor real** |
| **Lo pendiente se marca** | Un mock, un prototipo o una funcionalidad a medias se señala en pantalla y en el código. Una pantalla que calla y no hace nada se lee como una avería |
| **No se afirma lo que no se ha probado** | Si una integración no se ha ejercitado contra el sistema de verdad, se dice. Hay varios `[LIM]` en el código que existen solo para eso |

## 2 · Las etiquetas

Todo lo que se escribe —código, comentarios, documentación, mensajes de
commit— marca de dónde viene cada afirmación:

| Etiqueta | Significa |
|---|---|
| `[REQ]` | Requisito solicitado por el cliente |
| `[SUP]` | Supuesto adoptado a falta de confirmación |
| `[REC]` | Recomendación propia, no pedida |
| `[LIM]` | Limitación técnica conocida y asumida |
| `[PDV]` | Pendiente de validar con el cliente |

No son decorativas. `[LIM]` y `[PDV]` son los que más valen: son la diferencia
entre «esto está hecho» y «esto parece hecho».

## 3 · El idioma

**El producto está en castellano.** El código, los comentarios, los nombres de
función y de variable, la documentación y los mensajes de commit, también. El
inglés de la aplicación es una **traducción**, y vive en tablas de datos, no en
el código.

Hay cuatro capas de texto y cada una se traduce en otro sitio. Confundirlas es
el error que más veces ha salido aquí:

| Capa | Dónde está | Qué la traduce |
|---|---|---|
| Rótulos de pantalla | `apps/web/src/` | `apps/web/src/i18n/textos.ts` |
| Nombres de catálogo | La base de datos | La función SQL `nombre(name_es, name_en)` |
| Frases que compone el servidor | `apps/api/src/tdd/` | `data/api/textos_en.csv` |
| El entregable (PPTX, XLSX) | La plantilla del cliente | La plantilla, o el parámetro `?idioma=` |

### La regla: se traduce donde se pinta, nunca donde se declara

Una constante de módulo, un valor por omisión de un `dataclass` o de un modelo
de Pydantic, y una tabla de rótulos **se evalúan una vez al importar**.
Traducir ahí congela el idioma del primer arranque para todo el proceso y no
falla nada. La clave se queda en castellano; la traducción va al sitio donde se
pinta.

Lo mismo en el navegador: un formateador de `Intl` creado a nivel de módulo
nace con el idioma de ese instante y ya no cambia.

## 4 · Lo que ninguna herramienta ve

Esto ha costado encontrarlo cinco veces, siempre igual: **el extractor en verde
y la pantalla en castellano**.

`apps/web/herramientas/extraer-textos.mjs` lee el **texto** de las etiquetas
JSX. No ve, y no puede ver:

- Un rótulo pintado desde una variable: `{nombre}`, `{t.etiqueta}`.
- Una tabla de rótulos declarada como constante de módulo.
- Una plantilla de JavaScript: `` `${n}/${m} objetos` ``.
- Una ternaria de dos literales dentro de una expresión.
- Un conector suelto entre dos expresiones: `<strong>{n}</strong> de {total}`.

Lo que sí lo encuentra es **mirar la pantalla**:

```bash
node apps/web/herramientas/comprobar-prototipo.mjs
```

Abre el prototipo ya compilado y busca castellano en diecinueve pantallas. Se
comprueba contra sí mismo: apuntado al prototipo castellano (`TDD_IDIOMA=es`)
tiene que encender las diecinueve. Si no las enciende, no está mirando nada.

**Corolario, y vale para todo el proyecto, no solo para los idiomas: una
comprobación que pasa sin haber mirado es peor que ninguna.** De los defectos
reales de este repositorio, la mayoría salieron de abrir la aplicación, no de
la suite.

## 5 · Las puertas

Nada se da por terminado sin esto en verde. Es lo mismo que corre en CI
(`.github/workflows/ci.yml`), y cada paso es un objetivo del `Makefile`, para
que un fallo se reproduzca con una orden y no con arqueología de YAML.

```bash
make lint              # ruff: formato y reglas
make typecheck         # mypy estricto, dos configuraciones
make catalogs-check    # los CSV de catálogos, al día con docs/05
make no-fonts          # ninguna tipografía versionada
make test              # la suite entera contra PostgreSQL de verdad

cd apps/web
npm run lint           # tsc, dos configuraciones
npm test               # vitest
npx vite build
node herramientas/extraer-textos.mjs     # 0 sin traducir
```

`make ci` encadena las cinco primeras.

**Las pruebas corren contra PostgreSQL real, no contra un doble.** Lo que más
valor tiene de esa suite son las políticas RLS, los `CHECK`, los disparadores y
las columnas generadas, y nada de eso existe fuera de PostgreSQL. El rol de
aplicación **no tiene `BYPASSRLS`**: con un superusuario las pruebas de
aislamiento pasarían todas sin demostrar nada.

### No corras dos suites a la vez

Comparten la base `tdd_test`. Dos `pytest` simultáneos dan decenas de fallos y
errores de preparación que **se parecen muchísimo a un fallo real**. Aquí costó
media hora distinguirlo. Antes de dar por roja una suite, comprueba que solo
hay un proceso:

```bash
ps -e -o pid=,args= | grep "[p]ytest"
```

## 6 · Git

- Se desarrolla en una rama, nunca directamente sobre la rama por defecto.
- `git push -u origin <rama>`. Si falla por red, reintentar con espera creciente.
- **No se abre un pull request salvo que se pida explícitamente.**
- Los mensajes de commit están en castellano, explican **por qué** y no solo
  qué, y nombran el defecto que arreglan cuando lo hay. Son largos a propósito:
  es donde vive la razón de una decisión que el código no puede contar.
- Nunca se escribe el identificador de un modelo de IA en un commit, en un PR,
  en un comentario de código ni en nada que entre en el repositorio.

## 7 · Mapa del repositorio

```
apps/api/      FastAPI + SQLAlchemy 2 + Pydantic v2. Monolito modular.
apps/web/      React 18 + TypeScript sobre Vite. PWA.
  herramientas/  Comprobaciones con navegador de verdad (Playwright).
  prototipo/     El prototipo navegable: la aplicación en un fichero HTML.
data/
  catalogos/     Los catálogos como CSV, generados desde docs/05.
  demo/          El encargo de demostración. Datos ficticios.
  api/textos_en.csv   Las frases que compone el servidor, en inglés.
docs/          01–24, los entregables de diseño. 25 en adelante, lo que venga.
docs/migracion/     Cómo traer esto a otro entorno. Empieza por su README.
tools/         Utilidades de desarrollo (generación de catálogos, extracción).
```

## 8 · Qué leer antes de tocar qué

| Si vas a tocar… | Lee antes |
|---|---|
| El modelo de datos | `docs/04-modelo-de-datos.md` |
| Los catálogos | `docs/05-catalogos-y-taxonomias.md`, y regenera con `make catalogs` |
| El CAPEX o los precios | `docs/11-capex-precios.md` |
| La generación del informe | `docs/12-pptx.md` y `docs/24-plantillas-del-informe.md` |
| Permisos o RLS | `docs/07-roles-permisos.md` y `docs/13-seguridad-privacidad-auditoria.md` |
| Cualquier texto visible | La sección 3 y la 4 de este fichero |

---

## 9 · Dos cosas que este proyecto ha aprendido a su costa

**Un respaldo silencioso esconde el fallo.** Una tabla de traducciones que no
se encuentra y devuelve vacío, un `ContextVar` con castellano por omisión, una
columna `name_en` que admite nulos: ninguno falla, todos dejan la aplicación
entera en el idioma equivocado sin un solo error. Donde el valor por omisión
sea indistinguible de un acierto, haz que falle fuerte o escribe la prueba.

**Contar niveles de directorio falla.** `parents[5]`, luego `parents[6]`, y las
dos mal. Se busca hacia arriba hasta encontrar el fichero, y si no está, se
lanza. El síntoma de no hacerlo es el peor: la tabla queda vacía y todo sale en
castellano sin un solo error.

# 4 · Comprobar que la migración ha salido

Una lista que se recorre de arriba abajo. Cada paso dice **qué número esperar**,
porque «pasó» sin una cifra al lado no distingue entre una suite que corrió y
una que se saltó la mitad.

---

## 4.1 · Las puertas estáticas

```bash
make lint              # → All checks passed!
make typecheck         # → Success: no issues found in 141 source files
                       #   Success: no issues found in 18 source files
make catalogs-check    # sin salida = los CSV están al día con docs/05
make no-fonts          # sin salida = no hay ninguna tipografía versionada
```

`make typecheck` corre mypy **dos veces**, con dos configuraciones: la de
`apps/api` y la de `tools`. Si solo ves una línea de «Success», falta una.

## 4.2 · La suite de la API

```bash
make test
```

Espera **1.505 pruebas pasadas y 11 saltadas**.

Las 11 saltadas son las de medición de desbordamiento, que se saltan solas
cuando no hay ninguna tipografía instalada. **Si ves muchas más saltadas, algo
no está donde debería.** Para que corran:

```bash
make fonts-install && make test     # → menos saltadas
```

### Si la suite sale roja

Antes de leer un solo fallo, comprueba que no hay **dos `pytest` a la vez**:

```bash
ps -e -o pid=,args= | grep "[p]ytest"
```

Comparten la base `tdd_test`. Dos simultáneos dan decenas de fallos y errores
de preparación con el mismo `connection refused`, y **se parecen muchísimo a un
fallo real**. Aquí costó media hora distinguirlo.

## 4.3 · El aislamiento entre organizaciones

```bash
make test-rls
```

Es la prueba que de verdad protege al cliente. Para que signifique algo, el rol
`tdd_app` **no puede tener `BYPASSRLS`** ni ser propietario de las tablas: con
un superusuario pasan todas sin demostrar nada. Compruébalo:

```bash
psql -h /tmp -p 55432 -U postgres -tAc \
  "SELECT rolbypassrls FROM pg_roles WHERE rolname = 'tdd_app';"   # → f
```

## 4.4 · Los catálogos

```bash
make test-catalogs
```

Comprueba las 86 combinaciones de zona × tipología y el árbol de CAPEX
completo. Si falla, lo más probable es que alguien haya editado
`docs/05-catalogos-y-taxonomias.md` o un CSV sin regenerar el otro:
`make catalogs` los vuelve a sacar del documento.

## 4.5 · La interfaz

```bash
cd apps/web
npm run lint                            # tsc, dos configuraciones, sin salida
npm test                                # → 6 ficheros, 61 pruebas
npx vite build                          # → ✓ built in …
node herramientas/extraer-textos.mjs    # → 962 textos · 962 traducidos · 0 sin traducir
```

## 4.6 · Las traducciones del servidor

Van dentro de `make test`, pero conviene saber cuál es su prueba, porque es la
que falla el día que alguien escribe un mensaje nuevo:

```
apps/api/tests/unit/test_textos_de_la_api.py
```

Vigila cuatro cosas, y las cuatro se estropean **sin hacer ruido**: entradas
muertas en la tabla, llamadas a `traducir()` sin traducción, huecos que no
coinciden entre los dos idiomas, y mensajes de error que saldrían en castellano
en una pantalla inglesa.

## 4.7 · La comprobación que mira la pantalla

Esta es la que encuentra lo que ninguna otra puede. Necesita Chromium y los dos
prototipos compilados.

```bash
cd apps/web
node herramientas/comprobar-prototipo.mjs
# → 19 pantallas, todas ✓, «Ninguna pantalla con texto castellano.»
```

**Y el control, que no es opcional:**

```bash
TDD_IDIOMA=es node herramientas/comprobar-prototipo.mjs
# → 19 pantallas con texto castellano
```

Si el control **no** enciende las diecinueve, la comprobación no está mirando
nada y su «todo verde» no vale. Una comprobación que pasa sin mirar es peor que
ninguna.

## 4.8 · Y después, a mano

Nada de lo anterior sustituye a abrir la aplicación. Lo mínimo que yo haría:

1. Entrar, crear un proyecto, darle una fase y un activo.
2. Subir una fotografía y clasificarla.
3. Registrar un hallazgo con su línea de CAPEX y exportarlo a Excel.
4. Subir **cualquier** PPTX como plantilla, mapearla y generar el informe.
5. Cambiar el idioma a inglés arriba a la derecha y recorrer lo mismo.
6. Cortar la red y comprobar que el armazón carga y la cola de fotos sigue ahí.

El punto 6 destapó un fallo que con cobertura no se ve: `Vary: Origin` impedía
encontrar el JavaScript precacheado y la aplicación abría en blanco sin red.

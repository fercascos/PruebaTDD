# 2 · Del `git clone` a la aplicación funcionando

Hay dos caminos y los dos valen. Elige por lo que quieras hacer:

| | Para | Lo que aporta |
|---|---|---|
| **Contenedores** | Enseñar la aplicación, probar el despliegue, validar el informe de punta a punta | Un **S3 de verdad** (MinIO) con versionado y Object Lock, un SMTP de verdad, LibreOffice para convertir, y las tipografías dentro de la imagen |
| **Local** | Desarrollar, correr la suite, iterar deprisa | Arranca en segundos y no necesita Docker |

---

## Camino A · En contenedores

```bash
git clone <la-url> PruebaTDD && cd PruebaTDD
cp .env.example .env
```

Abre `.env` y rellena **lo único imprescindible**:

```bash
APP_SECRET_KEY=$(openssl rand -hex 32)
```

El resto tiene valores por omisión que funcionan en local. Lo que dejes vacío
—SMTP, antivirus, teselas del mapa— degrada de forma visible, no en silencio.

```bash
make up          # base, objetos, correo, API, workers y frontend, y espera a que respondan
make up-admin ORG='Consultora Ejemplo' EMAIL='admin@ejemplo.example' NOMBRE='Nombre Apellido'
```

`make up-admin` pide la contraseña por teclado: no se pasa por la línea de
órdenes, que quedaría en el historial del shell.

| | |
|---|---|
| Aplicación | http://localhost:8080 |
| API y su documentación | http://localhost:8000/docs |
| Correo capturado | http://localhost:8025 |
| Consola del almacén | http://localhost:9001 |

`make ps` dice qué está levantado y con qué salud · `make logs` sigue los
registros · `make down` para sin tocar los datos · `make destroy` borra también
los volúmenes.

---

## Camino B · Local

```bash
git clone <la-url> PruebaTDD && cd PruebaTDD
make install                       # pip install -e "apps/api[dev]"
cd apps/web && npm ci && cd ../..
```

### La base

```bash
make db-up      # arranca PostgreSQL por socket en /tmp, puerto 55432
make db-init    # DESTRUCTIVO: recrea las dos bases, aplica migraciones y siembra
```

`make db-init` crea **dos** bases y eso importa:

- `tdd` — la de desarrollo.
- `tdd_test` — la de la suite, **aparte a propósito**. El `conftest` hace un
  `DROP SCHEMA public CASCADE` en cada arranque: apuntándola a `tdd` bastaba
  con ejecutar `make test` una vez para perder los datos de desarrollo, el
  administrador incluido, y volver a una aplicación en la que no se puede
  entrar. Se descubrió justo así.

También crea el rol `tdd_app`, que **no es propietario de las tablas y no tiene
`BYPASSRLS`**. Arrancar la API con la conexión de administración dejaría la RLS
sin efecto y todo parecería funcionar, que es la peor forma de que falle.

### Arrancar

```bash
make db-admin ORG='Consultora Ejemplo' EMAIL='admin@ejemplo.example' NOMBRE='Nombre Apellido'
make run        # la API, como tdd_app, con la RLS en vigor
```

Y en otra terminal:

```bash
cd apps/web && npm run dev      # http://localhost:5173, con proxy a la API
```

### Datos para ver algo

Con la API en marcha:

```bash
make demo       # siembra un encargo de demostración con datos ficticios
```

---

## Después de cada migración del esquema

```bash
make db-migrate
```

Ese objetivo vuelve a dar permisos al rol de aplicación, y no es redundante:
una migración que crea una tabla la crea como `postgres`, y `tdd_app` —que no
es propietario— se queda sin permisos sobre ella. La tabla existe, la RLS está
puesta, y la aplicación recibe «permission denied» en cuanto la toca.

## El prototipo navegable

No es una maqueta: es la aplicación de verdad en un solo fichero HTML, que se
abre con doble clic sin servidor, sin base de datos y sin red. Necesita la
aplicación en marcha para **grabarse**, no para verse.

```bash
cd apps/web

# Castellano
TDD_PROYECTO=<uuid-del-proyecto-demo> npm run prototipo:grabar
npm run prototipo

# Inglés: necesita SU grabación, porque la mitad del texto lo manda la API
TDD_PROYECTO=<uuid> TDD_IDIOMA=en TDD_GRABACION=prototipo/grabacion-en.json npm run prototipo:grabar
TDD_IDIOMA=en npm run prototipo

node herramientas/comprobar-prototipo.mjs    # busca castellano en el inglés
```

Los dos ficheros quedan en `apps/web/prototipo/entregable/`. No se versionan:
son 1,4 MB por idioma de HTML generado que envejece en cuanto la API cambia.

`[REQ]` Apunta el grabador **solo a una base de demostración con datos
ficticios**. Lo que grabe acaba dentro de un fichero que se puede compartir;
con datos de un cliente sería publicar su proyecto.

# 1 · Qué tiene que ofrecer el entorno

## Lo imprescindible

| | Versión | Por qué esa |
|---|---|---|
| **Python** | **3.11** o superior | `pyproject.toml` lo exige. CI corre exactamente 3.11 |
| **Node** | **22** | Es con la que corre CI. No hay `engines` en `package.json`: si usas otra y algo se rompe, empieza por aquí |
| **PostgreSQL** | **16** | No es un capricho de versión: ver abajo |
| **Docker** | cualquiera reciente, con Compose v2 | Solo para el camino de contenedores |

### PostgreSQL no se puede sustituir por otra base

No es portabilidad perdida por descuido. El modelo se apoya en cosas que solo
existen en PostgreSQL y que son **la mitad de las garantías del producto**:

- **Row Level Security** para el aislamiento entre organizaciones. Es lo que
  impide que un proyecto de un cliente se vea desde otro.
- **Restricciones `CHECK`** que sostienen reglas de negocio que la aplicación
  también comprueba. La redundancia es a propósito: si alguien se salta la
  capa de servicio, la base sigue diciendo que no.
- **Disparadores** y **columnas generadas**.
- Una **función SQL** propia, `nombre(name_es, name_en)`, que resuelve el
  idioma de los catálogos leyendo el contexto de la sesión.

Las pruebas corren contra una base de verdad por este motivo. Un doble en
memoria pasaría las mismas pruebas sin demostrar nada.

## Lo que hace falta según qué quieras hacer

| Para… | Necesitas | Si no lo tienes |
|---|---|---|
| Correr la API y la suite | Lo de arriba y nada más | — |
| Generar el informe con medición de desbordamiento fiable | Una tipografía instalada (`make fonts-install` trae Montserrat, SIL OFL) | Las pruebas de medición **se saltan solas** y no demuestran nada. La aplicación lo dice en un aviso |
| Las comprobaciones de navegador (`apps/web/herramientas/`) | Chromium, y WebKit para la vista de campo | Esas comprobaciones no corren. La suite de `vitest` sí |
| El prototipo navegable | Chromium | No se puede grabar ni comprobar |
| El entorno completo en contenedores | Docker con Compose | Queda el camino local, que también funciona |

### Chromium y Playwright

Las comprobaciones de navegador usan Playwright. En un contenedor donde
Chromium ya venga instalado, dilo con la variable y **no lo descargues otra
vez**:

```bash
export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
export CHROMIUM_PATH=/ruta/al/chrome        # la lee herramientas/navegador.mjs
```

`[LIM]` **WebKit de Playwright no es Safari de iOS.** Comparte motor, así que
caza las diferencias de CSS y de API de JavaScript, que son la mayoría. Lo que
no reproduce: la cámara real, HEIC de verdad, el desalojo de IndexedDB a los
siete días, la presión de memoria que recarga la pestaña, y «Añadir a pantalla
de inicio». Eso solo se comprueba en un teléfono, y hasta que se haga no se
puede afirmar que la vista de campo funcione en un iPhone.

## Servicios de apoyo

Ninguno es obligatorio para que la aplicación arranque. Todos degradan de forma
**visible**, que es la decisión de diseño que hay detrás de cada uno:

| Servicio | Sin él | Se nota en |
|---|---|---|
| **Almacén S3** | `STORAGE_BACKEND=disco` guarda en el sistema de ficheros | Nada en desarrollo. En producción se pierde el WORM, que es la barrera 4 de la inmutabilidad |
| **SMTP** | No se envía nada. Se registra en el log que **no** se ha enviado, con destinatario y asunto pero nunca el cuerpo | Recuperar la contraseña: el enlace no llega. La aplicación no finge que sí |
| **ClamAV** | Cada fichero queda `NO_ANALIZADO`, que **no es lo mismo que limpio**, y así se dice | La ficha de cada fotografía y del informe |
| **Redis** | — | Solo si se usa la cola con Celery; el worker de la aplicación no lo necesita |

Habilitar el antivirus **sin** `CLAMAV_HOST` no arranca a medias: falla. Sería
peor que no habilitarlo, porque quien despliega creería estar protegido.

## Red

El proyecto **no llama a ningún servicio externo** en funcionamiento normal, y
eso es deliberado:

- **No hay ninguna fuente de precios externa**, ni está prevista (`[REQ]` P-06).
- **No hay proveedor de teselas** configurado. El mapa funciona igual —las
  posiciones y las distancias son correctas, hay escala— y la aplicación no
  contacta con ningún servidor. Poner una URL en `VITE_MAP_TILE_URL` es aceptar
  las condiciones de quien la sirve, y esa decisión es de quien despliega.
- La revisión documental con IA está **apagada por proyecto** y la enciende
  quien lo dirige, con registro de quién lo hizo.

Para **instalar** sí hace falta red: PyPI y el registro de npm. Si el entorno
nuevo tiene una política de red restrictiva, esos dos son los que hay que
permitir, más el `git` del repositorio.

## Para un agente trabajando en el repositorio

Si en el entorno nuevo va a trabajar Claude Code o similar, además de lo
anterior conviene que tenga:

- **`CLAUDE.md` en la raíz** (está). Es lo que le dice las reglas del cliente,
  las etiquetas, la regla del idioma y las puertas.
- **Chromium**, porque buena parte de los defectos de este proyecto solo se
  encuentran abriendo la aplicación, y eso está escrito en `CLAUDE.md` §4.
- **PostgreSQL arrancable sin permisos especiales.** El camino local usa un
  servidor por socket en `/tmp`, sin `sudo`.
- Acceso de escritura al repositorio para empujar a una rama.

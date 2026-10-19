# Traer este proyecto a otro entorno

Esta carpeta es lo que hace falta para sacar el repositorio del entorno donde
se construyó y ponerlo a funcionar en otro: un entorno privado de Claude para
empresa, el portátil de alguien, o un servidor.

No duplica la documentación de producto. Los veinticuatro entregables de diseño
siguen en `docs/01-…` a `docs/24-…` y el estado de cada mitad, en
`apps/api/README.md` y `apps/web/README.md`. **Esto es solo lo que cambia al
cambiar de sitio.**

## Léelo en este orden

| | | Para qué |
|---|---|---|
| 1 | [`01-el-entorno.md`](01-el-entorno.md) | Qué tiene que ofrecer la máquina y el contenedor: versiones, servicios, herramientas, red |
| 2 | [`02-arrancar-desde-cero.md`](02-arrancar-desde-cero.md) | Del `git clone` a la aplicación funcionando, por los dos caminos |
| 3 | [`03-lo-que-no-viaja.md`](03-lo-que-no-viaja.md) | **Lo más importante.** Lo que el repositorio no lleva dentro y hay que conseguir aparte |
| 4 | [`04-comprobar-la-migracion.md`](04-comprobar-la-migracion.md) | Cómo saber que ha salido bien, con las cifras que se esperan |
| 5 | [`05-estado-y-pendientes.md`](05-estado-y-pendientes.md) | Qué está construido, qué está a medias y qué está sin empezar |

Y en la raíz del repositorio, [`CLAUDE.md`](../../CLAUDE.md): las reglas de
trabajo, que Claude Code lee solo al abrir el proyecto. Si en el entorno nuevo
va a trabajar un agente, ese fichero es el que más importa de todos.

## Si no puedes conectar el repositorio

Si lo que tienes delante es un cuadro de «sube un fichero» y no un repositorio
conectado, los siete documentos se juntan en uno:

```bash
python3 tools/juntar_documentacion.py -s TDD-documentacion-migracion.md
```

Salen 41 KB con su índice, los títulos encajados y los enlaces entre documentos
convertidos en enlaces internos. **No se versiona**: es una copia de ficheros
que ya están aquí, y una copia que envejece dentro del propio repositorio es lo
que hace que alguien acabe leyendo una aplicación que ya no existe.

`[REC]` Si el sitio donde lo subes distingue entre **instrucciones** y
**ficheros adjuntos**, la parte 1 —las reglas de trabajo— va en las
instrucciones, no como adjunto: son reglas de comportamiento y tienen que estar
siempre delante, no competir por la atención con el resto.

## La versión de diez minutos

Si solo quieres verlo funcionando y tienes Docker:

```bash
git clone <la-url> PruebaTDD && cd PruebaTDD
cp .env.example .env            # y rellena APP_SECRET_KEY: openssl rand -hex 32
make up                         # base, objetos, correo, API, workers y frontend
make up-admin ORG='Consultora Ejemplo' EMAIL='admin@ejemplo.example' NOMBRE='Nombre Apellido'
```

| | |
|---|---|
| Aplicación | http://localhost:8080 |
| API y su documentación | http://localhost:8000/docs |
| Correo capturado | http://localhost:8025 |
| Almacén de objetos | http://localhost:9001 |

Eso te deja la aplicación en pie y vacía. Para verla **con contenido**, sigue
con `make demo`, que siembra un encargo de demostración con datos ficticios.

## Lo que este repositorio no te va a dar

Y conviene saberlo antes de empezar, no a mitad:

- **El material del cliente.** Las memorias técnicas, los presupuestos y las
  plantillas PPTX del informe son confidenciales y **no están aquí**. Sin ellos
  la aplicación arranca y funciona; lo que no se puede es generar un informe
  con la plantilla de verdad. Está todo en [`03-lo-que-no-viaja.md`](03-lo-que-no-viaja.md).
- **Ningún secreto.** `.env.example` es una plantilla sin un solo valor real.
- **El prototipo navegable ya compilado**, ni las grabaciones de la API que
  lleva dentro: se regeneran, y un fichero generado que envejece dentro del
  repositorio acaba enseñando una aplicación que ya no existe.

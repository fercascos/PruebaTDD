"""Las cuatro cosas que hay que poder mirar en un panel.

Deliberadamente **pocas**. Un panel con sesenta gráficas no lo mira nadie; lo
que se necesita para operar esto es saber si la aplicación responde, si
responde rápido, si la cola avanza y si se está llenando.

`[REC]` La profundidad de la cola es la métrica que más avisa de esta
aplicación. Un informe tarda minutos y se genera en otro proceso: si el worker
muere, la interfaz no se entera —las peticiones siguen respondiendo en
milisegundos— y lo único que se ve es que los informes «tardan». La cola
creciendo se ve **antes** de que nadie llame.

`[LIM]` No hay traza distribuida (OpenTelemetry). Sería lo siguiente, y con dos
procesos y una base de datos no compensa todavía: el identificador de petición
correlaciona la API con el worker, que es el salto que hay.
"""

from __future__ import annotations

from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.core import CollectorRegistry as _Registro
from sqlalchemy import text
from sqlalchemy.engine import Engine

#: Un registro propio, no el global. El global es un singleton de módulo: dos
#: aplicaciones en el mismo proceso —la suite crea varias— chocarían al
#: registrar la misma métrica dos veces.
REGISTRO: _Registro = CollectorRegistry()

#: `text/plain; version=0.0.4`, no `text/plain` a secas: Prometheus mira la
#: versión para decidir cómo interpretar el cuerpo.
TIPO_MIME = CONTENT_TYPE_LATEST

PETICIONES = Counter(
    "tdd_peticiones_total",
    "Peticiones atendidas",
    # La ruta con PLANTILLA, no la concreta: `/projects/{id}` y no
    # `/projects/8f3a…`. Con el identificador dentro, cada encargo crearía su
    # propia serie temporal y en un mes habría cien mil.
    ["metodo", "ruta", "estado"],
    registry=REGISTRO,
)

DURACION = Histogram(
    "tdd_peticion_segundos",
    "Duración de las peticiones",
    ["metodo", "ruta"],
    # Los cortes van pensados para esta aplicación: el compromiso es que nada
    # bloquee la interfaz más de 3 s (E-10), así que hay corte justo ahí.
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 3.0, 10.0),
    registry=REGISTRO,
)

TAREAS = Counter(
    "tdd_tareas_total",
    "Tareas de la cola terminadas",
    ["tipo", "resultado"],
    registry=REGISTRO,
)

COLA = Gauge(
    "tdd_cola_pendientes",
    "Tareas esperando en la cola",
    ["cola"],
    registry=REGISTRO,
)

COLA_ANTIGUEDAD = Gauge(
    "tdd_cola_espera_segundos",
    "Antigüedad de la tarea pendiente más vieja",
    ["cola"],
    registry=REGISTRO,
)


def medir_cola(motor: Engine) -> None:
    """Lee la cola y actualiza los medidores. La llama `/metrics` al servirse.

    Se consulta al pedir las métricas y no en un hilo aparte: son dos consultas
    agregadas cada vez que el recolector pasa, y un hilo más es una cosa más
    que puede quedarse colgada sin que nadie lo note.
    """
    with motor.connect() as conn:
        filas = conn.execute(
            text(
                "SELECT queue, count(*), "
                "       COALESCE(EXTRACT(EPOCH FROM (now() - min(created_at))), 0) "
                "  FROM job WHERE status = 'PENDIENTE' GROUP BY queue"
            )
        ).all()
    vistas = set()
    for cola, cuantas, espera in filas:
        COLA.labels(cola=cola).set(cuantas)
        COLA_ANTIGUEDAD.labels(cola=cola).set(float(espera))
        vistas.add(cola)
    # Una cola que se vacía deja de aparecer en el GROUP BY. Sin esto, su
    # medidor se quedaría clavado en el último valor y el panel diría que hay
    # trabajo pendiente para siempre.
    for cola in ("heavy", "io"):
        if cola not in vistas:
            COLA.labels(cola=cola).set(0)
            COLA_ANTIGUEDAD.labels(cola=cola).set(0)


def exponer() -> bytes:
    """El texto que entiende Prometheus."""
    return generate_latest(REGISTRO)


def plantilla_de_ruta(scope: Any) -> str:
    """La ruta **completa** con sus parámetros sin sustituir, o `desconocida`.

    Sin ninguna ruta que case —un 404— se devuelve una etiqueta fija: contar
    cada URL inexistente crearía una serie por cada intento de alguien probando
    rutas al azar, que es una de las formas más fáciles de reventar un
    Prometheus desde fuera.

    Y no se usa `scope["route"].path` directamente, aunque parezca lo obvio.
    Con routers anidados —esta aplicación monta todo bajo `/api/v1`— esa ruta
    viene **relativa al router incluido**: salía `/catalogs/zones` en vez de
    `/api/v1/catalogs/zones`, y `root_path` está vacío, así que el prefijo se
    perdía. Una etiqueta que no coincide con ninguna URL real es una etiqueta
    que no sirve para buscar nada. Se reconstruye desde la ruta que se pidió,
    devolviendo cada parámetro a su forma de plantilla.
    """
    if scope.get("route") is None:
        return "desconocida"
    camino = str(scope.get("path", ""))
    for nombre, valor in (scope.get("path_params") or {}).items():
        camino = camino.replace(str(valor), "{" + nombre + "}")
    return camino or "desconocida"

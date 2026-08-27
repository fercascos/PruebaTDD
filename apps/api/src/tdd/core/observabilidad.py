"""Qué está pasando ahí dentro: registro estructurado y trazas correladas.

Antes de esto, el sistema era **opaco en el peor momento**. El manejador de
`500` prometía en su propia documentación que «el detalle técnico va al log,
correlacionado por `X-Request-Id`», y no había ni identificador ni registro: la
excepción se descartaba entera. Un error en producción no dejaba nada que mirar.

Tres piezas, y ninguna es opcional para operar esto:

1. **Un identificador por petición**, que entra por `X-Request-Id` si el
   balanceador ya puso uno y se genera si no. Viaja en un `ContextVar`, así que
   cualquier registro emitido durante esa petición lo lleva sin que haya que
   pasarlo por parámetro por medio sistema.

2. **Ese identificador llega al worker.** Es la correlación que de verdad
   importa aquí: un informe se pide en una petición y se genera minutos después
   en otro proceso. Sin esto, «el informe de las 11:04 salió mal» no se puede
   atar a nada.

3. **Una línea por petición**, en JSON fuera de local: método, ruta, estado,
   duración, organización y usuario. Identificadores, nunca datos personales:
   un registro que lleva el correo de alguien es un registro que no se puede
   mandar a un servicio externo sin una evaluación de impacto.

`[REC]` En local se escribe en texto, que se lee; en `staging` y `production`,
JSON, que se indexa. Es la misma información.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

#: La cabecera estándar de hecho. La respetan los balanceadores y las mallas de
#: servicio, así que si alguien ya puso una, se conserva en vez de inventar otra
#: y romper la traza a mitad de camino.
CABECERA = "X-Request-Id"

#: El identificador de la petición en curso. `ContextVar` y no una variable
#: global porque el servidor atiende varias a la vez en el mismo proceso.
peticion_actual: ContextVar[str] = ContextVar("peticion_actual", default="")

#: Qué se admite como identificador venido de fuera: lo que usan en la práctica
#: los balanceadores (hexadecimal, UUID, los identificadores de traza de W3C).
_ADMISIBLE = re.compile(r"[A-Za-z0-9._-]{8,64}")

#: Qué se le cuenta a quien mida: el `scope` —para sacar la ruta con
#: plantilla—, el método, el estado y los segundos.
Observador = Callable[[Any, str, int, float], None]

#: Campos que `logging` pone en cada registro y que no aportan nada en JSON.
_RESERVADOS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


#: Dónde se guarda el identificador dentro del `scope` de ASGI.
CLAVE_EN_SCOPE = "tdd_traza"


def id_de_peticion() -> str:
    """El identificador de la petición en curso, o vacío fuera de una."""
    return peticion_actual.get()


def traza_de(peticion: Request) -> str:
    """El identificador de **esta** petición, mirando primero en su `scope`.

    Hace falta la doble vía, y no es redundancia. El manejador de `500` de
    Starlette vive en `ServerErrorMiddleware`, que envuelve a todos los
    middlewares de la aplicación —también a este—: cuando corre, el
    `ContextVar` ya se ha restaurado y el identificador saldría **vacío justo
    en el registro que más falta hace**. El `scope` sí sobrevive, porque es el
    mismo objeto que viaja con la petición de principio a fin.
    """
    del_scope = peticion.scope.get(CLAVE_EN_SCOPE, "")
    return str(del_scope) if del_scope else peticion_actual.get()


class FormatoJson(logging.Formatter):
    """Un registro por línea, en JSON, con el identificador de petición dentro.

    Se escribe a mano en vez de traer `structlog`: lo que hace falta cabe en
    treinta líneas, y una dependencia menos en la ruta de arranque es una cosa
    menos que pueda impedir que la aplicación levante.
    """

    def format(self, record: logging.LogRecord) -> str:
        datos: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "nivel": record.levelname,
            "logger": record.name,
            "mensaje": record.getMessage(),
        }
        traza = id_de_peticion()
        if traza:
            datos["peticion"] = traza
        # Lo que cada llamada añada con `extra={...}` entra tal cual. Es lo que
        # convierte «falló algo» en «falló la tarea X del encargo Y».
        for clave, valor in record.__dict__.items():
            if clave not in _RESERVADOS and not clave.startswith("_"):
                datos[clave] = valor
        if record.exc_info:
            datos["excepcion"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False, default=str)


class FormatoTexto(logging.Formatter):
    """El de local: legible por una persona, con la traza al final si la hay."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)s · %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        traza = id_de_peticion()
        return f"{base}  [{traza[:8]}]" if traza else base


def configurar(*, entorno: str = "local", nivel: str = "INFO") -> None:
    """Deja el registro raíz como toca. Idempotente.

    La llaman la API y el worker: los dos escriben con el mismo formato, que es
    lo que permite mirarlos juntos cuando algo cruza de uno a otro.
    """
    manejador = logging.StreamHandler()
    manejador.setFormatter(FormatoTexto() if entorno == "local" else FormatoJson())
    raiz = logging.getLogger()
    # Se sustituyen los manejadores en vez de añadir otro: `basicConfig` o
    # `uvicorn` pueden haber puesto ya el suyo, y entonces cada línea saldría
    # dos veces, una en cada formato.
    raiz.handlers = [manejador]
    raiz.setLevel(nivel.upper())
    # `uvicorn.access` escribe su propia línea por petición, con menos datos que
    # la nuestra y sin identificador. Se apaga: dos líneas por petición que no
    # se pueden correlacionar entre sí es peor que una sola.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False


class TrazaDePeticion:
    """Middleware ASGI: identificador, una línea por petición y la cabecera.

    Es ASGI puro y no `BaseHTTPMiddleware` a propósito. `BaseHTTPMiddleware`
    ejecuta el resto de la aplicación en otra tarea, y un `ContextVar` puesto
    ahí **no lo ven** los manejadores de excepción de FastAPI: el identificador
    saldría vacío justo en el registro que más falta hace, el del error.
    """

    def __init__(self, app: ASGIApp, al_terminar: Observador | None = None) -> None:
        self.app = app
        self.log = logging.getLogger("tdd.peticion")
        # Las métricas se enchufan por aquí en vez de importarse: así este
        # módulo sirve aunque no haya `prometheus_client`, y quien lea el
        # arranque ve en un sitio qué se está midiendo.
        self.al_terminar = al_terminar

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        peticion = Request(scope)
        entrante = peticion.headers.get(CABECERA, "")
        # Se acepta el de fuera solo si tiene una pinta razonable. `isascii()`
        # NO basta: un salto de línea es ASCII, y ese identificador acaba escrito
        # en un registro, así que aceptarlo sería dejar que alguien inyecte
        # líneas falsas en el log desde una cabecera. Se exige un conjunto
        # cerrado de caracteres y una longitud acotada.
        traza = entrante if _ADMISIBLE.fullmatch(entrante) else uuid.uuid4().hex
        scope[CLAVE_EN_SCOPE] = traza
        testigo = peticion_actual.set(traza)
        comienzo = time.perf_counter()
        estado = 500

        async def enviar(mensaje: Any) -> None:
            nonlocal estado
            if mensaje["type"] == "http.response.start":
                estado = mensaje["status"]
                cabeceras = list(mensaje.get("headers", []))
                cabeceras.append((CABECERA.lower().encode(), traza.encode()))
                mensaje = {**mensaje, "headers": cabeceras}
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        finally:
            ms = round((time.perf_counter() - comienzo) * 1000, 1)
            # `/health` lo pide una sonda cada quince segundos: registrarlo
            # ahogaría todo lo demás.
            if peticion.url.path != "/health":
                self.log.info(
                    "%s %s → %s (%s ms)",
                    peticion.method,
                    peticion.url.path,
                    estado,
                    ms,
                    extra={
                        "metodo": peticion.method,
                        "ruta": peticion.url.path,
                        "estado": estado,
                        "ms": ms,
                    },
                )
            if self.al_terminar is not None:
                self.al_terminar(scope, peticion.method, estado, ms / 1000)
            peticion_actual.reset(testigo)


def cabecera_de_traza(respuesta: Response) -> Response:
    """Pone el identificador en una respuesta construida a mano."""
    traza = id_de_peticion()
    if traza:
        respuesta.headers[CABECERA] = traza
    return respuesta


#: Tipo del siguiente eslabón, para quien quiera envolver esto.
Siguiente = Callable[[Request], Awaitable[Response]]

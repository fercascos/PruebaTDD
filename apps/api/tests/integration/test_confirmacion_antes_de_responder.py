"""La transacción se confirma **antes** de enviar la respuesta.

El fallo que estas pruebas fijan salió al sembrar el encargo de demostración, y
no de la suite: el sembrador creaba un activo, leía el identificador del `201` y
pedía ese activo acto seguido. A veces no estaba.

La causa no es la base de datos, es el orden. La sesión se abre en una
dependencia con `yield`, y el `commit` va después del `yield`; FastAPI ejecuta
ese tramo al cerrar la pila de salida de la petición, y **esa pila se cierra
después de haber enviado la respuesta**. Entre medias hay una ventana —corta,
pero real— en la que el cliente ya tiene el identificador y la fila todavía no
existe para nadie más.

Reproducirlo con dos peticiones seguidas sería una prueba que falla una de cada
veinte ejecuciones, que es la peor clase de prueba. Aquí se mira el orden
directamente: una sonda ASGI se interpone entre la aplicación y el envío, y
cuando pasa el cuerpo de la respuesta pregunta **desde otra conexión** si la
fila ya se ve. Si el `commit` va después, no se ve, y la prueba falla siempre.

`[REQ]` §13 · Esto no es cosmético. La ventana también afecta al caso de error:
si el `commit` falla —un interbloqueo, un disco lleno—, fallar después de haber
enviado un `201` deja al cliente creyendo que existe algo que se deshizo.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from conftest import montar_app
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from tdd.core.db import ContextoRLS, aplicar_contexto

pytestmark = pytest.mark.db

RUTA = "/api/v1"


class SondaDeEnvio:
    """Se interpone entre la aplicación y el envío de la respuesta.

    Es ASGI puro y no `BaseHTTPMiddleware` a propósito: el middleware de
    Starlette introduce su propia tarea y su propio momento de envío, con lo que
    mediría el orden de otra cosa distinta de la que se quiere medir.
    """

    def __init__(self, app: Any, mirar: Any) -> None:
        self.app = app
        self.mirar = mirar
        #: Lo que se veía desde fuera en el instante de enviar cada respuesta.
        self.visto: list[bool] = []

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trozos: list[bytes] = []

        async def enviar(mensaje: Any) -> None:
            if mensaje["type"] == "http.response.body":
                trozos.append(mensaje.get("body", b""))
                if not mensaje.get("more_body", False):
                    # Justo aquí: la respuesta está saliendo. Lo que se vea
                    # desde otra conexión es lo que vería el cliente si pidiera
                    # el recurso inmediatamente después.
                    self.visto.append(self.mirar(b"".join(trozos)))
            await send(mensaje)

        await self.app(scope, receive, enviar)


def test_la_fila_ya_se_ve_desde_fuera_cuando_sale_la_respuesta(
    motor_app: Engine,
    fabrica: sessionmaker[Session],
    datos_base: dict[str, uuid.UUID],
    cab: Any,
) -> None:
    """Crear un encargo y preguntar por él desde otra conexión, a la vez."""

    def mirar(cuerpo: bytes) -> bool:
        creado = json.loads(cuerpo)
        # Otra sesión, otra conexión: es el punto de vista de la siguiente
        # petición, que puede caer en otro proceso de la aplicación.
        otra = fabrica()
        try:
            otra.begin()
            aplicar_contexto(
                otra,
                ContextoRLS(
                    organization_id=datos_base["org_a"],
                    user_id=datos_base["admin_a"],
                    can_manage_suggestions=True,
                ),
            )
            return (
                otra.execute(
                    text("SELECT 1 FROM project WHERE id = :i"), {"i": creado["id"]}
                ).first()
                is not None
            )
        finally:
            otra.rollback()
            otra.close()

    app = montar_app(motor_app, fabrica)
    sonda = SondaDeEnvio(app, mirar)

    with TestClient(sonda, base_url="http://pruebas") as cliente:
        respuesta = cliente.post(
            f"{RUTA}/projects",
            json={
                "client_id": str(datos_base["cliente_a"]),
                "internal_code": f"CARRERA-{uuid.uuid4().hex[:8]}",
                "name": "Encargo para medir el orden",
            },
            headers=cab("admin_a"),
        )

    assert respuesta.status_code == 201, respuesta.text
    assert sonda.visto == [True], (
        "La respuesta salió antes de confirmar la transacción: quien reciba ese "
        "identificador y lo pida acto seguido puede no encontrarlo."
    )


class _SesionQueFallaAlConfirmar(Session):
    """Una sesión cuyo `COMMIT` falla, como falla el de verdad.

    No es un capricho: un `COMMIT` puede fallar en producción —interbloqueo,
    disco lleno, la conexión que se cae— y lo que se comprueba aquí es que ese
    fallo llega al cliente como un error, y no pegado al final de un `201` ya
    enviado.
    """

    def commit(self) -> None:
        raise OperationalError("COMMIT", {}, Exception("el servidor se fue"))


def test_si_falla_el_commit_el_cliente_no_recibe_un_201(
    motor_app: Engine,
    datos_base: dict[str, uuid.UUID],
    cab: Any,
) -> None:
    rota = sessionmaker(
        bind=motor_app,
        class_=_SesionQueFallaAlConfirmar,
        expire_on_commit=False,
        future=True,
    )
    app = montar_app(motor_app, rota)

    with TestClient(app, base_url="http://pruebas", raise_server_exceptions=False) as cliente:
        respuesta = cliente.post(
            f"{RUTA}/projects",
            json={
                "client_id": str(datos_base["cliente_a"]),
                "internal_code": f"FALLO-{uuid.uuid4().hex[:8]}",
                "name": "Encargo que no llega a confirmarse",
            },
            headers=cab("admin_a"),
        )

    assert respuesta.status_code >= 500, (
        f"Se respondió {respuesta.status_code} para una transacción que no llegó a "
        "confirmarse: el cliente se queda con un identificador de algo que se deshizo."
    )

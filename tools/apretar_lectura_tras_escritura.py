"""Crear y leer inmediatamente, sobre la misma conexión, N veces.

Es la reproducción del defecto de **lectura tras escritura**: la API confirmaba
la transacción después de enviar la respuesta, así que un `201` podía devolver un
identificador que la petición siguiente todavía no veía. Está arreglado
—`SesionDep` usa `scope="function"`—; esto queda como la forma de comprobarlo
contra un servidor de verdad, que es la única donde el síntoma se ve.

    python tools/apretar_lectura_tras_escritura.py [vueltas]

`[REQ]` Apúntelo **solo** a una base de demostración: crea un encargo por vuelta.

`[LIM]` No sirve de prueba automática y por eso no está en la suite: con un solo
proceso de `uvicorn` casi nunca falla —el bucle de eventos confirma antes de
atender la petición siguiente— y hacen falta varios procesos para que la lectura
caiga en otro y la ventana se note. Lo que sí se puede fijar sin azar es el
**orden**, y eso lo hace
`apps/api/tests/integration/test_confirmacion_antes_de_responder.py`.

Para ver el fallo tal como era, con el arreglo quitado:

    uvicorn tdd.main:app --port 8000 --workers 4
    python tools/apretar_lectura_tras_escritura.py 60
"""

from __future__ import annotations

import http.client
import json
import sys
import uuid
from typing import Any

CORREO = "admin@ejemplo.example"
CLAVE = "cubierta invertida 2026"


def main() -> int:
    vueltas = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    # `http.client` y no `requests`: reutiliza el socket, así que entre el último
    # byte del `201` y el primero del `GET` no hay ni apretón de manos ni
    # resolución de nombres. Es el peor caso realista, y es exactamente lo que
    # hace una pantalla que navega a la ficha nada más guardar.
    conexion = http.client.HTTPConnection("localhost", 8000)

    def pedir(metodo: str, ruta: str, cuerpo: Any = None, token: str | None = None):
        cabeceras = {}
        datos = None
        if token:
            cabeceras["Authorization"] = f"Bearer {token}"
        if cuerpo is not None:
            datos = json.dumps(cuerpo).encode()
            cabeceras["Content-Type"] = "application/json"
        conexion.request(metodo, f"/api/v1{ruta}", body=datos, headers=cabeceras)
        respuesta = conexion.getresponse()
        texto = respuesta.read().decode()
        return respuesta.status, (json.loads(texto) if texto else None)

    _, sesion = pedir("POST", "/auth/login", {"email": CORREO, "password": CLAVE})
    token = sesion["access_token"]
    _, clientes = pedir("GET", "/clients", token=token)
    cliente_id = clientes[0]["id"]

    perdidos = 0
    for i in range(vueltas):
        estado, creado = pedir(
            "POST",
            "/projects",
            {
                "client_id": cliente_id,
                "internal_code": f"AP-{uuid.uuid4().hex[:8]}",
                "name": f"Apretón {i}",
            },
            token=token,
        )
        if estado != 201:
            print(f"El alta falló con {estado}: {creado}", file=sys.stderr)
            return 2
        # Sin pausa: el siguiente byte que sale por el socket es el GET.
        leido, _ = pedir("GET", f"/projects/{creado['id']}", token=token)
        if leido == 404:
            perdidos += 1

    print(
        f"{perdidos} de {vueltas} identificadores no se veían al pedirlos acto seguido"
    )
    return 1 if perdidos else 0


if __name__ == "__main__":
    raise SystemExit(main())

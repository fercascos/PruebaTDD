"""El antivirus aplicado a lo que entra `[REQ]` §18.5.

Vive aparte de `antivirus.py` —que es el puerto y no sabe nada de HTTP— y
aparte de los tres routers que suben ficheros, para que la regla se escriba una
vez. Antes estaba solo en las fotografías, y **el hueco importante eran las
otras dos**: un PPTX o un PDF que llega de un cliente es un vector mucho más
probable que un JPEG.
"""

from __future__ import annotations

import json
import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.evidence import antivirus


def obtener_antivirus(request: Request) -> antivirus.Antivirus:
    """Lo aporta la aplicación. Por defecto es `SinAntivirus`, que **no analiza
    y lo dice**."""
    return request.app.state.antivirus  # type: ignore[no-any-return]


def rechazar_si_infectado(
    av: antivirus.Antivirus,
    datos: bytes,
    *,
    s: Session,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    nombre: str,
    entidad: str,
) -> antivirus.Resultado:
    """Analiza y corta si hay positivo. Devuelve el resultado si se puede seguir.

    Se llama **antes de escribir nada**, ni en el almacén ni en la base: un
    fichero rechazado no debe dejar ni objeto huérfano ni fila fantasma.

    El registro de auditoría se **confirma antes de lanzar**. La sesión hace
    `rollback` cuando la petición falla, así que sin ese `commit` el rastro de
    un intento de subir malware desaparecería junto con la petición que lo
    rechazó, que es justo el registro que alguien va a querer consultar.
    """
    resultado = av.analizar(datos)
    if resultado.veredicto is not antivirus.Veredicto.INFECTADO:
        return resultado

    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "after_data, severity) VALUES (:o, :u, 'UPLOAD_INFECTED', :e, "
            "CAST(:d AS jsonb), 'CRITICO')"
        ),
        {
            "o": str(organization_id),
            "u": str(actor_id),
            "e": entidad,
            "d": json.dumps({"firma": resultado.detalle, "nombre": nombre[:200]}),
        },
    )
    s.commit()
    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        f"El antivirus ha detectado una amenaza en el fichero ({resultado.detalle}). "
        f"No se ha subido.",
    )

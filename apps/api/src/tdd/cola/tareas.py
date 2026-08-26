"""Qué hace el worker con cada tipo de tarea.

Este módulo es el único que conoce a la vez la cola y el resto de la
aplicación. `worker.py` no importa nada de informes ni de correo a propósito:
si lo hiciera, probar la cola exigiría tener `python-pptx` instalado, y un
fallo al importar el generador dejaría al worker sin poder mandar un correo.

Cada manejador recibe `(sesion, tarea, recursos)` y **no devuelve nada**: que
salga bien es no levantar excepción. El bucle se encarga de marcar la tarea y
de reintentar.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.cola import Tarea, TareaPendiente
from tdd.cola import worker as w
from tdd.notificaciones.correo import Correo, Mensaje
from tdd.reporting import produccion


@dataclass(frozen=True, slots=True)
class Recursos:
    """Lo que las tareas necesitan y el worker no conoce."""

    almacen: Any
    correo: Correo


def enviar_correo(s: Session, tarea: TareaPendiente, recursos: Recursos) -> None:
    """`[REQ]` §10.2 · Saca el envío del hilo de la petición.

    Además de la latencia, esto cierra un agujero que el propio endpoint de
    recuperación declaraba: la respuesta tardaba distinto según existiera o no
    la cuenta, porque la rama que existe hablaba con el servidor SMTP. Ahora las
    dos ramas hacen lo mismo —escribir una fila o no escribirla— y la diferencia
    deja de ser observable desde fuera.
    """
    p = tarea.payload
    for campo in ("destinatario", "asunto", "cuerpo"):
        if not p.get(campo):
            raise ValueError(f"La tarea de correo no trae «{campo}»")
    recursos.correo.enviar(
        Mensaje(destinatario=p["destinatario"], asunto=p["asunto"], cuerpo=p["cuerpo"])
    )


def generar_informe(s: Session, tarea: TareaPendiente, recursos: Recursos) -> None:
    """Produce el PPTX y el XLSX de una versión que ya está congelada.

    Si falla, deja la versión en `ERROR` **en su propia transacción** antes de
    volver a levantar la excepción. Sin eso, el `rollback` del bucle se llevaría
    también la marca y la pantalla se quedaría esperando para siempre a un
    informe que nadie va a terminar.
    """
    version_id = uuid.UUID(str(tarea.payload["version_id"]))
    incluir_fotos = bool(tarea.payload.get("incluir_fotos", True))
    try:
        producido = produccion.producir(
            s, recursos.almacen, version_id, incluir_fotos=incluir_fotos
        )
        produccion.marcar_generado(s, version_id, producido)
        s.execute(
            text(
                "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
                "entity_id) VALUES (:o, :u, 'REPORT_GENERATED', 'report_version', :e)"
            ),
            {"o": str(tarea.organization_id), "u": str(tarea.created_by), "e": str(version_id)},
        )
    except Exception:
        s.rollback()
        produccion.marcar_error(s, version_id)
        s.commit()
        raise


def registrar_todas() -> None:
    """Enchufa los manejadores. La llaman el worker al arrancar y las pruebas."""
    w.registrar(Tarea.ENVIAR_CORREO, enviar_correo)  # type: ignore[arg-type]
    w.registrar(Tarea.GENERAR_INFORME, generar_informe)  # type: ignore[arg-type]

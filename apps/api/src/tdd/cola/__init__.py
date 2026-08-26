"""La cola de tareas: encolar, coger, terminar.

`[REQ]` §17 · Nada bloquea la interfaz más de 3 s. Lo que tarda —generar un
PPTX, hablar con un servidor SMTP— se apunta aquí y lo hace el worker.

**Encolar es parte de la transacción de quien encola.** `encolar()` recibe la
sesión de la petición y escribe en ella: si la petición falla después, la tarea
desaparece con el resto. Es la propiedad que un broker externo no da, y la
razón principal de que la cola viva en la base de datos.

`[REC]` El puerto está separado del adaptador por si algún día la carga
justifica Celery. Lo que habría que cambiar entonces es `ColaEnPostgres`, no
los endpoints ni las tareas: los primeros solo llaman a `encolar()` y las
segundas son funciones puras sobre su `payload`.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session


class Cola(StrEnum):
    """`[REQ]` E-10 · Colas separadas, para que una no retrase a la otra.

    Una tanda de informes no puede dejar esperando el correo de recuperación de
    contraseña de alguien que no puede entrar.
    """

    #: Informes: minutos de CPU y memoria.
    PESADA = "heavy"
    #: Correo y avisos: segundos, casi todo esperando a un tercero.
    LIGERA = "io"


class Tarea(StrEnum):
    """Qué hay que hacer. El worker traduce esto a una función."""

    GENERAR_INFORME = "GENERAR_INFORME"
    ENVIAR_CORREO = "ENVIAR_CORREO"


#: Qué cola le toca a cada tarea. Vive aquí y no en cada sitio que encola:
#: repartirlo por los endpoints haría que dos llamadas a lo mismo acabaran en
#: colas distintas según quién escribiera el código.
COLA_DE: dict[Tarea, Cola] = {
    Tarea.GENERAR_INFORME: Cola.PESADA,
    Tarea.ENVIAR_CORREO: Cola.LIGERA,
}

#: Espera antes de reintentar, por número de intento ya gastado. Crece para no
#: machacar un servicio que está caído: reintentar cada segundo contra un SMTP
#: apagado no lo arregla y llena la tabla de intentos inútiles.
ESPERAS: tuple[timedelta, ...] = (
    timedelta(seconds=30),
    timedelta(minutes=5),
    timedelta(minutes=30),
)


def espera_tras(intentos: int) -> timedelta:
    """Cuánto esperar tras `intentos` fallos. Función pura, se prueba sola."""
    if intentos <= 0:
        return ESPERAS[0]
    return ESPERAS[min(intentos, len(ESPERAS)) - 1]


@dataclass(frozen=True, slots=True)
class TareaPendiente:
    """Una tarea cogida de la cola, tal y como la ve el worker."""

    id: uuid.UUID
    organization_id: uuid.UUID
    kind: Tarea
    #: Quién la encargó. El worker trabaja **en su nombre**: aplica su contexto
    #: RLS y la auditoría que se genere lleva su firma, no la de un usuario
    #: «sistema» que no existe y del que nadie podría pedir cuentas.
    created_by: uuid.UUID
    payload: dict[str, Any] = field(default_factory=dict)
    attempts: int = 1
    max_attempts: int = 3

    @property
    def es_ultimo_intento(self) -> bool:
        return self.attempts >= self.max_attempts


class Encolador(Protocol):
    """Lo mínimo que la aplicación necesita de una cola."""

    def encolar(
        self,
        s: Session,
        *,
        kind: Tarea,
        organization_id: uuid.UUID,
        payload: dict[str, Any],
        created_by: uuid.UUID,
    ) -> uuid.UUID: ...


class ColaEnPostgres:
    """Adaptador sobre la tabla `job`. El único que hay hoy."""

    def encolar(
        self,
        s: Session,
        *,
        kind: Tarea,
        organization_id: uuid.UUID,
        payload: dict[str, Any],
        created_by: uuid.UUID,
    ) -> uuid.UUID:
        """Apunta la tarea **en la sesión que se le pasa**.

        No abre transacción propia ni hace `commit`: eso es justamente lo que
        la ata a la operación que la encarga. Si la petición revierte, la tarea
        revierte con ella.
        """
        return uuid.UUID(
            str(
                s.execute(
                    text(
                        "INSERT INTO job (organization_id, kind, queue, payload, created_by) "
                        "VALUES (:o, :k, :q, CAST(:p AS jsonb), :u) RETURNING id"
                    ),
                    {
                        "o": str(organization_id),
                        "k": kind.value,
                        "q": COLA_DE[kind].value,
                        "p": json.dumps(payload, ensure_ascii=False, default=str),
                        "u": str(created_by),
                    },
                ).scalar_one()
            )
        )

    # ── Lo que usa el worker ────────────────────────────────────────────────
    #
    # Pasa por las funciones `SECURITY DEFINER` del esquema y no por la tabla:
    # el worker tiene que ver las tareas de todas las organizaciones, y darle
    # BYPASSRLS al usuario de aplicación dejaría decorativas las políticas.

    def coger(self, s: Session, *, cola: Cola, worker: str) -> TareaPendiente | None:
        fila = (
            s.execute(
                text("SELECT * FROM job_coger(:c, :w)"),
                {"c": cola.value, "w": worker},
            )
            .mappings()
            .first()
        )
        if fila is None or fila["id"] is None:
            return None
        if fila["created_by"] is None:
            # No debería pasar: `encolar` lo exige. Si pasa, es una tarea
            # escrita a mano en la base, y hacerla sin saber en nombre de quién
            # dejaría auditoría sin firma.
            raise ValueError(f"La tarea {fila['id']} no dice quién la encargó")
        return TareaPendiente(
            id=uuid.UUID(str(fila["id"])),
            organization_id=uuid.UUID(str(fila["organization_id"])),
            kind=Tarea(fila["kind"]),
            created_by=uuid.UUID(str(fila["created_by"])),
            payload=dict(fila["payload"] or {}),
            attempts=int(fila["attempts"]),
            max_attempts=int(fila["max_attempts"]),
        )

    def hecha(self, s: Session, job_id: uuid.UUID) -> None:
        s.execute(text("SELECT job_hecha(:i)"), {"i": str(job_id)})

    def fallada(self, s: Session, job_id: uuid.UUID, *, error: str, espera: timedelta) -> None:
        s.execute(
            text("SELECT job_fallada(:i, :e, :w)"),
            {"i": str(job_id), "e": error[:2000], "w": espera},
        )

    def rescatar(self, s: Session, *, limite: timedelta) -> int:
        """Devuelve a la cola lo que un worker muerto dejó cogido."""
        return int(s.execute(text("SELECT job_rescatar(:l)"), {"l": limite}).scalar_one())


def encolar(
    s: Session,
    *,
    kind: Tarea,
    organization_id: uuid.UUID,
    payload: dict[str, Any],
    created_by: uuid.UUID,
) -> uuid.UUID:
    """Atajo para los endpoints, que no necesitan conocer el adaptador."""
    return ColaEnPostgres().encolar(
        s,
        kind=kind,
        organization_id=organization_id,
        payload=payload,
        created_by=created_by,
    )

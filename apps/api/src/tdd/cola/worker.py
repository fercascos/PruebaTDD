"""El proceso que vacía la cola.

Está escrito como **un paso que se puede llamar una vez**, no como un demonio
opaco. `una_vuelta()` coge una tarea, la hace y devuelve qué pasó; el bucle de
`servir()` no es más que llamarla en redondo. La razón es que así el worker se
prueba de verdad —con una base real y una tarea real— en vez de comprobar que
un hilo arranca.

Dos garantías que el bucle sostiene:

* **Una tarea que revienta no tumba el worker.** Se captura todo, se apunta el
  motivo en `last_error` y se reintenta con espera creciente. Un PPTX corrupto
  no puede dejar sin correo a quien no puede entrar.
* **El worker aplica el contexto RLS de la organización de la tarea** antes de
  tocar nada. Coger la tarea pasa por las funciones `SECURITY DEFINER`, pero el
  trabajo en sí queda dentro de las políticas como cualquier petición.
"""

from __future__ import annotations

import logging
import os
import socket
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from tdd.cola import Cola, ColaEnPostgres, Tarea, TareaPendiente, espera_tras
from tdd.core import metricas, observabilidad
from tdd.core.db import ContextoRLS, aplicar_contexto

log = logging.getLogger("tdd.worker")

#: Cuánto puede estar una tarea EN_CURSO antes de darla por abandonada. Tiene
#: que ser holgado: un informe con trescientas diapositivas tarda.
LIMITE_DE_RESCATE = timedelta(minutes=30)

#: Cuánto duerme el bucle cuando no hay nada que hacer. Con la cola en la base
#: no hay notificación push, así que se sondea; medio segundo es imperceptible
#: para quien espera un informe y no carga nada a PostgreSQL.
DESCANSO = 0.5


def nombre_de_este_worker() -> str:
    """Algo que identifique al proceso en `locked_by`.

    Sirve para lo único que se hace con ese campo: mirar qué worker se quedó
    con una tarea que nunca terminó.
    """
    return f"{socket.gethostname()}/{os.getpid()}"


@dataclass(frozen=True, slots=True)
class Resultado:
    """Qué pasó en una vuelta del bucle."""

    #: `None` cuando la cola estaba vacía.
    tarea: TareaPendiente | None = None
    ok: bool = False
    error: str | None = None

    @property
    def hubo_trabajo(self) -> bool:
        return self.tarea is not None


#: Qué función hace cada tipo de tarea. Se registra desde fuera para que este
#: módulo no dependa de los de informes ni de correo: si lo hiciera, importar
#: el worker arrastraría medio proyecto y las pruebas de la cola necesitarían
#: python-pptx.
Manejador = Callable[[Session, TareaPendiente, Any], None]
_MANEJADORES: dict[Tarea, Manejador] = {}


def registrar(kind: Tarea, manejador: Manejador) -> None:
    _MANEJADORES[kind] = manejador


def manejadores() -> dict[Tarea, Manejador]:
    return dict(_MANEJADORES)


class SinManejador(RuntimeError):
    """Llegó una tarea que nadie sabe hacer."""


def una_vuelta(
    s: Session,
    *,
    cola: Cola,
    recursos: Any,
    worker: str | None = None,
    adaptador: ColaEnPostgres | None = None,
) -> Resultado:
    """Coge una tarea, la hace y la cierra. Devuelve qué pasó.

    `recursos` es lo que las tareas necesitan y el worker no conoce —el almacén
    de objetos, el correo—. Va como un solo objeto para que añadir una
    dependencia nueva no cambie esta firma ni la de los manejadores.
    """
    cc = adaptador or ColaEnPostgres()
    tarea = cc.coger(s, cola=cola, worker=worker or nombre_de_este_worker())
    if tarea is None:
        return Resultado()

    # La tarea ya está EN_CURSO y eso tiene que quedar escrito aunque el
    # trabajo tarde: si no, otro worker la cogería otra vez.
    s.commit()

    # Se recupera la traza de la petición que la encargó. A partir de aquí todo
    # lo que se registre —incluido lo que escriban los manejadores— sale con el
    # mismo identificador que la petición original, aunque hayan pasado minutos
    # y estemos en otro proceso. Es la correlación entera del sistema.
    testigo = observabilidad.peticion_actual.set(tarea.request_id or f"tarea-{tarea.id.hex[:12]}")
    comienzo = time.perf_counter()

    try:
        manejador = _MANEJADORES.get(tarea.kind)
        if manejador is None:
            raise SinManejador(f"Nadie sabe hacer una tarea de tipo {tarea.kind}")

        # El trabajo va dentro de las políticas de su organización, como
        # cualquier petición. Coger la tarea es lo único que las salta.
        aplicar_contexto(
            s,
            ContextoRLS(
                organization_id=tarea.organization_id,
                user_id=tarea.created_by,
                can_manage_suggestions=False,
            ),
        )
        manejador(s, tarea, recursos)
        cc.hecha(s, tarea.id)
        s.commit()
        log.info(
            "Tarea %s (%s) hecha en %.1f s",
            tarea.id,
            tarea.kind,
            time.perf_counter() - comienzo,
            extra={"tarea": str(tarea.id), "tipo": str(tarea.kind), "resultado": "hecha"},
        )
        metricas.TAREAS.labels(tipo=str(tarea.kind), resultado="hecha").inc()
        return Resultado(tarea=tarea, ok=True)

    except Exception as exc:  # noqa: BLE001 — una tarea rota no tumba el worker
        # Se deshace lo que la tarea dejara a medias antes de anotar el fallo:
        # si no, el `job_fallada` se ejecutaría dentro de la misma transacción
        # envenenada y no se guardaría tampoco.
        s.rollback()
        motivo = f"{type(exc).__name__}: {exc}"
        # `exception` y no `warning`: sin la traza, un fallo en la generación de
        # un informe deja un mensaje de una línea y ninguna forma de saber en
        # qué diapositiva se rompió.
        log.exception(
            "Tarea %s (%s) falló (intento %s de %s)",
            tarea.id,
            tarea.kind,
            tarea.attempts,
            tarea.max_attempts,
            extra={
                "tarea": str(tarea.id),
                "tipo": str(tarea.kind),
                "resultado": "fallida" if tarea.es_ultimo_intento else "reintenta",
                "intento": tarea.attempts,
            },
        )
        cc.fallada(s, tarea.id, error=motivo, espera=espera_tras(tarea.attempts))
        s.commit()
        metricas.TAREAS.labels(
            tipo=str(tarea.kind),
            resultado="fallida" if tarea.es_ultimo_intento else "reintenta",
        ).inc()
        return Resultado(tarea=tarea, ok=False, error=motivo)

    finally:
        # Se devuelve el contexto a como estaba: el bucle del worker atiende una
        # tarea tras otra en el mismo hilo, y sin esto la traza de una se
        # quedaría pegada a la siguiente.
        observabilidad.peticion_actual.reset(testigo)


def vaciar(
    fabrica: Callable[[], Session],
    *,
    recursos: Any,
    colas: tuple[Cola, ...] = (Cola.PESADA, Cola.LIGERA),
    tope: int = 500,
) -> int:
    """Procesa lo que haya pendiente y termina. Devuelve cuántas tareas hizo.

    No es un apaño de pruebas: es el modo que hace falta para **vaciar la cola
    antes de un despliegue** y para ejecutar el worker desde un `cron` en vez de
    como servicio permanente.

    `tope` evita un bucle infinito si una tarea se reencola sola: sin él, un
    fallo que la devuelve a la cola con `run_after` en el pasado dejaría el
    proceso girando para siempre.
    """
    hechas = 0
    for cola in colas:
        for _ in range(tope):
            with fabrica() as s:
                resultado = una_vuelta(s, cola=cola, recursos=recursos)
            if not resultado.hubo_trabajo:
                break
            hechas += 1
    return hechas


def servir(
    fabrica: Callable[[], Session],
    *,
    cola: Cola,
    recursos: Any,
    parar: Callable[[], bool] = lambda: False,
    descanso: float = DESCANSO,
) -> int:
    """El bucle. Devuelve cuántas tareas procesó.

    `parar` permite terminarlo desde fuera —una señal, una prueba— sin dejar una
    tarea a medias: se comprueba entre vueltas, nunca dentro de una.
    """
    worker = nombre_de_este_worker()
    hechas = 0
    ultimo_rescate = 0.0

    while not parar():
        with fabrica() as s:
            # De vez en cuando se recogen las tareas de workers que murieron.
            # Cada minuto basta: no es una operación urgente y hacerla en cada
            # vuelta sería una escritura por cada sondeo.
            if time.monotonic() - ultimo_rescate > 60:
                recuperadas = ColaEnPostgres().rescatar(s, limite=LIMITE_DE_RESCATE)
                s.commit()
                if recuperadas:
                    log.info("Rescatadas %s tareas de workers que no terminaron", recuperadas)
                ultimo_rescate = time.monotonic()

            resultado = una_vuelta(s, cola=cola, recursos=recursos, worker=worker)

        if resultado.hubo_trabajo:
            hechas += 1
        else:
            time.sleep(descanso)

    return hechas


def _uuid_de(payload: dict[str, Any], clave: str) -> uuid.UUID:
    """Lee un identificador del `payload` diciendo qué falta si no está.

    El `payload` es JSON escrito por quien encoló: puede venir de una versión
    anterior de la aplicación. Un `KeyError` pelado en el registro no dice qué
    tarea ni qué campo.
    """
    valor = payload.get(clave)
    if valor is None:
        raise ValueError(f"La tarea no trae «{clave}» en su payload")
    return uuid.UUID(str(valor))

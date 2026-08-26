"""El worker como proceso.

    python -m tdd.cola --cola heavy       # informes, en bucle
    python -m tdd.cola --cola io          # correo, en bucle
    python -m tdd.cola --una-vez          # vacía las dos y termina

`[REC]` En producción se levantan **dos procesos**, uno por cola (E-10): así una
tanda de informes no deja esperando el correo de recuperación de contraseña de
alguien que no puede entrar. Escalar la cola pesada es levantar más copias de
ese proceso; no hace falta coordinarlos, de eso se encarga
`FOR UPDATE SKIP LOCKED`.

`--una-vez` es el modo para vaciar antes de un despliegue, o para ejecutarlo
desde un `cron` en instalaciones pequeñas en vez de como servicio permanente.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from types import FrameType

from tdd.cola import Cola
from tdd.cola import worker as w
from tdd.cola.tareas import Recursos, registrar_todas
from tdd.core.config import get_settings
from tdd.core.db import crear_fabrica_de_sesiones, crear_motor
from tdd.evidence import storage
from tdd.notificaciones import correo as correo_mod

log = logging.getLogger("tdd.worker")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tdd.cola", description="Worker de la cola de tareas")
    parser.add_argument(
        "--cola",
        choices=[c.value for c in Cola],
        default=Cola.LIGERA.value,
        help="Qué cola atender. Se levanta un proceso por cola.",
    )
    parser.add_argument(
        "--una-vez",
        action="store_true",
        help="Procesa lo pendiente de las dos colas y termina.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    if not settings.database_url:
        print("DATABASE_URL no está definida.", file=sys.stderr)
        return 2

    motor = crear_motor(str(settings.database_url))
    fabrica = crear_fabrica_de_sesiones(motor)
    recursos = Recursos(
        almacen=storage.construir(settings),
        correo=correo_mod.construir(
            host=settings.smtp_host,
            puerto=settings.smtp_port,
            remitente=settings.mail_from,
            usuario=settings.smtp_user,
            clave=settings.smtp_password,
        ),
    )
    registrar_todas()

    try:
        if args.una_vez:
            log.info("Procesadas %s tareas", w.vaciar(fabrica, recursos=recursos))
            return 0

        # Una señal no corta una tarea a medias: se pide parar y el bucle lo
        # comprueba entre vueltas. Matar el proceso en mitad de un informe
        # dejaría la tarea EN_CURSO hasta que `job_rescatar` la recogiera.
        parar = False

        def _pedir_parada(_sig: int, _marco: FrameType | None) -> None:
            nonlocal parar
            log.info("Señal recibida: se para al terminar la tarea en curso")
            parar = True

        signal.signal(signal.SIGTERM, _pedir_parada)
        signal.signal(signal.SIGINT, _pedir_parada)

        cola = Cola(args.cola)
        log.info("Worker atendiendo la cola %s", cola.value)
        hechas = w.servir(fabrica, cola=cola, recursos=recursos, parar=lambda: parar)
        log.info("Worker parado tras %s tareas", hechas)
        return 0
    finally:
        motor.dispose()


if __name__ == "__main__":  # pragma: no cover — punto de entrada
    raise SystemExit(main())

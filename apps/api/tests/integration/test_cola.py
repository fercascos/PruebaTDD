"""La cola de tareas y el worker `[REQ]` §17.

Lo que se prueba aquí es lo que hace que una cola sirva para algo. En orden de
importancia:

1. **Encolar es transaccional.** Si la operación que encarga la tarea revierte,
   la tarea no existe. Es la razón principal de que la cola viva en esta base y
   no en un broker aparte, así que si eso deja de cumplirse hay que enterarse.
2. **Una tarea que revienta no tumba el worker**, y se reintenta con espera
   creciente hasta agotar los intentos.
3. **Dos workers no cogen la misma tarea**, que es lo que sostiene
   `FOR UPDATE SKIP LOCKED`.
4. **Un worker que muere deja su tarea recuperable.** Sin eso, matar un proceso
   perdería en silencio el informe que tenía entre manos.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, text

from tdd.cola import Cola, ColaEnPostgres, Tarea, espera_tras
from tdd.cola import worker as w

pytestmark = pytest.mark.db


# ─────────────────────────────────────────────────────────────────────────────
#  La espera entre reintentos: función pura
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("intentos", "esperado"),
    [(0, 30), (1, 30), (2, 300), (3, 1800), (9, 1800)],
)
def test_la_espera_crece_y_luego_se_estanca(intentos: int, esperado: int) -> None:
    """Crece para no machacar un servicio caído, y deja de crecer para que el
    último intento no quede a horas de distancia."""
    assert espera_tras(intentos) == timedelta(seconds=esperado)


# ─────────────────────────────────────────────────────────────────────────────
#  Encolar
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sesion(motor_admin: Engine):  # type: ignore[no-untyped-def]
    """Sesión con la cola vacía.

    Se limpia **antes y después**: `coger` se lleva la tarea más antigua de la
    cola, así que una tarea que sobreviva de otra prueba hace que la siguiente
    trabaje sobre la fila equivocada. Costó cuatro fallos entenderlo.
    """
    from sqlalchemy.orm import sessionmaker

    fabrica = sessionmaker(bind=motor_admin, expire_on_commit=False, future=True)
    with fabrica() as s:
        s.execute(text("DELETE FROM job"))
        s.commit()
        yield s
        s.rollback()
        s.execute(text("DELETE FROM job"))
        s.commit()


@pytest.fixture
def quien(datos_base: dict[str, uuid.UUID]) -> dict[str, uuid.UUID]:
    return {"org": datos_base["org_a"], "usuario": datos_base["consultor_a"]}


def encolar(s: Any, quien: dict[str, uuid.UUID], **extra: Any) -> uuid.UUID:
    return ColaEnPostgres().encolar(
        s,
        kind=extra.pop("kind", Tarea.ENVIAR_CORREO),
        organization_id=quien["org"],
        payload=extra.pop("payload", {"a": "quien@sea.example"}),
        created_by=quien["usuario"],
    )


def test_una_tarea_encolada_queda_pendiente(sesion: Any, quien: dict[str, uuid.UUID]) -> None:
    job_id = encolar(sesion, quien)
    sesion.commit()
    fila = (
        sesion.execute(
            text("SELECT CAST(status AS text) AS status, queue, attempts FROM job WHERE id = :i"),
            {"i": str(job_id)},
        )
        .mappings()
        .one()
    )
    assert fila["status"] == "PENDIENTE"
    assert fila["queue"] == "io"
    assert fila["attempts"] == 0


def test_un_informe_va_a_la_cola_pesada(sesion: Any, quien: dict[str, uuid.UUID]) -> None:
    """`[REQ]` E-10 · Una tanda de informes no puede retrasar un correo."""
    job_id = encolar(sesion, quien, kind=Tarea.GENERAR_INFORME, payload={"version_id": "x"})
    sesion.commit()
    cola = sesion.execute(text("SELECT queue FROM job WHERE id = :i"), {"i": str(job_id)}).scalar()
    assert cola == "heavy"


def test_si_la_transaccion_revierte_la_tarea_no_existe(
    sesion: Any, quien: dict[str, uuid.UUID]
) -> None:
    """`[REQ]` La propiedad que justifica tener la cola en esta base.

    Con un broker aparte se puede encolar la generación de un informe cuya fila
    acaba revirtiendo, y el worker se encuentra trabajo sobre algo que no
    existe. Aquí no puede pasar.
    """
    job_id = encolar(sesion, quien)
    sesion.rollback()
    hay = sesion.execute(text("SELECT 1 FROM job WHERE id = :i"), {"i": str(job_id)}).first()
    assert hay is None


# ─────────────────────────────────────────────────────────────────────────────
#  Coger y repartir
# ─────────────────────────────────────────────────────────────────────────────


def test_coger_marca_la_tarea_y_cuenta_el_intento(sesion: Any, quien: dict[str, uuid.UUID]) -> None:
    encolar(sesion, quien)
    sesion.commit()
    tarea = ColaEnPostgres().coger(sesion, cola=Cola.LIGERA, worker="pruebas/1")
    assert tarea is not None
    assert tarea.attempts == 1
    assert tarea.created_by == quien["usuario"]
    estado = sesion.execute(
        text("SELECT CAST(status AS text), locked_by FROM job WHERE id = :i"),
        {"i": str(tarea.id)},
    ).one()
    assert estado[0] == "EN_CURSO"
    assert estado[1] == "pruebas/1"


def test_una_cola_vacia_devuelve_nada(sesion: Any) -> None:
    """`None`, no una excepción: que no haya trabajo es lo normal."""
    assert ColaEnPostgres().coger(sesion, cola=Cola.PESADA, worker="x") is None


def test_no_se_coge_una_tarea_cuya_hora_no_ha_llegado(
    sesion: Any, quien: dict[str, uuid.UUID]
) -> None:
    """`run_after` es lo que implementa la espera entre reintentos."""
    job_id = encolar(sesion, quien)
    sesion.execute(
        text("UPDATE job SET run_after = now() + INTERVAL '1 hour' WHERE id = :i"),
        {"i": str(job_id)},
    )
    sesion.commit()
    assert ColaEnPostgres().coger(sesion, cola=Cola.LIGERA, worker="x") is None


def test_dos_workers_no_cogen_la_misma_tarea(
    motor_admin: Engine, quien: dict[str, uuid.UUID]
) -> None:
    """`[REQ]` Lo que sostiene `FOR UPDATE SKIP LOCKED`.

    Se usan **dos conexiones de verdad**: con una sola sesión el bloqueo no se
    ejerce y la prueba pasaría sin probar nada.
    """
    from sqlalchemy.orm import sessionmaker

    fabrica = sessionmaker(bind=motor_admin, expire_on_commit=False, future=True)
    with fabrica() as limpieza:
        limpieza.execute(text("DELETE FROM job"))
        encolar(limpieza, quien)
        encolar(limpieza, quien)
        limpieza.commit()

    with fabrica() as uno, fabrica() as otro:
        a = ColaEnPostgres().coger(uno, cola=Cola.LIGERA, worker="uno")
        b = ColaEnPostgres().coger(otro, cola=Cola.LIGERA, worker="otro")
        assert a is not None and b is not None
        assert a.id != b.id
        uno.rollback()
        otro.rollback()


# ─────────────────────────────────────────────────────────────────────────────
#  Fallos, reintentos y rescate
# ─────────────────────────────────────────────────────────────────────────────


def test_un_fallo_devuelve_la_tarea_a_la_cola_con_espera(
    sesion: Any, quien: dict[str, uuid.UUID]
) -> None:
    encolar(sesion, quien)
    sesion.commit()
    tarea = ColaEnPostgres().coger(sesion, cola=Cola.LIGERA, worker="x")
    assert tarea is not None
    ColaEnPostgres().fallada(sesion, tarea.id, error="SMTP caído", espera=timedelta(minutes=5))
    sesion.commit()

    fila = (
        sesion.execute(
            text(
                "SELECT CAST(status AS text) AS status, last_error, "
                "run_after > now() AS espera FROM job WHERE id = :i"
            ),
            {"i": str(tarea.id)},
        )
        .mappings()
        .one()
    )
    assert fila["status"] == "PENDIENTE"
    assert fila["last_error"] == "SMTP caído"
    assert fila["espera"] is True


def test_agotados_los_intentos_la_tarea_queda_fallida(
    sesion: Any, quien: dict[str, uuid.UUID]
) -> None:
    job_id = encolar(sesion, quien)
    sesion.execute(text("UPDATE job SET max_attempts = 1 WHERE id = :i"), {"i": str(job_id)})
    sesion.commit()
    tarea = ColaEnPostgres().coger(sesion, cola=Cola.LIGERA, worker="x")
    assert tarea is not None and tarea.es_ultimo_intento
    ColaEnPostgres().fallada(sesion, tarea.id, error="no hubo manera", espera=timedelta(minutes=5))
    sesion.commit()
    fila = (
        sesion.execute(
            text("SELECT CAST(status AS text) AS status, finished_at FROM job WHERE id = :i"),
            {"i": str(job_id)},
        )
        .mappings()
        .one()
    )
    assert fila["status"] == "FALLIDA"
    assert fila["finished_at"] is not None


def test_una_tarea_de_un_worker_muerto_vuelve_a_la_cola(
    sesion: Any, quien: dict[str, uuid.UUID]
) -> None:
    """`[REQ]` Sin esto, matar un worker perdería en silencio el informe que
    tenía entre manos, y nadie relacionaría el fallo con la causa."""
    encolar(sesion, quien)
    sesion.commit()
    tarea = ColaEnPostgres().coger(sesion, cola=Cola.LIGERA, worker="el-que-murio")
    assert tarea is not None
    sesion.execute(
        text("UPDATE job SET locked_at = now() - INTERVAL '2 hours' WHERE id = :i"),
        {"i": str(tarea.id)},
    )
    sesion.commit()

    assert ColaEnPostgres().rescatar(sesion, limite=timedelta(minutes=30)) >= 1
    sesion.commit()
    estado = sesion.execute(
        text("SELECT CAST(status AS text) FROM job WHERE id = :i"), {"i": str(tarea.id)}
    ).scalar()
    assert estado == "PENDIENTE"


# ─────────────────────────────────────────────────────────────────────────────
#  El bucle del worker
# ─────────────────────────────────────────────────────────────────────────────


def test_una_vuelta_hace_la_tarea_y_la_cierra(sesion: Any, quien: dict[str, uuid.UUID]) -> None:
    hechas: list[uuid.UUID] = []
    w.registrar(Tarea.ENVIAR_CORREO, lambda s, t, r: hechas.append(t.id))
    try:
        job_id = encolar(sesion, quien)
        sesion.commit()
        resultado = w.una_vuelta(sesion, cola=Cola.LIGERA, recursos=None, worker="x")
        assert resultado.ok and resultado.tarea is not None
        assert job_id in hechas
        estado = sesion.execute(
            text("SELECT CAST(status AS text) FROM job WHERE id = :i"), {"i": str(job_id)}
        ).scalar()
        assert estado == "HECHA"
    finally:
        w._MANEJADORES.pop(Tarea.ENVIAR_CORREO, None)


def test_una_tarea_que_revienta_no_tumba_el_worker(
    sesion: Any, quien: dict[str, uuid.UUID]
) -> None:
    """`[REQ]` Un PPTX corrupto no puede dejar sin correo a quien no puede entrar."""

    def revienta(s: Any, t: Any, r: Any) -> None:
        raise RuntimeError("plantilla ilegible")

    w.registrar(Tarea.ENVIAR_CORREO, revienta)
    try:
        job_id = encolar(sesion, quien)
        sesion.commit()
        resultado = w.una_vuelta(sesion, cola=Cola.LIGERA, recursos=None, worker="x")
        assert resultado.ok is False
        assert "plantilla ilegible" in (resultado.error or "")
        fila = (
            sesion.execute(
                text("SELECT CAST(status AS text) AS status, last_error FROM job WHERE id = :i"),
                {"i": str(job_id)},
            )
            .mappings()
            .one()
        )
        assert fila["status"] == "PENDIENTE"
        assert "plantilla ilegible" in fila["last_error"]
    finally:
        w._MANEJADORES.pop(Tarea.ENVIAR_CORREO, None)


def test_una_tarea_sin_manejador_falla_diciendolo(sesion: Any, quien: dict[str, uuid.UUID]) -> None:
    w._MANEJADORES.pop(Tarea.ENVIAR_CORREO, None)
    job_id = encolar(sesion, quien)
    sesion.commit()
    resultado = w.una_vuelta(sesion, cola=Cola.LIGERA, recursos=None, worker="x")
    assert resultado.ok is False
    error = sesion.execute(
        text("SELECT last_error FROM job WHERE id = :i"), {"i": str(job_id)}
    ).scalar()
    assert "Nadie sabe hacer" in error


def test_sin_trabajo_la_vuelta_no_hace_nada(sesion: Any) -> None:
    resultado = w.una_vuelta(sesion, cola=Cola.PESADA, recursos=None, worker="x")
    assert resultado.hubo_trabajo is False
    assert resultado.ok is False


def test_el_worker_trabaja_con_el_contexto_de_la_organizacion_de_la_tarea(
    sesion: Any, quien: dict[str, uuid.UUID]
) -> None:
    """`[REQ]` Coger la tarea salta la RLS; el trabajo no.

    El manejador comprueba desde dentro que `org_actual()` es la organización
    de la tarea. Sin esto, una tarea podría escribir en la organización
    equivocada y las políticas no lo impedirían.
    """
    vistas: list[Any] = []

    def mira_el_contexto(s: Any, t: Any, r: Any) -> None:
        vistas.append(s.execute(text("SELECT org_actual()")).scalar())

    w.registrar(Tarea.ENVIAR_CORREO, mira_el_contexto)
    try:
        encolar(sesion, quien)
        sesion.commit()
        w.una_vuelta(sesion, cola=Cola.LIGERA, recursos=None, worker="x")
        assert vistas == [quien["org"]]
    finally:
        w._MANEJADORES.pop(Tarea.ENVIAR_CORREO, None)

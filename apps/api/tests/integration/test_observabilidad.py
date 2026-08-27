"""Que el sistema se pueda mirar por dentro.

El caso que estas pruebas fijan, con nombres: **Marta** pide un informe a las
11:04 y a las 11:09 le llega roto. Alguien tiene que poder responder «qué
pasó», y para eso hacen falta tres cosas que hasta ahora no había:

  1. que la petición de Marta lleve un identificador y se lo devuelva,
  2. que ese identificador **llegue al worker** que generó el informe cinco
     minutos después, en otro proceso,
  3. y que un `500` deje algo escrito. Esto último es lo más grave de lo que
     había: el manejador de errores prometía en su propia documentación que «el
     detalle técnico va al log» y **descartaba la excepción entera**. Un error
     en producción no dejaba absolutamente nada.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import pytest
from conftest import montar_app
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from tdd.core import observabilidad
from tdd.core.observabilidad import CABECERA, FormatoJson

pytestmark = pytest.mark.db

RUTA = "/api/v1"


def test_cada_respuesta_lleva_su_identificador(cliente: TestClient, cab: Any) -> None:
    respuesta = cliente.get(f"{RUTA}/catalogs/zones", headers=cab("consultor_a"))
    assert respuesta.status_code == 200
    traza = respuesta.headers.get(CABECERA)
    assert traza and len(traza) >= 8, "Sin identificador no hay nada que buscar en el registro"


def test_se_respeta_el_identificador_que_venga_de_fuera(cliente: TestClient, cab: Any) -> None:
    """Si el balanceador ya puso uno, se conserva: si no, la traza se parte."""
    mio = "trazadelbalanceador0123"
    respuesta = cliente.get(f"{RUTA}/catalogs/zones", headers={**cab("consultor_a"), CABECERA: mio})
    assert respuesta.headers.get(CABECERA) == mio


@pytest.mark.parametrize(
    "sucio",
    [
        "corto",  # menos de 8
        "con espacios dentro",
        "salto\nde-linea-inyectado",  # `isascii()` lo dejaba pasar
        "x" * 200,  # sin cota, alguien nos llena el disco
    ],
)
def test_un_identificador_sucio_se_descarta(cliente: TestClient, cab: Any, sucio: str) -> None:
    """`[REQ]` Ese texto acaba escrito en un registro.

    Aceptar un salto de línea es dejar que cualquiera inyecte líneas falsas en
    el log desde una cabecera HTTP. Se genera uno propio y se ignora el suyo.
    """
    respuesta = cliente.get(
        f"{RUTA}/catalogs/zones", headers={**cab("consultor_a"), CABECERA: sucio}
    )
    devuelto = respuesta.headers.get(CABECERA, "")
    assert devuelto != sucio
    assert "\n" not in devuelto and " " not in devuelto


def test_un_500_deja_rastro_y_dice_su_identificador(
    motor_app: Engine,
    fabrica: sessionmaker[Session],
    cab: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """El fallo que más importaba: un `500` no registraba nada.

    Se monta una aplicación aparte con una ruta que revienta a propósito. No se
    usa la compartida porque añadirle una ruta que falla la dejaría contaminada
    para el resto de la suite.
    """
    app = montar_app(motor_app, fabrica)

    @app.get("/api/v1/_revienta")
    def _revienta() -> None:
        raise RuntimeError("algo muy concreto que debe salir en el registro")

    with (
        caplog.at_level(logging.ERROR),
        TestClient(app, base_url="http://pruebas", raise_server_exceptions=False) as c,
    ):
        respuesta = c.get(f"{RUTA}/_revienta", headers=cab("admin_a"))

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()

    # 1 · El cliente se lleva algo que citar.
    assert cuerpo["request_id"], "Sin esto, «me ha dado un error» no se puede buscar"
    assert respuesta.headers.get(CABECERA) == cuerpo["request_id"]

    # 2 · Y no se lleva nada de dentro. `[REQ]` §13.
    plano = json.dumps(cuerpo)
    assert "algo muy concreto" not in plano
    assert "RuntimeError" not in plano and "Traceback" not in plano

    # 3 · Pero el registro sí lo tiene, con la traza completa.
    registros = [r for r in caplog.records if r.name == "tdd.error"]
    assert registros, "El 500 no registró nada: es exactamente el fallo que había"
    assert registros[0].exc_info is not None, "Sin `exc_info` no hay traza que mirar"
    assert "algo muy concreto" in caplog.text


def test_la_traza_de_la_peticion_llega_al_worker(
    cliente: TestClient, motor_admin: Engine, datos_base: dict[str, uuid.UUID], cab: Any
) -> None:
    """La correlación entera: petición → fila de `job` → worker.

    Se comprueba sobre la tabla y no sobre el registro del worker porque es el
    eslabón que puede romperse en silencio: si `encolar` deja de guardar la
    traza, todo lo demás sigue funcionando y nadie se entera hasta que hace
    falta investigar algo.
    """
    mio = "peticionquepidioelinforme01"
    respuesta = cliente.post(
        f"{RUTA}/auth/password/forgot",
        json={"email": "admin@alfa.example"},
        headers={CABECERA: mio},
    )
    assert respuesta.status_code == 202

    with motor_admin.begin() as conn:
        fila = conn.execute(
            text(
                "SELECT id, request_id FROM job WHERE kind = 'ENVIAR_CORREO' "
                "ORDER BY created_at DESC LIMIT 1"
            )
        ).first()
        assert fila is not None
        # Se retira la tarea antes de comprobar nada. La cola es estado
        # compartido por toda la suite: dejarla pendiente hacía que la prueba
        # de recuperación de contraseña —que vacía el worker— se llevara dos
        # correos en vez de uno y fallara. La prueba pasaba sola y fallaba en
        # la suite, que es la peor forma de fallar.
        conn.execute(text("DELETE FROM job WHERE id = :i"), {"i": fila[0]})

    assert fila[1] == mio, (
        "La tarea no recuerda de qué petición vino: un informe que falla no se "
        "puede atar a la petición que lo pidió."
    )


def test_el_registro_en_json_lleva_la_traza_y_lo_que_se_le_ponga() -> None:
    """El formato de `staging` y `production`: una línea, JSON, con contexto."""
    testigo = observabilidad.peticion_actual.set("abc12345")
    try:
        registro = logging.LogRecord(
            name="tdd.prueba",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="informe %s generado",
            args=("A-17",),
            exc_info=None,
        )
        registro.tarea = "3f2a"  # type: ignore[attr-defined]
        salida = json.loads(FormatoJson().format(registro))
    finally:
        observabilidad.peticion_actual.reset(testigo)

    assert salida["mensaje"] == "informe A-17 generado"
    assert salida["peticion"] == "abc12345"
    assert salida["tarea"] == "3f2a"
    assert salida["nivel"] == "INFO"
    # Una línea: si llevara saltos, cada registro se partiría en varios al
    # indexarlo y dejaría de poder buscarse.
    assert "\n" not in FormatoJson().format(registro)


def test_ready_dice_que_falta_cuando_falta(
    motor_app: Engine, fabrica: sessionmaker[Session]
) -> None:
    """`503` con **qué** está roto, no un `503` mudo.

    Un `503` sin detalle obliga a entrar en la máquina para saber cuál de las
    dos piezas es, que es justo lo que no se quiere estar haciendo cuando algo
    se ha caído.
    """
    app = montar_app(motor_app, fabrica)

    class AlmacenRoto:
        def existe(self, clave: str) -> bool:
            raise ConnectionError("el almacén no contesta")

    app.state.object_store = AlmacenRoto()

    with TestClient(app, base_url="http://pruebas", raise_server_exceptions=False) as c:
        respuesta = c.get("/ready")

    assert respuesta.status_code == 503
    piezas = respuesta.json()["piezas"]
    assert piezas["base"] == "ok"
    assert piezas["almacen"].startswith("error: ConnectionError")


def test_ready_y_health_no_son_lo_mismo(cliente: TestClient) -> None:
    """`/health` no mira la base a propósito.

    Si PostgreSQL se cae, el proceso de la API no está roto y reiniciarlo no
    arregla nada: un orquestador que use `/health` como sonda de vida entraría
    en un bucle de reinicios que solo empeora la situación.
    """
    assert cliente.get("/health").json() == {"status": "ok"}
    listo = cliente.get("/ready").json()
    assert listo["status"] == "ok"
    assert set(listo["piezas"]) == {"base", "almacen"}


def test_las_metricas_cuentan_peticiones_y_miden_la_cola(cliente: TestClient) -> None:
    """Lo que se mira en un panel."""
    cliente.get("/health")
    cuerpo = cliente.get("/metrics").text

    assert "tdd_peticiones_total" in cuerpo
    assert "tdd_peticion_segundos" in cuerpo
    # La profundidad de la cola es la métrica que más avisa de esta aplicación:
    # si el worker muere, la interfaz sigue respondiendo rápido y lo único que
    # se ve es que los informes «tardan».
    assert 'tdd_cola_pendientes{cola="heavy"}' in cuerpo
    assert 'tdd_cola_pendientes{cola="io"}' in cuerpo


def test_la_ruta_de_las_metricas_no_lleva_identificadores(cliente: TestClient, cab: Any) -> None:
    """`[REC]` La etiqueta es la ruta con plantilla, no la concreta.

    Con el identificador dentro, cada encargo crearía su propia serie temporal
    y en un mes habría cien mil. Es la forma más habitual de reventar un
    Prometheus.
    """
    proyecto = cliente.get(f"{RUTA}/projects", headers=cab("consultor_a")).json()[0]["id"]
    cliente.get(f"{RUTA}/projects/{proyecto}", headers=cab("consultor_a"))

    cuerpo = cliente.get("/metrics").text
    assert proyecto not in cuerpo, "Un identificador en una etiqueta multiplica las series"
    # Y la ruta **entera**, con su prefijo. `scope["route"].path` viene relativa
    # al router incluido y salía `/projects/{project_id}` a secas: una etiqueta
    # que no coincide con ninguna URL real no sirve para buscar nada.
    assert 'ruta="/api/v1/projects/{project_id}"' in cuerpo, cuerpo[:400]


def test_un_error_de_usuario_no_se_registra_como_error(
    motor_app: Engine, fabrica: sessionmaker[Session], cab: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """Un `404` no es un fallo del servidor y no debe ensuciar el registro.

    Si cada permiso denegado apareciera como error, el registro de errores
    dejaría de servir para lo único que sirve: mirar lo que está roto.
    """
    app = montar_app(motor_app, fabrica)

    @app.get("/api/v1/_no_existe_para_ti")
    def _cuatrocientos_cuatro() -> None:
        raise HTTPException(404, "no existe")

    with (
        caplog.at_level(logging.ERROR),
        TestClient(app, base_url="http://pruebas", raise_server_exceptions=False) as c,
    ):
        assert c.get(f"{RUTA}/_no_existe_para_ti", headers=cab("admin_a")).status_code == 404

    assert not [r for r in caplog.records if r.name == "tdd.error"]

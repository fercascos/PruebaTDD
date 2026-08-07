"""Antivirus `[REQ]` §18.5.

**Qué prueba esto y qué no.** No hay ClamAV en este entorno y no se puede
descargar, así que el adaptador se prueba contra un `clamd` **de mentira**: un
servidor que habla el protocolo `INSTREAM` de verdad —lee el verbo, los
prefijos de longitud de cada trozo y el trozo final vacío— y responde lo que
respondería el real.

Eso verifica lo que suele fallar de un cliente de protocolo binario: el
troceado, el orden de bytes de las longitudes y la lectura de la respuesta.
**No** verifica que ClamAV detecte nada, que es cosa de su base de firmas.

Lo que sí se prueba a fondo, porque es una decisión de diseño y no de
integración: que **nada devuelva LIMPIO sin haber analizado**.
"""

from __future__ import annotations

import socket
import threading

import pytest

from tdd.evidence.antivirus import (
    ClamAvPorSocket,
    Resultado,
    SinAntivirus,
    Veredicto,
    construir,
)

#: La cadena de prueba EICAR, partida para que ningún antivirus la marque en
#: el propio repositorio. No es malware: es el patrón que la industria acordó
#: para probar que un antivirus está vivo.
EICAR = r"X5O!P%@AP[4\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


class ClamdDeMentira:
    """Habla `INSTREAM` de verdad; el veredicto lo decide una función.

    Lee el protocolo en lugar de tragarse los bytes: si el cliente se equivoca
    con el prefijo de longitud o no manda el trozo final, esto se cuelga o
    reconstruye mal el fichero, y la prueba lo nota.
    """

    def __init__(self, responder) -> None:
        self.responder = responder
        self.recibido = b""
        self._servidor = socket.socket()
        self._servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._servidor.bind(("127.0.0.1", 0))
        self._servidor.listen(1)
        self.puerto = self._servidor.getsockname()[1]
        self._hilo = threading.Thread(target=self._atender, daemon=True)
        self._hilo.start()

    def _leer_exacto(self, conexion, n: int) -> bytes:
        datos = b""
        while len(datos) < n:
            trozo = conexion.recv(n - len(datos))
            if not trozo:
                break
            datos += trozo
        return datos

    def _atender(self) -> None:
        conexion, _ = self._servidor.accept()
        with conexion:
            verbo = self._leer_exacto(conexion, len(b"zINSTREAM\0"))
            if verbo != b"zINSTREAM\0":
                conexion.sendall(b"UNKNOWN COMMAND\0")
                return
            while True:
                cabecera = self._leer_exacto(conexion, 4)
                if len(cabecera) < 4:
                    return
                tamano = int.from_bytes(cabecera, "big")
                if tamano == 0:
                    break
                self.recibido += self._leer_exacto(conexion, tamano)
            conexion.sendall(self.responder(self.recibido).encode() + b"\0")

    def cerrar(self) -> None:
        self._servidor.close()


@pytest.fixture
def clamd():
    creados = []

    def crear(responder):
        s = ClamdDeMentira(responder)
        creados.append(s)
        return s

    yield crear
    for s in creados:
        s.cerrar()


# ─────────────────────────────────────────────────────────────────────────────
#  El protocolo
# ─────────────────────────────────────────────────────────────────────────────


def test_un_fichero_limpio_se_reconoce(clamd) -> None:
    servidor = clamd(lambda _: "stream: OK")
    r = ClamAvPorSocket("127.0.0.1", servidor.puerto).analizar(b"contenido inofensivo")
    assert r.veredicto is Veredicto.LIMPIO
    assert r.se_puede_publicar is True


def test_el_fichero_llega_entero_y_sin_alterar(clamd) -> None:
    """El troceado y los prefijos de longitud son donde falla un cliente de
    protocolo binario, y el fallo es silencioso: el antivirus analizaría un
    fichero distinto del que se subió y diría que está limpio."""
    servidor = clamd(lambda _: "stream: OK")
    # Más de un trozo: 32 KiB es el tamaño, así que 80 KiB son tres.
    original = bytes(range(256)) * 320
    ClamAvPorSocket("127.0.0.1", servidor.puerto).analizar(original)
    assert servidor.recibido == original


def test_un_fichero_vacio_tambien_se_anuncia(clamd) -> None:
    """Sin el trozo final de longitud cero, `clamd` se queda esperando y la
    subida se cuelga hasta el `timeout`."""
    servidor = clamd(lambda _: "stream: OK")
    r = ClamAvPorSocket("127.0.0.1", servidor.puerto).analizar(b"")
    assert r.veredicto is Veredicto.LIMPIO
    assert servidor.recibido == b""


def test_un_positivo_trae_el_nombre_de_la_firma(clamd) -> None:
    servidor = clamd(lambda _: "stream: Eicar-Test-Signature FOUND")
    r = ClamAvPorSocket("127.0.0.1", servidor.puerto).analizar(EICAR.encode())
    assert r.veredicto is Veredicto.INFECTADO
    assert r.detalle == "Eicar-Test-Signature"
    assert r.se_puede_publicar is False


# ─────────────────────────────────────────────────────────────────────────────
#  Nada devuelve LIMPIO sin haber analizado
# ─────────────────────────────────────────────────────────────────────────────


def test_sin_antivirus_el_resultado_es_no_analizado_y_no_limpio() -> None:
    """Tratar «no lo he mirado» como «está bien» es peor que no tener
    antivirus, porque además da confianza."""
    r = SinAntivirus().analizar(b"lo que sea")
    assert r.veredicto is Veredicto.NO_ANALIZADO
    assert r.veredicto is not Veredicto.LIMPIO
    assert "sin analizar" in r.detalle
    # No bloquea la subida: bloquearla dejaría la aplicación inservible sin un
    # ClamAV al lado. Lo que hace es no callarse.
    assert r.se_puede_publicar is True


def test_si_el_antivirus_no_responde_no_se_da_por_limpio() -> None:
    """Es el modo de fallo que convierte una caída del servicio en una tanda de
    subidas sin analizar que nadie vuelve a mirar."""
    # Puerto cerrado: nadie escucha.
    with socket.socket() as libre:
        libre.bind(("127.0.0.1", 0))
        puerto = libre.getsockname()[1]
    r = ClamAvPorSocket("127.0.0.1", puerto, timeout=1.0).analizar(b"x")
    assert r.veredicto is Veredicto.NO_ANALIZADO
    assert "No se ha podido contactar" in r.detalle


def test_una_respuesta_que_no_se_entiende_tampoco_es_limpia(clamd) -> None:
    servidor = clamd(lambda _: "stream: size limit exceeded ERROR")
    r = ClamAvPorSocket("127.0.0.1", servidor.puerto).analizar(b"x")
    assert r.veredicto is Veredicto.NO_ANALIZADO
    assert "no reconocida" in r.detalle


@pytest.mark.parametrize(
    "respuesta",
    ["stream: OK", "stream: Win.Test.EICAR_HDB-1 FOUND", "cualquier cosa"],
)
def test_el_veredicto_siempre_lleva_explicacion(clamd, respuesta: str) -> None:
    """Un veredicto sin motivo no se puede auditar seis meses después."""
    servidor = clamd(lambda _: respuesta)
    r = ClamAvPorSocket("127.0.0.1", servidor.puerto).analizar(b"x")
    assert r.detalle.strip()


# ─────────────────────────────────────────────────────────────────────────────
#  Configuración
# ─────────────────────────────────────────────────────────────────────────────


def test_por_defecto_no_hay_antivirus_y_se_sabe() -> None:
    assert isinstance(construir(habilitado=False, host="", puerto=3310), SinAntivirus)


def test_habilitarlo_sin_servidor_no_arranca_a_medias() -> None:
    """Peor que no habilitarlo: quien despliega creería que está protegido."""
    with pytest.raises(ValueError, match="CLAMAV_HOST"):
        construir(habilitado=True, host="", puerto=3310)


def test_habilitado_con_host_da_el_adaptador_real() -> None:
    av = construir(habilitado=True, host="clamav.interno", puerto=3310)
    assert isinstance(av, ClamAvPorSocket)
    assert (av.host, av.puerto) == ("clamav.interno", 3310)


def test_el_resultado_es_inmutable() -> None:
    """Se arrastra hasta el informe: que nadie pueda cambiarlo por el camino."""
    r = Resultado(Veredicto.INFECTADO, "firma")
    with pytest.raises(AttributeError):
        r.veredicto = Veredicto.LIMPIO  # type: ignore[misc]

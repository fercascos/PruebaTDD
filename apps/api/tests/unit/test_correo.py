"""Correo saliente `[REQ]` §10.2.

`[LIM]` No hay ningún servidor SMTP en este entorno, así que el adaptador se
prueba contra uno **de mentira** que habla SMTP: eso verifica la conversación y
el mensaje construido, no que su proveedor lo acepte.
"""

from __future__ import annotations

import asyncio
import ssl
import threading
from email import message_from_bytes
from email.policy import default as politica_moderna
from pathlib import Path

import pytest

from tdd.notificaciones.correo import (
    CorreoALog,
    CorreoEnMemoria,
    CorreoPorSmtp,
    Mensaje,
    construir,
)

MENSAJE = Mensaje(
    destinatario="ana@ejemplo.example",
    asunto="Restablecer su contraseña",
    cuerpo="Abra este enlace:\n\n  https://tdd.ejemplo.example/restablecer#TOKEN\n",
)


# ── El adaptador por defecto ────────────────────────────────────────────────


def test_sin_smtp_no_se_envia_nada_y_se_registra(caplog: pytest.LogCaptureFixture) -> None:
    """Una aplicación recién desplegada sin SMTP no debe fallar al pedir una
    recuperación —dejaría a la gente fuera sin saber por qué— ni fingir que ha
    enviado un correo que nadie va a recibir."""
    with caplog.at_level("WARNING", logger="tdd.correo"):
        CorreoALog().enviar(MENSAJE)
    assert "NO enviado" in caplog.text
    assert "SMTP_HOST" in caplog.text


def test_el_log_no_lleva_el_enlace(caplog: pytest.LogCaptureFixture) -> None:
    """`[REQ]` Un enlace de recuperación en el log del servidor está al alcance
    de cualquiera que lea los logs, que suele ser más gente que la que puede
    leer el buzón del destinatario."""
    with caplog.at_level("WARNING", logger="tdd.correo"):
        CorreoALog().enviar(MENSAJE)
    assert "TOKEN" not in caplog.text
    assert "restablecer#" not in caplog.text


def test_sin_host_o_sin_remitente_se_cae_al_de_log() -> None:
    """Se exige el remitente además del servidor: un mensaje sin `From` válido
    lo tira el primer filtro por el que pase, y el usuario esperaría un correo
    que sí se «envió»."""
    assert isinstance(construir(host="", puerto=587, remitente="a@b.example"), CorreoALog)
    assert isinstance(construir(host="smtp.interno", puerto=587, remitente=""), CorreoALog)
    assert isinstance(
        construir(host="smtp.interno", puerto=587, remitente="a@b.example"), CorreoPorSmtp
    )


# ── El adaptador SMTP, contra un servidor de mentira ────────────────────────


class SmtpDeMentira:
    """Un servidor SMTP mínimo. Guarda lo recibido para poder mirarlo."""

    def __init__(self, *, con_starttls: bool) -> None:
        self.con_starttls = con_starttls
        self.recibido = b""
        self.de = ""
        self.para: list[str] = []
        import socket

        self._s = socket.socket()
        self._s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._s.bind(("127.0.0.1", 0))
        self._s.listen(1)
        self.puerto = self._s.getsockname()[1]
        threading.Thread(target=self._atender, daemon=True).start()

    def _atender(self) -> None:
        conexion, _ = self._s.accept()
        with conexion, conexion.makefile("rwb") as f:
            f.write(b"220 mentira ESMTP\r\n")
            f.flush()
            while True:
                linea = f.readline()
                if not linea:
                    return
                orden = linea.decode("utf-8", "replace").strip()
                arriba = orden.upper()
                if arriba.startswith("EHLO"):
                    extras = b"250-STARTTLS\r\n" if self.con_starttls else b""
                    f.write(b"250-mentira\r\n" + extras + b"250 SIZE 10240000\r\n")
                elif arriba.startswith("STARTTLS"):
                    # No se completa el TLS: al cliente le basta con que la
                    # extensión NO esté para negarse, que es lo que se prueba.
                    f.write(b"454 no disponible\r\n")
                elif arriba.startswith("MAIL FROM"):
                    self.de = orden
                    f.write(b"250 ok\r\n")
                elif arriba.startswith("RCPT TO"):
                    self.para.append(orden)
                    f.write(b"250 ok\r\n")
                elif arriba == "DATA":
                    f.write(b"354 adelante\r\n")
                    f.flush()
                    while True:
                        trozo = f.readline()
                        if trozo in (b".\r\n", b""):
                            break
                        self.recibido += trozo
                    f.write(b"250 aceptado\r\n")
                elif arriba == "QUIT":
                    f.write(b"221 adios\r\n")
                    f.flush()
                    return
                else:
                    f.write(b"250 ok\r\n")
                f.flush()

    def cerrar(self) -> None:
        self._s.close()


def test_sin_starttls_no_se_envia_en_claro() -> None:
    """`[REQ]` Degradar a texto plano mandaría el enlace de recuperación por la
    red sin cifrar, y eso es peor que no enviarlo."""
    servidor = SmtpDeMentira(con_starttls=False)
    try:
        adaptador = CorreoPorSmtp(
            host="127.0.0.1", puerto=servidor.puerto, remitente="tdd@ejemplo.example", timeout=5
        )
        with pytest.raises(RuntimeError, match="STARTTLS"):
            adaptador.enviar(MENSAJE)
        # Y no ha llegado nada: no es que fallara después de mandarlo.
        assert servidor.recibido == b""
    finally:
        servidor.cerrar()


def test_el_mensaje_se_construye_con_lo_que_debe() -> None:
    """El `From`, el `To`, el asunto y la marca que evita que un contestador
    automático conteste y genere un bucle con el buzón del sistema."""
    adaptador = CorreoPorSmtp(
        host="no-se-usa", puerto=587, remitente="Due diligence <tdd@ejemplo.example>"
    )
    correo = adaptador._construir(MENSAJE)  # noqa: SLF001
    # `policy=default` da un `EmailMessage`, con `get_content()`; sin ella se
    # obtiene el `Message` antiguo, que no lo tiene.
    crudo = message_from_bytes(bytes(correo), policy=politica_moderna)

    assert crudo["To"] == "ana@ejemplo.example"
    assert crudo["From"] == "Due diligence <tdd@ejemplo.example>"
    # Descodificado es lo que ve quien recibe el correo: la eñe sobrevive.
    assert str(crudo["Subject"]) == "Restablecer su contraseña"
    # Y por el cable va codificado en RFC 2047, porque una cabecera SMTP es
    # ASCII. Una aplicación en español manda eñes y acentos en cada asunto: si
    # esto se rompiera, los correos llegarían con el asunto ilegible.
    assert b"=?utf-8?" in bytes(correo)
    assert crudo["Auto-Submitted"] == "auto-generated"
    assert "restablecer#TOKEN" in crudo.get_content()


def test_el_de_memoria_guarda_lo_enviado() -> None:
    c = CorreoEnMemoria()
    c.enviar(MENSAJE)
    assert c.enviados == [MENSAJE]


def test_no_se_usa_asyncio_por_error() -> None:
    """El adaptador es síncrono a propósito: se llama desde un endpoint
    síncrono, que FastAPI ya ejecuta en su pool de hilos."""
    assert not asyncio.iscoroutinefunction(CorreoPorSmtp.enviar)


def test_el_certificado_del_servidor_se_verifica() -> None:
    """`[REQ]` Cifrar sin autenticar protege de la mitad del problema.

    `smtplib.starttls()` **sin contexto** usa uno de biblioteca con
    `check_hostname=False` y `verify_mode=CERT_NONE`: quien esté en medio
    presenta cualquier certificado, el cliente lo acepta, y el enlace de
    recuperación viaja cifrado hacia el atacante. Era lo que hacía este
    adaptador.

    Se comprueba sobre el contexto y no negociando TLS de verdad porque lo que
    puede volver a romperse es exactamente esto: que alguien llame a
    `starttls()` sin pasarle un contexto.
    """
    contexto = CorreoPorSmtp(
        host="smtp.interno", puerto=587, remitente="tdd@ejemplo.example"
    )._contexto()  # noqa: SLF001
    assert contexto.verify_mode == ssl.CERT_REQUIRED
    assert contexto.check_hostname is True


def test_una_ca_propia_se_anade_a_las_del_sistema(tmp_path: Path) -> None:
    """Un relé corporativo con su propia CA se declara, no se deja de verificar."""
    # Un PEM que no es un certificado: basta con que `load_verify_locations`
    # lo intente para saber que la ruta se usa.
    ca = tmp_path / "ca.crt"
    ca.write_text("-----BEGIN CERTIFICATE-----\nno soy un certificado\n-----END CERTIFICATE-----\n")
    adaptador = CorreoPorSmtp(
        host="smtp.interno", puerto=587, remitente="tdd@ejemplo.example", ca_fichero=str(ca)
    )
    with pytest.raises(ssl.SSLError):
        adaptador._contexto()  # noqa: SLF001

    # Y sin CA declarada, el contexto se construye sin tocar nada del sistema.
    assert CorreoPorSmtp(
        host="smtp.interno", puerto=587, remitente="tdd@ejemplo.example"
    )._contexto()  # noqa: SLF001

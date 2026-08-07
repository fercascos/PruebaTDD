"""Correo saliente · **puerto y adaptadores**.

`[LIM]` **El adaptador SMTP no se ha probado contra un servidor real.** Usa
`smtplib` de la biblioteca estándar con STARTTLS, y está probado contra un
servidor de mentira que habla SMTP, lo que verifica la conversación y el
mensaje construido. No verifica que su proveedor lo acepte.

El adaptador **por defecto no envía nada**: escribe en el log. Es deliberado.
Una aplicación recién desplegada sin SMTP configurado no debe fallar al pedir
una recuperación —dejaría a la gente sin poder entrar y sin saber por qué— ni
fingir que ha enviado un correo que nadie va a recibir.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

log = logging.getLogger("tdd.correo")


@dataclass(frozen=True, slots=True)
class Mensaje:
    destinatario: str
    asunto: str
    cuerpo: str


class Correo(Protocol):
    def enviar(self, mensaje: Mensaje) -> None: ...


class CorreoALog:
    """El adaptador por defecto. **No envía: registra que no ha enviado.**

    `[REQ]` No se registra el cuerpo. Un enlace de recuperación en el log del
    servidor es un enlace de recuperación al alcance de cualquiera que lea los
    logs, que suele ser más gente que la que puede leer el buzón del
    destinatario.
    """

    def enviar(self, mensaje: Mensaje) -> None:
        log.warning(
            "Correo NO enviado (sin SMTP configurado). Destinatario=%s asunto=%r. "
            "Configure SMTP_HOST y MAIL_FROM para enviarlo de verdad.",
            mensaje.destinatario,
            mensaje.asunto,
        )


class CorreoEnMemoria:
    """Para pruebas: guarda lo enviado y no toca la red."""

    def __init__(self) -> None:
        self.enviados: list[Mensaje] = []

    def enviar(self, mensaje: Mensaje) -> None:
        self.enviados.append(mensaje)


class CorreoPorSmtp:
    """`[LIM]` Sin probar contra un servidor SMTP real.

    STARTTLS y no SMTPS por el puerto 465 porque es lo que aceptan casi todos
    los relés corporativos en el 587. Si el servidor no ofrece STARTTLS, **no
    se envía en claro**: se lanza. Degradar a texto plano mandaría el enlace de
    recuperación por la red sin cifrar, y eso es peor que no enviarlo.
    """

    def __init__(
        self,
        *,
        host: str,
        puerto: int,
        remitente: str,
        usuario: str = "",
        clave: str = "",
        timeout: float = 20.0,
    ) -> None:
        self.host = host
        self.puerto = puerto
        self.remitente = remitente
        self.usuario = usuario
        self.clave = clave
        self.timeout = timeout

    def _construir(self, mensaje: Mensaje) -> EmailMessage:
        correo = EmailMessage()
        correo["From"] = self.remitente
        correo["To"] = mensaje.destinatario
        correo["Subject"] = mensaje.asunto
        # `Auto-Submitted` evita que un contestador automático responda al
        # correo y genere un bucle con el buzón del sistema.
        correo["Auto-Submitted"] = "auto-generated"
        correo.set_content(mensaje.cuerpo)
        return correo

    def enviar(self, mensaje: Mensaje) -> None:
        with smtplib.SMTP(self.host, self.puerto, timeout=self.timeout) as servidor:
            servidor.ehlo()
            if not servidor.has_extn("starttls"):
                raise RuntimeError(
                    f"El servidor SMTP {self.host}:{self.puerto} no ofrece STARTTLS. "
                    f"No se envía en claro: el mensaje lleva un enlace de recuperación."
                )
            servidor.starttls()
            servidor.ehlo()
            if self.usuario:
                servidor.login(self.usuario, self.clave)
            servidor.send_message(self._construir(mensaje))


def construir(
    *, host: str, puerto: int, remitente: str, usuario: str = "", clave: str = ""
) -> Correo:
    """El adaptador que toca. Sin `SMTP_HOST` o sin remitente, no se envía nada.

    Se exige el remitente además del servidor: un mensaje sin `From` válido lo
    tira el primer filtro antimalware por el que pase, y el usuario se quedaría
    esperando un correo que sí se «envió».
    """
    if not host or not remitente:
        return CorreoALog()
    return CorreoPorSmtp(
        host=host, puerto=puerto, remitente=remitente, usuario=usuario, clave=clave
    )

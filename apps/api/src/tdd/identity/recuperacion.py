"""Recuperación de contraseña `[REQ]` §10.2 · **lógica pura**.

Ni base de datos ni HTTP ni correo: se prueba sin levantar nada.

Cuatro reglas, y las cuatro son de seguridad:

**No se puede averiguar si una cuenta existe.** El endpoint responde lo mismo
siempre. Un formulario de «he olvidado mi contraseña» que distingue entre
«enviado» y «ese correo no existe» es un comprobador de cuentas gratuito.

**Se guarda la huella, nunca el token.** Igual que las sesiones. Si la tabla se
filtra, lo que se lleva el atacante son hashes, no enlaces vivos.

**Un solo uso y treinta minutos.** Un enlace reenviado, dejado en el historial
del navegador o guardado en el buzón deja de valer.

**Restablecer cierra todas las sesiones.** Si alguien recupera su contraseña es
porque sospecha o porque ha perdido el acceso; dejar vivas las sesiones abiertas
convertiría el cambio en un gesto vacío y mantendría dentro a quien entró.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

#: 32 bytes de entropía: 256 bits. Sobra para que no haya nada que adivinar, y
#: cabe en una URL sin partirse.
BYTES_DEL_TOKEN = 32

#: `[REQ]` §10.2 · Treinta minutos. Suficiente para leer el correo, corto para
#: que un buzón comprometido más tarde ya no sirva.
MINUTOS_DE_VALIDEZ = 30

#: Cuántas peticiones se admiten por usuario en la ventana. Es el freno contra
#: usar la recuperación para llenarle el buzón a alguien: a partir de aquí se
#: sigue respondiendo lo mismo, pero no se manda otro correo.
MAXIMO_POR_VENTANA = 3
MINUTOS_DE_VENTANA = 60

#: `[REQ]` La respuesta es SIEMPRE esta, exista o no la cuenta.
RESPUESTA_UNICA = (
    "Si esa dirección corresponde a una cuenta, le hemos enviado un enlace para "
    "restablecer la contraseña. Caduca en 30 minutos y solo se puede usar una vez."
)


class MotivoDeRechazo(StrEnum):
    NO_EXISTE = "NO_EXISTE"
    CADUCADO = "CADUCADO"
    YA_USADO = "YA_USADO"
    CUENTA_INACTIVA = "CUENTA_INACTIVA"


#: Qué se le dice a quien presenta un token que no sirve.
#:
#: Aquí **sí** se distingue, y no contradice la regla de no revelar cuentas:
#: para llegar hasta aquí hay que tener el token, que solo tiene quien recibió
#: el correo. Decir «el enlace ha caducado» en vez de «no válido» evita que
#: alguien pruebe tres veces creyendo que se equivocó al copiarlo.
EXPLICACION = {
    MotivoDeRechazo.NO_EXISTE: (
        "El enlace no es válido. Puede que se haya copiado incompleto: pida uno nuevo."
    ),
    MotivoDeRechazo.CADUCADO: (
        "El enlace ha caducado. Los enlaces duran 30 minutos: pida uno nuevo."
    ),
    MotivoDeRechazo.YA_USADO: (
        "Este enlace ya se ha usado. Cada enlace sirve una sola vez: pida uno nuevo."
    ),
    MotivoDeRechazo.CUENTA_INACTIVA: (
        "La cuenta está desactivada. Póngase en contacto con un administrador de su organización."
    ),
}


class TokenRechazado(Exception):  # noqa: N818 — el dominio está en español
    def __init__(self, motivo: MotivoDeRechazo) -> None:
        self.motivo = motivo
        super().__init__(EXPLICACION[motivo])


@dataclass(frozen=True, slots=True)
class TokenDeRecuperacion:
    """El token en claro y su huella. **La huella es lo único que se guarda.**"""

    valor: str
    huella: str
    expira_el: datetime


def generar(*, ahora: datetime, minutos: int = MINUTOS_DE_VALIDEZ) -> TokenDeRecuperacion:
    valor = secrets.token_urlsafe(BYTES_DEL_TOKEN)
    return TokenDeRecuperacion(
        valor=valor, huella=huella_de(valor), expira_el=ahora + timedelta(minutes=minutos)
    )


def huella_de(token: str) -> str:
    """SHA-256, sin sal y sin coste, igual que en las sesiones.

    El token ya son 256 bits aleatorios: no hay diccionario que aplicar, y sí
    hace falta poder buscarlo por igualdad en un índice.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class TokenGuardado:
    expira_el: datetime | None
    usado_el: datetime | None
    cuenta_activa: bool


def comprobar(guardado: TokenGuardado | None, *, ahora: datetime) -> None:
    """O pasa o lanza. El orden importa.

    «Ya usado» se comprueba **antes** que «caducado» porque es más informativo:
    a quien pulsó dos veces el mismo enlace le sirve más saber que ya lo gastó
    que enterarse de que además han pasado treinta minutos.
    """
    if guardado is None:
        raise TokenRechazado(MotivoDeRechazo.NO_EXISTE)
    if guardado.usado_el is not None:
        raise TokenRechazado(MotivoDeRechazo.YA_USADO)
    if guardado.expira_el is None or guardado.expira_el <= ahora:
        raise TokenRechazado(MotivoDeRechazo.CADUCADO)
    if not guardado.cuenta_activa:
        # Se comprueba también aquí y no solo al pedirlo: entre la petición y el
        # uso puede haber media hora, y en ese rato pueden haber dado de baja a
        # la persona.
        raise TokenRechazado(MotivoDeRechazo.CUENTA_INACTIVA)


def enlace(base: str, token: str) -> str:
    """La URL que va en el correo.

    El token viaja en el **fragmento**, detrás de `#`, y no en la cadena de
    consulta: el fragmento no se manda al servidor, así que no acaba en los
    registros de acceso del proxy ni en la cabecera `Referer` si la página
    carga algo de fuera. Es un detalle pequeño y evita la fuga más tonta.
    """
    return f"{base.rstrip('/')}/restablecer#{token}"


def ip_valida(valor: str | None) -> str:
    """La IP si lo es, cadena vacía si no. La columna es `inet` y no admite otra cosa.

    Lo que llega en `request.client.host` no siempre es una dirección: el
    cliente de pruebas pone «testclient», y en producción lo pone el proxy de
    delante, que puede estar mal configurado. Guardar una petición de
    recuperación no puede fallar porque la cabecera venga rara.
    """
    import ipaddress  # noqa: PLC0415

    try:
        return str(ipaddress.ip_address((valor or "").strip()))
    except ValueError:
        return ""


def se_debe_enviar(peticiones_en_la_ventana: int) -> bool:
    """Si se ha pasado del tope, no se manda otro correo.

    La respuesta al usuario **no cambia**: sigue siendo la misma frase. Cambiar
    la respuesta al llegar al tope volvería a delatar qué cuentas existen.
    """
    return peticiones_en_la_ventana < MAXIMO_POR_VENTANA

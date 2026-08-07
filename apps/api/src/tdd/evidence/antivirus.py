"""Análisis antivirus de lo que se sube · **puerto y adaptadores**.

`[REQ]` §18.5 · «ClamAV en contenedor propio, antes de que el archivo sea
accesible. Positivo ⇒ `CUARENTENA` + alerta.»

Tres cosas que conviene tener claras leyendo esto:

**El adaptador de ClamAV no se ha probado contra un ClamAV de verdad.** Habla
el protocolo `INSTREAM` de `clamd`, y está probado contra un servidor de
mentira que responde ese protocolo —lo que verifica el troceado, los prefijos
de longitud y el análisis de la respuesta, que es donde están los fallos—, pero
**no** contra el demonio real con una base de firmas. `[LIM]`

**Sin antivirus configurado no se dice que el fichero esté limpio.** El
resultado es `NO_ANALIZADO`, que es distinto de `LIMPIO`, y viaja hasta el
informe. Un sistema que trata «no lo he mirado» como «está bien» es peor que
uno sin antivirus, porque además da confianza.

**Un positivo no borra el objeto.** docs/10 §15.6 lo pide así: el fichero se
conserva para poder analizarlo. Lo que se hace es no dejar descargarlo.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Veredicto(StrEnum):
    LIMPIO = "LIMPIO"
    INFECTADO = "INFECTADO"
    #: No hay antivirus configurado, o no se pudo hablar con él. **No es
    #: «limpio»**, y la diferencia se arrastra hasta el informe.
    NO_ANALIZADO = "NO_ANALIZADO"


@dataclass(frozen=True, slots=True)
class Resultado:
    veredicto: Veredicto
    #: Nombre de la firma cuando hay positivo, o el motivo de no haber
    #: analizado. Nunca vacío: un veredicto sin explicación no se puede
    #: auditar.
    detalle: str

    @property
    def se_puede_publicar(self) -> bool:
        return self.veredicto is not Veredicto.INFECTADO


class Antivirus(Protocol):
    def analizar(self, datos: bytes) -> Resultado: ...


class SinAntivirus:
    """El adaptador por defecto. **No analiza y lo dice.**

    Es deliberado que exista y que sea el valor por defecto: la alternativa
    —arrancar sin antivirus fingiendo que hay uno— es la que produce sistemas
    que nadie sabe que están desprotegidos.
    """

    MOTIVO = (
        "No hay ningún antivirus configurado: el fichero se ha aceptado sin analizar. "
        "Configure ANTIVIRUS_ENABLED y CLAMAV_HOST para activarlo."
    )

    def analizar(self, datos: bytes) -> Resultado:  # noqa: ARG002
        return Resultado(Veredicto.NO_ANALIZADO, self.MOTIVO)


#: Tamaño de cada trozo del `INSTREAM`. `clamd` impone un máximo por trozo
#: (`StreamMaxLength`), y 32 KiB va holgado por debajo de cualquier valor
#: razonable de ese ajuste.
TROZO = 32 * 1024


class ClamAvPorSocket:
    """Adaptador sobre `clamd` hablando `INSTREAM` por TCP.

    `[LIM]` **Sin probar contra un ClamAV real.** Ver el encabezado del módulo.

    Se usa `INSTREAM` y no `SCAN` a propósito: `SCAN` le pasa una **ruta** al
    demonio, lo que obliga a compartir un volumen entre la aplicación y el
    contenedor del antivirus y a que los dos vean el mismo sistema de ficheros.
    `INSTREAM` manda los bytes por el socket y no comparte nada.

    El protocolo, para quien lo lea sin tenerlo delante:

        > zINSTREAM\\0
        > <4 bytes big-endian con el tamaño><trozo>   (repetido)
        > <4 bytes a cero>                            (fin)
        < stream: OK\\0            |  stream: Eicar-Test-Signature FOUND\\0
    """

    def __init__(self, host: str, puerto: int = 3310, *, timeout: float = 30.0) -> None:
        self.host = host
        self.puerto = puerto
        self.timeout = timeout

    def analizar(self, datos: bytes) -> Resultado:
        try:
            respuesta = self._instream(datos)
        except (OSError, TimeoutError) as exc:
            # `[REQ]` Que el antivirus no conteste **no puede** devolver LIMPIO.
            # Es el modo de fallo que convierte una caída del servicio en una
            # subida sin analizar que nadie vuelve a mirar.
            return Resultado(
                Veredicto.NO_ANALIZADO,
                f"No se ha podido contactar con el antivirus en {self.host}:{self.puerto}: {exc}",
            )
        return self._interpretar(respuesta)

    def _instream(self, datos: bytes) -> str:
        with socket.create_connection((self.host, self.puerto), timeout=self.timeout) as s:
            s.settimeout(self.timeout)
            s.sendall(b"zINSTREAM\0")
            for i in range(0, len(datos), TROZO):
                trozo = datos[i : i + TROZO]
                s.sendall(len(trozo).to_bytes(4, "big") + trozo)
            # Un fichero de cero bytes también se anuncia: el trozo final vacío
            # es lo que le dice a `clamd` que ya está todo.
            s.sendall((0).to_bytes(4, "big"))

            partes = []
            while True:
                trozo = s.recv(4096)
                if not trozo:
                    break
                partes.append(trozo)
                if b"\0" in trozo:
                    break
        return b"".join(partes).rstrip(b"\0").decode("utf-8", "replace").strip()

    @staticmethod
    def _interpretar(respuesta: str) -> Resultado:
        """`stream: OK` · `stream: X FOUND` · `... ERROR`.

        Lo que no se reconoce **no es limpio**: si un día `clamd` contesta algo
        nuevo, el fichero se queda sin analizar y se dice, en vez de darlo por
        bueno por no haber sabido leer la respuesta.
        """
        if respuesta.endswith("OK"):
            return Resultado(Veredicto.LIMPIO, "Analizado por ClamAV: sin amenazas")
        if respuesta.endswith("FOUND"):
            firma = respuesta.removeprefix("stream:").removesuffix("FOUND").strip()
            return Resultado(Veredicto.INFECTADO, firma or "amenaza sin identificar")
        return Resultado(
            Veredicto.NO_ANALIZADO,
            f"Respuesta no reconocida del antivirus: «{respuesta}»",
        )


def construir(*, habilitado: bool, host: str, puerto: int, timeout: float = 30.0) -> Antivirus:
    """El adaptador que toca según la configuración.

    Habilitarlo **sin host** no arranca a medias: sería peor que no habilitarlo,
    porque quien despliega creería que está protegido.
    """
    if not habilitado:
        return SinAntivirus()
    if not host:
        raise ValueError(
            "ANTIVIRUS_ENABLED está activo pero CLAMAV_HOST está vacío. "
            "Con el antivirus habilitado y sin servidor, cada fichero quedaría "
            "sin analizar creyendo que se analiza."
        )
    return ClamAvPorSocket(host, puerto, timeout=timeout)

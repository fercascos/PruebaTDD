"""El puerto de revisión documental: qué se le pide a un proveedor de IA.

`[REQ]` El proveedor **está sin elegir**. Esta capa existe para que esa
decisión —que es legal antes que técnica— no bloquee el resto del módulo ni
obligue a rehacerlo cuando se tome.

Lo que el puerto fija, y que ningún proveedor puede saltarse:

* **Toda observación viaja con su evidencia.** `Observacion.evidencia` y
  `Observacion.pagina` no son adorno: son lo que permite a la persona que
  confirma ir al documento y comprobarlo. Un veredicto sin respaldo es un acto
  de fe, y en una TDD eso no vale.
* **El dictamen dice quién lo produjo y si es simulado.** Una revisión de
  mentira no puede pasar por una de verdad ni en la base ni en la pantalla.
* **El puerto no decide nada.** Devuelve observaciones; quien las convierte en
  propuestas, y quien las acepta, está en `servicio.py` y en la pantalla.

`[REC]` Cuando se elija proveedor, el adaptador se escribe **aquí al lado** y
no se toca nada más. Si el elegido fuera la API de Anthropic, dos cosas de su
contrato encajan directamente con este puerto y conviene aprovecharlas:

1. Los PDF se envían nativos como bloque `document`, sin extraer texto antes.
   Extraerlo con una librería perdería la maquetación, que es justo lo que
   hace falta para juzgar si un plano está cortado o una firma falta.
2. Con `citations` activadas, la respuesta trae `cited_text` y un
   `page_location` con el número de página. Eso alimenta `evidencia` y
   `pagina` sin que el adaptador tenga que adivinarlos.

   `[LIM]` Las citas son **incompatibles** con `output_config.format`: no se
   pueden pedir citas y salida estructurada por el mismo camino. La forma de
   tener las dos es declarar una herramienta con `strict` y dejar las citas en
   el documento. Está anotado aquí para que quien escriba el adaptador no
   descubra el choque a base de recibir un 400.

Nada de lo anterior está implementado ni probado. Es una nota de diseño, no
una afirmación sobre código que exista.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Protocol


class Veredicto(StrEnum):
    """Coincide con el tipo `doc_finding_verdict` de la base."""

    CONFORME = "CONFORME"
    NO_CONFORME = "NO_CONFORME"
    FALTA = "FALTA"
    #: El proveedor no ha podido pronunciarse. Es un resultado legítimo y
    #: preferible a un veredicto inventado: obliga a que lo mire una persona.
    DUDOSO = "DUDOSO"


class RevisionNoDisponible(RuntimeError):
    """No hay proveedor utilizable, o el que hay no admite este documento."""


@dataclass(frozen=True, slots=True)
class Documento:
    """El documento tal y como se le entrega al proveedor.

    Se pasa el **binario**, no un texto ya extraído: la maquetación es parte de
    lo que hay que juzgar. Un anexo que falta o un escaneo cortado no se ven en
    el texto plano.
    """

    nombre: str
    mime_type: str
    contenido: bytes
    sha256: str
    #: El título de la línea de la checklist a la que se subió, si la hay. Es
    #: lo que da sentido a la comprobación de correspondencia: sin saber qué se
    #: pedía, «¿es el documento correcto?» no tiene respuesta.
    solicitado: str | None = None
    categoria: str | None = None


@dataclass(frozen=True, slots=True)
class Comprobacion:
    """Un criterio de revisión, tal y como está en `doc_check_type`.

    `descripcion` sale de la base y viaja al proveedor. No es documentación
    interna: es parte de la instrucción, y por eso se audita como dato.
    """

    codigo: str
    nombre: str
    descripcion: str


@dataclass(frozen=True, slots=True)
class Observacion:
    """Lo que el proveedor dice haber encontrado sobre un criterio."""

    comprobacion: str
    veredicto: Veredicto
    resumen: str
    #: Lo que dice haber leído, literal. `None` cuando el veredicto no se apoya
    #: en un fragmento concreto (una página en negro no tiene texto que citar).
    evidencia: str | None = None
    #: 1-indexada, como la enseña cualquier visor.
    pagina: int | None = None
    #: `[REC]` Entre 0 y 1, o `None`. Un proveedor que no sepa estimarla debe
    #: dejarla vacía: un número inventado es peor que ninguno, porque quien
    #: revisa lo leería como una medida.
    confianza: float | None = None


@dataclass(frozen=True, slots=True)
class Dictamen:
    """El resultado completo de revisar un documento."""

    observaciones: tuple[Observacion, ...]
    proveedor: str
    modelo: str | None = None
    #: Mientras no haya proveedor elegido esto es siempre `True`, y la
    #: aplicación lo enseña. Que una revisión simulada pudiera confundirse con
    #: una real sería el peor fallo posible de este módulo.
    simulado: bool = True


class Revisor(Protocol):
    """Lo que tiene que saber hacer un proveedor para encajar aquí."""

    @property
    def nombre(self) -> str:
        """Identificador corto que se guarda en `doc_review.provider`."""
        ...

    def revisar(
        self,
        documento: Documento,
        comprobaciones: Sequence[Comprobacion],
        *,
        fecha_encargo: date | None = None,
    ) -> Dictamen:
        """Revisa el documento contra los criterios y devuelve sus hallazgos.

        `fecha_encargo` es la referencia contra la que se juzga la vigencia: un
        certificado caducado el mes pasado es no conforme hoy, pero era válido
        cuando se emitió el informe del año pasado.

        Levanta `RevisionNoDisponible` si no puede hacerlo. **No** devuelve un
        dictamen vacío para disimular un fallo: un documento sin observaciones
        significa «lo he mirado y está bien», que es una afirmación distinta.
        """
        ...

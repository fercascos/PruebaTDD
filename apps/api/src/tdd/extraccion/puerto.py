"""El contrato: qué se le pide a un extractor, y qué puede aportar.

Está separado de cualquier extractor concreto a propósito. Añadir el lector de
planes de autoprotección no puede obligar a tocar el de la memoria técnica, y
elegir un proveedor de IA para clasificar prosa no puede obligar a tocar
ninguno de los dos.

**Lo que el puerto fija, y ningún extractor puede saltarse:**

* **Todo lo que sale es propuesta.** No hay ninguna ruta desde aquí al activo
  ni al CAPEX. La escritura la hace otro, después de que una persona acepte.
* **Todo viaja con su procedencia.** Documento, sección y el texto literal del
  que salió. Es lo que permite a quien valida ir al PDF y comprobarlo, y lo que
  permite enseñar dos cifras en conflicto diciendo de dónde viene cada una.
* **El extractor declara si es simulado.** Uno de mentira no puede pasar por
  uno de verdad ni en la base ni en la pantalla. Es la misma regla que la
  revisión documental y que la clasificación.
* **Un extractor no decide nada.** No elige entre dos valores, no descarta el
  peor y no marca nada como validado.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class Procedencia:
    """De dónde salió un dato. Sin esto, una propuesta no vale nada.

    `evidencia` es el fragmento literal del documento. Que sea literal importa:
    un resumen escrito por la máquina de lo que la máquina creyó leer no sirve
    para comprobar si la máquina se equivocó.
    """

    doc_type: str
    document_id: uuid.UUID | None = None
    #: El epígrafe del que salió: «MD.2 Descripción del proyecto».
    seccion: str | None = None
    evidencia: str | None = None


@dataclass(frozen=True, slots=True)
class CampoPropuesto:
    """Un campo del activo que un documento propone rellenar."""

    campo: str
    #: Como texto. El tipo lo pone el destino al aceptarlo: aquí no se sabe si
    #: `8.134` acabará en un `NUMERIC` o en un `VARCHAR`, y convertirlo antes de
    #: tiempo obligaría al extractor a conocer el esquema del activo.
    valor: str
    procedencia: Procedencia


@dataclass(frozen=True, slots=True)
class PlantaPropuesta:
    label: str
    level: int | None = None
    usable_area_sqm: Decimal | None = None
    built_area_sqm: Decimal | None = None
    procedencia: Procedencia | None = None


@dataclass(frozen=True, slots=True)
class ObjetoPropuesto:
    """Un objeto del CAPEX que el documento menciona.

    `capex_chapter_code` es el capítulo (nivel 2) al que se **propone**, no al
    que pertenece: quien lo escribe puede equivocarse, y por eso viaja con la
    evidencia al lado.
    """

    capex_chapter_code: str
    nombre: str
    cantidad: Decimal | None = None
    unidad: str | None = None
    procedencia: Procedencia | None = None


@dataclass
class Aportacion:
    """Lo que un documento aporta al expediente. Todo propuesto, nada escrito.

    Un extractor rellena **solo lo que su tipo de documento trae**. Una memoria
    técnica da campos, plantas y objetos; un plan de autoprotección dará equipos
    y limitaciones y ningún campo de superficie. Las listas vacías son normales
    y no son un fallo.
    """

    doc_type: str
    #: Quién lo produjo: `memoria-tecnica-v1`, y mañana el nombre del proveedor.
    extractor: str
    #: `[REQ]` Sin valor por omisión permisivo. Un extractor que se olvide de
    #: declararlo no compila, en vez de pasar por bueno.
    es_simulada: bool

    campos: list[CampoPropuesto] = field(default_factory=list)
    plantas: list[PlantaPropuesta] = field(default_factory=list)
    objetos: list[ObjetoPropuesto] = field(default_factory=list)

    #: Etiquetas del documento que el extractor leyó y no supo encajar. Se
    #: declaran en vez de descartarse: es como se descubre el sinónimo que
    #: falta, y sin ellas «no venía el dato» y «no lo supe leer» se confunden.
    desconocidos: dict[str, str] = field(default_factory=dict)
    #: Lo que quien valida tiene que mirar a mano.
    avisos: list[str] = field(default_factory=list)

    def vacia(self) -> bool:
        return not (self.campos or self.plantas or self.objetos)


class Extractor(Protocol):
    """Un lector de un tipo de documento.

    `soporta` es una tupla de `doc_type` y no uno solo porque un mismo lector
    puede servir para tipos emparentados —una memoria de proyecto y una memoria
    de reforma comparten estructura— sin duplicar el registro.
    """

    # De solo lectura: un extractor es inmutable. Declararlos como atributos
    # sueltos obligaría a que fueran escribibles, y entonces un `dataclass`
    # congelado —que es lo que son— no cumpliría el contrato.
    @property
    def nombre(self) -> str: ...  # pragma: no cover - es un Protocol

    @property
    def soporta(self) -> tuple[str, ...]: ...  # pragma: no cover - es un Protocol

    def leer(
        self, contenido: bytes, procedencia: Procedencia
    ) -> Aportacion:  # pragma: no cover - es un Protocol
        """Lee el documento. **No escribe en ningún sitio.**

        `procedencia` llega con el documento y el tipo ya puestos; el extractor
        la completa con la sección y la evidencia de cada cosa que proponga.
        """
        ...


class SinExtractor(LookupError):
    """No hay lector para ese tipo de documento.

    Es un caso normal y no un fallo: la mayoría de los documentos de un encargo
    —una licencia, un certificado— no se extraen. Se distingue con su propia
    excepción para que quien llama pueda decir «este tipo todavía no se lee» en
    vez de un error genérico que parece una avería.
    """


_REGISTRO: dict[str, Extractor] = {}


def registrar(extractor: Extractor) -> None:
    """Da de alta un extractor para los tipos que declara soportar."""
    for tipo in extractor.soporta:
        anterior = _REGISTRO.get(tipo)
        if anterior is not None and anterior.nombre != extractor.nombre:
            raise ValueError(
                f"Ya hay un extractor para «{tipo}»: {anterior.nombre}. Dos lectores "
                "del mismo tipo dejarían el resultado a merced del orden de importación."
            )
        _REGISTRO[tipo] = extractor


def para(doc_type: str) -> Extractor:
    """El extractor de ese tipo, o `SinExtractor` si no hay ninguno."""
    extractor = _REGISTRO.get(doc_type)
    if extractor is None:
        raise SinExtractor(
            f"No hay lector para documentos de tipo «{doc_type}». Los que se leen hoy: "
            f"{', '.join(sorted(_REGISTRO)) or 'ninguno'}."
        )
    return extractor


def tipos_soportados() -> tuple[str, ...]:
    """Para que la interfaz sepa dónde ofrecer el botón de extraer."""
    return tuple(sorted(_REGISTRO))


def _olvidar_todo() -> None:
    """Solo para las pruebas: vacía el registro."""
    _REGISTRO.clear()


__all__ = [
    "Aportacion",
    "CampoPropuesto",
    "Extractor",
    "ObjetoPropuesto",
    "PlantaPropuesta",
    "Procedencia",
    "SinExtractor",
    "para",
    "registrar",
    "tipos_soportados",
]


def _valor_como_texto(valor: Any) -> str:
    """Normaliza a texto lo que un extractor proponga.

    Está aquí y no en cada extractor para que dos lectores no escriban el mismo
    número de dos formas distintas y el gestor crea que discrepan.
    """
    if isinstance(valor, Decimal):
        return format(valor.normalize(), "f")
    return str(valor)

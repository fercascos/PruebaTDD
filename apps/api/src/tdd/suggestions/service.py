"""Módulo de Sugerencias · lógica de dominio.

`[REQ]` «Cada usuario propone cambios y solo el/los administrador/es ven las
propuestas.»

**La visibilidad no se implementa aquí.** Vive en las políticas RLS del esquema,
y este servicio simplemente consulta. Es deliberado: si mañana alguien añade una
consulta nueva y olvida filtrar, la base de datos sigue sin entregar la fila.
Lo que sí vive aquí son las **guardas del ciclo de vida**, que son reglas de
negocio y no de acceso.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum


class SuggestionType(StrEnum):
    CATALOGO = "CATALOGO"
    PRECIO = "PRECIO"
    PLANTILLA = "PLANTILLA"
    APLICACION = "APLICACION"


class SuggestionStatus(StrEnum):
    NUEVA = "NUEVA"
    EN_REVISION = "EN_REVISION"
    ACEPTADA = "ACEPTADA"
    RECHAZADA = "RECHAZADA"
    DUPLICADA = "DUPLICADA"
    APLICADA = "APLICADA"


#: Transiciones permitidas. Lo que no está aquí, no ocurre.
TRANSICIONES: dict[SuggestionStatus, frozenset[SuggestionStatus]] = {
    SuggestionStatus.NUEVA: frozenset(
        {SuggestionStatus.EN_REVISION, SuggestionStatus.DUPLICADA}
    ),
    SuggestionStatus.EN_REVISION: frozenset(
        {
            SuggestionStatus.ACEPTADA,
            SuggestionStatus.RECHAZADA,
            SuggestionStatus.DUPLICADA,
        }
    ),
    SuggestionStatus.ACEPTADA: frozenset({SuggestionStatus.APLICADA}),
    SuggestionStatus.RECHAZADA: frozenset(),
    SuggestionStatus.DUPLICADA: frozenset(),
    SuggestionStatus.APLICADA: frozenset(),
}

LONGITUD_MINIMA_RESPUESTA = 10


class TransicionInvalida(ValueError):
    """El cambio de estado pedido no está permitido."""


class RespuestaObligatoria(ValueError):
    """Rechazar exige explicarse.

    Es la única regla que impide que el buzón se convierta en un cementerio: sin
    ella, «rechazada» acaba siendo un sinónimo educado de «archivada» y la gente
    deja de proponer.
    """


@dataclass(frozen=True, slots=True)
class PeticionTransicion:
    a: SuggestionStatus
    resolution_note: str | None = None
    duplicate_of_id: uuid.UUID | None = None
    applied_entity_type: str | None = None
    applied_entity_id: uuid.UUID | None = None


def validar_transicion(
    actual: SuggestionStatus, peticion: PeticionTransicion, *, propia_id: uuid.UUID
) -> None:
    """Comprueba las guardas del ciclo de vida. Lanza si algo no cuadra.

    Las mismas reglas están además como `CHECK` en la base de datos: aquí se
    validan para poder devolver un `422` legible, allí para que nadie pueda
    saltárselas por otra vía.
    """
    permitidas = TRANSICIONES[actual]
    if peticion.a not in permitidas:
        opciones = ", ".join(sorted(permitidas)) or "ninguna: es un estado final"
        raise TransicionInvalida(
            f"No se puede pasar de «{actual}» a «{peticion.a}». Transiciones posibles: {opciones}"
        )

    if peticion.a is SuggestionStatus.RECHAZADA:
        nota = (peticion.resolution_note or "").strip()
        if len(nota) < LONGITUD_MINIMA_RESPUESTA:
            raise RespuestaObligatoria(
                "Al rechazar una sugerencia hay que explicar por qué: "
                f"al menos {LONGITUD_MINIMA_RESPUESTA} caracteres. "
                "Quien la escribió va a leer esta respuesta."
            )

    if peticion.a is SuggestionStatus.DUPLICADA:
        if peticion.duplicate_of_id is None:
            raise TransicionInvalida(
                "Marcar como duplicada exige indicar con cuál se agrupa"
            )
        if peticion.duplicate_of_id == propia_id:
            raise TransicionInvalida("Una sugerencia no puede ser duplicada de sí misma")

    if peticion.a is SuggestionStatus.APLICADA and peticion.applied_entity_id is None:
        raise TransicionInvalida(
            "Aplicar una sugerencia exige enlazar lo que se ha creado o cambiado: "
            "sin ese enlace, «aplicada» no es comprobable"
        )


def contexto_es_por_referencia(payload: dict[str, object] | None) -> bool:
    """`[REC]` Comprobación defensiva del contrato de privacidad.

    El contexto de una sugerencia se guarda **por referencia** —identificadores—
    y nunca copiando datos del proyecto. Esto detecta el caso más probable de
    despiste: un `payload` que trae nombres de cliente o importes del proyecto
    en vez de identificadores.
    """
    if not payload:
        return True
    prohibidas = {"client_name", "project_name", "capex_total", "asset_name"}
    return not (prohibidas & set(payload))

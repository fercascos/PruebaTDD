"""Máquina de estados del proyecto · **función pura**.

`[REQ]` docs/02 §5.1. El `estado` describe el **ciclo administrativo** del
encargo. No describe el trabajo: para eso están las fases, que son un eje
independiente y avanzan en paralelo.

Las guardas no son decoración. Dejar pasar un proyecto a «visita realizada»
cuando falta un activo por visitar es exactamente el tipo de descuido que
después aparece en un informe.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProjectStatus(StrEnum):
    BORRADOR = "BORRADOR"
    EN_PREPARACION = "EN_PREPARACION"
    VISITA_PROGRAMADA = "VISITA_PROGRAMADA"
    VISITA_REALIZADA = "VISITA_REALIZADA"
    EN_ANALISIS = "EN_ANALISIS"
    EN_REVISION = "EN_REVISION"
    INFORME_EMITIDO = "INFORME_EMITIDO"
    CERRADO = "CERRADO"
    ARCHIVADO = "ARCHIVADO"


S = ProjectStatus

TRANSICIONES: dict[ProjectStatus, frozenset[ProjectStatus]] = {
    S.BORRADOR: frozenset({S.EN_PREPARACION, S.ARCHIVADO}),
    S.EN_PREPARACION: frozenset({S.VISITA_PROGRAMADA, S.ARCHIVADO}),
    S.VISITA_PROGRAMADA: frozenset({S.VISITA_REALIZADA}),
    S.VISITA_REALIZADA: frozenset({S.EN_ANALISIS}),
    S.EN_ANALISIS: frozenset({S.EN_REVISION}),
    S.EN_REVISION: frozenset({S.EN_ANALISIS, S.INFORME_EMITIDO}),
    # Reapertura autorizada: crea una versión nueva, no modifica la emitida.
    S.INFORME_EMITIDO: frozenset({S.CERRADO, S.EN_ANALISIS}),
    S.CERRADO: frozenset({S.ARCHIVADO}),
    S.ARCHIVADO: frozenset({S.CERRADO}),  # desarchivar: solo ADMIN
}


@dataclass(frozen=True, slots=True)
class EstadoDelEncargo:
    """Los hechos contra los que se comprueban las guardas."""

    clientes: int = 0
    activos: int = 0
    visitas_agendadas: int = 0
    visitas_realizadas: int = 0
    versiones_generadas: int = 0
    aprobaciones_registradas: int = 0
    fases_posteriores_completadas: bool = False


class TransicionNoPermitida(ValueError):
    """El destino no existe desde el estado actual."""


class GuardaIncumplida(ValueError):
    """El destino existe, pero falta algo por hacer.

    Se separa de `TransicionNoPermitida` a propósito: son dos conversaciones
    distintas con el usuario. Una dice «eso no se puede»; la otra, «falta esto».
    """


def _guardas(actual: ProjectStatus, destino: ProjectStatus, e: EstadoDelEncargo) -> list[str]:
    """Devuelve la lista de motivos que impiden la transición. Vacía si procede."""
    faltan: list[str] = []

    if destino is S.EN_PREPARACION:
        if e.clientes < 1:
            faltan.append("el proyecto no tiene cliente asignado")
        if e.activos < 1:
            faltan.append("el proyecto no tiene ningún activo")

    elif destino is S.VISITA_PROGRAMADA:
        if e.visitas_agendadas < 1:
            faltan.append("no hay ninguna visita agendada")

    elif destino is S.VISITA_REALIZADA:
        pendientes = e.activos - e.visitas_realizadas
        if pendientes > 0:
            verbo = "queda" if pendientes == 1 else "quedan"
            sustantivo = "activo" if pendientes == 1 else "activos"
            faltan.append(
                f"{verbo} {pendientes} {sustantivo} por visitar "
                f"({e.visitas_realizadas} de {e.activos} realizadas)"
            )

    elif destino is S.EN_REVISION:
        if e.versiones_generadas < 1:
            faltan.append("no hay ninguna versión de informe generada")

    elif destino is S.INFORME_EMITIDO:
        if e.aprobaciones_registradas < 1:
            faltan.append("falta la aprobación de un revisor")

    elif destino is S.CERRADO and actual is S.INFORME_EMITIDO:
        if not e.fases_posteriores_completadas:
            faltan.append("quedan fases posteriores sin completar (presentación o defensa)")

    return faltan


def validar_transicion(
    actual: ProjectStatus, destino: ProjectStatus, estado: EstadoDelEncargo
) -> None:
    """Comprueba que la transición existe y que sus guardas se cumplen."""
    if actual == destino:
        raise TransicionNoPermitida(f"El proyecto ya está en «{actual}»")

    posibles = TRANSICIONES[actual]
    if destino not in posibles:
        opciones = ", ".join(sorted(posibles)) or "ninguna: es un estado final"
        raise TransicionNoPermitida(
            f"No se puede pasar de «{actual}» a «{destino}». Destinos posibles: {opciones}"
        )

    faltan = _guardas(actual, destino, estado)
    if faltan:
        raise GuardaIncumplida(f"Para pasar a «{destino}» falta: " + "; ".join(faltan))


def destinos_posibles(
    actual: ProjectStatus, estado: EstadoDelEncargo
) -> dict[ProjectStatus, list[str]]:
    """Qué transiciones se ofrecen y qué falta para cada una.

    `[REC]` La interfaz usa esto para **mostrar el botón deshabilitado con su
    motivo** en vez de ocultarlo. Un botón que no está no se puede preguntar por
    qué no está; uno deshabilitado que dice «faltan 2 activos por visitar»
    enseña cómo funciona el proceso.
    """
    return {d: _guardas(actual, d, estado) for d in sorted(TRANSICIONES[actual])}

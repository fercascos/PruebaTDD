"""Motor de fases · **funciones puras**.

Dos ideas sostienen este módulo:

1. **Estado y fases son ejes independientes.** El `estado` del proyecto describe
   el ciclo administrativo del encargo (borrador → archivado). Las **fases**
   describen el trabajo real y avanzan en paralelo: un encargo puede tener la
   documentación pendiente, la visita hecha y el Q&A en curso a la vez.

2. **Dos fases tienen el estado derivado y no se marcan a mano.** Red Flag/CAPEX
   y Full Report se calculan a partir del trabajo que hay debajo. Una lista de
   verificación que se puede marcar cuando el trabajo no está hecho es peor que
   no tenerla: da una falsa sensación de avance justo donde más cuesta.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PhaseCode(StrEnum):
    SOLICITUD_DOCUMENTACION = "SOLICITUD_DOCUMENTACION"
    VDR = "VDR"
    VISITA = "VISITA"
    QA = "QA"
    RED_FLAG_CAPEX = "RED_FLAG_CAPEX"
    FULL_REPORT = "FULL_REPORT"
    PRESENTACION_CLIENTE = "PRESENTACION_CLIENTE"
    DEFENSA = "DEFENSA"


class PhaseStatus(StrEnum):
    NO_APLICA = "NO_APLICA"
    PENDIENTE = "PENDIENTE"
    EN_CURSO = "EN_CURSO"
    COMPLETADA = "COMPLETADA"
    BLOQUEADA = "BLOQUEADA"


#: Las fases cuyo estado calcula el motor y **no acepta la API**.
FASES_DERIVADAS: frozenset[PhaseCode] = frozenset({PhaseCode.RED_FLAG_CAPEX, PhaseCode.FULL_REPORT})


class EstadoNoEscribible(ValueError):
    """Se ha intentado fijar a mano el estado de una fase derivada."""


@dataclass(frozen=True, slots=True)
class HechosDelProyecto:
    """Lo que el motor necesita saber. Nada más, y nada de base de datos.

    Es lo que hace comprobable el motor: se le pasan números y devuelve estados,
    sin montar medio proyecto para probar un caso límite.
    """

    lineas_capex: int = 0
    lineas_con_precio_validado: int = 0
    versiones_de_informe: int = 0
    versiones_emitidas: int = 0
    # Solicitud de documentación
    documentos_solicitados: int = 0
    documentos_resueltos: int = 0
    # Visitas
    activos: int = 0
    visitas_agendadas: int = 0
    visitas_realizadas: int = 0
    # Q&A
    rondas_qa: int = 0
    rondas_qa_cerradas: int = 0
    # VDR
    tiene_enlace_vdr: bool = False
    # Presentación y defensa
    eventos_registrados: int = 0


def estado_derivado(codigo: PhaseCode, h: HechosDelProyecto) -> PhaseStatus:
    """Calcula el estado de una fase derivada. Solo Red Flag/CAPEX y Full Report."""
    if codigo not in FASES_DERIVADAS:
        raise ValueError(f"La fase «{codigo}» no tiene estado derivado")

    if codigo is PhaseCode.RED_FLAG_CAPEX:
        if h.lineas_capex == 0:
            return PhaseStatus.PENDIENTE
        if h.lineas_con_precio_validado < h.lineas_capex:
            # Quedan precios sin validar: el CAPEX no está cerrado, aunque
            # todas las líneas existan.
            return PhaseStatus.EN_CURSO
        return PhaseStatus.COMPLETADA

    # FULL_REPORT
    if h.versiones_emitidas > 0:
        return PhaseStatus.COMPLETADA
    if h.versiones_de_informe > 0:
        return PhaseStatus.EN_CURSO
    return PhaseStatus.PENDIENTE


def estado_sugerido(codigo: PhaseCode, h: HechosDelProyecto) -> PhaseStatus:
    """Estado **sugerido** para las fases NO derivadas.

    `[REC]` Se ofrece como ayuda, no se impone: el responsable de la fase puede
    tener motivos que la aplicación no conoce —una visita aplazada por el
    cliente, una documentación que llega por otra vía—. La interfaz lo muestra
    como «parece que esta fase ya está en curso», con un botón para aplicarlo.
    """
    if codigo in FASES_DERIVADAS:
        return estado_derivado(codigo, h)

    match codigo:
        case PhaseCode.SOLICITUD_DOCUMENTACION:
            if h.documentos_solicitados == 0:
                return PhaseStatus.PENDIENTE
            if h.documentos_resueltos >= h.documentos_solicitados:
                return PhaseStatus.COMPLETADA
            return PhaseStatus.EN_CURSO
        case PhaseCode.VDR:
            return PhaseStatus.COMPLETADA if h.tiene_enlace_vdr else PhaseStatus.PENDIENTE
        case PhaseCode.VISITA:
            if h.activos == 0 or (h.visitas_agendadas == 0 and h.visitas_realizadas == 0):
                return PhaseStatus.PENDIENTE
            if h.visitas_realizadas >= h.activos:
                return PhaseStatus.COMPLETADA
            return PhaseStatus.EN_CURSO
        case PhaseCode.QA:
            if h.rondas_qa == 0:
                return PhaseStatus.PENDIENTE
            if h.rondas_qa_cerradas >= h.rondas_qa:
                return PhaseStatus.COMPLETADA
            return PhaseStatus.EN_CURSO
        case PhaseCode.PRESENTACION_CLIENTE | PhaseCode.DEFENSA:
            return PhaseStatus.COMPLETADA if h.eventos_registrados > 0 else PhaseStatus.PENDIENTE
        case _:  # pragma: no cover — el enum está cerrado
            return PhaseStatus.PENDIENTE


def comprobar_estado_escribible(codigo: PhaseCode) -> None:
    """Lanza si se intenta escribir a mano el estado de una fase derivada."""
    if codigo in FASES_DERIVADAS:
        raise EstadoNoEscribible(
            f"El estado de «{codigo}» lo calcula la aplicación a partir del trabajo real "
            "y no se puede fijar a mano. Marque como completado lo que falte "
            "(líneas de CAPEX con precio validado, o la versión del informe)."
        )


@dataclass(frozen=True, slots=True)
class AvanceDeFase:
    """Lo que se muestra en la ficha de proyecto, por fase."""

    code: PhaseCode
    status: PhaseStatus
    es_derivado: bool
    detalle: str


def describir_avance(codigo: PhaseCode, estado: PhaseStatus, h: HechosDelProyecto) -> AvanceDeFase:
    """Frase corta que explica *por qué* la fase está donde está.

    `[REC]` Un estado sin explicación obliga a entrar en la fase para entenderlo.
    Esta frase es lo que hace útil la vista de fases de la ficha de proyecto.
    """
    match codigo:
        case PhaseCode.SOLICITUD_DOCUMENTACION:
            detalle = f"{h.documentos_resueltos} de {h.documentos_solicitados} resueltas"
        case PhaseCode.VDR:
            detalle = "enlace activo" if h.tiene_enlace_vdr else "sin enlace"
        case PhaseCode.VISITA:
            detalle = f"{h.visitas_realizadas} de {h.activos} activos visitados"
        case PhaseCode.QA:
            detalle = f"{h.rondas_qa_cerradas} de {h.rondas_qa} rondas cerradas"
        case PhaseCode.RED_FLAG_CAPEX:
            sin_validar = h.lineas_capex - h.lineas_con_precio_validado
            detalle = f"{h.lineas_capex} líneas"
            if sin_validar > 0:
                detalle += f" · {sin_validar} sin precio validado"
        case PhaseCode.FULL_REPORT:
            if h.versiones_emitidas:
                detalle = f"{h.versiones_emitidas} versión(es) emitida(s)"
            elif h.versiones_de_informe:
                detalle = f"{h.versiones_de_informe} versión(es) en borrador"
            else:
                detalle = "sin generar"
        case _:
            detalle = f"{h.eventos_registrados} evento(s)"

    return AvanceDeFase(
        code=codigo,
        status=estado,
        es_derivado=codigo in FASES_DERIVADAS,
        detalle=detalle,
    )

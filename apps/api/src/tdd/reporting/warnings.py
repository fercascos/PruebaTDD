"""Avisos previos a la generación `[REQ]` §17.7 · **función pura**.

La decisión que gobierna el módulo: **hay cinco avisos bloqueantes y ni uno
más**. Todo lo demás informa y deja decidir.

Es deliberado. Un generador que se niega a producir nada mientras quede un pie
de foto vacío convierte cada borrador interno en una pelea, y la reacción del
equipo es rellenar los campos con texto de relleno para poder avanzar. Lo que
sí se bloquea es lo que produciría un documento **incorrecto**: un marcador sin
resolver que saldría como `{{...}}` en la pantalla del cliente, una foto que no
ha superado las verificaciones, un mapeo que apunta a un campo inexistente.

`UNVALIDATED_PRICES` es el caso interesante: generar con precios sin validar es
legítimo —un borrador interno lo es— pero **enviarlo al cliente sin darse
cuenta es un problema real**. Por eso no bloquea y a la vez es el aviso más
visible del conjunto.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class Severidad(StrEnum):
    BLOQUEANTE = "BLOQUEANTE"
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


@dataclass(frozen=True, slots=True)
class Aviso:
    codigo: str
    severidad: Severidad
    mensaje: str
    #: A qué se refiere, para que la interfaz pueda llevar al usuario allí.
    entidad: str | None = None
    entidad_id: uuid.UUID | None = None

    @property
    def bloquea(self) -> bool:
        return self.severidad is Severidad.BLOQUEANTE


@dataclass(frozen=True, slots=True)
class EstadoDelInforme:
    """Todo lo que hace falta saber para decidir si se puede generar."""

    #: Marcadores de la plantilla sin ninguna expresión que los alimente.
    marcadores_sin_mapear: tuple[str, ...] = ()
    #: Expresiones del mapeo que apuntan a un campo que no existe.
    expresiones_invalidas: tuple[str, ...] = ()
    plantilla_analizada: bool = True
    #: Fotos seleccionadas que no han superado las verificaciones.
    fotos_no_utilizables: tuple[uuid.UUID, ...] = ()
    fotos_sin_activo: tuple[uuid.UUID, ...] = ()
    fotos_sin_pie: tuple[uuid.UUID, ...] = ()
    activos_sin_fotos: tuple[uuid.UUID, ...] = ()
    #: Líneas con precio sin validar, con su importe acumulado.
    lineas_con_precio_sin_validar: int = 0
    importe_sin_validar: Decimal = Decimal("0")
    #: Hallazgos cuya zona dejó de ser válida al reclasificar el activo.
    lineas_con_zona_a_revisar: tuple[uuid.UUID, ...] = ()
    #: Bloques de texto que no caben en su marco, con su exceso.
    desbordamientos: tuple[tuple[str, float], ...] = ()
    #: En cuántas diapositivas se partirá la tabla de CAPEX.
    diapositivas_de_tabla: int = 1
    fuentes_ausentes: tuple[str, ...] = ()
    campos_vacios: tuple[str, ...] = ()
    solicitudes_pendientes: int = 0
    hay_marca_de_borrador_en_plantilla: bool = False


#: Exceso a partir del cual se avisa de desbordamiento `[REQ]` §17.7.
UMBRAL_DESBORDAMIENTO = 0.10


def evaluar(estado: EstadoDelInforme) -> list[Aviso]:
    """Devuelve todos los avisos, los bloqueantes primero.

    El orden importa: quien mira la lista tiene que ver antes lo que le impide
    generar que lo que solo debería mirar.
    """
    avisos: list[Aviso] = []

    # ── Bloqueantes ─────────────────────────────────────────────────────────
    for marcador in estado.marcadores_sin_mapear:
        avisos.append(
            Aviso(
                "UNMAPPED_PLACEHOLDER",
                Severidad.BLOQUEANTE,
                # Sin esto, el marcador saldría literal en la pantalla del
                # cliente, que es la peor forma posible de descubrir el fallo.
                f"El marcador «{marcador}» no tiene origen en el mapeo y saldría "
                "literalmente en el documento.",
                "placeholder",
            )
        )
    if not estado.plantilla_analizada:
        avisos.append(
            Aviso(
                "MISSING_TEMPLATE",
                Severidad.BLOQUEANTE,
                "La plantilla no se ha analizado todavía: no se sabe qué marcadores tiene.",
                "template",
            )
        )
    for expresion in estado.expresiones_invalidas:
        avisos.append(
            Aviso(
                "INVALID_MAPPING_EXPRESSION",
                Severidad.BLOQUEANTE,
                f"La expresión «{expresion}» del mapeo apunta a un campo que no existe.",
                "mapping",
            )
        )
    for foto in estado.fotos_no_utilizables:
        avisos.append(
            Aviso(
                "PHOTO_QUARANTINED",
                Severidad.BLOQUEANTE,
                "Hay una fotografía seleccionada que no ha superado las verificaciones.",
                "photo",
                foto,
            )
        )
    for linea in estado.lineas_con_zona_a_revisar:
        avisos.append(
            Aviso(
                "ZONE_REVIEW_PENDING",
                Severidad.BLOQUEANTE,
                # Reclasificar un activo puede dejar zonas que ya no aplican.
                # Salir en el informe con una zona imposible es peor que parar.
                "Una línea quedó con una zona que ya no corresponde a la tipología del activo.",
                "finding",
                linea,
            )
        )

    # ── Altas ───────────────────────────────────────────────────────────────
    for donde, exceso in estado.desbordamientos:
        if exceso > UMBRAL_DESBORDAMIENTO:
            avisos.append(
                Aviso(
                    "TEXT_OVERFLOW",
                    Severidad.ALTA,
                    f"El texto de «{donde}» excede su marco un {exceso:.0%}.",
                    "placeholder",
                )
            )
    if estado.diapositivas_de_tabla > 1:
        avisos.append(
            Aviso(
                "TABLE_DOES_NOT_FIT",
                Severidad.ALTA,
                f"La tabla de CAPEX se repartirá en {estado.diapositivas_de_tabla} diapositivas.",
                "table",
            )
        )
    for foto in estado.fotos_sin_activo:
        avisos.append(
            Aviso(
                "PHOTO_WITHOUT_ASSET",
                Severidad.ALTA,
                "Fotografía seleccionada sin activo: no se sabría en qué diapositiva colocarla.",
                "photo",
                foto,
            )
        )

    # ── Medias ──────────────────────────────────────────────────────────────
    if estado.lineas_con_precio_sin_validar:
        avisos.append(
            Aviso(
                "UNVALIDATED_PRICES",
                Severidad.MEDIA,
                # No bloquea —un borrador interno es legítimo— pero enviarlo al
                # cliente sin darse cuenta sí es un problema real.
                f"{estado.lineas_con_precio_sin_validar} líneas con precio sin validar, "
                f"por un total de {estado.importe_sin_validar:,.2f} €. "
                "Revíselas antes de enviar el informe al cliente.",
                "capex",
            )
        )
    for activo in estado.activos_sin_fotos:
        avisos.append(
            Aviso(
                "MISSING_PHOTO",
                Severidad.MEDIA,
                "El activo no tiene ninguna fotografía seleccionada para el informe.",
                "asset",
                activo,
            )
        )
    for fuente in estado.fuentes_ausentes:
        avisos.append(
            Aviso(
                "FONT_NOT_AVAILABLE",
                Severidad.MEDIA,
                # No bloquea: el PPTX guarda el NOMBRE de la fuente, así que en
                # un equipo que sí la tenga se verá bien. Lo que falla es la
                # medición del desbordamiento aquí.
                f"La fuente «{fuente}» no está instalada en el servidor. El documento la "
                "seguirá pidiendo por nombre, pero la estimación de desbordamiento pierde "
                "precisión.",
                "font",
            )
        )
    if estado.solicitudes_pendientes:
        avisos.append(
            Aviso(
                "PENDING_DOC_REQUESTS",
                Severidad.MEDIA,
                f"Quedan {estado.solicitudes_pendientes} documentos en «solicitada»: "
                "compruebe si deben declararse como limitación.",
                "doc_request",
            )
        )

    # ── Bajas ───────────────────────────────────────────────────────────────
    for foto in estado.fotos_sin_pie:
        avisos.append(
            Aviso("MISSING_CAPTION", Severidad.BAJA, "Fotografía sin pie de foto.", "photo", foto)
        )
    for campo in estado.campos_vacios:
        avisos.append(
            Aviso(
                "EMPTY_FIELD",
                Severidad.BAJA,
                # [REQ] §17.7 · Se inserta texto VACÍO, nunca el literal
                # `{{...}}` ni un «N/D» inventado.
                f"El campo «{campo}» está vacío: se insertará texto vacío.",
                "placeholder",
            )
        )

    orden = {s: i for i, s in enumerate(Severidad)}
    return sorted(avisos, key=lambda a: orden[a.severidad])


def puede_generarse(avisos: list[Aviso]) -> bool:
    return not any(a.bloquea for a in avisos)


def motivos_de_bloqueo(avisos: list[Aviso]) -> list[str]:
    return [a.mensaje for a in avisos if a.bloquea]


@dataclass(frozen=True, slots=True)
class Resumen:
    """Lo que se enseña arriba de la previsualización."""

    total: int
    bloqueantes: int
    por_severidad: dict[str, int] = field(default_factory=dict)


def resumir(avisos: list[Aviso]) -> Resumen:
    por_severidad: dict[str, int] = {}
    for aviso in avisos:
        por_severidad[aviso.severidad.value] = por_severidad.get(aviso.severidad.value, 0) + 1
    return Resumen(
        total=len(avisos),
        bloqueantes=sum(1 for a in avisos if a.bloquea),
        por_severidad=por_severidad,
    )

"""Reglas del bloque de fotografías · **funciones puras**.

Nada de aquí toca la base de datos ni el almacenamiento: recibe datos y
devuelve decisiones. Es lo que permite probar las reglas difíciles —duplicados,
papelera, avisos previos al informe— sin montar infraestructura, y lo que evita
que esas reglas queden repartidas por los endpoints.

Las tres reglas que el cliente fijó y que aquí se hacen cumplir:

* **Nunca se borra un duplicado automáticamente.** Se avisa y decide una persona.
* **Nunca se infiere una fecha ni una ubicación.** Lo que no viene en el EXIF,
  no está.
* **El borrado es siempre lógico** y la purga, autorizada y con retención.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from tdd.evidence.images import UMBRAL_DUPLICADO_PERCEPTUAL, distancia_hamming
from tdd.evidence.naming import (
    PLANTILLA_POR_DEFECTO,
    generar_nombre,
    numero_correlativo,
    resolver_colisiones,
)


class EstadoDeFoto(StrEnum):
    SUBIENDO = "SUBIENDO"
    PROCESANDO = "PROCESANDO"
    LISTA = "LISTA"
    CUARENTENA = "CUARENTENA"
    ERROR = "ERROR"
    PAPELERA = "PAPELERA"
    PURGADA = "PURGADA"


#: §15.9. Lo que no está aquí no ocurre: de `PURGADA` no se sale, y a `LISTA`
#: solo se llega superando las verificaciones o restaurando desde la papelera.
TRANSICIONES: dict[EstadoDeFoto, frozenset[EstadoDeFoto]] = {
    EstadoDeFoto.SUBIENDO: frozenset({EstadoDeFoto.PROCESANDO, EstadoDeFoto.ERROR}),
    EstadoDeFoto.PROCESANDO: frozenset(
        {EstadoDeFoto.LISTA, EstadoDeFoto.CUARENTENA, EstadoDeFoto.ERROR}
    ),
    EstadoDeFoto.LISTA: frozenset({EstadoDeFoto.PAPELERA}),
    EstadoDeFoto.CUARENTENA: frozenset({EstadoDeFoto.PURGADA}),
    EstadoDeFoto.ERROR: frozenset({EstadoDeFoto.PAPELERA}),
    EstadoDeFoto.PAPELERA: frozenset({EstadoDeFoto.LISTA, EstadoDeFoto.PURGADA}),
    EstadoDeFoto.PURGADA: frozenset(),
}


class TransicionDeFotoNoPermitida(Exception):  # noqa: N818 — el dominio está en español
    """El cambio de estado no existe en §15.9. Se traduce a `409`."""


class PurgaNoPermitida(Exception):  # noqa: N818
    """La foto no puede purgarse todavía, o no puede purgarse nunca."""

    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


def comprobar_transicion(desde: EstadoDeFoto, hasta: EstadoDeFoto) -> None:
    if hasta not in TRANSICIONES[desde]:
        posibles = ", ".join(sorted(TRANSICIONES[desde])) or "ninguno"
        raise TransicionDeFotoNoPermitida(
            f"Una fotografía en «{desde}» no puede pasar a «{hasta}». Destinos posibles: {posibles}"
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Duplicados §15.5
# ─────────────────────────────────────────────────────────────────────────────


class TipoDeDuplicado(StrEnum):
    EXACTO = "EXACTO"
    CASI = "CASI"


@dataclass(frozen=True, slots=True)
class FotoConocida:
    """Lo mínimo de una foto ya existente para decidir si la nueva es repetida."""

    id: uuid.UUID
    sha256: str
    phash: str | None = None
    display_name: str = ""


@dataclass(frozen=True, slots=True)
class Duplicado:
    tipo: TipoDeDuplicado
    photo_id: uuid.UUID
    distancia: int
    display_name: str = ""

    @property
    def mensaje(self) -> str:
        if self.tipo is TipoDeDuplicado.EXACTO:
            return "Este archivo ya está en el proyecto. Súbalo solo si quiere una copia."
        return (
            "Se parece mucho a una fotografía ya subida. Puede ser otro disparo "
            "de la misma escena: revíselo antes de descartarlo."
        )


def buscar_duplicado(
    sha256: str, phash: str | None, catalogo: Iterable[FotoConocida]
) -> Duplicado | None:
    """Decide si la foto entrante ya está, y **solo informa**.

    `[REQ]` §15.5 · En ningún caso se borra automáticamente un duplicado. Una
    foto aparentemente redundante puede ser la única que documenta un detalle.

    El exacto tiene prioridad: si el `sha256` coincide no hace falta mirar nada
    más, y es la única coincidencia de la que se puede estar seguro.
    """
    mejor: Duplicado | None = None
    for conocida in catalogo:
        if conocida.sha256 == sha256:
            return Duplicado(TipoDeDuplicado.EXACTO, conocida.id, 0, conocida.display_name)
        if phash and conocida.phash:
            d = distancia_hamming(phash, conocida.phash)
            if d <= UMBRAL_DUPLICADO_PERCEPTUAL and (mejor is None or d < mejor.distancia):
                mejor = Duplicado(TipoDeDuplicado.CASI, conocida.id, d, conocida.display_name)
    return mejor


def agrupar_duplicados(fotos: Sequence[FotoConocida]) -> list[list[uuid.UUID]]:
    """Grupos de fotos que son la misma o casi la misma.

    Para la pantalla de revisión de duplicados: se muestran juntas y decide una
    persona. El orden dentro del grupo es el de entrada, para que la primera
    subida encabece el grupo.
    """
    grupos: list[list[FotoConocida]] = []
    for foto in fotos:
        for grupo in grupos:
            cabeza = grupo[0]
            if cabeza.sha256 == foto.sha256:
                grupo.append(foto)
                break
            if (
                foto.phash
                and cabeza.phash
                and distancia_hamming(foto.phash, cabeza.phash) <= UMBRAL_DUPLICADO_PERCEPTUAL
            ):
                grupo.append(foto)
                break
        else:
            grupos.append([foto])
    return [[f.id for f in g] for g in grupos if len(g) > 1]


# ─────────────────────────────────────────────────────────────────────────────
#  GPS §15.6
# ─────────────────────────────────────────────────────────────────────────────

#: `[SUP]` Radio por defecto del aviso. Configurable por organización.
RADIO_AVISO_GPS_M = 500.0

_RADIO_TERRESTRE_M = 6_371_000.0


def distancia_en_metros(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia sobre la esfera (haversine). Suficiente a escala de un activo."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _RADIO_TERRESTRE_M * math.asin(math.sqrt(a))


# ─────────────────────────────────────────────────────────────────────────────
#  Avisos §15.10
# ─────────────────────────────────────────────────────────────────────────────


class Severidad(StrEnum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    BLOQUEANTE = "BLOQUEANTE"


@dataclass(frozen=True, slots=True)
class Aviso:
    codigo: str
    severidad: Severidad
    mensaje: str
    photo_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class FotoParaInforme:
    """Vista de una foto desde el punto de vista de la generación del informe."""

    id: uuid.UUID
    estado: EstadoDeFoto
    include_in_report: bool
    asset_id: uuid.UUID | None = None
    caption: str | None = None
    gps: tuple[float, float] | None = None
    #: Coordenadas declaradas del activo al que se asignó, si se conocen.
    gps_del_activo: tuple[float, float] | None = None


def avisos_previos_al_informe(
    fotos: Iterable[FotoParaInforme],
    *,
    activos_esperados: Iterable[uuid.UUID] = (),
    radio_gps_m: float = RADIO_AVISO_GPS_M,
) -> list[Aviso]:
    """Todo lo que conviene mirar antes de generar el PPTX.

    Un solo aviso es **bloqueante**: insertar en un informe una foto en
    cuarentena o con error. Los demás son de calidad, y quien firma el informe
    decide. Bloquear por falta de pie de foto sería tratar al consultor como si
    no supiera lo que hace.
    """
    avisos: list[Aviso] = []
    seleccionadas = [f for f in fotos if f.include_in_report]
    con_fotos = {f.asset_id for f in seleccionadas if f.asset_id}

    for foto in seleccionadas:
        if foto.estado in (EstadoDeFoto.CUARENTENA, EstadoDeFoto.ERROR):
            avisos.append(
                Aviso(
                    "PHOTO_NOT_USABLE",
                    Severidad.BLOQUEANTE,
                    f"La fotografía está en «{foto.estado}» y no puede insertarse en el informe.",
                    foto.id,
                )
            )
        if foto.asset_id is None:
            avisos.append(
                Aviso(
                    "PHOTO_WITHOUT_ASSET",
                    Severidad.ALTA,
                    "Fotografía sin activo: no se sabría en qué diapositiva colocarla.",
                    foto.id,
                )
            )
        if not (foto.caption or "").strip():
            avisos.append(
                Aviso(
                    "PHOTO_WITHOUT_CAPTION",
                    Severidad.BAJA,
                    "Fotografía seleccionada sin pie de foto.",
                    foto.id,
                )
            )
        if foto.gps and foto.gps_del_activo:
            metros = distancia_en_metros(*foto.gps, *foto.gps_del_activo)
            if metros > radio_gps_m:
                avisos.append(
                    Aviso(
                        "PHOTO_GPS_FAR_FROM_ASSET",
                        Severidad.MEDIA,
                        # Aviso, nunca bloqueo: hay sótanos sin GPS fiable y hay
                        # instalaciones exteriores legítimamente alejadas.
                        f"La fotografía se tomó a {metros:,.0f} m del activo asignado.",
                        foto.id,
                    )
                )

    for activo in activos_esperados:
        if activo not in con_fotos:
            avisos.append(
                Aviso(
                    "ASSET_WITHOUT_PHOTOS",
                    Severidad.MEDIA,
                    "El activo no tiene ninguna fotografía seleccionada para el informe.",
                    None,
                )
            )
    return avisos


# ─────────────────────────────────────────────────────────────────────────────
#  Renombrado en lote §15.4
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ContextoDeFoto:
    """Los valores con los que se rellena la plantilla de nombre."""

    photo_id: uuid.UUID
    nombre_actual: str
    extension: str
    valores: dict[str, str | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CambioDeNombre:
    photo_id: uuid.UUID
    antes: str
    despues: str
    #: Tokens de la plantilla sin valor, que se omitieron con su separador.
    omitidos: tuple[str, ...] = ()

    @property
    def cambia(self) -> bool:
        return self.antes != self.despues


@dataclass(frozen=True, slots=True)
class PlanDeRenombrado:
    """`[REQ]` §15.4 · Lo que devuelve `dry_run: true`, **sin escribir nada**."""

    cambios: tuple[CambioDeNombre, ...]
    colisiones_resueltas: tuple[str, ...]

    @property
    def total_cambian(self) -> int:
        return sum(1 for c in self.cambios if c.cambia)


def planificar_renombrado(
    fotos: Sequence[ContextoDeFoto],
    *,
    plantilla: str = PLANTILLA_POR_DEFECTO,
    numerar_desde: int | None = None,
    digitos: int = 3,
) -> PlanDeRenombrado:
    """Calcula la tabla antes/después. **No escribe. No decide nada solo.**

    La previsualización es obligatoria porque el renombrado en lote es la
    operación con más capacidad de destrozo de todo el bloque: 400 nombres
    cambiados a la vez y ninguna forma cómoda de recordar cómo se llamaban.
    """
    propuestos: list[str] = []
    omitidos_por_foto: list[tuple[str, ...]] = []

    for indice, foto in enumerate(fotos):
        valores = dict(foto.valores)
        if numerar_desde is not None:
            valores["numero"] = numero_correlativo(numerar_desde + indice, digitos=digitos)
        generado = generar_nombre(valores, plantilla=plantilla, extension=f".{foto.extension}")
        propuestos.append(generado.nombre)
        omitidos_por_foto.append(generado.omitidos)

    resueltos = resolver_colisiones(propuestos)
    colisiones = tuple(
        nuevo for original, nuevo in zip(propuestos, resueltos, strict=True) if original != nuevo
    )

    cambios = tuple(
        CambioDeNombre(
            photo_id=foto.photo_id,
            antes=foto.nombre_actual,
            despues=nuevo,
            omitidos=omitidos,
        )
        for foto, nuevo, omitidos in zip(fotos, resueltos, omitidos_por_foto, strict=True)
    )
    return PlanDeRenombrado(cambios=cambios, colisiones_resueltas=colisiones)


# ─────────────────────────────────────────────────────────────────────────────
#  Papelera y purga §15.9
# ─────────────────────────────────────────────────────────────────────────────

#: `[SUP]` Retención por defecto de la papelera.
DIAS_DE_PAPELERA = 30


def dias_en_papelera(borrada_el: datetime, ahora: datetime) -> int:
    return max((ahora - borrada_el).days, 0)


def dias_restantes_en_papelera(
    borrada_el: datetime, ahora: datetime, *, retencion_dias: int = DIAS_DE_PAPELERA
) -> int:
    return max(retencion_dias - dias_en_papelera(borrada_el, ahora), 0)


def comprobar_purga(
    *,
    estado: EstadoDeFoto,
    borrada_el: datetime | None,
    ahora: datetime,
    referenciada_por_informe_emitido: bool,
    retencion_del_proyecto_hasta: date | None = None,
    retencion_dias: int = DIAS_DE_PAPELERA,
) -> None:
    """`[REQ]` La purga física es irreversible, así que tiene cuatro guardas.

    La tercera es la que más veces salvará el pellejo a alguien: una foto
    referenciada por un **informe emitido** no se purga nunca mientras el
    informe exista, porque un informe emitido debe seguir siendo reproducible.
    """
    if referenciada_por_informe_emitido:
        raise PurgaNoPermitida(
            "REFERENCED_BY_ISSUED_REPORT",
            "La fotografía aparece en un informe ya emitido y no puede purgarse: "
            "el informe dejaría de ser reproducible.",
        )
    if estado is EstadoDeFoto.CUARENTENA:
        return  # Lo positivo en el antivirus se purga con autorización explícita.
    if estado is not EstadoDeFoto.PAPELERA or borrada_el is None:
        raise PurgaNoPermitida(
            "NOT_IN_TRASH", "Solo se purga lo que está en la papelera o en cuarentena."
        )
    restantes = dias_restantes_en_papelera(borrada_el, ahora, retencion_dias=retencion_dias)
    if restantes > 0:
        raise PurgaNoPermitida(
            "RETENTION_NOT_ELAPSED",
            f"Quedan {restantes} días de retención en la papelera.",
        )
    if retencion_del_proyecto_hasta is not None and ahora.date() < retencion_del_proyecto_hasta:
        raise PurgaNoPermitida(
            "PROJECT_RETENTION_ACTIVE",
            f"La retención del proyecto llega hasta {retencion_del_proyecto_hasta.isoformat()}.",
        )

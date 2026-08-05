"""Estimación de desbordamiento de texto.

`[LIM]` Es una **estimación**, y el aviso lo dice al usuario. `python-pptx` no
renderiza, así que no hay forma de saber con certeza si un texto cabe sin
dibujarlo. Lo que sí se puede hacer —y se hace— es medir con las métricas
reales de la fuente instalada, que es mucho mejor que contar caracteres.
"""

from __future__ import annotations

from dataclasses import dataclass

from tdd.reporting.fonts import FuenteNoDisponible, cargar

#: Margen de seguridad: el ajuste de palabras desperdicia parte de cada línea.
FACTOR_AJUSTE_DE_LINEA = 0.92


@dataclass(frozen=True, slots=True)
class Capacidad:
    familia: str
    caracteres_por_linea: int
    lineas: int
    caracteres: int
    fuente_real: bool
    #: Texto para el usuario. Nunca se presenta como una certeza.
    nota: str


def capacidad_del_marco(
    *,
    ancho_in: float,
    alto_in: float,
    cuerpo_pt: float,
    familia: str,
    muestra: str | None = None,
) -> Capacidad:
    """Cuántos caracteres caben, aproximadamente, en un marco."""
    texto_tipo = muestra or (
        "Se observa corrosión generalizada en la carrocería y en la batería de la "
        "enfriadora situada en cubierta, con pérdida de sección en varios puntos."
    )
    try:
        m = cargar(familia)
        ancho_medio_em = m.ancho_medio_em(texto_tipo)
        interlineado = m.interlineado_em
        real = True
        nota = f"Estimación con métricas reales de «{familia}». Margen aproximado: ±10 %."
    except FuenteNoDisponible:
        # No se mide en silencio con una sustituta: se declara.
        ancho_medio_em, interlineado, real = 0.50, 1.20, False
        nota = (
            f"⚠ «{familia}» no está instalada: la estimación usa valores genéricos "
            "y puede desviarse bastante más del 10 %. Instale las fuentes corporativas."
        )

    ancho_car_in = ancho_medio_em * cuerpo_pt / 72
    alto_linea_in = interlineado * cuerpo_pt / 72
    cpl = max(1, int(ancho_in / ancho_car_in * FACTOR_AJUSTE_DE_LINEA))
    lineas = max(1, int(alto_in / alto_linea_in))
    return Capacidad(
        familia=familia,
        caracteres_por_linea=cpl,
        lineas=lineas,
        caracteres=cpl * lineas,
        fuente_real=real,
        nota=nota,
    )


@dataclass(frozen=True, slots=True)
class Aviso:
    severidad: str  # "OK" | "CERCA" | "DESBORDA"
    ocupacion: float
    mensaje: str


def evaluar(texto: str, capacidad: Capacidad, *, umbral_aviso: float = 0.90) -> Aviso:
    """Compara un texto con la capacidad estimada del marco."""
    ocupacion = len(texto) / capacidad.caracteres if capacidad.caracteres else 99.0
    if ocupacion > 1.0:
        sobran = len(texto) - capacidad.caracteres
        return Aviso(
            "DESBORDA",
            ocupacion,
            f"El texto probablemente no cabe: sobran unos {sobran} caracteres "
            f"de {len(texto)}. {capacidad.nota}",
        )
    if ocupacion >= umbral_aviso:
        return Aviso(
            "CERCA",
            ocupacion,
            f"El texto ocupa el {ocupacion:.0%} del marco. {capacidad.nota}",
        )
    return Aviso("OK", ocupacion, f"Ocupa el {ocupacion:.0%} del marco disponible.")

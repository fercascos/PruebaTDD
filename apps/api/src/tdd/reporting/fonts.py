"""Métricas tipográficas reales.

`[REQ]` La detección de textos que desbordan se apoya en medir, no en adivinar.
Este módulo carga las familias corporativas instaladas en el sistema y expone su
anchura de avance real. Si una familia falta, **lo dice**: nunca mide en
silencio con una sustituta, porque un aviso calculado sobre otra fuente es peor
que no dar aviso.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont

#: Familias que el informe usa. El arranque del worker falla si falta alguna.
FAMILIAS_REQUERIDAS = (
    "Gotham Light",
    "Gotham Book",
    "Gotham Medium",
    "Gotham Bold",
    "Gotham Black",
    "Gotham Ultra",
)


class FuenteNoDisponible(RuntimeError):
    """Una familia declarada no está instalada en el sistema."""


@dataclass(frozen=True, slots=True)
class MetricasDeFuente:
    familia: str
    ruta: Path
    upm: int
    #: Interlineado natural, en múltiplos del cuerpo.
    interlineado_em: float
    anchos: dict[int, int]  # codepoint → avance en unidades de la fuente

    def ancho_texto_em(self, texto: str) -> float:
        """Anchura de un texto en em. `em` = el cuerpo en puntos."""
        falta = self.anchos.get(ord("?"), self.upm // 2)
        return sum(self.anchos.get(ord(c), falta) for c in texto) / self.upm

    def ancho_medio_em(self, muestra: str) -> float:
        return self.ancho_texto_em(muestra) / len(muestra) if muestra else 0.0


@lru_cache(maxsize=32)
def localizar(familia: str) -> Path | None:
    """Busca el fichero de una familia con `fc-match`, sin sustituciones."""
    try:
        r = subprocess.run(  # noqa: S603
            ["fc-match", "-f", "%{file}\t%{family}", familia],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0 or "\t" not in r.stdout:
        return None
    ruta, familias = r.stdout.split("\t", 1)
    # `fc-match` SIEMPRE devuelve algo: si no encuentra la familia pedida
    # entrega una sustituta. Sin esta comprobación mediríamos con la fuente
    # equivocada y el aviso de desbordamiento sería un número inventado.
    if familia.lower() not in familias.lower():
        return None
    return Path(ruta)


@lru_cache(maxsize=32)
def cargar(familia: str) -> MetricasDeFuente:
    ruta = localizar(familia)
    if ruta is None or not ruta.exists():
        raise FuenteNoDisponible(
            f"La familia «{familia}» no está instalada. Instálela con "
            "`make fonts-install`: sin ella el aviso de desbordamiento no es fiable."
        )
    f = TTFont(str(ruta), lazy=True)
    upm = f["head"].unitsPerEm
    cmap = f.getBestCmap()
    hmtx = f["hmtx"]
    anchos = {cp: hmtx[g][0] for cp, g in cmap.items()}
    hh = f["hhea"]
    interlineado = (hh.ascent - hh.descent + hh.lineGap) / upm
    f.close()
    return MetricasDeFuente(
        familia=familia, ruta=ruta, upm=upm, interlineado_em=interlineado, anchos=anchos
    )


def comprobar_familias(familias: tuple[str, ...] = FAMILIAS_REQUERIDAS) -> dict[str, bool]:
    """Qué familias hay y cuáles faltan. Se llama al arrancar el worker."""
    return {fam: localizar(fam) is not None for fam in familias}


def exigir_familias(familias: tuple[str, ...] = FAMILIAS_REQUERIDAS) -> None:
    """Falla el arranque si falta alguna familia declarada."""
    estado = comprobar_familias(familias)
    faltan = [f for f, ok in estado.items() if not ok]
    if faltan:
        raise FuenteNoDisponible(
            "Faltan familias corporativas: " + ", ".join(faltan) + ". Ejecute `make fonts-install`."
        )

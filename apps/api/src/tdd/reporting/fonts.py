"""Métricas tipográficas reales.

`[REQ]` La detección de textos que desbordan se apoya en medir, no en adivinar.
Este módulo carga las familias del informe instaladas en el sistema y expone su
anchura de avance real. Si una familia falta, **lo dice**: nunca mide en
silencio con una sustituta, porque un aviso calculado sobre otra fuente es peor
que no dar aviso.

## Por qué Montserrat, y no Segoe UI

`[REQ]` El cliente descarta Gotham y pide **Segoe UI, o Montserrat en su
defecto**. La aplicación web usa Segoe UI —está en la máquina de quien la abre y
ahí no hay nada que distribuir—; el **informe usa Montserrat**, y la razón es
esta línea de código: para medir hace falta el **fichero** de la fuente
instalado en el servidor.

Segoe UI es de Microsoft y viaja con Windows y con Office: no se puede instalar
en un contenedor Linux ni incrustar en un PPTX que se envía a un tercero.
Declararla en el informe y medirla con otra cosa es justo lo que este módulo
existe para impedir. Montserrat es **SIL OFL 1.1**: se instala con un paquete
del sistema (`fonts-montserrat`), se mide de verdad y se puede incrustar.

`[LIM]` Cambia el resultado, y está medido: la diapositiva de sistema pasa de
**4.405 caracteres con Gotham Light a 4.080 con Montserrat Light**, un 7,4 %
menos. Montserrat es más ancha. No es un problema del informe —el aviso de
desbordamiento se recalcula solo, porque sale de la fuente y no de una
constante— pero un texto que antes cabía justo, ahora no cabe.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont

#: Familias que el informe usa. El arranque del worker falla si falta alguna.
#:
#: Son los nombres **tal y como los publica la fuente**, que es lo que entiende
#: `fc-match` y lo que escribe PowerPoint. Montserrat reparte sus pesos en dos
#: sitios: «Montserrat» lleva dentro Regular y Bold, y cada peso que no es
#: ninguno de los dos tiene familia propia. Por eso aquí no aparece «Montserrat
#: Bold»: no existe como familia, y pedirla daría por ausente una fuente que
#: está instalada.
FAMILIAS_REQUERIDAS = (
    "Montserrat Light",
    "Montserrat",
    "Montserrat Medium",
    "Montserrat SemiBold",
    "Montserrat ExtraBold",
    "Montserrat Black",
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
    #
    # La comparación es **por nombre entero**, no por «contiene»: `%{family}`
    # trae la lista de nombres del fichero separados por comas, y con la
    # comparación laxa «Montserrat» daba por buena «Montserrat Alternates», que
    # es otra fuente —otras formas y otras anchuras— del mismo paquete.
    nombres = {n.strip().lower() for n in familias.split(",")}
    if familia.strip().lower() not in nombres:
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

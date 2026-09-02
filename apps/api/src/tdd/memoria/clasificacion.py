"""De la prosa de la memoria a los objetos del CAPEX `[REQ]`.

Ésta es la mitad que **no** se puede hacer con reglas, y conviene decir por qué
con el ejemplo exacto que lo demuestra. `MC.6 Instalaciones` de una memoria
real dice:

    «Acometida y centro de transformación, cuadros, LED, emergencia, fuerza,
    tierras y rayo; AF y ACS; climatización y ventilación de oficinas; PCI;
    redes separadas de pluviales y fecales; telecomunicaciones; y ascensor
    accesible de dos paradas.»

Una sola sección cuyos elementos caen en **seis capítulos distintos**:
Electricidad, Fontanería, HVAC, PCI activa, Telecomunicaciones y Transporte
vertical. Trocear por comas da doce fragmentos; saber que «tierras y rayo» es
electricidad y «AF y ACS» es fontanería es clasificación semántica.

Así que la arquitectura es la misma que la de la revisión documental, y por la
misma razón: **el proveedor está sin elegir**, esa decisión es de coste antes
que técnica, y no puede bloquear el resto ni obligar a rehacerlo después.

* `Clasificador` es el puerto. Fija lo que ningún proveedor puede saltarse.
* `PorSeccion` es el adaptador que hay hoy: **no lee prosa**. Usa la tabla de
  §5.9 para decir a qué capítulos toca cada sección, y lo declara.
* Cuando se elija proveedor, su adaptador se escribe aquí al lado y no se toca
  nada más.

`[REQ]` Todo lo que sale de aquí es **propuesta**. Va a la memoria, no al
CAPEX, y de ahí no pasa sin que alguien pulse el botón.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from tdd.memoria.extraccion import Seccion

#: Secciones que sí describen obra del activo. La memoria trae también agentes,
#: normativa y presupuesto, y clasificar eso produciría objetos que no son
#: partidas: «Real Decreto 314/2006» no es algo que se repare.
PREFIJOS_CONSTRUCTIVOS = ("MC", "MD.2", "MD.3")


@dataclass(frozen=True, slots=True)
class ObjetoPropuesto:
    """Un objeto que la memoria menciona, con el capítulo al que se propone.

    `evidencia` no es adorno: es el fragmento literal del documento del que
    salió. Es lo que permite a quien valida ir a la memoria y comprobarlo. Una
    propuesta sin respaldo es un acto de fe, y en una TDD eso no vale.
    """

    capex_chapter_code: str
    nombre: str
    evidencia: str
    seccion: str
    #: Entre 0 y 1, o `None` cuando el adaptador no sabe estimarla. `None` y
    #: cero no son lo mismo: el primero dice «no lo mido», el segundo «no me lo
    #: creo», y presentarlos igual engaña a quien decide.
    confianza: float | None = None


@dataclass
class Dictamen:
    """Lo propuesto, quién lo propuso y **si es de mentira**.

    `es_simulado` es obligatorio y no tiene valor por omisión permisivo: una
    clasificación simulada no puede pasar por una de verdad ni en la base ni en
    la pantalla.
    """

    proveedor: str
    es_simulado: bool
    objetos: list[ObjetoPropuesto] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)


class Clasificador(Protocol):
    """Qué se le pide a quien clasifique la prosa de una memoria.

    Lo que el puerto fija:

    * **Entra el texto de las secciones, no el documento entero.** El
      clasificador no ve la portada ni los datos personales del promotor: no
      los necesita, y no mandarlos es más barato y más prudente.
    * **Sale una propuesta con su evidencia**, nunca una escritura.
    * **El dictamen dice quién lo produjo y si es simulado.**
    """

    def clasificar(
        self, secciones: list[Seccion], capitulos: dict[str, str]
    ) -> Dictamen:  # pragma: no cover - es un Protocol
        """`capitulos` es `{código de capítulo: nombre}`, del catálogo vivo."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
#  El adaptador que hay hoy
# ─────────────────────────────────────────────────────────────────────────────

#: Los conectores con los que un redactor enumera. Se cortan también por «y»
#: final de lista, que es lo que separa el último elemento en castellano.
_SEPARADORES = re.compile(r"[;,]|\.\s|\sy\s(?=[a-záéíóúñ])")


@dataclass(frozen=True, slots=True)
class PorSeccion:
    """Reparte los objetos de cada sección **entre los capítulos que ésta toca**.

    `[LIM]` Esto **no clasifica**. Cuando una sección mapea a un solo capítulo
    —`MC.3 Sistema estructural` → `H01`— el resultado es correcto por
    construcción. Cuando mapea a varios —`MC.6` toca seis— no sabe cuál es cuál,
    y en vez de repartir al azar **lo dice**: propone los objetos en el primer
    capítulo de la sección y avisa de que hay que repasarlos.

    Es deliberadamente honesto en vez de deliberadamente listo. Un diccionario
    de palabras clave acertaría en esta memoria y fallaría en la siguiente
    escrita con otras palabras, y ese fallo no se vería: los objetos saldrían
    en el capítulo equivocado con aspecto de estar bien.
    """

    #: `{código de sección: [códigos de capítulo]}`, de la tabla de §5.9.
    mapa: dict[str, list[str]]

    def clasificar(self, secciones: list[Seccion], capitulos: dict[str, str]) -> Dictamen:
        dictamen = Dictamen(proveedor="por-seccion", es_simulado=True)
        dictamen.avisos.append(
            "Clasificación por sección, sin leer la prosa: los objetos se proponen en el "
            "primer capítulo al que toca su sección. Hay que repasarlos antes de aceptar."
        )

        for seccion in secciones:
            if not seccion.codigo.startswith(PREFIJOS_CONSTRUCTIVOS):
                continue
            destinos = [c for c in self.mapa.get(seccion.codigo, []) if c in capitulos]
            if not destinos:
                continue

            for fragmento in _SEPARADORES.split(seccion.cuerpo):
                nombre = _limpiar(fragmento)
                if not nombre:
                    continue
                dictamen.objetos.append(
                    ObjetoPropuesto(
                        capex_chapter_code=destinos[0],
                        nombre=nombre[:240],
                        evidencia=seccion.cuerpo[:500],
                        seccion=f"{seccion.codigo} {seccion.titulo}",
                        confianza=None,
                    )
                )

            if len(destinos) > 1:
                nombres = ", ".join(capitulos[c] for c in destinos)
                dictamen.avisos.append(
                    f"«{seccion.codigo} {seccion.titulo}» toca {len(destinos)} capítulos "
                    f"({nombres}). Todos sus objetos se han propuesto en el primero: "
                    "hay que repartirlos a mano."
                )
        return dictamen


#: Palabras que abren una frase y no son el nombre de nada.
_ARRANQUES = re.compile(r"^(?:y|e|o|u|con|en|de|del|la|el|los|las|un|una|se|que)\s+", re.I)


def _limpiar(fragmento: str) -> str:
    """Un fragmento de prosa convertido en algo que se pueda leer en una fila.

    Se descartan los muy cortos —«LED», «PCI» sueltos son siglas útiles pero no
    identifican una partida— y los muy largos, que son frases enteras y no
    objetos. El corte es un juicio, no una medida: está aquí en un sitio para
    poder discutirlo cuando alguien vea el resultado sobre memorias de verdad.
    """
    texto = " ".join(fragmento.split()).strip(" .;,:")
    texto = _ARRANQUES.sub("", texto)
    if not (4 <= len(texto) <= 120):
        return ""
    if not re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3}", texto):
        return ""
    return texto[0].upper() + texto[1:]

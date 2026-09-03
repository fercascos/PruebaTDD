"""Lectura determinista de una memoria técnica en PDF `[REQ]`.

**Sin IA y sin red.** Lo que se saca aquí son las dos tablas y el esqueleto de
epígrafes, que en una memoria redactada según el Código Técnico están donde
están. Escrito contra una memoria real —anonimizada— de un edificio
industrial-logístico, no contra un formato imaginado.

Qué sale, y por qué se puede sin modelo:

* **La tabla de portada.** Pares etiqueta/valor: Documento, Tipo de actuación,
  Emplazamiento, Promotor, Proyectista, Contratista, Fecha.
* **La tabla de superficies.** Pares concepto/valor: útil por planta, útil
  total, construida total, parcela, ocupación, urbanización exterior.
* **El esqueleto de epígrafes.** `MG`, `MD`, `MC.0`…`MC.7`, `MN`, más los
  bloques romanos. Es la estructura del CTE, y viene numerada.
* **Un puñado de números escritos en prosa**, y solo los que se dicen de una
  forma cerrada: «siete muelles de carga».

Qué **no** sale de aquí, y hay que decirlo aunque incomode: los objetos del
CAPEX. La memoria no los lista por capítulo; los enumera en prosa dentro de sus
propias secciones, y una sola —`MC.6 Instalaciones`— reparte sus elementos
entre seis capítulos distintos. Eso es clasificación semántica, no lectura de
tabla, y vive en `clasificacion.py`.

`[LIM]` Escrito contra **un** ejemplo. Puedo afirmar que lee ése; no puedo
afirmar que generalice. Por eso los sinónimos de las etiquetas son datos
—`VOCABULARIO`— y no expresiones repartidas por el código: la segunda memoria
que llegue va a traer otras palabras, y corregirlo tiene que ser cambiar una
línea de tabla, no salir a buscar por dónde.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

#: Etiqueta de la memoria → campo del activo. En claro y en un solo sitio.
#:
#: Las claves se comparan **normalizadas** —sin tildes, en minúsculas y sin
#: espacios de más—, así que «Superficie útil total», «SUPERFICIE UTIL TOTAL» y
#: «Útil total» encajan sin necesidad de una entrada por cada forma de
#: escribirlo. Lo que sí necesita entrada propia es cada sinónimo de verdad.
VOCABULARIO: dict[str, str] = {
    # Superficies
    "util total": "usable_area_sqm",
    "superficie util total": "usable_area_sqm",
    "construida total": "total_built_sqm",
    "superficie construida total": "total_built_sqm",
    "parcela": "plot_area_sqm",
    "superficie de parcela": "plot_area_sqm",
    # `[REQ]` «Ocupación» es la palabra de la memoria para lo que el modelo
    # llama `occupied_area_sqm`. Se descubrió leyendo una de verdad.
    "ocupacion": "occupied_area_sqm",
    "superficie ocupada": "occupied_area_sqm",
    "urbanizacion exterior": "urbanised_area_sqm",
    "superficie urbanizada": "urbanised_area_sqm",
    "superficie alquilable": "lettable_area_sqm",
    "altura maxima": "max_height_m",
    "altura maxima del edificio": "max_height_m",
    # Portada
    "promotor": "developer",
    "emplazamiento": "address_line",
    "referencia catastral": "cadastral_reference",
}

#: Etiquetas de la portada que NO son datos del activo. Se leen igual y se
#: devuelven aparte: el consultor quiere verlas al validar aunque la ficha del
#: edificio no tenga dónde guardarlas.
PORTADA_INFORMATIVA = frozenset(
    {"documento", "tipo de actuacion", "proyectista", "contratista", "fecha"}
)

#: Una fila de superficie por planta: «Útil planta baja», «Útil sótano -1».
_PLANTA = re.compile(r"^util\s+(?:de\s+)?(planta\s+.+|altillo|sotano.*|entreplanta.*|cubierta)$")

#: El número de planta, para poder ordenarlas. Lo que no encaje va sin nivel y
#: se ordena por el orden en el que aparece en el documento, que es el del
#: propio redactor y suele ser el bueno.
_NIVELES = {
    "baja": 0,
    "primera": 1,
    "segunda": 2,
    "tercera": 3,
    "cuarta": 4,
    "quinta": 5,
    "sexta": 6,
}

#: Los números que la memoria escribe con letra. Solo hasta doce: más allá, un
#: redactor pone la cifra, y una tabla larga de numerales invita a acertar por
#: casualidad en frases que no hablaban de eso.
_CARDINALES = {
    "un": 1,
    "una": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
}

#: Epígrafes del Código Técnico: `MG.1`, `MC.6`, `MN`…
_EPIGRAFE = re.compile(r"^((?:MG|MD|MC|MN|ME)(?:\.\d+)?)\.?\s+(\S.*)$", re.M)


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con los espacios colapsados.

    Es lo que permite que el vocabulario tenga una entrada por concepto y no
    una por cada forma de teclearlo.
    """
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", sin_tildes).strip().lower()


def _decimal(bruto: str) -> Decimal | None:
    """«6.023 m²» → `Decimal("6023")`. Devuelve `None` si no hay número.

    El punto es separador de millares en castellano y la coma, decimal. Al
    revés —como lo lee `Decimal` por defecto— «12.410 m²» se convertiría en
    doce metros y pico, y esa cifra pasaría desapercibida en una ficha.
    """
    encontrado = re.search(r"-?[\d.]+(?:,\d+)?", bruto.replace(" ", ""))
    if not encontrado:
        return None
    numero = encontrado.group(0).replace(".", "").replace(",", ".")
    try:
        return Decimal(numero)
    except InvalidOperation:  # pragma: no cover - la expresión ya lo acota
        return None


@dataclass(frozen=True, slots=True)
class Planta:
    label: str
    level: int | None
    usable_area_sqm: Decimal | None


@dataclass(frozen=True, slots=True)
class Seccion:
    """Un epígrafe de la memoria con su texto. Alimenta la clasificación."""

    codigo: str
    titulo: str
    cuerpo: str


@dataclass
class Extraccion:
    """Lo que se ha podido leer, y lo que no.

    `avisos` no es decoración: es la lista de cosas que el consultor tiene que
    mirar a mano al validar. Una extracción que solo dice lo que encontró deja
    creer que lo demás no estaba.
    """

    propuesta: dict[str, Any] = field(default_factory=dict)
    plantas: list[Planta] = field(default_factory=list)
    secciones: list[Seccion] = field(default_factory=list)
    #: Etiquetas de portada que no son campos del activo, para enseñarlas.
    informativos: dict[str, str] = field(default_factory=dict)
    #: Etiquetas leídas que el vocabulario no conoce. Se declaran en vez de
    #: descartarse en silencio: es como se descubre el sinónimo que falta.
    desconocidos: dict[str, str] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    #: Campo del activo → la celda **tal y como está escrita en el documento**.
    #:
    #: `[REQ]` Literal, no reconstruida. Quien valida tiene que poder comparar
    #: con el PDF; «`plot_area_sqm` = 12410» es lo que la máquina creyó leer, y
    #: si la máquina se equivocó, repetir su lectura no lo delata. «Parcela |
    #: 12.410 m²» sí.
    #:
    #: `[LIM]` Lo de las tablas es literal. Lo que sale de la prosa —muelles,
    #: plazas— viene del texto normalizado y va marcado como tal: localiza el
    #: párrafo, no lo cita.
    evidencias: dict[str, str] = field(default_factory=dict)


def _anonimizado(valor: str) -> bool:
    """`[UBICACIÓN DEL ACTIVO]` no es un dato: es un hueco.

    Un documento anonimizado —o uno a medio rellenar— trae marcadores entre
    corchetes. Volcarlos al activo llenaría la ficha de texto que parece un
    dato y no lo es.
    """
    return bool(re.fullmatch(r"\[.*\]", valor.strip()))


def _leer_tabla(filas: list[list[str | None]], destino: Extraccion) -> None:
    for fila in filas:
        celdas = [(c or "").strip() for c in fila if c is not None]
        if len(celdas) < 2 or not celdas[0]:
            continue
        etiqueta, valor = celdas[0], celdas[1]
        clave = normalizar(etiqueta)
        if clave in {"concepto", "superficie aproximada"}:
            continue  # la cabecera de la tabla

        literal = f"{etiqueta.strip()} | {valor.strip()}"

        if planta := _PLANTA.match(clave):
            nombre = planta.group(1)
            nivel = next((n for p, n in _NIVELES.items() if p in nombre), None)
            destino.plantas.append(
                Planta(label=etiqueta.strip(), level=nivel, usable_area_sqm=_decimal(valor))
            )
            destino.evidencias[f"planta:{etiqueta.strip()}"] = literal
            continue

        if _anonimizado(valor):
            destino.avisos.append(
                f"«{etiqueta}» viene anonimizado en el documento ({valor}): hay que "
                "teclearlo a mano."
            )
            continue

        if campo := VOCABULARIO.get(clave):
            numero = _decimal(valor)
            destino.propuesta[campo] = str(numero) if numero is not None else valor.strip()
            destino.evidencias[campo] = literal
        elif clave in PORTADA_INFORMATIVA:
            destino.informativos[etiqueta.strip()] = valor.strip()
        else:
            destino.desconocidos[etiqueta.strip()] = valor.strip()


def _leer_prosa(texto: str, destino: Extraccion) -> None:
    """Los pocos números que la memoria dice con palabras, y solo ésos.

    `[REC]` La tentación es sacar de aquí todo lo que parezca un dato. No se
    hace: una expresión que caza «siete muelles de carga» y también «siete
    metros de fachada» convierte la extracción en una fuente de errores con
    aspecto de precisión.
    """
    plano = normalizar(texto)
    cardinales = "|".join(_CARDINALES)
    for campo, sustantivo in (
        ("loading_docks", r"muelles?\s+de\s+carga"),
        ("parking_spaces", r"plazas?\s+de\s+aparcamiento"),
    ):
        m = re.search(rf"\b(\d+|{cardinales})\s+{sustantivo}", plano)
        if m is None:
            continue
        bruto = m.group(1)
        destino.propuesta[campo] = int(bruto) if bruto.isdigit() else _CARDINALES[bruto]
        # La frase con contexto alrededor: es lo que hay que releer para decidir
        # si «siete muelles de carga» hablaba de este edificio o de otro.
        #
        # `[LIM]` Sale del texto **normalizado** —minúsculas y sin tildes—, no
        # del original. La expresión se aplica sobre él y las posiciones no se
        # corresponden carácter a carácter con el PDF. Sirve para localizar el
        # párrafo, que es para lo que se usa; no es una cita literal, y por eso
        # no se presenta como tal.
        destino.evidencias[campo] = (
            "(texto normalizado) …" + plano[max(0, m.start() - 60) : m.end() + 60].strip() + "…"
        )


def _leer_secciones(texto: str, destino: Extraccion) -> None:
    encontrados = list(_EPIGRAFE.finditer(texto))
    for n, actual in enumerate(encontrados):
        fin = encontrados[n + 1].start() if n + 1 < len(encontrados) else len(texto)
        cuerpo = texto[actual.end() : fin]
        # El pie de página se repite en cada hoja y ensucia el cuerpo.
        cuerpo = re.sub(r"Memoria t[eé]cnica[^\n]*\n\s*P[áa]gina \d+", " ", cuerpo)
        destino.secciones.append(
            Seccion(
                codigo=actual.group(1),
                titulo=actual.group(2).strip(),
                cuerpo=" ".join(cuerpo.split()),
            )
        )


def leer(pdf: bytes) -> Extraccion:
    """Lee una memoria técnica en PDF. **No escribe nada en ningún sitio.**

    Devuelve una propuesta que después alguien tiene que aceptar con el botón,
    igual que si la hubiera tecleado. Esta función no sabe qué es un activo.
    """
    import io

    import pdfplumber
    from pdfminer.high_level import extract_text

    destino = Extraccion()
    try:
        with pdfplumber.open(io.BytesIO(pdf)) as documento:
            for pagina in documento.pages:
                for tabla in pagina.extract_tables():
                    _leer_tabla(tabla, destino)
    except Exception as exc:  # noqa: BLE001 — un PDF roto no puede tumbar la API
        destino.avisos.append(
            f"No se han podido leer las tablas del documento ({type(exc).__name__}). "
            "Los datos del edificio hay que teclearlos a mano."
        )

    try:
        texto = extract_text(io.BytesIO(pdf))
    except Exception as exc:  # noqa: BLE001
        destino.avisos.append(
            f"No se ha podido leer el texto del documento ({type(exc).__name__})."
        )
        return destino

    if len(texto.strip()) < 200:
        # Un PDF escaneado da tablas vacías y cuatro caracteres sueltos. Decirlo
        # es la diferencia entre «no había datos» y «no sé leer este fichero».
        destino.avisos.append(
            "El documento apenas tiene texto: probablemente sea un escaneado. "
            "Haría falta OCR, que no está construido."
        )
        return destino

    _leer_prosa(texto, destino)
    _leer_secciones(texto, destino)

    if not destino.propuesta:
        destino.avisos.append(
            "No se ha reconocido ningún dato del edificio. Puede que la memoria use "
            "otras etiquetas: las que no se reconocen salen en «desconocidos»."
        )
    if destino.desconocidos:
        destino.avisos.append(
            f"{len(destino.desconocidos)} etiquetas leídas no están en el vocabulario "
            f"({', '.join(sorted(destino.desconocidos)[:5])}). No se han perdido: hay "
            "que decidir a qué campo corresponden."
        )
    return destino

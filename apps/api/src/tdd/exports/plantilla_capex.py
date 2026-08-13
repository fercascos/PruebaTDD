"""Relleno de la plantilla CAPEX DDT del cliente `[REQ]` P-31.

**Se rellena el fichero del cliente, no se reconstruye.** La plantilla lleva
gráficos, tablas dinámicas, segmentaciones, formato condicional avanzado,
validaciones de datos en cascada y dos logotipos. Volver a escribirla con
`openpyxl` destruye 33 de sus 87 partes —se comprobó— y devolvería al cliente
una versión rota de su propia hoja. Así que aquí se abre el `.xltm` como el ZIP
que es, se reescriben **solo las celdas que se rellenan** y todo lo demás se
copia byte a byte.

El precio de esa decisión es que hay que conocer la geometría de la hoja, y por
eso está escrita abajo en `GEOMETRIA`. Se comprobó que las plantillas española e
inglesa **coinciden celda a celda**: mismas filas, mismas columnas, solo cambian
las etiquetas. Por eso hay una sola rutina y dos ficheros.

`[LIM]` Cada categoría admite **10 actuaciones**. Es lo que trae la plantilla.
Una undécima no cabe: insertar filas obligaría a recalcular los rangos de los
subtotales, la fórmula de HARD COSTS —que lista las filas una a una—, las
celdas combinadas, los rangos de formato condicional y los orígenes de las
tablas dinámicas. En vez de arriesgar eso, `comprobar_cabida()` avisa **antes**
de exportar diciendo qué categoría se pasa y por cuánto. Ninguna actuación se
descarta en silencio.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from io import BytesIO
from pathlib import Path
from typing import Any

from lxml import etree

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML_ESPACIO = "{http://www.w3.org/XML/1998/namespace}space"

#: De plantilla con macros a libro normal. Se comprobó que el fichero **no
#: lleva `vbaProject.bin`**: la extensión es de macros pero no hay ninguna, así
#: que convertir a `.xlsx` no pierde nada y evita que el correo lo bloquee.
CT_PLANTILLA = "application/vnd.ms-excel.template.macroEnabled.main+xml"
CT_LIBRO = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"

PLANTILLAS = Path(__file__).resolve().parent / "plantillas"
FICHERO = {"es": "capex_ddt_es.xltm", "en": "capex_ddt_en.xltm"}


class Idioma(StrEnum):
    """Los idiomas para los que hay plantilla.

    Enumeración y no `str` para que la API lo publique en el OpenAPI y rechace
    con un `422` legible lo que no exista, en vez de reventar al abrir el
    fichero. Añadir un idioma es añadir una plantilla y una línea aquí.
    """

    ES = "es"
    EN = "en"


def _q(etiqueta: str) -> str:
    return f"{{{NS}}}{etiqueta}"


# ─────────────────────────────────────────────────────────────────────────────
#  Geometría de la hoja «CapEx»
# ─────────────────────────────────────────────────────────────────────────────
#
# Derivada del propio fichero y verificada contra las dos plantillas: los 20
# bloques ocupan exactamente las mismas filas en español y en inglés.

FILAS_POR_BLOQUE = 10


@dataclass(frozen=True, slots=True)
class Bloque:
    """Un tramo de la hoja donde caben actuaciones de una misma categoría."""

    #: Código de `capex_code` de nivel 2 al que corresponde el bloque.
    codigo: str
    #: Fila del subtotal, que es también donde la plantilla escribe el nombre.
    subtotal: int
    #: Primera fila **que puede escribir la aplicación**.
    primera: int
    ultima: int
    #: Cuántas filas de la cabeza del bloque se reserva la plantilla para sus
    #: propias líneas de porcentaje. La aplicación empieza después.
    reservadas: int = 0

    @property
    def primera_de_la_hoja(self) -> int:
        """Dónde empieza el bloque **en la hoja**, líneas de plantilla incluidas.

        No es lo mismo que `primera`: el subtotal suma el bloque entero, así que
        comprobarlo contra la zona escribible daría un falso positivo.
        """
        return self.primera - self.reservadas

    @property
    def cabida(self) -> int:
        return self.ultima - self.primera + 1


#: `codigo de capex_code` → tramo de la hoja.
GEOMETRIA: tuple[Bloque, ...] = (
    *(
        Bloque(f"HC.H{n:02d}", 13 + 12 * (n - 1), 14 + 12 * (n - 1), 23 + 12 * (n - 1))
        for n in range(1, 16)
    ),
    Bloque("MA.General", 194, 195, 204),
    Bloque("ESG.General", 207, 208, 217),
    # `[REQ]` Los bloques por porcentaje **empiezan después de las líneas que
    # trae la plantilla**. `SC.S01` ocupa 221-223 con los honorarios de
    # proyectos, dirección de ejecución y project monitoring; `SC.S02` la 233
    # con seguridad y salud; `SC.S03` las 245-247 con ECLU, licencia de obras y
    # otras licencias. Son fórmulas —un tanto por ciento de los hard costs— y
    # escribir encima una actuación de la aplicación las borraría: el importe
    # dejaría de recalcularse y nadie lo notaría hasta cuadrar a mano.
    Bloque("SC.S01", 220, 224, 230, 3),
    Bloque("SC.S02", 232, 234, 242, 1),
    Bloque("SC.S03", 244, 248, 254, 3),
    # Añadidos por `tools/anadir_bloques_plantillas.py`: la plantilla declaraba
    # los dos tipos de coste en «00 Datos Categorías» pero no tenía dónde
    # escribirlos. Van al final de la hoja, sobre filas que estaban vacías.
    # `[LIM]` Operativos tiene dos categorías y **comparten el bloque**: sus
    # veinte filas son las mismas diez, porque la plantilla no da más. Se
    # controla con `comprobar_cabida`, que las cuenta juntas.
    Bloque("OP.C01", 257, 258, 267),
    Bloque("OP.C02", 257, 258, 267),
    # La 271 es la línea de imprevistos que calcula la plantilla desde el
    # porcentaje de «00 Datos Activo». La aplicación escribe a partir de la 272.
    Bloque("IMP.General", 270, 272, 280, 1),
)
POR_CODIGO: dict[str, Bloque] = {b.codigo: b for b in GEOMETRIA}

#: Columnas de una fila de actuación.
COL_OBJETO = "E"
COL_ZONA = "F"
COL_DESCRIPCION = "G"
COL_RIESGO = "H"
COL_COMENTARIOS = "I"
COL_CONCEPTO = "P"
COL_RECUPERABLE = "Q"
COL_MEDICION = "S"
COL_UDS = "T"
COL_PRECIO_UD = "U"
#: Los cinco plazos, en el orden de la plantilla.
COL_PLAZO: dict[str, str] = {
    "CORTO": "J",
    "MEDIO": "K",
    "LARGO": "L",
    "MEJORAS": "M",
    "OTRO": "N",
}

#: Hoja «00 Datos Activo»: dónde va cada dato del encargo.
CELDA_ACTIVO = {
    "nombre": "C5",
    "direccion": "C6",
    "fecha": "C7",
    "ano_construccion": "C8",
    "superficie_parcela": "C10",
    "superficie_total": "C11",
    "superficie_almacen": "C12",
    "superficie_oficinas": "C13",
    "altura_almacen": "C14",
    "tipo_edificio": "C16",
}

#: Porcentajes de soft costs. `[REQ]` Decisión del cliente: **manda esta hoja**,
#: no los números escritos a mano en la hoja `CapEx`. Quedan editables.
CELDA_PORCENTAJE = {
    "proyectos_y_df": "C38",
    "direccion_de_ejecucion": "C39",
    "project_monitoring": "C40",
    "seguridad_y_salud": "C41",
    "honorarios_eclu": "C42",
    "licencia_de_obras": "C43",
    "otras_licencias": "C44",
    "imprevistos": "C45",
}


# ─────────────────────────────────────────────────────────────────────────────
#  Escritura de celdas
# ─────────────────────────────────────────────────────────────────────────────


class CeldaInexistente(KeyError):
    """La plantilla cambió de forma y la celda que se busca ya no está.

    Es un error de programación, no de datos: se prefiere reventar a escribir
    en el sitio equivocado y devolver una hoja que parece correcta.
    """


def _celda(datos: etree._Element, ref: str) -> etree._Element:
    numero = int(re.search(r"\d+", ref).group(0))
    for fila in datos.iterfind(_q("row")):
        if int(fila.get("r", "0")) != numero:
            continue
        for celda in fila:
            if celda.get("r") == ref:
                return celda
        raise CeldaInexistente(f"la fila {numero} existe pero no tiene la celda {ref}")
    raise CeldaInexistente(f"la plantilla no tiene la fila {numero}")


def escribir(datos: etree._Element, ref: str, valor: Any) -> None:
    """Escribe en una celda que ya existe, **conservando su estilo**.

    El atributo `s` lleva el índice de formato: quitarlo dejaría la celda sin
    borde, sin color y sin formato de número. Se vacía el contenido —fórmula y
    valor cacheado— y se pone el nuevo.
    """
    celda = _celda(datos, ref)
    for hijo in list(celda):
        celda.remove(hijo)
    celda.attrib.pop("t", None)

    if valor is None or valor == "":
        return
    if isinstance(valor, str) and valor.startswith("="):
        etree.SubElement(celda, _q("f")).text = valor[1:]
        return
    if isinstance(valor, Decimal):
        valor = float(valor)
    if isinstance(valor, bool):  # antes que int: bool es subclase de int
        valor = str(valor)
    if isinstance(valor, (int, float)):
        etree.SubElement(celda, _q("v")).text = repr(valor)
        return
    # Cadena en línea: no toca `sharedStrings.xml`, que se copia intacto.
    celda.set("t", "inlineStr")
    texto = etree.SubElement(etree.SubElement(celda, _q("is")), _q("t"))
    texto.text = str(valor)
    texto.set(XML_ESPACIO, "preserve")


# ─────────────────────────────────────────────────────────────────────────────
#  Lo que se escribe
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Actuacion:
    """Una fila de la hoja. Los importes van por plazo, como en la plantilla."""

    #: Código de `capex_code` de nivel 2: decide en qué bloque cae.
    categoria: str
    objeto: str | None = None
    zona: str | None = None
    descripcion: str = ""
    riesgo: str | None = None
    comentarios: str | None = None
    #: `{código de plazo: importe}`. Una actuación normal trae **una** entrada.
    importes: dict[str, Decimal] = field(default_factory=dict)
    concepto: str | None = None
    #: «SI» / «NO» / «N.A.», tal como lo espera el desplegable de la plantilla.
    recuperable: str | None = None
    medicion: str | None = None
    unidades: Decimal | None = None
    precio_unitario: Decimal | None = None


@dataclass(frozen=True, slots=True)
class Encargo:
    """La cabecera que va a «00 Datos Activo»."""

    nombre: str
    direccion: str | None = None
    fecha: str | None = None
    ano_construccion: int | None = None
    superficie_parcela: Decimal | None = None
    superficie_total: Decimal | None = None
    superficie_almacen: Decimal | None = None
    superficie_oficinas: Decimal | None = None
    altura_almacen: Decimal | None = None
    #: Uno de los seis de la plantilla: decide qué zonas ofrece el desplegable.
    tipo_edificio: str | None = None


@dataclass(frozen=True, slots=True)
class Desbordamiento:
    categoria: str
    caben: int
    hay: int

    @property
    def sobran(self) -> int:
        return self.hay - self.caben


def comprobar_cabida(actuaciones: list[Actuacion]) -> list[Desbordamiento]:
    """Qué categorías no caben en la plantilla. Se llama **antes** de exportar.

    Devolver la lista en vez de recortar es deliberado: una actuación que
    desaparece de la hoja que se manda al cliente es exactamente el fallo que
    nadie detecta hasta que alguien suma a mano.
    """
    # Se cuenta por BLOQUE, no por categoría: `OP.C01` y `OP.C02` comparten
    # las mismas diez filas —la plantilla no da más—, así que once actuaciones
    # repartidas entre las dos tampoco caben.
    cuenta: dict[int, int] = {}
    etiquetas: dict[int, list[str]] = {}
    for a in actuaciones:
        bloque = POR_CODIGO.get(a.categoria)
        if bloque is None:
            continue
        cuenta[bloque.primera] = cuenta.get(bloque.primera, 0) + 1
        if a.categoria not in etiquetas.setdefault(bloque.primera, []):
            etiquetas[bloque.primera].append(a.categoria)
    por_primera = {b.primera: b for b in GEOMETRIA}
    return [
        Desbordamiento(" + ".join(sorted(etiquetas[primera])), por_primera[primera].cabida, n)
        for primera, n in sorted(cuenta.items())
        if n > por_primera[primera].cabida
    ]


class NoCabe(ValueError):
    """Se intentó exportar con más actuaciones de las que admite la plantilla."""


# ─────────────────────────────────────────────────────────────────────────────
#  Exportación
# ─────────────────────────────────────────────────────────────────────────────


def ruta_de_hoja(zf: zipfile.ZipFile, posicion: int) -> str:
    """Ruta de la hoja dentro del ZIP, resuelta **por posición**.

    Por posición y no por nombre porque el nombre cambia con el idioma —«00
    Datos Activo» / «00 Asset Data»— y el orden no: se comprobó que las dos
    plantillas declaran las siete hojas en la misma secuencia.
    """
    libro = zf.read("xl/workbook.xml").decode("utf-8")
    relaciones = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    destinos = dict(re.findall(r'Id="([^"]+)"[^>]*Target="(worksheets/[^"]+)"', relaciones))
    hojas = re.findall(r'<sheet name="[^"]+"[^>]*r:id="([^"]+)"', libro)
    try:
        return "xl/" + destinos[hojas[posicion]]
    except (IndexError, KeyError) as e:  # pragma: no cover - plantilla corrupta
        raise CeldaInexistente(f"la plantilla no tiene hoja en la posición {posicion}") from e


#: Posición de las dos hojas que se rellenan, contando desde 0.
POS_ACTIVO = 2  # «00 Datos Activo» / «00 Asset Data»
POS_CAPEX = 4  # «CapEx» en los dos idiomas


def generar(
    encargo: Encargo,
    actuaciones: list[Actuacion],
    *,
    idioma: str = "es",
    porcentajes: dict[str, Decimal] | None = None,
) -> bytes:
    """Devuelve el `.xlsx` relleno.

    `[REQ]` Los soft costs se toman de «00 Datos Activo» y las filas de la hoja
    `CapEx` pasan a **referenciar** esa hoja en vez de llevar el porcentaje
    escrito a mano, que es lo que decidió el cliente. Así cambiarlo una vez lo
    cambia en todas las líneas.
    """
    if idioma not in FICHERO:
        raise ValueError(f"idioma no soportado: {idioma!r}. Hay plantilla para {sorted(FICHERO)}")
    if sobran := comprobar_cabida(actuaciones):
        detalle = ", ".join(f"{d.categoria}: {d.hay} de {d.caben}" for d in sobran)
        raise NoCabe(f"La plantilla no admite tantas actuaciones por categoría ({detalle})")

    origen = PLANTILLAS / FICHERO[idioma]
    with zipfile.ZipFile(origen) as zf:
        nombres = zf.namelist()
        partes = {n: zf.read(n) for n in nombres}
        ruta_activo = ruta_de_hoja(zf, POS_ACTIVO)
        ruta_capex = ruta_de_hoja(zf, POS_CAPEX)

    partes[ruta_activo] = _rellenar_activo(partes[ruta_activo], encargo, porcentajes)
    partes[ruta_capex] = _rellenar_capex(partes[ruta_capex], actuaciones)

    libro = partes["xl/workbook.xml"].decode("utf-8")
    # Los valores cacheados de las fórmulas que dependen de lo escrito ya no
    # valen. Sin esto Excel enseñaría los ceros de la plantilla en blanco.
    libro = re.sub(r"<calcPr[^>]*?/>", '<calcPr calcId="191029" fullCalcOnLoad="1"/>', libro)
    partes["xl/workbook.xml"] = libro.encode("utf-8")
    partes["[Content_Types].xml"] = partes["[Content_Types].xml"].replace(
        CT_PLANTILLA.encode(), CT_LIBRO.encode()
    )

    salida = BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as destino:
        for n in nombres:  # se conserva el orden original del ZIP
            destino.writestr(n, partes[n])
    return salida.getvalue()


def _arbol(bruto: bytes) -> tuple[etree._Element, etree._Element]:
    raiz = etree.fromstring(bruto)
    datos = raiz.find(_q("sheetData"))
    if datos is None:
        raise CeldaInexistente("la hoja no tiene sheetData")
    return raiz, datos


def _serializar(raiz: etree._Element) -> bytes:
    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)


def _rellenar_activo(
    bruto: bytes, encargo: Encargo, porcentajes: dict[str, Decimal] | None
) -> bytes:
    raiz, datos = _arbol(bruto)
    for campo, ref in CELDA_ACTIVO.items():
        escribir(datos, ref, getattr(encargo, campo))
    for campo, ref in CELDA_PORCENTAJE.items():
        if porcentajes and campo in porcentajes:
            escribir(datos, ref, porcentajes[campo])
    return _serializar(raiz)


def _rellenar_capex(bruto: bytes, actuaciones: list[Actuacion]) -> bytes:
    raiz, datos = _arbol(bruto)
    # La cuenta va por BLOQUE y no por categoría: dos categorías que comparten
    # tramo —`OP.C01` y `OP.C02`— tienen que seguir la misma fila, o la segunda
    # empezaría otra vez por arriba y machacaría a la primera.
    siguiente: dict[int, int] = {}

    for a in actuaciones:
        bloque = POR_CODIGO.get(a.categoria)
        if bloque is None:
            raise CeldaInexistente(
                f"la plantilla no tiene bloque para la categoría {a.categoria!r}"
            )
        fila = siguiente.get(bloque.primera, bloque.primera)
        siguiente[bloque.primera] = fila + 1

        escribir(datos, f"{COL_OBJETO}{fila}", a.objeto)
        escribir(datos, f"{COL_ZONA}{fila}", a.zona)
        escribir(datos, f"{COL_DESCRIPCION}{fila}", a.descripcion)
        escribir(datos, f"{COL_RIESGO}{fila}", a.riesgo)
        escribir(datos, f"{COL_COMENTARIOS}{fila}", a.comentarios)
        escribir(datos, f"{COL_CONCEPTO}{fila}", a.concepto)
        escribir(datos, f"{COL_RECUPERABLE}{fila}", a.recuperable)
        escribir(datos, f"{COL_MEDICION}{fila}", a.medicion)
        escribir(datos, f"{COL_UDS}{fila}", a.unidades)
        escribir(datos, f"{COL_PRECIO_UD}{fila}", a.precio_unitario)
        for plazo, columna in COL_PLAZO.items():
            escribir(datos, f"{columna}{fila}", a.importes.get(plazo))

    return _serializar(raiz)

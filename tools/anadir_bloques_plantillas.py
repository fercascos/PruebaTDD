#!/usr/bin/env python3
"""Añade a la hoja `CapEx` los bloques de **Operativos** e **Imprevistos**.

Las dos plantillas declaran esos tipos de coste en «00 Datos Categorías» pero
**la hoja `CapEx` no tiene ninguna fila donde escribirlos**: solo hay 20
bloques —15 de Hard Costs, Medioambiental, ESG y los 3 de Soft Costs—. Una
actuación clasificada como Operativos no tenía sitio, y `Imprevistos` existía
únicamente como un porcentaje suelto en «00 Datos Activo»!C45.

**Se añaden al final, no se insertan.** Las filas 255 en adelante están vacías,
así que los bloques nuevos van detrás de la última usada. Es lo que hace esto
viable: al no desplazarse ninguna fila existente, ninguna fórmula, celda
combinada, regla de formato condicional ni origen de tabla dinámica cambia de
sitio. Insertar en medio habría obligado a recalcular todo eso a mano.

Cada bloque se **clona del medioambiental** —sección, subtotal y diez filas de
datos— para heredar sus estilos celda a celda, y luego se le cambia lo propio.
Las referencias de fila que apuntan dentro del bloque se desplazan; las que
apuntan fuera, como `$O$12`, no se tocan: es la diferencia entre un subtotal
que suma sus filas y uno que suma las del vecino.

`Imprevistos` se monta como los soft costs, con su importe calculado a partir
del porcentaje de «00 Datos Activo»!C45, porque es como lo tenía pensado la
plantilla: un tanto por ciento de los hard costs, no una lista de actuaciones.

Uso:  python3 tools/anadir_bloques_plantillas.py [--check]
"""

from __future__ import annotations

import argparse
import copy
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLAS = RAIZ / "apps" / "api" / "src" / "tdd" / "exports" / "plantillas"
FICHEROS = ("capex_ddt_es.xltm", "capex_ddt_en.xltm")

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML_ESPACIO = "{http://www.w3.org/XML/1998/namespace}space"
POS_CAPEX = 4

#: El bloque que se clona: sección, subtotal y diez filas de datos.
MODELO_SECCION = 193
MODELO_SUBTOTAL = 194
MODELO_PRIMERA = 195
MODELO_ULTIMA = 204
FILAS_DE_DATOS = MODELO_ULTIMA - MODELO_PRIMERA + 1


@dataclass(frozen=True, slots=True)
class Bloque:
    """Un bloque nuevo. `seccion` es su primera fila en la hoja destino."""

    seccion: int
    titulo_es: str
    titulo_en: str
    #: Lo que va en la columna «Tipo de Coste» de sus filas de datos.
    tipo_es: str
    tipo_en: str
    #: Código corto de la columna «Item». Se hereda del modelo si no se pone, y
    #: el modelo es el medioambiental: sin esto las filas nuevas dirían «M».
    item: str = ""
    #: Lo que va en «Categoría». Vacío = lo elige el usuario del desplegable.
    categoria: str = ""
    #: Solo Imprevistos: se calcula como un % de los hard costs.
    porcentaje_desde: str = ""
    etiqueta_es: str = ""
    etiqueta_en: str = ""


BLOQUES = (
    Bloque(
        seccion=256,
        titulo_es="OPERATIVOS",
        titulo_en="OPERATING",
        tipo_es="Operativos",
        tipo_en="Operating",
        item="OP",
        # Dos categorías —Consumos Obra y Limpieza—, así que la celda se deja
        # en blanco y la elige el desplegable en cascada.
        categoria="",
    ),
    Bloque(
        seccion=269,
        titulo_es="IMPREVISTOS",
        titulo_en="CONTINGENCIES",
        tipo_es="Imprevistos",
        tipo_en="Contingencies",
        item="IMP",
        categoria="General",
        porcentaje_desde="C45",
        etiqueta_es="Imprevistos",
        etiqueta_en="Contingencies",
    ),
)

#: Fila del TOTAL general y su fórmula, que debe incluir los bloques nuevos.
FILA_TOTAL = 11
COLUMNAS_PLAZO = "JKLMN"


def _q(t: str) -> str:
    return f"{{{NS}}}{t}"


def _ruta(zf: zipfile.ZipFile, posicion: int) -> str:
    libro = zf.read("xl/workbook.xml").decode("utf-8")
    rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    destinos = dict(re.findall(r'Id="([^"]+)"[^>]*Target="(worksheets/[^"]+)"', rels))
    hojas = re.findall(r'<sheet name="[^"]+"[^>]*r:id="([^"]+)"', libro)
    return "xl/" + destinos[hojas[posicion]]


def _desplazar(texto: str, delta: int, desde: int, hasta: int) -> str:
    """Suma `delta` a las filas de `texto` que caen dentro de `[desde, hasta]`.

    Las de fuera se dejan intactas: `$O$12` apunta al total de hard costs y
    tiene que seguir apuntando ahí desde el bloque nuevo.
    """

    def sustituir(m: re.Match[str]) -> str:
        fila = int(m.group(2))
        return f"{m.group(1)}{fila + delta}" if desde <= fila <= hasta else m.group(0)

    return re.sub(r"(\$?[A-Z]{1,3}\$?)(\d+)", sustituir, texto)


def _texto_en(celda: etree._Element, valor: str) -> None:
    for hijo in list(celda):
        celda.remove(hijo)
    celda.attrib.pop("t", None)
    if valor == "":
        return
    celda.set("t", "inlineStr")
    t = etree.SubElement(etree.SubElement(celda, _q("is")), _q("t"))
    t.text = valor
    t.set(XML_ESPACIO, "preserve")


def _formula(celda: etree._Element, valor: str) -> None:
    for hijo in list(celda):
        celda.remove(hijo)
    celda.attrib.pop("t", None)
    etree.SubElement(celda, _q("f")).text = valor


def _celdas(fila: etree._Element) -> dict[str, etree._Element]:
    return {re.sub(r"\d+", "", c.get("r") or ""): c for c in fila}


def anadir(bruto: bytes, bloques: tuple[Bloque, ...], *, ingles: bool) -> bytes:
    raiz = etree.fromstring(bruto)
    datos = raiz.find(_q("sheetData"))
    por_fila = {int(f.get("r")): f for f in datos.iterfind(_q("row"))}

    for bloque in bloques:
        delta = bloque.seccion - MODELO_SECCION
        nuevas: list[etree._Element] = []
        for origen in range(MODELO_SECCION, MODELO_ULTIMA + 1):
            fila = copy.deepcopy(por_fila[origen])
            fila.set("r", str(origen + delta))
            for celda in fila:
                celda.set("r", _desplazar(celda.get("r"), delta, MODELO_SECCION, MODELO_ULTIMA))
                f = celda.find(_q("f"))
                if f is not None and f.text:
                    f.text = _desplazar(f.text, delta, MODELO_SECCION, MODELO_ULTIMA)
                    f.attrib.pop("t", None)  # una fórmula compartida deja de serlo
                    f.attrib.pop("si", None)
                    f.attrib.pop("ref", None)
                # El valor cacheado ya no vale: que Excel lo recalcule.
                v = celda.find(_q("v"))
                if v is not None and f is not None:
                    celda.remove(v)
            nuevas.append(fila)

        seccion, subtotal = nuevas[0], nuevas[1]
        _texto_en(_celdas(seccion)["A"], bloque.titulo_en if ingles else bloque.titulo_es)
        # El subtotal del modelo dice «=+A193»; aquí apunta a su propia sección.
        _formula(_celdas(subtotal)["A"], f"+A{bloque.seccion}")

        primera = bloque.seccion + (MODELO_PRIMERA - MODELO_SECCION)
        for i, fila in enumerate(nuevas[2:]):
            n = primera + i
            celdas = _celdas(fila)
            _texto_en(celdas["A"], bloque.item)
            _texto_en(celdas["C"], bloque.tipo_en if ingles else bloque.tipo_es)
            _texto_en(celdas["D"], bloque.categoria)
            if bloque.porcentaje_desde and i == 0:
                # `[REQ]` Manda «00 Datos Activo»: el porcentaje se lee de ahí y
                # no se escribe a mano, que es lo que decidió el cliente.
                hoja = "'00 Asset Data'" if ingles else "'00 Datos Activo'"
                _texto_en(celdas["G"], bloque.etiqueta_en if ingles else bloque.etiqueta_es)
                _formula(celdas["T"], f"+{hoja}!{bloque.porcentaje_desde}")
                _formula(celdas["U"], "+$O$12")
                for col in COLUMNAS_PLAZO:
                    _formula(celdas[col], f"+$T{n}*{col}$12")
        # Las filas de destino **ya existen** en el XML: están vacías pero con
        # su estilo y su alto. Se sustituyen en su sitio; añadirlas sin más
        # dejaría dos filas con el mismo número y Excel daría el fichero por
        # corrupto.
        for fila in nuevas:
            n = int(fila.get("r"))
            viejo = por_fila.get(n)
            if viejo is None:
                datos.append(fila)
            else:
                viejo.getparent().replace(viejo, fila)
            por_fila[n] = fila

    # ── El TOTAL general tiene que contarlos ────────────────────────────────
    total = por_fila[FILA_TOTAL]
    for col, celda in _celdas(total).items():
        if col not in COLUMNAS_PLAZO:
            continue
        f = celda.find(_q("f"))
        if f is None or f.text is None:
            continue
        faltan = [f"+{col}{b.seccion}" for b in bloques if f"{col}{b.seccion}" not in f.text]
        if faltan:
            f.text = f.text + "".join(faltan)
            v = celda.find(_q("v"))
            if v is not None:
                celda.remove(v)

    # Las filas tienen que ir en orden o Excel se queja del fichero.
    orden = sorted(datos.iterfind(_q("row")), key=lambda f: int(f.get("r")))
    for f in orden:
        datos.append(f)
    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)


def _ampliar_area_de_impresion(libro: str, ultima: int) -> str:
    """El área de impresión acababa en la 255 y dejaría fuera lo nuevo."""
    return re.sub(
        r"(<definedName name=\"_xlnm.Print_Area\" localSheetId=\"4\">CapEx!\$A\$9:\$Q\$)\d+",
        rf"\g<1>{ultima}",
        libro,
    )


def procesar(fichero: Path, *, comprobar: bool) -> bool:
    ingles = fichero.name.endswith("_en.xltm")
    with zipfile.ZipFile(fichero) as z:
        nombres = z.namelist()
        partes = {n: z.read(n) for n in nombres}
        ruta = _ruta(z, POS_CAPEX)

    # Las filas de destino existen desde el principio, vacías: preguntar si
    # existen no dice nada. Lo que distingue un bloque puesto de uno por poner
    # es que su fila de sección tenga celdas con contenido.
    raiz = etree.fromstring(partes[ruta])
    por_fila = {
        int(f.get("r")): f for f in raiz.find(_q("sheetData")).iterfind(_q("row"))
    }
    ya_estan = all(len(por_fila.get(b.seccion, ())) > 5 for b in BLOQUES)
    if ya_estan:
        return False
    if comprobar:
        return True

    partes[ruta] = anadir(partes[ruta], BLOQUES, ingles=ingles)
    ultima = BLOQUES[-1].seccion + (MODELO_ULTIMA - MODELO_SECCION) + 1
    partes["xl/workbook.xml"] = _ampliar_area_de_impresion(
        partes["xl/workbook.xml"].decode("utf-8"), ultima
    ).encode("utf-8")

    with zipfile.ZipFile(fichero, "w", zipfile.ZIP_DEFLATED) as salida:
        for n in nombres:
            salida.writestr(n, partes[n])
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="no escribe; falla si faltan")
    args = ap.parse_args()

    pendientes = [f for f in FICHEROS if procesar(PLANTILLAS / f, comprobar=args.check)]
    if not pendientes:
        print("Las plantillas ya tienen los bloques de Operativos e Imprevistos.")
        return 0
    for f in pendientes:
        if args.check:
            print(f"FALTAN LOS BLOQUES en {f}", file=sys.stderr)
        else:
            print(f"{f}: añadidos {', '.join(b.titulo_es for b in BLOQUES)}")
    return 1 if args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())

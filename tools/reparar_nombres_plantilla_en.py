#!/usr/bin/env python3
"""Repara los nombres definidos de la plantilla CAPEX inglesa.

`[REQ]` La plantilla inglesa se hizo copiando la española, y al traducir las
celdas nadie tocó el gestor de nombres. Eso deja dos problemas.

**1 · Cuatro desplegables sin lista.** Los desplegables van en cascada: la
columna «Category» se valida con `INDIRECT(C)`, donde C es el tipo de coste, y
la columna «Item» con `INDIRECT(D)`, donde D es la categoría. Cada texto tiene
que existir como nombre definido. Los nombres siguen llamándose `Operativos`,
`ESG_Energía`, `Imprevistos` y `Mediambiente` mientras las celdas dicen
`Operating`, `ESG_Energy`, `Contingencies` y `Environmental`, así que
`INDIRECT()` no encuentra nada y la lista sale vacía.

Los nombres **ya apuntan al rango correcto**: solo están mal llamados. Se
renombran, no se rehacen.

**2 · El choque de «Environmental».** Es el único que no se arregla
renombrando. En español los dos niveles se llaman distinto —`Mediambiente` es
el tipo de coste y `Medioamb` la categoría—, así que cada nombre hace un
trabajo. En inglés **los dos se llaman `Environmental`**, y un nombre definido
no puede apuntar a dos listas a la vez: hoy apunta a la de objetos, con lo que
la columna «Item» funciona y la de «Category» no.

Se resuelve dando nombre propio al **tipo de coste**, que pasa a llamarse
`Environmental_Cost`. Se toca ese nivel y no la categoría por dos razones: es
el que menos se ve —la categoría es la que sale en cada fila del CAPEX y por la
que agrupan las tablas dinámicas— y deja la etiqueta al lado de `Hard_Cost` y
`Soft_Cost`, que ya llevan ese sufijo.

**3 · Diecisiete nombres que sobran.** Quince nombres españoles apuntando a
`#REF!` que quedaron al renombrar las hojas, el duplicado `HH01.Structure` y un
`_xleta.SUM` que apunta a `#NAME?`. No rompen nada; ensucian el gestor de
nombres y confunden al siguiente que lo abra.

Como en el resto de utilidades de plantillas, **no se reescribe el libro**: se
sustituyen solo las tres partes que cambian y las otras 80 se copian byte a
byte. Es idempotente.

Uso:  python3 tools/reparar_nombres_plantilla_en.py [--check]
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "apps" / "api" / "src" / "tdd" / "exports" / "plantillas" / "capex_ddt_en.xltm"

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XML_ESPACIO = "{http://www.w3.org/XML/1998/namespace}space"

#: Nombre viejo → nombre nuevo. El rango al que apuntan ya es el correcto.
RENOMBRAR: dict[str, str] = {
    "Operativos": "Operating",
    "ESG_Energía": "ESG_Energy",
    "Imprevistos": "Contingencies",
    "Mediambiente": "Environmental_Cost",
}

#: Nombres a borrar: los que apuntan a `#REF!` o `#NAME?`, más el duplicado.
BORRAR: frozenset[str] = frozenset(
    {
        "H01.Estructura",
        "H02.Cubierta",
        "H03.Fachadas",
        "H04.Interiores",
        "H05.Zonas_Exteriores",
        "H06.Protección_Pasiva_Incendios",
        "H07.Accesibilidad",
        "H09.Electricidad",
        "H10.Protección_Activa_Incendios",
        "H11.Fontanería_y_Saneamiento",
        "H12.Transporte_Vertical_y_Puertas_Mecánicas",
        "H13.Seguridad_CCTV_y_BMS",
        "H14.Telecomunicaciones_Voz_y_Datos",
        "H15.Otros",
        "Medioamb",
        "HH01.Structure",
        "_xleta.SUM",
    }
)

#: El tipo de coste pasa a llamarse así, para no chocar con su categoría.
TIPO_VIEJO = "Environmental"
TIPO_NUEVO = "Environmental_Cost"

#: Celda de «00 Category Data» con la etiqueta del tipo de coste medioambiental.
CELDA_TIPO = "F3"
#: Columna «Cost Type» del bloque medioambiental de la hoja `CapEx`.
CELDAS_BLOQUE = tuple(f"C{fila}" for fila in range(195, 205))


def _q(etiqueta: str) -> str:
    return f"{{{NS}}}{etiqueta}"


def _ruta_de_hoja(zf: zipfile.ZipFile, posicion: int) -> str:
    libro = zf.read("xl/workbook.xml").decode("utf-8")
    rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    destinos = dict(re.findall(r'Id="([^"]+)"[^>]*Target="(worksheets/[^"]+)"', rels))
    hojas = re.findall(r'<sheet name="[^"]+"[^>]*r:id="([^"]+)"', libro)
    return "xl/" + destinos[hojas[posicion]]


def _escribir_texto(bruto: bytes, celdas: tuple[str, ...], valor: str) -> bytes:
    """Pone `valor` en celdas concretas **sin tocar `sharedStrings.xml`**.

    Va con cadena en línea a propósito: la celda comparte su texto con otras
    —`F3` lo comparte con `F4`, que es la categoría y no debe cambiar—, así que
    editar la cadena compartida las cambiaría todas de golpe. El atributo `s`
    se conserva: lleva el formato.
    """
    raiz = etree.fromstring(bruto)
    datos = raiz.find(_q("sheetData"))
    pendientes = set(celdas)
    for fila in datos.iterfind(_q("row")):
        for celda in fila:
            if celda.get("r") not in pendientes:
                continue
            pendientes.discard(celda.get("r"))
            for hijo in list(celda):
                celda.remove(hijo)
            celda.set("t", "inlineStr")
            texto = etree.SubElement(etree.SubElement(celda, _q("is")), _q("t"))
            texto.text = valor
            texto.set(XML_ESPACIO, "preserve")
    if pendientes:
        raise SystemExit(f"La plantilla no tiene las celdas {sorted(pendientes)}")
    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)


def reparar(origen: Path, *, comprobar: bool) -> int:
    with zipfile.ZipFile(origen) as zf:
        nombres_zip = zf.namelist()
        partes = {n: zf.read(n) for n in nombres_zip}
        ruta_categorias = _ruta_de_hoja(zf, 0)
        ruta_capex = _ruta_de_hoja(zf, 4)

    libro = partes["xl/workbook.xml"].decode("utf-8")
    definidos = dict(re.findall(r'<definedName name="([^"]+)"[^>]*>([^<]*)</definedName>', libro))

    pendientes: list[str] = []
    pendientes += [f"renombrar {v} → {n}" for v, n in RENOMBRAR.items() if v in definidos]
    pendientes += [f"borrar {n}" for n in sorted(BORRAR) if n in definidos]
    if TIPO_NUEVO not in definidos:
        pendientes.append(f"etiquetar el tipo de coste como {TIPO_NUEVO}")

    if not pendientes:
        print("Los nombres definidos de la plantilla inglesa ya están reparados.")
        return 0
    if comprobar:
        for p in pendientes:
            print(f"PENDIENTE: {p}", file=sys.stderr)
        return 1

    for viejo, nuevo in RENOMBRAR.items():
        libro = libro.replace(f'<definedName name="{viejo}"', f'<definedName name="{nuevo}"')
    for muerto in BORRAR:
        libro = re.sub(
            rf'<definedName name="{re.escape(muerto)}"[^>]*>[^<]*</definedName>', "", libro
        )
    partes["xl/workbook.xml"] = libro.encode("utf-8")

    partes[ruta_categorias] = _escribir_texto(partes[ruta_categorias], (CELDA_TIPO,), TIPO_NUEVO)
    partes[ruta_capex] = _escribir_texto(partes[ruta_capex], CELDAS_BLOQUE, TIPO_NUEVO)

    with zipfile.ZipFile(origen, "w", zipfile.ZIP_DEFLATED) as salida:
        for n in nombres_zip:
            salida.writestr(n, partes[n])

    for p in pendientes:
        print(f"  {p}")
    print(f"\n{len(pendientes)} correcciones en {origen.relative_to(RAIZ)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="no escribe; falla si queda algo")
    return reparar(PLANTILLA, comprobar=ap.parse_args().check)


if __name__ == "__main__":
    raise SystemExit(main())

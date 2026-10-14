#!/usr/bin/env python3
"""Saca el inglés de los catálogos **de las propias plantillas del cliente**.

`[REQ]` La versión en inglés de la aplicación necesita el nombre inglés de 341
filas de catálogo. Hay dos maneras de conseguirlo, y solo una es aceptable:

1. Traducirlas. Rápido, y «Comercial» sale **Commercial**.
2. Leerlas del fichero inglés que el cliente ya usa. Ahí «Comercial» es
   **Retail**, que es como se llama en el sector.

Esto hace la segunda. Las plantillas CAPEX española e inglesa del cliente son
el mismo libro con las etiquetas cambiadas —se comprobó celda a celda al
escribir `exports/plantilla_capex.py`—, así que **la misma celda de las dos
hojas es una pareja de traducción**. De ahí salen 171 de los 178 códigos CAPEX,
las 20 zonas, las 6 tipologías, los 10 conceptos, los 5 horizontes y los 4
niveles de riesgo con su definición entera.

      python3 tools/extraer_ingles_del_cliente.py            # escribe el CSV
      python3 tools/extraer_ingles_del_cliente.py --check    # solo comprueba

`[LIM]` Lo que **no** sale de aquí, y queda marcado `propia` en el CSV para que
se revise: el árbol documental (73 nodos) y las secciones de memoria (19). Son
nombres de documentos administrativos españoles —«Licencia de Primera
Ocupación», «Informe Preliminar de la calidad del suelo»— que no aparecen en
ninguna plantilla inglesa del cliente porque esa parte del trabajo no se le
entrega al comprador traducida. Esas 92 las traduce esta herramienta a partir
de la tabla de abajo, escrita a mano, y van marcadas como propias.

`[PDV]` Las dos fuentes del cliente **no siempre concuerdan**: la hoja
«Legend» de la plantilla CAPEX dice *MEDIUM TERM* y la tabla del informe
—recuperada de los EMF, `docs/18` §«Estructura real de la tabla de CAPEX»—
dice *Mid term*. Manda el informe, que es lo que ve el comprador, y la
divergencia queda anotada en el CSV y aquí para que el cliente decida.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

RAIZ = Path(__file__).resolve().parents[1]
PLANTILLAS = RAIZ / "apps/api/src/tdd/exports/plantillas"
CATALOGOS = RAIZ / "data/catalogos"
SALIDA = CATALOGOS / "traducciones_en.csv"

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

#: Posición de cada hoja en el libro. Las dos plantillas las traen en el mismo
#: orden; los nombres sí cambian («00 Datos Categorías» / «00 Category Data»).
HOJA_CATEGORIAS = 0
HOJA_OBJETOS = 1
HOJA_ACTIVO = 2
HOJA_LEYENDA = 3


#: Lo que la plantilla pone delante del rótulo para ordenar el desplegable:
#: «a. Mantenimiento», «01 Bajo», «H01.Estructura». Estorba al emparejar.
ENUMERADOR = re.compile(r"^(?:[a-z]\.|\d{1,2}[.)]?)\s+", re.IGNORECASE)


def _normalizar(texto: str) -> str:
    """Para emparejar: sin acentos, sin mayúsculas, sin guiones bajos.

    Se quita también el enumerador de cabeza, porque la plantilla numera los
    conceptos y los riesgos para ordenar sus desplegables —«a. Mantenimiento»,
    «01 Bajo»— y el catálogo guarda el rótulo solo.
    """
    limpio = ENUMERADOR.sub("", texto.strip())
    sin_tildes = unicodedata.normalize("NFD", limpio.lower()).encode("ascii", "ignore")
    return " ".join(sin_tildes.decode().replace("_", " ").split())


def _leer_hoja(libro: Path, posicion: int) -> list[list[str]]:
    """Las celdas de una hoja, por filas, ya resueltas las cadenas compartidas."""
    with zipfile.ZipFile(libro) as zf:
        compartidas = etree.fromstring(zf.read("xl/sharedStrings.xml"))
        cadenas = [
            "".join(t.text or "" for t in si.iter(f"{NS}t"))
            for si in compartidas.findall(f"{NS}si")
        ]
        wb = etree.fromstring(zf.read("xl/workbook.xml"))
        hoja = list(wb.iter(f"{NS}sheet"))[posicion]
        rels = etree.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        destino = {r.get("Id"): r.get("Target") for r in rels}[hoja.get(f"{REL}id")]
        contenido = etree.fromstring(zf.read("xl/" + str(destino).lstrip("/").removeprefix("xl/")))

    filas: list[list[str]] = []
    for fila in contenido.iter(f"{NS}row"):
        celdas: list[str] = []
        for c in fila.iter(f"{NS}c"):
            v = c.find(f"{NS}v")
            if v is None:
                celdas.append("")
            elif c.get("t") == "s":
                celdas.append(cadenas[int(v.text or "0")])
            else:
                celdas.append(v.text or "")
        filas.append(celdas)
    return filas


def _parejas(posicion: int) -> list[tuple[str, str]]:
    """Celda a celda, el castellano de una plantilla con el inglés de la otra."""
    es = _leer_hoja(PLANTILLAS / "capex_ddt_es.xltm", posicion)
    en = _leer_hoja(PLANTILLAS / "capex_ddt_en.xltm", posicion)
    salida: list[tuple[str, str]] = []
    for fes, fen in zip(es, en, strict=False):
        for a, b in zip(fes, fen, strict=False):
            a, b = a.strip(), b.strip()
            # `-` es el relleno de los desplegables en cascada.
            if not a or not b or a == "-" or b == "-":
                continue
            # Una celda idéntica en los dos ficheros **sí** cuenta, y además es
            # la pareja más fiable que hay: el cliente escribió «General»,
            # «HVAC», «UPS» o «BMS» igual en los dos idiomas a propósito.
            # Descartarlas dejaba sin fuente 22 códigos CAPEX y media docena de
            # zonas y conceptos, y obligaba a inventar un inglés que ya estaba
            # escrito.
            salida.append((a, b))
    return salida


def _codigo_y_nombre(celda: str) -> tuple[str, str] | None:
    """`'H01.Estructura'` → `('H01', 'Estructura')`. Si no lleva código, nada."""
    if "." not in celda:
        return None
    codigo, _, nombre = celda.partition(".")
    codigo = codigo.strip()
    if len(codigo) == 3 and codigo[0] in "HSO" and codigo[1:].isdigit():
        return codigo, nombre.replace("_", " ").strip()
    return None


def ingles_del_capex() -> tuple[dict[str, str], dict[str, str]]:
    """`({'H01': 'Structure', …}, {'estructura': 'Structure', …})`.

    Dos diccionarios porque los dos niveles del árbol se emparejan distinto.
    Los **capítulos** llevan su código delante en la celda (`H01.Estructura`),
    así que se emparejan por código, que es exacto. Los **objetos** no llevan
    código en ninguna parte de la hoja: van en la fila de su capítulo y se
    emparejan por nombre, normalizado.
    """
    capitulos: dict[str, str] = {}
    objetos: dict[str, str] = {}
    for posicion in (HOJA_CATEGORIAS, HOJA_OBJETOS):
        for a, b in _parejas(posicion):
            pa, pb = _codigo_y_nombre(a), _codigo_y_nombre(b)
            if pa and pb and pa[0] == pb[0]:
                capitulos[pa[0]] = pb[1]
                # El nombre del capítulo sirve además de pareja suelta: hay
                # códigos de nivel 2 que en la hoja salen sin prefijo.
                objetos.setdefault(_normalizar(pa[1]), pb[1])
            else:
                objetos.setdefault(_normalizar(a), b)
    return capitulos, objetos


def ingles_de_la_leyenda() -> dict[str, list[str]]:
    """Zonas, tipologías, conceptos, horizontes y riesgos, con definiciones.

    Devuelve **todas** las grafías que el cliente usa para cada rótulo, no la
    primera. La misma palabra aparece dos veces en la hoja con registro
    distinto: «OFICINAS»→«OFFICES» en la fila de cabecera de las tipologías y
    «Oficinas»→«Offices» en la columna de las zonas. Quedarse con la primera
    metía una zona en mayúsculas en un catálogo escrito en minúsculas.
    `_mismo_registro()` elige después.
    """
    sueltas: dict[str, list[str]] = {}
    for posicion in (HOJA_ACTIVO, HOJA_LEYENDA):
        for a, b in _parejas(posicion):
            variantes = sueltas.setdefault(_normalizar(a), [])
            limpio = ENUMERADOR.sub("", b)
            if limpio not in variantes:
                variantes.append(limpio)
    return sueltas


def _mismo_registro(nombre_es: str, variantes: list[str]) -> tuple[str, str]:
    """La grafía inglesa en el registro del castellano del catálogo, y la nota.

    `[LIM]` Solo distingue mayúsculas de no mayúsculas, que es la única
    diferencia que se ha visto, y **nunca cambia una palabra**: elige entre lo
    que el cliente escribió.

    Hay un caso en el que sí toca el texto, y por eso devuelve una nota. Las
    seis tipologías aparecen en la hoja una sola vez, en la fila de cabecera de
    «00 Asset Data», y por tanto solo en mayúsculas: «RETAIL», «HEALTHCARE».
    El catálogo las guarda en minúscula —«Comercial», «Sanitario»—, así que
    dejarlas tal cual pondría «RETAIL» al lado de «Offices» en el mismo
    desplegable. Se pasa la inicial a mayúscula y el resto a minúscula, que es
    la misma palabra en otro registro y no una traducción nuestra. Queda
    anotado en el CSV.

    Una sigla no se toca: `HVAC`, `ESG`, `UPS`, `BMS`, `WIFI` y `PPV` llevan el
    `name_es` también en mayúsculas, así que entran por la primera rama.
    """
    if nombre_es.isupper():
        return next((v for v in variantes if v.isupper()), variantes[0]), ""
    if minuscula := next((v for v in variantes if not v.isupper()), None):
        return minuscula, ""
    original = variantes[0]
    return original[:1] + original[1:].lower(), f"la hoja lo escribe «{original}», en cabecera"


# ─────────────────────────────────────────────────────────────────────────────
#  Lo que no está en ninguna plantilla del cliente
# ─────────────────────────────────────────────────────────────────────────────
#
# `[SUP]` El criterio, que es el de un informe técnico en inglés sobre un
# activo español: **se traduce lo que describe y se conserva el nombre legal
# español entre paréntesis** cuando el documento es un instrumento
# administrativo con nombre propio. «First Occupancy Licence» a secas deja al
# lector inglés sin saber qué pedir al ayuntamiento; el nombre español sin
# traducir lo deja sin saber qué es.
#
# Van marcadas `propia` en el CSV: son nuestra traducción, no la del cliente, y
# está dicho en el fichero para que las repase quien firma el informe.

ARBOL_DOCUMENTAL: dict[str, str] = {
    "S1": "Planning documentation",
    "S1.1": "Planning permissions",
    "S1.1.1": "New-build works licence and amendments (Licencia de Obras)",
    "S1.1.2": "First occupancy licence (Licencia de Primera Ocupación)",
    "S1.1.3": "Activity licence (Licencia de Actividad)",
    "S1.1.4": "Operating licence (Licencia de Funcionamiento)",
    "S1.2": "Projects with permissions granted",
    "S1.2.1": "Concept design (Proyecto Básico)",
    "S1.2.2": "Detailed design (Proyecto de Ejecución)",
    "S1.2.3": "Activity design (Proyecto de Actividad)",
    "S1.2.4": "Designs and responsible declarations for extensions and/or mobile-home installation",
    "S1.3": "Notices from the local authority",
    "S1.3.1": "Formal requests",
    "S1.3.2": "Refusals",
    "S1.3.3": "Planning-infringement proceedings",
    "S2": "Technical documentation",
    "S2.1": "Technical report (Memoria técnica)",
    "S2.2": "Final works certificate (Certificado Final de Obra)",
    "S2.3": (
        "Maintenance contracts in the owner's name (fire protection, electrical, substation, etc.)"
    ),
    "S2.4": (
        "Maintenance reports for the installations in the owner's name "
        "(fire protection, electrical, substation, etc.)"
    ),
    "S2.5": (
        "Mandatory statutory inspections of the installations (fire protection, electrical, HVAC, "
        "gas, etc.)"
    ),
    "S2.6": (
        "Registration with the Industry authority of low-voltage electrical installations / "
        "electrical certificates and high voltage"
    ),
    "S2.7": (
        "Registration of thermal installations (air conditioning, heating and domestic hot water)"
    ),
    "S2.8": "Registration with the Industry authority of thermal installations (solar thermal)",
    "S2.9": "Registration with the Industry authority of the fire-protection installation",
    "S2.10": "Registration of the propane gas installation",
    "S2.11": "CAD drawings",
    "S2.12": "Energy performance certificate",
    "S2.13": (
        "Previous technical reports: due diligences, specific studies (facades, structure, "
        "installations, …)"
    ),
    "S2.14": "Electricity and water consumption invoices (domestic and fire-protection supply)",
    "S2.15": (
        "Details of the drainage pumping system and the discharge authorisation to the public sewer"
    ),
    "S3": "Environmental documentation",
    "S3.1": "Site",
    "S3.1.1": "Address",
    "S3.1.2": "Land Registry extract (nota simple)",
    "S3.1.3": "Site drawings",
    "S3.1.4": "Annual consumption",
    "S3.2": "Permits and inspections",
    "S3.2.1": "Environmental permit or licence held",
    "S3.2.2": "Application submitted to obtain the environmental licence",
    "S3.2.3": "Environmental impact assessment",
    "S3.2.4": "Inspection reports issued by the environmental authority or an accredited body",
    "S3.2.5": "Correspondence with the environmental authority on environmental matters",
    "S3.3": "Soil",
    "S3.3.1": (
        "Geotechnical report and any soil quality or contamination investigations carried out"
    ),
    "S3.3.2": "Preliminary soil quality report and the authority's response",
    "S3.4": "Storage of hazardous substances",
    "S3.4.1": (
        "Description of the existing tanks (above and below ground) – type, volume, contents, "
        "age, tightness tests, etc. (include fuel tanks for generators, fire pumps, etc., and "
        "former tanks out of use or decommissioned). Attach a location drawing if available"
    ),
    "S3.4.2": (
        "Schedule of chemical products stored by hazard class. Quantities stored "
        "(and consumed annually)"
    ),
    "S3.4.3": "Latest Seveso report (if applicable) and the authority's response",
    "S3.4.4": (
        "If chemical substances are imported from outside the European customs territory (>1t), "
        "include the substance pre-registration documentation. If a downstream user, include the "
        "correspondence with suppliers on pre-registrations. If an importer of articles, include "
        "the documentation on the control of SVHC substances in them"
    ),
    "S3.5": "Air emissions",
    "S3.5.1": (
        "Inventory of emission sources (boilers included), classification and measurement "
        "reports of air pollutants"
    ),
    "S3.5.2": "External noise studies carried out",
    "S3.5.3": "Odour studies carried out",
    "S3.5.4": "If there is refrigeration equipment, the gas it uses",
    "S3.5.5": "Extinguishing agents used",
    "S3.5.6": (
        "Annual quantities of solvents used. Fugitive emissions balance and solvent management plan"
    ),
    "S3.5.7": (
        "For cooling towers, attach the analyses and controls carried out for legionella control"
    ),
    "S3.6": "Water supply and discharges",
    "S3.6.1": "If there is a well on site, the water abstraction authorisation and its analysis",
    "S3.6.2": "Description of any pre-treatment applied to the supply water",
    "S3.6.3": (
        "Discharge permit for waste water and rainwater (state where it discharges, to a "
        "watercourse or to the municipal sewer)"
    ),
    "S3.6.4": "Description of the treatment applied to the waste water before discharge",
    "S3.6.5": "Analyses carried out on the waste water",
    "S3.7": "Waste and other matters",
    "S3.7.1": (
        "Documentation on waste management (hazardous and non-hazardous), waste producer number"
    ),
    "S3.7.2": "Inventory of asbestos-containing materials on site",
    "S3.7.3": (
        "If there are oil-filled electrical transformers or hydraulic equipment, their year and "
        "the PCB content analysis of the oil in that equipment"
    ),
    "S3.7.4": "Environmental investment plan for the next 5 years",
    "S3.7.5": (
        "Environmental certifications (ISO 14001, EMAS, etc.). Include any other certifications "
        "held (ISO 9001, 18001, etc.)"
    ),
    "S3.7.6": "Environmental incidents over the history of the plant",
    "S4": "Q&A",
}

SECCIONES_DE_MEMORIA: dict[str, str] = {
    "MC.0": "Preliminary works",
    "MC.1": "Earthworks",
    "MC.2": "Foundations and retaining works",
    "MC.3": "Structural system",
    "MC.4": "Building envelope",
    "MC.5": "Compartmentation and finishes",
    "MC.6": "Building services",
    "MC.7": "Internal site works",
    "MD.2": "Description of the project",
    "MD.3": "Building performance",
}

FASES: dict[str, str] = {
    "SOLICITUD_DOCUMENTACION": "Document request",
    "VDR": "Virtual Data Room set-up",
    "VISITA": "Asset site visit",
    "RED_FLAG_CAPEX": "Red Flag / CAPEX",
    "FULL_REPORT": "Full Report",
    "PRESENTACION_CLIENTE": "Client presentation",
    "DEFENSA": "Defence against the counterparty",
    "QA": "Q&A",
}

TIPOS_DE_COMPROBACION: dict[str, str] = {
    "COMPLETITUD": "Completeness",
    "CORRESPONDENCIA": "Matches what was requested",
    "LEGIBILIDAD": "Legibility",
    "VIGENCIA": "Validity and expiry",
}

#: `[LIM]` Los 14 sistemas técnicos son nuestra taxonomía de trabajo (`docs/05`
#: §5.8), no la del cliente: agrupan el inventario de equipo para que una
#: incidencia caiga en el capítulo CAPEX que le toca. Tres coinciden con un
#: capítulo del cliente y se usa SU inglés; los otros once son propios.
SISTEMAS_TECNICOS: dict[str, str] = {
    "FACH": "Facade and envelope",
    "CUB": "Roof",
    "EST": "Structure",
    "INT": "Interior areas",
    "CLIMA": "HVAC",
    "ELEC": "Electrical",
    "FONT": "Plumbing and drainage",
    "PCI": "Fire protection",
    "ASC": "Lifts",
    "SEG": "Security",
    "URB": "External site works",
    "ACC": "Accessibility",
    "SOST": "Sustainability",
    "OTROS": "Others",
}

#: `[REQ]` Lo que se decide a mano porque las dos fuentes del cliente no
#: coinciden, o porque el catálogo no tiene sitio para la distinción que él
#: hace. Los cinco horizontes salen de **la tabla del informe** y no de la
#: hoja «Legend», aunque las dos sean del cliente. Dos razones:
#:
#: 1. La «Legend» los escribe como títulos —«CORTO PLAZO\n(0-2 AÑOS)»—, con el
#:    rango de años dentro de la celda y en mayúsculas. Son encabezados de una
#:    leyenda, no los rótulos de una columna.
#: 2. El informe es **el documento que ve el comprador**, y ahí la cabecera de
#:    la tabla de CAPEX pone «Short term · Mid term · Long term ·
#:    Improvements» (recuperado de los EMF de la plantilla, `docs/18`).
#:
#: `[PDV]` Y en uno de los cinco las dos fuentes del cliente **no dicen lo
#: mismo**: «Medio plazo» es *MEDIUM TERM* en la hoja y *Mid term* en el
#: informe. Se elige el informe y la divergencia queda escrita en el CSV, en
#: la columna `nota`, para que el cliente decida si quiere unificarlas.
MANDA_EL_INFORME: dict[tuple[str, str], tuple[str, str]] = {
    ("time_horizon", "CORTO"): (
        "Short term",
        "cabecera de la tabla de CAPEX del informe (docs/18); "
        "la hoja «Legend» pone «SHORT TERM (0-2 YEARS)»",
    ),
    ("time_horizon", "MEDIO"): (
        "Mid term",
        "cabecera de la tabla de CAPEX del informe (docs/18); "
        "la hoja «Legend» pone «MEDIUM TERM» · DIVERGEN, se sigue el informe",
    ),
    ("time_horizon", "LARGO"): (
        "Long term",
        "cabecera de la tabla de CAPEX del informe (docs/18); "
        "la hoja «Legend» pone «LONG TERM (6-10 YEARS)»",
    ),
    ("time_horizon", "MEJORAS"): (
        "Improvements",
        "cabecera de la tabla de CAPEX del informe (docs/18); la hoja «Legend» pone «IMPROVEMENTS»",
    ),
    ("time_horizon", "OTRO"): (
        "Other",
        "la hoja «Legend» pone «OTHER»; el informe no lleva esta columna (P-37)",
    ),
    # `[PDV]` Un hallazgo del emparejamiento, y no un problema de la
    # herramienta: el cliente llama «Habitaciones» a la misma zona en hotel y
    # en sanitario, y en inglés la llama **distinto según la tipología** —
    # «Guest rooms» en la columna de HOTEL y «Patient rooms» en la de
    # SANITARIO, en «00 Asset Data»—. El catálogo tiene **una** fila `zone`
    # por código, así que no cabe esa distinción: el nombre inglés es del
    # código, no del par zona×tipología.
    #
    # Se deja «Guest rooms», que es la columna que aparece primero, y se dice
    # aquí y en el CSV. Resolverlo de verdad es mover `name_en` a la tabla
    # `zone_typology`, que son 86 filas en vez de 20, y eso es una decisión
    # del cliente, no una que se tome al traducir.
    ("zone", "HABITACIONES"): (
        "Guest rooms",
        "«00 Asset Data» pone «Guest rooms» en HOTEL y «Patient rooms» en "
        "HEALTHCARE · PDV: el catálogo solo admite un nombre por zona",
    ),
}


Fila = dict[str, str]


def construir() -> tuple[list[Fila], list[str]]:
    """Las filas del CSV y lo que no se ha podido resolver."""
    capitulos, objetos = ingles_del_capex()
    leyenda = ingles_de_la_leyenda()

    filas: list[Fila] = []
    sin_fuente: list[str] = []

    def apuntar(tabla: str, code: str, campo: str, texto: str, fuente: str, nota: str = "") -> None:
        filas.append(
            {
                "tabla": tabla,
                "code": code,
                "campo": campo,
                "texto_en": texto,
                "fuente": fuente,
                "nota": nota,
            }
        )

    def de_la_leyenda(tabla: str, code: str, nombre_es: str, propia: dict[str, str]) -> None:
        clave = (tabla, code)
        if clave in MANDA_EL_INFORME:
            texto, nota = MANDA_EL_INFORME[clave]
            fuente = "cliente:capex_en" if tabla == "zone" else "cliente:informe"
            apuntar(tabla, code, "name_en", texto, fuente, nota)
            return
        if variantes := leyenda.get(_normalizar(nombre_es)):
            texto, nota = _mismo_registro(nombre_es, variantes)
            apuntar(tabla, code, "name_en", texto, "cliente:capex_en", nota)
        elif en := propia.get(code):
            apuntar(tabla, code, "name_en", en, "propia")
        else:
            sin_fuente.append(f"{tabla}/{code}: «{nombre_es}»")

    def csv_de(nombre: str) -> list[dict[str, Any]]:
        with (CATALOGOS / nombre).open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    # ── El árbol CAPEX ───────────────────────────────────────────────────
    for fila in csv_de("codigos_capex.csv"):
        code, nivel, nombre = fila["code"], fila["level"], fila["name_es"]
        corto = code.split(".")[-1]
        if nivel == "2" and corto in capitulos:
            apuntar("capex_code", code, "name_en", capitulos[corto], "cliente:capex_en")
        elif en := objetos.get(_normalizar(nombre)):
            apuntar("capex_code", code, "name_en", en, "cliente:capex_en")
        elif en := CAPEX_NIVEL_1.get(code):
            apuntar("capex_code", code, "name_en", en, "cliente:capex_en", CAPEX_NIVEL_1_NOTA[code])
        else:
            sin_fuente.append(f"capex_code/{code}: «{nombre}»")

    for code, en in CAPEX_JUBILADOS.items():
        apuntar(
            "capex_code",
            code,
            "name_en",
            en,
            "cliente:capex_en",
            "código jubilado por 0020; sigue vivo para los hallazgos antiguos",
        )

    # ── Lo que está en la leyenda ────────────────────────────────────────
    for fila in csv_de("tipologias.csv"):
        de_la_leyenda("asset_typology", fila["code"], fila["name_es"], {})
    for fila in csv_de("zonas.csv"):
        de_la_leyenda("zone", fila["code"], fila["name_es"], {})
    for fila in csv_de("conceptos.csv"):
        de_la_leyenda("capex_concept", fila["code"], fila["name_es"], {})
    for fila in csv_de("horizontes.csv"):
        de_la_leyenda("time_horizon", fila["code"], fila["name_es"], {})
    for fila in csv_de("riesgos.csv"):
        de_la_leyenda("risk_level", fila["code"], fila["name_es"], {})
        # La definición entera, que son cuatro párrafos largos y los escribió
        # el cliente en los dos idiomas.
        definicion = DEFINICION_DE_RIESGO.get(fila["code"])
        if definicion:
            apuntar("risk_level", fila["code"], "definition_en", definicion, "cliente:capex_en")
        else:
            sin_fuente.append(f"risk_level/{fila['code']}: definición")

    # ── Lo nuestro ───────────────────────────────────────────────────────
    for fila in csv_de("arbol_documental.csv"):
        code = fila["code"]
        if en := ARBOL_DOCUMENTAL.get(code):
            apuntar("doc_request_category", code, "name_en", en, "propia")
        else:
            sin_fuente.append(f"doc_request_category/{code}: «{fila['name_es']}»")
    vistas: set[str] = set()
    for fila in csv_de("secciones_memoria.csv"):
        code = fila["seccion_code"]
        if code in vistas:
            continue
        vistas.add(code)
        if en := SECCIONES_DE_MEMORIA.get(code):
            apuntar("memoria_seccion", code, "name_en", en, "propia")
        else:
            sin_fuente.append(f"memoria_seccion/{code}: «{fila['name_es']}»")
    for fila in csv_de("sistemas_tecnicos.csv"):
        code = fila["code"]
        if en := SISTEMAS_TECNICOS.get(code):
            fuente = "cliente:capex_en" if _normalizar(fila["name_es"]) in leyenda else "propia"
            apuntar("technical_system", code, "name_en", en, fuente)
        else:
            sin_fuente.append(f"technical_system/{code}: «{fila['name_es']}»")
    for code, en in FASES.items():
        apuntar("phase_definition", code, "name_en", en, "propia")
    for code, en in TIPOS_DE_COMPROBACION.items():
        apuntar("doc_check_type", code, "name_en", en, "propia")

    return filas, sin_fuente


#: `[REQ]` Los cinco códigos de nivel 1 y los dos de nivel 2 que la hoja no
#: empareja sola, con la celda de donde sale cada inglés. Están aquí y no en la
#: tabla de traducciones propias porque **el inglés sí es del cliente**: lo que
#: falla es el emparejamiento automático, porque en la hoja aparecen con otra
#: grafía («Operativos» en la fila «Tipo Coste», «Medioamb» como columna).
CAPEX_NIVEL_1: dict[str, str] = {
    "HC": "Hard Cost",
    "SC": "Soft Cost",
    "OP": "Operating",
    "MA": "Environmental",
    "MA.MA1": "Environmental",
    "ESG": "ESG and Energy",
    "ESG.ES1": "ESG",
}
#: `[REQ]` Códigos que **están en la base y no en el CSV de la semilla**: los
#: creó la migración 0006 y la 0020 los jubiló (`deprecated_at`) al adoptar el
#: árbol del cliente. Ya no se ofrecen al codificar, pero siguen existiendo
#: para que un hallazgo antiguo se resuelva, y un hallazgo antiguo sale en el
#: informe. Sin estas tres filas, un informe en inglés enseñaría «General» en
#: castellano y nadie sabría por qué.
#:
#: Los tres se llaman «General», que el cliente escribe igual en los dos
#: idiomas (capítulo H02 de «00 Item Data»), así que el inglés también es suyo.
CAPEX_JUBILADOS: dict[str, str] = {
    "OP.C01.01": "General",
    "OP.C02.01": "General",
    "IMP.General.01": "General",
}

CAPEX_NIVEL_1_NOTA: dict[str, str] = {
    "HC": "«Hard_Cost», fila «Cost Type» de «00 Category Data»",
    "SC": "«Soft_Cost», fila «Cost Type» de «00 Category Data»",
    "OP": "«Operativos»→«Operating», fila «Cost Type» de «00 Category Data»",
    "MA": "«Medioamb»→«Environmental», columna de «00 Category Data»",
    "MA.MA1": "«Medioamb»→«Environmental», columna de «00 Category Data»",
    "ESG": "«h. ESG» en «00 Asset Data»; «y Energía» traducido",
    "ESG.ES1": "«h. ESG» en «00 Asset Data»",
}

#: Las cuatro definiciones de riesgo, de la hoja «Legend» de la plantilla
#: inglesa. Se copian enteras porque el informe las imprime enteras.
DEFINICION_DE_RIESGO: dict[str, str] = {
    "01": (
        "Aspects that would improve the building's efficiency and/or performance, although not "
        "required due to regulatory non-compliance, necessary repair, or renewal due to end of "
        "useful life."
    ),
    "02": (
        "Anomalies due to age (parts of the property that have exceeded their useful life) "
        "which, although currently may not be negatively and substantially affecting operations, "
        "we believe will require renovation to be addressed in the transaction."
    ),
    "03": (
        "Anomalies that may be interpreted as non-compliant but are open to interpretation and "
        "could be negotiated without becoming relevant to the transaction."
    ),
    "04": (
        "Irrefutable anomalies expected to be claimed by the buyer requiring a commitment to "
        "resolve within an agreed timeframe. This group includes anomalies that by their nature "
        "affect building deterioration, may constitute a clear breach of current regulations "
        "and/or may impact operations."
    ),
}

CABECERA = ("tabla", "code", "campo", "texto_en", "fuente", "nota")


def escribir(filas: list[Fila]) -> str:
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=list(CABECERA), lineterminator="\n")
    w.writeheader()
    for fila in sorted(filas, key=lambda f: (f["tabla"], f["code"], f["campo"])):
        w.writerow(fila)
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="no escribe; falla si está desfasado")
    args = ap.parse_args()

    filas, sin_fuente = construir()
    contenido = escribir(filas)

    if sin_fuente:
        print(f"{len(sin_fuente)} filas sin inglés:", file=sys.stderr)
        for s in sin_fuente:
            print(f"  {s}", file=sys.stderr)
        return 1

    if args.check:
        if not SALIDA.exists() or SALIDA.read_text(encoding="utf-8") != contenido:
            print(
                f"{SALIDA.relative_to(RAIZ)} está desfasado. "
                "Ejecute `python3 tools/extraer_ingles_del_cliente.py`.",
                file=sys.stderr,
            )
            return 1
        print(f"{len(filas)} traducciones al día")
        return 0

    SALIDA.write_text(contenido, encoding="utf-8")
    por_fuente: dict[str, int] = {}
    for f in filas:
        por_fuente[f["fuente"]] = por_fuente.get(f["fuente"], 0) + 1
    detalle = " · ".join(f"{n} {k}" for k, n in sorted(por_fuente.items()))
    print(f"{SALIDA.relative_to(RAIZ)}: {len(filas)} traducciones ({detalle})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

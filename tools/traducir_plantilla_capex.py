#!/usr/bin/env python3
"""Traduce los textos que quedaron en español en la plantilla CAPEX inglesa.

`[REQ]` La plantilla inglesa se hizo copiando la española y quedaron cinco
textos sin traducir. Los cinco viven en `xl/sharedStrings.xml`, así que se
corrigen ahí una vez y las once celdas que los usan se actualizan solas.

**No se reescribe el libro.** Se abre como el ZIP que es y se sustituye
únicamente `sharedStrings.xml`; las otras 82 partes se copian byte a byte. Con
`openpyxl` se perderían gráficos, tablas dinámicas, segmentaciones y logotipos
—se midió: 33 de 87 partes—, y el fichero se abriría igual, que es la peor
forma posible de romperlo.

Es **idempotente**: volver a ejecutarlo sobre una plantilla ya traducida no
cambia nada y lo dice.

Uso:  python3 tools/traducir_plantilla_capex.py [--check]
      --check no escribe; sale con 1 si queda algo sin traducir.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "apps" / "api" / "src" / "tdd" / "exports" / "plantillas" / "capex_ddt_en.xltm"

#: Español encontrado → inglés. Las traducciones **siguen el estilo que la
#: propia plantilla ya usa** en las celdas equivalentes de la hoja `CapEx`, para
#: no introducir una tercera forma de decir lo mismo:
#:   · «Works permit (ICIO...)» y «Other licenses» son literalmente lo que dicen
#:     G246 y G247, que sí estaban traducidas.
#:   · «Contingencies» es como llama la hoja «00 Category Data» a ese tipo de
#:     coste en H3.
#:   · «H15.Others» es lo que ya dice la cabecera del bloque en `CapEx!A181` y
#:     el nombre definido `H15.Others`. Cambiarlo además **repara** el
#:     desplegable: hasta ahora la lista de categorías ofrecía «H15.Otros»
#:     mientras la celda de al lado decía «H15.Others», así que el valor no
#:     estaba en su propia lista.
TRADUCCIONES: dict[str, str] = {
    "% Estimado (eliminar si no procede o adaptar si fuera necesario)": (
        "Estimated % (delete if not applicable or adapt if necessary)"
    ),
    "H15.Otros": "H15.Others",
    "Imprevistos": "Contingencies",
    "Licencia de Obras (ICIO, Tasas en construcción, Instalaciones y otros trabajos)": (
        "Works permit (ICIO, Tax on Construction, Installations and Works)"
    ),
    "Otras licencias": "Other licenses",
}

CADENAS = "xl/sharedStrings.xml"


def _escapar(texto: str) -> str:
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def traducir(origen: Path, *, comprobar: bool) -> int:
    with zipfile.ZipFile(origen) as z:
        nombres = z.namelist()
        partes = {n: z.read(n) for n in nombres}

    xml = partes[CADENAS].decode("utf-8")
    pendientes: list[str] = []
    for espanol, ingles in TRADUCCIONES.items():
        # Solo dentro de un `<t>`: así no se toca ningún atributo ni fórmula.
        patron = re.compile(rf"(<t[^>]*>){re.escape(_escapar(espanol))}(</t>)")
        if not patron.search(xml):
            continue
        pendientes.append(espanol)
        xml = patron.sub(rf"\g<1>{_escapar(ingles)}\g<2>", xml)

    if not pendientes:
        print("La plantilla inglesa ya está traducida: nada que hacer.")
        return 0
    if comprobar:
        for p in pendientes:
            print(f"SIN TRADUCIR: {p!r}", file=sys.stderr)
        return 1

    partes[CADENAS] = xml.encode("utf-8")
    respaldo = origen.with_suffix(origen.suffix + ".bak")
    shutil.copy2(origen, respaldo)
    with zipfile.ZipFile(origen, "w", zipfile.ZIP_DEFLATED) as salida:
        for n in nombres:  # mismo orden que el original
            salida.writestr(n, partes[n])
    respaldo.unlink()

    for p in pendientes:
        print(f"  {p[:58]!r}\n    → {TRADUCCIONES[p]!r}")
    print(f"\n{len(pendientes)} textos traducidos en {origen.relative_to(RAIZ)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="no escribe; falla si queda español")
    args = ap.parse_args()
    return traducir(PLANTILLA, comprobar=args.check)


if __name__ == "__main__":
    raise SystemExit(main())

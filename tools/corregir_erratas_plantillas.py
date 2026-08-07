#!/usr/bin/env python3
"""Corrige erratas de literal en las plantillas CAPEX del cliente.

Hermano de `traducir_plantilla_capex.py` —que traduce lo que quedó en español
en la inglesa— y de `reparar_nombres_plantilla_en.py` —que arregla los nombres
definidos—. Este se ocupa de las palabras mal escritas, que no rompen nada pero
salen impresas en el informe que ve el cliente.

**`Mediambiente` → `Medioambiente`.** Le falta la «o». Aparece en cuatro sitios
y hay que cambiarlos los cuatro a la vez, porque el desplegable de la columna
«Categoría» se resuelve con `INDIRECT()` sobre el texto de la celda: cambiar el
literal sin cambiar el nombre definido dejaría esa lista vacía.

A diferencia del caso inglés, aquí **no hay colisión**: el tipo de coste se
llama `Mediambiente` y la categoría `Medioamb`, que son textos distintos, así
que renombrar el primero no pisa al segundo. Por eso basta con editar la cadena
compartida —la usan `F3`, el bloque `C195:C204` y el resumen— en vez de escribir
celda a celda.

No se reescribe el libro: se sustituyen solo las partes que cambian y las demás
se copian byte a byte. Es idempotente.

Uso:  python3 tools/corregir_erratas_plantillas.py [--check]
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLAS = RAIZ / "apps" / "api" / "src" / "tdd" / "exports" / "plantillas"

#: `fichero → {texto mal escrito: texto correcto}`.
#:
#: `[REC]` No toda diferencia con el diccionario es una errata que se corrija
#: aquí. `Certificación WIRESCORED` también está mal —el producto es
#: *WiredScore*— y **se deja como está**: ese texto es un valor de una lista
#: cerrada por la que agrupan las tablas dinámicas, y cambiarlo sin cambiar
#: también el catálogo sembrado dejaría celdas fuera de su propia lista. Ver la
#: nota de §5.3. `Mediambiente` sí se corrige porque es una **etiqueta** y su
#: nombre definido se renombra con ella.
ERRATAS: dict[str, dict[str, str]] = {
    "capex_ddt_es.xltm": {"Mediambiente": "Medioambiente"},
}

#: Partes donde puede aparecer el literal. `sharedStrings` lleva el texto de las
#: celdas; `workbook` el nombre definido; `app` el índice de nombres que enseña
#: PowerPoint en las propiedades; y la caché de la tabla dinámica, su lista de
#: valores vistos.
PARTES = (
    "xl/sharedStrings.xml",
    "xl/workbook.xml",
    "docProps/app.xml",
    "xl/pivotCache/pivotCacheDefinition1.xml",
    "xl/pivotCache/pivotCacheDefinition2.xml",
)


def corregir(fichero: Path, cambios: dict[str, str], *, comprobar: bool) -> list[str]:
    with zipfile.ZipFile(fichero) as z:
        nombres = z.namelist()
        partes = {n: z.read(n) for n in nombres}

    pendientes: list[str] = []
    for parte in PARTES:
        if parte not in partes:
            continue
        texto = partes[parte].decode("utf-8")
        original = texto
        for malo, bueno in cambios.items():
            # Palabra entera: `Medioamb` NO debe convertirse en `Medioambiente`
            # por estar contenido en él. Es justo el fallo que dejaría la lista
            # de objetos del bloque medioambiental apuntando a ninguna parte.
            texto = re.sub(rf"\b{re.escape(malo)}\b", bueno, texto)
        if texto != original:
            pendientes.append(parte)
            partes[parte] = texto.encode("utf-8")

    if not pendientes or comprobar:
        return pendientes

    with zipfile.ZipFile(fichero, "w", zipfile.ZIP_DEFLATED) as salida:
        for n in nombres:
            salida.writestr(n, partes[n])
    return pendientes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="no escribe; falla si queda alguna")
    args = ap.parse_args()

    total = 0
    for nombre, cambios in ERRATAS.items():
        tocadas = corregir(PLANTILLAS / nombre, cambios, comprobar=args.check)
        if not tocadas:
            continue
        total += len(tocadas)
        if args.check:
            for parte in tocadas:
                print(f"ERRATA SIN CORREGIR en {nombre}: {parte}", file=sys.stderr)
        else:
            print(f"{nombre}: {', '.join(cambios)} corregido en {len(tocadas)} partes")
            for parte in tocadas:
                print(f"   · {parte}")
    if not total:
        print("Las plantillas no tienen erratas pendientes.")
    return 1 if (args.check and total) else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Convierte la hoja de estructura del cliente en el árbol de CAPEX.

`[REQ]` El cliente mantiene el árbol en **una hoja de cálculo** —tipos de coste,
categorías y objetos, una fila por nodo— y la manda cuando cambia. Esto la
traduce al formato del catálogo sembrado, aplicando las decisiones que se
tomaron al recibirla y que están escritas aquí para que no se vuelvan a
discutir:

1. **Las filas con `-` son «Otros»**, no relleno. Cada categoría acaba con un
   objeto «Otros» y cada tipo con una categoría «Otros»: es la salida que
   necesita un consultor en campo cuando lo que ve no está en la lista.
2. `H14 Telecomunicaciones, voz y datos` viene como **objeto** y es una
   **categoría**: errata confirmada.
3. Los objetos de ESG cuelgan de «ESG y Energía», que es el nombre del tipo. Se
   confirmó dejarlo así, de modo que **la categoría lleva el nombre de su
   tipo**, igual que ya pasa en Medioambiente.
4. `V1.2` estaba repetido en el bloque de visita; el segundo es `V1.3`.

`[SUP]` Dos más, propuestas y no contestadas, marcadas en el resultado:

5. `H15 Otros` y `H16 -` serían dos categorías hermanas llamadas «Otros». Se
   **fusionan** en `H15`, y `H16.1 General` pasa a ser objeto suyo.
6. La última fila de la hoja crea un **tipo de coste** entero llamado «Otros»,
   sin objetos. Se **descarta**: el cajón de sastre ya existe dentro de cada
   tipo y de cada categoría.

Uso::

    python3 tools/importar_arbol_capex.py hoja.xlsx --csv data/catalogos/codigos_capex.csv
    python3 tools/importar_arbol_capex.py hoja.xlsx --comparar   # qué cambia
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

#: Nombre del tipo en la hoja → código con el que ya está sembrado. Mantenerlos
#: es lo que evita el remapeo: los hallazgos existentes apuntan a estos códigos.
TIPOS = {
    "Hard Cost": "HC",
    "Soft Cost": "SC",
    "Operativo": "OP",
    "Medioambiente": "MA",
    "ESG y Energía": "ESG",
    "Imprevistos": "IMP",
}

#: Lo que la hoja escribe cuando quiere decir «Otros».
HUECO = "-"

#: `[SUP]` Decisión 5: `H16` no llega a existir; su contenido va a `H15`.
FUSIONAR = {"H16": "H15"}


def leer(hoja: Path) -> list[dict[str, str]]:
    import openpyxl

    ws = openpyxl.load_workbook(hoja, data_only=True)["Sheet1"]
    filas = []
    for celdas in ws.iter_rows(min_row=2, values_only=True):
        v = [("" if c is None else str(c).strip()) for c in celdas]
        if not any(v):
            continue
        filas.append({"bloque": v[0], "nivel": v[1], "codigo": v[2], "nombre": v[3], "padre": v[4]})
    return filas


def arbol(filas: list[dict[str, str]]) -> list[dict[str, str]]:
    """Las filas del catálogo: `code, name_es, level, parent_code`."""
    salida: list[dict[str, str]] = []
    capex = [f for f in filas if f["bloque"] == "CAPEX"]

    for nombre, code in TIPOS.items():
        salida.append({"code": code, "name_es": nombre, "level": "1", "parent_code": ""})

    #: nombre de la categoría en la hoja → su código completo, para colgar los
    #: objetos. Se indexa por nombre porque es lo que trae la columna `padre`.
    por_nombre: dict[str, str] = {}

    for f in capex:
        # Decisión 2: la errata de nivel de H14.
        es_categoria = f["nivel"] == "Categoría" or (
            f["nivel"] == "Objeto" and f["codigo"] == "H14"
        )
        if not es_categoria:
            continue
        sufijo = FUSIONAR.get(f["codigo"], f["codigo"])
        if sufijo in FUSIONAR.values() and any(c["code"].endswith(f".{sufijo}") for c in salida):
            # Ya existe por la fusión: los objetos de H16 se cuelgan de H15.
            por_nombre[f["nombre"]] = next(
                c["code"] for c in salida if c["code"].endswith(f".{sufijo}")
            )
            continue
        tipo = TIPOS.get(f["padre"])
        if tipo is None:  # Decisión 6: el tipo «Otros» del final se descarta.
            continue
        nombre = "Otros" if f["nombre"] == HUECO else f["nombre"]
        code = f"{tipo}.{sufijo}"
        salida.append({"code": code, "name_es": nombre, "level": "2", "parent_code": tipo})
        # Decisión 3: una categoría puede llamarse igual que su tipo, y entonces
        # los objetos la nombran a ella. El nombre de la hoja manda.
        por_nombre[f["nombre"]] = code
        por_nombre.setdefault(nombre, code)

    # Un tipo cuya única categoría se llama como él —Medioambiente, ESG y
    # Energía— hace que `padre` sea ambiguo. Se resuelve a la categoría, que es
    # lo que dijo el cliente.
    for nombre_tipo, code_tipo in TIPOS.items():
        unicas = [c for c in salida if c["level"] == "2" and c["parent_code"] == code_tipo]
        if nombre_tipo not in por_nombre and len(unicas) >= 1:
            por_nombre[nombre_tipo] = unicas[0]["code"]

    contador: dict[str, int] = {}
    for f in capex:
        if f["nivel"] != "Objeto" or f["codigo"] == "H14":
            continue
        padre = por_nombre.get(f["padre"])
        if padre is None:
            print(f"AVISO: objeto sin categoría, se descarta: {f}", file=sys.stderr)
            continue
        contador[padre] = contador.get(padre, 0) + 1
        nombre = "Otros" if f["nombre"] == HUECO else f["nombre"]
        salida.append(
            {
                "code": f"{padre}.{contador[padre]:02d}",
                "name_es": nombre,
                "level": "3",
                "parent_code": padre,
            }
        )
    return salida


def comparar(nuevo: list[dict[str, str]], csv_actual: Path) -> None:
    """Qué cambia respecto de lo que ya está sembrado."""
    actual = {f["code"]: f["name_es"] for f in csv.DictReader(csv_actual.open())}
    nuevos = {f["code"]: f["name_es"] for f in nuevo}

    altas = [c for c in nuevos if c not in actual]
    bajas = [c for c in actual if c not in nuevos]
    renombres = [
        (c, actual[c], nuevos[c]) for c in nuevos if c in actual and actual[c] != nuevos[c]
    ]

    print(f"IGUALES     {len(nuevos) - len(altas) - len(renombres):4d}")
    print(f"RENOMBRADOS {len(renombres):4d}")
    for c, a, b in renombres:
        print(f"    {c:14} «{a}» → «{b}»")
    print(f"ALTAS       {len(altas):4d}")
    print(f"BAJAS       {len(bajas):4d}   (se quedan en la base: sembrar no borra)")
    for c in bajas:
        print(f"    {c:14} «{actual[c]}»")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("hoja", type=Path)
    ap.add_argument("--csv", type=Path, help="fichero de catálogo a escribir")
    ap.add_argument("--comparar", action="store_true", help="qué cambia respecto de lo sembrado")
    args = ap.parse_args()

    filas = arbol(leer(args.hoja))
    niveles = {n: sum(1 for f in filas if f["level"] == n) for n in "123"}
    print(
        f"{niveles['1']} tipos · {niveles['2']} categorías · {niveles['3']} objetos",
        file=sys.stderr,
    )

    if args.comparar:
        comparar(filas, RAIZ / "data" / "catalogos" / "codigos_capex.csv")
    if args.csv:
        with args.csv.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["code", "name_es", "level", "parent_code"])
            w.writeheader()
            w.writerows(filas)
        print(f"escrito {args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

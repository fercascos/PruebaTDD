#!/usr/bin/env python3
"""Genera los CSV de catálogos **a partir de docs/05-catalogos-y-taxonomias.md**.

`[REC]` La fuente de verdad es el documento de diseño, no un fichero de datos
escrito a mano en paralelo. Si alguien corrige la matriz de zonas en el
documento y no regenera los CSV, la prueba `test_catalogos_no_divergen_del_doc`
falla. Así el documento y los datos no pueden separarse en silencio.

Uso:  python3 tools/generar_catalogos.py [--check]
      --check no escribe nada; sale con código 1 si los CSV están desfasados.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DOC = RAIZ / "docs" / "05-catalogos-y-taxonomias.md"
SALIDA = RAIZ / "data" / "catalogos"


def _slug(texto: str) -> str:
    """Convierte «Salas de uso sanitario» en `SALAS_USO_SANITARIO`.

    Descarta antes las etiquetas de convención (`[SUP]`, `[REQ]`…) y el formato
    Markdown: un encabezado de tabla como «Otros `[SUP]`» debe dar `OTROS`, no
    `OTROS_SUP`, o la matriz de zonas apuntaría a una tipología inexistente.
    """
    limpio_previo = re.sub(r"`?\[(REQ|SUP|REC|LIM|PDV)\]`?", "", texto)
    sin_tildes = "".join(
        c
        for c in unicodedata.normalize("NFD", limpio_previo)
        if unicodedata.category(c) != "Mn"
    )
    limpio = re.sub(r"[^A-Za-z0-9]+", "_", sin_tildes).strip("_").upper()
    return re.sub(r"_+", "_", limpio)


def _celdas(linea: str) -> list[str]:
    return [c.strip() for c in linea.strip().strip("|").split("|")]


def _seccion(texto: str, titulo: str) -> str:
    """Devuelve el cuerpo de una sección `## N.N.` completa, con sus subtítulos.

    Corta solo en el siguiente `## ` de segundo nivel: si cortase también en los
    `###`, se perdería el grueso del contenido, que vive en subsecciones.
    """
    patron = rf"^## {re.escape(titulo)}.*?$(.*?)(?=^## |\Z)"
    m = re.search(patron, texto, re.M | re.S)
    if not m:
        raise SystemExit(f"No se encuentra la sección «{titulo}» en {DOC.name}")
    return m.group(1)


# ─────────────────────────────────────────────────────────────────────────────


def tipologias(doc: str) -> list[dict[str, str]]:
    cuerpo = _seccion(doc, "5.1.")
    filas = []
    for linea in cuerpo.splitlines():
        if not linea.startswith("|") or "---" in linea:
            continue
        c = _celdas(linea)
        if len(c) < 2 or c[0].lower().startswith(("`code", "code", "#")):
            continue
        code = c[0].strip("`*")
        if not re.fullmatch(r"[A-Z_]+", code):
            continue
        filas.append({"code": code, "name_es": c[1].strip("*")})
    return filas


def zonas_y_matriz(doc: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    cuerpo = _seccion(doc, "5.2.")

    # Catálogo de zonas: filas con `CODIGO` en la primera celda
    zonas: list[dict[str, str]] = []
    for linea in cuerpo.splitlines():
        if not linea.startswith("|") or "---" in linea:
            continue
        c = _celdas(linea)
        if len(c) < 3:
            continue
        code = c[0].strip("`")
        if re.fullmatch(r"[A-Z_]+", code) and code != "CODE":
            zonas.append({"code": code, "name_es": c[1]})
    if not zonas:
        raise SystemExit("No se ha extraído ninguna zona de §5.2")
    por_nombre = {z["name_es"]: z["code"] for z in zonas}

    # Matriz: la tabla cuya cabecera contiene las tipologías
    matriz: list[dict[str, str]] = []
    cabecera: list[str] | None = None
    for linea in cuerpo.splitlines():
        if not linea.startswith("|"):
            cabecera = None
            continue
        c = _celdas(linea)
        if "Industrial" in c and "Oficinas" in c:
            cabecera = [_slug(x) for x in c[1:]]
            continue
        if cabecera is None or "---" in linea:
            continue
        nombre_zona = c[0]
        if nombre_zona not in por_nombre:
            continue
        for tipologia, celda in zip(cabecera, c[1:], strict=False):
            if "●" in celda:
                matriz.append({"zone_code": por_nombre[nombre_zona], "typology_code": tipologia})
    if not matriz:
        raise SystemExit("No se ha extraído la matriz de disponibilidad de §5.2")
    return zonas, matriz


def codigos_capex(doc: str) -> list[dict[str, str]]:
    """Extrae el árbol de tres niveles de §5.3.

    Nivel 1 sale de la tabla «Nivel 1 · Categorías»; niveles 2 y 3, de la tabla
    «Nivel 2 y 3», donde cada fila es un capítulo y sus elementos van separados
    por «·» en la segunda celda. Las tres categorías sin desglose (P-03) se
    siembran con capítulo y elemento «General».
    """
    cuerpo = _seccion(doc, "5.3.")
    filas: list[dict[str, str]] = []

    categorias: list[tuple[str, str]] = []
    for linea in cuerpo.splitlines():
        if not linea.startswith("|") or "---" in linea:
            continue
        c = _celdas(linea)
        if len(c) < 3:
            continue
        code = c[0].strip("`")
        if re.fullmatch(r"[A-Z]{2,4}", code) and code != "CODE":
            categorias.append((code, c[1]))
            filas.append({"code": code, "name_es": c[1], "level": "1", "parent_code": ""})
    if not categorias:
        raise SystemExit("No se han extraído las categorías de nivel 1 de §5.3")

    # Nivel 2 y 3 de Hard Costs: | **H01. Estructura** | Cimentación · Solera · … |
    for linea in cuerpo.splitlines():
        if not linea.startswith("|") or "---" in linea:
            continue
        c = _celdas(linea)
        if len(c) != 2:
            continue
        m = re.match(r"^\*\*(H\d{2})\.\s*(.+?)\*\*$", c[0])
        if not m:
            continue
        cap_code = f"HC.{m.group(1)}"
        filas.append(
            {"code": cap_code, "name_es": m.group(2).strip(), "level": "2", "parent_code": "HC"}
        )
        for i, elemento in enumerate(x.strip() for x in c[1].split("·")):
            if not elemento:
                continue
            filas.append(
                {
                    "code": f"{cap_code}.{i + 1:02d}",
                    "name_es": elemento,
                    "level": "3",
                    "parent_code": cap_code,
                }
            )

    # P-03: las categorías sin desglose se siembran con «General»/«General»
    for code, _ in categorias:
        if code == "HC":
            continue
        cap_code = f"{code}.General"
        filas.append({"code": cap_code, "name_es": "General", "level": "2", "parent_code": code})
        filas.append(
            {
                "code": f"{cap_code}.01",
                "name_es": "General",
                "level": "3",
                "parent_code": cap_code,
            }
        )
    return filas


def riesgos(doc: str) -> list[dict[str, str]]:
    """Grados de riesgo con su **definición íntegra**, tal cual la escribió el cliente."""
    cuerpo = _seccion(doc, "5.4.")
    filas = []
    for linea in cuerpo.splitlines():
        if not linea.startswith("|") or "---" in linea:
            continue
        c = _celdas(linea)
        if len(c) < 4:
            continue
        code = c[0].strip("`")
        if not re.fullmatch(r"0[1-4]", code):
            continue
        filas.append(
            {"code": code, "name_es": c[1], "score": c[2].strip("`"), "definition_es": c[3]}
        )
    if len(filas) != 4:
        raise SystemExit(f"Se esperaban 4 grados de riesgo, se han extraído {len(filas)}")
    return filas


def conceptos(doc: str) -> list[dict[str, str]]:
    cuerpo = _seccion(doc, "5.5.")
    filas = []
    for linea in cuerpo.splitlines():
        if not linea.startswith("|") or "---" in linea:
            continue
        c = _celdas(linea)
        if len(c) < 2:
            continue
        code = c[0].strip("`")
        if re.fullmatch(r"[A-Z_]+", code) and code != "CODE":
            filas.append({"code": code, "name_es": c[1]})
    return filas


def horizontes(doc: str) -> list[dict[str, str]]:
    cuerpo = _seccion(doc, "5.6.")
    filas = []
    for linea in cuerpo.splitlines():
        if not linea.startswith("|") or "---" in linea:
            continue
        c = _celdas(linea)
        if len(c) < 4:
            continue
        code = c[0].strip("`")
        if not re.fullmatch(r"[A-Z_]+", code) or code == "CODE":
            continue
        anios = c[2].strip("*")
        m = re.match(r"(\d+)\s*-\s*(\d+)", anios)
        filas.append(
            {
                "code": code,
                "name_es": c[1],
                "year_from": m.group(1) if m else "",
                "year_to": m.group(2) if m else "",
                "is_execution_term": "true" if m else "false",
            }
        )
    return filas


def _escribir(nombre: str, campos: list[str], filas: list[dict[str, str]], comprobar: bool) -> bool:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=campos, lineterminator="\n")
    w.writeheader()
    w.writerows(filas)
    contenido = buf.getvalue()
    destino = SALIDA / nombre
    if comprobar:
        actual = destino.read_text(encoding="utf-8") if destino.exists() else ""
        if actual != contenido:
            print(f"DESFASADO: {destino.relative_to(RAIZ)}", file=sys.stderr)
            return False
        return True
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")
    print(f"{destino.relative_to(RAIZ)}: {len(filas)} filas")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="no escribe; falla si hay desfase")
    args = ap.parse_args()

    doc = DOC.read_text(encoding="utf-8")
    tips = tipologias(doc)
    zonas, matriz = zonas_y_matriz(doc)
    codigos = codigos_capex(doc)

    ries = riesgos(doc)
    conc = conceptos(doc)
    hor = horizontes(doc)

    ok = all(
        [
            _escribir("tipologias.csv", ["code", "name_es"], tips, args.check),
            _escribir("zonas.csv", ["code", "name_es"], zonas, args.check),
            _escribir(
                "zonas_por_tipologia.csv", ["zone_code", "typology_code"], matriz, args.check
            ),
            _escribir(
                "codigos_capex.csv",
                ["code", "name_es", "level", "parent_code"],
                codigos,
                args.check,
            ),
            _escribir(
                "riesgos.csv", ["code", "name_es", "score", "definition_es"], ries, args.check
            ),
            _escribir("conceptos.csv", ["code", "name_es"], conc, args.check),
            _escribir(
                "horizontes.csv",
                ["code", "name_es", "year_from", "year_to", "is_execution_term"],
                hor,
                args.check,
            ),
        ]
    )

    niveles = {n: sum(1 for c in codigos if c["level"] == n) for n in ("1", "2", "3")}
    print(
        f"\nResumen: {len(tips)} tipologías · {len(zonas)} zonas · {len(matriz)} relaciones\n"
        f"         árbol CAPEX: {niveles['1']} categorías + {niveles['2']} capítulos + "
        f"{niveles['3']} elementos = {len(codigos)} nodos\n"
        f"         {len(ries)} grados de riesgo · {len(conc)} conceptos · {len(hor)} horizontes"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

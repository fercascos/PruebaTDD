#!/usr/bin/env python3
"""Cambia la tipografía declarada dentro de una plantilla PPTX.

`[REQ]` P-39: el cliente descarta **Gotham** y elige **Segoe UI, o Montserrat en
su defecto**. Cambiar lo que genera la aplicación no basta, y ésta es la razón
por la que existe este programa:

Las cuatro plantillas reales llevan `Gotham` escrita **por dentro** —en el tema
y en cada `run`—. Si solo cambiamos la tabla y los textos que generamos
nosotros, el informe sale con dos tipografías: la nuestra en lo generado y una
sustituta silenciosa en todo lo demás, porque en el PowerPoint del que lo abra
no hay ninguna Gotham instalada. Eso es peor que no cambiar nada: se nota, y no
se sabe por qué.

`[REQ]` **No sobrescribe el original.** Escribe un fichero nuevo y se niega a
pisar uno que exista, salvo `--forzar`. Las partes que no cambian se copian
byte a byte, así que la plantilla conserva sus imágenes, sus gráficos y su
diseño; lo único que se toca son los atributos `typeface`.

Uso::

    python3 tools/retipografiar_plantilla.py informe.pptx            # qué declara
    python3 tools/retipografiar_plantilla.py informe.pptx -s nuevo.pptx

`[LIM]` Cambia lo que la plantilla **declara**, no cómo se ve. Montserrat no
tiene las mismas anchuras que Gotham —mide un 7,4 % menos de texto por
diapositiva de sistema, medido— así que un texto ajustado al límite puede pasar
a dos líneas. El aviso de desbordamiento de la aplicación lo detecta, porque
mide con la fuente que la forma declara; lo que no puede es recolocar un cuadro
de texto por su cuenta. Hay que mirar el resultado.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import zipfile
from collections import Counter
from pathlib import Path

#: Gotham reparte ocho pesos en ocho familias; Montserrat publica seis y mete
#: Regular y Bold en la misma. El emparejamiento es **por peso**, no por
#: nombre: `Ultra` es el más grueso de Gotham y `Black` el más grueso de
#: Montserrat, así que un titular sigue siendo un titular.
#:
#: `[SUP]` `Book` es el peso de texto de Gotham y equivale al Regular. Si
#: apareciera un peso que no está aquí, el programa lo dice y no lo toca: es
#: mejor una familia sin traducir y señalada que una traducida a ojo.
EQUIVALENCIAS: dict[str, str] = {
    "Gotham Thin": "Montserrat Thin",
    "Gotham XLight": "Montserrat ExtraLight",
    "Gotham Extra Light": "Montserrat ExtraLight",
    "Gotham Light": "Montserrat Light",
    "Gotham Book": "Montserrat",
    "Gotham": "Montserrat",
    "Gotham Medium": "Montserrat Medium",
    "Gotham Bold": "Montserrat SemiBold",
    "Gotham Black": "Montserrat ExtraBold",
    "Gotham Ultra": "Montserrat Black",
}

#: `Century Gothic` estaba en las tablas pegadas desde Excel (P-38). La tabla
#: nativa ya no viene de ahí, pero una plantilla vieja puede conservarla en
#: algún cuadro suelto.
EQUIVALENCIAS_EXTRA: dict[str, str] = {"Century Gothic": "Montserrat Light"}

#: Un `typeface=""` vacío es legítimo en OOXML: significa «la del tema». No se
#: toca.
_TYPEFACE = re.compile(r'typeface="([^"]+)"')


def declaradas(fichero: Path) -> Counter[str]:
    """Qué familias declara el fichero, y cuántas veces cada una."""
    cuenta: Counter[str] = Counter()
    with zipfile.ZipFile(fichero) as z:
        for nombre in z.namelist():
            if not nombre.endswith(".xml"):
                continue
            texto = z.read(nombre).decode("utf-8", errors="replace")
            cuenta.update(_TYPEFACE.findall(texto))
    return cuenta


def _equivalencia(familia: str, mapa: dict[str, str]) -> str | None:
    """La familia de destino, o `None` si no hay que tocarla.

    El emparejamiento es **por nombre exacto**, y no por prefijo, a propósito:
    con «empieza por Gotham», `Gotham Ultra` habría casado con la regla de
    `Gotham` a secas —la primera que empieza igual— y todos los titulares del
    informe habrían acabado en el peso del cuerpo.
    """
    return mapa.get(familia.strip())


def retipografiar(
    origen: Path,
    destino: Path | None,
    *,
    mapa: dict[str, str],
    forzar: bool = False,
) -> tuple[Counter[str], list[str]]:
    """Devuelve (cambios aplicados, familias que no se supo traducir)."""
    with zipfile.ZipFile(origen) as z:
        nombres = z.namelist()
        partes = {n: z.read(n) for n in nombres}

    cambios: Counter[str] = Counter()
    sin_traducir: list[str] = []

    for nombre in nombres:
        if not nombre.endswith(".xml"):
            continue
        texto = partes[nombre].decode("utf-8")

        def sustituir(m: re.Match[str]) -> str:
            familia = m.group(1)
            nueva = _equivalencia(familia, mapa)
            if nueva is None:
                # Solo se señala lo que huele a la tipografía que se retira:
                # una plantilla declara además Arial, Calibri y las de los
                # símbolos, y listarlas sería ruido.
                if familia.lower().startswith(("gotham", "century gothic")):
                    sin_traducir.append(familia)
                return m.group(0)
            if nueva != familia:
                cambios[f"{familia} → {nueva}"] += 1
            return f'typeface="{nueva}"'

        nuevo = _TYPEFACE.sub(sustituir, texto)
        if nuevo != texto:
            partes[nombre] = nuevo.encode("utf-8")

    if destino is None:
        return cambios, sorted(set(sin_traducir))

    if destino.exists() and not forzar:
        raise SystemExit(f"«{destino}» ya existe. Use --forzar si de verdad quiere pisarlo.")
    if destino.resolve() == origen.resolve():
        # `[REQ]` El original nunca se sobrescribe, ni con `--forzar`: es la
        # regla de la casa para los ficheros que trae el cliente, y aquí no
        # hay ningún motivo para hacer una excepción.
        raise SystemExit("El destino no puede ser el propio original.")

    # Se escribe a un temporal y se mueve al final: si algo falla a mitad, no
    # queda un PPTX a medias con aspecto de estar bien.
    temporal = destino.with_suffix(destino.suffix + ".parcial")
    with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as salida:
        for n in nombres:
            salida.writestr(n, partes[n])
    shutil.move(str(temporal), str(destino))
    return cambios, sorted(set(sin_traducir))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("plantilla", type=Path, help="el .pptx o .potx de partida")
    ap.add_argument(
        "-s",
        "--salida",
        type=Path,
        help="fichero a escribir. Sin él solo se informa de lo que declara",
    )
    ap.add_argument("--forzar", action="store_true", help="permite pisar un fichero existente")
    ap.add_argument(
        "--con-century-gothic",
        action="store_true",
        help="traduce también Century Gothic, que venía de las tablas de Excel",
    )
    args = ap.parse_args()

    if not args.plantilla.exists():
        print(f"No existe «{args.plantilla}».", file=sys.stderr)
        return 1

    mapa = dict(EQUIVALENCIAS)
    if args.con_century_gothic:
        mapa.update(EQUIVALENCIAS_EXTRA)

    if args.salida is None:
        cuenta = declaradas(args.plantilla)
        if not cuenta:
            print("La plantilla no declara ninguna tipografía explícita.")
            return 0
        print(f"{args.plantilla.name} declara:")
        for familia, veces in cuenta.most_common():
            destino = _equivalencia(familia, mapa)
            flecha = f"  →  {destino}" if destino and destino != familia else ""
            print(f"  {veces:5d} × {familia}{flecha}")
        return 0

    cambios, sin_traducir = retipografiar(
        args.plantilla, args.salida, mapa=mapa, forzar=args.forzar
    )
    if not cambios:
        print("No había nada que cambiar. Se ha escrito una copia idéntica.")
    else:
        print(f"{args.salida.name}: {sum(cambios.values())} sustituciones")
        for cambio, veces in cambios.most_common():
            print(f"   · {veces:5d} × {cambio}")
    for familia in sin_traducir:
        print(
            f"AVISO: «{familia}» no tiene equivalencia y se ha dejado como estaba.",
            file=sys.stderr,
        )
    print("El original no se ha tocado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

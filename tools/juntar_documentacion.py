"""Junta la documentación de migración en **un solo fichero** para subirlo.

Para quien no va a conectar el repositorio y lo que tiene delante es un cuadro
de «sube un fichero»: ocho documentos sueltos se suben de ocho en ocho y se
desordenan; uno solo, no.

    python3 tools/juntar_documentacion.py              # a la salida estándar
    python3 tools/juntar_documentacion.py -s doc.md    # a un fichero

`[REQ]` **El resultado no se versiona.** Es una copia de ficheros que sí están
en el repositorio, y una copia que envejece dentro del mismo repositorio es
exactamente lo que hace que alguien lea una aplicación que ya no existe —pasó
con el prototipo ya compilado—. Se genera cuando hace falta y se tira.

Tres cosas que hay que hacer al concatenar, y que son la razón de que esto sea
un guion y no un `cat`:

1. **Bajar un nivel los títulos** de cada documento, para que las partes queden
   por encima y el índice del resultado tenga sentido.
2. **Reescribir los enlaces relativos.** `[x](03-lo-que-no-viaja.md)` dentro de
   un fichero suelto no lleva a ninguna parte. Los que apuntan a un documento
   incluido pasan a ser enlaces internos; los demás, a su nombre en crudo, que
   es información honesta: dice dónde mirar en el repositorio.
3. **Decir de dónde sale cada parte**, para que quien lo lea sepa qué fichero
   abrir si quiere la versión viva.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

#: Qué se junta y en qué orden. El orden no es alfabético: es el de lectura
#: —las reglas primero, porque enmarcan todo lo demás— y está razonado en
#: `docs/migracion/README.md`.
PARTES: tuple[tuple[str, str], ...] = (
    ("CLAUDE.md", "Cómo se trabaja en este proyecto"),
    ("docs/migracion/README.md", "Traer el proyecto a otro entorno"),
    ("docs/migracion/01-el-entorno.md", "Qué tiene que ofrecer el entorno"),
    ("docs/migracion/02-arrancar-desde-cero.md", "Del «git clone» a la aplicación funcionando"),
    ("docs/migracion/03-lo-que-no-viaja.md", "Lo que no viaja en el repositorio"),
    ("docs/migracion/04-comprobar-la-migracion.md", "Comprobar que la migración ha salido"),
    ("docs/migracion/05-estado-y-pendientes.md", "Estado y pendientes"),
    ("docs/migracion/06-portar-a-otro-stack.md", "Portar a otro stack"),
)

ENLACE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
TITULO = re.compile(r"^(#{1,5}) ", re.MULTILINE)


def _ancla(titulo: str) -> str:
    """El ancla que GitHub le da a un título: minúsculas, sin signos, con guiones."""
    limpio = re.sub(r"[^\w\s-]", "", titulo.lower(), flags=re.UNICODE)
    return re.sub(r"[\s_]+", "-", limpio).strip("-")


def _sin_el_titulo(texto: str) -> str:
    """Quita la primera línea `# …`: el título lo pone la parte que la envuelve."""
    lineas = texto.splitlines()
    if lineas and lineas[0].startswith("# "):
        return "\n".join(lineas[1:]).lstrip("\n")
    return texto


def _bajar_titulos(texto: str) -> str:
    """`##` pasa a `###`. Los bloques de código se dejan en paz.

    Dentro de un bloque ``` una línea que empiece por `#` es un comentario de
    shell, no un título, y bajarla convertiría `# comentario` en `## comentario`
    dentro del código que alguien va a copiar y pegar.
    """
    trozos = texto.split("```")
    for i in range(0, len(trozos), 2):  # los pares están fuera de los bloques
        trozos[i] = TITULO.sub(lambda m: f"#{m.group(1)} ", trozos[i])
    return "```".join(trozos)


def _reescribir_enlaces(texto: str, origen: Path, anclas: dict[str, str]) -> str:
    """Los enlaces relativos, resueltos contra el fichero único."""

    def sustituir(m: re.Match[str]) -> str:
        etiqueta, destino = m.group(1), m.group(2)
        if destino.startswith(("http", "#", "mailto")):
            return m.group(0)
        fichero = destino.split("#")[0]
        ruta = (origen.parent / fichero).resolve()
        try:
            relativa = ruta.relative_to(RAIZ).as_posix()
        except ValueError:
            return f"`{fichero}`"
        if relativa in anclas:
            return f"[{etiqueta}](#{anclas[relativa]})"
        # Fuera del fichero único: se nombra la ruta, que es lo útil para quien
        # tenga el repositorio delante, en vez de un enlace que no lleva a nada.
        #
        # Salvo que la etiqueta YA sea esa ruta o ese nombre, que es lo normal
        # cuando el enlace se escribió como ``[`docs/18-….md`](../18-….md)``:
        # repetirla daría «docs/18-….md (`docs/18-….md`)».
        desnuda = etiqueta.strip("`")
        if desnuda in (relativa, Path(relativa).name, fichero):
            return f"`{relativa}`"
        return f"{etiqueta} (`{relativa}`)"

    return ENLACE.sub(sustituir, texto)


def juntar() -> str:
    anclas = {ruta: _ancla(f"{i}. {titulo}") for i, (ruta, titulo) in enumerate(PARTES, 1)}
    hoy = dt.date.today().isoformat()

    cabecera = [
        "# Due diligence técnica · documentación para migrar el proyecto",
        "",
        # El número sale de `PARTES`, no escrito a mano: estaba puesto a mano,
        # se añadió una parte y la portada siguió diciendo «siete».
        f"> **Esto es una copia juntada de {len(PARTES)} ficheros del repositorio**, generada",
        f"> el {hoy} con `python3 tools/juntar_documentacion.py`. Existe para subirla de una",
        "> vez a un sitio donde no se puede conectar el repositorio.",
        ">",
        "> **Si puedes conectar el repositorio, no uses esto**: `CLAUDE.md` se lee solo al",
        "> abrir el proyecto y el resto viaja dentro. Dos copias de lo mismo divergen en",
        "> cuanto alguien toca una.",
        "",
        "## Qué hay aquí dentro",
        "",
        "| | Parte | Sale de |",
        "|---|---|---|",
    ]
    for i, (ruta, titulo) in enumerate(PARTES, 1):
        cabecera.append(f"| {i} | [{titulo}](#{anclas[ruta]}) | `{ruta}` |")
    cabecera += [
        "",
        "La parte 1 son **las reglas de trabajo**: va primero porque enmarca todo lo",
        "demás. Si vas a pegar algo en las instrucciones de un proyecto en vez de",
        "subirlo como fichero, es esa.",
        "",
    ]

    piezas = ["\n".join(cabecera)]
    for i, (ruta, titulo) in enumerate(PARTES, 1):
        origen = RAIZ / ruta
        cuerpo = _reescribir_enlaces(
            _bajar_titulos(_sin_el_titulo(origen.read_text(encoding="utf-8"))), origen, anclas
        )
        piezas.append(
            f"---\n\n# {i}. {titulo}\n\n"
            f"<sub>En el repositorio: `{ruta}`</sub>\n\n{cuerpo.rstrip()}\n"
        )
    return "\n".join(piezas)


def main() -> int:
    trozos = argparse.ArgumentParser(description=__doc__)
    trozos.add_argument("-s", "--salida", type=Path, help="fichero donde escribir")
    args = trozos.parse_args()

    texto = juntar()
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(texto, encoding="utf-8")
        kb = len(texto.encode("utf-8")) / 1024
        print(f"{args.salida} · {kb:.0f} KB · {len(PARTES)} partes", file=sys.stderr)
    else:
        sys.stdout.write(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

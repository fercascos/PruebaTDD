"""Convierte la página del artefacto en un HTML suelto que funciona sin red.

La página que se publica como artefacto va sin `<!doctype>` porque el anfitrión
la envuelve él, y pide las tipografías a Google Fonts. Un fichero que alguien se
descarga y abre con doble clic no tiene ese anfitrión y puede no tener conexión,
así que aquí se añaden la envoltura y un reinicio mínimo de estilos, y **se
incrustan las tipografías**: un mockup que se enseña en una reunión no puede
depender de que haya wifi.

    python tools/mockup/construir.py --capturas /tmp/capturas --salida /tmp/mockup.html
    python tools/mockup/empaquetar.py --entrada /tmp/mockup.html --salida /tmp/suelto.html

`[REQ]` No hay claves ni credenciales aquí: Google Fonts sirve las tipografías
sin autenticación. Lo único que sale a Internet es la descarga de los `.woff2`
al construir, y el fichero resultante ya no pide nada.
"""

import argparse
import base64
import pathlib
import re
import urllib.request

CSS_URL = (
    "https://fonts.googleapis.com/css2?family=Archivo:wght@600;700"
    "&family=IBM+Plex+Mono:wght@400;500"
    "&family=IBM+Plex+Sans:wght@400;500;600&display=swap"
)
#: Google devuelve un CSS distinto según el navegador que dice pedirlo. Sin un
#: agente moderno contesta con `.ttf`, que pesa el triple que `.woff2`.
AGENTE = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

RESET = """
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0}
img,svg{display:block;max-width:100%}
button{font:inherit;color:inherit}
"""


def bajar(url: str) -> bytes:
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})  # noqa: S310
    with urllib.request.urlopen(peticion, timeout=60) as respuesta:  # noqa: S310
        return respuesta.read()


def tipografias() -> tuple[str, int]:
    """Los `@font-face` del subconjunto latino, con el `.woff2` dentro.

    Solo `latin`: cubre el castellano entero —acentos, eñe, apertura de
    interrogación— y los signos que usa la página («», ›, —). Los demás
    subconjuntos multiplicarían el peso sin pintar un solo carácter.
    """
    css = bajar(CSS_URL).decode()
    trozos = []
    for subconjunto, bloque in re.findall(
        r"/\* ([a-z-]+) \*/\s*(@font-face \{.*?\})", css, re.S
    ):
        if subconjunto != "latin":
            continue
        url = re.search(r"url\((https://[^)]+)\)", bloque).group(1)
        datos = base64.b64encode(bajar(url)).decode()
        trozos.append(bloque.replace(url, f"data:font/woff2;base64,{datos}"))
    if not trozos:
        raise SystemExit("Google Fonts no devolvió ningún bloque `latin`")
    return "\n".join(trozos), len(trozos)


def main() -> None:
    opciones = argparse.ArgumentParser(description=__doc__)
    opciones.add_argument(
        "--entrada", type=pathlib.Path, default=pathlib.Path("mockup.html")
    )
    opciones.add_argument(
        "--salida", type=pathlib.Path, default=pathlib.Path("mockup-suelto.html")
    )
    args = opciones.parse_args()

    cuerpo = args.entrada.read_text()
    fuentes, cuantas = tipografias()

    # Fuera el enlace a Google: el fichero tiene que abrir sin salir a Internet.
    cuerpo = re.sub(r'<link rel="preconnect"[^>]*>\s*', "", cuerpo)
    cuerpo = re.sub(
        r'<link rel="stylesheet" href="https://fonts\.googleapis[^>]*>\s*', "", cuerpo
    )
    titulo = re.search(r"<title>(.*?)</title>", cuerpo).group(1)
    cuerpo = cuerpo.replace(f"<title>{titulo}</title>\n", "", 1)

    args.salida.write_text(
        "<!doctype html>\n"
        '<html lang="es">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{titulo}</title>\n"
        f"<style>{RESET}{fuentes}</style>\n"
        "</head>\n<body>\n"
        f"{cuerpo}\n"
        "</body>\n</html>\n"
    )
    print(
        f"{cuantas} tipografías incrustadas · {args.salida} · "
        f"{args.salida.stat().st_size / 1024 / 1024:.2f} MB"
    )


if __name__ == "__main__":
    main()

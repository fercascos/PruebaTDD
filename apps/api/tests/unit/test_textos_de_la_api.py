"""La tabla de traducciones de la API, vigilada. `[REQ]` 0030

`data/api/textos_en.csv` traduce lo que **escribe el servidor**: los mensajes
de error que ve un usuario, el avance de cada fase, la fila de los hallazgos
sin clasificar. Una tabla así se estropea de dos maneras y ninguna hace ruido:

1. **Se llena de entradas muertas.** Alguien reescribe un mensaje y la
   traducción vieja se queda ahí, sin que nada la use. La siguiente persona la
   lee y cree que el mensaje está traducido.
2. **Se queda corta.** Un `raise` nuevo escribe una frase que no está en la
   tabla, y en inglés sale en castellano. No falla nada: el respaldo devuelve
   la clave, que **es** el castellano.

Estas pruebas leen el árbol de sintaxis de la API, no el texto, porque una
frase puede estar partida en varios literales —`"El código "` `"no existe"`—
y es el compilador quien los junta. Buscarlas con una expresión regular daría
por muerta media tabla.

`[LIM]` No se comprueba que una frase **llegue** a una pantalla, solo que
exista en el código. Un mensaje que ya no se lanza nunca seguiría contando
como vivo. Para eso hace falta mirar la aplicación, que es como se encontró
esta capa entera.
"""

from __future__ import annotations

import ast
import csv
from pathlib import Path

import pytest

RAIZ_API = Path(__file__).resolve().parents[2]
FUENTE = RAIZ_API / "src" / "tdd"
CSV = RAIZ_API.parents[1] / "data" / "api" / "textos_en.csv"


def _tabla() -> dict[str, str]:
    with CSV.open(encoding="utf-8", newline="") as fh:
        return {f["es"]: f["en"] for f in csv.DictReader(fh)}


def _ficheros() -> list[Path]:
    return [f for f in sorted(FUENTE.rglob("*.py")) if "migrations" not in str(f)]


def _literales_y_claves() -> tuple[set[str], set[str]]:
    """`(toda cadena del código, las que pasan por traducir())`.

    La primera incluye la segunda. Hacen falta las dos porque hay **dos vías**
    de traducción y una entrada viva puede ir por cualquiera:

    * El `detail` de un `HTTPException` lo traduce el manejador de `main.py`,
      a la salida, así que su frase nunca aparece dentro de un `traducir(`.
    * El resto se traduce en su sitio, con `idioma.traducir(...)`.
    """
    literales: set[str] = set()
    claves: set[str] = set()
    for f in _ficheros():
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                literales.add(n.value)
            elif isinstance(n, ast.Call):
                fn = n.func
                nombre = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if nombre not in ("traducir", "traducir_a"):
                    continue
                args = n.args[1:] if nombre == "traducir_a" else n.args
                if args and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
                    claves.add(args[0].value)
    return literales, claves


def test_ninguna_entrada_esta_muerta() -> None:
    """Toda clave de la tabla corresponde a una frase que el código escribe.

    Si falla, o la frase cambió en el código y hay que actualizar la clave, o
    la entrada sobra. Las dos se arreglan en el CSV.
    """
    literales, _ = _literales_y_claves()
    muertas = sorted(k for k in _tabla() if k not in literales)
    assert muertas == [], (
        "Estas traducciones no corresponden a ninguna frase del código:\n  " + "\n  ".join(muertas)
    )


def test_ninguna_llamada_a_traducir_se_queda_sin_traduccion() -> None:
    """Lo contrario: una clave que se traduce a mano y no está en la tabla.

    Es el caso que de verdad se ve: `idioma.traducir("…")` con la frase fuera
    del CSV devuelve el castellano, y sale en una pantalla inglesa.
    """
    _, claves = _literales_y_claves()
    tabla = _tabla()
    faltan = sorted(k for k in claves if k not in tabla)
    assert faltan == [], (
        "Estas frases pasan por `traducir()` y no tienen inglés:\n  " + "\n  ".join(faltan)
    )


def test_ninguna_traduccion_vacia_ni_copiada() -> None:
    """Una traducción vacía es peor que no tenerla: el respaldo ya no actúa."""
    tabla = _tabla()
    vacias = sorted(k for k, v in tabla.items() if not v.strip())
    assert vacias == [], f"Traducciones vacías: {vacias}"
    # Y copiar la clave en el valor es el despiste clásico al traducir a mano.
    # «El proyecto» no entra en la excepción: en inglés es «The project».
    copiadas = sorted(k for k, v in tabla.items() if k == v)
    assert copiadas == [], f"La clave está copiada en el valor: {copiadas}"


def test_los_huecos_de_la_frase_inglesa_son_los_de_la_castellana() -> None:
    """`{cuantos}` en castellano y `{count}` en inglés revienta al formatear.

    `str.format` lanza `KeyError` con un hueco que no se le pasa, y lo haría
    **dentro de un `raise`**: el usuario vería un 500 en vez del mensaje que
    explica qué ha hecho mal. Es el fallo más caro de esta tabla y el más
    fácil de cometer, porque traducir invita a renombrar.
    """
    import re

    hueco = re.compile(r"\{(\w+)\}")
    malas = []
    for es, en in _tabla().items():
        if set(hueco.findall(es)) != set(hueco.findall(en)):
            malas.append(f"{es}\n    → {en}")
    assert malas == [], "Los huecos no coinciden:\n  " + "\n  ".join(malas)


def test_ningun_mensaje_de_error_se_queda_sin_traducir() -> None:
    """Todo `detail` literal de un `HTTPException` está en la tabla.

    `[REQ]` Es **la** prueba de esta capa, y la que convierte el truco de
    traducir a la salida en algo fiable. El manejador traduce lo que le llega;
    si la frase no está en la tabla devuelve la clave, o sea el castellano, y
    el usuario ve un error en español en una pantalla inglesa **sin que nada
    falle**. Un `raise HTTPException(404, "Equipo no encontrado")` nuevo falla
    aquí el día que se escribe.

    Solo mira los literales: un `detail` compuesto con un `f-string` no tiene
    una frase que buscar, y por eso esos se convierten en su sitio a
    `idioma.traducir("… {x}", x=…)`, que vigila
    `test_ninguna_llamada_a_traducir_se_queda_sin_traduccion`.
    """
    tabla = _tabla()
    pendientes: list[str] = []
    for f in _ficheros():
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if not isinstance(n, ast.Call):
                continue
            nombre = getattr(n.func, "id", "") or getattr(n.func, "attr", "")
            if nombre != "HTTPException":
                continue
            detalles = list(n.args) + [k.value for k in n.keywords if k.arg == "detail"]
            for a in detalles:
                literal = isinstance(a, ast.Constant) and isinstance(a.value, str)
                if literal and a.value not in tabla:  # type: ignore[union-attr]
                    pendientes.append(f"{f.name}:{a.lineno}  {a.value}")  # type: ignore[union-attr]
    assert pendientes == [], (
        "Estos mensajes de error saldrían en castellano en una pantalla inglesa:\n  "
        + "\n  ".join(sorted(pendientes))
    )


@pytest.mark.parametrize(
    ("es", "en"),
    [
        # Tres que importan de verdad, por si alguien «mejora» la tabla.
        ("Credencial no válida", "Invalid credential"),
        ("Sesión no válida", "Invalid session"),
        ("sin generar", "not generated"),
    ],
)
def test_lo_que_no_se_toca(es: str, en: str) -> None:
    assert _tabla()[es] == en

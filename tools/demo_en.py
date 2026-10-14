"""El texto libre del encargo de demostración, en inglés.

`[REQ]` `sembrar_demo.py` crea un encargo de mentira con datos **inventados**:
dos naves en un polígono que no existe, diez hallazgos, una memoria técnica,
una visita. Su texto está escrito en castellano técnico de verdad, porque de
eso vive la demostración: enseña cómo se lee un informe real, no cómo se rellena
un formulario.

Esto lo traduce, para poder enseñar el prototipo a alguien que no lee
castellano.

## Por qué la traducción va en el borde y no en cada sitio

El seeder tiene unas 1.200 líneas y el texto está repartido por todas: en
constantes, en literales dentro de un bucle, en `f-string`. Pasar un idioma por
todas ellas es mucha cirugía en un fichero que no es producción, y bastaría
olvidarse de una para que la demostración saliera mezclada.

Así que se traduce **en el único sitio por el que pasa todo**: el cuerpo de la
petición HTTP, en `Api._pedir`. `traducir()` recorre el JSON y sustituye las
cadenas que estén en esta tabla. Ningún sitio puede olvidarse, porque no hay
sitios: hay uno.

`[LIM]` La contrapartida es que la tabla es **exacta y completa o no sirve**: una
frase que cambie en el seeder y no aquí sale en castellano. Por eso
`sembrar_demo.py --idioma en` **enumera al terminar** todo el texto que ha
pasado sin traducir, y por eso hay una prueba que compara las dos listas.

## Qué NO está aquí

Los nombres de catálogo —zonas, capítulos de CAPEX, conceptos, horizontes— no
se traducen aquí: los traduce la base de datos con `nombre(name_es, name_en)`,
con el inglés del propio cliente (migración 0029). Esta tabla es solo el texto
que una persona escribiría: descripciones de hallazgos, valoraciones,
descriptivos de la memoria, notas de la visita.
"""

from __future__ import annotations

import csv
import re
import uuid as _uuid
from pathlib import Path
from typing import Any

#: Castellano → inglés. El castellano es la clave porque es el original, igual
#: que en el frontend (`i18n/textos.ts`): una frase que falte sale en
#: castellano, que **se lee** como lo que es.
#:
#: `[SUP]` Es inglés técnico de informe de *technical due diligence*. Donde el
#: original nombra una norma o un documento español se conserva el nombre
#: —«CTE DB-SI», «Licencia de Primera Ocupación»—, porque traducirlo dejaría al
#: lector sin saber qué pedir.
CSV = Path(__file__).resolve().parents[1] / "data" / "demo" / "textos_en.csv"


def _cargar() -> dict[str, str]:
    """Lee la tabla del CSV.

    Va en un fichero de datos y no incrustada aquí por dos razones. La primera
    es práctica: son 110 frases largas de castellano técnico, y como literales
    de Python el formateador y el límite de 100 columnas las parten por donde
    le conviene, de modo que revisar una traducción obliga a leer código. La
    segunda es quién las revisa: esto lo tiene que poder corregir quien firma
    el informe, que sabe de edificios y no de Python.

    Es el mismo criterio que `data/catalogos/traducciones_en.csv`, y por eso
    tiene el mismo formato.
    """
    if not CSV.exists():
        raise FileNotFoundError(f"No se encuentra {CSV}, que trae el texto en inglés de la demo.")
    with CSV.open(encoding="utf-8", newline="") as fh:
        return {f["es"]: f["en"] for f in csv.DictReader(fh)}


TEXTOS: dict[str, str] = _cargar()


#: Claves cuyo valor **no es texto para una persona** aunque lo parezca: una
#: credencial, un identificador, un código de catálogo. Traducir la contraseña
#: del administrador de la demostración impediría entrar en ella.
NO_ES_TEXTO = frozenset(
    {"email", "password", "token", "code", "codigo", "capex_code", "status", "slug"}
)

#: El separador con el que el seeder compone un descriptivo: «nombre (N ud) —
#: descripción». Se parte para que la tabla guarde frases atómicas y no las
#: veinte combinaciones que salen de juntarlas.
UNION = " — "
UNIDADES = re.compile(r"^(.*) \((\d+) ud\)$")


def traducir(valor: Any, idioma: str, *, clave: str = "") -> Any:
    """Recorre un cuerpo JSON y traduce las cadenas que estén en la tabla.

    Devuelve el valor **tal cual** si el idioma es el castellano, para que el
    camino normal del seeder no pague nada por que esto exista.

    Lo que no está en la tabla pasa sin tocar y queda apuntado en
    `SIN_TRADUCIR`, que es lo que el seeder enumera al terminar. No se inventa
    una traducción ni se omite el dato: sale el castellano, y se dice.
    """
    if idioma == "es":
        return valor
    if isinstance(valor, str):
        return valor if clave in NO_ES_TEXTO else _cadena(valor)
    if isinstance(valor, dict):
        return {k: traducir(v, idioma, clave=k) for k, v in valor.items()}
    if isinstance(valor, list):
        return [traducir(v, idioma, clave=clave) for v in valor]
    if isinstance(valor, tuple):
        # Los ficheros de un `multipart`: `(nombre, contenido, tipo)`. El
        # contenido es binario y no se toca.
        return valor
    return valor


def _cadena(valor: str) -> str:
    """Traduce una cadena, **por segmentos** si viene compuesta.

    El seeder compone descriptivos juntando piezas: «Enfriadora aire-agua en
    cubierta (2 ud) — Dos unidades en la cubierta…». Si la tabla tuviera que
    guardar la frase entera, tendría las veinte combinaciones además de las
    piezas, y cada vez que alguien cambiara una cantidad habría que volver a
    traducirla.

    Así que se parte por el separador, se le quita el recuento de unidades, se
    traduce la pieza y se recompone. `ud` pasa a `units`, que es lo que el
    cliente pone en su plantilla inglesa.

    El recuento se convierte **aunque la cabeza no esté en la tabla**: el
    seeder lee de la API un nombre que ya viene traducido y vuelve a componer
    con él, así que la cabeza llega en inglés y buscarla en una tabla
    castellano→inglés no encuentra nada. Sin esto, la demostración enseñaba
    «Air-to-water chiller on the roof (2 ud)».
    """
    if directa := TEXTOS.get(valor):
        return directa
    if UNION in valor:
        return UNION.join(_cadena(parte) for parte in valor.split(UNION))
    if m := UNIDADES.match(valor):
        return f"{_cadena(m.group(1))} ({m.group(2)} units)"
    for sufijo, traducido in SUFIJOS.items():
        if valor.endswith(sufijo):
            return f"{_cadena(valor[: -len(sufijo)].rstrip())} {traducido}"
    if _esta_en_castellano(valor):
        SIN_TRADUCIR.add(valor)
    return valor


#: Frases que el seeder **añade al final** de un texto que ya existía, en vez
#: de componerlo con el separador. Se tratan aparte para que la tabla no tenga
#: que guardar la frase larga otra vez con la coletilla pegada.
SUFIJOS: dict[str, str] = {
    "Revisado en visita: se confirma el estado descrito.": (
        "Checked during the inspection: the condition described is confirmed."
    ),
}


#: Lo que ha pasado sin traducir. Lo vacía y lo lee `sembrar_demo.py`.
SIN_TRADUCIR: set[str] = set()


#: Palabras que no aparecen en una frase inglesa. Bastan para distinguir lo que
#: falta por traducir de lo que ya está traducido.
PALABRAS_CASTELLANAS = (
    " de ",
    " del ",
    " la ",
    " el ",
    " las ",
    " los ",
    " con ",
    " que ",
    " para ",
    " por ",
    " una ",
    " un ",
    " se ",
    " sin ",
    " y ",
    " en ",
)


def _esta_en_castellano(valor: str) -> bool:
    """¿Falta por traducir, o es un texto que ya volvió traducido de la API?

    `[REQ]` Esta distinción es la que hace útil el informe de pendientes. El
    seeder **lee de la API y vuelve a enviar**: crea un descriptivo, lo
    recupera para completarlo y lo manda otra vez. En la segunda vuelta el
    texto llega ya en inglés, y una tabla castellano→inglés no lo encuentra.
    Sin esta comprobación el informe daba 38 pendientes que estaban todas
    traducidas, y una lista así no se lee: se ignora.

    `[LIM]` Es una heurística por palabras funcionales, no un detector de
    idioma. Se equivoca con una frase castellana muy corta sin artículos ni
    preposiciones, que saldría como traducida sin estarlo. Se acepta porque el
    coste de equivocarse es una frase en castellano en una demostración, y
    porque la alternativa —una dependencia de detección de idioma— es
    desproporcionada para un seeder.
    """
    if len(valor) < 8:
        return False
    if valor.replace("-", "").replace(":", "").replace("T", "").isdigit():
        return False  # fechas y horas
    try:
        _uuid.UUID(valor)
    except ValueError:
        pass
    else:
        return False
    minusculas = f" {valor.lower()} "
    return any(p in minusculas for p in PALABRAS_CASTELLANAS)

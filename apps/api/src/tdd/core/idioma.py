"""El idioma de la petición, para el texto que escribe la API.

`[REQ]` Hay **tres** capas de texto en esta aplicación y conviene no
confundirlas, porque cada una se traduce en otro sitio:

1. **Los rótulos de la pantalla** —«Guardar», «Zona afectada»—, que están en el
   código del frontend y traduce `i18n/textos.ts`.
2. **Los nombres de catálogo** —«Cubierta», «Protección Pasiva Incendios»—, que
   están en la base y traduce la función de SQL `nombre(name_es, name_en)` con
   el inglés del propio cliente (migraciones 0029 y 0030).
3. **Las frases que escribe la API**, que es esto. No son rótulos ni datos: las
   compone el servidor a partir del estado del proyecto —«3 de 12 resueltas»,
   «sin generar»— y llegan ya escritas al navegador, que no puede traducirlas
   porque no sabe cómo se han compuesto.

La tercera se descubrió **mirando el prototipo en inglés**: la ficha del
proyecto enseñaba las cinco fases con su avance en castellano, en medio de una
pantalla por lo demás inglesa.

## Cómo viaja el idioma hasta aquí

Por un `ContextVar`, que fija el **middleware ASGI** de `core/observabilidad.py`
y por tanto no se puede olvidar en una ruta. Un `ContextVar` y no un argumento
porque estas frases se componen **cinco capas por debajo** de la ruta
—`phases/engine.describir_avance()` no sabe que existe una petición HTTP—, y
pasar el idioma por toda esa cadena serían veinte firmas cambiadas para que una
función de hoja escriba una palabra.

`[REQ]` En el middleware y **no en una dependencia** de FastAPI. La primera
versión lo fijaba en `core/deps.obtener_sesion`, que es un generador síncrono:
FastAPI lo ejecuta en un hilo del pool, con **su propio** contexto, así que el
valor no llegaba al endpoint. La API devolvía castellano con
`Accept-Language: en` y no fallaba nada.

`[LIM]` Un `ContextVar` es estado implícito, con lo que eso implica: una
función que lo lea fuera de una petición —el worker de la cola, una prueba
unitaria— obtiene el castellano. Es el valor correcto por omisión, pero es un
valor por omisión y no un error, así que un sitio que debería traducir y no lo
hace no se queja. Lo que lo delata es mirar la pantalla.

`[PDV]` De las frases que escribe la API, aquí están **solo las del avance de
las fases**: las que se ven en la ficha del proyecto, que es la pantalla que
abre cualquiera. Quedan unas 490 cadenas más repartidas por 73 ficheros
—mensajes de error de validación, avisos del informe, resultados de
importación—, y están sin traducir. Es trabajo medido, no un olvido.
"""

from __future__ import annotations

import csv
from contextvars import ContextVar, Token
from pathlib import Path

#: Los idiomas que la aplicación sabe servir. Igual que en `core/db`.
IDIOMAS = frozenset({"es", "en"})

#: El idioma de la petición en curso. Castellano por omisión, que es el idioma
#: del producto y el valor correcto cuando no hay petición.
_idioma: ContextVar[str] = ContextVar("idioma", default="es")


def fijar(idioma: str) -> None:
    """Fija el idioma de la petición en curso."""
    _idioma.set(idioma if idioma in IDIOMAS else "es")


def fijar_testigo(idioma: str) -> Token[str]:
    """Igual, devolviendo el testigo para deshacerlo.

    Lo usa el middleware, que **restaura** al terminar la petición: sin eso, el
    valor se queda en el contexto de la tarea y una petición que no mande
    cabecera heredaría el idioma de la anterior. Es la misma razón por la que
    el contexto de la base de datos usa `SET LOCAL`.
    """
    return _idioma.set(idioma if idioma in IDIOMAS else "es")


def restaurar(testigo: Token[str]) -> None:
    _idioma.reset(testigo)


def de_cabecera(cabecera: str) -> str:
    """El idioma que pide una cabecera `Accept-Language`.

    `[LIM]` Mira **el primero** de la lista y nada más: no interpreta los pesos
    (`q=`) ni ordena, porque quien manda esta cabecera es el frontend de esta
    aplicación con un valor que él mismo fija. Si algún día la consume un
    tercero, hay que ordenar por `q`.

    Reconoce la **etiqueta**, no el prefijo: `en` y `en-GB` son inglés, pero
    `english` y `enm` —inglés medio— no. La primera versión usaba
    `startswith('en')` y los daba por inglés; lo cazó una prueba de cabeceras
    raras.
    """
    primero = cabecera.split(",")[0].strip().lower()
    return "en" if primero.split("-")[0] == "en" else "es"


def actual() -> str:
    return _idioma.get()


#: Dónde vive la tabla. En un fichero de datos y no incrustada en este módulo,
#: por el mismo criterio que `data/catalogos/traducciones_en.csv` y
#: `data/demo/textos_en.csv`:
#:
#: * Son frases largas, y como literales de Python el formateador y el límite
#:   de 100 columnas las parten por donde le conviene. Revisar una traducción
#:   obligaría a leer código.
#: * Quien las tiene que revisar sabe de edificios, no de Python.
#:
#: Castellano → inglés, igual que en el frontend: la clave **es** el texto
#: original, así que una frase sin traducir sale en castellano y se lee como lo
#: que es, en vez de como un identificador crudo.
RELATIVA = Path("data") / "api" / "textos_en.csv"


def _csv() -> Path:
    """Sube buscando el CSV en vez de contar niveles de directorio.

    `[REQ]` Contar falla. En la migración 0029 se puso `parents[5]`, luego
    `parents[6]`, y las dos estaban mal; aquí se puso `parents[4]` y también.
    El síntoma es siempre el mismo y es el peor: el fichero no se encuentra, la
    tabla queda vacía y **todo sale en castellano sin un solo error**.
    """
    for carpeta in Path(__file__).resolve().parents:
        if (candidato := carpeta / RELATIVA).exists():
            return candidato
    return Path(__file__).resolve().parents[-1] / RELATIVA


CSV = _csv()


def _cargar() -> dict[str, str]:
    """`[LIM]` Si falta el CSV **no falla**: devuelve una tabla vacía y todo
    sale en castellano, que es el idioma del producto y un fallo visible. Una
    instalación a la que le falte un fichero de datos tiene que poder
    arrancar; lo que no puede es dar por traducido lo que no está.
    """
    if not CSV.exists():
        return {}
    with CSV.open(encoding="utf-8", newline="") as fh:
        return {f["es"]: f["en"] for f in csv.DictReader(fh)}


TEXTOS: dict[str, str] = _cargar()


def traducir_a(lengua: str, clave: str, **valores: object) -> str:
    """Igual que `traducir()`, con el idioma dicho a la cara.

    Lo usa el manejador de `HTTPException` de `main.py`, que corre en un sitio
    donde el `ContextVar` puede no estar fijado —un manejador de excepciones
    puede quedar por fuera del middleware— y donde la cabecera sí está.
    """
    texto = TEXTOS.get(clave, clave) if lengua == "en" else clave
    return texto.format(**valores) if valores else texto


def traducir(clave: str, **valores: object) -> str:
    """La frase en el idioma de la petición, con sus huecos rellenos.

    Los huecos se resuelven **después** de traducir, para que la frase inglesa
    pueda colocarlos en otro orden. Es la misma regla que en el frontend.

    Una clave que no esté en la tabla devuelve la clave: el castellano, que es
    el original. No se inventa una traducción.
    """
    texto = TEXTOS.get(clave, clave) if actual() == "en" else clave
    return texto.format(**valores) if valores else texto


def numero(valor: float, *, decimales: int = 0) -> str:
    """Un número con el separador de miles del idioma en curso.

    `[REQ]` Traducir la frase y dejar el número en inglés deja el aviso a medio
    camino: «se tomó a 1,200 m» en una pantalla castellana se lee como *mil
    doscientos* o como *uno coma dos* según quién lo mire, y las dos lecturas
    están a un factor de mil de distancia. `f"{x:,.0f}"` es la convención
    inglesa y Python no tiene otra sin `locale`, que es estado global del
    proceso y no se puede fijar por petición.

    Es el mismo criterio que `reporting/capex_layout.formatear_importe`, que ya
    lo hacía para los importes del informe; aquí el idioma sale del contexto de
    la petición en vez de un argumento.
    """
    crudo = f"{valor:,.{decimales}f}"
    if actual() == "en":
        return crudo
    entero, _, dec = crudo.partition(".")
    entero = entero.replace(",", ".")
    return f"{entero},{dec}" if dec else entero

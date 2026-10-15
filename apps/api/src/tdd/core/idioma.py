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

Por un `ContextVar`, que lo fija la misma dependencia que abre la sesión
(`core/deps.obtener_sesion`) y por tanto no se puede olvidar en una ruta. Un
`ContextVar` y no un argumento porque estas frases se componen **cinco capas
por debajo** de la ruta —`phases/engine.describir_avance()` no sabe que existe
una petición HTTP—, y pasar el idioma por toda esa cadena serían veinte firmas
cambiadas para que una función de hoja escriba una palabra.

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

from contextvars import ContextVar, Token

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


#: Castellano → inglés, igual que en el frontend: la clave **es** el texto
#: original, así que una frase sin traducir sale en castellano y se lee como lo
#: que es, en vez de como un identificador crudo.
TEXTOS: dict[str, str] = {
    # ── El avance de cada fase, en la ficha del proyecto ──────────────────
    "{resueltos} de {solicitados} resueltas": "{resueltos} of {solicitados} resolved",
    "enlace activo": "link active",
    "sin enlace": "no link",
    "{hechas} de {activos} activos visitados": "{hechas} of {activos} assets inspected",
    "{cerradas} de {rondas} rondas cerradas": "{cerradas} of {rondas} rounds closed",
    "{lineas} líneas": "{lineas} lines",
    " · {cuantas} sin precio validado": " · {cuantas} with an unvalidated price",
    "{cuantas} versión(es) emitida(s)": "{cuantas} version(s) issued",
    "{cuantas} versión(es) en borrador": "{cuantas} draft version(s)",
    "sin generar": "not generated",
    "{cuantos} evento(s)": "{cuantos} event(s)",
    # ── La fila de los hallazgos que nadie clasificó ──────────────────────
    #
    # Sale en la matriz de riesgo y en el reparto por grado. Es una frase del
    # servidor y no un catálogo: no hay fila de `risk_level` que traducir,
    # porque justo lo que dice es que no hay grado.
    "Sin clasificar": "Unclassified",
}


def traducir(clave: str, **valores: object) -> str:
    """La frase en el idioma de la petición, con sus huecos rellenos.

    Los huecos se resuelven **después** de traducir, para que la frase inglesa
    pueda colocarlos en otro orden. Es la misma regla que en el frontend.

    Una clave que no esté en la tabla devuelve la clave: el castellano, que es
    el original. No se inventa una traducción.
    """
    texto = TEXTOS.get(clave, clave) if actual() == "en" else clave
    return texto.format(**valores) if valores else texto

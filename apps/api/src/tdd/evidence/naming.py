"""Nombres de fichero configurables `[REQ]` §15.4 · **función pura**.

Renombrar **nunca toca el original**: produce un nombre para un derivado o para
la descarga. El objeto original conserva su `storage_key` y su hash, y hay un
disparador en la base de datos que lo impide aunque el código se equivoque.

Las reglas de saneado parecen menores hasta que alguien sube 400 fotos desde un
móvil y la mitad se llaman `IMG_20260715_114233.HEIC`. Entonces son lo único que
hace navegable el repositorio.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

#: Marcador → clave del contexto. `[REQ]` §15.4.
TOKENS: dict[str, str] = {
    "[Proyecto]": "proyecto",
    "[ProyectoNombre]": "proyecto_nombre",
    "[Activo]": "activo",
    "[Sistema]": "sistema",
    "[Zona]": "zona",
    "[Espacio]": "espacio",
    "[Capitulo]": "capitulo",
    "[Categoria]": "categoria",
    "[Fecha]": "fecha",
    "[Hora]": "hora",
    "[Numero]": "numero",
    "[Autor]": "autor",
    "[Etiqueta]": "etiqueta",
}

#: Tokens que, si faltan, llevan un valor de reemplazo en vez de omitirse.
RELLENO_SI_FALTA = {"activo": "SinActivo", "sistema": "SinSistema", "categoria": "Otros"}

PLANTILLA_POR_DEFECTO = "[Proyecto]_[Activo]_[Sistema]_[Zona]_[Numero]"

LONGITUD_MAXIMA = 200

#: Windows los rechaza incluso con extensión. Un ZIP con un fichero `CON.jpg`
#: no se puede descomprimir allí, y el usuario no sabría por qué.
RESERVADOS_WINDOWS = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

_PROHIBIDOS = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
_SEPARADORES_REPETIDOS = re.compile(r"_{2,}")


def sanear(valor: str) -> str:
    """Transcribe a ASCII, quita lo prohibido y colapsa espacios.

    `Cubierta Nº1` → `CubiertaN1` · `Añadido` → `Anadido`
    """
    if not valor:
        return ""
    # NFD separa la tilde de la letra; descartar los diacríticos deja el ASCII.
    # Se usa NFD y no NFKD a propósito: NFKD convertiría `Nº` en `No` y el
    # ejemplo documentado (`Cubierta Nº1` → `CubiertaN1`) dejaría de cumplirse.
    # Los símbolos que no son letras se pierden, que en un nombre de fichero es
    # justo lo que se quiere.
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", valor) if not unicodedata.combining(c)
    )
    sin_prohibidos = _PROHIBIDOS.sub("-", sin_tildes)
    # Los espacios desaparecen DENTRO del token: el `_` separa campos, no
    # palabras. Si no, «Sala de máquinas» produciría tres campos falsos.
    sin_espacios = re.sub(r"\s+", "", sin_prohibidos)
    return sin_espacios.encode("ascii", "ignore").decode("ascii")


@dataclass(frozen=True, slots=True)
class NombreGenerado:
    nombre: str
    extension: str
    #: Tokens de la plantilla que no tenían valor y se omitieron.
    omitidos: tuple[str, ...]

    @property
    def completo(self) -> str:
        return f"{self.nombre}{self.extension}"


def _recortar(nombre: str, sufijo_numerico: str) -> str:
    """Recorta preservando **siempre** el sufijo numérico `[REQ]` regla 6.

    Perder el correlativo al recortar produciría colisiones justo en los
    nombres más largos, que son los que más se parecen entre sí.
    """
    if len(nombre) <= LONGITUD_MAXIMA:
        return nombre
    if not sufijo_numerico:
        return nombre[:LONGITUD_MAXIMA].rstrip("_")
    cabeza = nombre[: LONGITUD_MAXIMA - len(sufijo_numerico) - 1].rstrip("_")
    return f"{cabeza}_{sufijo_numerico}"


def generar_nombre(
    contexto: dict[str, str | None],
    *,
    plantilla: str = PLANTILLA_POR_DEFECTO,
    extension: str = ".jpg",
) -> NombreGenerado:
    """Aplica la plantilla al contexto y devuelve el nombre saneado.

    `[REQ]` La **extensión no forma parte de la plantilla** ni del nombre
    editable: se arrastra del original, intacta. Cambiarla convertiría un
    renombrado en una conversión de formato que nadie ha pedido.
    """
    partes: list[str] = []
    omitidos: list[str] = []

    # Se recorre la plantilla marcador a marcador para conservar el orden y
    # poder omitir un token **junto con su separador** (regla 5).
    for trozo in re.split(r"(\[[A-Za-z]+\])", plantilla):
        if not trozo:
            continue
        if trozo in TOKENS:
            clave = TOKENS[trozo]
            valor = sanear(contexto.get(clave) or "")
            if not valor:
                valor = RELLENO_SI_FALTA.get(clave, "")
            if valor:
                partes.append(valor)
            else:
                omitidos.append(trozo)
        elif trozo.strip("_"):
            partes.append(sanear(trozo))

    nombre = _SEPARADORES_REPETIDOS.sub("_", "_".join(p for p in partes if p)).strip("_")
    nombre = _recortar(nombre, sanear(contexto.get("numero") or ""))

    if nombre.upper() in RESERVADOS_WINDOWS:
        nombre = f"_{nombre}"
    if not nombre:
        nombre = "SinNombre"

    ext = extension if extension.startswith(".") else f".{extension}"
    return NombreGenerado(nombre=nombre, extension=ext, omitidos=tuple(omitidos))


def sufijo_alfabetico(orden: int) -> str:
    """`b`, `c`, … `z`, `aa`, `ab`… para el segundo, tercero, … repetido.

    Base 26 biyectiva: no hay dígito cero, así que después de `z` viene `aa` y
    no `ba`. Con 27 fotos idénticas —que las hay, cuando alguien dispara en
    ráfaga— el sufijo sigue siendo único.
    """
    if orden < 2:
        return ""
    # El primero no lleva sufijo, así que el segundo empieza en «b»: el orden
    # coincide con la letra sin necesidad de desplazarlo.
    n = orden
    letras = ""
    while n > 0:
        n, resto = divmod(n - 1, 26)
        letras = chr(ord("a") + resto) + letras
    return letras


def resolver_colisiones(nombres: list[str]) -> list[str]:
    """Añade un sufijo `_b`, `_c`… a los nombres repetidos, en orden estable.

    `[REC]` §15.4 · El sufijo es **alfabético a propósito**, para no confundirlo
    con el correlativo:

        2026-014_NaveA_CLIMA_Cubierta_004
        2026-014_NaveA_CLIMA_Cubierta_004_b

    `[REC]` No se renumera el correlativo: el número es estable por diseño y
    cambiarlo aquí rompería la correspondencia con lo ya entregado al cliente.
    """
    vistos: dict[str, int] = {}
    ocupados: set[str] = set()
    salida: list[str] = []
    for nombre in nombres:
        raiz, punto, ext = nombre.rpartition(".")
        base = raiz if punto else nombre
        clave = nombre.lower()
        orden = vistos.get(clave, 0) + 1
        # Se avanza hasta encontrar un hueco libre: si en el lote ya había un
        # `foto_b`, el `foto` repetido no puede convertirse en otro `foto_b`.
        while True:
            sufijo = sufijo_alfabetico(orden)
            candidato_base = f"{base}_{sufijo}" if sufijo else base
            candidato = f"{candidato_base}.{ext}" if punto else candidato_base
            if candidato.lower() not in ocupados:
                break
            orden += 1
        vistos[clave] = orden
        ocupados.add(candidato.lower())
        salida.append(candidato)
    return salida


def numero_correlativo(indice: int, *, digitos: int = 3) -> str:
    return str(indice).zfill(digitos)

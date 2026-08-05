"""Almacenamiento de binarios · **puerto y adaptador de desarrollo**.

`[LIM]` **El adaptador de producción (S3 con Object Lock) NO está implementado
ni probado.** Lo que hay aquí es un adaptador sobre disco que sirve para la
suite y para levantar la aplicación en local. La barrera 4 del bloque de
fotografías —versionado y WORM sobre el prefijo `originals/`— es una propiedad
del bucket, no de este código, y no se puede afirmar que funcione hasta
probarla contra un bucket real.

Lo que sí es definitivo es la **forma de las claves** y el contrato del puerto:
el resto de la aplicación depende solo de `AlmacenDeObjetos`, así que sustituir
el adaptador no toca ni el servicio ni la API.

    {org}/{proyecto}/originals/{photo_id}.{ext}      ← inmutable
    {org}/{proyecto}/derivatives/{photo_id}/thumb-320.jpg
    {org}/{proyecto}/derivatives/{photo_id}/preview-1600.jpg

El identificador del objeto es un **UUID**, nunca el nombre que puso el
usuario: así renombrar no mueve bytes y un nombre con caracteres raros no puede
convertirse en una ruta con caracteres raros.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

#: Nombre de fichero de cada derivado dentro de su carpeta.
NOMBRE_DE_DERIVADO = {
    "MINIATURA_320": "thumb-320.jpg",
    "VISTA_1600": "preview-1600.jpg",
    "WEB": "web.jpg",
    "ANOTADA_RASTER": "annotated.jpg",
}

#: Lado máximo en píxeles de cada derivado.
LADO_DE_DERIVADO = {"MINIATURA_320": 320, "VISTA_1600": 1600, "WEB": 1200}


class ObjetoNoEncontrado(KeyError):
    """La clave no existe en el almacén."""


class OriginalInmutable(PermissionError):
    """`[REQ]` Se intentó sobrescribir un objeto bajo `originals/`.

    Es la barrera 4 llevada al puerto: aunque el bucket todavía no tenga Object
    Lock, el código no ofrece ninguna forma de sobrescribir un original.
    """


def clave_de_original(
    organization_id: uuid.UUID, project_id: uuid.UUID, photo_id: uuid.UUID, extension: str
) -> str:
    ext = extension.lstrip(".").lower()
    return f"{organization_id}/{project_id}/originals/{photo_id}.{ext}"


def clave_de_derivado(
    organization_id: uuid.UUID, project_id: uuid.UUID, photo_id: uuid.UUID, clase: str
) -> str:
    nombre = NOMBRE_DE_DERIVADO[clase]
    return f"{organization_id}/{project_id}/derivatives/{photo_id}/{nombre}"


def es_original(clave: str) -> bool:
    return "/originals/" in clave


class AlmacenDeObjetos(Protocol):
    """El contrato. Nótese que **no existe una operación de sobrescritura**."""

    def guardar(self, clave: str, datos: bytes) -> None: ...
    def leer(self, clave: str) -> bytes: ...
    def existe(self, clave: str) -> bool: ...
    def borrar(self, clave: str) -> None: ...


class AlmacenEnDisco:
    """Adaptador de desarrollo y pruebas. `[LIM]` No apto para producción.

    Le faltan, como mínimo: URLs firmadas, versionado, Object Lock, cifrado en
    reposo y ciclo de vida. No se afirma que ninguna de esas cosas funcione.
    """

    def __init__(self, raiz: Path) -> None:
        self.raiz = Path(raiz)
        self.raiz.mkdir(parents=True, exist_ok=True)

    def _ruta(self, clave: str) -> Path:
        # Sin esto, una clave con `..` escribiría fuera de la raíz. Las claves
        # las genera el servidor, pero la comprobación no cuesta nada y el día
        # que alguien acepte una clave de fuera sigue en pie.
        destino = (self.raiz / clave).resolve()
        if not destino.is_relative_to(self.raiz.resolve()):
            raise ValueError("Clave de almacenamiento fuera de la raíz")
        return destino

    def guardar(self, clave: str, datos: bytes) -> None:
        ruta = self._ruta(clave)
        if es_original(clave) and ruta.exists():
            raise OriginalInmutable(f"El original {clave} ya existe y no se sobrescribe")
        ruta.parent.mkdir(parents=True, exist_ok=True)
        # Escritura atómica: un fallo a mitad no deja un original truncado que
        # parecería válido y no coincidiría con su hash.
        temporal = ruta.with_suffix(ruta.suffix + ".parcial")
        temporal.write_bytes(datos)
        temporal.replace(ruta)

    def leer(self, clave: str) -> bytes:
        ruta = self._ruta(clave)
        if not ruta.exists():
            raise ObjetoNoEncontrado(clave)
        return ruta.read_bytes()

    def existe(self, clave: str) -> bool:
        return self._ruta(clave).exists()

    def borrar(self, clave: str) -> None:
        if es_original(clave):
            raise OriginalInmutable(f"Un original no se borra desde el almacén ({clave})")
        ruta = self._ruta(clave)
        if ruta.exists():
            ruta.unlink()


class AlmacenEnMemoria:
    """Para pruebas que no deben tocar el disco."""

    def __init__(self) -> None:
        self._objetos: dict[str, bytes] = {}

    def guardar(self, clave: str, datos: bytes) -> None:
        if es_original(clave) and clave in self._objetos:
            raise OriginalInmutable(f"El original {clave} ya existe y no se sobrescribe")
        self._objetos[clave] = datos

    def leer(self, clave: str) -> bytes:
        if clave not in self._objetos:
            raise ObjetoNoEncontrado(clave)
        return self._objetos[clave]

    def existe(self, clave: str) -> bool:
        return clave in self._objetos

    def borrar(self, clave: str) -> None:
        if es_original(clave):
            raise OriginalInmutable(f"Un original no se borra desde el almacén ({clave})")
        self._objetos.pop(clave, None)

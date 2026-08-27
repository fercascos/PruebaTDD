"""Lectura de imágenes: hash, EXIF, GPS y orientación.

Todo lo de este módulo opera **sobre bytes en memoria y devuelve datos**. No
escribe nada, no toca el almacenamiento y no modifica el original: es lo que
permite probarlo sin montar infraestructura.

Las tres fuentes de foto que la aplicación admite —ordenador, carrete del móvil
y cámara en directo— llegan aquí igual, pero traen problemas distintos:

| Origen | Lo que trae | Lo que hay que resolver |
|---|---|---|
| Ordenador | JPEG/PNG ya organizados | Volumen y duplicados |
| Carrete del móvil | **HEIC**, ficheros grandes, GPS | Formato que Windows no abre |
| Cámara en directo | JPEG con **orientación EXIF** | Fotos que salen giradas |
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from datetime import datetime
from fractions import Fraction
from typing import Any

from PIL import Image, ImageOps
from PIL.ExifTags import GPSTAGS, TAGS

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    #: Pillow **no abre HEIC por sí solo**. Sin este complemento, la subida
    #: desde el carrete de un iPhone falla con «no es una imagen legible», que
    #: es un mensaje engañoso: la imagen es correcta, lo que falta es el códec.
    HEIC_DISPONIBLE = True
except ImportError:  # pragma: no cover — depende del entorno, no del código
    HEIC_DISPONIBLE = False

#: Formatos que se aceptan al subir. HEIC entra porque es lo que produce un
#: iPhone por defecto, y rechazarlo obligaría al consultor a convertir 400
#: fotos a mano.
FORMATOS_ACEPTADOS = frozenset({"JPEG", "PNG", "HEIF", "WEBP", "TIFF"})

MIME_POR_FORMATO = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "HEIF": "image/heic",
    "WEBP": "image/webp",
    "TIFF": "image/tiff",
}

#: `[REQ]` La extensión se deriva del **formato real**, no del nombre que traía
#: el fichero: alguien renombra `foto.png` a `foto.jpg` y a partir de ahí todo
#: el que se fíe del nombre se equivoca.
EXTENSION_POR_FORMATO = {
    "JPEG": "jpg",
    "PNG": "png",
    "HEIF": "heic",
    "WEBP": "webp",
    "TIFF": "tif",
}


class ImagenNoValida(ValueError):
    """El fichero no es una imagen o su formato no se acepta."""


@dataclass(frozen=True, slots=True)
class Coordenadas:
    latitud: float
    longitud: float

    def __str__(self) -> str:
        return f"{self.latitud:.6f}, {self.longitud:.6f}"


@dataclass(frozen=True, slots=True)
class MetadatosDeImagen:
    sha256: str
    phash: str
    byte_size: int
    formato: str
    mime_type: str
    ancho: int
    alto: int
    taken_at: datetime | None
    coordenadas: Coordenadas | None
    orientacion: int | None
    camara: str | None
    fabricante: str | None = None
    #: EXIF completo reducido a tipos que aguantan un `json.dumps`. Se guarda
    #: entero porque lo útil de mañana no se sabe hoy, y el original ya no
    #: estará abierto para volver a mirarlo.
    exif_legible: dict[str, str] = field(default_factory=dict)

    @property
    def es_apaisada(self) -> bool:
        return self.ancho >= self.alto

    @property
    def extension(self) -> str:
        return EXTENSION_POR_FORMATO.get(self.formato, "bin")


def sha256_de(datos: bytes) -> str:
    """Huella exacta. Dos ficheros con el mismo `sha256` son el mismo fichero."""
    return hashlib.sha256(datos).hexdigest()


def phash_de(imagen: Image.Image, *, lado: int = 8) -> str:
    """Huella **perceptual**: detecta la misma foto reescalada o recomprimida.

    `[REC]` Hace falta porque el duplicado real en campo no es byte a byte: es
    la misma foto subida desde el móvil y otra vez desde el ordenador, que pasa
    por una recompresión y cambia de `sha256`. Con hash exacto no se detectaría.

    Implementación: media de luminancia sobre una miniatura. Es el método
    clásico —sencillo y suficiente— y no depende de bibliotecas extra.
    """
    reducida = imagen.convert("L").resize((lado, lado), Image.Resampling.LANCZOS)
    # En modo «L» cada píxel es un byte, así que `tobytes()` da la lista de
    # luminancias directamente y sin pasar por la API de acceso píxel a píxel.
    pixeles = reducida.tobytes()
    media = sum(pixeles) / len(pixeles)
    bits = "".join("1" if p >= media else "0" for p in pixeles)
    return f"{int(bits, 2):0{lado * lado // 4}x}"


def distancia_hamming(a: str, b: str) -> int:
    """Cuántos bits difieren entre dos `phash`. 0 = idénticas."""
    if len(a) != len(b):
        raise ValueError("Los hashes perceptuales deben tener la misma longitud")
    return bin(int(a, 16) ^ int(b, 16)).count("1")


#: Por debajo de este umbral se consideran la misma foto. Elegido conservador:
#: preferimos avisar de más que fusionar dos fotos distintas en silencio.
UMBRAL_DUPLICADO_PERCEPTUAL = 5


def _a_grados(valor: object, referencia: str | None) -> float | None:
    """Convierte los grados/minutos/segundos del EXIF en grados decimales."""
    try:
        grados, minutos, segundos = (
            float(Fraction(str(v)))
            for v in valor  # type: ignore[attr-defined]  # el EXIF trae lo que trae
        )
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    decimal = grados + minutos / 60 + segundos / 3600
    if referencia in ("S", "W"):
        decimal = -decimal
    return decimal


def _leer_gps(exif: dict[str | int, Any]) -> Coordenadas | None:
    bruto = exif.get("GPSInfo")
    if not bruto:
        return None
    gps = {GPSTAGS.get(k, k): v for k, v in bruto.items()}
    lat = _a_grados(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
    lon = _a_grados(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
    if lat is None or lon is None:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return Coordenadas(latitud=lat, longitud=lon)


def _leer_fecha(exif: dict[str | int, Any]) -> datetime | None:
    for clave in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
        valor = exif.get(clave)
        if not valor:
            continue
        try:
            return datetime.strptime(str(valor), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
    return None


#: No se guardan en `exif_raw`: son los que la exportación para el cliente
#: elimina, y conservarlos en la base multiplicaría los sitios donde vigilarlos.
_EXIF_QUE_NO_SE_GUARDA = frozenset({"MakerNote", "UserComment", "PrintImageMatching", "GPSInfo"})


def _exif_legible(exif: dict[str | int, Any]) -> dict[str, str]:
    """Aplana el EXIF a texto para que quepa en un JSONB sin sorpresas.

    Los valores del EXIF son racionales, bytes y tuplas anidadas; serializarlos
    tal cual falla en el momento menos oportuno, que es al guardar la foto.
    """
    salida: dict[str, str] = {}
    for clave, valor in exif.items():
        nombre = str(clave)
        if nombre in _EXIF_QUE_NO_SE_GUARDA or nombre.isdigit():
            continue
        if isinstance(valor, bytes):
            continue
        texto = str(valor).strip().replace("\x00", "")
        if texto:
            salida[nombre] = texto[:300]
    return salida


def leer(datos: bytes) -> MetadatosDeImagen:
    """Extrae todo lo que hace falta para dar de alta una fotografía.

    No modifica los bytes recibidos: el original se guarda **tal cual llegó**.
    """
    if not datos:
        raise ImagenNoValida("El fichero está vacío")
    try:
        imagen = Image.open(io.BytesIO(datos))
        imagen.load()
    except Exception as exc:  # noqa: BLE001 — cualquier fallo aquí es «no es imagen»
        raise ImagenNoValida("El fichero no es una imagen legible") from exc

    formato = (imagen.format or "").upper()
    if formato not in FORMATOS_ACEPTADOS:
        raise ImagenNoValida(
            f"Formato «{formato or 'desconocido'}» no admitido. "
            f"Se aceptan: {', '.join(sorted(FORMATOS_ACEPTADOS))}"
        )

    exif_bruto = {}
    try:
        crudo = imagen.getexif()
        exif_bruto = {TAGS.get(k, k): v for k, v in crudo.items()}
        # `getexif()` devuelve SOLO la IFD0. `DateTimeOriginal` —la fecha en que
        # se disparó la foto, que es la única que interesa aquí— vive en la
        # sub-IFD Exif. Sin este paso, toda foto de móvil llegaría sin fecha.
        exif_ifd = crudo.get_ifd(0x8769)
        exif_bruto.update({TAGS.get(k, k): v for k, v in exif_ifd.items()})
        gps_ifd = crudo.get_ifd(0x8825)
        if gps_ifd:
            exif_bruto["GPSInfo"] = gps_ifd
    except Exception:  # noqa: BLE001 — un EXIF corrupto no impide subir la foto
        exif_bruto = {}

    return MetadatosDeImagen(
        sha256=sha256_de(datos),
        phash=phash_de(imagen),
        byte_size=len(datos),
        formato=formato,
        mime_type=MIME_POR_FORMATO.get(formato, "application/octet-stream"),
        ancho=imagen.width,
        alto=imagen.height,
        taken_at=_leer_fecha(exif_bruto),
        coordenadas=_leer_gps(exif_bruto),
        orientacion=_entero_o_nada(exif_bruto.get("Orientation")),
        camara=(str(exif_bruto.get("Model") or "")).strip() or None,
        fabricante=(str(exif_bruto.get("Make") or "")).strip() or None,
        exif_legible=_exif_legible(exif_bruto),
    )


def _entero_o_nada(valor: object) -> int | None:
    if not isinstance(valor, (int, float, str, bytes)):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def generar_derivado(
    datos: bytes, *, lado_maximo: int, calidad: int = 82, sin_metadatos: bool = False
) -> bytes:
    """Crea una miniatura o versión de trabajo. **El original no se toca.**

    `[REQ]` Aplica la orientación EXIF: una foto tomada con el móvil en vertical
    llega con los píxeles apaisados y una etiqueta que dice «gírala». Si no se
    aplica, la miniatura sale tumbada aunque la original se vea bien.
    """
    # El tipo es `Image`, no `ImageFile`: `open` da un `ImageFile` pero
    # `exif_transpose`, `convert` y `frombytes` devuelven `Image` a secas, y
    # anotarlo al revés hacía que cada una de esas asignaciones fuera un error.
    imagen: Image.Image = Image.open(io.BytesIO(datos))
    imagen = ImageOps.exif_transpose(imagen) or imagen
    imagen.thumbnail((lado_maximo, lado_maximo), Image.Resampling.LANCZOS)
    if imagen.mode not in ("RGB", "L"):
        imagen = imagen.convert("RGB")

    salida = io.BytesIO()
    # `exif=None` no basta: `save` arrastra el bloque original si existe. Se
    # construye una imagen limpia para que el derivado no lleve GPS.
    if sin_metadatos:
        imagen = Image.frombytes(imagen.mode, imagen.size, imagen.tobytes())
    imagen.save(salida, format="JPEG", quality=calidad, optimize=True)
    return salida.getvalue()


def tiene_metadatos_sensibles(datos: bytes) -> bool:
    """`[REQ]` Comprobación previa a exportar para el cliente."""
    try:
        m = leer(datos)
    except ImagenNoValida:
        return False
    return m.coordenadas is not None or m.camara is not None

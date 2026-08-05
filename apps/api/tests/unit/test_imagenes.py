"""Lectura de imágenes: hash, EXIF, GPS y orientación `[REQ]` §15.6.

Las imágenes se construyen aquí, con Pillow. `[REQ]` No se usa ni una sola
fotografía real del cliente, ni siquiera como fixture: el repositorio no debe
contener material del encargo.
"""

from __future__ import annotations

import io
from datetime import datetime

import piexif
import pytest
from PIL import Image

from tdd.evidence.images import (
    HEIC_DISPONIBLE,
    UMBRAL_DUPLICADO_PERCEPTUAL,
    Coordenadas,
    ImagenNoValida,
    distancia_hamming,
    generar_derivado,
    leer,
    phash_de,
    sha256_de,
    tiene_metadatos_sensibles,
)


def imagen(
    ancho: int = 640,
    alto: int = 480,
    color: tuple[int, int, int] = (120, 90, 60),
    formato: str = "JPEG",
) -> bytes:
    """Una imagen con degradado: un color plano daría un `phash` degenerado."""
    img = Image.new("RGB", (ancho, alto))
    pixeles = img.load()
    assert pixeles is not None
    for x in range(ancho):
        for y in range(alto):
            pixeles[x, y] = (
                (color[0] + x) % 256,
                (color[1] + y) % 256,
                (color[2] + x + y) % 256,
            )
    salida = io.BytesIO()
    img.save(salida, format=formato)
    return salida.getvalue()


def con_exif(
    datos: bytes,
    *,
    fecha: str | None = "2026:07:15 11:42:33",
    gps: tuple[float, float] | None = None,
    modelo: str | None = "Pixel Ficticio",
    orientacion: int | None = None,
) -> bytes:
    exif: dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    if fecha:
        exif["Exif"][piexif.ExifIFD.DateTimeOriginal] = fecha
    if modelo:
        exif["0th"][piexif.ImageIFD.Model] = modelo
        exif["0th"][piexif.ImageIFD.Make] = "Fabricante Ficticio"
    if orientacion:
        exif["0th"][piexif.ImageIFD.Orientation] = orientacion
    if gps:
        lat, lon = gps
        exif["GPS"] = {
            piexif.GPSIFD.GPSLatitudeRef: "N" if lat >= 0 else "S",
            piexif.GPSIFD.GPSLatitude: _grados(abs(lat)),
            piexif.GPSIFD.GPSLongitudeRef: "E" if lon >= 0 else "W",
            piexif.GPSIFD.GPSLongitude: _grados(abs(lon)),
        }
    salida = io.BytesIO()
    piexif.insert(piexif.dump(exif), datos, salida)
    return salida.getvalue()


def _grados(valor: float) -> tuple[tuple[int, int], ...]:
    grados = int(valor)
    minutos_f = (valor - grados) * 60
    minutos = int(minutos_f)
    segundos = round((minutos_f - minutos) * 60 * 100)
    return ((grados, 1), (minutos, 1), (segundos, 100))


# ── Hash exacto ──────────────────────────────────────────────────────────────


def test_el_mismo_fichero_da_el_mismo_sha256() -> None:
    datos = imagen()
    assert sha256_de(datos) == sha256_de(datos)
    assert len(sha256_de(datos)) == 64


def test_un_byte_distinto_cambia_el_sha256() -> None:
    assert sha256_de(b"a") != sha256_de(b"b")


# ── Hash perceptual ──────────────────────────────────────────────────────────


def test_la_misma_foto_recomprimida_conserva_el_hash_perceptual() -> None:
    """`[REC]` El duplicado real en campo no es byte a byte: es la misma foto
    subida desde el móvil y otra vez desde el ordenador, recomprimida por el
    camino. Con hash exacto no se detectaría."""
    original = imagen()
    recomprimida = generar_derivado(original, lado_maximo=400, calidad=60)

    a = leer(original)
    b = leer(recomprimida)

    assert a.sha256 != b.sha256, "la recompresión cambia el fichero"
    assert distancia_hamming(a.phash, b.phash) <= UMBRAL_DUPLICADO_PERCEPTUAL


def test_dos_fotos_distintas_no_se_confunden() -> None:
    a = leer(imagen(color=(10, 200, 30)))
    b = leer(imagen(color=(200, 10, 220), ancho=500, alto=700))
    assert distancia_hamming(a.phash, b.phash) > UMBRAL_DUPLICADO_PERCEPTUAL


def test_comparar_hashes_de_distinta_longitud_es_un_error() -> None:
    with pytest.raises(ValueError, match="misma longitud"):
        distancia_hamming("ff", "ffff")


def test_el_hash_perceptual_tiene_la_longitud_esperada() -> None:
    assert len(phash_de(Image.new("RGB", (64, 64)))) == 16


# ── EXIF ─────────────────────────────────────────────────────────────────────


def test_se_extrae_la_fecha_de_captura() -> None:
    meta = leer(con_exif(imagen()))
    assert meta.taken_at == datetime(2026, 7, 15, 11, 42, 33)


def test_se_extraen_las_coordenadas_en_grados_decimales() -> None:
    meta = leer(con_exif(imagen(), gps=(40.416775, -3.703790)))
    assert meta.coordenadas is not None
    assert meta.coordenadas.latitud == pytest.approx(40.416775, abs=1e-4)
    # El hemisferio occidental llega como referencia «W» y debe salir negativo.
    assert meta.coordenadas.longitud == pytest.approx(-3.703790, abs=1e-4)


def test_sin_exif_los_campos_quedan_vacios_y_no_se_inventa_nada() -> None:
    """`[REQ]` §15.6 · No se infiere la fecha del sistema de archivos ni la
    ubicación del activo. Un dato inventado en una evidencia técnica es peor
    que un dato ausente."""
    meta = leer(imagen())
    assert meta.taken_at is None
    assert meta.coordenadas is None
    assert meta.camara is None


def test_un_exif_corrupto_no_impide_dar_de_alta_la_foto() -> None:
    """La foto es la evidencia; el EXIF es un extra. Perder la foto por un
    bloque de metadatos roto sería el peor intercambio posible."""
    datos = bytearray(con_exif(imagen()))
    datos[30:120] = b"\xff" * 90
    meta = leer(bytes(datos))
    assert meta.byte_size > 0


def test_el_exif_se_guarda_en_texto_serializable() -> None:
    """Los valores del EXIF son racionales y bytes: guardarlos tal cual falla
    al serializar, y falla justo al guardar la foto."""
    import json

    meta = leer(con_exif(imagen()))
    json.dumps(meta.exif_legible)  # no debe lanzar
    assert meta.exif_legible["Model"] == "Pixel Ficticio"


def test_el_gps_no_se_guarda_en_el_exif_plano() -> None:
    """Se promociona a columnas indexadas; duplicarlo en el JSONB multiplicaría
    los sitios donde hay que acordarse de eliminarlo al exportar."""
    meta = leer(con_exif(imagen(), gps=(40.4, -3.7)))
    assert "GPSInfo" not in meta.exif_legible


# ── Formatos ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("formato", ["JPEG", "PNG", "WEBP"])
def test_se_aceptan_los_formatos_previstos(formato: str) -> None:
    meta = leer(imagen(formato=formato))
    assert meta.formato == formato
    assert meta.mime_type.startswith("image/")


def test_la_extension_se_deriva_del_formato_real_y_no_del_nombre() -> None:
    """Alguien renombra `foto.png` a `foto.jpg` y a partir de ahí todo el que
    se fíe del nombre se equivoca."""
    assert leer(imagen(formato="PNG")).extension == "png"


def test_el_heic_del_iphone_se_lee_y_se_convierte() -> None:
    """`[REQ]` El carrete de un iPhone produce HEIC por defecto. Rechazarlo
    obligaría al consultor a convertir 400 fotos a mano.

    Se comprueba de verdad, no de palabra: Pillow **no** abre HEIC por sí solo,
    hace falta `pillow-heif`. Si el complemento faltara en la imagen del worker,
    esta prueba fallaría en vez de descubrirse en una visita.
    """
    assert HEIC_DISPONIBLE, "falta pillow-heif: la subida desde el carrete no funcionaría"

    salida = io.BytesIO()
    with Image.open(io.BytesIO(imagen(400, 300))) as img:
        img.save(salida, format="HEIF")

    meta = leer(salida.getvalue())
    assert meta.formato == "HEIF"
    assert meta.mime_type == "image/heic"
    assert meta.extension == "heic"

    # Y el derivado sale en JPEG, que sí abre cualquiera.
    derivado = generar_derivado(salida.getvalue(), lado_maximo=200)
    assert leer(derivado).formato == "JPEG"


def test_un_fichero_que_no_es_imagen_se_rechaza() -> None:
    with pytest.raises(ImagenNoValida):
        leer(b"MZ\x90\x00 esto es un ejecutable")


def test_un_fichero_vacio_se_rechaza() -> None:
    with pytest.raises(ImagenNoValida, match="vacío"):
        leer(b"")


# ── Derivados ────────────────────────────────────────────────────────────────


def test_el_derivado_no_supera_el_lado_maximo() -> None:
    datos = generar_derivado(imagen(1600, 1200), lado_maximo=320)
    with Image.open(io.BytesIO(datos)) as img:
        assert max(img.size) <= 320


def test_el_derivado_se_genera_sin_tocar_el_original() -> None:
    """`[REQ]` La invariante del bloque. Se comprueba por hash, no de palabra."""
    original = imagen()
    antes = sha256_de(original)
    generar_derivado(original, lado_maximo=320)
    assert sha256_de(original) == antes


def test_el_derivado_aplica_la_orientacion_exif() -> None:
    """`[REQ]` Una foto tomada con el móvil en vertical llega con los píxeles
    apaisados y una etiqueta que dice «gírala». Sin aplicarla, la miniatura
    sale tumbada aunque la original se vea bien en el visor del teléfono."""
    apaisada = con_exif(imagen(800, 400), orientacion=6)  # 6 = girar 90°
    meta = leer(apaisada)
    assert meta.ancho > meta.alto, "los píxeles llegan apaisados"

    derivado = generar_derivado(apaisada, lado_maximo=400)
    with Image.open(io.BytesIO(derivado)) as img:
        assert img.height > img.width, "el derivado sale ya en vertical"


def test_el_derivado_para_el_cliente_no_lleva_gps() -> None:
    """`[REQ]` §15.6 · La exportación para el cliente elimina el GPS. Se
    comprueba releyendo el derivado, no confiando en el parámetro."""
    con_gps = con_exif(imagen(), gps=(40.416775, -3.703790))
    assert tiene_metadatos_sensibles(con_gps) is True

    limpio = generar_derivado(con_gps, lado_maximo=320, sin_metadatos=True)
    assert leer(limpio).coordenadas is None
    assert tiene_metadatos_sensibles(limpio) is False


def test_las_coordenadas_se_muestran_con_seis_decimales() -> None:
    assert str(Coordenadas(40.416775, -3.703790)) == "40.416775, -3.703790"

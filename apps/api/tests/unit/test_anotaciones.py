"""La capa de anotaciones `[REQ]` §15.2.

Lógica pura: ni base de datos ni HTTP. Lo que más importa aquí es lo que se
**rechaza**, porque la capa se guardaba admitiendo cualquier cosa y el
renderizador que la recibe solo tiene malas opciones ante un dato imposible:
adivinar, reventar, o dibujar algo que nadie pidió.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from tdd.evidence.anotaciones import (
    MAX_FORMAS,
    AnotacionInvalida,
    Capa,
    Forma,
    TipoDeForma,
    leer,
    rasterizar,
)


def capa(**extra):
    return {"shapes": [{"tipo": "FLECHA", "x1": 0.1, "y1": 0.1, "x2": 0.5, "y2": 0.5, **extra}]}


def foto(ancho: int = 400, alto: int = 300, color=(200, 200, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (ancho, alto), color).save(buf, format="JPEG")
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
#  Validación
# ─────────────────────────────────────────────────────────────────────────────


def test_una_capa_bien_formada_se_lee() -> None:
    leida = leer(capa(color="#1D4ED8", grosor=5))
    assert len(leida.formas) == 1
    forma = leida.formas[0]
    assert forma.tipo is TipoDeForma.FLECHA
    assert forma.color == "#1D4ED8"
    assert forma.grosor == 5


def test_las_coordenadas_van_en_fraccion_no_en_pixeles() -> None:
    """Es el fallo clásico de las anotaciones. Una flecha guardada en píxeles
    del original apunta al cielo en cuanto algo se redimensiona, y aquí todo se
    redimensiona: miniatura, vista y PPTX."""
    with pytest.raises(AnotacionInvalida) as exc:
        leer(capa(x2=1250))
    assert "píxeles" in str(exc.value)
    assert "x2" in str(exc.value)


def test_una_coordenada_negativa_tambien_se_rechaza() -> None:
    with pytest.raises(AnotacionInvalida):
        leer(capa(y1=-0.2))


def test_no_se_recorta_en_silencio() -> None:
    """Recortar a [0,1] dejaría una flecha señalando un sitio que nadie eligió,
    y eso en un informe entregado es peor que un error al guardar."""
    with pytest.raises(AnotacionInvalida):
        leer(capa(x1=1.4))


def test_un_tipo_desconocido_dice_cuales_hay() -> None:
    with pytest.raises(AnotacionInvalida) as exc:
        leer({"shapes": [{"tipo": "GARABATO", "x1": 0, "y1": 0}]})
    assert "FLECHA" in str(exc.value)
    assert "RECTANGULO" in str(exc.value)


def test_un_color_que_no_es_hexadecimal_se_rechaza() -> None:
    for malo in ("rojo", "#GGG", "#12345", "rgb(255,0,0)"):
        with pytest.raises(AnotacionInvalida):
            leer(capa(color=malo))


def test_el_color_se_normaliza_a_mayusculas() -> None:
    assert leer(capa(color="#dc2626")).formas[0].color == "#DC2626"


def test_una_anotacion_de_texto_vacia_se_rechaza() -> None:
    """Quien la mandó cree que ha anotado algo, y no hay nada que pintar."""
    with pytest.raises(AnotacionInvalida) as exc:
        leer({"shapes": [{"tipo": "TEXTO", "x1": 0.2, "y1": 0.2, "texto": "   "}]})
    assert "vacía" in str(exc.value)


def test_sin_lista_de_formas_no_es_una_capa() -> None:
    with pytest.raises(AnotacionInvalida):
        leer({"version": 1})
    with pytest.raises(AnotacionInvalida):
        leer("no soy un objeto")


def test_una_capa_vacia_es_valida() -> None:
    """Borrar todas las anotaciones es una operación legítima: deja la foto
    limpia sin tener que borrar la versión."""
    assert leer({"shapes": []}).formas == ()


def test_hay_un_tope_de_formas() -> None:
    """No es una regla de negocio: impide que un cliente mal escrito mande cien
    mil polígonos y el informe se quede colgado sin que nadie sepa por qué."""
    demasiadas = {"shapes": [{"tipo": "LINEA", "x1": 0, "y1": 0} for _ in range(MAX_FORMAS + 1)]}
    with pytest.raises(AnotacionInvalida) as exc:
        leer(demasiadas)
    assert str(MAX_FORMAS) in str(exc.value)


def test_el_grosor_se_acota_en_vez_de_rechazarse() -> None:
    """A diferencia de las coordenadas, un grosor absurdo no cambia dónde
    señala la anotación: se acota y se sigue."""
    assert leer(capa(grosor=900)).formas[0].grosor == 20.0
    assert leer(capa(grosor=0)).formas[0].grosor == 0.5


def test_el_texto_largo_se_corta_en_vez_de_rechazarse() -> None:
    leida = leer({"shapes": [{"tipo": "TEXTO", "x1": 0.1, "y1": 0.1, "texto": "x" * 500}]})
    assert len(leida.formas[0].texto) == 200


def test_ida_y_vuelta_por_json() -> None:
    """Lo que se guarda se vuelve a leer igual: si no, editar una anotación
    existente la deformaría un poco en cada pasada."""
    original = leer(capa(color="#059669", grosor=4))
    assert leer(original.como_json()) == original


# ─────────────────────────────────────────────────────────────────────────────
#  Rasterizado
# ─────────────────────────────────────────────────────────────────────────────


def _pixeles_distintos(antes: bytes, despues: bytes) -> int:
    with Image.open(io.BytesIO(antes)) as a, Image.open(io.BytesIO(despues)) as b:
        pa, pb = a.convert("RGB").tobytes(), b.convert("RGB").tobytes()
    return sum(1 for x, y in zip(pa, pb, strict=True) if x != y)


def test_rasterizar_pinta_algo_encima() -> None:
    limpia = foto()
    anotada = rasterizar(limpia, leer(capa()))
    assert _pixeles_distintos(limpia, anotada) > 0


def test_una_capa_vacia_no_cambia_la_imagen_visiblemente() -> None:
    limpia = foto()
    igual = rasterizar(limpia, Capa())
    with Image.open(io.BytesIO(limpia)) as a, Image.open(io.BytesIO(igual)) as b:
        assert a.size == b.size


def test_el_resultado_es_un_jpeg_valido() -> None:
    anotada = rasterizar(foto(), leer(capa()))
    with Image.open(io.BytesIO(anotada)) as img:
        assert img.format == "JPEG"


def test_el_original_no_se_toca() -> None:
    """`[REQ]` §15.2 · La garantía número uno del sistema. Lo que sale es un
    derivado desechable; el fichero de la cámara sigue byte a byte."""
    limpia = foto()
    copia = bytes(limpia)
    rasterizar(limpia, leer(capa()))
    assert limpia == copia


def test_un_rectangulo_dibujado_de_derecha_a_izquierda_se_pinta() -> None:
    """Arrastrar el ratón hacia atrás es lo normal, y Pillow exige la caja
    ordenada: sin ordenarla no pintaría nada y el usuario creería que la
    herramienta no funciona."""
    limpia = foto()
    al_reves = {"shapes": [{"tipo": "RECTANGULO", "x1": 0.8, "y1": 0.8, "x2": 0.2, "y2": 0.2}]}
    assert _pixeles_distintos(limpia, rasterizar(limpia, leer(al_reves))) > 0


def test_el_trazo_escala_con_el_tamano_de_la_imagen() -> None:
    """Un trazo fijo de 3 px no se ve sobre una foto de 4000 px de ancho, y tapa
    entera una miniatura de 320."""
    forma = leer(capa(grosor=3))
    pequena = _pixeles_distintos(foto(400, 300), rasterizar(foto(400, 300), forma))
    grande = _pixeles_distintos(foto(1600, 1200), rasterizar(foto(1600, 1200), forma))
    assert grande > pequena * 4, "el trazo no está escalando con la imagen"


def test_la_misma_capa_señala_lo_mismo_a_dos_tamanos() -> None:
    """Es la razón de que las coordenadas sean relativas: la flecha que apunta a
    la fisura tiene que apuntar a la fisura en la miniatura, en la vista y en el
    PPTX."""
    marca = {"shapes": [{"tipo": "RECTANGULO", "x1": 0.4, "y1": 0.4, "x2": 0.6, "y2": 0.6}]}
    leida = leer(marca)

    def centro_marcado(ancho: int, alto: int) -> bool:
        anotada = rasterizar(foto(ancho, alto), leida)
        with Image.open(io.BytesIO(anotada)) as img:
            recorte = img.convert("RGB").crop(
                (int(ancho * 0.38), int(alto * 0.38), int(ancho * 0.62), int(alto * 0.62))
            )
            # El rojo del trazo por defecto debe aparecer en esa franja.
            # `tobytes` y no `getdata()`: esta última está en retirada en Pillow.
            crudo = recorte.tobytes()
        return any(
            crudo[i] > 150 and crudo[i + 1] < 100  # noqa: PLR2004
            for i in range(0, len(crudo) - 2, 3)
        )

    assert centro_marcado(400, 300)
    assert centro_marcado(1600, 1200)


def test_todas_las_formas_pintan_algo() -> None:
    limpia = foto()
    for tipo in TipoDeForma:
        una = Capa(
            formas=(
                Forma(
                    tipo=tipo,
                    x1=0.2,
                    y1=0.2,
                    x2=0.7,
                    y2=0.7,
                    texto="Fisura" if tipo is TipoDeForma.TEXTO else "",
                ),
            )
        )
        assert _pixeles_distintos(limpia, rasterizar(limpia, una)) > 0, f"{tipo} no pinta nada"


def test_un_png_con_transparencia_se_convierte_sin_reventar() -> None:
    """Un PNG con canal alfa no se puede guardar como JPEG. Sin convertir, el
    informe fallaría justo con las capturas de pantalla que alguien adjunta."""
    buf = io.BytesIO()
    Image.new("RGBA", (200, 150), (100, 100, 100, 128)).save(buf, format="PNG")
    anotada = rasterizar(buf.getvalue(), leer(capa()))
    with Image.open(io.BytesIO(anotada)) as img:
        assert img.format == "JPEG"

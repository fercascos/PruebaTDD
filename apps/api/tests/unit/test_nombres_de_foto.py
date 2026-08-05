"""Sistema de nombres configurable `[REQ]` §15.4.

Las ocho reglas de saneado son el tipo de cosa que parece menor hasta que
alguien sube 400 fotos y la mitad se llaman `IMG_20260715_114233.HEIC`.
"""

from __future__ import annotations

import pytest

from tdd.evidence.naming import (
    LONGITUD_MAXIMA,
    PLANTILLA_POR_DEFECTO,
    generar_nombre,
    numero_correlativo,
    resolver_colisiones,
    sanear,
    sufijo_alfabetico,
)

CONTEXTO = {
    "proyecto": "2026-014",
    "activo": "Nave A",
    "sistema": "CLIMA",
    "zona": "Cubierta",
    "numero": "004",
}


# ── Regla 1 · transliteración ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Cubierta Nº1", "CubiertaN1"),
        ("Añadido", "Anadido"),
        ("Instalación eléctrica", "Instalacionelectrica"),
        ("Fachada Sur", "FachadaSur"),
    ],
)
def test_se_transcribe_a_ascii_sin_perder_letras(entrada: str, esperado: str) -> None:
    assert sanear(entrada) == esperado


# ── Regla 2 · caracteres prohibidos ──────────────────────────────────────────


def test_los_caracteres_prohibidos_no_llegan_al_nombre() -> None:
    """Un `/` en el nombre convertiría el fichero en una carpeta al descomprimir."""
    assert sanear('Zona/Sub:calle*?"<>|') == "Zona-Sub-calle------"


def test_los_caracteres_de_control_tampoco() -> None:
    assert sanear("Nave\x00A\x1f") == "Nave-A-"


# ── Regla 3 · espacios dentro del token ──────────────────────────────────────


def test_los_espacios_desaparecen_dentro_del_token() -> None:
    """El `_` separa CAMPOS. Si los espacios se convirtieran en `_`, «Sala de
    máquinas» produciría tres campos falsos y el nombre dejaría de ser legible
    por la plantilla."""
    generado = generar_nombre({**CONTEXTO, "zona": "Sala de máquinas"})
    assert "Salademaquinas" in generado.nombre
    assert generado.nombre.count("_") == 4


# ── Reglas 4 y 5 · separadores y tokens vacíos ───────────────────────────────


def test_el_token_vacio_se_omite_junto_con_su_separador() -> None:
    """Sin la zona, el nombre no puede quedar con un hueco `NaveA__004`."""
    generado = generar_nombre({**CONTEXTO, "zona": None})
    assert generado.nombre == "2026-014_NaveA_CLIMA_004"
    assert "__" not in generado.nombre
    assert generado.omitidos == ("[Zona]",)


def test_los_tokens_con_relleno_no_se_omiten() -> None:
    """Activo y sistema llevan valor de reemplazo: su ausencia es información
    y conviene que se vea en el nombre."""
    generado = generar_nombre({"proyecto": "2026-014", "numero": "004"})
    assert generado.nombre == "2026-014_SinActivo_SinSistema_004"
    assert generado.omitidos == ("[Zona]",)


# ── Regla 6 · longitud ───────────────────────────────────────────────────────


def test_al_recortar_se_conserva_siempre_el_correlativo() -> None:
    """Perder el número al recortar produciría colisiones justo en los nombres
    más largos, que son los que más se parecen entre sí."""
    generado = generar_nombre(
        {**CONTEXTO, "activo": "A" * 400, "numero": "017"}, plantilla=PLANTILLA_POR_DEFECTO
    )
    assert len(generado.nombre) <= LONGITUD_MAXIMA
    assert generado.nombre.endswith("_017")


# ── Regla 7 · nombres reservados de Windows ──────────────────────────────────


@pytest.mark.parametrize("reservado", ["CON", "PRN", "AUX", "NUL", "COM1", "LPT9"])
def test_los_nombres_reservados_de_windows_reciben_prefijo(reservado: str) -> None:
    """Un ZIP con `CON.jpg` dentro no se puede descomprimir en Windows, y el
    usuario no tendría forma de saber por qué."""
    generado = generar_nombre({"proyecto": reservado}, plantilla="[Proyecto]")
    assert generado.nombre == f"_{reservado}"


# ── Regla 8 · la extensión no está en la plantilla ───────────────────────────


def test_la_extension_no_forma_parte_del_nombre_editable() -> None:
    generado = generar_nombre(CONTEXTO, extension=".HEIC")
    assert "." not in generado.nombre
    assert generado.completo == f"{generado.nombre}.HEIC"


def test_la_extension_se_normaliza_con_punto() -> None:
    assert generar_nombre(CONTEXTO, extension="jpg").extension == ".jpg"


# ── Plantilla completa ───────────────────────────────────────────────────────


def test_la_plantilla_por_defecto_produce_el_nombre_documentado() -> None:
    assert generar_nombre(CONTEXTO).nombre == "2026-014_NaveA_CLIMA_Cubierta_004"


def test_los_tokens_desconocidos_no_rompen_el_nombre() -> None:
    """Una plantilla mal escrita produce un nombre razonable, no una excepción:
    quien la escribe es un usuario, no un programador."""
    generado = generar_nombre(CONTEXTO, plantilla="[Proyecto]_[NoExiste]_[Numero]")
    assert generado.nombre.startswith("2026-014_")
    assert generado.nombre.endswith("_004")


def test_un_contexto_vacio_no_produce_un_nombre_vacio() -> None:
    assert generar_nombre({}, plantilla="[Zona]").nombre == "SinNombre"


# ── Colisiones ───────────────────────────────────────────────────────────────


def test_las_colisiones_reciben_sufijo_alfabetico() -> None:
    """`[REC]` Alfabético a propósito: `_2` se confundiría con el correlativo."""
    base = "2026-014_NaveA_CLIMA_Cubierta_004"
    assert resolver_colisiones([base, base, base]) == [base, f"{base}_b", f"{base}_c"]


def test_las_colisiones_respetan_la_extension() -> None:
    assert resolver_colisiones(["foto.jpg", "foto.jpg"]) == ["foto.jpg", "foto_b.jpg"]


def test_las_colisiones_no_distinguen_mayusculas() -> None:
    """Windows y macOS no distinguen: dos nombres que solo difieren en la caja
    colisionarían al descomprimir, aunque en la base sean distintos."""
    assert resolver_colisiones(["Foto", "foto"]) == ["Foto", "foto_b"]


@pytest.mark.parametrize(
    ("orden", "sufijo"), [(1, ""), (2, "b"), (3, "c"), (26, "z"), (27, "aa"), (28, "ab")]
)
def test_el_sufijo_sigue_siendo_unico_pasada_la_z(orden: int, sufijo: str) -> None:
    assert sufijo_alfabetico(orden) == sufijo


def test_sin_repetidos_no_se_toca_nada() -> None:
    nombres = ["a", "b", "c"]
    assert resolver_colisiones(nombres) == nombres


# ── Correlativo ──────────────────────────────────────────────────────────────


def test_el_correlativo_se_rellena_con_ceros() -> None:
    assert numero_correlativo(4) == "004"
    assert numero_correlativo(4, digitos=5) == "00004"


def test_el_correlativo_no_se_trunca_si_se_pasa_de_digitos() -> None:
    """Con más de 999 fotos —que las hay— el número crece, no se corta."""
    assert numero_correlativo(1234) == "1234"

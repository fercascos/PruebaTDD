"""El comparador de precios `[REQ]` §14.

Lo que se comprueba aquí no es que compare bien: es que **no haga las tres cosas
que el cliente prohibió por escrito**. No consultar fuentes sin permiso, no
elegir un precio por su cuenta y no callarse lo que no ha mirado.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from tdd.pricing.service import (
    MINIMO_JUSTIFICACION,
    Fuente,
    Referencia,
    TipoDeFuente,
    ValidacionRechazada,
    actualizar_por_indice,
    comparar,
    comprobar_validacion,
    motivo_de_no_consulta,
)

HOY = date(2026, 8, 6)


def fuente(**extra) -> Fuente:
    base = {
        "code": "PRECIOCENTRO",
        "name": "Precio Centro",
        "source_type": TipoDeFuente.BASE_PRECIOS_LICENCIADA,
        "is_enabled": False,
        "tos_reviewed": False,
    }
    return Fuente(**{**base, **extra})


def referencia(**extra) -> Referencia:
    base = {
        "id": "r1",
        "source_code": "CI",
        "source_name": "Catálogo interno",
        "description": "Sustitución de enfriadora 300 kW",
        "unit": "ud",
        "unit_price": Decimal("48500.00"),
        "currency": "EUR",
        "price_date": date(2025, 11, 1),
    }
    return Referencia(**{**base, **extra})


# ─────────────────────────────────────────────────────────────────────────────
#  Lo que NO se ha consultado, y por qué
# ─────────────────────────────────────────────────────────────────────────────


def test_una_fuente_sin_habilitar_sale_como_no_consultada() -> None:
    """`[REQ]` §14 · Es la columna que impide que la pantalla mienta por
    omisión: tres referencias parecen decir «esto es lo que hay en el mercado»
    cuando dicen «esto es lo que alguien introdujo»."""
    motivo = motivo_de_no_consulta(fuente(), hoy=HOY)
    assert motivo is not None
    assert "no se ha realizado ninguna consulta automatizada" in motivo.lower()


def test_el_motivo_escrito_por_el_administrador_manda() -> None:
    motivo = motivo_de_no_consulta(
        fuente(disabled_reason="Pendiente de firmar el contrato de licencia."), hoy=HOY
    )
    assert motivo == "Pendiente de firmar el contrato de licencia."


def test_habilitada_pero_sin_revisar_las_condiciones_tampoco_se_consulta() -> None:
    """Redundante con el `CHECK` de la base de datos, y a propósito: si un día
    alguien relaja la restricción, la pantalla sigue diciendo la verdad."""
    motivo = motivo_de_no_consulta(fuente(is_enabled=True, tos_reviewed=False), hoy=HOY)
    assert motivo is not None
    assert "condiciones de uso" in motivo


def test_una_licencia_caducada_deja_la_fuente_fuera() -> None:
    motivo = motivo_de_no_consulta(
        fuente(is_enabled=True, tos_reviewed=True, license_expires_at=date(2026, 1, 31)),
        hoy=HOY,
    )
    assert motivo is not None
    assert "2026-01-31" in motivo


def test_una_licencia_vigente_no_bloquea() -> None:
    assert (
        motivo_de_no_consulta(
            fuente(is_enabled=True, tos_reviewed=True, license_expires_at=date(2027, 1, 1)),
            hoy=HOY,
        )
        is None
    )


def test_una_fuente_manual_nunca_se_consulta_ni_se_avisa() -> None:
    """Es el consultor tecleando: no tiene sentido decir que no se ha llamado a
    nadie."""
    manual = fuente(code="MANUAL", source_type=TipoDeFuente.MANUAL, is_enabled=True)
    assert motivo_de_no_consulta(manual, hoy=HOY) is None


def test_la_comparacion_enumera_las_fuentes_que_se_ha_dejado_fuera() -> None:
    resultado = comparar(
        [referencia()],
        [
            fuente(code="MANUAL", source_type=TipoDeFuente.MANUAL, is_enabled=True),
            fuente(),
        ],
        hoy=HOY,
    )
    assert len(resultado.referencias) == 1
    assert [f.code for f in resultado.no_consultadas] == ["PRECIOCENTRO"]


def test_sin_referencias_sigue_diciendo_lo_que_no_ha_mirado() -> None:
    """Es cuando más importa: una pantalla vacía sin explicación parece un
    fallo, y lo que hay es que no se ha consultado nada."""
    resultado = comparar([], [fuente()], hoy=HOY)
    assert resultado.referencias == []
    assert len(resultado.no_consultadas) == 1


# ─────────────────────────────────────────────────────────────────────────────
#  Nada se elige solo
# ─────────────────────────────────────────────────────────────────────────────


def test_la_comparacion_no_marca_ninguna_referencia_como_elegida() -> None:
    """`[REQ]` «Nunca selecciones automáticamente un precio como definitivo sin
    revisión humana.» No hay campo donde ponerlo."""
    resultado = comparar([referencia(), referencia(id="r2")], [], hoy=HOY)
    assert not hasattr(resultado, "recomendada")
    assert not hasattr(resultado, "elegida")
    assert "un consultor debe validar" in resultado.aviso.lower()


def test_las_referencias_salen_por_fecha_y_no_por_importe() -> None:
    """Ordenar por precio sugeriría preferencia por el más barato, que es justo
    la insinuación que no se puede hacer."""
    vieja = referencia(id="vieja", unit_price=Decimal("10"), price_date=date(2024, 1, 1))
    nueva = referencia(id="nueva", unit_price=Decimal("99999"), price_date=date(2026, 7, 10))
    resultado = comparar([vieja, nueva], [], hoy=HOY)
    assert [r.id for r in resultado.referencias] == ["nueva", "vieja"]


def test_una_referencia_sin_fecha_va_al_final_y_no_se_pierde() -> None:
    sin_fecha = referencia(id="sin_fecha", price_date=None)
    resultado = comparar([sin_fecha, referencia(id="con_fecha")], [], hoy=HOY)
    assert [r.id for r in resultado.referencias] == ["con_fecha", "sin_fecha"]


# ─────────────────────────────────────────────────────────────────────────────
#  Validación humana
# ─────────────────────────────────────────────────────────────────────────────


def test_aplicar_la_referencia_tal_cual_no_exige_escribir_nada() -> None:
    """Exigir que alguien escriba «es el precio de la referencia» produce ruido,
    no trazabilidad."""
    nota = comprobar_validacion(
        importe=Decimal("48500.00"), referencia=referencia(), justificacion=None
    )
    assert "Catálogo interno" in nota


def test_un_importe_distinto_exige_explicacion() -> None:
    with pytest.raises(ValidacionRechazada) as exc:
        comprobar_validacion(
            importe=Decimal("52000.00"), referencia=referencia(), justificacion=None
        )
    assert "48500.00" in str(exc.value)
    assert "52000.00" in str(exc.value)


def test_una_explicacion_de_dos_letras_no_cuenta() -> None:
    with pytest.raises(ValidacionRechazada):
        comprobar_validacion(
            importe=Decimal("52000.00"), referencia=referencia(), justificacion="ok"
        )


def test_un_importe_distinto_con_explicacion_pasa() -> None:
    nota = comprobar_validacion(
        importe=Decimal("52000.00"),
        referencia=referencia(),
        justificacion="Oferta en firme del proveedor, incluye puesta en marcha.",
    )
    assert nota.startswith("Oferta en firme")


def test_una_nota_corta_con_el_importe_de_la_referencia_no_rompe_la_base() -> None:
    """La nota es opcional cuando el importe coincide, pero la base exige diez
    caracteres a cualquier precio validado (`validado_exige_persona_y_nota`).

    Escribir «ok» de más devolvía una nota de dos letras que la base rechazaba:
    el usuario veía un 500 por haber escrito de más en un campo opcional. Ahora
    se conserva lo escrito y se le añade la procedencia.
    """
    nota = comprobar_validacion(
        importe=Decimal("48500.00"), referencia=referencia(), justificacion="ok"
    )
    assert nota.startswith("ok")
    assert "Catálogo interno" in nota
    assert len(nota.strip()) >= MINIMO_JUSTIFICACION


def test_un_precio_sin_procedencia_no_se_valida_por_mucho_que_se_explique() -> None:
    """`[REQ]` «Una partida con precio conserva su procedencia», y lo exige el
    `CHECK` `precio_exige_referencia` de la base de datos.

    Esta capa lo comprueba antes para que salga un mensaje que dice **qué
    hacer**, no un error de integridad. La primera versión del servicio dejaba
    pasar un precio sin referencia si venía explicado: habría producido un 500
    en cuanto tocara la base.
    """
    with pytest.raises(ValidacionRechazada) as exc:
        comprobar_validacion(
            importe=Decimal("1000"),
            referencia=None,
            justificacion="Presupuesto solicitado a tres industriales, media de los tres.",
        )
    assert "referencia" in str(exc.value).lower()
    # El mensaje explica la salida: dar de alta una referencia manual.
    assert "manual" in str(exc.value).lower()


# ─────────────────────────────────────────────────────────────────────────────
#  Actualización por índice
# ─────────────────────────────────────────────────────────────────────────────


def test_la_actualizacion_devuelve_la_formula_con_sus_operandos() -> None:
    """`[REQ]` Un número sin el cálculo detrás no se puede defender delante de
    un cliente."""
    r = actualizar_por_indice(
        Decimal("48500.00"),
        indice_origen=Decimal("112.7"),
        indice_destino=Decimal("118.4"),
        factor_geografico=Decimal("1.05"),
    )
    # 48.500 × (118,4 / 112,7) × 1,05 = 53.500,62.
    # La maqueta de `docs/09-ux-pantallas.md` decía 53.494,52: era un error
    # aritmético del boceto, corregido en el documento al escribir esta prueba.
    assert r.resultado == Decimal("53500.62")
    assert "112.7" in r.formula
    assert "118.4" in r.formula
    assert "1.05" in r.formula


def test_sin_factor_geografico_el_precio_solo_se_actualiza_por_indice() -> None:
    r = actualizar_por_indice(
        Decimal("100"), indice_origen=Decimal("100"), indice_destino=Decimal("110")
    )
    assert r.resultado == Decimal("110.00")


def test_un_indice_a_cero_se_rechaza_en_vez_de_dividir() -> None:
    for malo in (Decimal("0"), Decimal("-5")):
        with pytest.raises(ValueError, match="origen"):
            actualizar_por_indice(Decimal("100"), indice_origen=malo, indice_destino=Decimal("110"))


def test_el_calculo_no_pasa_por_float() -> None:
    """Pasar por `float` introduce error en el último céntimo, y estos números
    acaban sumados en la tabla de un informe que alguien firma."""
    r = actualizar_por_indice(
        Decimal("0.10"), indice_origen=Decimal("3"), indice_destino=Decimal("1")
    )
    assert isinstance(r.resultado, Decimal)
    assert r.resultado == Decimal("0.03")


def test_actualizar_no_aplica_nada_por_su_cuenta() -> None:
    """Devuelve una propuesta. Quien llama decide, y al aplicarla el precio
    vuelve a quedar pendiente de validación."""
    r = actualizar_por_indice(
        Decimal("100"), indice_origen=Decimal("100"), indice_destino=Decimal("200")
    )
    assert r.base == Decimal("100"), "la base no se toca"
    assert r.resultado == Decimal("200.00")


# ─────────────────────────────────────────────────────────────────────────────
#  Lo que este módulo no hace
# ─────────────────────────────────────────────────────────────────────────────


def test_el_modulo_no_abre_ninguna_conexion() -> None:
    """`[REQ]` «No inventes APIs ni fuentes de precios», y no se hace scraping
    de nada. Se comprueba sobre el fichero: leerlo es lo único que garantiza
    que nadie añada un `requests.get` de aquí a seis meses sin enterarse."""
    from pathlib import Path

    import tdd.pricing.service as modulo

    fuente_del_modulo = Path(modulo.__file__).read_text(encoding="utf-8")
    for prohibido in ("requests", "httpx", "urllib", "aiohttp", "socket", "urlopen"):
        assert prohibido not in fuente_del_modulo, (
            f"«{prohibido}» aparece en el comparador de precios: este módulo no "
            "puede salir a la red."
        )


def test_ninguna_referencia_de_prueba_apunta_a_un_sitio_real() -> None:
    """El comparador guarda `source_url` como dato, pero nada lo abre."""
    r = referencia()
    assert not hasattr(r, "descargar")
    assert not hasattr(r, "consultar")
    assert isinstance(r.retrieved_at, datetime | None)

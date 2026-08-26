"""El conector simulado no puede parecerse a uno real.

`[LIM]` Estas pruebas existen para que la simulación siga siendo evidente. El
día que alguien sustituya el conector por uno de verdad, las que hablan de la
marca y de la confianza vacía deben **borrarse a conciencia**, no pasar de
casualidad porque el nuevo también las cumpla.
"""

from __future__ import annotations

import hashlib

from tdd.revision_documental.puerto import Comprobacion, Documento, Veredicto
from tdd.revision_documental.simulado import MARCA, NOMBRE, RevisorSimulado

CRITERIOS = (
    Comprobacion("CORRESPONDENCIA", "Corresponde con lo solicitado", "…"),
    Comprobacion("VIGENCIA", "Vigencia y caducidad", "…"),
    Comprobacion("COMPLETITUD", "Completitud", "…"),
    Comprobacion("LEGIBILIDAD", "Legibilidad", "…"),
)


def documento(contenido: bytes = b"%PDF-1.7 nada") -> Documento:
    return Documento(
        nombre="licencia.pdf",
        mime_type="application/pdf",
        contenido=contenido,
        sha256=hashlib.sha256(contenido).hexdigest(),
        solicitado="Licencia de actividad",
    )


def test_da_una_observacion_por_criterio() -> None:
    d = RevisorSimulado().revisar(documento(), CRITERIOS)
    assert len(d.observaciones) == len(CRITERIOS)
    assert {o.comprobacion for o in d.observaciones} == {c.codigo for c in CRITERIOS}


def test_toda_observacion_va_marcada_como_simulada() -> None:
    """Quien lo lea en pantalla tiene que saberlo sin consultar nada más."""
    d = RevisorSimulado().revisar(documento(), CRITERIOS)
    assert all(o.resumen.startswith(MARCA) for o in d.observaciones)


def test_el_dictamen_se_declara_simulado_y_sin_modelo() -> None:
    d = RevisorSimulado().revisar(documento(), CRITERIOS)
    assert d.simulado is True
    assert d.proveedor == NOMBRE
    assert d.modelo is None


def test_nunca_inventa_una_confianza() -> None:
    """`[REQ]` Un número de confianza simulado se leería como una medida.

    Es el fallo más engañoso que podría cometer este módulo: quien revisa
    trataría un 0,92 inventado como una razón para no mirar el documento.
    """
    d = RevisorSimulado().revisar(documento(), CRITERIOS)
    assert all(o.confianza is None for o in d.observaciones)


def test_nunca_inventa_una_pagina() -> None:
    """Citar «página 4» sin haber abierto el fichero sería una cita falsa."""
    d = RevisorSimulado().revisar(documento(), CRITERIOS)
    assert all(o.pagina is None for o in d.observaciones)


def test_el_mismo_documento_da_siempre_lo_mismo() -> None:
    """Determinista: si no lo fuera, ninguna prueba de arriba sería estable."""
    revisor = RevisorSimulado()
    uno = revisor.revisar(documento(), CRITERIOS)
    otro = revisor.revisar(documento(), CRITERIOS)
    assert [o.veredicto for o in uno.observaciones] == [o.veredicto for o in otro.observaciones]


def test_documentos_distintos_dan_veredictos_distintos() -> None:
    """Sin esto, la pantalla solo se podría probar contra un único caso."""
    revisor = RevisorSimulado()
    vistos = {
        tuple(
            o.veredicto
            for o in revisor.revisar(documento(f"doc {i}".encode()), CRITERIOS).observaciones
        )
        for i in range(20)
    }
    assert len(vistos) > 1


def test_cubre_los_cuatro_veredictos_en_algun_documento() -> None:
    """La pantalla tiene que poder ejercitarse con `NO_CONFORME`, que es el
    caso que dispara trabajo de verdad."""
    revisor = RevisorSimulado()
    vistos = {
        o.veredicto
        for i in range(20)
        for o in revisor.revisar(documento(f"doc {i}".encode()), CRITERIOS).observaciones
    }
    assert vistos == set(Veredicto)


def test_sin_criterios_no_hay_observaciones() -> None:
    """Desactivar todos los criterios da una revisión vacía, no un error."""
    d = RevisorSimulado().revisar(documento(), ())
    assert d.observaciones == ()

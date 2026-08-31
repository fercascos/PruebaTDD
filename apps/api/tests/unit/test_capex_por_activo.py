"""El CAPEX de una cartera, separado por activo.

La plantilla del cliente describe **un** edificio: un nombre, unas superficies
y un tipo que decide qué zonas ofrece el desplegable. Un encargo de tres naves
metido en un solo libro sale con la cabecera de la primera y las otras dos sin
identificar, y si son de tipos distintos sus zonas se vacían.

`separar_por_activo()` es lo que lo arregla. Lo que se comprueba aquí no es que
devuelva tres cosas, sino las tres propiedades de las que depende que el
fichero que se le manda al cliente sea correcto:

* **no se pierde nada** —ni un hallazgo, ni una línea, ni un activo—,
* cada parte lleva **su** tipo de edificio, que es lo que resuelve las zonas,
* y la cabida de la plantilla se cuenta por activo, no entre todos.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tdd.exports.capex_desde_snapshot import (
    Parte,
    actuaciones_de,
    encargo_de,
    preparar,
    separar_por_activo,
)
from tdd.exports.vocabulario_capex import leer

#: Dos tipologías **distintas** a propósito: es el caso que rompía las zonas.
NAVE = {
    "id": "a-1",
    "name": "Nave Norte",
    "asset_code": "N-01",
    "typology_code": "INDUSTRIAL",
    "address_line": "Polígono ficticio, 1",
    "total_built_sqm": "18400",
}
OFICINA = {
    "id": "a-2",
    "name": "Edificio Sur",
    "asset_code": "S-02",
    "typology_code": "OFICINAS",
    "address_line": "Calle ficticia, 2",
    "total_built_sqm": "6100",
}


def _hallazgo(id_: str, activo: str, **extra: Any) -> dict[str, Any]:
    base = {
        "id": id_,
        "asset_id": activo,
        "title": f"Hallazgo {id_}",
        "capex_chapter_code": "HC.H08",
        "capex_code": "HC.H08.01",
        "zone_code": "CUARTOS_TECNICOS",
        "risk_code": "04",
        "concept_code": "MANTENIMIENTO",
        "tenant_recoverable": "NO",
    }
    return {**base, **extra}


def _linea(hallazgo: str, importe: str = "1000") -> dict[str, Any]:
    return {"finding_id": hallazgo, "time_horizon_code": "CORTO", "amount": importe}


def _snapshot(
    activos: list[dict[str, Any]],
    hallazgos: list[dict[str, Any]],
    lineas: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "project": {"id": "p-1", "name": "Cartera ficticia", "internal_code": "2026-099"},
        "generated_at": "2026-08-31T09:00:00",
        "assets": activos,
        "findings": hallazgos,
        "capex_items": lineas,
    }


def _cartera() -> dict[str, Any]:
    hallazgos = [
        _hallazgo("h-1", "a-1"),
        _hallazgo("h-2", "a-1"),
        _hallazgo("h-3", "a-2"),
    ]
    lineas = [_linea("h-1", "1000"), _linea("h-2", "2000"), _linea("h-3", "4000")]
    return _snapshot([NAVE, OFICINA], hallazgos, lineas)


# ─────────────────────────────────────────────────────────────────────────────
#  Que no se pierda nada
# ─────────────────────────────────────────────────────────────────────────────


def test_cada_activo_se_lleva_sus_hallazgos_y_sus_lineas() -> None:
    partes = separar_por_activo(_cartera())

    assert [p.asset_id for p in partes] == ["a-1", "a-2"]
    assert [p.actuaciones for p in partes] == [2, 1]
    # Las líneas siguen a su hallazgo: si se repartieran por su cuenta, el
    # importe de un activo acabaría en el libro del otro.
    assert [len(p.snapshot["capex_items"]) for p in partes] == [2, 1]
    assert {linea["finding_id"] for linea in partes[1].snapshot["capex_items"]} == {"h-3"}


def test_la_suma_de_las_partes_es_el_encargo_entero() -> None:
    """`[REQ]` La propiedad que importa: separar **no puede perder** nada.

    Un hallazgo que desaparece del Excel que se manda al cliente es el fallo
    que nadie detecta hasta que alguien suma a mano.
    """
    entero = _cartera()
    partes = separar_por_activo(entero)

    hallazgos = [h["id"] for p in partes for h in p.snapshot["findings"]]
    lineas = [linea["finding_id"] for p in partes for linea in p.snapshot["capex_items"]]

    assert sorted(hallazgos) == sorted(h["id"] for h in entero["findings"])
    assert sorted(lineas) == sorted(linea["finding_id"] for linea in entero["capex_items"])
    assert len(hallazgos) == len(set(hallazgos)), "un hallazgo ha salido en dos partes"


def test_un_activo_sin_actuaciones_sale_igual_con_su_parte_vacia() -> None:
    """No es lo mismo un edificio sin visitar que uno visitado y sin hallazgos.

    Si el activo desapareciera de la lista, desde fuera se verían igual.
    """
    partes = separar_por_activo(_snapshot([NAVE, OFICINA], [_hallazgo("h-1", "a-1")], []))

    assert [p.asset_id for p in partes] == ["a-1", "a-2"]
    assert partes[1].actuaciones == 0


def test_un_hallazgo_de_un_activo_borrado_no_se_evapora() -> None:
    """El snapshot deja fuera los activos borrados, pero **no** sus hallazgos.

    Sin la parte huérfana, esos hallazgos no caerían en ninguna y se irían del
    fichero en silencio. Con ella salen, marcados, en su propio libro.
    """
    partes = separar_por_activo(
        _snapshot([NAVE], [_hallazgo("h-1", "a-1"), _hallazgo("h-9", "borrado")], [])
    )

    assert len(partes) == 2
    huerfana = partes[-1]
    assert huerfana.huerfana is True
    assert huerfana.asset_id is None
    assert [h["id"] for h in huerfana.snapshot["findings"]] == ["h-9"]


def test_sin_huerfanos_no_hay_parte_de_huerfanos() -> None:
    assert all(not p.huerfana for p in separar_por_activo(_cartera()))


# ─────────────────────────────────────────────────────────────────────────────
#  Que cada libro describa SU edificio
# ─────────────────────────────────────────────────────────────────────────────


def test_cada_parte_lleva_su_cabecera_y_su_tipo_de_edificio() -> None:
    """Es la razón de ser de todo esto.

    En el libro conjunto la cabecera describe al primer activo y el tipo de
    edificio es el suyo, así que el desplegable de zonas del segundo es el
    equivocado. Separado, cada uno lleva el propio.
    """
    v = leer("es")
    partes = separar_por_activo(_cartera())

    nave = encargo_de(partes[0].snapshot, v, activo_en_el_nombre=True)
    oficina = encargo_de(partes[1].snapshot, v, activo_en_el_nombre=True)

    assert nave.direccion == "Polígono ficticio, 1"
    assert oficina.direccion == "Calle ficticia, 2"
    assert nave.superficie_total == Decimal("18400")
    assert oficina.superficie_total == Decimal("6100")
    # Lo que decide qué zonas ofrece la plantilla.
    assert nave.tipo_edificio != oficina.tipo_edificio


def test_el_libro_de_un_activo_lleva_su_nombre_en_la_cabecera() -> None:
    """La celda se llama «Nombre del proyecto» y en una cartera eso no basta.

    Dos libros del mismo encargo llevarían la misma cabecera y solo se
    distinguirían por el nombre del fichero.
    """
    v = leer("es")
    partes = separar_por_activo(_cartera())

    conjunto = encargo_de(_cartera(), v)
    suelto = encargo_de(partes[1].snapshot, v, activo_en_el_nombre=True)

    assert conjunto.nombre == "Cartera ficticia"
    assert suelto.nombre == "Cartera ficticia · Edificio Sur"


def test_el_libro_del_encargo_entero_no_cambia_de_cabecera() -> None:
    """Quien ya usaba la descarga de siempre se sigue bajando el mismo fichero."""
    v = leer("es")
    assert encargo_de(_cartera(), v).nombre == "Cartera ficticia"


def test_la_zona_se_resuelve_con_la_tipologia_de_su_activo() -> None:
    """`Almacén` existe en industrial y no en oficinas.

    En el libro conjunto, un hallazgo del edificio de oficinas se evaluaba
    contra la tipología del primer activo. Aquí cada parte usa la suya.
    """
    v = leer("es")
    cartera = _snapshot(
        [NAVE, OFICINA],
        [
            _hallazgo("h-1", "a-1", zone_code="ALMACEN"),
            _hallazgo("h-2", "a-2", zone_code="ALMACEN"),
        ],
        [],
    )
    partes = separar_por_activo(cartera)

    en_la_nave = actuaciones_de(partes[0].snapshot, v)[0]
    en_la_oficina = actuaciones_de(partes[1].snapshot, v)[0]

    assert en_la_nave.zona is not None, "«Almacén» sí existe en industrial"
    # Y en oficinas no: la celda se deja vacía en vez de escribir un valor que
    # el desplegable rechaza y las tablas dinámicas dejan fuera.
    assert en_la_oficina.zona is None


def test_preparar_acepta_la_parte_como_si_fuera_el_encargo_entero() -> None:
    """La parte es un snapshot completo, no una estructura aparte.

    Importa porque significa que el libro por activo se rellena por el **mismo**
    camino que el conjunto: no hay una segunda ruta que pueda divergir.
    """
    parte = separar_por_activo(_cartera())[0]

    encargo, actuaciones = preparar(parte.snapshot, idioma="es", activo_en_el_nombre=True)

    assert encargo.nombre.endswith("Nave Norte")
    assert len(actuaciones) == 2


# ─────────────────────────────────────────────────────────────────────────────
#  Cabida y nombres de fichero
# ─────────────────────────────────────────────────────────────────────────────


def test_la_cabida_de_la_plantilla_se_cuenta_por_activo() -> None:
    """`[REQ]` Diez actuaciones por bloque **y por activo**, no entre todos.

    Doce hallazgos del mismo capítulo repartidos entre dos naves no caben en un
    libro conjunto —la plantilla admite diez— y sí caben separados, seis y
    seis. Es la otra mitad de por qué la cartera necesita separarse.
    """
    from tdd.exports.plantilla_capex import comprobar_cabida

    hallazgos = [_hallazgo(f"h-{i}", "a-1" if i < 6 else "a-2") for i in range(12)]
    cartera = _snapshot([NAVE, OFICINA], hallazgos, [])
    v = leer("es")

    assert comprobar_cabida(actuaciones_de(cartera, v)), "el libro conjunto no debería caber"
    for parte in separar_por_activo(cartera):
        assert not comprobar_cabida(actuaciones_de(parte.snapshot, v))


def test_el_nombre_del_fichero_usa_el_codigo_del_activo() -> None:
    partes = separar_por_activo(_cartera())
    assert partes[0].nombre_de_fichero("CAPEX_2026-099") == "CAPEX_2026-099_N-01.xlsx"


def test_el_nombre_del_fichero_se_sanea() -> None:
    """Un activo llamado «Nave A / B» rompería la ruta dentro del ZIP."""
    parte = Parte(
        asset_id="a-9",
        nombre="Nave Ñ / Sección 2",
        codigo=None,
        snapshot=_snapshot([], [], []),
    )
    nombre = parte.nombre_de_fichero("CAPEX_X")

    assert "/" not in nombre
    assert nombre.isascii()
    assert nombre.endswith(".xlsx")

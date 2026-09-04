"""`[REQ]` Los cortes del CAPEX que alimentan el resumen.

Cuatro preguntas distintas y por eso cuatro consultas: **en qué se va el
dinero** (concepto), **cuándo hay que pagarlo** (horizonte), **qué parte del
edificio** (capítulo) y **qué edificio** (activo).

Lo que se fija aquí es lo que hace que un gráfico no mienta:

* que un hallazgo codificado en un **objeto** sume en su **capítulo**, y no
  aparezca como un trozo suelto que no suma nada reconocible;
* que las líneas de un hallazgo **sin concepto** no se pierdan;
* que los cuatro cortes **sumen lo mismo**, porque si no el gráfico de al lado
  contradice al de arriba;
* y que un hallazgo descartado no cuente en ninguno.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.db

RUTA = "/api/v1"


@pytest.fixture
def proyecto(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo con resumen') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"RES-{uuid.uuid4().hex[:6]}",
                },
            ).scalar_one()
        )


@pytest.fixture(scope="module")
def tipologia(motor_admin: Engine) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text("SELECT id FROM asset_typology WHERE code = 'INDUSTRIAL'")
            ).scalar_one()
        )


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, tipologia: str) -> str:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave 1", "typology_id": tipologia},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def catalogo(cliente: TestClient, cab: Any, ruta: str) -> list[dict[str, Any]]:
    return list(cliente.get(f"{RUTA}/catalogs/{ruta}", headers=cab("consultor_a")).json())


def crear_hallazgo(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    activo: str,
    *,
    codigo_capex: str,
    concepto: str | None,
    importe: str,
    horizonte: str = "CORTO",
    titulo: str = "Actuación",
) -> str:
    # `/capex-codes` es una lista PLANA con `level` y `parent_id`. La
    # documentación menciona un `/capex-codes/tree` que no está construido:
    # pedirlo devuelve un 404 cuyo cuerpo, iterado, da cadenas.
    codigos = catalogo(cliente, cab, "capex-codes")
    code_id = next(c["id"] for c in codigos if c["code"] == codigo_capex)

    zonas = catalogo(cliente, cab, "zones")
    zona = next(z for z in zonas if z["code"] == "GENERAL")

    cuerpo: dict[str, Any] = {
        "asset_id": activo,
        "capex_code_id": code_id,
        "zone_id": zona["id"],
        "title": titulo,
        "description": "",
        "capex_lines": [{"time_horizon_code": horizonte, "amount": importe}],
    }
    if concepto is not None:
        conceptos = catalogo(cliente, cab, "capex-concepts")
        cuerpo["capex_concept_id"] = next(c["id"] for c in conceptos if c["code"] == concepto)

    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/findings", headers=cab("consultor_a"), json=cuerpo
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def resumen(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    corte: str,
    *,
    asset_id: str | None = None,
) -> list[dict[str, Any]]:
    sufijo = f"?asset_id={asset_id}" if asset_id else ""
    r = cliente.get(
        f"{RUTA}/projects/{proyecto}/capex/summary/by-{corte}{sufijo}",
        headers=cab("consultor_a"),
    )
    assert r.status_code == 200, r.text
    return list(r.json())


@pytest.fixture
def otro_activo(cliente: TestClient, cab: Any, proyecto: str, tipologia: str) -> str:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave 2", "typology_id": tipologia},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


# ─────────────────────────────────────────────────────────────────────────────
#  Por concepto: en qué se va el dinero
# ─────────────────────────────────────────────────────────────────────────────


def test_el_reparto_por_concepto_agrupa_y_ordena_por_importe(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` Es la distinción que separa un edificio caro de uno mal mantenido:
    «Normativa» hay que pagarlo, «Mejora» se puede decidir, y en el total valen
    lo mismo."""
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H06",
        concepto="NORMATIVA",
        importe="30000.00",
        titulo="PCI fuera de norma",
    )
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H02",
        concepto="NORMATIVA",
        importe="20000.00",
        titulo="Más normativa",
    )
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H03",
        concepto="MEJORA",
        importe="10000.00",
        titulo="Una mejora",
    )

    filas = resumen(cliente, cab, proyecto, "concept")

    assert [f["capex_concept_code"] for f in filas] == ["NORMATIVA", "MEJORA"]
    assert Decimal(filas[0]["amount"]) == Decimal("50000.00")
    assert filas[0]["findings"] == 2
    assert Decimal(filas[1]["amount"]) == Decimal("10000.00")


def test_un_hallazgo_sin_concepto_no_se_pierde(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` Que nadie lo haya clasificado **es un dato**, no un hueco. Si
    desapareciera del reparto, la tarta no sumaría el total del encargo y nadie
    sabría por qué."""
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H06",
        concepto=None,
        importe="7000.00",
        titulo="Sin clasificar",
    )

    filas = resumen(cliente, cab, proyecto, "concept")

    assert len(filas) == 1
    assert filas[0]["capex_concept_code"] == "SIN_CONCEPTO"
    assert filas[0]["capex_concept_name"] == "Sin concepto"
    assert Decimal(filas[0]["amount"]) == Decimal("7000.00")


def test_los_conceptos_sin_importe_no_salen(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """Los diez del catálogo con ceros llenarían el gráfico de porciones
    invisibles. Los que faltan es que no hay."""
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H06",
        concepto="SEGURIDAD",
        importe="1000.00",
    )
    filas = resumen(cliente, cab, proyecto, "concept")
    assert [f["capex_concept_code"] for f in filas] == ["SEGURIDAD"]


# ─────────────────────────────────────────────────────────────────────────────
#  Por capítulo: qué parte del edificio
# ─────────────────────────────────────────────────────────────────────────────


def test_un_hallazgo_en_un_objeto_suma_en_su_capitulo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` El capítulo es el nivel 2 y un hallazgo puede estar codificado en
    el 3. Agrupando por el código directo, un encargo con hallazgos a distintos
    niveles saldría partido en trozos que no suman nada reconocible."""
    codigos = catalogo(cliente, cab, "capex-codes")
    # Un objeto cualquiera de nivel 3 y el capítulo del que cuelga.
    objeto = next(c for c in codigos if c["level"] == 3)
    capitulo = next(c for c in codigos if c["id"] == objeto["parent_id"])

    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex=objeto["code"],
        concepto="MEJORA",
        importe="5000.00",
        titulo="Codificado en el objeto",
    )
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex=capitulo["code"],
        concepto="MEJORA",
        importe="3000.00",
        titulo="Codificado en el capítulo",
    )

    filas = resumen(cliente, cab, proyecto, "chapter")

    assert len(filas) == 1, "los dos tienen que caer en el mismo capítulo"
    assert filas[0]["chapter_code"] == capitulo["code"]
    assert Decimal(filas[0]["amount"]) == Decimal("8000.00")
    assert filas[0]["findings"] == 2


# ─────────────────────────────────────────────────────────────────────────────
#  Los cuatro cortes tienen que cuadrar entre sí
# ─────────────────────────────────────────────────────────────────────────────


def test_los_cuatro_cortes_suman_lo_mismo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` **Lo que hace creíble el resumen.** Cuatro gráficos en la misma
    pantalla que no cuadran entre sí destruyen la confianza en los cuatro, y el
    descuadre no lo ve nadie hasta que el cliente suma con la calculadora."""
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H06",
        concepto="NORMATIVA",
        importe="12345.67",
        horizonte="CORTO",
    )
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H02",
        concepto=None,
        importe="8000.00",
        horizonte="LARGO",
    )
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H03",
        concepto="MEJORA",
        importe="500.33",
        horizonte="MEJORAS",
    )

    totales = {
        corte: sum(Decimal(f["amount"]) for f in resumen(cliente, cab, proyecto, corte))
        for corte in ("concept", "horizon", "chapter", "asset")
    }

    assert len(set(totales.values())) == 1, totales
    assert totales["concept"] == Decimal("20846.00")


def test_un_hallazgo_borrado_no_cuenta_en_ninguno(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    vivo = crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H06",
        concepto="NORMATIVA",
        importe="1000.00",
    )
    muerto = crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H02",
        concepto="MEJORA",
        importe="9999.00",
    )
    # `If-Match` es obligatorio al borrar un hallazgo: sin él la API responde
    # 428 en vez de borrar a ciegas algo que otro pudo haber cambiado.
    borrado = cliente.delete(
        f"{RUTA}/findings/{muerto}",
        headers={**cab("consultor_a"), "If-Match": "1"},
    )
    assert borrado.status_code in (200, 204), borrado.text

    for corte in ("concept", "horizon", "chapter", "asset"):
        total = sum(Decimal(f["amount"]) for f in resumen(cliente, cab, proyecto, corte))
        assert total == Decimal("1000.00"), f"{corte} cuenta el hallazgo borrado"
    assert vivo


def test_un_encargo_sin_capex_devuelve_listas_vacias_y_no_revienta(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """La pantalla tiene que poder decir «todavía no hay nada» sin un 500."""
    assert resumen(cliente, cab, proyecto, "concept") == []
    assert resumen(cliente, cab, proyecto, "chapter") == []
    # El activo sale igual, con ceros: uno que desaparece de la tabla se
    # confunde con uno que se visitó y no tenía nada.
    por_activo = resumen(cliente, cab, proyecto, "asset")
    assert len(por_activo) == 1
    assert Decimal(por_activo[0]["amount"]) == Decimal("0")


def test_otra_organizacion_no_ve_el_resumen_ajeno(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H06",
        concepto="NORMATIVA",
        importe="1000.00",
    )
    assert resumen(cliente, cab, proyecto, "concept") != []

    r = cliente.get(f"{RUTA}/projects/{proyecto}/capex/summary/by-concept", headers=cab("admin_b"))
    assert r.json() == []


# ─────────────────────────────────────────────────────────────────────────────
#  El reparto por concepto, activo a activo `[REQ]`
# ─────────────────────────────────────────────────────────────────────────────


def test_el_reparto_se_puede_mirar_de_un_solo_activo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, otro_activo: str
) -> None:
    """`[REQ]` Son **dos preguntas** y las dos se hacen en la misma reunión.

    Agregado dice cómo se comporta el parque —si el problema es mantenimiento
    diferido o normativa—; por activo dice qué le pasa a ESE edificio, que es
    sobre el que se negocia el precio. Un parque con un 40 % de normativa puede
    tenerlo concentrado en una sola nave, y agregado eso no se ve.
    """
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H06",
        concepto="NORMATIVA",
        importe="90000.00",
        titulo="Normativa de la nave 1",
    )
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        otro_activo,
        codigo_capex="HC.H03",
        concepto="MEJORA",
        importe="10000.00",
        titulo="Mejora de la nave 2",
    )

    todos = resumen(cliente, cab, proyecto, "concept")
    solo_uno = resumen(cliente, cab, proyecto, "concept", asset_id=activo)
    solo_el_otro = resumen(cliente, cab, proyecto, "concept", asset_id=otro_activo)

    assert {f["capex_concept_code"] for f in todos} == {"NORMATIVA", "MEJORA"}
    assert [f["capex_concept_code"] for f in solo_uno] == ["NORMATIVA"]
    assert Decimal(solo_uno[0]["amount"]) == Decimal("90000.00")
    assert [f["capex_concept_code"] for f in solo_el_otro] == ["MEJORA"]


def test_los_repartos_por_activo_suman_el_del_encargo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, otro_activo: str
) -> None:
    """`[REQ]` Lo que hace que el filtro sea creíble. Si la suma de las partes
    no diera el todo, el gestor tendría que elegir a cuál de las dos vistas
    hacer caso, y ninguna de las dos merecería la pena."""
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H06",
        concepto="NORMATIVA",
        importe="12345.67",
    )
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H02",
        concepto=None,
        importe="1000.00",
    )
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        otro_activo,
        codigo_capex="HC.H03",
        concepto="NORMATIVA",
        importe="500.33",
    )

    def total(**kw: str) -> Decimal:
        return sum(
            (Decimal(f["amount"]) for f in resumen(cliente, cab, proyecto, "concept", **kw)),
            Decimal("0"),
        )

    assert total(asset_id=activo) + total(asset_id=otro_activo) == total()


def test_un_activo_sin_capex_devuelve_una_lista_vacia(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, otro_activo: str
) -> None:
    """Y la pantalla tiene que poder decir «este edificio no tiene nada
    valorado», que no es lo mismo que no tener hallazgos."""
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H06",
        concepto="NORMATIVA",
        importe="1000.00",
    )
    assert resumen(cliente, cab, proyecto, "concept", asset_id=otro_activo) == []


def test_un_activo_de_otro_encargo_no_trae_nada(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    activo: str,
    motor_admin: Engine,
    datos_base: Any,
    tipologia: str,
) -> None:
    """`[REC]` **Solo filtra**, como en la matriz de riesgos: no es un 404.

    Es la convención de la casa para los filtros de lectura, y aquí además el
    desplegable de la pantalla se construye con los activos del propio encargo,
    así que un identificador ajeno solo llega escribiendo la URL a mano.
    """
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H06",
        concepto="NORMATIVA",
        importe="1000.00",
    )
    with motor_admin.begin() as conn:
        otro = conn.execute(
            text(
                "INSERT INTO project (organization_id, client_id, internal_code, name) "
                "VALUES (:o, :c, :cod, 'Otro encargo') RETURNING id"
            ),
            {
                "o": str(datos_base["org_a"]),
                "c": str(datos_base["cliente_a"]),
                "cod": f"AJ-{uuid.uuid4().hex[:6]}",
            },
        ).scalar_one()
        ajeno = conn.execute(
            text(
                "INSERT INTO asset (organization_id, project_id, typology_id, name) "
                "VALUES (:o, :p, :t, 'Nave ajena') RETURNING id"
            ),
            {"o": str(datos_base["org_a"]), "p": str(otro), "t": tipologia},
        ).scalar_one()

    assert resumen(cliente, cab, proyecto, "concept", asset_id=str(ajeno)) == []


def test_los_tres_cortes_filtrados_cuadran_entre_si(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, otro_activo: str
) -> None:
    """`[REQ]` **Lo que hace usable el filtro en toda la pantalla.**

    Con el filtro puesto, concepto, horizonte y capítulo se leen uno debajo del
    otro. Si no sumaran lo mismo, el descuadre lo encontraría el cliente con la
    calculadora delante —que es exactamente como se descubrió que `by-horizon`
    contaba los hallazgos borrados—.
    """
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H06",
        concepto="NORMATIVA",
        importe="12345.67",
        horizonte="CORTO",
    )
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H02",
        concepto=None,
        importe="8000.00",
        horizonte="LARGO",
    )
    # Ruido en el otro activo: si el filtro no llegara a alguno de los tres
    # cortes, ese corte saldría más grande que los demás.
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        otro_activo,
        codigo_capex="HC.H03",
        concepto="MEJORA",
        importe="99999.00",
        horizonte="MEDIO",
    )

    totales = {
        corte: sum(
            (Decimal(f["amount"]) for f in resumen(cliente, cab, proyecto, corte, asset_id=activo)),
            Decimal("0"),
        )
        for corte in ("concept", "horizon", "chapter")
    }

    assert len(set(totales.values())) == 1, totales
    assert totales["concept"] == Decimal("20345.67")


def test_el_horizonte_filtrado_conserva_los_cinco_plazos(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, otro_activo: str
) -> None:
    """Un plazo que desaparece de la lista se confunde con uno que no toca."""
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        activo,
        codigo_capex="HC.H06",
        concepto="NORMATIVA",
        importe="1000.00",
        horizonte="CORTO",
    )
    crear_hallazgo(
        cliente,
        cab,
        proyecto,
        otro_activo,
        codigo_capex="HC.H03",
        concepto="MEJORA",
        importe="500.00",
        horizonte="LARGO",
    )

    filas = resumen(cliente, cab, proyecto, "horizon", asset_id=activo)

    assert len(filas) == 5, "los cinco plazos, con ceros"
    corto = next(f for f in filas if f["time_horizon_code"] == "CORTO")
    largo = next(f for f in filas if f["time_horizon_code"] == "LARGO")
    assert Decimal(corto["amount"]) == Decimal("1000.00")
    assert Decimal(largo["amount"]) == Decimal("0"), "el del otro activo no cuenta"


def test_un_hallazgo_recurrente_cuenta_una_vez_en_su_activo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` P-44 · Una actuación recurrente tiene varias líneas y **un solo
    edificio**. El activo está en el hallazgo, no en la línea: filtrando por la
    línea, una actuación a dos plazos se contaría en dos sitios o en ninguno."""
    codigos = catalogo(cliente, cab, "capex-codes")
    zonas = catalogo(cliente, cab, "zones")
    conceptos = catalogo(cliente, cab, "capex-concepts")
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/findings",
        headers=cab("consultor_a"),
        json={
            "asset_id": activo,
            "capex_code_id": next(c["id"] for c in codigos if c["code"] == "HC.H06"),
            "zone_id": next(z for z in zonas if z["code"] == "GENERAL")["id"],
            "capex_concept_id": next(c["id"] for c in conceptos if c["code"] == "MANTENIMIENTO"),
            "title": "Revisión recurrente",
            "description": "",
            "capex_lines": [
                {"time_horizon_code": "CORTO", "amount": "1000.00"},
                {"time_horizon_code": "LARGO", "amount": "2000.00"},
            ],
        },
    )
    assert r.status_code == 201, r.text

    filas = resumen(cliente, cab, proyecto, "concept", asset_id=activo)

    assert len(filas) == 1
    assert filas[0]["findings"] == 1, "un hallazgo, aunque tenga dos líneas"
    assert filas[0]["lines"] == 2
    assert Decimal(filas[0]["amount"]) == Decimal("3000.00")

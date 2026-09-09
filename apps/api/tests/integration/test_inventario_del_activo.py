"""El inventario del activo `[REQ]` §3.2 d.

Tres piezas que el cliente pidió juntas y que solo se sostienen contra
PostgreSQL de verdad:

* **el descriptivo de cada objeto de Hard Cost**, traído de la documentación,
  editable, y con la casilla que lo da por validado;
* **la casilla «pasa a CAPEX»** del inventario de equipo y la generación en
  bloque de actuaciones que produce;
* **la fotografía atada al equipo** que retrata.

Lo que se comprueba de las tres es lo mismo: que **no se pisa trabajo hecho**.
Traer los descriptivos otra vez, regenerar el CAPEX de los equipos y volver a
guardar la rejilla son gestos normales, y que cualquiera de ellos borrara lo que
una persona escribió o firmó sería indefendible.
"""

from __future__ import annotations

import io
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.unit.test_imagenes import imagen

pytestmark = pytest.mark.db

RUTA = "/api/v1"


@pytest.fixture(scope="module")
def catalogo(motor_admin: Engine) -> dict[str, Any]:
    """Códigos reales del catálogo del cliente, no inventados."""
    with motor_admin.begin() as conn:
        tipologia = conn.execute(
            text("SELECT id FROM asset_typology WHERE code = 'INDUSTRIAL'")
        ).scalar_one()
        capitulos = {
            code: str(id_)
            for code, id_ in conn.execute(
                text(
                    "SELECT code, id FROM capex_code WHERE level = 2 "
                    "AND code IN ('HC.H02', 'HC.H08', 'HC.H09')"
                )
            ).all()
        }
        objetos = {
            code: str(id_)
            for code, id_ in conn.execute(
                text(
                    "SELECT code, id FROM capex_code WHERE level = 3 "
                    "AND code IN ('HC.H08.01', 'HC.H02.01')"
                )
            ).all()
        }
        # Un soft cost de nivel 3 no existe —los tramos SC no tienen objetos—,
        # así que el caso «no es nivel 3» se prueba con un capítulo.
    return {"tipologia": str(tipologia), "capitulos": capitulos, "objetos": objetos}


@pytest.fixture
def proyecto(datos_base: dict[str, uuid.UUID]) -> str:
    return str(datos_base["proyecto_a"])


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, catalogo: dict[str, Any]) -> str:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": f"Nave {uuid.uuid4().hex[:6]}", "typology_id": catalogo["tipologia"]},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def memoria_con_objetos(catalogo: dict[str, Any], *, simulada: bool = False) -> dict[str, Any]:
    """Una memoria con lo que importa aquí.

    Dos objetos codificados a nivel 3 —uno de ellos repetido en dos categorías,
    para ver que se juntan en un solo descriptivo— y uno sin código.
    """
    return {
        "origen": "MANUAL",
        "es_simulada": simulada,
        "categorias": [
            {
                "capex_code_id": catalogo["capitulos"]["HC.H08"],
                "objetos": [
                    {
                        "capex_code_id": catalogo["objetos"]["HC.H08.01"],
                        "nombre": "Enfriadora de la cubierta",
                        "cantidad": "2",
                        "unidad": "ud",
                        "notes": "Refrigerante R-410A.",
                    },
                    {"nombre": "Climatizadora de oficinas"},
                ],
            },
            {
                "capex_code_id": catalogo["capitulos"]["HC.H02"],
                "objetos": [
                    {
                        "capex_code_id": catalogo["objetos"]["HC.H02.01"],
                        "nombre": "Lámina impermeabilizante",
                    }
                ],
            },
        ],
    }


def con_memoria(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any], **kw: Any
) -> None:
    r = cliente.put(
        f"{RUTA}/assets/{activo}/memoria",
        headers=cab("consultor_a"),
        json=memoria_con_objetos(catalogo, **kw),
    )
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────────────────────
#  El descriptivo traído de la documentación
# ─────────────────────────────────────────────────────────────────────────────


def test_trae_un_descriptivo_por_objeto_de_hard_cost(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    con_memoria(cliente, cab, activo, catalogo)

    r = cliente.post(
        f"{RUTA}/assets/{activo}/descriptivos/desde-documentacion", headers=cab("consultor_a")
    )

    assert r.status_code == 201, r.text
    assert r.json()["creados"] == 2, "los dos objetos codificados a nivel 3"
    filas = cliente.get(f"{RUTA}/assets/{activo}/descriptivos", headers=cab("consultor_a")).json()
    assert [f["capex_code"] for f in filas] == ["HC.H02.01", "HC.H08.01"]
    enfriadora = filas[1]
    # `[REQ]` El texto es lo que dice la memoria de ese objeto: sus palabras, su
    # cantidad y sus notas. «Producción de climatización» ya está al lado.
    assert enfriadora["texto"] == "Enfriadora de la cubierta (2 ud) — Refrigerante R-410A."
    assert enfriadora["capex_name"]
    assert enfriadora["chapter_code"] == "HC.H08"


def test_nace_pendiente_de_validar(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """`[REQ]` «que indique que está pendiente de validar por el Gestor Técnico»."""
    con_memoria(cliente, cab, activo, catalogo)
    cliente.post(
        f"{RUTA}/assets/{activo}/descriptivos/desde-documentacion", headers=cab("consultor_a")
    )

    filas = cliente.get(f"{RUTA}/assets/{activo}/descriptivos", headers=cab("consultor_a")).json()
    assert all(f["validado"] is False for f in filas)
    assert all(f["validado_at"] is None and f["validado_por"] is None for f in filas)


def test_el_objeto_sin_codigo_no_inventa_un_descriptivo_y_lo_avisa(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """Un descriptivo cuelga de un objeto del árbol. Sin código no hay de qué
    colgarlo, y colgarlo del capítulo sería decir que la climatizadora *es* el
    capítulo entero."""
    con_memoria(cliente, cab, activo, catalogo)

    r = cliente.post(
        f"{RUTA}/assets/{activo}/descriptivos/desde-documentacion", headers=cab("consultor_a")
    )

    assert any("no están codificados" in a for a in r.json()["avisos"])


def test_una_memoria_simulada_marca_sus_descriptivos_y_lo_dice(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """`[LIM]` Un texto de mentira que pase por bueno es peor que no tener texto."""
    con_memoria(cliente, cab, activo, catalogo, simulada=True)

    r = cliente.post(
        f"{RUTA}/assets/{activo}/descriptivos/desde-documentacion", headers=cab("consultor_a")
    )

    assert any("SIMULADA" in a for a in r.json()["avisos"])
    filas = cliente.get(f"{RUTA}/assets/{activo}/descriptivos", headers=cab("consultor_a")).json()
    assert all(f["es_simulada"] for f in filas)


def test_sin_memoria_no_se_inventan_descriptivos(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """`[REQ]` «No inventes información.» Sin documento leído no hay descriptivo
    que traer, y devolver una rejilla vacía de filas creadas sería peor: parece
    que se ha mirado."""
    r = cliente.post(
        f"{RUTA}/assets/{activo}/descriptivos/desde-documentacion", headers=cab("consultor_a")
    )
    assert r.status_code == 409
    assert "memoria técnica" in r.json()["detail"]


def test_traerlos_dos_veces_no_duplica_ni_pisa_lo_escrito(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """`[REQ]` Ampliar la memoria y volver a traer es lo normal."""
    con_memoria(cliente, cab, activo, catalogo)
    cliente.post(
        f"{RUTA}/assets/{activo}/descriptivos/desde-documentacion", headers=cab("consultor_a")
    )
    filas = cliente.get(f"{RUTA}/assets/{activo}/descriptivos", headers=cab("consultor_a")).json()
    corregida = next(f for f in filas if f["capex_code"] == "HC.H08.01")
    cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={
            "lineas": [
                {
                    "capex_code_id": corregida["capex_code_id"],
                    "texto": "Dos enfriadoras aire-agua en cubierta, de 2004, con el "
                    "compresor de la nº2 sustituido.",
                }
            ]
        },
    )

    segunda = cliente.post(
        f"{RUTA}/assets/{activo}/descriptivos/desde-documentacion", headers=cab("consultor_a")
    )

    assert segunda.status_code == 201
    assert segunda.json()["creados"] == 0
    assert segunda.json()["respetados"] == 2, "las dos tienen ya texto de alguien o del documento"
    filas = cliente.get(f"{RUTA}/assets/{activo}/descriptivos", headers=cab("consultor_a")).json()
    assert len(filas) == 2, "no ha duplicado"
    de_nuevo = next(f for f in filas if f["capex_code"] == "HC.H08.01")
    assert "compresor de la nº2" in de_nuevo["texto"], "no se ha pisado"


def test_completa_la_fila_que_alguien_abrio_y_dejo_en_blanco(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """Una fila vacía no es trabajo hecho, es un hueco. Respetarla dejaría al
    gestor tecleando a mano lo que el documento ya dice."""
    con_memoria(cliente, cab, activo, catalogo)
    cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={"lineas": [{"capex_code_id": catalogo["objetos"]["HC.H08.01"], "texto": ""}]},
    )

    r = cliente.post(
        f"{RUTA}/assets/{activo}/descriptivos/desde-documentacion", headers=cab("consultor_a")
    )

    assert r.json()["creados"] == 1
    assert r.json()["completados"] == 1
    filas = cliente.get(f"{RUTA}/assets/{activo}/descriptivos", headers=cab("consultor_a")).json()
    completada = next(f for f in filas if f["capex_code"] == "HC.H08.01")
    assert completada["texto"].startswith("Enfriadora de la cubierta")


def test_no_pisa_un_descriptivo_ya_validado(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    con_memoria(cliente, cab, activo, catalogo)
    cliente.post(
        f"{RUTA}/assets/{activo}/descriptivos/desde-documentacion", headers=cab("consultor_a")
    )
    filas = cliente.get(f"{RUTA}/assets/{activo}/descriptivos", headers=cab("consultor_a")).json()
    validada = filas[0]
    cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={
            "lineas": [
                {
                    "capex_code_id": validada["capex_code_id"],
                    "texto": "Texto revisado en obra.",
                    "validado": True,
                }
            ]
        },
    )

    segunda = cliente.post(
        f"{RUTA}/assets/{activo}/descriptivos/desde-documentacion", headers=cab("consultor_a")
    )

    assert segunda.json()["respetados"] >= 1
    filas = cliente.get(f"{RUTA}/assets/{activo}/descriptivos", headers=cab("consultor_a")).json()
    otra_vez = next(f for f in filas if f["id"] == validada["id"])
    assert otra_vez["texto"] == "Texto revisado en obra."
    assert otra_vez["validado"] is True


def test_los_objetos_repetidos_se_juntan_en_un_solo_descriptivo(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """La memoria puede enumerar el mismo objeto en dos categorías. Quedarse con
    una de las dos frases perdería la mitad de lo que dice el documento."""
    memoria = memoria_con_objetos(catalogo)
    memoria["categorias"][1]["objetos"].append(
        {
            "capex_code_id": catalogo["objetos"]["HC.H08.01"],
            "nombre": "Enfriadora de reserva",
        }
    )
    cliente.put(f"{RUTA}/assets/{activo}/memoria", headers=cab("consultor_a"), json=memoria)

    cliente.post(
        f"{RUTA}/assets/{activo}/descriptivos/desde-documentacion", headers=cab("consultor_a")
    )

    filas = cliente.get(f"{RUTA}/assets/{activo}/descriptivos", headers=cab("consultor_a")).json()
    enfriadora = next(f for f in filas if f["capex_code"] == "HC.H08.01")
    assert "Enfriadora de la cubierta" in enfriadora["texto"]
    assert "Enfriadora de reserva" in enfriadora["texto"]


# ─────────────────────────────────────────────────────────────────────────────
#  La rejilla editable y su casilla
# ─────────────────────────────────────────────────────────────────────────────


def test_se_edita_el_texto_de_una_fila_que_no_existia(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """`[REQ]` «que sea un cuadro editable». No hace falta haber traído nada: el
    gestor puede describir un objeto que la documentación no menciona."""
    r = cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={
            "lineas": [
                {
                    "capex_code_id": catalogo["objetos"]["HC.H02.01"],
                    "texto": "Cubierta deck con lámina de PVC.",
                }
            ]
        },
    )

    assert r.status_code == 200, r.text
    fila = next(f for f in r.json() if f["capex_code"] == "HC.H02.01")
    assert fila["texto"] == "Cubierta deck con lámina de PVC."
    assert fila["validado"] is False
    assert fila["document_id"] is None, "no viene de ningún documento y no lo finge"


def test_la_casilla_firma_quien_valido_y_cuando(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any], datos_base: Any
) -> None:
    """`[REQ]` «una casilla de check para marcar como validado». La pantalla dice
    sí o no; la base guarda quién y cuándo, que es lo que hace que valga."""
    r = cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={
            "lineas": [
                {
                    "capex_code_id": catalogo["objetos"]["HC.H02.01"],
                    "texto": "Cubierta deck con lámina de PVC.",
                    "validado": True,
                }
            ]
        },
    )

    fila = r.json()[0]
    assert fila["validado"] is True
    assert fila["validado_at"] is not None
    assert fila["validado_por"] == str(datos_base["consultor_a"])
    assert fila["validado_por_nombre"]


def test_volver_a_guardar_el_texto_no_mueve_la_fecha_de_validacion(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """Guardar otra vez no es volver a validar. Mover la fecha borraría cuándo
    se firmó de verdad, que es justo lo que se pregunta seis meses después."""
    codigo = catalogo["objetos"]["HC.H02.01"]
    primera = cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={"lineas": [{"capex_code_id": codigo, "texto": "Lámina de PVC.", "validado": True}]},
    ).json()[0]

    segunda = cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={
            "lineas": [
                {"capex_code_id": codigo, "texto": "Lámina de PVC de 1,5 mm.", "validado": True}
            ]
        },
    ).json()[0]

    assert segunda["texto"] == "Lámina de PVC de 1,5 mm."
    assert segunda["validado_at"] == primera["validado_at"]


def test_desvalidar_borra_el_testigo(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """Dejar quién validó en una fila que ya no está validada es guardar la
    firma de algo que no está firmado."""
    codigo = catalogo["objetos"]["HC.H02.01"]
    cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={"lineas": [{"capex_code_id": codigo, "texto": "Lámina de PVC.", "validado": True}]},
    )

    r = cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={"lineas": [{"capex_code_id": codigo, "texto": "Lámina de PVC.", "validado": False}]},
    )

    fila = r.json()[0]
    assert fila["validado"] is False
    assert fila["validado_at"] is None
    assert fila["validado_por"] is None


def test_no_se_valida_un_descriptivo_vacio(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """Sería firmar una casilla en blanco. Y el mensaje lo explica: un 23514 de
    PostgreSQL no cuenta que lo que falta es escribir el texto."""
    r = cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={
            "lineas": [
                {
                    "capex_code_id": catalogo["objetos"]["HC.H02.01"],
                    "texto": "   ",
                    "validado": True,
                }
            ]
        },
    )

    assert r.status_code == 422
    assert "vacío" in r.json()["detail"]


def test_un_capitulo_no_lleva_descriptivo(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    """El descriptivo describe un objeto. Admitir el capítulo produciría una
    rejilla con dos niveles mezclados y un texto que no se sabe de qué habla."""
    r = cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={"lineas": [{"capex_code_id": catalogo["capitulos"]["HC.H02"], "texto": "Cubierta."}]},
    )

    assert r.status_code == 422
    assert "nivel 3" in r.json()["detail"] or "nivel 2" in r.json()["detail"]


def test_un_codigo_que_no_existe_se_rechaza(cliente: TestClient, cab: Any, activo: str) -> None:
    r = cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={"lineas": [{"capex_code_id": str(uuid.uuid4()), "texto": "Algo."}]},
    )
    assert r.status_code == 422
    assert "no existe" in r.json()["detail"]


def test_otra_organizacion_no_ve_los_descriptivos(
    cliente: TestClient, cab: Any, activo: str, catalogo: dict[str, Any]
) -> None:
    cliente.put(
        f"{RUTA}/assets/{activo}/descriptivos",
        headers=cab("consultor_a"),
        json={"lineas": [{"capex_code_id": catalogo["objetos"]["HC.H02.01"], "texto": "Secreto."}]},
    )
    r = cliente.get(f"{RUTA}/assets/{activo}/descriptivos", headers=cab("admin_b"))
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
#  «Pasa a CAPEX» desde el inventario de equipo
# ─────────────────────────────────────────────────────────────────────────────


def sistema(cliente: TestClient, cab: Any, code: str) -> dict[str, Any]:
    sistemas = cliente.get(f"{RUTA}/catalogs/technical-systems", headers=cab("consultor_a")).json()
    return next(s for s in sistemas if s["code"] == code)


def equipo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, **campos: Any
) -> dict[str, Any]:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/equipment",
        headers=cab("consultor_a"),
        json={"asset_id": activo, "equipment_type": "Enfriadora", **campos},
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def test_la_casilla_pasa_a_capex_se_guarda_y_por_defecto_esta_quitada(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """Marcar no crea nada: el gestor recorre la visita marcando, y el CAPEX se
    genera después de una vez."""
    por_defecto = equipo(cliente, cab, proyecto, activo, tag="CL-00")
    assert por_defecto["pasa_a_capex"] is False

    marcado = equipo(cliente, cab, proyecto, activo, tag="CL-01", pasa_a_capex=True)
    assert marcado["pasa_a_capex"] is True

    r = cliente.patch(
        f"{RUTA}/equipment/{por_defecto['id']}",
        headers=cab("consultor_a"),
        json={"pasa_a_capex": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["pasa_a_capex"] is True


def test_genera_una_actuacion_por_equipo_marcado(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    clima = sistema(cliente, cab, "CLIMA")
    equipo(
        cliente,
        cab,
        proyecto,
        activo,
        tag="CL-01",
        manufacturer="Fabricante Ficticio",
        model="XR-300",
        technical_system_id=clima["id"],
        pasa_a_capex=True,
    )
    equipo(cliente, cab, proyecto, activo, tag="CL-02", technical_system_id=clima["id"])

    r = cliente.post(f"{RUTA}/assets/{activo}/equipment/generar-capex", headers=cab("consultor_a"))

    assert r.status_code == 201, r.text
    assert r.json() == {"creadas": 1, "omitidas": 0, "marcados": 1, "avisos": []}
    hallazgos = cliente.get(
        f"{RUTA}/projects/{proyecto}/findings?asset_id={activo}", headers=cab("consultor_a")
    ).json()
    titulos = [h["title"] for h in hallazgos]
    assert titulos == [
        "Sustitución o intervención: CL-01 · Enfriadora (Fabricante Ficticio XR-300)"
    ]
    assert hallazgos[0]["status"] == "BORRADOR"


def test_el_capitulo_sale_del_sistema_tecnico(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, catalogo: dict[str, Any]
) -> None:
    clima = sistema(cliente, cab, "CLIMA")
    assert clima["capex_chapter"] == "H08", "la pista del catálogo, no una inventada"
    equipo(
        cliente,
        cab,
        proyecto,
        activo,
        tag="CL-01",
        technical_system_id=clima["id"],
        pasa_a_capex=True,
    )

    cliente.post(f"{RUTA}/assets/{activo}/equipment/generar-capex", headers=cab("consultor_a"))

    hallazgos = cliente.get(
        f"{RUTA}/projects/{proyecto}/findings?asset_id={activo}", headers=cab("consultor_a")
    ).json()
    assert hallazgos[0]["capex_code_id"] == catalogo["capitulos"]["HC.H08"]


def test_el_sistema_que_apunta_a_dos_capitulos_no_se_codifica_a_ciegas(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[LIM]` «Protección contra incendios» es `H06 + H10`. Elegir uno sería
    codificar mal una actuación, y eso no se ve hasta que alguien suma el
    capítulo equivocado."""
    pci = sistema(cliente, cab, "PCI")
    equipo(
        cliente,
        cab,
        proyecto,
        activo,
        tag="BIE-01",
        equipment_type="BIE",
        technical_system_id=pci["id"],
        pasa_a_capex=True,
    )

    r = cliente.post(f"{RUTA}/assets/{activo}/equipment/generar-capex", headers=cab("consultor_a"))

    assert r.json()["creadas"] == 0
    assert r.json()["marcados"] == 1
    assert any("BIE-01" in a for a in r.json()["avisos"])
    hallazgos = cliente.get(
        f"{RUTA}/projects/{proyecto}/findings?asset_id={activo}", headers=cab("consultor_a")
    ).json()
    assert hallazgos == []


def test_un_equipo_sin_sistema_tecnico_tambien_avisa(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    equipo(cliente, cab, proyecto, activo, tag="XX-01", pasa_a_capex=True)

    r = cliente.post(f"{RUTA}/assets/{activo}/equipment/generar-capex", headers=cab("consultor_a"))

    assert r.json()["creadas"] == 0
    assert any("sin sistema" in a for a in r.json()["avisos"])


def test_regenerar_no_duplica_ni_pisa_lo_valorado(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    clima = sistema(cliente, cab, "CLIMA")
    equipo(
        cliente,
        cab,
        proyecto,
        activo,
        tag="CL-01",
        technical_system_id=clima["id"],
        pasa_a_capex=True,
    )
    cliente.post(f"{RUTA}/assets/{activo}/equipment/generar-capex", headers=cab("consultor_a"))
    hallazgos = cliente.get(
        f"{RUTA}/projects/{proyecto}/findings?asset_id={activo}", headers=cab("consultor_a")
    ).json()
    puesto = cliente.post(
        f"{RUTA}/findings/{hallazgos[0]['id']}/capex-items",
        headers=cab("consultor_a"),
        json={"time_horizon_code": "CORTO", "amount": "48500.00"},
    )
    assert puesto.status_code == 201, puesto.text

    # Se marca un segundo equipo y se vuelve a generar.
    equipo(
        cliente,
        cab,
        proyecto,
        activo,
        tag="CL-02",
        technical_system_id=clima["id"],
        pasa_a_capex=True,
    )
    segunda = cliente.post(
        f"{RUTA}/assets/{activo}/equipment/generar-capex", headers=cab("consultor_a")
    )

    assert segunda.json()["creadas"] == 1, "solo el nuevo"
    assert segunda.json()["omitidas"] == 1
    hallazgos = cliente.get(
        f"{RUTA}/projects/{proyecto}/findings?asset_id={activo}", headers=cab("consultor_a")
    ).json()
    assert len(hallazgos) == 2
    valorado = next(h for h in hallazgos if "CL-01" in h["title"])
    assert valorado["total_amount"] is not None


def test_sin_ningun_equipo_marcado_no_genera_nada(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    equipo(cliente, cab, proyecto, activo, tag="CL-01")

    r = cliente.post(f"{RUTA}/assets/{activo}/equipment/generar-capex", headers=cab("consultor_a"))

    assert r.status_code == 201
    assert r.json() == {"creadas": 0, "omitidas": 0, "marcados": 0, "avisos": []}


# ─────────────────────────────────────────────────────────────────────────────
#  La fotografía atada al equipo
# ─────────────────────────────────────────────────────────────────────────────


def sube_foto(cliente: TestClient, cab: Any, proyecto: str, activo: str) -> dict[str, Any]:
    import random

    datos = imagen(color=(random.randrange(256), random.randrange(256), 90))
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/photos",
        headers=cab("consultor_a"),
        files={"file": ("IMG_0001.jpg", io.BytesIO(datos), "image/jpeg")},
        data={"asset_id": activo},
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def test_una_foto_se_ata_al_equipo_que_retrata(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` §3.2 d · Es lo que justifica seis meses después por qué se propone
    sustituir esa máquina y no otra."""
    maquina = equipo(cliente, cab, proyecto, activo, tag="CL-01")
    foto = sube_foto(cliente, cab, proyecto, activo)
    assert foto["equipment_id"] is None

    r = cliente.patch(
        f"{RUTA}/photos/{foto['id']}",
        headers=cab("consultor_a"),
        json={"equipment_id": maquina["id"]},
    )

    assert r.status_code == 200, r.text
    assert r.json()["equipment_id"] == maquina["id"]


def test_se_atan_varias_fotos_del_mismo_equipo_de_una_vez(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """Las cinco fotos que se hicieron de la misma enfriadora, en un gesto."""
    maquina = equipo(cliente, cab, proyecto, activo, tag="CL-01")
    fotos = [sube_foto(cliente, cab, proyecto, activo) for _ in range(3)]

    r = cliente.post(
        f"{RUTA}/photos/bulk-update",
        headers=cab("consultor_a"),
        json={"photo_ids": [f["id"] for f in fotos], "equipment_id": maquina["id"]},
    )

    assert r.status_code == 200, r.text
    assert {f["equipment_id"] for f in r.json()} == {maquina["id"]}


def test_borrar_el_equipo_no_se_lleva_la_foto(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, motor_admin: Engine
) -> None:
    """La fotografía es la evidencia de la visita y vale por sí sola. El vínculo
    es una clasificación, no la razón de existir de la foto."""
    maquina = equipo(cliente, cab, proyecto, activo, tag="CL-01")
    foto = sube_foto(cliente, cab, proyecto, activo)
    cliente.patch(
        f"{RUTA}/photos/{foto['id']}",
        headers=cab("consultor_a"),
        json={"equipment_id": maquina["id"]},
    )

    # El borrado de la API es lógico; el `ON DELETE SET NULL` se prueba con el
    # borrado físico, que es lo único que lo dispara.
    with motor_admin.begin() as conn:
        conn.execute(text("DELETE FROM equipment WHERE id = :i"), {"i": maquina["id"]})

    r = cliente.get(f"{RUTA}/photos/{foto['id']}", headers=cab("consultor_a"))
    assert r.status_code == 200
    assert r.json()["equipment_id"] is None

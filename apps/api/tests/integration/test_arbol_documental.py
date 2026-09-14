"""El árbol documental del activo `[REQ]` §3.2 b.

Los 73 nodos de la hoja v2 del cliente, de los que 60 son casillas. Lo que se
comprueba aquí es lo que distingue este árbol de una lista de tareas cualquiera:

* **una casilla sin tocar no tiene fila**, y eso es un estado válido —pendiente
  de pedir— y no un dato que falte;
* **un nodo que agrupa no lleva estado**, porque marcarlo no diría nada de lo
  que cuelga de él;
* **`NO_DISPONIBLE` exige motivo**, que es lo que acaba escrito en las
  limitaciones del informe;
* **un documento adjunto se clasifica solo** por el código del nodo.
"""

from __future__ import annotations

import io
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.db

RUTA = "/api/v1"

#: Un PDF mínimo válido. El mismo truco que en `test_documentos.py`: la subida
#: comprueba el MIME real del contenido, así que no vale un `b"hola"`.
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


@pytest.fixture(scope="module")
def tipologia(motor_admin: Engine) -> str:
    with motor_admin.begin() as conn:
        fila = conn.execute(text("SELECT id FROM asset_typology WHERE code = 'INDUSTRIAL'"))
        return str(fila.scalar_one())


@pytest.fixture
def proyecto(cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]) -> str:
    """Un proyecto **con la fase documental activada**.

    Las fases se eligen a la carta al dar de alta el proyecto, y el árbol vive
    en `SOLICITUD_DOCUMENTACION`: sin ella no hay dónde colgar las casillas, y
    la API lo dice con un `404` en vez de crear la fase por su cuenta.
    """
    r = cliente.post(
        f"{RUTA}/projects",
        headers=cab("admin_a"),
        json={
            "client_id": str(datos_base["cliente_a"]),
            "internal_code": f"ARB-{uuid.uuid4().hex[:6]}",
            "name": "Proyecto con árbol documental",
            "applicable_phases": [{"code": "SOLICITUD_DOCUMENTACION"}],
        },
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def test_sin_la_fase_documental_el_arbol_dice_que_falta(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID], tipologia: str
) -> None:
    """Y dice **qué hacer**: quien abre la pestaña de un activo no ha pedido una
    fase, así que «el proyecto no tiene SOLICITUD_DOCUMENTACION» sin más no le
    sirve de nada."""
    sin_fase = cliente.post(
        f"{RUTA}/projects",
        headers=cab("admin_a"),
        json={
            "client_id": str(datos_base["cliente_a"]),
            "internal_code": f"SIN-{uuid.uuid4().hex[:6]}",
            "name": "Proyecto sin fase documental",
            "applicable_phases": [{"code": "QA"}],
        },
    ).json()["id"]
    otro = cliente.post(
        f"{RUTA}/projects/{sin_fase}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave sin fase", "typology_id": tipologia},
    ).json()["id"]

    r = cliente.get(f"{RUTA}/assets/{otro}/doc-tree", headers=cab("consultor_a"))
    assert r.status_code == 404
    assert "Actívela" in r.json()["detail"]


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, tipologia: str) -> str:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": f"Nave {uuid.uuid4().hex[:6]}", "typology_id": tipologia},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def arbol(cliente: TestClient, cab: Any, activo: str) -> list[dict[str, Any]]:
    r = cliente.get(f"{RUTA}/assets/{activo}/doc-tree", headers=cab("consultor_a"))
    assert r.status_code == 200, r.text
    nodos: list[dict[str, Any]] = r.json()
    return nodos


def nodo(nodos: list[dict[str, Any]], code: str) -> dict[str, Any]:
    return next(n for n in nodos if n["code"] == code)


def fijar(cliente: TestClient, cab: Any, activo: str, code: str, **cuerpo: Any) -> Any:
    return cliente.put(
        f"{RUTA}/assets/{activo}/doc-tree/{code}", headers=cab("consultor_a"), json=cuerpo
    )


# ─────────────────────────────────────────────────────────────────────────────
#  La forma del árbol
# ─────────────────────────────────────────────────────────────────────────────


def test_el_arbol_llega_entero_y_sin_tocar(cliente: TestClient, cab: Any, activo: str) -> None:
    """Los 73 **siempre**, tenga o no algo cada casilla.

    Devolver solo las tocadas dejaría la pantalla enseñando lo que ya está
    hecho, que es justo lo que no hay que mirar.
    """
    nodos = arbol(cliente, cab, activo)
    assert len(nodos) == 73
    assert sum(1 for n in nodos if n["es_casilla"]) == 60
    # Ninguna fila creada por el mero hecho de abrir la pantalla.
    assert all(n["item_id"] is None and n["status"] is None for n in nodos)
    assert all(n["documentos"] == [] for n in nodos)


def test_el_orden_es_el_de_la_hoja_y_no_el_alfabetico(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """Por código, `S2.10` caería entre `S2.1` y `S2.2`."""
    codigos = [n["code"] for n in arbol(cliente, cab, activo)]
    assert codigos[0] == "S1"
    assert codigos.index("S2.9") < codigos.index("S2.10")


def test_una_casilla_puede_estar_en_cualquier_nivel(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """`S4` es de nivel 1 y no tiene hijos: es casilla. `S2.1` es de nivel 2 y
    también. Atar la casilla al nivel 3 habría dejado veinte nodos sin poder
    marcarse nunca."""
    nodos = arbol(cliente, cab, activo)
    assert nodo(nodos, "S4")["es_casilla"] is True
    assert nodo(nodos, "S2.1")["es_casilla"] is True
    assert nodo(nodos, "S1")["es_casilla"] is False
    assert nodo(nodos, "S1.1")["es_casilla"] is False


# ─────────────────────────────────────────────────────────────────────────────
#  Poner estado
# ─────────────────────────────────────────────────────────────────────────────


def test_la_fila_aparece_al_poner_el_primer_estado(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    r = fijar(cliente, cab, activo, "S1.1.1", status="SOLICITADA")
    assert r.status_code == 200, r.text
    assert r.json()["item_id"] is not None
    assert r.json()["status"] == "SOLICITADA"

    casilla = nodo(arbol(cliente, cab, activo), "S1.1.1")
    assert casilla["status"] == "SOLICITADA"
    # Y solo esa: las otras 59 siguen sin fila.
    assert sum(1 for n in arbol(cliente, cab, activo) if n["item_id"]) == 1


def test_volver_a_poner_estado_no_crea_una_segunda_casilla(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """Lo impone `doc_request_casilla_uniq`, pero el endpoint tiene que
    encontrarla y actualizarla en vez de chocar con el índice."""
    primera = fijar(cliente, cab, activo, "S2.1", status="SOLICITADA").json()
    segunda = fijar(cliente, cab, activo, "S2.1", status="RECIBIDA").json()
    assert primera["item_id"] == segunda["item_id"]
    assert segunda["status"] == "RECIBIDA"
    assert sum(1 for n in arbol(cliente, cab, activo) if n["item_id"]) == 1


def test_recibir_deja_fecha_sin_que_nadie_la_escriba(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    """Marcar «recibida» sin fecha dejaría el árbol sin saber cuándo llegó, y
    esa fecha es la que se contrasta con la del informe."""
    assert fijar(cliente, cab, activo, "S2.1", status="SOLICITADA").json()["received_at"] is None
    recibida = fijar(cliente, cab, activo, "S2.1", status="RECIBIDA").json()
    assert recibida["received_at"] is not None

    # Y no se mueve al volver a guardar: la fecha es cuándo llegó, no cuándo se
    # tocó la casilla por última vez.
    otra_vez = fijar(cliente, cab, activo, "S2.1", status="PARCIAL").json()
    assert otra_vez["received_at"] == recibida["received_at"]


def test_un_nodo_que_agrupa_no_lleva_estado(cliente: TestClient, cab: Any, activo: str) -> None:
    """Marcar `S1.1` como recibida cuando cuelgan cuatro licencias no dice nada
    de ninguna de las cuatro."""
    r = fijar(cliente, cab, activo, "S1.1", status="RECIBIDA")
    assert r.status_code == 422
    assert "agrupa" in r.json()["detail"]
    assert all(n["item_id"] is None for n in arbol(cliente, cab, activo))


def test_un_codigo_que_no_esta_en_el_arbol_es_404(
    cliente: TestClient, cab: Any, activo: str
) -> None:
    r = fijar(cliente, cab, activo, "S9.9.9", status="RECIBIDA")
    assert r.status_code == 404


def test_no_disponible_exige_motivo(cliente: TestClient, cab: Any, activo: str) -> None:
    """Es lo que se declara como limitación del informe. Sin él, la limitación
    se queda en «falta algo»."""
    r = fijar(cliente, cab, activo, "S2.11", status="NO_DISPONIBLE")
    assert r.status_code == 422
    assert "por qué" in r.json()["detail"]
    # Un motivo de espacios en blanco tampoco cuenta.
    blancos = fijar(cliente, cab, activo, "S2.11", status="NO_DISPONIBLE", unavailable_reason="   ")
    assert blancos.status_code == 422

    bien = fijar(
        cliente,
        cab,
        activo,
        "S2.11",
        status="NO_DISPONIBLE",
        unavailable_reason="Solo hay PDF escaneados de 2004.",
    )
    assert bien.status_code == 200
    assert bien.json()["limita_el_informe"] is True


def test_parcial_tambien_limita_el_informe(cliente: TestClient, cab: Any, activo: str) -> None:
    """`[REC]` Recibir tres de los ocho boletines eléctricos no es haberlos
    recibido, y el sitio donde eso se declara es el informe."""
    assert fijar(cliente, cab, activo, "S2.5", status="PARCIAL").json()["limita_el_informe"]
    assert not fijar(cliente, cab, activo, "S2.5", status="RECIBIDA").json()["limita_el_informe"]
    assert not fijar(cliente, cab, activo, "S2.5", status="NO_APLICA").json()["limita_el_informe"]


def test_un_estado_inventado_es_422_y_no_500(cliente: TestClient, cab: Any, activo: str) -> None:
    """La enumeración de Pydantic contesta antes de que el `CAST` llegue a
    PostgreSQL, así que quien llama ve la lista de valores válidos."""
    assert fijar(cliente, cab, activo, "S2.1", status="PENDIENTE").status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
#  Documentos colgando de la casilla
# ─────────────────────────────────────────────────────────────────────────────


def test_el_documento_adjunto_sale_en_su_casilla_y_se_clasifica_solo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REC]` §15.11 · El tipo sale del código del nodo. `S1.1.3` es una
    licencia de actividad, así que el documento es `LICENCIA_URBANISTICA` sin
    que nadie elija nada de un desplegable."""
    casilla = fijar(cliente, cab, activo, "S1.1.3", status="SOLICITADA").json()

    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/documents",
        headers=cab("consultor_a"),
        files={"file": ("licencia.pdf", io.BytesIO(PDF), "application/pdf")},
        data={"asset_id": activo, "doc_request_item_id": casilla["item_id"]},
    )
    assert r.status_code == 201, r.text
    assert r.json()["doc_type"] == "LICENCIA_URBANISTICA"

    despues = nodo(arbol(cliente, cab, activo), "S1.1.3")
    # `display_name` viene sin extensión: es el nombre que se enseña, y el
    # original se guarda aparte.
    assert [d["display_name"] for d in despues["documentos"]] == ["licencia"]
    # Recibir el documento adelanta la casilla sola: marcarlo a mano después se
    # olvida siempre.
    assert despues["status"] == "RECIBIDA"


def test_el_tipo_se_resuelve_por_segmentos_y_no_por_prefijo_de_texto(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`S2.1` es la memoria técnica y `S2.10` la legalización del gas propano.

    Con un `startswith` a pelo, el gas propano habría entrado como memoria
    técnica —y la memoria técnica es el único tipo al que la aplicación le
    ofrece extracción de datos, así que el fallo no se habría quedado en una
    etiqueta mal puesta—.
    """
    for code, esperado in (("S2.1", "MEMORIA_TECNICA"), ("S2.10", "LEGALIZACION")):
        casilla = fijar(cliente, cab, activo, code, status="SOLICITADA").json()
        r = cliente.post(
            f"{RUTA}/projects/{proyecto}/documents",
            headers=cab("consultor_a"),
            files={"file": (f"{code}.pdf", io.BytesIO(PDF + code.encode()), "application/pdf")},
            data={"asset_id": activo, "doc_request_item_id": casilla["item_id"]},
        )
        assert r.status_code == 201, r.text
        assert r.json()["doc_type"] == esperado, code


# ─────────────────────────────────────────────────────────────────────────────
#  Aislamiento
# ─────────────────────────────────────────────────────────────────────────────


def test_el_arbol_de_un_activo_no_ensena_el_del_vecino(
    cliente: TestClient, cab: Any, proyecto: str, tipologia: str, activo: str
) -> None:
    """Dos activos del mismo proyecto comparten fase documental: si el filtro
    por `asset_id` faltara, el segundo nacería con el árbol del primero ya
    resuelto."""
    otro = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": f"Nave {uuid.uuid4().hex[:6]}", "typology_id": tipologia},
    ).json()["id"]

    fijar(cliente, cab, activo, "S2.1", status="RECIBIDA")
    assert nodo(arbol(cliente, cab, activo), "S2.1")["status"] == "RECIBIDA"
    assert nodo(arbol(cliente, cab, str(otro)), "S2.1")["status"] is None

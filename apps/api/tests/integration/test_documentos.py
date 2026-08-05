"""Documentos `[REQ]` §15.11.

Dos cosas se prueban aquí y en ningún otro sitio: que **el rechazo de ficheros
peligrosos mira el contenido y no la extensión** —renombrar un `.exe` a `.pdf`
es lo primero que se intenta— y que el **versionado explícito** permite saber
cuál era el documento vigente en la fecha del informe.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tdd.evidence.documents import ContenidoRechazado, comprobar_contenido

pytestmark = pytest.mark.db

RUTA = "/api/v1"

PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"


def pdf_unico() -> bytes:
    """Cada llamada, un fichero distinto: el índice único por `sha256` es real."""
    return PDF + uuid.uuid4().hex.encode()


def ooxml(*, con_macro: bool = False) -> bytes:
    """Un contenedor OOXML real, con o sin proyecto VBA dentro."""
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f"<w:document>{uuid.uuid4().hex}</w:document>")
        if con_macro:
            z.writestr("word/vbaProject.bin", b"\x00\x01\x02")
    return salida.getvalue()


@pytest.fixture
def proyecto(cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]) -> str:
    r = cliente.post(
        f"{RUTA}/projects",
        headers=cab("admin_a"),
        json={
            "client_id": str(datos_base["cliente_a"]),
            "internal_code": f"DOC-{uuid.uuid4().hex[:6]}",
            "name": "Encargo con documentación",
            "applicable_phases": [{"code": "SOLICITUD_DOCUMENTACION"}, {"code": "QA"}],
        },
    )
    return str(r.json()["id"])


def subir(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    datos: bytes,
    *,
    nombre: str = "licencia.pdf",
    usuario: str = "consultor_a",
    **campos: Any,
) -> Any:
    return cliente.post(
        f"{RUTA}/projects/{proyecto}/documents",
        headers=cab(usuario),
        files={"file": (nombre, io.BytesIO(datos), "application/pdf")},
        data={k: str(v) for k, v in campos.items()},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Qué entra y qué no (función pura)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("datos", "que_es"),
    [
        (b"MZ\x90\x00 ejecutable", "ejecutable de Windows"),
        (b"\x7fELF\x02\x01\x01\x00", "ejecutable de Linux"),
        (b"#!/bin/sh\nrm -rf /", "script ejecutable"),
        (b"Rar!\x1a\x07\x00", "archivo comprimido"),
        (b"\x1f\x8b\x08\x00\x00\x00", "archivo comprimido"),
    ],
)
def test_el_contenido_manda_sobre_la_extension(datos: bytes, que_es: str) -> None:
    """`[REQ]` Renombrar un ejecutable a `.pdf` es lo primero que se intenta.
    Por eso se mira la firma binaria antes que el nombre."""
    with pytest.raises(ContenidoRechazado, match=que_es):
        comprobar_contenido(datos, extension="pdf")


def test_un_docm_disfrazado_de_docx_se_detecta() -> None:
    """El proyecto VBA sigue dentro del contenedor por mucho que cambie el
    nombre: buscarlo ahí es lo único que lo detecta."""
    with pytest.raises(ContenidoRechazado, match="macros"):
        comprobar_contenido(ooxml(con_macro=True), extension="docx")


def test_un_docx_limpio_pasa() -> None:
    comprobar_contenido(ooxml(), extension="docx")


def test_un_zip_suelto_no_pasa() -> None:
    """Un ZIP anidado puede ser una bomba de descompresión."""
    with pytest.raises(ContenidoRechazado, match="comprimido"):
        comprobar_contenido(ooxml(), extension="zip")


def test_una_extension_no_prevista_se_rechaza_diciendo_cuales_valen() -> None:
    with pytest.raises(ContenidoRechazado, match="pdf"):
        comprobar_contenido(PDF, extension="exe")


def test_un_pdf_normal_pasa() -> None:
    comprobar_contenido(PDF, extension="pdf")


# ─────────────────────────────────────────────────────────────────────────────
#  Subida
# ─────────────────────────────────────────────────────────────────────────────


def test_se_sube_un_documento(cliente: TestClient, cab: Any, proyecto: str) -> None:
    r = subir(cliente, cab, proyecto, pdf_unico(), doc_type="LICENCIA_URBANISTICA")
    assert r.status_code == 201, r.text
    assert r.json()["doc_type"] == "LICENCIA_URBANISTICA"
    assert r.json()["confidentiality"] == "INTERNO"
    assert r.json()["version_number"] == 1


def test_un_ejecutable_renombrado_se_rechaza_con_415(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    r = subir(cliente, cab, proyecto, b"MZ\x90\x00 esto es un exe", nombre="inofensivo.pdf")
    assert r.status_code == 415


def test_el_mismo_documento_dos_veces_se_rechaza_diciendo_cual_es(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    datos = pdf_unico()
    ya = subir(cliente, cab, proyecto, datos).json()
    r = subir(cliente, cab, proyecto, datos)
    assert r.status_code == 409
    assert ya["id"] in r.json()["detail"]


def test_la_extension_se_guarda_sin_punto(cliente: TestClient, cab: Any, proyecto: str) -> None:
    r = subir(cliente, cab, proyecto, pdf_unico())
    assert r.json()["file_extension"] == "pdf"


# ─────────────────────────────────────────────────────────────────────────────
#  Clasificación automática desde la fase
# ─────────────────────────────────────────────────────────────────────────────


def test_adjuntar_a_una_linea_del_checklist_clasifica_el_documento(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    """`[REC]` §15.11 · Elegir el tipo a mano cuando el sistema ya lo sabe es
    trabajo repetido y una fuente de incoherencias."""
    with motor_admin.begin() as conn:
        categoria = conn.execute(
            text("SELECT id FROM doc_request_category WHERE code = 'LICENCIAS'")
        ).scalar()
    if categoria is None:
        pytest.skip("el catálogo no trae la categoría LICENCIAS")

    linea = cliente.post(
        f"{RUTA}/projects/{proyecto}/doc-requests",
        headers=cab("consultor_a"),
        json={"category_id": str(categoria), "title": "Licencia de actividad"},
    ).json()

    r = subir(cliente, cab, proyecto, pdf_unico(), doc_request_item_id=linea["id"])
    assert r.status_code == 201
    assert r.json()["doc_type"] == "LICENCIA_URBANISTICA"


def test_recibir_el_documento_adelanta_la_linea_del_checklist(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    """Es la razón por la que existe esa línea, y marcarla a mano después se
    olvida siempre."""
    with motor_admin.begin() as conn:
        categoria = conn.execute(
            text("SELECT id FROM doc_request_category ORDER BY display_order LIMIT 1")
        ).scalar_one()

    linea = cliente.post(
        f"{RUTA}/projects/{proyecto}/doc-requests",
        headers=cab("consultor_a"),
        json={"category_id": str(categoria), "title": "Contrato de mantenimiento"},
    ).json()
    assert linea["status"] == "SOLICITADA"

    subir(cliente, cab, proyecto, pdf_unico(), doc_request_item_id=linea["id"])

    lineas = cliente.get(
        f"{RUTA}/projects/{proyecto}/doc-requests", headers=cab("consultor_a")
    ).json()
    actualizada = next(item for item in lineas if item["id"] == linea["id"])
    assert actualizada["status"] == "RECIBIDA"
    assert actualizada["received_at"] is not None


def test_un_documento_de_una_ronda_de_qa_se_clasifica_como_tal(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    ronda = cliente.post(
        f"{RUTA}/projects/{proyecto}/qa-rounds", headers=cab("consultor_a"), json={}
    ).json()
    r = subir(cliente, cab, proyecto, pdf_unico(), qa_round_id=ronda["id"])
    assert r.json()["doc_type"] == "QA"


# ─────────────────────────────────────────────────────────────────────────────
#  Versionado
# ─────────────────────────────────────────────────────────────────────────────


def test_una_version_nueva_sustituye_a_la_anterior(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    v1 = subir(cliente, cab, proyecto, pdf_unico(), nombre="plano-v1.pdf").json()
    v2 = subir(
        cliente, cab, proyecto, pdf_unico(), nombre="plano-v2.pdf", supersedes_document_id=v1["id"]
    ).json()
    assert v2["version_number"] == 2
    assert v2["supersedes_document_id"] == v1["id"]


def test_el_listado_devuelve_solo_la_vigente(cliente: TestClient, cab: Any, proyecto: str) -> None:
    """Un listado que mezcle las cinco versiones de un plano no ayuda a nadie."""
    v1 = subir(cliente, cab, proyecto, pdf_unico(), nombre="p1.pdf").json()
    v2 = subir(
        cliente, cab, proyecto, pdf_unico(), nombre="p2.pdf", supersedes_document_id=v1["id"]
    ).json()

    vigentes = cliente.get(
        f"{RUTA}/projects/{proyecto}/documents", headers=cab("consultor_a")
    ).json()
    ids = [d["id"] for d in vigentes]
    assert v2["id"] in ids
    assert v1["id"] not in ids


def test_el_historial_completo_se_pide_expresamente(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REC]` Para saber cuál era la vigente **en la fecha del informe**: sin
    esto, un informe firmado sobre la versión 2 parecería basarse en la 5."""
    v1 = subir(cliente, cab, proyecto, pdf_unico(), nombre="h1.pdf").json()
    v2 = subir(
        cliente, cab, proyecto, pdf_unico(), nombre="h2.pdf", supersedes_document_id=v1["id"]
    ).json()
    v3 = subir(
        cliente, cab, proyecto, pdf_unico(), nombre="h3.pdf", supersedes_document_id=v2["id"]
    ).json()

    historial = cliente.get(
        f"{RUTA}/documents/{v2['id']}/versions", headers=cab("consultor_a")
    ).json()
    assert [d["version_number"] for d in historial] == [1, 2, 3]
    assert {d["id"] for d in historial} == {v1["id"], v2["id"], v3["id"]}


def test_sustituir_a_un_documento_inexistente_se_rechaza(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    r = subir(cliente, cab, proyecto, pdf_unico(), supersedes_document_id=str(uuid.uuid4()))
    assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
#  Confidencialidad y descarga
# ─────────────────────────────────────────────────────────────────────────────


def test_la_descarga_devuelve_el_original_y_queda_auditada(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    datos = pdf_unico()
    doc = subir(cliente, cab, proyecto, datos).json()

    r = cliente.get(f"{RUTA}/documents/{doc['id']}/download", headers=cab("consultor_a"))
    assert r.status_code == 200
    assert r.content == datos

    with motor_admin.begin() as conn:
        acciones = (
            conn.execute(
                text("SELECT action FROM audit_log WHERE entity_id = :i"), {"i": doc["id"]}
            )
            .scalars()
            .all()
        )
    assert "DOCUMENT_DOWNLOADED" in acciones


def test_lo_restringido_no_lo_descarga_cualquiera(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`RESTRINGIDO` se reserva a lo que no debería salir del núcleo del
    equipo."""
    doc = subir(cliente, cab, proyecto, pdf_unico(), confidentiality="RESTRINGIDO").json()

    assert (
        cliente.get(
            f"{RUTA}/documents/{doc['id']}/download", headers=cab("consultor_a")
        ).status_code
        == 403
    )
    assert (
        cliente.get(f"{RUTA}/documents/{doc['id']}/download", headers=cab("admin_a")).status_code
        == 200
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Inmutabilidad y papelera
# ─────────────────────────────────────────────────────────────────────────────


def test_la_base_de_datos_rechaza_reapuntar_el_original(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    """Misma barrera que en las fotografías, probada saltándose la API."""
    doc = subir(cliente, cab, proyecto, pdf_unico()).json()
    with motor_admin.begin() as conn, pytest.raises(Exception, match="no se sobrescribe"):
        conn.execute(
            text("UPDATE document SET sha256 = :h WHERE id = :i"),
            {"h": "f" * 64, "i": doc["id"]},
        )


def test_renombrar_no_toca_el_binario(cliente: TestClient, cab: Any, proyecto: str) -> None:
    doc = subir(cliente, cab, proyecto, pdf_unico()).json()
    r = cliente.patch(
        f"{RUTA}/documents/{doc['id']}",
        headers=cab("consultor_a"),
        json={"display_name": "Licencia de actividad 2019"},
    )
    assert r.status_code == 200
    assert r.json()["sha256"] == doc["sha256"]
    assert r.json()["file_extension"] == "pdf"


def test_el_hash_no_es_escribible_por_la_api(cliente: TestClient, cab: Any, proyecto: str) -> None:
    doc = subir(cliente, cab, proyecto, pdf_unico()).json()
    r = cliente.patch(
        f"{RUTA}/documents/{doc['id']}", headers=cab("consultor_a"), json={"sha256": "0" * 64}
    )
    assert r.status_code == 422


def test_el_borrado_es_logico(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    doc = subir(cliente, cab, proyecto, pdf_unico()).json()
    assert (
        cliente.delete(f"{RUTA}/documents/{doc['id']}", headers=cab("consultor_a")).status_code
        == 204
    )
    with motor_admin.begin() as conn:
        estado = conn.execute(
            text("SELECT CAST(status AS text) FROM document WHERE id = :i"), {"i": doc["id"]}
        ).scalar_one()
    assert estado == "PAPELERA"


def test_otra_organizacion_no_ve_el_documento(cliente: TestClient, cab: Any, proyecto: str) -> None:
    doc = subir(cliente, cab, proyecto, pdf_unico()).json()
    assert cliente.get(f"{RUTA}/documents/{doc['id']}", headers=cab("admin_b")).status_code == 404

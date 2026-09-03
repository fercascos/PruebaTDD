"""`[REQ]` Del documento al apartado de limitaciones del informe.

La **tercera clase de limitación**. Las dos que ya había salen de lo que *no*
llegó: una línea de la checklist sin recibir, una pregunta sin respuesta. Ésta
es lo contrario: el documento llegó, la casilla está marcada, el expediente
parece completo, y el documento dice que no se puede confiar en él.

Lo que estas pruebas fijan:

* que un plan de autoprotección **se puede leer sin activo** —cubre un complejo
  entero, y sus reservas son del encargo—;
* que **nada llega al informe sin que una persona lo acepte**, y que el snapshot
  es el punto donde eso deja de poder corregirse;
* que las tres clases salen **distinguidas** por su origen;
* y que un plan de autoprotección nace **RESTRINGIDO**.
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

#: Un plan con las tres cosas que las reglas buscan: fecha fuera de plazo, una
#: declaración de no vigencia y una sección de salvedades.
#:
#: `[REQ]` Fabricado aquí. El documento contra el que se escribió el extractor
#: es confidencial y no está —ni estará— en el repositorio.
PLAN = """\
Plan de Autoprotección del complejo logístico
Fecha: 14/03/2016

Advertencia: este documento no sustituye al Plan de Autoprotección completo, a
sus planos ni a sus anexos.

Índice

1. Capítulo 1: identificación del titular

2. Alertas, vacíos e inconsistencias

1. Capítulo 1: identificación del titular

Recoge el nombre y la dirección del establecimiento, los usos, las licencias y
el titular de la actividad junto con sus responsables designados por escrito.

2. Alertas, vacíos e inconsistencias

"""
# Las dos salvedades, cada una en UNA sola línea del PDF: `reportlab` hace un
# párrafo por línea del fuente, así que partirlas aquí daría tres candidatas por
# viñeta en vez de una. Se concatenan para no pasar de cien columnas en el
# código.
PLAN += (
    "- El plan se redactó con las naves vacías. No refleja necesariamente actividades, "
    "mercancías, estanterías, cargas de fuego ni distribuciones actuales del establecimiento.\n"
    "\n"
    "- Los recorridos de evacuación se definieron suponiendo espacios diáfanos. Cualquier "
    "implantación interior puede alterar longitudes, salidas y capacidades de evacuación.\n"
)


def plan_pdf(texto: str = PLAN) -> bytes:
    from reportlab.lib.pagesizes import A4  # type: ignore[import-not-found]
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    cuerpo = getSampleStyleSheet()["BodyText"]
    doc.build([Paragraph(linea or "&nbsp;", cuerpo) for linea in texto.split("\n")])
    return buffer.getvalue()


@pytest.fixture
def proyecto(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo con plan de autoprotección') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"PAU-{uuid.uuid4().hex[:6]}",
                },
            ).scalar_one()
        )


def subir_plan(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    *,
    contenido: bytes | None = None,
    asset_id: str | None = None,
    confidentiality: str | None = None,
) -> dict[str, Any]:
    datos: dict[str, str] = {"doc_type": "PLAN_AUTOPROTECCION", "display_name": "plan.pdf"}
    if asset_id is not None:
        datos["asset_id"] = asset_id
    if confidentiality is not None:
        datos["confidentiality"] = confidentiality
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/documents",
        headers=cab("consultor_a"),
        files={"file": ("plan.pdf", contenido or plan_pdf(), "application/pdf")},
        data=datos,
    )
    assert r.status_code == 201, r.text
    return dict(r.json())


def extraer(cliente: TestClient, cab: Any, documento: str) -> dict[str, Any]:
    r = cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))
    assert r.status_code == 201, r.text
    return dict(r.json())


# ─────────────────────────────────────────────────────────────────────────────
#  Un plan de autoprotección no necesita activo
# ─────────────────────────────────────────────────────────────────────────────


def test_el_plan_se_lee_sin_activo_porque_cubre_el_complejo(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REQ]` Esto era un 409 y estaba mal.

    La comprobación de activo estaba al principio del endpoint, antes de leer.
    Con ella, el documento que más limitaciones aporta —un plan que cubre seis
    naves y no es de ninguna— era justo el que no se podía leer. El activo hace
    falta para los **campos**, no para extraer.
    """
    documento = subir_plan(cliente, cab, proyecto)
    assert documento["asset_id"] is None

    resultado = extraer(cliente, cab, documento["id"])

    assert resultado["limitaciones"] >= 3
    assert resultado["propuestas"] == 0, "un plan no propone superficies"
    assert resultado["es_simulada"] is False


def test_el_plan_se_publica_como_tipo_extraible(cliente: TestClient, cab: Any) -> None:
    r = cliente.get(f"{RUTA}/extraccion/tipos-soportados", headers=cab("consultor_a"))
    assert r.status_code == 200
    assert {"MEMORIA_TECNICA", "PLAN_AUTOPROTECCION"} <= set(r.json())


# ─────────────────────────────────────────────────────────────────────────────
#  Las tres reglas, punta a punta
# ─────────────────────────────────────────────────────────────────────────────


def test_las_limitaciones_llegan_con_su_motivo_y_su_procedencia(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    documento = subir_plan(cliente, cab, proyecto)
    extraer(cliente, cab, documento["id"])

    todas = cliente.get(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales", headers=cab("consultor_a")
    ).json()
    por_motivo = {lim["motivo"] for lim in todas}

    # Fecha de 2016: fuera del plazo de tres años del RD 393/2007.
    assert "CADUCADO" in por_motivo
    # «no sustituye al Plan completo».
    assert "NO_VIGENTE" in por_motivo
    # Las dos viñetas de la sección de alertas, literales.
    declaradas = [lim for lim in todas if lim["motivo"] == "DECLARADA"]
    assert len(declaradas) == 2
    assert any("naves vacías" in lim["texto"] for lim in declaradas)
    assert all(lim["seccion"] == "Alertas, vacíos e inconsistencias" for lim in declaradas)

    assert all(lim["estado"] == "PENDIENTE" for lim in todas)
    assert all(lim["document_id"] == documento["id"] for lim in todas)
    assert all(lim["documento"] == "plan" for lim in todas)


def test_la_fecha_caducada_trae_la_fecha_literal_como_evidencia(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Sin la fecha delante, quien valida no puede comprobar el cálculo."""
    documento = subir_plan(cliente, cab, proyecto)
    extraer(cliente, cab, documento["id"])

    todas = cliente.get(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales", headers=cab("consultor_a")
    ).json()
    caducado = next(lim for lim in todas if lim["motivo"] == "CADUCADO")

    assert "14/03/2016" in caducado["evidencia"]
    assert "RD 393/2007" in caducado["texto"]


# ─────────────────────────────────────────────────────────────────────────────
#  Nada llega al informe sin que alguien lo acepte
# ─────────────────────────────────────────────────────────────────────────────


def test_una_limitacion_pendiente_no_sale_en_el_informe(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REQ]` Una limitación que una máquina propuso y nadie miró no puede
    aparecer en un entregable firmado."""
    documento = subir_plan(cliente, cab, proyecto)
    extraer(cliente, cab, documento["id"])

    delinforme = cliente.get(
        f"{RUTA}/projects/{proyecto}/report-limitations", headers=cab("consultor_a")
    ).json()
    assert [lim for lim in delinforme if lim["origen"] == "DOCUMENTO"] == []


def test_aceptar_la_mete_en_el_informe_y_descartar_no(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    documento = subir_plan(cliente, cab, proyecto)
    extraer(cliente, cab, documento["id"])
    todas = cliente.get(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales", headers=cab("consultor_a")
    ).json()
    declaradas = [lim for lim in todas if lim["motivo"] == "DECLARADA"]
    resto = [lim for lim in todas if lim["motivo"] != "DECLARADA"]

    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales/decidir",
        headers=cab("consultor_a"),
        json={
            "aceptar": [lim["id"] for lim in declaradas],
            "descartar": [lim["id"] for lim in resto],
        },
    )

    assert r.status_code == 200, r.text
    assert r.json() == {"aceptadas": len(declaradas), "descartadas": len(resto)}

    delinforme = cliente.get(
        f"{RUTA}/projects/{proyecto}/report-limitations", headers=cab("consultor_a")
    ).json()
    documentales = [lim for lim in delinforme if lim["origen"] == "DOCUMENTO"]
    assert len(documentales) == len(declaradas)
    assert all(lim["documento"] == "plan" for lim in documentales)
    assert any("naves vacías" in lim["title"] for lim in documentales)


def test_descartar_deja_constancia_de_quien_fue(
    cliente: TestClient, cab: Any, proyecto: str, datos_base: Any
) -> None:
    """Descartar no es borrar. Si el cliente pregunta por qué el informe no
    menciona que el plan se redactó con las naves vacías, la respuesta tiene que
    estar en la base y no en la memoria de nadie."""
    documento = subir_plan(cliente, cab, proyecto)
    extraer(cliente, cab, documento["id"])
    primera = cliente.get(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales", headers=cab("consultor_a")
    ).json()[0]

    cliente.post(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales/decidir",
        headers=cab("consultor_a"),
        json={"descartar": [primera["id"]]},
    )

    tras = cliente.get(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales?estado=DESCARTADA",
        headers=cab("consultor_a"),
    ).json()
    assert len(tras) == 1
    assert tras[0]["id"] == primera["id"]
    assert tras[0]["decidida_por"] == str(datos_base["consultor_a"])


def test_aceptar_y_descartar_la_misma_se_rechaza(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Aplicarlas en orden dejaría ganando a la última por azar."""
    documento = subir_plan(cliente, cab, proyecto)
    extraer(cliente, cab, documento["id"])
    primera = cliente.get(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales", headers=cab("consultor_a")
    ).json()[0]

    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales/decidir",
        headers=cab("consultor_a"),
        json={"aceptar": [primera["id"]], "descartar": [primera["id"]]},
    )
    assert r.status_code == 422
    assert "las dos listas" in r.json()["detail"]


def test_decidir_dos_veces_la_misma_se_rechaza(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Puede que otra persona la haya resuelto entre la carga y el clic."""
    documento = subir_plan(cliente, cab, proyecto)
    extraer(cliente, cab, documento["id"])
    primera = cliente.get(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales", headers=cab("consultor_a")
    ).json()[0]
    cuerpo = {"aceptar": [primera["id"]]}

    assert (
        cliente.post(
            f"{RUTA}/projects/{proyecto}/limitaciones-documentales/decidir",
            headers=cab("consultor_a"),
            json=cuerpo,
        ).status_code
        == 200
    )
    segunda = cliente.post(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales/decidir",
        headers=cab("consultor_a"),
        json=cuerpo,
    )
    assert segunda.status_code == 409
    assert "ya estaba decidida" in segunda.json()["detail"]


def test_volver_a_extraer_no_reabre_lo_ya_decidido(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    documento = subir_plan(cliente, cab, proyecto)
    extraer(cliente, cab, documento["id"])
    primera = cliente.get(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales", headers=cab("consultor_a")
    ).json()[0]
    cliente.post(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales/decidir",
        headers=cab("consultor_a"),
        json={"aceptar": [primera["id"]]},
    )

    segunda = extraer(cliente, cab, documento["id"])

    assert any("ya decidió" in aviso for aviso in segunda["avisos"])
    todas = cliente.get(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales", headers=cab("consultor_a")
    ).json()
    iguales = [lim for lim in todas if lim["texto"] == primera["texto"]]
    assert len(iguales) == 1, "la aceptada no puede haberse duplicado"
    assert iguales[0]["estado"] == "ACEPTADA"


def test_volver_a_extraer_sustituye_las_pendientes_y_no_las_acumula(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    documento = subir_plan(cliente, cab, proyecto)
    primera = extraer(cliente, cab, documento["id"])
    extraer(cliente, cab, documento["id"])

    todas = cliente.get(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales", headers=cab("consultor_a")
    ).json()
    assert len(todas) == primera["limitaciones"]


# ─────────────────────────────────────────────────────────────────────────────
#  Las tres clases se distinguen
# ─────────────────────────────────────────────────────────────────────────────


def test_el_informe_distingue_de_donde_sale_cada_limitacion(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine, datos_base: Any
) -> None:
    """`[REQ]` «No nos lo dieron» y «nos lo dieron y dice que no vale» no se
    redactan igual en un informe. Sin el origen, las dos se leen igual."""
    # Una línea de checklist sin recibir: la primera clase.
    with motor_admin.begin() as conn:
        fase = conn.execute(
            text(
                "INSERT INTO project_phase (organization_id, project_id, phase_definition_id, "
                "display_order) SELECT :o, :p, pd.id, 1 FROM phase_definition pd "
                "WHERE pd.code = 'SOLICITUD_DOCUMENTACION' RETURNING id"
            ),
            {"o": str(datos_base["org_a"]), "p": proyecto},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO doc_request_item (organization_id, project_phase_id, category_id, "
                "title, status, unavailable_reason, display_order) "
                "SELECT :o, :f, c.id, 'Certificado de instalación eléctrica', 'NO_DISPONIBLE', "
                "'El cliente no lo localiza', 1 FROM doc_request_category c LIMIT 1"
            ),
            {"o": str(datos_base["org_a"]), "f": str(fase)},
        )

    # Y una limitación documental aceptada: la tercera.
    documento = subir_plan(cliente, cab, proyecto)
    extraer(cliente, cab, documento["id"])
    primera = cliente.get(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales", headers=cab("consultor_a")
    ).json()[0]
    cliente.post(
        f"{RUTA}/projects/{proyecto}/limitaciones-documentales/decidir",
        headers=cab("consultor_a"),
        json={"aceptar": [primera["id"]]},
    )

    delinforme = cliente.get(
        f"{RUTA}/projects/{proyecto}/report-limitations", headers=cab("consultor_a")
    ).json()

    origenes = {lim["origen"] for lim in delinforme}
    assert origenes == {"CHECKLIST", "DOCUMENTO"}
    checklist = next(lim for lim in delinforme if lim["origen"] == "CHECKLIST")
    assert checklist["documento"] is None, "una línea sin recibir no sale de ningún documento"


def test_otra_organizacion_no_ve_las_limitaciones_ajenas(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    documento = subir_plan(cliente, cab, proyecto)
    extraer(cliente, cab, documento["id"])

    r = cliente.get(f"{RUTA}/projects/{proyecto}/limitaciones-documentales", headers=cab("admin_b"))
    assert r.json() == []


# ─────────────────────────────────────────────────────────────────────────────
#  Confidencialidad
# ─────────────────────────────────────────────────────────────────────────────


def test_un_plan_de_autoproteccion_nace_restringido(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REQ]` Lleva procedimientos de emergencia, puntos de reunión y datos de
    las personas con responsabilidad en una emergencia. Antes se quedaba en
    `INTERNO` porque el valor por omisión estaba clavado en la firma."""
    documento = subir_plan(cliente, cab, proyecto)
    assert documento["confidentiality"] == "RESTRINGIDO"


def test_el_resto_de_documentos_sigue_naciendo_interno(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/documents",
        headers=cab("consultor_a"),
        files={"file": ("lic.pdf", b"%PDF-1.4 lo que sea", "application/pdf")},
        data={"doc_type": "LICENCIA_URBANISTICA", "display_name": "lic.pdf"},
    )
    assert r.json()["confidentiality"] == "INTERNO"


def test_quien_sube_puede_decidir_otro_nivel(cliente: TestClient, cab: Any, proyecto: str) -> None:
    """`[REC]` Es un valor por omisión, no una imposición."""
    documento = subir_plan(cliente, cab, proyecto, confidentiality="CONFIDENCIAL")
    assert documento["confidentiality"] == "CONFIDENCIAL"

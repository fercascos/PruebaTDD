"""`[REQ]` La documentación va completando el cuadro, y el gestor valida.

Con las palabras del cliente: *«dependiendo de la documentación que se suba se
pueda ir completando el cuadro de CAPEX automáticamente para que después el
gestor de la due diligence valide la información»*.

Lo que estas pruebas fijan es lo que hace que esa frase se sostenga cuando hay
**más de un documento**, que es donde el diseño anterior se rompía:

* que el extractor lo elige **el tipo del documento**, y un tipo sin lector se
  dice en vez de reventar;
* que **nada se aplica solo**: extraer deja propuestas, no datos;
* que dos documentos pueden proponer **cosas distintas para el mismo campo** y
  las dos se ven, con su procedencia, para que alguien elija;
* y que lo ya decidido **no se reabre** al volver a extraer.
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


def memoria_pdf(superficies: dict[str, str]) -> bytes:
    """Un PDF con una tabla de superficies, como la de una memoria real.

    `[REQ]` No hay ninguna memoria de cliente en el repositorio: el documento
    contra el que se escribió el extractor es confidencial. Aquí se fabrica uno
    con las mismas etiquetas y la misma forma de tabla.
    """
    from reportlab.lib import colors  # type: ignore[import-not-found]
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    filas = [["Concepto", "Superficie aproximada"], *[[k, v] for k, v in superficies.items()]]
    tabla = Table(filas)
    # Con rejilla a propósito: `pdfplumber` detecta las tablas por sus líneas.
    # Una tabla sin trazar se lee como texto corrido y el extractor no vería
    # ningún par etiqueta/valor —que es justo lo que la prueba quiere ejercitar.
    tabla.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))

    # Prosa suficiente para que el extractor no lo tome por un escaneado: por
    # debajo de doscientos caracteres avisa de que haría falta OCR y se para.
    cuerpo = getSampleStyleSheet()["BodyText"]
    relleno = Paragraph(
        "MD.2 Descripción del proyecto. El edificio objeto de la presente memoria es "
        "una nave industrial-logística destinada a almacenamiento y distribución, con "
        "zona de oficinas en planta primera. La parcela dispone de vial perimetral y "
        "muelles de carga en su fachada posterior. Las superficies que figuran en el "
        "cuadro anterior son aproximadas y se recogen a los solos efectos descriptivos.",
        cuerpo,
    )
    doc.build([tabla, relleno])
    return buffer.getvalue()


@pytest.fixture(scope="module")
def tipologia(motor_admin: Engine) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text("SELECT id FROM asset_typology WHERE code = 'INDUSTRIAL'")
            ).scalar_one()
        )


@pytest.fixture
def proyecto(motor_admin: Engine, datos_base: dict[str, uuid.UUID]) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text(
                    "INSERT INTO project (organization_id, client_id, internal_code, name) "
                    "VALUES (:o, :c, :cod, 'Encargo con documentos') RETURNING id"
                ),
                {
                    "o": str(datos_base["org_a"]),
                    "c": str(datos_base["cliente_a"]),
                    "cod": f"EXT-{uuid.uuid4().hex[:6]}",
                },
            ).scalar_one()
        )


@pytest.fixture
def activo(cliente: TestClient, cab: Any, proyecto: str, tipologia: str) -> str:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave documentada", "typology_id": tipologia},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def subir(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    activo: str,
    contenido: bytes,
    *,
    nombre: str,
    doc_type: str = "MEMORIA_TECNICA",
) -> str:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/documents",
        headers=cab("consultor_a"),
        files={"file": (nombre, contenido, "application/pdf")},
        data={"asset_id": activo, "doc_type": doc_type, "display_name": nombre},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


# ─────────────────────────────────────────────────────────────────────────────
#  El extractor lo elige el tipo del documento
# ─────────────────────────────────────────────────────────────────────────────


def test_los_tipos_que_se_leen_hoy_se_publican(cliente: TestClient, cab: Any) -> None:
    """Para que la pantalla ofrezca el botón solo donde va a funcionar.

    Ofrecerlo en todos y fallar en la mayoría enseña a la gente a no pulsarlo.
    """
    r = cliente.get(f"{RUTA}/extraccion/tipos-soportados", headers=cab("consultor_a"))
    assert r.status_code == 200
    assert "MEMORIA_TECNICA" in r.json()


def test_un_tipo_sin_lector_lo_dice_y_no_revienta(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` La mayoría de los documentos de un encargo no se extraen. Que un
    tipo no se lea todavía es un caso normal, no una avería: 422 con la lista
    de los que sí, que es lo accionable."""
    documento = subir(
        cliente,
        cab,
        proyecto,
        activo,
        b"%PDF-1.4 lo que sea",
        nombre="lic.pdf",
        doc_type="LICENCIA_URBANISTICA",
    )
    r = cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))

    assert r.status_code == 422
    assert "No hay lector" in r.json()["detail"]
    assert "MEMORIA_TECNICA" in r.json()["detail"]


def test_un_documento_sin_activo_no_sabe_a_quien_proponerle_nada(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/documents",
        headers=cab("consultor_a"),
        files={"file": ("suelto.pdf", memoria_pdf({"Parcela": "12.410 m²"}), "application/pdf")},
        data={"doc_type": "MEMORIA_TECNICA", "display_name": "suelto.pdf"},
    )
    documento = str(r.json()["id"])

    extraido = cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))
    assert extraido.status_code == 409
    assert "no está asignado" in extraido.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
#  Nada se aplica solo
# ─────────────────────────────────────────────────────────────────────────────


def test_extraer_propone_pero_no_toca_el_activo(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` Entre la propuesta y el dato hay una persona pulsando un botón."""
    documento = subir(
        cliente,
        cab,
        proyecto,
        activo,
        memoria_pdf({"Parcela": "12.410 m²", "Construida total": "8.134 m²"}),
        nombre="memoria.pdf",
    )

    r = cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))

    assert r.status_code == 201, r.text
    assert r.json()["propuestas"] >= 2
    assert r.json()["es_simulada"] is False, "lee el documento de verdad"

    ficha = cliente.get(f"{RUTA}/assets/{activo}", headers=cab("consultor_a")).json()
    assert ficha["plot_area_sqm"] is None, "la propuesta no puede haberse aplicado sola"
    assert ficha["total_built_sqm"] is None


def test_cada_propuesta_trae_su_procedencia_y_el_valor_actual(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """Sin el valor actual al lado, quien valida no distingue «esto completa un
    hueco» de «esto contradice lo que ya había»."""
    cliente.patch(
        f"{RUTA}/assets/{activo}",
        headers={**cab("consultor_a"), "If-Match": "1"},
        json={"plot_area_sqm": "9000.00"},
    )
    documento = subir(
        cliente,
        cab,
        proyecto,
        activo,
        memoria_pdf({"Parcela": "12.410 m²"}),
        nombre="memoria.pdf",
    )
    cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))

    propuestas = cliente.get(
        f"{RUTA}/assets/{activo}/propuestas", headers=cab("consultor_a")
    ).json()

    parcela = next(p for p in propuestas if p["campo"] == "plot_area_sqm")
    assert parcela["valor"] == "12410"
    assert parcela["valor_actual"] == "9000.00", "lo que hay hoy, para poder comparar"
    assert parcela["document_id"] == documento
    assert parcela["doc_type"] == "MEMORIA_TECNICA"
    assert parcela["estado"] == "PENDIENTE"

    # `[REQ]` La evidencia es la celda **tal y como está escrita en el PDF**, no
    # lo que la máquina entendió. «12.410 m²» es lo que hay que poder comparar
    # con el documento; «plot_area_sqm = 12410» es la misma lectura repetida, y
    # si la lectura estaba mal, repetirla no lo delata.
    assert parcela["evidencia"] == "Parcela | 12.410 m²"


# ─────────────────────────────────────────────────────────────────────────────
#  Dos documentos conviven
# ─────────────────────────────────────────────────────────────────────────────


def test_dos_documentos_pueden_discrepar_y_se_ven_los_dos(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` Es la razón de que la propuesta tenga procedencia.

    Una memoria de proyecto y otra de reforma redactadas con años de diferencia
    dan superficies que no coinciden. **El desacuerdo es información**: quien
    valida tiene que ver las dos con su documento, no una sola porque llegó la
    última.
    """
    primero = subir(
        cliente,
        cab,
        proyecto,
        activo,
        memoria_pdf({"Construida total": "8.134 m²"}),
        nombre="proyecto.pdf",
    )
    segundo = subir(
        cliente,
        cab,
        proyecto,
        activo,
        memoria_pdf({"Construida total": "8.200 m²"}),
        nombre="reforma.pdf",
    )
    cliente.post(f"{RUTA}/documents/{primero}/extraer", headers=cab("consultor_a"))
    cliente.post(f"{RUTA}/documents/{segundo}/extraer", headers=cab("consultor_a"))

    propuestas = cliente.get(
        f"{RUTA}/assets/{activo}/propuestas", headers=cab("consultor_a")
    ).json()
    construidas = [p for p in propuestas if p["campo"] == "total_built_sqm"]

    assert len(construidas) == 2, "el segundo documento no puede haber pisado al primero"
    assert {p["valor"] for p in construidas} == {"8134", "8200"}
    assert {p["document_id"] for p in construidas} == {primero, segundo}


def test_aceptar_dos_valores_del_mismo_campo_se_rechaza(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """Aplicarlas en orden dejaría ganando a la última, que es un resultado que
    depende de cómo se ordenó una lista y que no ha decidido nadie."""
    for nombre, valor in (("a.pdf", "8.134 m²"), ("b.pdf", "8.200 m²")):
        documento = subir(
            cliente,
            cab,
            proyecto,
            activo,
            memoria_pdf({"Construida total": valor}),
            nombre=nombre,
        )
        cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))

    propuestas = cliente.get(
        f"{RUTA}/assets/{activo}/propuestas", headers=cab("consultor_a")
    ).json()
    ambas = [p["id"] for p in propuestas if p["campo"] == "total_built_sqm"]

    r = cliente.post(
        f"{RUTA}/assets/{activo}/propuestas/decidir",
        headers=cab("consultor_a"),
        json={"aceptar": ambas},
    )
    assert r.status_code == 422
    assert "mismo campo" in r.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
#  El botón
# ─────────────────────────────────────────────────────────────────────────────


def test_aceptar_aplica_al_activo_y_firma_quien_fue(
    cliente: TestClient, cab: Any, proyecto: str, activo: str, datos_base: Any
) -> None:
    """Y la firma va **en la propuesta**, no en el activo.

    `[REQ]` `memoria_validada_at` significa «alguien ha revisado la memoria de
    este edificio», y la ficha del activo lo enseña como «validada». Aceptar una
    superficie suelta —que mañana puede venir de un plan de autoprotección— no
    es eso, y ponerlo ahí convertiría el testigo en una afirmación que nadie ha
    hecho. Quién aceptó qué, y de qué documento, queda en cada propuesta.
    """
    documento = subir(
        cliente,
        cab,
        proyecto,
        activo,
        memoria_pdf({"Parcela": "12.410 m²", "Ocupación": "6.766 m²"}),
        nombre="memoria.pdf",
    )
    cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))
    propuestas = cliente.get(
        f"{RUTA}/assets/{activo}/propuestas", headers=cab("consultor_a")
    ).json()

    r = cliente.post(
        f"{RUTA}/assets/{activo}/propuestas/decidir",
        headers=cab("consultor_a"),
        json={"aceptar": [p["id"] for p in propuestas]},
    )

    assert r.status_code == 200, r.text
    assert r.json()["aceptadas"] == len(propuestas)
    ficha = cliente.get(f"{RUTA}/assets/{activo}", headers=cab("consultor_a")).json()
    assert ficha["plot_area_sqm"] == "12410.00"
    assert ficha["occupied_area_sqm"] == "6766.00"
    # El testigo de la memoria NO se toca: nadie ha validado ninguna memoria.
    assert ficha["memoria_validada_at"] is None

    tras = cliente.get(f"{RUTA}/assets/{activo}/propuestas", headers=cab("consultor_a")).json()
    assert {p["estado"] for p in tras} == {"ACEPTADA"}
    assert {p["decidida_por"] for p in tras} == {str(datos_base["consultor_a"])}


def test_descartar_no_toca_el_activo_pero_deja_constancia(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    documento = subir(
        cliente,
        cab,
        proyecto,
        activo,
        memoria_pdf({"Parcela": "12.410 m²"}),
        nombre="memoria.pdf",
    )
    cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))
    propuesta = cliente.get(
        f"{RUTA}/assets/{activo}/propuestas", headers=cab("consultor_a")
    ).json()[0]

    cliente.post(
        f"{RUTA}/assets/{activo}/propuestas/decidir",
        headers=cab("consultor_a"),
        json={"descartar": [propuesta["id"]]},
    )

    ficha = cliente.get(f"{RUTA}/assets/{activo}", headers=cab("consultor_a")).json()
    assert ficha["plot_area_sqm"] is None
    tras = cliente.get(f"{RUTA}/assets/{activo}/propuestas", headers=cab("consultor_a")).json()[0]
    assert tras["estado"] == "DESCARTADA"
    assert tras["decidida_por"] is not None, "descartar también lo firma alguien"


def test_volver_a_extraer_no_reabre_lo_ya_decidido(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` Reabrir sin avisar algo que una persona ya resolvió es la forma
    más rápida de que deje de fiarse de la pantalla."""
    documento = subir(
        cliente,
        cab,
        proyecto,
        activo,
        memoria_pdf({"Parcela": "12.410 m²"}),
        nombre="memoria.pdf",
    )
    cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))
    propuesta = cliente.get(
        f"{RUTA}/assets/{activo}/propuestas", headers=cab("consultor_a")
    ).json()[0]
    cliente.post(
        f"{RUTA}/assets/{activo}/propuestas/decidir",
        headers=cab("consultor_a"),
        json={"descartar": [propuesta["id"]]},
    )

    segunda = cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))

    assert segunda.status_code == 201
    assert any("ya decidió" in a for a in segunda.json()["avisos"])
    propuestas = cliente.get(
        f"{RUTA}/assets/{activo}/propuestas", headers=cab("consultor_a")
    ).json()
    parcelas = [p for p in propuestas if p["campo"] == "plot_area_sqm"]
    assert len(parcelas) == 1 and parcelas[0]["estado"] == "DESCARTADA"


def test_volver_a_extraer_sustituye_las_pendientes_y_no_las_acumula(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    documento = subir(
        cliente,
        cab,
        proyecto,
        activo,
        memoria_pdf({"Parcela": "12.410 m²"}),
        nombre="memoria.pdf",
    )
    cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))
    cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))

    propuestas = cliente.get(
        f"{RUTA}/assets/{activo}/propuestas", headers=cab("consultor_a")
    ).json()
    assert len([p for p in propuestas if p["campo"] == "plot_area_sqm"]) == 1


def test_otra_organizacion_no_ve_las_propuestas_ajenas(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    documento = subir(
        cliente,
        cab,
        proyecto,
        activo,
        memoria_pdf({"Parcela": "12.410 m²"}),
        nombre="memoria.pdf",
    )
    cliente.post(f"{RUTA}/documents/{documento}/extraer", headers=cab("consultor_a"))

    r = cliente.get(f"{RUTA}/assets/{activo}/propuestas", headers=cab("admin_b"))
    assert r.json() == []

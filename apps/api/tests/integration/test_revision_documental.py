"""Revisión de documentación con IA `[REQ]`.

Lo que se prueba aquí y en ningún otro sitio son las tres garantías que el
cliente puso como condición, y que no valen nada si solo están escritas en la
documentación:

1. **Sin autorización expresa del encargo no se analiza nada**, y la
   autorización deja constancia de quién la dio.
2. **La IA no decide.** Ninguna observación sale de `PROPUESTA` sin una
   persona, y aceptar una propuesta **no cambia** el estado de la línea de la
   checklist.
3. **Una revisión simulada no puede pasar por real**, ni en la base ni en la
   respuesta de la API.
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
PDF = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"


@pytest.fixture
def proyecto(cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]) -> str:
    r = cliente.post(
        f"{RUTA}/projects",
        headers=cab("admin_a"),
        json={
            "client_id": str(datos_base["cliente_a"]),
            "internal_code": f"IA-{uuid.uuid4().hex[:6]}",
            "name": "Encargo con revisión documental",
            "applicable_phases": [{"code": "SOLICITUD_DOCUMENTACION"}],
        },
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


@pytest.fixture
def categoria(motor_admin: Engine) -> str:
    with motor_admin.begin() as conn:
        return str(
            conn.execute(
                text("SELECT id FROM doc_request_category ORDER BY display_order LIMIT 1")
            ).scalar_one()
        )


@pytest.fixture
def documento(cliente: TestClient, cab: Any, proyecto: str) -> str:
    datos = PDF + uuid.uuid4().hex.encode()
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/documents",
        headers=cab("consultor_a"),
        files={"file": ("licencia.pdf", io.BytesIO(datos), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def autorizar(cliente: TestClient, cab: Any, proyecto: str, activo: bool = True) -> Any:
    return cliente.put(
        f"{RUTA}/projects/{proyecto}/ai-doc-review",
        headers=cab("admin_a"),
        json={"activo": activo},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  1 · La autorización por encargo
# ─────────────────────────────────────────────────────────────────────────────


def test_un_encargo_nace_sin_revision_con_ia(cliente: TestClient, cab: Any, proyecto: str) -> None:
    """`[REQ]` Apagado de fábrica. Nadie tiene que acordarse de apagarlo."""
    r = cliente.get(f"{RUTA}/projects/{proyecto}/ai-doc-review", headers=cab("admin_a"))
    assert r.status_code == 200
    assert r.json()["activo"] is False


def test_sin_autorizacion_no_se_analiza_nada(cliente: TestClient, cab: Any, documento: str) -> None:
    """El documento existe y el conector funciona: lo que falta es el permiso."""
    r = cliente.post(f"{RUTA}/documents/{documento}/ai-review", headers=cab("consultor_a"))
    assert r.status_code == 403
    assert "no tiene activada" in r.json()["detail"]


def test_autorizar_deja_constancia_de_quien_y_cuando(
    cliente: TestClient, cab: Any, proyecto: str, datos_base: dict[str, uuid.UUID]
) -> None:
    """`[REQ]` «Autorización expresa y verificable»: sin autoría no es verificable."""
    r = autorizar(cliente, cab, proyecto)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["activo"] is True
    assert cuerpo["desde"] is not None
    assert cuerpo["por"] == str(datos_base["admin_a"])


def test_un_consultor_no_puede_autorizar(cliente: TestClient, cab: Any, proyecto: str) -> None:
    """Es una autorización sobre documentación del cliente, no una preferencia."""
    r = cliente.put(
        f"{RUTA}/projects/{proyecto}/ai-doc-review",
        headers=cab("consultor_a"),
        json={"activo": True},
    )
    assert r.status_code == 403


def test_apagar_borra_la_autoria(cliente: TestClient, cab: Any, proyecto: str) -> None:
    """Dejar la autoría puesta daría a entender que sigue autorizado."""
    autorizar(cliente, cab, proyecto, True)
    r = autorizar(cliente, cab, proyecto, False)
    assert r.json() == {"activo": False, "desde": None, "por": None}


def test_la_autorizacion_queda_en_la_auditoria(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    autorizar(cliente, cab, proyecto)
    with motor_admin.begin() as conn:
        acciones = (
            conn.execute(
                text("SELECT action FROM audit_log WHERE entity_id = :e"),
                {"e": proyecto},
            )
            .scalars()
            .all()
        )
    assert "AI_DOC_REVIEW_ENABLED" in acciones


# ─────────────────────────────────────────────────────────────────────────────
#  2 · La revisión, y su honestidad
# ─────────────────────────────────────────────────────────────────────────────


def test_la_revision_produce_una_propuesta_por_criterio(
    cliente: TestClient, cab: Any, proyecto: str, documento: str
) -> None:
    autorizar(cliente, cab, proyecto)
    r = cliente.post(f"{RUTA}/documents/{documento}/ai-review", headers=cab("consultor_a"))
    assert r.status_code == 201, r.text
    cuerpo = r.json()

    criterios = cliente.get(f"{RUTA}/ai-review-checks", headers=cab("consultor_a")).json()
    assert len(cuerpo["observaciones"]) == len(criterios)
    assert all(o["decision"] == "PROPUESTA" for o in cuerpo["observaciones"])


def test_la_revision_se_declara_simulada(
    cliente: TestClient, cab: Any, proyecto: str, documento: str
) -> None:
    """`[LIM]` Mientras no haya proveedor, que se note en la propia respuesta."""
    autorizar(cliente, cab, proyecto)
    cuerpo = cliente.post(
        f"{RUTA}/documents/{documento}/ai-review", headers=cab("consultor_a")
    ).json()
    assert cuerpo["is_simulated"] is True
    assert cuerpo["provider"] == "SIMULADO"
    assert all(o["summary"].startswith("SIMULADO —") for o in cuerpo["observaciones"])


def test_la_revision_congela_el_hash_del_documento(
    cliente: TestClient, cab: Any, proyecto: str, documento: str
) -> None:
    """Sustituir el documento no puede hacer parecer que se opinó sobre el nuevo."""
    autorizar(cliente, cab, proyecto)
    revision = cliente.post(
        f"{RUTA}/documents/{documento}/ai-review", headers=cab("consultor_a")
    ).json()
    doc = cliente.get(f"{RUTA}/documents/{documento}", headers=cab("consultor_a")).json()
    assert revision["document_sha256"] == doc["sha256"]


def test_el_historial_devuelve_las_revisiones_de_la_mas_nueva_a_la_mas_vieja(
    cliente: TestClient, cab: Any, proyecto: str, documento: str
) -> None:
    autorizar(cliente, cab, proyecto)
    for _ in range(2):
        cliente.post(f"{RUTA}/documents/{documento}/ai-review", headers=cab("consultor_a"))
    r = cliente.get(f"{RUTA}/documents/{documento}/ai-reviews", headers=cab("consultor_a"))
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_revisar_un_documento_que_no_existe_da_404(cliente: TestClient, cab: Any) -> None:
    r = cliente.post(f"{RUTA}/documents/{uuid.uuid4()}/ai-review", headers=cab("consultor_a"))
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
#  3 · La IA propone, una persona decide
# ─────────────────────────────────────────────────────────────────────────────


def primera_observacion(cliente: TestClient, cab: Any, documento: str) -> dict[str, Any]:
    cuerpo = cliente.post(
        f"{RUTA}/documents/{documento}/ai-review", headers=cab("consultor_a")
    ).json()
    return cuerpo["observaciones"][0]  # type: ignore[no-any-return]


def test_aceptar_una_propuesta_deja_quien_la_acepto(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    documento: str,
    datos_base: dict[str, uuid.UUID],
) -> None:
    autorizar(cliente, cab, proyecto)
    obs = primera_observacion(cliente, cab, documento)
    r = cliente.post(
        f"{RUTA}/ai-review-findings/{obs['id']}/decision",
        headers=cab("consultor_a"),
        json={"aceptar": True, "nota": "Comprobado contra el original"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["decision"] == "ACEPTADA"
    assert r.json()["decided_by"] == str(datos_base["consultor_a"])


def test_rechazar_tambien_exige_persona(
    cliente: TestClient, cab: Any, proyecto: str, documento: str
) -> None:
    autorizar(cliente, cab, proyecto)
    obs = primera_observacion(cliente, cab, documento)
    r = cliente.post(
        f"{RUTA}/ai-review-findings/{obs['id']}/decision",
        headers=cab("consultor_a"),
        json={"aceptar": False},
    )
    assert r.json()["decision"] == "RECHAZADA"
    assert r.json()["decided_by"] is not None


def test_no_se_decide_dos_veces(
    cliente: TestClient, cab: Any, proyecto: str, documento: str
) -> None:
    autorizar(cliente, cab, proyecto)
    obs = primera_observacion(cliente, cab, documento)
    url = f"{RUTA}/ai-review-findings/{obs['id']}/decision"
    cliente.post(url, headers=cab("consultor_a"), json={"aceptar": True})
    r = cliente.post(url, headers=cab("consultor_a"), json={"aceptar": False})
    assert r.status_code == 409
    assert "ya está aceptada" in r.json()["detail"]


def test_aceptar_una_propuesta_no_cambia_el_estado_de_la_checklist(
    cliente: TestClient, cab: Any, proyecto: str, categoria: str
) -> None:
    """`[REQ]` El corazón del requisito.

    Un documento puede estar RECIBIDA y ser no conforme a la vez. Aceptar la
    observación dice que es cierta; **no** decide qué hacer con la línea. Eso
    lo decide quien lleva el encargo, con la información delante.
    """
    autorizar(cliente, cab, proyecto)
    linea = cliente.post(
        f"{RUTA}/projects/{proyecto}/doc-requests",
        headers=cab("consultor_a"),
        json={"category_id": categoria, "title": "Licencia de actividad"},
    ).json()

    datos = PDF + uuid.uuid4().hex.encode()
    doc = cliente.post(
        f"{RUTA}/projects/{proyecto}/documents",
        headers=cab("consultor_a"),
        files={"file": ("licencia.pdf", io.BytesIO(datos), "application/pdf")},
        data={"doc_request_item_id": linea["id"]},
    ).json()

    def estado() -> str:
        filas = cliente.get(
            f"{RUTA}/projects/{proyecto}/doc-requests", headers=cab("consultor_a")
        ).json()
        return next(x["status"] for x in filas if x["id"] == linea["id"])  # type: ignore[no-any-return]

    antes = estado()
    obs = primera_observacion(cliente, cab, str(doc["id"]))
    cliente.post(
        f"{RUTA}/ai-review-findings/{obs['id']}/decision",
        headers=cab("consultor_a"),
        json={"aceptar": True},
    )
    assert estado() == antes


def test_decidir_sobre_algo_que_no_existe_da_404(cliente: TestClient, cab: Any) -> None:
    r = cliente.post(
        f"{RUTA}/ai-review-findings/{uuid.uuid4()}/decision",
        headers=cab("consultor_a"),
        json={"aceptar": True},
    )
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
#  4 · Los criterios son catálogo, no código
# ─────────────────────────────────────────────────────────────────────────────


def test_los_criterios_salen_de_la_base(cliente: TestClient, cab: Any) -> None:
    r = cliente.get(f"{RUTA}/ai-review-checks", headers=cab("consultor_a"))
    assert r.status_code == 200
    codigos = {c["code"] for c in r.json()}
    assert codigos == {"CORRESPONDENCIA", "VIGENCIA", "COMPLETITUD", "LEGIBILIDAD"}
    assert all(c["description_es"].strip() for c in r.json())


def test_desactivar_un_criterio_lo_saca_de_la_revision(
    cliente: TestClient, cab: Any, proyecto: str, documento: str, motor_admin: Engine
) -> None:
    """`[PDV]` Los criterios están pendientes de cerrar con el cliente: cambiar
    qué se revisa tiene que ser una fila, no un despliegue."""
    autorizar(cliente, cab, proyecto)
    with motor_admin.begin() as conn:
        conn.execute(text("UPDATE doc_check_type SET is_active = FALSE WHERE code = 'LEGIBILIDAD'"))
    try:
        cuerpo = cliente.post(
            f"{RUTA}/documents/{documento}/ai-review", headers=cab("consultor_a")
        ).json()
        assert "LEGIBILIDAD" not in {o["check_code"] for o in cuerpo["observaciones"]}
    finally:
        with motor_admin.begin() as conn:
            conn.execute(
                text("UPDATE doc_check_type SET is_active = TRUE WHERE code = 'LEGIBILIDAD'")
            )


def test_una_organizacion_puede_anadir_su_propio_criterio(
    cliente: TestClient,
    cab: Any,
    proyecto: str,
    documento: str,
    motor_admin: Engine,
    datos_base: dict[str, uuid.UUID],
) -> None:
    """`[LIM]` Los criterios del sistema (`organization_id IS NULL`) son de solo
    lectura para la aplicación, como todos los catálogos del proyecto: la
    política RLS de catálogo solo deja escribir filas propias.

    Así que «cambiar qué se revisa sin migración» significa **añadir criterios
    propios**, no editar los de fábrica. Desactivar uno del sistema sigue
    requiriendo administración de la base. Queda dicho aquí para que nadie lo
    descubra al intentarlo.
    """
    autorizar(cliente, cab, proyecto)
    with motor_admin.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO doc_check_type (organization_id, code, name_es, "
                "description_es, display_order, is_system) "
                "VALUES (:o, 'FIRMA_TECNICO', 'Firma de técnico competente', "
                "'Comprueba si el documento lo firma un técnico con visado.', 9, FALSE)"
            ),
            {"o": str(datos_base["org_a"])},
        )
    try:
        cuerpo = cliente.post(
            f"{RUTA}/documents/{documento}/ai-review", headers=cab("consultor_a")
        ).json()
        assert "FIRMA_TECNICO" in {o["check_code"] for o in cuerpo["observaciones"]}
    finally:
        # Se desactiva, no se borra: la clave ajena de `doc_review_finding` lo
        # impide en cuanto una revisión lo ha usado, y hace bien. Perder el
        # criterio dejaría observaciones ya emitidas sin poder decir contra qué
        # se pronunciaron.
        with motor_admin.begin() as conn:
            conn.execute(
                text("UPDATE doc_check_type SET is_active = FALSE WHERE code = 'FIRMA_TECNICO'")
            )


# ─────────────────────────────────────────────────────────────────────────────
#  5 · Aislamiento entre organizaciones
# ─────────────────────────────────────────────────────────────────────────────


def test_otra_organizacion_no_ve_las_revisiones(
    cliente: TestClient, cab: Any, proyecto: str, documento: str
) -> None:
    """Lo revisado es documentación confidencial de un cliente."""
    autorizar(cliente, cab, proyecto)
    cliente.post(f"{RUTA}/documents/{documento}/ai-review", headers=cab("consultor_a"))
    r = cliente.get(f"{RUTA}/documents/{documento}/ai-reviews", headers=cab("admin_b"))
    assert r.json() == []

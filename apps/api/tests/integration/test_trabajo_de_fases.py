"""El trabajo que se hace dentro de cada fase.

El hilo que une todo este fichero: **lo que no se ha podido revisar acaba en el
apartado de limitaciones del informe, sin que nadie tenga que acordarse.** Un
documento `NO_DISPONIBLE` y una pregunta `SIN_RESPUESTA` son lo mismo desde el
punto de vista del informe, y las dos columnas que lo marcan son generadas.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.db

RUTA = "/api/v1"

FASES = [
    "SOLICITUD_DOCUMENTACION",
    "VDR",
    "VISITA",
    "QA",
    "PRESENTACION_CLIENTE",
    "DEFENSA",
]


@pytest.fixture
def proyecto(cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID]) -> str:
    """Un encargo con todas las fases activas, creado por la API real."""
    r = cliente.post(
        f"{RUTA}/projects",
        headers=cab("admin_a"),
        json={
            "client_id": str(datos_base["cliente_a"]),
            "internal_code": f"FAS-{uuid.uuid4().hex[:6]}",
            "name": "Encargo con todas las fases",
            "applicable_phases": [{"code": c} for c in FASES],
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
def activo(cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine) -> str:
    with motor_admin.begin() as conn:
        tipologia = conn.execute(text("SELECT id FROM asset_typology LIMIT 1")).scalar_one()
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/assets",
        headers=cab("consultor_a"),
        json={"name": "Nave A", "typology_id": str(tipologia)},
    )
    return str(r.json()["id"])


# ─────────────────────────────────────────────────────────────────────────────
#  Checklist documental
# ─────────────────────────────────────────────────────────────────────────────


def test_se_anaden_lineas_al_checklist(
    cliente: TestClient, cab: Any, proyecto: str, categoria: str
) -> None:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/doc-requests",
        headers=cab("consultor_a"),
        json={"category_id": categoria, "title": "Licencia de actividad"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "SOLICITADA"
    assert r.json()["requested_at"] is not None


def test_una_fase_no_activada_da_404_en_vez_de_crearse_sola(
    cliente: TestClient, cab: Any, datos_base: dict[str, uuid.UUID], categoria: str
) -> None:
    """Las fases se eligen a la carta al dar de alta el encargo. Crear una
    porque alguien llamó a su endpoint saltaría esa decisión."""
    sin_fases = cliente.post(
        f"{RUTA}/projects",
        headers=cab("admin_a"),
        json={
            "client_id": str(datos_base["cliente_a"]),
            "internal_code": f"SIN-{uuid.uuid4().hex[:6]}",
            "name": "Encargo sin fases",
            "applicable_phases": [],
        },
    ).json()

    r = cliente.post(
        f"{RUTA}/projects/{sin_fases['id']}/doc-requests",
        headers=cab("consultor_a"),
        json={"category_id": categoria, "title": "Lo que sea"},
    )
    assert r.status_code == 404
    assert "actívela" in r.json()["detail"]


def test_marcar_no_disponible_exige_motivo(
    cliente: TestClient, cab: Any, proyecto: str, categoria: str
) -> None:
    """Decir «no disponible» sin decir por qué deja el informe sin poder
    explicar la limitación, que es exactamente para lo que sirve el campo."""
    linea = cliente.post(
        f"{RUTA}/projects/{proyecto}/doc-requests",
        headers=cab("consultor_a"),
        json={"category_id": categoria, "title": "Proyecto de ejecución"},
    ).json()

    sin_motivo = cliente.patch(
        f"{RUTA}/doc-requests/{linea['id']}",
        headers=cab("consultor_a"),
        json={"status": "NO_DISPONIBLE"},
    )
    assert sin_motivo.status_code == 422

    con_motivo = cliente.patch(
        f"{RUTA}/doc-requests/{linea['id']}",
        headers=cab("consultor_a"),
        json={
            "status": "NO_DISPONIBLE",
            "unavailable_reason": "La propiedad no conserva el proyecto original",
        },
    )
    assert con_motivo.status_code == 200


def test_la_base_de_datos_tambien_lo_exige(
    cliente: TestClient, cab: Any, proyecto: str, categoria: str, motor_admin: Engine
) -> None:
    linea = cliente.post(
        f"{RUTA}/projects/{proyecto}/doc-requests",
        headers=cab("consultor_a"),
        json={"category_id": categoria, "title": "Legalización de baja tensión"},
    ).json()
    with motor_admin.begin() as conn, pytest.raises(Exception, match="no_disponible_exige_motivo"):
        conn.execute(
            text("UPDATE doc_request_item SET status = 'NO_DISPONIBLE' WHERE id = :i"),
            {"i": linea["id"]},
        )


def test_marcar_recibida_fecha_la_recepcion_sola(
    cliente: TestClient, cab: Any, proyecto: str, categoria: str
) -> None:
    linea = cliente.post(
        f"{RUTA}/projects/{proyecto}/doc-requests",
        headers=cab("consultor_a"),
        json={"category_id": categoria, "title": "Certificado energético"},
    ).json()
    r = cliente.patch(
        f"{RUTA}/doc-requests/{linea['id']}",
        headers=cab("consultor_a"),
        json={"status": "RECIBIDA"},
    )
    assert r.json()["received_at"] is not None


@pytest.mark.parametrize(
    ("estado", "limita"),
    [
        ("SOLICITADA", False),
        ("RECIBIDA", False),
        ("PARCIAL", True),
        ("NO_DISPONIBLE", True),
        ("NO_APLICA", False),
    ],
)
def test_lo_que_falta_se_marca_solo_como_limitacion(
    cliente: TestClient, cab: Any, proyecto: str, categoria: str, estado: str, limita: bool
) -> None:
    """`[REC]` La columna es generada: no depende de que nadie se acuerde."""
    linea = cliente.post(
        f"{RUTA}/projects/{proyecto}/doc-requests",
        headers=cab("consultor_a"),
        json={"category_id": categoria, "title": f"Documento en {estado}"},
    ).json()
    cuerpo: dict[str, Any] = {"status": estado}
    if estado == "NO_DISPONIBLE":
        cuerpo["unavailable_reason"] = "No existe"
    r = cliente.patch(f"{RUTA}/doc-requests/{linea['id']}", headers=cab("consultor_a"), json=cuerpo)
    assert r.json()["affects_report_limitations"] is limita


def test_las_limitaciones_llegan_listas_para_el_informe(
    cliente: TestClient, cab: Any, proyecto: str, categoria: str
) -> None:
    """Declarar las limitaciones es una obligación profesional en una TDD, y
    hoy suele reconstruirse de memoria al final del encargo."""
    linea = cliente.post(
        f"{RUTA}/projects/{proyecto}/doc-requests",
        headers=cab("consultor_a"),
        json={"category_id": categoria, "title": "Plano de instalaciones"},
    ).json()
    cliente.patch(
        f"{RUTA}/doc-requests/{linea['id']}",
        headers=cab("consultor_a"),
        json={"status": "NO_DISPONIBLE", "unavailable_reason": "No se conserva"},
    )
    limitaciones = cliente.get(
        f"{RUTA}/projects/{proyecto}/report-limitations", headers=cab("consultor_a")
    ).json()
    assert any(item["title"] == "Plano de instalaciones" for item in limitaciones)


# ─────────────────────────────────────────────────────────────────────────────
#  Enlace VDR
# ─────────────────────────────────────────────────────────────────────────────


def test_se_registra_el_enlace_al_repositorio(cliente: TestClient, cab: Any, proyecto: str) -> None:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/vdr-link",
        headers=cab("consultor_a"),
        json={
            "url": "https://vdr.example.com/proyecto",
            "provider": "Proveedor Ficticio",
            "access_notes": "Pedir acceso a la persona de contacto del cliente",
        },
    )
    assert r.status_code == 201


def test_el_enlace_no_admite_campo_de_credenciales(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """`[REC]` Deliberado: guardar la contraseña de un repositorio de terceros
    multiplicaría la superficie de riesgo sin aportar nada."""
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/vdr-link",
        headers=cab("consultor_a"),
        json={"url": "https://vdr.example.com/x", "password": "loquesea"},
    )
    assert r.status_code == 422


def test_solo_hay_un_enlace_vigente_y_el_anterior_se_conserva(
    cliente: TestClient, cab: Any, proyecto: str, motor_admin: Engine
) -> None:
    """Saber a qué repositorio se accedió y cuándo forma parte de la
    trazabilidad del encargo."""
    for url in ("https://vdr.example.com/v1", "https://vdr.example.com/v2"):
        cliente.post(
            f"{RUTA}/projects/{proyecto}/vdr-link", headers=cab("consultor_a"), json={"url": url}
        )

    vigente = cliente.get(f"{RUTA}/projects/{proyecto}/vdr-link", headers=cab("consultor_a")).json()
    assert vigente["url"] == "https://vdr.example.com/v2"

    with motor_admin.begin() as conn:
        total = conn.execute(text("SELECT count(*) FROM vdr_link")).scalar_one()
    assert total >= 2, "el anterior sigue como histórico"


# ─────────────────────────────────────────────────────────────────────────────
#  Visitas
# ─────────────────────────────────────────────────────────────────────────────


def test_se_programa_una_visita(cliente: TestClient, cab: Any, proyecto: str, activo: str) -> None:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/visits",
        headers=cab("consultor_a"),
        json={"asset_id": activo, "scheduled_date": str(date.today() + timedelta(days=7))},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "AGENDADO"


def test_sin_fecha_la_visita_queda_pendiente_de_definir(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/visits", headers=cab("consultor_a"), json={"asset_id": activo}
    )
    assert r.json()["status"] == "PENDIENTE_DEFINIR"


def test_agendar_sin_fecha_se_rechaza(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """«Agendado» sin fecha no es agendado."""
    visita = cliente.post(
        f"{RUTA}/projects/{proyecto}/visits", headers=cab("consultor_a"), json={"asset_id": activo}
    ).json()
    r = cliente.patch(
        f"{RUTA}/visits/{visita['id']}", headers=cab("consultor_a"), json={"status": "AGENDADO"}
    )
    assert r.status_code == 422


def test_marcar_visitado_fecha_la_visita_sola(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """La fecha real es la que fecha el informe: «visitado» sin ella deja el
    documento sin poder decir cuándo se vio lo que describe."""
    visita = cliente.post(
        f"{RUTA}/projects/{proyecto}/visits", headers=cab("consultor_a"), json={"asset_id": activo}
    ).json()
    r = cliente.patch(
        f"{RUTA}/visits/{visita['id']}", headers=cab("consultor_a"), json={"status": "VISITADO"}
    )
    assert r.status_code == 200
    assert r.json()["actual_date"] == str(date.today())


def test_se_registran_las_limitaciones_de_acceso(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """`[REQ]` De las que más pesan en el informe: «no se pudo acceder a la
    cubierta» cambia lo que se puede afirmar sobre ella."""
    visita = cliente.post(
        f"{RUTA}/projects/{proyecto}/visits", headers=cab("consultor_a"), json={"asset_id": activo}
    ).json()
    r = cliente.patch(
        f"{RUTA}/visits/{visita['id']}",
        headers=cab("consultor_a"),
        json={
            "status": "VISITADO",
            "access_limitations": "No se pudo acceder a la cubierta por falta de línea de vida",
        },
    )
    assert "línea de vida" in r.json()["access_limitations"]


def test_un_activo_de_otro_proyecto_no_se_puede_visitar(
    cliente: TestClient, cab: Any, proyecto: str, datos_base: dict[str, uuid.UUID]
) -> None:
    otro = cliente.post(
        f"{RUTA}/projects/{proyecto}/visits",
        headers=cab("consultor_a"),
        json={"asset_id": str(uuid.uuid4())},
    )
    assert otro.status_code == 422


def test_la_visita_hace_avanzar_la_fase(
    cliente: TestClient, cab: Any, proyecto: str, activo: str
) -> None:
    """El motor de fases cuenta las visitas: es lo que hace que la ficha del
    proyecto refleje el trabajo real y no lo que alguien marcó a mano."""
    visita = cliente.post(
        f"{RUTA}/projects/{proyecto}/visits", headers=cab("consultor_a"), json={"asset_id": activo}
    ).json()
    cliente.patch(
        f"{RUTA}/visits/{visita['id']}", headers=cab("consultor_a"), json={"status": "VISITADO"}
    )
    fases = cliente.get(f"{RUTA}/projects/{proyecto}/phases", headers=cab("consultor_a")).json()
    visita_fase = next(f for f in fases if f["code"] == "VISITA")
    assert visita_fase["estado_sugerido"] in ("COMPLETADA", "EN_CURSO", None)
    assert "1" in visita_fase["detalle"]


# ─────────────────────────────────────────────────────────────────────────────
#  Q&A
# ─────────────────────────────────────────────────────────────────────────────


def test_las_rondas_se_numeran_solas(cliente: TestClient, cab: Any, proyecto: str) -> None:
    """Dejarlo al cliente produciría dos «ronda 2» en cuanto dos personas
    abrieran una a la vez."""
    numeros = [
        cliente.post(
            f"{RUTA}/projects/{proyecto}/qa-rounds", headers=cab("consultor_a"), json={}
        ).json()["round_number"]
        for _ in range(3)
    ]
    assert numeros == [1, 2, 3]


def test_se_anaden_preguntas_numeradas(cliente: TestClient, cab: Any, proyecto: str) -> None:
    ronda = cliente.post(
        f"{RUTA}/projects/{proyecto}/qa-rounds",
        headers=cab("consultor_a"),
        json={"title": "Primera ronda"},
    ).json()
    for pregunta in ("¿Existe licencia de primera ocupación?", "¿Hay contrato de mantenimiento?"):
        r = cliente.post(
            f"{RUTA}/qa-rounds/{ronda['id']}/questions",
            headers=cab("consultor_a"),
            json={"question": pregunta},
        )
        assert r.status_code == 201
    assert [q["number"] for q in r.json()["questions"]] == [1, 2]


def test_responder_cambia_el_estado_sin_pedirlo_dos_veces(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Pedir dos campos para una sola acción es la clase de fricción que hace
    que la gente no lo rellene."""
    ronda = cliente.post(
        f"{RUTA}/projects/{proyecto}/qa-rounds", headers=cab("consultor_a"), json={}
    ).json()
    ronda = cliente.post(
        f"{RUTA}/qa-rounds/{ronda['id']}/questions",
        headers=cab("consultor_a"),
        json={"question": "¿Hay proyecto de legalización?"},
    ).json()

    r = cliente.patch(
        f"{RUTA}/qa-questions/{ronda['questions'][0]['id']}",
        headers=cab("consultor_a"),
        json={"answer": "Sí, se adjunta en el repositorio"},
    )
    assert r.json()["questions"][0]["status"] == "RESPONDIDA"


def test_marcar_respondida_sin_respuesta_se_rechaza(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    ronda = cliente.post(
        f"{RUTA}/projects/{proyecto}/qa-rounds", headers=cab("consultor_a"), json={}
    ).json()
    ronda = cliente.post(
        f"{RUTA}/qa-rounds/{ronda['id']}/questions",
        headers=cab("consultor_a"),
        json={"question": "¿Y el certificado?"},
    ).json()
    r = cliente.patch(
        f"{RUTA}/qa-questions/{ronda['questions'][0]['id']}",
        headers=cab("consultor_a"),
        json={"status": "RESPONDIDA"},
    )
    assert r.status_code == 422


def test_cerrar_la_ronda_no_obliga_a_inventar_respuestas(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Lo que queda sin contestar pasa a `SIN_RESPUESTA` y aparece como
    limitación. Bloquear el cierre obligaría a inventar respuestas para poder
    avanzar, que es peor que declarar honestamente que no las hubo."""
    ronda = cliente.post(
        f"{RUTA}/projects/{proyecto}/qa-rounds", headers=cab("consultor_a"), json={}
    ).json()
    ronda = cliente.post(
        f"{RUTA}/qa-rounds/{ronda['id']}/questions",
        headers=cab("consultor_a"),
        json={"question": "¿Se conservan los certificados de la instalación?"},
    ).json()

    r = cliente.post(
        f"{RUTA}/qa-rounds/{ronda['id']}/status",
        headers=cab("consultor_a"),
        json={"status": "CERRADA"},
    )
    assert r.status_code == 200
    pregunta = r.json()["questions"][0]
    assert pregunta["status"] == "SIN_RESPUESTA"
    assert pregunta["affects_report_limitations"] is True


def test_lo_ya_respondido_no_se_toca_al_cerrar(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    ronda = cliente.post(
        f"{RUTA}/projects/{proyecto}/qa-rounds", headers=cab("consultor_a"), json={}
    ).json()
    ronda = cliente.post(
        f"{RUTA}/qa-rounds/{ronda['id']}/questions",
        headers=cab("consultor_a"),
        json={"question": "¿Hay ascensor?"},
    ).json()
    cliente.patch(
        f"{RUTA}/qa-questions/{ronda['questions'][0]['id']}",
        headers=cab("consultor_a"),
        json={"answer": "Sí, dos"},
    )
    r = cliente.post(
        f"{RUTA}/qa-rounds/{ronda['id']}/status",
        headers=cab("consultor_a"),
        json={"status": "CERRADA"},
    )
    assert r.json()["questions"][0]["status"] == "RESPONDIDA"


def test_enviar_la_ronda_la_fecha(cliente: TestClient, cab: Any, proyecto: str) -> None:
    ronda = cliente.post(
        f"{RUTA}/projects/{proyecto}/qa-rounds", headers=cab("consultor_a"), json={}
    ).json()
    r = cliente.post(
        f"{RUTA}/qa-rounds/{ronda['id']}/status",
        headers=cab("consultor_a"),
        json={"status": "ENVIADA"},
    )
    assert r.json()["sent_at"] is not None


# ─────────────────────────────────────────────────────────────────────────────
#  Hitos
# ─────────────────────────────────────────────────────────────────────────────


def test_se_registra_la_presentacion_al_cliente(
    cliente: TestClient, cab: Any, proyecto: str
) -> None:
    """Es lo que convierte «se presentó» en algo verificable meses después."""
    r = cliente.post(
        f"{RUTA}/projects/{proyecto}/phase-events",
        headers=cab("consultor_a"),
        json={
            "phase_code": "PRESENTACION_CLIENTE",
            "event_date": str(date.today()),
            "counterparty": "Comité de inversión",
            "attendees": ["Dirección técnica", "Asesor financiero"],
            "outcome": "Se solicita ampliar el detalle de la cubierta",
        },
    )
    assert r.status_code == 201, r.text

    hitos = cliente.get(
        f"{RUTA}/projects/{proyecto}/phase-events", headers=cab("consultor_a")
    ).json()
    assert hitos[0]["phase_code"] == "PRESENTACION_CLIENTE"
    assert hitos[0]["attendees"] == ["Dirección técnica", "Asesor financiero"]


def test_otra_organizacion_no_ve_el_trabajo_de_las_fases(
    cliente: TestClient, cab: Any, proyecto: str, categoria: str
) -> None:
    cliente.post(
        f"{RUTA}/projects/{proyecto}/doc-requests",
        headers=cab("consultor_a"),
        json={"category_id": categoria, "title": "Confidencial"},
    )
    r = cliente.get(f"{RUTA}/projects/{proyecto}/doc-requests", headers=cab("admin_b"))
    # La fase misma queda fuera de su alcance, así que ni siquiera llega a la
    # lista: la RLS corta antes.
    assert r.status_code == 404

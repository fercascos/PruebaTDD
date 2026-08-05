"""Fases y proyectos, punta a punta.

Lo que se comprueba aquí es el vínculo entre los dos ejes: que el **estado** del
encargo y las **fases** avanzan por separado, y que las dos fases derivadas
siguen al trabajo real en vez de a lo que alguien haya marcado.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

pytestmark = pytest.mark.db


@pytest.fixture
def proyecto(cliente, cab, datos_base):
    """Un proyecto nuevo con las cuatro fases habituales."""
    r = cliente.post(
        "/api/v1/projects",
        headers=cab("consultor_a"),
        json={
            "client_id": str(datos_base["cliente_a"]),
            "internal_code": f"2026-{uuid.uuid4().hex[:6]}",
            "name": "TDD de prueba",
            "applicable_phases": [
                {"code": "SOLICITUD_DOCUMENTACION"},
                {"code": "VISITA"},
                {"code": "RED_FLAG_CAPEX"},
                {"code": "FULL_REPORT"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
#  Alta con fases a la carta
# ─────────────────────────────────────────────────────────────────────────────


def test_solo_se_crean_las_fases_marcadas(cliente, cab, datos_base, proyecto) -> None:
    """[REQ] §3.1.5 · Un encargo sin Q&A no arrastra una fase vacía."""
    fases = cliente.get(
        f"/api/v1/projects/{proyecto['id']}/phases", headers=cab("consultor_a")
    ).json()
    codigos = {f["code"] for f in fases}
    assert codigos == {"SOLICITUD_DOCUMENTACION", "VISITA", "RED_FLAG_CAPEX", "FULL_REPORT"}
    assert "QA" not in codigos
    assert "VDR" not in codigos


def test_una_fase_se_puede_activar_despues(cliente, cab, datos_base, proyecto) -> None:
    cabecera = cab("consultor_a")
    r = cliente.post(f"/api/v1/projects/{proyecto['id']}/phases/QA/activate", headers=cabecera)
    assert r.status_code == 200
    assert r.json()["code"] == "QA"

    fases = cliente.get(f"/api/v1/projects/{proyecto['id']}/phases", headers=cabecera).json()
    assert "QA" in {f["code"] for f in fases}


def test_un_proyecto_nuevo_nace_en_borrador(proyecto) -> None:
    assert proyecto["status"] == "BORRADOR"


# ─────────────────────────────────────────────────────────────────────────────
#  Las fases derivadas siguen al trabajo real
# ─────────────────────────────────────────────────────────────────────────────


def _fase(cliente, cab, project_id: str, code: str) -> dict:
    fases = cliente.get(f"/api/v1/projects/{project_id}/phases", headers=cab("consultor_a")).json()
    return next(f for f in fases if f["code"] == code)


def test_red_flag_capex_arranca_pendiente(cliente, cab, datos_base, proyecto) -> None:
    f = _fase(cliente, cab, proyecto["id"], "RED_FLAG_CAPEX")
    assert f["status"] == "PENDIENTE"
    assert f["es_derivado"] is True
    assert f["estado_sugerido"] is None, "Una fase derivada no propone: calcula"


def test_al_anadir_una_linea_de_capex_la_fase_pasa_a_en_curso(
    cliente, cab, datos_base, proyecto, motor_admin
) -> None:
    """El vínculo que hace útil el estado derivado: nadie lo marca a mano."""
    with motor_admin.begin() as c:
        perfil = c.execute(
            text(
                "INSERT INTO cost_profile (organization_id, name, cascade_config) "
                "VALUES (:o, :n, '{}'::jsonb) RETURNING id"
            ),
            {"o": datos_base["org_a"], "n": f"Perfil {uuid.uuid4().hex[:6]}"},
        ).scalar_one()
        tip = c.execute(text("SELECT id FROM asset_typology WHERE code='INDUSTRIAL'")).scalar_one()
        activo = c.execute(
            text(
                "INSERT INTO asset (organization_id, project_id, typology_id, name) "
                "VALUES (:o, :p, :t, 'Nave') RETURNING id"
            ),
            {"o": datos_base["org_a"], "p": proyecto["id"], "t": tip},
        ).scalar_one()
        codigo = c.execute(text("SELECT id FROM capex_code WHERE code='HC.H08.01'")).scalar_one()
        zona = c.execute(text("SELECT id FROM zone WHERE code='CUBIERTA'")).scalar_one()
        hallazgo = c.execute(
            text(
                "INSERT INTO finding (organization_id, project_id, asset_id, capex_code_id, "
                "zone_id, title, created_by) VALUES (:o,:p,:a,:c,:z,'Corrosión',:u) RETURNING id"
            ),
            {
                "o": datos_base["org_a"],
                "p": proyecto["id"],
                "a": activo,
                "c": codigo,
                "z": zona,
                "u": datos_base["consultor_a"],
            },
        ).scalar_one()
        horizonte = c.execute(text("SELECT id FROM time_horizon WHERE code='CORTO'")).scalar_one()
        c.execute(
            text(
                "INSERT INTO capex_item (organization_id, project_id, finding_id, "
                "cost_profile_id, time_horizon_id, amount, tax_pct) "
                "VALUES (:o,:p,:f,:cp,:h,:amt,0.21)"
            ),
            {
                "o": datos_base["org_a"],
                "p": proyecto["id"],
                "f": hallazgo,
                "cp": perfil,
                "h": horizonte,
                "amt": Decimal("48500"),
            },
        )

    f = _fase(cliente, cab, proyecto["id"], "RED_FLAG_CAPEX")
    assert f["status"] == "EN_CURSO", "Hay una línea, pero su precio no está validado"
    assert "1 líneas" in f["detalle"]
    assert "1 sin precio validado" in f["detalle"]


def test_no_se_puede_marcar_a_mano_una_fase_derivada(cliente, cab, datos_base, proyecto) -> None:
    """[REC] La regla que impide la falsa sensación de avance."""
    f = _fase(cliente, cab, proyecto["id"], "RED_FLAG_CAPEX")
    r = cliente.patch(
        f"/api/v1/project-phases/{f['id']}",
        headers=cab("consultor_a"),
        json={"status": "COMPLETADA"},
    )
    assert r.status_code == 422
    assert "no se puede fijar a mano" in r.json()["detail"]


def test_una_fase_manual_si_se_marca(cliente, cab, datos_base, proyecto) -> None:
    f = _fase(cliente, cab, proyecto["id"], "VISITA")
    r = cliente.patch(
        f"/api/v1/project-phases/{f['id']}",
        headers=cab("consultor_a"),
        json={"status": "EN_CURSO"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "EN_CURSO"


def test_full_report_se_queda_en_pendiente_sin_modulo_de_informes(
    cliente, cab, datos_base, proyecto
) -> None:
    """[LIM] Documentado y probado: el motor implementa la regla completa, pero
    todavía no hay versiones de informe que contar. `PENDIENTE` es lo correcto
    —no se puede generar nada— y no una cifra inventada."""
    f = _fase(cliente, cab, proyecto["id"], "FULL_REPORT")
    assert f["status"] == "PENDIENTE"
    assert f["detalle"] == "sin generar"


# ─────────────────────────────────────────────────────────────────────────────
#  Máquina de estados con las guardas reales
# ─────────────────────────────────────────────────────────────────────────────


def test_un_proyecto_sin_activos_no_sale_de_borrador(cliente, cab, datos_base, proyecto) -> None:
    r = cliente.post(
        f"/api/v1/projects/{proyecto['id']}/transitions",
        headers=cab("consultor_a"),
        json={"to": "EN_PREPARACION"},
    )
    assert r.status_code == 422
    assert "activo" in r.json()["detail"]


def test_los_destinos_posibles_dicen_que_falta(cliente, cab, datos_base, proyecto) -> None:
    """[REC] Es lo que permite el botón deshabilitado con su motivo."""
    r = cliente.get(
        f"/api/v1/projects/{proyecto['id']}/transitions",
        headers=cab("consultor_a"),
    ).json()
    destinos = {d["to"]: d for d in r}
    assert set(destinos) == {"EN_PREPARACION", "ARCHIVADO"}
    assert destinos["EN_PREPARACION"]["permitida"] is False
    assert any("activo" in m for m in destinos["EN_PREPARACION"]["falta"])
    # Descartar un borrador no tiene guardas.
    assert destinos["ARCHIVADO"]["permitida"] is True


def test_una_transicion_inexistente_da_409_y_no_422(cliente, cab, datos_base, proyecto) -> None:
    """Se distinguen los dos casos a propósito: «eso no se puede» y «falta esto»
    son dos conversaciones distintas con el usuario."""
    r = cliente.post(
        f"/api/v1/projects/{proyecto['id']}/transitions",
        headers=cab("consultor_a"),
        json={"to": "INFORME_EMITIDO"},
    )
    assert r.status_code == 409
    assert "EN_PREPARACION" in r.json()["detail"]


def test_con_activo_y_visita_el_proyecto_avanza(
    cliente, cab, datos_base, proyecto, motor_admin
) -> None:
    cabecera = cab("consultor_a")
    with motor_admin.begin() as c:
        tip = c.execute(text("SELECT id FROM asset_typology WHERE code='OFICINAS'")).scalar_one()
        activo = c.execute(
            text(
                "INSERT INTO asset (organization_id, project_id, typology_id, name) "
                "VALUES (:o,:p,:t,'Edificio') RETURNING id"
            ),
            {"o": datos_base["org_a"], "p": proyecto["id"], "t": tip},
        ).scalar_one()

    assert (
        cliente.post(
            f"/api/v1/projects/{proyecto['id']}/transitions",
            headers=cabecera,
            json={"to": "EN_PREPARACION"},
        ).status_code
        == 200
    )

    with motor_admin.begin() as c:
        c.execute(
            text(
                "INSERT INTO asset_visit (organization_id, project_id, asset_id, status, "
                "scheduled_date) VALUES (:o,:p,:a,'AGENDADO', CURRENT_DATE)"
            ),
            {"o": datos_base["org_a"], "p": proyecto["id"], "a": activo},
        )

    assert (
        cliente.post(
            f"/api/v1/projects/{proyecto['id']}/transitions",
            headers=cabecera,
            json={"to": "VISITA_PROGRAMADA"},
        ).status_code
        == 200
    )

    # Todavía no se ha visitado: la guarda lo impide.
    r = cliente.post(
        f"/api/v1/projects/{proyecto['id']}/transitions",
        headers=cabecera,
        json={"to": "VISITA_REALIZADA"},
    )
    assert r.status_code == 422
    assert "queda 1 activo por visitar" in r.json()["detail"]

    with motor_admin.begin() as c:
        c.execute(
            text(
                "UPDATE asset_visit SET status='VISITADO', actual_date=CURRENT_DATE "
                "WHERE project_id = :p"
            ),
            {"p": proyecto["id"]},
        )
    assert (
        cliente.post(
            f"/api/v1/projects/{proyecto['id']}/transitions",
            headers=cabecera,
            json={"to": "VISITA_REALIZADA"},
        ).status_code
        == 200
    )


def test_el_cambio_de_estado_queda_auditado(
    cliente, cab, datos_base, proyecto, motor_admin
) -> None:
    cliente.post(
        f"/api/v1/projects/{proyecto['id']}/transitions",
        headers=cab("consultor_a"),
        json={"to": "ARCHIVADO"},
    )
    with motor_admin.connect() as c:
        n = c.execute(
            text(
                "SELECT count(*) FROM audit_log WHERE action = 'PROJECT_STATUS_CHANGED' "
                "AND entity_id = :p"
            ),
            {"p": proyecto["id"]},
        ).scalar_one()
    assert n == 1


# ─────────────────────────────────────────────────────────────────────────────
#  Solicitud de documentación y limitaciones del informe
# ─────────────────────────────────────────────────────────────────────────────


def test_no_disponible_sin_motivo_no_se_admite(
    cliente, cab, datos_base, proyecto, motor_admin
) -> None:
    """Sin motivo, el informe no puede explicar la limitación."""
    with motor_admin.connect() as c:
        fase = c.execute(
            text(
                "SELECT ph.id FROM project_phase ph JOIN phase_definition pd "
                "ON pd.id = ph.phase_definition_id "
                "WHERE ph.project_id = :p AND pd.code = 'SOLICITUD_DOCUMENTACION'"
            ),
            {"p": proyecto["id"]},
        ).scalar_one()
        cat = c.execute(
            text("SELECT id FROM doc_request_category WHERE code = 'PROYECTOS'")
        ).scalar_one()

    with pytest.raises((IntegrityError, DBAPIError)):
        with motor_admin.begin() as c:
            c.execute(
                text(
                    "INSERT INTO doc_request_item (organization_id, project_phase_id, "
                    "category_id, title, status) VALUES (:o,:f,:c,'Proyecto de ejecución',"
                    "'NO_DISPONIBLE')"
                ),
                {"o": datos_base["org_a"], "f": fase, "c": cat},
            )


def test_las_limitaciones_del_informe_salen_solas_de_la_checklist(
    cliente, cab, datos_base, proyecto, motor_admin
) -> None:
    """[REC] Declarar qué no se ha podido revisar es una obligación profesional
    en una TDD, y hoy suele reconstruirse de memoria al final."""
    with motor_admin.begin() as c:
        fase = c.execute(
            text(
                "SELECT ph.id FROM project_phase ph JOIN phase_definition pd "
                "ON pd.id = ph.phase_definition_id "
                "WHERE ph.project_id = :p AND pd.code = 'SOLICITUD_DOCUMENTACION'"
            ),
            {"p": proyecto["id"]},
        ).scalar_one()
        cats = dict(c.execute(text("SELECT code, id FROM doc_request_category")).all())
        filas = [
            ("Licencia de primera ocupación", "RECIBIDA", None, cats["LICENCIAS_URBANISTICAS"]),
            (
                "Proyecto de ejecución",
                "NO_DISPONIBLE",
                "No se conserva en el archivo",
                cats["PROYECTOS"],
            ),
            ("Contratos de mantenimiento HVAC", "PARCIAL", None, cats["CONTRATOS_MANTENIMIENTO"]),
        ]
        for i, (titulo, estado, motivo, cat) in enumerate(filas):
            c.execute(
                text(
                    "INSERT INTO doc_request_item (organization_id, project_phase_id, "
                    "category_id, title, status, unavailable_reason, display_order) "
                    "VALUES (:o,:f,:c,:t,CAST(:s AS doc_request_status),:m,:i)"
                ),
                {
                    "o": datos_base["org_a"],
                    "f": fase,
                    "c": cat,
                    "t": titulo,
                    "s": estado,
                    "m": motivo,
                    "i": i,
                },
            )

    lim = cliente.get(
        f"/api/v1/projects/{proyecto['id']}/report-limitations",
        headers=cab("consultor_a"),
    ).json()

    # La recibida no es una limitación; las otras dos sí.
    assert {x["title"] for x in lim} == {"Proyecto de ejecución", "Contratos de mantenimiento HVAC"}
    no_disp = next(x for x in lim if x["status"] == "NO_DISPONIBLE")
    assert no_disp["unavailable_reason"] == "No se conserva en el archivo"


def test_la_fase_de_documentacion_sugiere_su_estado(
    cliente, cab, datos_base, proyecto, motor_admin
) -> None:
    """[REC] Se sugiere, no se impone: el responsable puede tener motivos que la
    aplicación no conoce."""
    with motor_admin.begin() as c:
        fase = c.execute(
            text(
                "SELECT ph.id FROM project_phase ph JOIN phase_definition pd "
                "ON pd.id = ph.phase_definition_id "
                "WHERE ph.project_id = :p AND pd.code = 'SOLICITUD_DOCUMENTACION'"
            ),
            {"p": proyecto["id"]},
        ).scalar_one()
        cat = c.execute(
            text("SELECT id FROM doc_request_category WHERE code = 'GARANTIAS'")
        ).scalar_one()
        c.execute(
            text(
                "INSERT INTO doc_request_item (organization_id, project_phase_id, "
                "category_id, title, status) VALUES (:o,:f,:c,'Garantías','SOLICITADA')"
            ),
            {"o": datos_base["org_a"], "f": fase, "c": cat},
        )

    f = _fase(cliente, cab, proyecto["id"], "SOLICITUD_DOCUMENTACION")
    assert f["status"] == "PENDIENTE", "El estado guardado no cambia solo"
    assert f["estado_sugerido"] == "EN_CURSO", "Pero la aplicación lo sugiere"


# ─────────────────────────────────────────────────────────────────────────────
#  Aislamiento
# ─────────────────────────────────────────────────────────────────────────────


def test_las_fases_de_otra_organizacion_no_se_ven(cliente, cab, datos_base, proyecto) -> None:
    fases = cliente.get(f"/api/v1/projects/{proyecto['id']}/phases", headers=cab("admin_b")).json()
    assert fases == []


def test_una_organizacion_ajena_no_transiciona_el_proyecto(
    cliente, cab, datos_base, proyecto
) -> None:
    r = cliente.post(
        f"/api/v1/projects/{proyecto['id']}/transitions",
        headers=cab("admin_b"),
        json={"to": "ARCHIVADO"},
    )
    assert r.status_code == 404

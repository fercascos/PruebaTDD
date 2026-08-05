"""La API punta a punta, con la base de datos real detrás.

El bloque que más importa es el de sugerencias: comprueba el requisito del
cliente —«solo el administrador ve las propuestas»— a través de HTTP, que es
como lo va a vivir un usuario.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from tdd.core.security import crear_token
from tests.conftest import PERFILES, SECRETO_PRUEBAS

pytestmark = pytest.mark.db

# ─────────────────────────────────────────────────────────────────────────────
#  Autenticación
# ─────────────────────────────────────────────────────────────────────────────


def test_sin_credencial_no_se_entra(cliente) -> None:
    assert cliente.get("/api/v1/catalogs/zones").status_code == 401


def test_un_token_manipulado_no_cuela(cliente, cab, datos_base) -> None:
    bueno = crear_token(
        secreto=SECRETO_PRUEBAS,
        user_id=datos_base["admin_a"],
        organization_id=datos_base[PERFILES["admin_a"][0]],
        org_role="ADMIN",
        can_manage_suggestions=True,
        ttl_minutos=15,
    )
    malo = bueno[:-4] + "AAAA"
    r = cliente.get("/api/v1/catalogs/zones", headers={"Authorization": f"Bearer {malo}"})
    assert r.status_code == 401
    assert "firma" not in r.text.lower(), "El motivo exacto no se revela"


def test_la_salud_no_exige_credencial(cliente) -> None:
    assert cliente.get("/health").json() == {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
#  Catálogos · el desplegable dependiente
# ─────────────────────────────────────────────────────────────────────────────


def test_las_zonas_se_filtran_por_tipologia(cliente, cab) -> None:
    """[REQ] §3.3.2 · Es la regla que impide ofrecer «Almacén» en un hotel."""
    cab = cab("consultor_a")
    tipologias = {
        t["code"]: t["id"]
        for t in cliente.get("/api/v1/catalogs/asset-typologies", headers=cab).json()
    }

    industrial = cliente.get(
        f"/api/v1/catalogs/zones?typology_id={tipologias['INDUSTRIAL']}", headers=cab
    ).json()
    hotel = cliente.get(
        f"/api/v1/catalogs/zones?typology_id={tipologias['HOTEL']}", headers=cab
    ).json()

    assert len(industrial) == 11
    assert len(hotel) == 16
    assert "ALMACEN" in {z["code"] for z in industrial}
    assert "ALMACEN" not in {z["code"] for z in hotel}
    assert "PISCINA" in {z["code"] for z in hotel}


def test_sin_tipologia_devuelve_las_veinte_zonas(cliente, cab) -> None:
    r = cliente.get("/api/v1/catalogs/zones", headers=cab("lector_a"))
    assert len(r.json()) == 20


def test_los_grados_de_riesgo_llevan_su_definicion_integra(cliente, cab) -> None:
    """[REQ] La definición viaja con el grado: se muestra al clasificar."""
    r = cliente.get("/api/v1/catalogs/risk-levels", headers=cab("consultor_a"))
    grados = r.json()
    assert [g["code"] for g in grados] == ["01", "02", "03", "04"]
    assert all(len(g["definition_es"]) > 100 for g in grados)


def test_la_comprobacion_de_zona_explica_el_motivo(cliente, cab) -> None:
    cab = cab("consultor_a")
    tip = {
        t["code"]: t["id"]
        for t in cliente.get("/api/v1/catalogs/asset-typologies", headers=cab).json()
    }
    zonas = {z["code"]: z["id"] for z in cliente.get("/api/v1/catalogs/zones", headers=cab).json()}

    r = cliente.get(
        f"/api/v1/catalogs/zones/{zonas['ALMACEN']}/allowed?typology_id={tip['HOTEL']}",
        headers=cab,
    ).json()
    assert r["permitida"] is False
    assert "Almacén" in r["motivo"] and "Hotel" in r["motivo"]


# ─────────────────────────────────────────────────────────────────────────────
#  CAPEX · la cascada expuesta por HTTP
# ─────────────────────────────────────────────────────────────────────────────


def test_la_previsualizacion_devuelve_la_formula_con_sus_operandos(cliente, cab) -> None:
    """[REQ] «No ocultes las fórmulas.» Cada peldaño con su base y su porcentaje."""
    r = cliente.post(
        "/api/v1/capex/preview-calculation",
        headers=cab("consultor_a"),
        json={
            "quantity": "1",
            "unit_price": "48500",
            "percentages": {
                "indirect_pct": "0.08",
                "overhead_pct": "0.13",
                "profit_pct": "0.06",
                "fees_pct": "0.06",
                "contingency_pct": "0.10",
            },
            "tax_pct": "0.21",
        },
    )
    d = r.json()
    assert Decimal(d["pem"]) == Decimal("52380.00")
    assert Decimal(d["pec"]) == Decimal("62332.20")
    assert Decimal(d["computed_base"]) == Decimal("72679.34")
    assert Decimal(d["total_with_tax"]) == Decimal("87942.00")

    peldanos = {p["key"]: p for p in d["steps"]}
    assert Decimal(peldanos["overhead"]["base_amount"]) == Decimal("52380.00")
    assert "no se ha guardado" in d["nota"]


def test_la_previsualizacion_rechaza_datos_imposibles(cliente, cab) -> None:
    r = cliente.post(
        "/api/v1/capex/preview-calculation",
        headers=cab("consultor_a"),
        json={
            "quantity": "-1",
            "unit_price": "100",
            "percentages": {
                "indirect_pct": "0.08",
                "overhead_pct": "0",
                "profit_pct": "0",
                "fees_pct": "0",
                "contingency_pct": "0",
            },
        },
    )
    assert r.status_code == 422


def test_el_resumen_por_horizonte_devuelve_los_cinco(cliente, cab, datos_base) -> None:
    """P-05 · Cinco categorías, siempre, aunque alguna esté a cero."""
    r = cliente.get(
        f"/api/v1/projects/{datos_base['proyecto_a']}/capex/summary/by-horizon",
        headers=cab("consultor_a"),
    )
    filas = r.json()
    assert [f["time_horizon_code"] for f in filas] == ["CORTO", "MEDIO", "LARGO", "MEJORAS", "OTRO"]


# ─────────────────────────────────────────────────────────────────────────────
#  [REQ] Sugerencias · el requisito del cliente, por HTTP
# ─────────────────────────────────────────────────────────────────────────────


def _crear(cliente, cab, usuario: str, titulo: str, **extra) -> dict:
    r = cliente.post(
        "/api/v1/suggestions",
        headers=cab(usuario),
        json={"type": "CATALOGO", "title": titulo, "body": "cuerpo de la propuesta", **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_cualquier_rol_puede_proponer_incluido_un_lector(cliente, cab) -> None:
    """[REC] El rol de menor privilegio suele ser quien más fricción encuentra."""
    for usuario in ("lector_a", "consultor_a", "admin_a"):
        s = _crear(cliente, cab, usuario, f"Propuesta de {usuario}")
        assert s["status"] == "NUEVA"


def test_el_autor_ve_las_suyas_y_solo_las_suyas(cliente, cab) -> None:
    """[REQ] P-40."""
    creada = _crear(cliente, cab, "consultor_a", "Mía y de nadie más")
    mias = cliente.get("/api/v1/suggestions/mine", headers=cab("consultor_a")).json()
    assert creada["id"] in {s["id"] for s in mias}

    otras = cliente.get("/api/v1/suggestions/mine", headers=cab("consultor2_a")).json()
    assert creada["id"] not in {s["id"] for s in otras}


def test_un_consultor_no_puede_abrir_la_bandeja(cliente, cab) -> None:
    """[REQ] «Solo el administrador ve las propuestas.»"""
    r = cliente.get("/api/v1/suggestions", headers=cab("consultor_a"))
    assert r.status_code == 403


def test_el_administrador_si_abre_la_bandeja(cliente, cab) -> None:
    _crear(cliente, cab, "consultor_a", "Para la bandeja")
    r = cliente.get("/api/v1/suggestions", headers=cab("admin_a"))
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_una_sugerencia_ajena_da_404_y_no_403(cliente, cab) -> None:
    """No se confirma que exista: un 403 revelaría que hay algo ahí."""
    creada = _crear(cliente, cab, "consultor_a", "Ajena")
    r = cliente.get(f"/api/v1/suggestions/{creada['id']}", headers=cab("consultor2_a"))
    assert r.status_code == 404


def test_un_administrador_de_otra_organizacion_no_la_ve(cliente, cab) -> None:
    creada = _crear(cliente, cab, "consultor_a", "Solo de la organización A")
    r = cliente.get(f"/api/v1/suggestions/{creada['id']}", headers=cab("admin_b"))
    assert r.status_code == 404


def test_el_cuerpo_no_puede_suplantar_al_autor(cliente, cab, datos_base) -> None:
    """El fallo clásico de un endpoint abierto a todos los roles.

    Aunque el cuerpo traiga `created_by` u `organization_id`, se ignoran: se
    toman del token. Aquí se comprueba enviándolos a propósito.
    """
    r = cliente.post(
        "/api/v1/suggestions",
        headers=cab("consultor_a"),
        json={
            "type": "APLICACION",
            "title": "Intento de suplantación",
            "body": "x",
            "created_by": str(datos_base["consultor2_a"]),
            "organization_id": str(datos_base["org_b"]),
        },
    )
    assert r.status_code == 201
    # La sugerencia es del autor real, no del suplantado.
    mias = cliente.get("/api/v1/suggestions/mine", headers=cab("consultor_a")).json()
    assert r.json()["id"] in {s["id"] for s in mias}


def test_rechazar_sin_motivo_devuelve_422_con_explicacion(cliente, cab) -> None:
    creada = _crear(cliente, cab, "consultor_a", "Será rechazada sin motivo")
    admin = cab("admin_a")
    cliente.post(
        f"/api/v1/suggestions/{creada['id']}/transitions", headers=admin, json={"to": "EN_REVISION"}
    )
    r = cliente.post(
        f"/api/v1/suggestions/{creada['id']}/transitions", headers=admin, json={"to": "RECHAZADA"}
    )
    assert r.status_code == 422
    assert "explicar por qué" in r.json()["detail"]


def test_el_ciclo_completo_y_el_autor_lee_la_respuesta(cliente, cab) -> None:
    """El recorrido que hace que el módulo no sea un cementerio."""
    creada = _crear(cliente, cab, "consultor_a", "Falta detección de gas")
    admin = cab("admin_a")
    sid = creada["id"]

    assert (
        cliente.post(
            f"/api/v1/suggestions/{sid}/transitions", headers=admin, json={"to": "EN_REVISION"}
        ).status_code
        == 200
    )
    assert (
        cliente.post(
            f"/api/v1/suggestions/{sid}/transitions", headers=admin, json={"to": "ACEPTADA"}
        ).status_code
        == 200
    )
    aplicada = cliente.post(
        f"/api/v1/suggestions/{sid}/transitions",
        headers=admin,
        json={
            "to": "APLICADA",
            "applied_entity_type": "capex_code",
            "applied_entity_id": str(uuid.uuid4()),
            "resolution_note": "Creado el código HC.H10.07",
        },
    )
    assert aplicada.status_code == 200

    # [REQ] P-40 · el autor ve en qué quedó, con el enlace a lo que se creó.
    mias = cliente.get("/api/v1/suggestions/mine", headers=cab("consultor_a")).json()
    suya = next(s for s in mias if s["id"] == sid)
    assert suya["status"] == "APLICADA"
    assert suya["applied_entity_type"] == "capex_code"
    assert "HC.H10.07" in suya["resolution_note"]


def test_no_se_puede_aceptar_sin_revisar(cliente, cab) -> None:
    creada = _crear(cliente, cab, "consultor_a", "Salto de estado")
    r = cliente.post(
        f"/api/v1/suggestions/{creada['id']}/transitions",
        headers=cab("admin_a"),
        json={"to": "ACEPTADA"},
    )
    assert r.status_code == 409
    assert "EN_REVISION" in r.json()["detail"]


def test_un_consultor_no_puede_cambiar_estados(cliente, cab) -> None:
    creada = _crear(cliente, cab, "consultor_a", "No me la apruebo yo")
    r = cliente.post(
        f"/api/v1/suggestions/{creada['id']}/transitions",
        headers=cab("consultor_a"),
        json={"to": "ACEPTADA"},
    )
    assert r.status_code == 403


def test_abrir_una_sugerencia_con_contexto_de_proyecto_queda_auditado(
    cliente, cab, datos_base, motor_admin
) -> None:
    """[REC] El buzón no puede ser una vía silenciosa hacia datos de un proyecto."""
    from sqlalchemy import text

    creada = _crear(
        cliente,
        cab,
        "consultor_a",
        "Sobre un proyecto",
        context_project_id=str(datos_base["proyecto_a"]),
    )
    cliente.get(f"/api/v1/suggestions/{creada['id']}", headers=cab("admin_a"))

    with motor_admin.connect() as c:
        n = c.execute(
            text(
                "SELECT count(*) FROM audit_log WHERE action = 'SUGGESTION_VIEWED' "
                "AND entity_id = :i AND project_id = :p"
            ),
            {"i": creada["id"], "p": datos_base["proyecto_a"]},
        ).scalar_one()
    assert n == 1

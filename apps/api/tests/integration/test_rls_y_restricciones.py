"""Las garantías que viven en la base de datos, comprobadas contra PostgreSQL.

Estas pruebas no comprueban «que el servicio filtra bien». Comprueban que
**aunque el servicio no filtrase**, la base de datos no entrega la fila. Es la
diferencia entre una promesa y una garantía.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

pytestmark = pytest.mark.db


# ─────────────────────────────────────────────────────────────────────────────
#  Aislamiento entre organizaciones
# ─────────────────────────────────────────────────────────────────────────────


def test_una_organizacion_no_ve_los_proyectos_de_otra(como, datos_base) -> None:
    """Se comprueba sobre un proyecto concreto, no sobre el total.

    Un recuento global ataría esta prueba al orden de ejecución: otras pruebas
    crean proyectos en la misma organización y la cifra dejaría de cuadrar.
    """
    with como("admin_a") as s:
        assert (
            s.execute(
                text("SELECT count(*) FROM project WHERE id = :i"),
                {"i": datos_base["proyecto_a"]},
            ).scalar_one()
            == 1
        )

    with como("admin_b") as s:
        # Ni en el listado, ni pidiéndolo por su identificador exacto.
        assert s.execute(text("SELECT count(*) FROM project")).scalar_one() == 0
        fila = s.execute(
            text("SELECT id FROM project WHERE id = :i"), {"i": datos_base["proyecto_a"]}
        ).first()
        assert fila is None


def test_sin_contexto_no_se_ve_absolutamente_nada(fabrica) -> None:
    """El fallo seguro: olvidar el `SET LOCAL` produce una lista vacía, no una fuga."""
    s = fabrica()
    try:
        assert s.execute(text("SELECT count(*) FROM project")).scalar_one() == 0
        assert s.execute(text("SELECT count(*) FROM app_user")).scalar_one() == 0
    finally:
        s.close()


def test_no_se_puede_escribir_en_otra_organizacion(como, datos_base) -> None:
    """La política lleva WITH CHECK, no solo USING: escribir tampoco cuela."""
    with pytest.raises((IntegrityError, DBAPIError)), como("admin_b") as s:
        s.execute(
            text("INSERT INTO client (organization_id, name) VALUES (:o, 'Intruso')"),
            {"o": datos_base["org_a"]},
        )


def test_el_usuario_de_aplicacion_no_puede_saltarse_la_rls(motor_app) -> None:
    """Si tuviera BYPASSRLS o fuese propietario, todo lo anterior sería teatro."""
    with motor_app.connect() as c:
        bypass = c.execute(
            text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar_one()
        assert bypass is False
        propias = c.execute(
            text(
                "SELECT count(*) FROM pg_tables WHERE schemaname = 'public' "
                "AND tableowner = current_user"
            )
        ).scalar_one()
        assert propias == 0, "El usuario de aplicación no debe ser propietario de las tablas"


# ─────────────────────────────────────────────────────────────────────────────
#  [REQ] Sugerencias · solo el administrador ve las propuestas
# ─────────────────────────────────────────────────────────────────────────────


def _crear_sugerencia(s, titulo: str = "Falta un código") -> uuid.UUID:
    return s.execute(
        text(
            "INSERT INTO suggestion (organization_id, type, title, body, created_by) "
            "VALUES (current_setting('app.current_org_id')::uuid, 'CATALOGO', :t, 'cuerpo', "
            "current_setting('app.current_user_id')::uuid) RETURNING id"
        ),
        {"t": titulo},
    ).scalar_one()


def test_el_autor_ve_las_suyas(como) -> None:
    """[REQ] P-40 · decidido por el cliente."""
    with como("consultor_a") as s:
        sid = _crear_sugerencia(s, "La mía")
    with como("consultor_a") as s:
        assert (
            s.execute(text("SELECT title FROM suggestion WHERE id = :i"), {"i": sid}).scalar_one()
            == "La mía"
        )


def test_un_consultor_no_ve_las_de_sus_companeros(como) -> None:
    """[REQ] El requisito literal del cliente, comprobado en la base de datos."""
    with como("consultor_a") as s:
        sid = _crear_sugerencia(s, "Privada de A")

    with como("consultor2_a") as s:
        # Misma organización, otro autor: no existe para él.
        assert (
            s.execute(
                text("SELECT count(*) FROM suggestion WHERE id = :i"), {"i": sid}
            ).scalar_one()
            == 0
        )


def test_el_administrador_las_ve_todas(como) -> None:
    with como("consultor_a") as s:
        sid = _crear_sugerencia(s, "Para el admin")
    with como("admin_a") as s:
        assert (
            s.execute(
                text("SELECT count(*) FROM suggestion WHERE id = :i"), {"i": sid}
            ).scalar_one()
            == 1
        )


def test_un_administrador_no_ve_las_sugerencias_de_otra_organizacion(como) -> None:
    with como("consultor_a") as s:
        sid = _crear_sugerencia(s, "De la organización A")
    with como("admin_b") as s:
        assert (
            s.execute(
                text("SELECT count(*) FROM suggestion WHERE id = :i"), {"i": sid}
            ).scalar_one()
            == 0
        )


def test_no_se_puede_crear_una_sugerencia_a_nombre_de_otro(como, datos_base) -> None:
    """El fallo clásico de un endpoint abierto a todos los roles."""
    with pytest.raises((IntegrityError, DBAPIError)), como("consultor_a") as s:
        s.execute(
            text(
                "INSERT INTO suggestion (organization_id, type, title, body, created_by) "
                "VALUES (current_setting('app.current_org_id')::uuid, 'APLICACION', "
                "'suplantada', 'x', :otro)"
            ),
            {"otro": datos_base["consultor2_a"]},
        )


def test_un_consultor_no_puede_resolver_su_propia_sugerencia(como) -> None:
    """Ver la suya, sí. Cambiarle el estado, no."""
    with como("consultor_a") as s:
        sid = _crear_sugerencia(s, "Me la apruebo yo")

    with como("consultor_a") as s:
        resultado = s.execute(
            text("UPDATE suggestion SET status = 'ACEPTADA' WHERE id = :i"), {"i": sid}
        )
        assert resultado.rowcount == 0, "La política de UPDATE debe impedirlo"


def test_rechazar_sin_motivo_es_imposible(como) -> None:
    """La regla que impide que el buzón se convierta en un cementerio."""
    with como("consultor_a") as s:
        sid = _crear_sugerencia(s, "Será rechazada")

    with pytest.raises((IntegrityError, DBAPIError)), como("admin_a") as s:
        s.execute(
            text(
                "UPDATE suggestion SET status = 'RECHAZADA', "
                "resolved_by = current_setting('app.current_user_id')::uuid, "
                "resolved_at = now() WHERE id = :i"
            ),
            {"i": sid},
        )


def test_rechazar_con_motivo_si_se_puede(como) -> None:
    with como("consultor_a") as s:
        sid = _crear_sugerencia(s, "Rechazada con motivo")
    with como("admin_a") as s:
        s.execute(
            text(
                "UPDATE suggestion SET status = 'RECHAZADA', resolution_note = :m, "
                "resolved_by = current_setting('app.current_user_id')::uuid, "
                "resolved_at = now() WHERE id = :i"
            ),
            {"i": sid, "m": "Ya existe en el agrupador; te enseñamos cómo."},
        )
    with como("consultor_a") as s:
        nota = s.execute(
            text("SELECT resolution_note FROM suggestion WHERE id = :i"), {"i": sid}
        ).scalar_one()
        assert "agrupador" in nota, "El autor debe poder leer la respuesta [REQ] P-40"


# ─────────────────────────────────────────────────────────────────────────────
#  Reglas del CAPEX
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def linea_capex(datos_base, motor_admin):
    """Crea un hallazgo nuevo y devuelve lo necesario para su línea de CAPEX.

    Cada invocación genera su propio hallazgo: `capex_item` tiene un índice
    único por `finding_id` (una línea por hallazgo), así que reutilizarlo entre
    pruebas las haría depender del orden de ejecución.
    """
    sufijo = uuid.uuid4().hex[:8]
    with motor_admin.begin() as c:
        perfil = c.execute(
            text(
                "INSERT INTO cost_profile (organization_id, name, cascade_config) "
                "VALUES (:o, :n, '{}'::jsonb) "
                "ON CONFLICT (organization_id, name) DO UPDATE SET name = EXCLUDED.name "
                "RETURNING id"
            ),
            {"o": datos_base["org_a"], "n": "Estándar 2026"},
        ).scalar_one()
        tipologia = c.execute(
            text("SELECT id FROM asset_typology WHERE code = 'INDUSTRIAL'")
        ).scalar_one()
        activo = c.execute(
            text(
                "INSERT INTO asset (organization_id, project_id, typology_id, name) "
                "VALUES (:o, :p, :t, :n) RETURNING id"
            ),
            {
                "o": datos_base["org_a"],
                "p": datos_base["proyecto_a"],
                "t": tipologia,
                "n": f"Nave {sufijo}",
            },
        ).scalar_one()
        codigo = c.execute(text("SELECT id FROM capex_code WHERE code = 'HC.H08.01'")).scalar_one()
        zona = c.execute(text("SELECT id FROM zone WHERE code = 'CUBIERTA'")).scalar_one()
        hallazgo = c.execute(
            text(
                "INSERT INTO finding (organization_id, project_id, asset_id, capex_code_id, "
                "zone_id, title, created_by) VALUES (:o, :p, :a, :c, :z, 'Corrosión', :u) "
                "RETURNING id"
            ),
            {
                "o": datos_base["org_a"],
                "p": datos_base["proyecto_a"],
                "a": activo,
                "c": codigo,
                "z": zona,
                "u": datos_base["consultor_a"],
            },
        ).scalar_one()
        horizonte = c.execute(text("SELECT id FROM time_horizon WHERE code = 'CORTO'")).scalar_one()
    return {
        "org": datos_base["org_a"],
        "proyecto": datos_base["proyecto_a"],
        "hallazgo": hallazgo,
        "perfil": perfil,
        "horizonte": horizonte,
    }


def _insertar_linea(s, ctx, **extra):
    campos = {
        "o": ctx["org"],
        "p": ctx["proyecto"],
        "f": ctx["hallazgo"],
        "cp": ctx["perfil"],
        "h": ctx["horizonte"],
        "amount": Decimal("48500.00"),
        "tax": Decimal("0.21"),
        **extra,
    }
    return s.execute(
        text(
            "INSERT INTO capex_item (organization_id, project_id, finding_id, cost_profile_id, "
            "time_horizon_id, amount, tax_pct) "
            "VALUES (:o, :p, :f, :cp, :h, :amount, :tax) "
            "RETURNING amount, tax_amount, total_cost"
        ),
        campos,
    ).one()


def test_el_total_de_la_linea_es_columna_generada(como, linea_capex) -> None:
    """P-05b · El impuesto se aplica encima del importe, y el total no se teclea."""
    with como("consultor_a") as s:
        amount, tax, total = _insertar_linea(s, linea_capex)
    assert amount == Decimal("48500.0000")
    assert tax == Decimal("10185.0000")
    assert total == Decimal("58685.0000")


def test_un_precio_validado_exige_persona_y_nota(como, linea_capex) -> None:
    """[REQ] Ninguna ruta de código puede dejar VALIDADO sin revisión humana."""
    with pytest.raises((IntegrityError, DBAPIError)), como("consultor_a") as s:
        s.execute(
            text(
                "INSERT INTO capex_item (organization_id, project_id, finding_id, "
                "cost_profile_id, time_horizon_id, amount, price_status) "
                "VALUES (:o, :p, :f, :cp, :h, 100, 'VALIDADO')"
            ),
            {
                "o": linea_capex["org"],
                "p": linea_capex["proyecto"],
                "f": linea_capex["hallazgo"],
                "cp": linea_capex["perfil"],
                "h": linea_capex["horizonte"],
            },
        )


def test_media_medicion_no_se_admite(como, linea_capex) -> None:
    with pytest.raises((IntegrityError, DBAPIError)), como("consultor_a") as s:
        _insertar_linea(s, linea_capex, cantidad=1)
        s.execute(
            text("UPDATE capex_item SET measurement_unit = 'ud' WHERE finding_id = :f"),
            {"f": linea_capex["hallazgo"]},
        )


def test_no_se_admite_un_importe_negativo(como, linea_capex) -> None:
    with pytest.raises((IntegrityError, DBAPIError)), como("consultor_a") as s:
        _insertar_linea(s, linea_capex, amount=Decimal("-1"))


# ─────────────────────────────────────────────────────────────────────────────
#  El original nunca se sobrescribe
# ─────────────────────────────────────────────────────────────────────────────


def test_un_original_no_se_sobrescribe(como, datos_base) -> None:
    with como("consultor_a") as s:
        oid = s.execute(
            text(
                "INSERT INTO stored_object (organization_id, project_id, kind, storage_key, "
                "sha256, byte_size, mime_type) VALUES (:o, :p, 'PHOTO_ORIGINAL', "
                "'originals/a.jpg', :h, 1024, 'image/jpeg') RETURNING id"
            ),
            {"o": datos_base["org_a"], "p": datos_base["proyecto_a"], "h": "a" * 64},
        ).scalar_one()

    with pytest.raises((IntegrityError, DBAPIError), match="original"):
        with como("consultor_a") as s:
            s.execute(
                text("UPDATE stored_object SET sha256 = :h WHERE id = :i"),
                {"h": "b" * 64, "i": oid},
            )


def test_un_original_no_se_borra(como, datos_base) -> None:
    with como("consultor_a") as s:
        oid = s.execute(
            text(
                "INSERT INTO stored_object (organization_id, project_id, kind, storage_key, "
                "sha256, byte_size, mime_type) VALUES (:o, :p, 'TEMPLATE', 'templates/t.pptx', "
                ":h, 2048, :mime) RETURNING id"
            ),
            {
                "o": datos_base["org_a"],
                "p": datos_base["proyecto_a"],
                "h": "c" * 64,
                "mime": (
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                ),
            },
        ).scalar_one()

    with pytest.raises((IntegrityError, DBAPIError), match="original"):
        with como("consultor_a") as s:
            s.execute(text("DELETE FROM stored_object WHERE id = :i"), {"i": oid})


def test_la_auditoria_no_se_modifica_ni_se_borra(como, datos_base) -> None:
    with como("admin_a") as s:
        s.execute(
            text(
                "INSERT INTO audit_log (organization_id, actor_user_id, action, severity) "
                "VALUES (:o, :u, 'PRICE_VALIDATED', 'INFO')"
            ),
            {"o": datos_base["org_a"], "u": datos_base["admin_a"]},
        )

    for sentencia in (
        "UPDATE audit_log SET action = 'FALSEADO'",
        "DELETE FROM audit_log",
    ):
        with pytest.raises((IntegrityError, DBAPIError), match="auditoría"):
            with como("admin_a") as s:
                s.execute(text(sentencia))

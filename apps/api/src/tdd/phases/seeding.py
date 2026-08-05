"""Semilla de las 8 fases y de las categorías de documentación.

Estas dos son catálogo del sistema y van en código, no en CSV: a diferencia de
las zonas y los códigos CAPEX, el cliente no los amplía —las fases del proceso
son la estructura de la aplicación— y sus banderas de comportamiento
(`status_is_derived`, `has_checklist`…) no son datos revisables en una hoja.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

#: `[REQ]` §3.1.5 · Las ocho fases, en su orden.
FASES: tuple[tuple[str, str, bool, bool, bool, bool, bool], ...] = (
    # code, nombre, checklist, enlace, visitas, rondas, derivado
    ("SOLICITUD_DOCUMENTACION", "Solicitud de documentación", True, False, False, False, False),
    ("VDR", "Generación del Virtual Data Room", False, True, False, False, False),
    ("VISITA", "Visita al activo", False, False, True, False, False),
    ("QA", "Q&A", False, False, False, True, False),
    ("RED_FLAG_CAPEX", "Red Flag / CAPEX", False, False, False, False, True),
    ("FULL_REPORT", "Full Report", False, False, False, False, True),
    ("PRESENTACION_CLIENTE", "Presentación a cliente", False, False, False, False, False),
    ("DEFENSA", "Defensa frente a la otra parte", False, False, False, False, False),
)

#: `[REQ]` §3.1.5 · Categorías de la solicitud de documentación. Ampliable.
CATEGORIAS_DOCUMENTACION: tuple[tuple[str, str], ...] = (
    ("LICENCIAS_URBANISTICAS", "Licencias urbanísticas"),
    ("PROYECTOS", "Proyectos"),
    ("CONTRATOS_MANTENIMIENTO", "Contratos de mantenimiento"),
    ("LEGALIZACIONES_CERTIFICADOS", "Legalizaciones y certificados"),
    ("GARANTIAS", "Garantías"),
)


def sembrar_fases(conn: Connection) -> tuple[int, int]:
    """Siembra las definiciones de fase y las categorías. Idempotente."""
    for orden, (code, nombre, chk, enlace, visitas, rondas, derivado) in enumerate(FASES, 1):
        conn.execute(
            text(
                "INSERT INTO phase_definition (code, name_es, display_order, has_checklist, "
                "has_external_link, has_visit_tracking, has_file_rounds, status_is_derived) "
                "VALUES (:c, :n, :o, :chk, :ext, :vis, :ron, :der) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {
                "c": code,
                "n": nombre,
                "o": orden,
                "chk": chk,
                "ext": enlace,
                "vis": visitas,
                "ron": rondas,
                "der": derivado,
            },
        )

    for orden, (code, nombre) in enumerate(CATEGORIAS_DOCUMENTACION, 1):
        conn.execute(
            text(
                "INSERT INTO doc_request_category (organization_id, code, name_es, "
                "display_order, is_system) VALUES (NULL, :c, :n, :o, TRUE) "
                "ON CONFLICT (organization_id, code) DO NOTHING"
            ),
            {"c": code, "n": nombre, "o": orden},
        )

    return len(FASES), len(CATEGORIAS_DOCUMENTACION)

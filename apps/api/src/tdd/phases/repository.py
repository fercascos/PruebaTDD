"""Puente entre la base de datos y el motor de fases.

El motor es puro y no sabe de SQL; este módulo le da los hechos. La separación
no es ceremonia: permite probar todos los casos límite del motor sin montar
medio proyecto, y deja este fichero reducido a consultas.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.phases.engine import HechosDelProyecto

_CONSULTA_HECHOS = text(
    """
    SELECT
      (SELECT count(*) FROM capex_item WHERE project_id = :p) AS lineas_capex,
      (SELECT count(*) FROM capex_item
        WHERE project_id = :p AND price_status = 'VALIDADO') AS lineas_validadas,
      (SELECT count(*) FROM asset WHERE project_id = :p AND deleted_at IS NULL) AS activos,
      (SELECT count(*) FROM asset_visit
        WHERE project_id = :p AND status = 'AGENDADO') AS visitas_agendadas,
      (SELECT count(*) FROM asset_visit
        WHERE project_id = :p AND status = 'VISITADO') AS visitas_realizadas,
      (SELECT count(*) FROM doc_request_item d
         JOIN project_phase ph ON ph.id = d.project_phase_id
        WHERE ph.project_id = :p) AS docs_solicitados,
      (SELECT count(*) FROM doc_request_item d
         JOIN project_phase ph ON ph.id = d.project_phase_id
        WHERE ph.project_id = :p
          AND d.status IN ('RECIBIDA', 'NO_DISPONIBLE', 'NO_APLICA')) AS docs_resueltos,
      (SELECT count(*) FROM qa_round q
         JOIN project_phase ph ON ph.id = q.project_phase_id
        WHERE ph.project_id = :p) AS rondas_qa,
      (SELECT count(*) FROM qa_round q
         JOIN project_phase ph ON ph.id = q.project_phase_id
        WHERE ph.project_id = :p AND q.status = 'CERRADA') AS rondas_cerradas,
      (SELECT count(*) > 0 FROM vdr_link v
         JOIN project_phase ph ON ph.id = v.project_phase_id
        WHERE ph.project_id = :p AND v.is_active) AS tiene_vdr,
      (SELECT count(*) FROM phase_event e
         JOIN project_phase ph ON ph.id = e.project_phase_id
        WHERE ph.project_id = :p) AS eventos
    """
)


def reunir_hechos(s: Session, project_id: uuid.UUID) -> HechosDelProyecto:
    """Cuenta lo que el motor necesita para calcular estados.

    `[LIM]` `versiones_de_informe` y `versiones_emitidas` van a cero mientras el
    módulo de informes no exista. La consecuencia es concreta y está probada:
    **la fase Full Report se queda en `PENDIENTE`**, que es lo correcto —todavía
    no se puede generar ningún informe— y no una cifra inventada. El motor ya
    implementa la regla completa; solo falta enchufarle el dato.
    """
    f = s.execute(_CONSULTA_HECHOS, {"p": project_id}).mappings().one()
    return HechosDelProyecto(
        lineas_capex=f["lineas_capex"],
        lineas_con_precio_validado=f["lineas_validadas"],
        versiones_de_informe=0,
        versiones_emitidas=0,
        documentos_solicitados=f["docs_solicitados"],
        documentos_resueltos=f["docs_resueltos"],
        activos=f["activos"],
        visitas_agendadas=f["visitas_agendadas"],
        visitas_realizadas=f["visitas_realizadas"],
        rondas_qa=f["rondas_qa"],
        rondas_qa_cerradas=f["rondas_cerradas"],
        tiene_enlace_vdr=bool(f["tiene_vdr"]),
        eventos_registrados=f["eventos"],
    )


def contar_para_transicion(s: Session, project_id: uuid.UUID) -> dict[str, int]:
    """Hechos para las guardas de la máquina de estados del proyecto."""
    f = (
        s.execute(
            text(
                """
            SELECT
              (SELECT count(*) FROM project WHERE id = :p AND client_id IS NOT NULL) AS clientes,
              (SELECT count(*) FROM asset
                WHERE project_id = :p AND deleted_at IS NULL) AS activos,
              (SELECT count(*) FROM asset_visit
                WHERE project_id = :p AND status = 'AGENDADO') AS agendadas,
              (SELECT count(*) FROM asset_visit
                WHERE project_id = :p AND status = 'VISITADO') AS realizadas
            """
            ),
            {"p": project_id},
        )
        .mappings()
        .one()
    )
    return dict(f)

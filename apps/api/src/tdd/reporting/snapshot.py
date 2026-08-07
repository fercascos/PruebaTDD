"""El snapshot del informe `[REQ]` §17.6.

> «Las partidas del informe deben corresponder a una versión concreta de los
> datos» y «un informe emitido debe quedar bloqueado; cualquier cambio
> posterior debe crear una nueva versión.»

**La generación lee del snapshot, no de la base de datos.** Es la decisión que
hace que un informe emitido siga siendo reproducible años después, y también la
que impide que un cambio concurrente —alguien editando un importe mientras otro
genera— produzca un documento incoherente consigo mismo.

`[REC]` El snapshot incluye **los catálogos usados**: nombres de códigos, zonas
y definiciones de riesgo vigentes en ese momento. Sin ello, retirar un código
CAPEX dos años después dejaría huecos en un informe ya entregado. Es la
diferencia entre archivar un PDF y poder reconstruir el informe.

El hash del snapshot se calcula sobre su forma canónica —claves ordenadas, sin
espacios— para que dos snapshots con el mismo contenido den el mismo hash
aunque se hayan serializado en distinto orden.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

#: Versión del formato del snapshot. Si cambia la estructura, un informe
#: antiguo debe seguir sabiendo cómo leerse.
VERSION_DE_FORMATO = 1


def _serializable(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        # Texto y no float: un importe en coma flotante deja de cuadrar al
        # sumarlo, y este es justo el sitio donde eso sería más caro.
        return str(valor)
    if isinstance(valor, uuid.UUID):
        return str(valor)
    if isinstance(valor, datetime):
        return valor.isoformat()
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return valor


def _filas(s: Session, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {k: _serializable(v) for k, v in fila.items()}
        for fila in s.execute(text(sql), params).mappings().all()
    ]


class ProyectoInexistente(LookupError):  # noqa: N818 — el dominio está en español
    """No hay proyecto con ese identificador **visible para quien pregunta**.

    Es una subclase propia y no un `LookupError` a secas porque la aplicación la
    traduce a un `404`: con la clase genérica habría que distinguirla de un
    `KeyError` cualquiera, que sí es un fallo de programación y debe seguir
    siendo un `500`.
    """


def huella(snapshot: dict[str, Any]) -> str:
    """SHA-256 de la forma canónica. Dos snapshots iguales dan el mismo hash."""
    canonico = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


#: `[REQ]` Estados de hallazgo que salen en un informe. Un borrador no debe
#: aparecer en un documento que se entrega al cliente.
ESTADOS_PUBLICABLES = ("EN_REVISION", "VALIDADO")

#: Todos los estados vivos. Lo usa la **exportación de trabajo** a XLSX: el
#: equipo comparte el CAPEX mientras todavía lo está construyendo, y un fichero
#: que se deja fuera las líneas en borrador da un total que no cuadra con la
#: pantalla desde la que se pulsó el botón.
#: `DESCARTADO` queda fuera: descartar una actuación es decir que no se hace, y
#: sumarla al total del fichero que se envía la resucitaría por la puerta de atrás.
ESTADOS_DE_TRABAJO = ("BORRADOR", "EN_REVISION", "VALIDADO")


def construir(
    s: Session,
    project_id: uuid.UUID,
    *,
    estados: tuple[str, ...] = ESTADOS_PUBLICABLES,
) -> dict[str, Any]:
    """Congela el proyecto entero: datos, hallazgos, fotos y **catálogos**.

    `estados` decide qué hallazgos entran. Por omisión, solo los publicables:
    cambiarlo es una decisión explícita de quien llama, y hoy solo la toma la
    exportación de trabajo a XLSX.
    """
    proyecto = (
        s.execute(
            text(
                "SELECT p.id, p.internal_code, p.name, CAST(p.status AS text) AS status, "
                "p.currency, p.report_due_date, c.name AS client_name "
                "FROM project p JOIN client c ON c.id = p.client_id WHERE p.id = :p"
            ),
            {"p": str(project_id)},
        )
        .mappings()
        .first()
    )
    if proyecto is None:
        # No existe, o la RLS no deja verlo porque es de otra organización: para
        # quien pregunta son lo mismo, y decirle cuál de las dos ya sería contar
        # algo. `main` lo traduce a un 404; antes salía un 500.
        raise ProyectoInexistente("Proyecto no encontrado")

    activos = _filas(
        s,
        "SELECT a.id, a.name, a.asset_code, a.city, a.address_line, a.year_built, "
        "a.year_last_refurb, a.total_built_sqm, a.plot_area_sqm, a.warehouse_area_sqm, "
        "a.office_area_sqm, a.warehouse_height_m, a.floors_above, a.floors_below, "
        "a.latitude, a.longitude, a.main_photo_id, t.name_es AS typology_name "
        "FROM asset a JOIN asset_typology t ON t.id = a.typology_id "
        "WHERE a.project_id = :p AND a.deleted_at IS NULL ORDER BY a.name",
        {"p": str(project_id)},
    )

    # El filtro de estados llega por parámetro: ver `ESTADOS_PUBLICABLES`.
    hallazgos = _filas(
        s,
        "SELECT f.id, f.asset_id, f.title, f.description, f.comments, f.recommendation, "
        "CAST(f.status AS text) AS status, "
        "CAST(f.tenant_recoverable AS text) AS tenant_recoverable, "
        "z.code AS zone_code, z.name_es AS zone_name, "
        "cc.code AS capex_code, cc.name_es AS capex_name, "
        # `[REQ]` Los ancestros viajan **resueltos** en el snapshot, no como una
        # referencia a resolver luego. La tabla del informe agrupa por tipo de
        # coste y por capítulo igual que la plantilla del cliente, y un informe
        # de hace seis meses tiene que poder reconstruirse aunque el catálogo
        # haya cambiado de nombre desde entonces.
        "tipo.code AS capex_type_code, tipo.name_es AS capex_type_name, "
        "cap.code AS capex_chapter_code, cap.name_es AS capex_chapter_name, "
        "CASE WHEN cc.level = 3 THEN cc.name_es END AS capex_item_name, "
        "rl.code AS risk_code, rl.name_es AS risk_name, rl.score AS risk_score, "
        "con.name_es AS concept_name "
        "FROM finding f "
        "JOIN zone z ON z.id = f.zone_id "
        "JOIN capex_code cc ON cc.id = f.capex_code_id "
        "LEFT JOIN capex_code tipo ON tipo.level = 1 "
        "  AND cc.path OPERATOR(public.<@) tipo.path "
        "  AND tipo.organization_id IS NOT DISTINCT FROM cc.organization_id "
        "LEFT JOIN capex_code cap ON cap.level = 2 "
        "  AND cc.path OPERATOR(public.<@) cap.path "
        "  AND cap.organization_id IS NOT DISTINCT FROM cc.organization_id "
        "LEFT JOIN risk_level rl ON rl.id = f.risk_level_id "
        "LEFT JOIN capex_concept con ON con.id = f.capex_concept_id "
        "WHERE f.project_id = :p AND f.deleted_at IS NULL "
        "  AND CAST(f.status AS text) = ANY(:estados) "
        "ORDER BY cc.code, f.created_at",
        {"p": str(project_id), "estados": list(estados)},
    )

    lineas = _filas(
        s,
        "SELECT ci.id, ci.finding_id, ci.amount, ci.tax_pct, ci.tax_amount, ci.total_cost, "
        "CAST(ci.price_status AS text) AS price_status, ci.measurement_unit, "
        "ci.measurement_quantity, ci.measurement_unit_price, "
        "th.code AS time_horizon_code, th.name_es AS time_horizon_name "
        "FROM capex_item ci "
        "JOIN time_horizon th ON th.id = ci.time_horizon_id "
        "JOIN finding f ON f.id = ci.finding_id "
        "WHERE ci.project_id = :p AND f.deleted_at IS NULL "
        "  AND CAST(f.status AS text) = ANY(:estados) "
        "ORDER BY th.sort_order",
        {"p": str(project_id), "estados": list(estados)},
    )

    # `[REQ]` §15.2 + §17.6 · La capa de anotaciones **vigente** viaja en el
    # snapshot. Si se leyera de la base al generar, volver a producir un informe
    # de hace seis meses recogería las anotaciones de hoy, y eso contradice lo
    # que significa congelar: el documento tiene que poder reconstruirse igual.
    fotos = _filas(
        s,
        "SELECT p.id, p.asset_id, p.zone_id, p.display_name, p.file_extension, p.caption, "
        "p.report_order, p.report_section, CAST(p.status AS text) AS status, p.taken_at, "
        "(SELECT pv.annotations FROM photo_version pv "
        "  WHERE pv.photo_id = p.id AND pv.is_current AND pv.annotations IS NOT NULL "
        "  ORDER BY pv.version_number DESC LIMIT 1) AS annotations "
        "FROM photo p WHERE p.project_id = :p AND p.deleted_at IS NULL AND p.include_in_report "
        "ORDER BY COALESCE(p.report_order, 2147483647), p.uploaded_at",
        {"p": str(project_id)},
    )

    limitaciones = _filas(
        s,
        "SELECT d.title, CAST(d.status AS text) AS status, d.unavailable_reason "
        "FROM doc_request_item d JOIN project_phase ph ON ph.id = d.project_phase_id "
        "WHERE ph.project_id = :p AND d.affects_report_limitations ORDER BY d.display_order",
        {"p": str(project_id)},
    ) + _filas(
        s,
        "SELECT q.question AS title, 'SIN_RESPUESTA' AS status, "
        "  'Pregunta sin respuesta del cliente' AS unavailable_reason "
        "FROM qa_question q JOIN qa_round r ON r.id = q.qa_round_id "
        "JOIN project_phase ph ON ph.id = r.project_phase_id "
        "WHERE ph.project_id = :p AND q.affects_report_limitations ORDER BY q.number",
        {"p": str(project_id)},
    )

    visitas = _filas(
        s,
        "SELECT v.asset_id, CAST(v.status AS text) AS status, v.actual_date, "
        "v.access_limitations FROM asset_visit v WHERE v.project_id = :p",
        {"p": str(project_id)},
    )

    # [REC] Los catálogos, tal como estaban HOY. Sin esto, retirar un código
    # dentro de dos años dejaría huecos en un informe ya entregado.
    # La RLS ya acota lo que se ve a las filas del sistema y las de la propia
    # organización, así que no hace falta filtrar aquí otra vez.
    catalogos = {
        # La definición íntegra del riesgo se vuelca al informe como leyenda:
        # sin ella, «Alto» es una palabra sin criterio detrás.
        "risk_levels": _filas(
            s, "SELECT code, name_es, score, definition_es FROM risk_level ORDER BY score", {}
        ),
        "time_horizons": _filas(
            s, "SELECT code, name_es, sort_order FROM time_horizon ORDER BY sort_order", {}
        ),
        # Solo los códigos y zonas realmente usados: copiar los 125 nodos del
        # árbol en cada informe engordaría el snapshot sin aportar nada.
        "capex_codes": _filas(
            s,
            "SELECT DISTINCT cc.code, cc.name_es, cc.level FROM capex_code cc "
            "JOIN finding f ON f.capex_code_id = cc.id "
            "WHERE f.project_id = :p AND f.deleted_at IS NULL ORDER BY cc.code",
            {"p": str(project_id)},
        ),
        "zones": _filas(
            s,
            "SELECT DISTINCT z.code, z.name_es FROM zone z "
            "JOIN finding f ON f.zone_id = z.id "
            "WHERE f.project_id = :p AND f.deleted_at IS NULL ORDER BY z.code",
            {"p": str(project_id)},
        ),
    }

    snapshot: dict[str, Any] = {
        "format_version": VERSION_DE_FORMATO,
        "generated_at": datetime.now(UTC).isoformat(),
        "project": {k: _serializable(v) for k, v in proyecto.items()},
        "assets": activos,
        "findings": hallazgos,
        "capex_items": lineas,
        "photos": fotos,
        "limitations": limitaciones,
        "visits": visitas,
        "catalogs": catalogos,
    }
    return snapshot


def totales_por_horizonte(snapshot: dict[str, Any]) -> dict[str, Decimal]:
    """Suma del CAPEX por plazo, **leída del snapshot**.

    Volver a consultarlo de la base daría un número distinto en cuanto alguien
    tocase un importe entre la generación y la consulta, y el informe dejaría
    de cuadrar consigo mismo.
    """
    totales: dict[str, Decimal] = {}
    for linea in snapshot.get("capex_items", []):
        codigo = linea["time_horizon_code"]
        totales[codigo] = totales.get(codigo, Decimal("0")) + Decimal(str(linea["amount"]))
    return totales


def comparar(anterior: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    """Diferencia entre dos versiones del informe `[REQ]` §17.6.

    Lo que de verdad se mira al comparar dos versiones: cuántos hallazgos
    entraron o salieron y **cuánto se movió el CAPEX en cada plazo**.
    """
    ids_antes = {h["id"] for h in anterior.get("findings", [])}
    ids_ahora = {h["id"] for h in actual.get("findings", [])}
    antes = totales_por_horizonte(anterior)
    ahora = totales_por_horizonte(actual)

    return {
        "findings_added": sorted(ids_ahora - ids_antes),
        "findings_removed": sorted(ids_antes - ids_ahora),
        "findings_before": len(ids_antes),
        "findings_after": len(ids_ahora),
        "capex_by_horizon": {
            codigo: {
                "before": str(antes.get(codigo, Decimal("0"))),
                "after": str(ahora.get(codigo, Decimal("0"))),
                "delta": str(ahora.get(codigo, Decimal("0")) - antes.get(codigo, Decimal("0"))),
            }
            for codigo in sorted(set(antes) | set(ahora))
        },
    }

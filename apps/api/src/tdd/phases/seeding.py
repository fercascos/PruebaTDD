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
    # `[REQ]` La primera de la lista, y no por orden alfabético: es el documento
    # del que salen los datos del edificio y el esqueleto del CAPEX. Pedirla
    # tarde retrasa todo lo demás, y el orden de la checklist es lo que le dice
    # al consultor por dónde empezar.
    ("MEMORIA_TECNICA", "Memoria técnica"),
    ("LICENCIAS_URBANISTICAS", "Licencias urbanísticas"),
    ("PROYECTOS", "Proyectos"),
    ("CONTRATOS_MANTENIMIENTO", "Contratos de mantenimiento"),
    ("LEGALIZACIONES_CERTIFICADOS", "Legalizaciones y certificados"),
    ("GARANTIAS", "Garantías"),
)

#: `[PDV]` Qué se le pide comprobar a la IA sobre cada documento recibido.
#:
#: Los cuatro criterios están **acordados en su enunciado y pendientes en su
#: detalle**: el cliente todavía tiene que decir qué hace exactamente que un
#: documento sea no conforme. Por eso son filas de catálogo y no constantes:
#: afinar la redacción, añadir un quinto o desactivar uno es un `UPDATE`.
#:
#: `description_es` no es documentación para quien lee el código: es el texto
#: que viaja al proveedor como parte de la instrucción. Cambiarlo cambia lo que
#: se revisa, y por eso se audita como dato y no se esconde en un `.py`.
TIPOS_DE_COMPROBACION: tuple[tuple[str, str, str], ...] = (
    (
        "CORRESPONDENCIA",
        "Corresponde con lo solicitado",
        "Comprueba si el documento es el que pide la línea de la checklist. Un "
        "certificado de baja tensión subido donde se pedía el proyecto de "
        "actividad es el fallo más frecuente y el más barato de detectar.",
    ),
    (
        "VIGENCIA",
        "Vigencia y caducidad",
        "Localiza las fechas de emisión, validez o caducidad y compáralas con la "
        "fecha del encargo. Cita siempre la fecha exacta que has leído y la "
        "página donde aparece: quien revise tiene que poder comprobarla.",
    ),
    (
        "COMPLETITUD",
        "Completitud",
        "Comprueba si faltan páginas, anexos, planos referenciados en el índice, "
        "firmas o sellos. Un documento de tres páginas cuyo índice anuncia "
        "cuarenta está incompleto aunque se lea perfectamente.",
    ),
    (
        "LEGIBILIDAD",
        "Legibilidad",
        "Comprueba si el documento se puede leer: escaneo con resolución "
        "suficiente, sin páginas giradas, cortadas ni en negro.",
    ),
)


def sembrar_fases(conn: Connection) -> tuple[int, int, int]:
    """Siembra las definiciones de fase, las categorías y los tipos de comprobación.

    Idempotente.
    """
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

    for orden, (code, nombre, descripcion) in enumerate(TIPOS_DE_COMPROBACION, 1):
        conn.execute(
            text(
                "INSERT INTO doc_check_type (organization_id, code, name_es, "
                "description_es, display_order, is_system) "
                "VALUES (NULL, :c, :n, :d, :o, TRUE) "
                "ON CONFLICT (organization_id, code) DO NOTHING"
            ),
            {"c": code, "n": nombre, "d": descripcion, "o": orden},
        )

    return len(FASES), len(CATEGORIAS_DOCUMENTACION), len(TIPOS_DE_COMPROBACION)

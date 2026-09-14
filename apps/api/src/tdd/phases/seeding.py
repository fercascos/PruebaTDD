"""Semilla de las 8 fases del proceso y de los tipos de comprobación documental.

Van en código y no en CSV: a diferencia de las zonas, los códigos CAPEX o el
árbol documental, el cliente no los amplía —las fases del proceso son la
estructura de la aplicación— y sus banderas de comportamiento
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
        "fecha del proyecto. Cita siempre la fecha exacta que has leído y la "
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


def sembrar_fases(conn: Connection) -> tuple[int, int]:
    """Siembra las definiciones de fase y los tipos de comprobación.

    Idempotente.

    Las **categorías de la solicitud documental ya no se siembran aquí**. Eran
    seis buckets de relleno escritos a mano —`MEMORIA_TECNICA`,
    `LICENCIAS_URBANISTICAS`…— puestos antes de que el cliente entregara su
    árbol. Ahora las 73 filas salen de `data/catalogos/arbol_documental.csv` y
    las carga `tdd.catalogs.seeding`, que es donde vive todo lo que viene de un
    CSV generado desde `docs/05`.
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

    return len(FASES), len(TIPOS_DE_COMPROBACION)

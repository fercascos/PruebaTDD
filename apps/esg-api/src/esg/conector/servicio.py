"""Importar lo que ha leído la IA, con la misma trazabilidad que un fichero.

Una factura leída por IA y una fila de un Excel acaban en la misma tabla, con
las mismas restricciones y la misma procedencia. Lo único que las distingue es
el `origen` y **la confianza**: por debajo del umbral, la lectura entra como
`PENDIENTE_REVISION` y no suma en ningún panel hasta que una persona la
confirma.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from esg.conector.puerto import FacturaLeida, LectorDeFacturas
from esg.indicadores.unidades import normalizar
from esg.ingesta.validacion import Incidencia


@dataclass
class ResultadoDeImportacion:
    carga_id: uuid.UUID
    facturas_leidas: int = 0
    confirmadas: int = 0
    pendientes_de_revision: int = 0
    rechazadas: int = 0
    incidencias: list[Incidencia] = field(default_factory=list)


def importar(
    session: Session,
    lector: LectorDeFacturas,
    *,
    desde: date,
    hasta: date,
    organizacion_id: uuid.UUID,
    usuario_id: uuid.UUID,
    confianza_minima: float = 0.85,
    paginas_maximas: int = 100,
) -> ResultadoDeImportacion:
    carga_id = session.execute(
        text(
            "INSERT INTO carga (organizacion_id, tipo, nombre, usuario_id, estado) "
            "VALUES (:org, 'CONECTOR', :nombre, :usuario, 'APLICADA') RETURNING id"
        ),
        {
            "org": organizacion_id,
            "nombre": f"Lector de facturas {desde.isoformat()} → {hasta.isoformat()}",
            "usuario": usuario_id,
        },
    ).scalar_one()
    resultado = ResultadoDeImportacion(carga_id=carga_id)

    catalogo = {
        (f["vector"], f["codigo"].strip().lower()): f["id"]
        for f in session.execute(
            text(
                "SELECT id, vector::text AS vector, codigo FROM punto_de_suministro "
                "WHERE borrado_en IS NULL"
            )
        ).mappings()
    }

    cursor: str | None = None
    for _ in range(paginas_maximas):
        lote = lector.facturas(desde=desde, hasta=hasta, cursor=cursor)
        for factura in lote.facturas:
            resultado.facturas_leidas += 1
            _importar_una(
                session,
                factura,
                catalogo=catalogo,
                carga_id=carga_id,
                organizacion_id=organizacion_id,
                usuario_id=usuario_id,
                confianza_minima=confianza_minima,
                resultado=resultado,
            )
        cursor = lote.siguiente
        if cursor is None:
            break
    else:
        # Un cursor que no termina nunca es un fallo del otro lado, y sin este
        # tope se traduciría en un proceso que no acaba y una tabla que crece.
        resultado.incidencias.append(
            Incidencia(
                None,
                None,
                "paginacion_sin_fin",
                f"El lector siguió dando páginas después de {paginas_maximas}: se paró aquí.",
            )
        )

    session.execute(
        text(
            "UPDATE carga SET filas_totales = :total, filas_aceptadas = :aceptadas, "
            "filas_rechazadas = :rechazadas WHERE id = :id"
        ),
        {
            "total": resultado.facturas_leidas,
            "aceptadas": resultado.confirmadas + resultado.pendientes_de_revision,
            "rechazadas": resultado.rechazadas,
            "id": carga_id,
        },
    )
    for incidencia in resultado.incidencias:
        session.execute(
            text(
                "INSERT INTO incidencia_de_carga (carga_id, organizacion_id, fila, columna, "
                "codigo, mensaje, valor) VALUES (:carga, :org, NULL, NULL, :codigo, :mensaje, "
                ":valor)"
            ),
            {
                "carga": carga_id,
                "org": organizacion_id,
                "codigo": incidencia.codigo,
                "mensaje": incidencia.mensaje,
                "valor": incidencia.valor,
            },
        )
    return resultado


def _importar_una(
    session: Session,
    factura: FacturaLeida,
    *,
    catalogo: dict[tuple[str, str], uuid.UUID],
    carga_id: uuid.UUID,
    organizacion_id: uuid.UUID,
    usuario_id: uuid.UUID,
    confianza_minima: float,
    resultado: ResultadoDeImportacion,
) -> None:
    punto = catalogo.get((factura.vector, factura.suministro.strip().lower()))
    if punto is None:
        resultado.rechazadas += 1
        resultado.incidencias.append(
            Incidencia(
                None,
                None,
                "suministro_desconocido",
                f"La factura {factura.referencia} es de un suministro de {factura.vector} "
                "que no está dado de alta.",
                factura.suministro,
            )
        )
        return

    normal = normalizar(
        factura.vector, factura.cantidad, factura.unidad, factor_gas=factura.factor_gas
    )
    dudosa = factura.confianza < confianza_minima
    estado = "PENDIENTE_REVISION" if dudosa else "CONFIRMADA"
    nota = json.dumps(
        {
            "confianza": factura.confianza,
            "por_campo": factura.confianza_por_campo,
            "documento": factura.documento_url,
        },
        ensure_ascii=False,
    )
    try:
        with session.begin_nested():
            session.execute(
                text(
                    "INSERT INTO lectura (organizacion_id, punto_id, inicio, fin, cantidad, "
                    "unidad, cantidad_normalizada, unidad_normalizada, factor_de_conversion, "
                    "calidad, origen, estado, confianza, importe, moneda, carga_id, "
                    "referencia_externa, nota, creado_por) "
                    "VALUES (:org, :punto, :inicio, :fin, :cantidad, :unidad, :normal, "
                    ":unidad_normal, :factor, 'MEDIDO', 'FACTURA_IA', "
                    "CAST(:estado AS estado_lectura), :confianza, :importe, :moneda, :carga, "
                    ":referencia, :nota, :usuario)"
                ),
                {
                    "org": organizacion_id,
                    "punto": punto,
                    "inicio": factura.inicio,
                    "fin": factura.fin,
                    "cantidad": factura.cantidad,
                    "unidad": factura.unidad,
                    "normal": normal.cantidad,
                    "unidad_normal": normal.unidad if normal.cantidad is not None else None,
                    "factor": normal.factor,
                    "estado": estado,
                    "confianza": round(factura.confianza, 3),
                    "importe": factura.importe,
                    "moneda": factura.moneda,
                    "carga": carga_id,
                    "referencia": factura.referencia,
                    "nota": nota,
                    "usuario": usuario_id,
                },
            )
    except IntegrityError as exc:
        resultado.rechazadas += 1
        detalle = str(exc.orig)
        if "lectura_referencia_externa_unica" in detalle:
            mensaje = "Esa factura ya estaba importada."
        elif "sin_solape_por_suministro" in detalle:
            mensaje = (
                "Ya hay una lectura de ese suministro que cubre parte del mismo periodo. "
                "Puede ser la misma factura cargada antes desde un fichero."
            )
        else:
            mensaje = detalle.strip()[:300]
        resultado.incidencias.append(
            Incidencia(None, None, "factura_rechazada", mensaje, factura.referencia)
        )
        return

    if dudosa:
        resultado.pendientes_de_revision += 1
    else:
        resultado.confirmadas += 1
    if normal.cantidad is None:
        resultado.incidencias.append(
            Incidencia(
                None,
                None,
                "sin_normalizar",
                f"Factura {factura.referencia}: se guarda pero no suma. {normal.motivo}",
                factura.unidad,
            )
        )

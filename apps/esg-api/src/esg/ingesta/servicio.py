"""Aplicar una carga de consumos contra la base de datos.

Dos modos, y el que importa es el primero:

* **Simular** — se hace todo de verdad, incluida la escritura, y al final se
  deshace. No es una comprobación aproximada: los solapes y los duplicados los
  detecta la base de datos intentándolo. Una simulación que solo mira el
  fichero diría «1.200 filas correctas» y la carga real fallaría en la 37.
* **Aplicar** — lo mismo, sin deshacerlo.

Lo que esta carga **no** hace es dar de alta activos ni suministros. Un fichero
con un CUPS que no existe produce una incidencia, no un suministro nuevo: el
inventario lo mantiene quien responde de él, y un CUPS mal tecleado que se da
de alta solo se convierte en un activo fantasma con consumo real dentro.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from esg.indicadores.unidades import normalizar
from esg.ingesta.lectura_tabular import FicheroIlegible, leer, sha256
from esg.ingesta.mapeo import Mapeo, proponer
from esg.ingesta.validacion import Incidencia, analizar_fila


@dataclass
class ResultadoDeCarga:
    carga_id: uuid.UUID | None
    aplicada: bool
    filas_totales: int = 0
    filas_aceptadas: int = 0
    filas_rechazadas: int = 0
    #: Lecturas que entraron pero **no se pueden agregar todavía** (gas en m³
    #: sin poder calorífico, unidad desconocida). No son un error de carga.
    filas_sin_normalizar: int = 0
    incidencias: list[Incidencia] = field(default_factory=list)
    mapeo: Mapeo | None = None
    ya_cargado_antes: bool = False


def _suministros(session: Session) -> dict[tuple[str, str], dict[str, Any]]:
    filas = session.execute(
        text(
            "SELECT id, vector::text AS vector, codigo, activo_id "
            "FROM punto_de_suministro WHERE borrado_en IS NULL"
        )
    ).mappings()
    return {(f["vector"], f["codigo"].strip().lower()): dict(f) for f in filas}


def procesar(
    session: Session,
    *,
    contenido: bytes,
    nombre: str,
    organizacion_id: uuid.UUID,
    usuario_id: uuid.UUID,
    hoja: str | None = None,
    mapeo: Mapeo | None = None,
    vector_por_defecto: str | None = None,
    aplicar: bool = False,
) -> ResultadoDeCarga:
    huella = sha256(contenido)
    ya = session.execute(
        text("SELECT count(*) FROM carga WHERE hash_sha256 = :h AND estado = 'APLICADA'"),
        {"h": huella},
    ).scalar_one()

    try:
        tabla = leer(contenido, nombre=nombre, hoja=hoja)
    except FicheroIlegible as exc:
        return ResultadoDeCarga(
            carga_id=None,
            aplicada=False,
            incidencias=[Incidencia(None, None, "fichero_ilegible", str(exc))],
            ya_cargado_antes=bool(ya),
        )

    mapeo = mapeo or proponer(tabla.cabeceras, vector_por_defecto=vector_por_defecto)
    if not mapeo.completo:
        return ResultadoDeCarga(
            carga_id=None,
            aplicada=False,
            filas_totales=len(tabla.filas),
            mapeo=mapeo,
            ya_cargado_antes=bool(ya),
            incidencias=[
                Incidencia(
                    None,
                    None,
                    "mapeo_incompleto",
                    "Faltan columnas por emparejar: " + ", ".join(mapeo.faltan),
                )
            ],
        )

    carga_id = session.execute(
        text(
            "INSERT INTO carga (organizacion_id, tipo, nombre, hash_sha256, hoja, mapeo, "
            "usuario_id, estado, filas_totales) "
            "VALUES (:org, 'FICHERO', :nombre, :hash, :hoja, CAST(:mapeo AS jsonb), :usuario, "
            "'SIMULADA', :filas) RETURNING id"
        ),
        {
            "org": organizacion_id,
            "nombre": nombre,
            "hash": huella,
            "hoja": tabla.hoja,
            "mapeo": _mapeo_json(mapeo),
            "usuario": usuario_id,
            "filas": len(tabla.filas),
        },
    ).scalar_one()

    resultado = ResultadoDeCarga(
        carga_id=carga_id,
        aplicada=aplicar,
        filas_totales=len(tabla.filas),
        mapeo=mapeo,
        ya_cargado_antes=bool(ya),
    )
    catalogo = _suministros(session)

    # Todo lo que escribe lecturas va dentro de este punto de guardado: en
    # simulación se deshace entero, y las incidencias —que se guardan después—
    # sobreviven. Así el informe de la simulación se puede volver a abrir.
    punto_de_guardado = session.begin_nested()
    for numero, fila in tabla.filas:
        lectura, problemas = analizar_fila(numero, fila, mapeo)
        resultado.incidencias.extend(problemas)
        if lectura is None:
            resultado.filas_rechazadas += 1
            continue

        clave = (lectura.vector, lectura.suministro.strip().lower())
        suministro = catalogo.get(clave)
        if suministro is None:
            resultado.filas_rechazadas += 1
            resultado.incidencias.append(
                Incidencia(
                    numero,
                    mapeo.columna("suministro"),
                    "suministro_desconocido",
                    f"No hay ningún suministro de {lectura.vector} con ese código. "
                    "Déselo de alta en el activo antes de cargar sus consumos.",
                    lectura.suministro,
                )
            )
            continue

        normal = normalizar(
            lectura.vector, lectura.cantidad, lectura.unidad, factor_gas=lectura.factor_gas
        )
        if normal.cantidad is None:
            resultado.filas_sin_normalizar += 1
            resultado.incidencias.append(
                Incidencia(
                    numero,
                    mapeo.columna("unidad"),
                    "sin_normalizar",
                    f"La lectura se guarda pero no entra en las sumas: {normal.motivo}",
                    lectura.unidad,
                )
            )

        try:
            with session.begin_nested():
                session.execute(
                    text(
                        "INSERT INTO lectura (organizacion_id, punto_id, inicio, fin, cantidad, "
                        "unidad, cantidad_normalizada, unidad_normalizada, factor_de_conversion, "
                        "calidad, origen, estado, importe, moneda, carga_id, fila_origen, "
                        "referencia_externa, creado_por) "
                        "VALUES (:org, :punto, :inicio, :fin, :cantidad, :unidad, :normal, "
                        ":unidad_normal, :factor, CAST(:calidad AS calidad_lectura), 'FICHERO', "
                        "'CONFIRMADA', :importe, :moneda, :carga, :fila, :referencia, :usuario)"
                    ),
                    {
                        "org": organizacion_id,
                        "punto": suministro["id"],
                        "inicio": lectura.inicio,
                        "fin": lectura.fin,
                        "cantidad": lectura.cantidad,
                        "unidad": lectura.unidad,
                        "normal": normal.cantidad,
                        "unidad_normal": normal.unidad if normal.cantidad is not None else None,
                        "factor": normal.factor,
                        "calidad": lectura.calidad,
                        "importe": lectura.importe,
                        "moneda": (lectura.moneda or None),
                        "carga": carga_id,
                        "fila": numero,
                        "referencia": lectura.referencia,
                        "usuario": usuario_id,
                    },
                )
        except IntegrityError as exc:
            resultado.filas_rechazadas += 1
            resultado.incidencias.append(_incidencia_de_integridad(numero, mapeo, lectura, exc))
            continue
        resultado.filas_aceptadas += 1

    if aplicar:
        punto_de_guardado.commit()
    else:
        punto_de_guardado.rollback()

    for incidencia in resultado.incidencias:
        session.execute(
            text(
                "INSERT INTO incidencia_de_carga (carga_id, organizacion_id, fila, columna, "
                "codigo, mensaje, valor) VALUES (:carga, :org, :fila, :columna, :codigo, "
                ":mensaje, :valor)"
            ),
            {
                "carga": carga_id,
                "org": organizacion_id,
                "fila": incidencia.fila,
                "columna": incidencia.columna,
                "codigo": incidencia.codigo,
                "mensaje": incidencia.mensaje,
                "valor": incidencia.valor,
            },
        )
    session.execute(
        text(
            "UPDATE carga SET estado = CAST(:estado AS estado_carga), "
            "filas_aceptadas = :aceptadas, filas_rechazadas = :rechazadas WHERE id = :id"
        ),
        {
            "estado": "APLICADA" if aplicar else "SIMULADA",
            "aceptadas": resultado.filas_aceptadas,
            "rechazadas": resultado.filas_rechazadas,
            "id": carga_id,
        },
    )
    return resultado


def _incidencia_de_integridad(
    numero: int, mapeo: Mapeo, lectura: Any, exc: IntegrityError
) -> Incidencia:
    """Traduce el error de PostgreSQL a algo que se pueda arreglar.

    El texto de un `ExclusionViolation` no se le enseña a nadie: lo que hay que
    decir es «este periodo ya está cargado para este suministro», que es la
    frase que lleva a mirar si el fichero se está subiendo dos veces.
    """
    detalle = str(exc.orig)
    if "sin_solape_por_suministro" in detalle:
        return Incidencia(
            numero,
            mapeo.columna("inicio"),
            "periodo_solapado",
            "Ya hay una lectura de ese suministro que cubre parte de este periodo. "
            "Suele significar que el fichero ya se cargó, entero o en parte.",
            f"{lectura.inicio} → {lectura.fin}",
        )
    if "lectura_referencia_externa_unica" in detalle:
        return Incidencia(
            numero,
            mapeo.columna("referencia"),
            "factura_repetida",
            "Esa factura ya está cargada.",
            lectura.referencia,
        )
    return Incidencia(numero, None, "rechazada_por_la_base", detalle.strip()[:300])


def _mapeo_json(mapeo: Mapeo) -> str:
    import json

    return json.dumps(
        {
            "columnas": mapeo.columnas,
            "fin_inclusivo": mapeo.fin_inclusivo,
            "vector_por_defecto": mapeo.vector_por_defecto,
        },
        ensure_ascii=False,
    )

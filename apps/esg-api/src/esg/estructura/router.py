"""Carteras, activos y suministros: el inventario sobre el que se agrega todo."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from esg.core.deps import EscrituraEstructuraDep, SesionDep, UsuarioDep
from esg.core.errores import NO_PROCESABLE
from esg.estructura.esquemas import (
    AMBITOS,
    CRITERIOS,
    TIPOLOGIAS,
    VECTORES_ADMITIDOS,
    ActivoFuera,
    CarteraFuera,
    NuevaCartera,
    NuevoActivo,
    NuevoSuministro,
    OcupacionEntra,
    SuministroFuera,
    validar_enumerado,
)

router = APIRouter(prefix="/api/v1", tags=["estructura"])


@router.get("/carteras", response_model=list[CarteraFuera])
def listar_carteras(sesion: SesionDep, usuario: UsuarioDep) -> list[CarteraFuera]:
    """Las carteras que **este** usuario ve.

    No hay ningún filtro por usuario en esta consulta: lo pone la RLS. Un
    cliente con ámbito sobre una cartera ve una fila; sin ámbito, ninguna.
    """
    filas = sesion.execute(
        text(
            "SELECT c.id, c.nombre, c.codigo, c.cliente_id, cl.nombre AS cliente, "
            "       c.superficie_de_referencia::text AS superficie_de_referencia, "
            "       (SELECT count(*) FROM activo a "
            "          WHERE a.cartera_id = c.id AND a.borrado_en IS NULL) AS activos "
            "FROM cartera c LEFT JOIN cliente cl ON cl.id = c.cliente_id "
            "WHERE c.borrado_en IS NULL ORDER BY c.nombre"
        )
    ).mappings()
    return [CarteraFuera(**f) for f in filas]


@router.post("/carteras", response_model=CarteraFuera, status_code=status.HTTP_201_CREATED)
def crear_cartera(
    datos: NuevaCartera, sesion: SesionDep, usuario: EscrituraEstructuraDep
) -> CarteraFuera:
    validar_enumerado(datos.superficie_de_referencia, CRITERIOS, "superficie_de_referencia")
    try:
        fila = sesion.execute(
            text(
                "INSERT INTO cartera (organizacion_id, cliente_id, nombre, codigo, "
                "superficie_de_referencia) VALUES (:org, :cliente, :nombre, :codigo, "
                "CAST(:criterio AS superficie_referencia)) RETURNING id"
            ),
            {
                "org": usuario.organizacion_id,
                "cliente": datos.cliente_id,
                "nombre": datos.nombre,
                "codigo": datos.codigo,
                "criterio": datos.superficie_de_referencia,
            },
        ).scalar_one()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Ya hay una cartera con el código «{datos.codigo}»"
        ) from exc
    return CarteraFuera(
        id=fila,
        nombre=datos.nombre,
        codigo=datos.codigo,
        cliente_id=datos.cliente_id,
        cliente=None,
        superficie_de_referencia=datos.superficie_de_referencia,
        activos=0,
    )


@router.get("/activos", response_model=list[ActivoFuera])
def listar_activos(
    sesion: SesionDep,
    usuario: UsuarioDep,
    cartera: uuid.UUID | None = None,
    tipologia: str | None = None,
) -> list[ActivoFuera]:
    condiciones = ["a.borrado_en IS NULL"]
    parametros: dict[str, object] = {}
    if cartera:
        condiciones.append("a.cartera_id = :cartera")
        parametros["cartera"] = cartera
    if tipologia:
        condiciones.append("a.tipologia::text = :tipologia")
        parametros["tipologia"] = tipologia
    filas = sesion.execute(
        text(
            "SELECT a.id, a.cartera_id, c.nombre AS cartera, a.codigo, a.nombre, a.municipio, "
            "       a.tipologia::text AS tipologia, "
            "       COALESCE(a.superficie_de_referencia, c.superficie_de_referencia)::text "
            "         AS superficie_de_referencia, "
            "       CASE COALESCE(a.superficie_de_referencia, c.superficie_de_referencia) "
            "            WHEN 'BRUTA' THEN a.superficie_bruta_m2 "
            "            WHEN 'ALQUILABLE' THEN a.superficie_alquilable_m2 "
            "            ELSE a.superficie_ocupada_m2 END AS superficie_m2, "
            "       (SELECT count(*) FROM punto_de_suministro p "
            "          WHERE p.activo_id = a.id AND p.borrado_en IS NULL) AS suministros "
            "FROM activo a JOIN cartera c ON c.id = a.cartera_id "
            f"WHERE {' AND '.join(condiciones)} ORDER BY a.codigo"
        ),
        parametros,
    ).mappings()
    return [ActivoFuera(**f) for f in filas]


@router.post("/activos", response_model=ActivoFuera, status_code=status.HTTP_201_CREATED)
def crear_activo(
    datos: NuevoActivo, sesion: SesionDep, usuario: EscrituraEstructuraDep
) -> ActivoFuera:
    validar_enumerado(datos.tipologia, TIPOLOGIAS, "tipologia")
    if datos.superficie_de_referencia:
        validar_enumerado(datos.superficie_de_referencia, CRITERIOS, "superficie_de_referencia")
    try:
        sesion.execute(
            text(
                "INSERT INTO activo (organizacion_id, cartera_id, codigo, nombre, direccion, "
                "municipio, pais, tipologia, superficie_bruta_m2, superficie_alquilable_m2, "
                "superficie_ocupada_m2, superficie_de_referencia, anio_construccion, "
                "incorporado_en) VALUES (:org, :cartera, :codigo, :nombre, :direccion, "
                ":municipio, :pais, CAST(:tipologia AS tipologia_activo), :bruta, :alquilable, "
                ":ocupada, CAST(:criterio AS superficie_referencia), :anio, :incorporado)"
            ),
            {
                "org": usuario.organizacion_id,
                "cartera": datos.cartera_id,
                "codigo": datos.codigo,
                "nombre": datos.nombre,
                "direccion": datos.direccion,
                "municipio": datos.municipio,
                "pais": datos.pais,
                "tipologia": datos.tipologia,
                "bruta": datos.superficie_bruta_m2,
                "alquilable": datos.superficie_alquilable_m2,
                "ocupada": datos.superficie_ocupada_m2,
                "criterio": datos.superficie_de_referencia,
                "anio": datos.anio_construccion,
                "incorporado": datos.incorporado_en,
            },
        )
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ya hay un activo con el código «{datos.codigo}», o la cartera no existe",
        ) from exc
    creados = listar_activos(sesion, usuario, cartera=datos.cartera_id)
    return next(a for a in creados if a.codigo == datos.codigo)


@router.get("/suministros", response_model=list[SuministroFuera])
def listar_suministros(
    sesion: SesionDep,
    usuario: UsuarioDep,
    activo: uuid.UUID | None = None,
    vector: str | None = Query(default=None),
) -> list[SuministroFuera]:
    condiciones = ["p.borrado_en IS NULL"]
    parametros: dict[str, object] = {}
    if activo:
        condiciones.append("p.activo_id = :activo")
        parametros["activo"] = activo
    if vector:
        condiciones.append("p.vector::text = :vector")
        parametros["vector"] = vector
    filas = sesion.execute(
        text(
            "SELECT p.id, p.activo_id, p.vector::text AS vector, p.codigo, p.descripcion, "
            "       p.ambito::text AS ambito, p.unidad_de_factura, "
            "       p.fraccion::text AS fraccion, p.alta_en, p.baja_en, "
            "       (SELECT count(*) FROM lectura l "
            "          WHERE l.punto_id = p.id AND l.estado <> 'DESCARTADA') AS lecturas "
            f"FROM punto_de_suministro p WHERE {' AND '.join(condiciones)} "
            "ORDER BY p.vector, p.codigo"
        ),
        parametros,
    ).mappings()
    return [SuministroFuera(**f) for f in filas]


@router.post("/suministros", response_model=SuministroFuera, status_code=status.HTTP_201_CREATED)
def crear_suministro(
    datos: NuevoSuministro, sesion: SesionDep, usuario: EscrituraEstructuraDep
) -> SuministroFuera:
    validar_enumerado(datos.vector, VECTORES_ADMITIDOS, "vector")
    validar_enumerado(datos.ambito, AMBITOS, "ambito")
    try:
        identificador = sesion.execute(
            text(
                "INSERT INTO punto_de_suministro (organizacion_id, activo_id, vector, codigo, "
                "descripcion, ambito, comercializadora, unidad_de_factura, fraccion, alta_en, "
                "baja_en) VALUES (:org, :activo, CAST(:vector AS vector_esg), :codigo, "
                ":descripcion, CAST(:ambito AS ambito_suministro), :comercializadora, :unidad, "
                "CAST(:fraccion AS fraccion_residuo), :alta, :baja) RETURNING id"
            ),
            {
                "org": usuario.organizacion_id,
                "activo": datos.activo_id,
                "vector": datos.vector,
                "codigo": datos.codigo,
                "descripcion": datos.descripcion,
                "ambito": datos.ambito,
                "comercializadora": datos.comercializadora,
                "unidad": datos.unidad_de_factura,
                "fraccion": datos.fraccion,
                "alta": datos.alta_en,
                "baja": datos.baja_en,
            },
        ).scalar_one()
    except IntegrityError as exc:
        detalle = str(exc.orig)
        if "fraccion_solo_en_residuos" in detalle:
            raise HTTPException(
                NO_PROCESABLE,
                "La fracción de residuo solo tiene sentido en un suministro de RESIDUOS",
            ) from exc
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Ya hay un suministro de {datos.vector} con el código «{datos.codigo}»",
        ) from exc
    return SuministroFuera(
        id=identificador,
        activo_id=datos.activo_id,
        vector=datos.vector,
        codigo=datos.codigo,
        descripcion=datos.descripcion,
        ambito=datos.ambito,
        unidad_de_factura=datos.unidad_de_factura,
        fraccion=datos.fraccion,
        alta_en=datos.alta_en,
        baja_en=datos.baja_en,
        lecturas=0,
    )


@router.put("/activos/{activo_id}/ocupacion", status_code=status.HTTP_204_NO_CONTENT)
def fijar_ocupacion(
    activo_id: uuid.UUID,
    meses: list[OcupacionEntra],
    sesion: SesionDep,
    usuario: EscrituraEstructuraDep,
) -> None:
    """Ocupación media por mes. Se sustituye la del mes, no se acumula."""
    for mes in meses:
        if mes.mes.day != 1:
            raise HTTPException(
                NO_PROCESABLE,
                f"La ocupación se declara por mes: use el día 1 ({mes.mes.isoformat()})",
            )
        sesion.execute(
            text(
                "INSERT INTO ocupacion (organizacion_id, activo_id, mes, ocupantes_medios) "
                "VALUES (:org, :activo, :mes, :ocupantes) "
                "ON CONFLICT (activo_id, mes) DO UPDATE "
                "SET ocupantes_medios = EXCLUDED.ocupantes_medios"
            ),
            {
                "org": usuario.organizacion_id,
                "activo": activo_id,
                "mes": mes.mes,
                "ocupantes": mes.ocupantes_medios,
            },
        )

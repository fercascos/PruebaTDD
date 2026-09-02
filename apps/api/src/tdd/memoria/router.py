"""API de la memoria técnica y del esqueleto de CAPEX que genera."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core.deps import SesionDep, UsuarioDep

router = APIRouter(tags=["Memoria técnica"])

#: Los campos del activo que la memoria puede proponer. La lista está escrita y
#: no se deduce del modelo a propósito: una propuesta solo puede tocar datos
#: **del edificio**. Sin este cerco, una extracción podría cambiar el nombre del
#: activo, su tipología o su proyecto, y el botón de validar estaría aceptando
#: mucho más de lo que la persona cree.
CAMPOS_PROPONIBLES = (
    "main_use",
    "secondary_use",
    "address_line",
    "city",
    "province",
    "postal_code",
    "cadastral_reference",
    "developer",
    "project_date",
    "year_built",
    "year_last_refurb",
    "plot_area_sqm",
    "total_built_sqm",
    "lettable_area_sqm",
    "usable_area_sqm",
    "occupied_area_sqm",
    "urbanised_area_sqm",
    "warehouse_area_sqm",
    "office_area_sqm",
    "warehouse_height_m",
    "max_height_m",
    "floors_above",
    "floors_below",
    "loading_docks",
    "parking_spaces",
)

#: La zona con la que nace una fila del esqueleto. `GENERAL` existe en las seis
#: tipologías —se comprueba en `test_catalogos`—, así que sirve para cualquier
#: edificio. No se adivina la zona real: la memoria enumera objetos, no dice
#: dónde están, y poner una zona inventada la haría pasar por sabida.
ZONA_DE_ARRANQUE = "GENERAL"


class ObjetoDeMemoria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: El elemento del catálogo, si lo hay. Nulo cuando la memoria nombra algo
    #: que el catálogo no tiene: perderlo sería tirar lo que el gestor necesita
    #: para acordarse de revisarlo.
    capex_code_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=240)
    cantidad: Decimal | None = Field(default=None, ge=0)
    unidad: str | None = Field(default=None, max_length=20)
    notes: str | None = None


class CategoriaDeMemoria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Un capítulo del catálogo (nivel 2). Los 15 de Hard Costs son los que el
    #: cliente llama «las categorías del CAPEX».
    capex_code_id: uuid.UUID
    notes: str | None = None
    objetos: list[ObjetoDeMemoria] = Field(default_factory=list)


class ContenidoDeMemoria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Los datos del edificio que la memoria propone, **sin aplicar**.
    propuesta: dict[str, Any] = Field(default_factory=dict)
    categorias: list[CategoriaDeMemoria] = Field(default_factory=list)
    document_id: uuid.UUID | None = None
    origen: str | None = Field(default=None, max_length=60)
    #: Por omisión **sí**: lo que entra sin declararse se trata como simulado.
    #: Al revés, una extracción de mentira pasaría por una de verdad si a algún
    #: llamador se le olvida el campo.
    es_simulada: bool = True
    notes: str | None = None


class ObjetoLeido(ObjetoDeMemoria):
    id: uuid.UUID
    capex_code: str | None = None


class CategoriaLeida(BaseModel):
    id: uuid.UUID
    capex_code_id: uuid.UUID
    capex_code: str
    capex_name: str
    notes: str | None
    objetos: list[ObjetoLeido]


class MemoriaLeida(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    document_id: uuid.UUID | None
    status: str
    origen: str | None
    es_simulada: bool
    extraida_at: Any = None
    validada_at: Any = None
    validada_por: uuid.UUID | None = None
    propuesta: dict[str, Any]
    notes: str | None
    row_version: int
    categorias: list[CategoriaLeida]


# ─────────────────────────────────────────────────────────────────────────────
#  Lectura
# ─────────────────────────────────────────────────────────────────────────────


def _activo(s: Session, asset_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text(
                "SELECT id, project_id, typology_id FROM asset WHERE id = :a AND deleted_at IS NULL"
            ),
            {"a": str(asset_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activo no encontrado")
    return dict(fila)


def _leer(s: Session, asset_id: uuid.UUID) -> dict[str, Any]:
    memoria = (
        s.execute(
            text(
                "SELECT id, asset_id, document_id, CAST(status AS text) AS status, origen, "
                "es_simulada, extraida_at, validada_at, validada_por, propuesta, notes, "
                "row_version FROM memoria_tecnica WHERE asset_id = :a"
            ),
            {"a": str(asset_id)},
        )
        .mappings()
        .first()
    )
    if memoria is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Este activo todavía no tiene memoria técnica"
        )

    categorias = (
        s.execute(
            text(
                "SELECT mc.id, mc.capex_code_id, mc.notes, cc.code AS capex_code, "
                "cc.name_es AS capex_name FROM memoria_categoria mc "
                "JOIN capex_code cc ON cc.id = mc.capex_code_id "
                "WHERE mc.memoria_id = :m ORDER BY mc.orden, cc.code"
            ),
            {"m": str(memoria["id"])},
        )
        .mappings()
        .all()
    )
    objetos = (
        s.execute(
            text(
                "SELECT mo.id, mo.memoria_categoria_id, mo.capex_code_id, mo.nombre, "
                "mo.cantidad, mo.unidad, mo.notes, cc.code AS capex_code "
                "FROM memoria_objeto mo "
                "LEFT JOIN capex_code cc ON cc.id = mo.capex_code_id "
                "WHERE mo.memoria_categoria_id = ANY(:ids) ORDER BY mo.orden, mo.nombre"
            ),
            {"ids": [c["id"] for c in categorias]},
        )
        .mappings()
        .all()
    )
    por_categoria: dict[Any, list[dict[str, Any]]] = {}
    for o in objetos:
        fila = {k: v for k, v in o.items() if k != "memoria_categoria_id"}
        por_categoria.setdefault(o["memoria_categoria_id"], []).append(fila)

    return {
        **dict(memoria),
        "categorias": [{**dict(c), "objetos": por_categoria.get(c["id"], [])} for c in categorias],
    }


@router.get("/assets/{asset_id}/memoria", response_model=MemoriaLeida)
def leer(asset_id: uuid.UUID, s: SesionDep) -> Any:
    _activo(s, asset_id)
    return _leer(s, asset_id)


# ─────────────────────────────────────────────────────────────────────────────
#  Escritura
# ─────────────────────────────────────────────────────────────────────────────


def _validar_codigos(s: Session, cuerpo: ContenidoDeMemoria) -> None:
    """Que las categorías sean capítulos y los objetos, elementos.

    La comprobación está aquí y no en un `CHECK` porque exigiría consultar otra
    tabla desde un disparador, y eso encarece cada escritura para una regla que
    no cambia. Lo que no puede pasar es que no se compruebe en ningún sitio: una
    categoría que en realidad es un elemento produce un esqueleto con la
    jerarquía del revés, y eso se ve al final, en el Excel del cliente.
    """
    niveles = {
        fila[0]: fila[1]
        for fila in s.execute(
            text("SELECT id, level FROM capex_code WHERE id = ANY(:ids)"),
            {
                "ids": [str(c.capex_code_id) for c in cuerpo.categorias]
                + [
                    str(o.capex_code_id)
                    for c in cuerpo.categorias
                    for o in c.objetos
                    if o.capex_code_id
                ]
            },
        ).all()
    }
    for c in cuerpo.categorias:
        nivel = niveles.get(c.capex_code_id)
        if nivel is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"El código de categoría {c.capex_code_id} no existe",
            )
        if nivel != 2:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Una categoría de la memoria tiene que ser un capítulo del catálogo "
                f"(nivel 2). El código {c.capex_code_id} es de nivel {nivel}.",
            )
        vistos: set[str] = set()
        for o in c.objetos:
            if o.nombre in vistos:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"El objeto «{o.nombre}» aparece dos veces en la misma categoría",
                )
            vistos.add(o.nombre)
            if o.capex_code_id and niveles.get(o.capex_code_id) != 3:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"El objeto «{o.nombre}» apunta a un código que no es un elemento "
                    "del catálogo (nivel 3)",
                )


def _propuesta_limpia(propuesta: dict[str, Any]) -> dict[str, Any]:
    if sobran := sorted(set(propuesta) - set(CAMPOS_PROPONIBLES)):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"La memoria no puede proponer estos campos del activo: {', '.join(sobran)}. "
            f"Admitidos: {', '.join(CAMPOS_PROPONIBLES)}.",
        )
    return propuesta


@router.put("/assets/{asset_id}/memoria", response_model=MemoriaLeida)
def guardar(
    asset_id: uuid.UUID,
    cuerpo: ContenidoDeMemoria,
    s: SesionDep,
    usuario: UsuarioDep,
) -> Any:
    """Crea o sustituye la memoria del activo. **Idempotente.**

    Se manda entera y no por trozos porque así es como llega: de un documento
    que se lee de una vez. Un alta por categoría obligaría a quien la escribe a
    calcular qué sobra y qué falta, y ese cálculo repetido es donde aparecen las
    memorias a medias.

    `[REQ]` Guardar **no toca el activo**. La propuesta se queda aquí hasta que
    alguien pulse validar. Es la mitad que hace que el botón signifique algo.
    """
    _activo(s, asset_id)
    _validar_codigos(s, cuerpo)
    propuesta = _propuesta_limpia(cuerpo.propuesta)

    org = str(usuario.organization_id)
    existente = s.execute(
        text("SELECT id, status FROM memoria_tecnica WHERE asset_id = :a"),
        {"a": str(asset_id)},
    ).first()

    # Volver a leer la memoria **deshace la validación**: lo que se aceptó ya no
    # es lo que hay. Dejar el testigo puesto sobre un contenido nuevo sería
    # exactamente la mentira que el testigo existe para evitar.
    estado = (
        "EXTRAIDA" if (cuerpo.document_id or propuesta or cuerpo.categorias) else ("SIN_DOCUMENTO")
    )
    comun = {
        "doc": str(cuerpo.document_id) if cuerpo.document_id else None,
        "est": estado,
        "ori": cuerpo.origen,
        "sim": cuerpo.es_simulada,
        "pro": json.dumps(propuesta, default=str),
        "not": cuerpo.notes,
    }

    if existente is None:
        memoria_id = s.execute(
            text(
                "INSERT INTO memoria_tecnica (organization_id, asset_id, document_id, "
                "status, origen, es_simulada, propuesta, notes, extraida_at) "
                "VALUES (:o, :a, :doc, CAST(:est AS memoria_status), :ori, :sim, "
                "CAST(:pro AS jsonb), :not, "
                "CASE WHEN :est = 'SIN_DOCUMENTO' THEN NULL ELSE now() END) RETURNING id"
            ),
            {**comun, "o": org, "a": str(asset_id)},
        ).scalar_one()
    else:
        memoria_id = existente[0]
        s.execute(
            text(
                "UPDATE memoria_tecnica SET document_id = :doc, "
                "status = CAST(:est AS memoria_status), origen = :ori, es_simulada = :sim, "
                "propuesta = CAST(:pro AS jsonb), notes = :not, "
                "extraida_at = CASE WHEN :est = 'SIN_DOCUMENTO' THEN NULL ELSE now() END, "
                "validada_at = NULL, validada_por = NULL, updated_at = now() "
                "WHERE id = :m"
            ),
            {**comun, "m": str(memoria_id)},
        )
        s.execute(
            text("DELETE FROM memoria_categoria WHERE memoria_id = :m"),
            {"m": str(memoria_id)},
        )

    for orden, categoria in enumerate(cuerpo.categorias):
        cat_id = s.execute(
            text(
                "INSERT INTO memoria_categoria (organization_id, memoria_id, capex_code_id, "
                "notes, orden) VALUES (:o, :m, :c, :n, :ord) RETURNING id"
            ),
            {
                "o": org,
                "m": str(memoria_id),
                "c": str(categoria.capex_code_id),
                "n": categoria.notes,
                "ord": orden,
            },
        ).scalar_one()
        for orden_objeto, objeto in enumerate(categoria.objetos):
            s.execute(
                text(
                    "INSERT INTO memoria_objeto (organization_id, memoria_categoria_id, "
                    "capex_code_id, nombre, cantidad, unidad, notes, orden) "
                    "VALUES (:o, :c, :cod, :n, :cant, :u, :not, :ord)"
                ),
                {
                    "o": org,
                    "c": str(cat_id),
                    "cod": str(objeto.capex_code_id) if objeto.capex_code_id else None,
                    "n": objeto.nombre,
                    "cant": objeto.cantidad,
                    "u": objeto.unidad,
                    "not": objeto.notes,
                    "ord": orden_objeto,
                },
            )

    return _leer(s, asset_id)


class Validacion(BaseModel):
    confirmar: bool = Field(
        description=(
            "Debe ser true. Aplicar la memoria al activo es una acción explícita: "
            "es el botón que separa «una máquina lo leyó» de «una persona lo aceptó»."
        )
    )


@router.post("/assets/{asset_id}/memoria/validar", response_model=MemoriaLeida)
def validar(
    asset_id: uuid.UUID,
    cuerpo: Validacion,
    s: SesionDep,
    usuario: UsuarioDep,
) -> Any:
    """`[REQ]` El botón. Vuelca la propuesta al activo y deja constancia.

    Hasta aquí, los datos leídos del documento no habían tocado la ficha. Esto
    los aplica y firma quién lo hizo y cuándo, en la memoria **y en el activo**:
    los dos testigos hacen falta, porque quien mira la ficha del edificio no
    tiene por qué saber que existe una memoria detrás.

    `[REQ]` Solo se escriben los campos que la propuesta trae. Un campo ausente
    **no borra** el valor que ya tuviera el activo: una memoria que no menciona
    la superficie de oficinas no es una memoria que diga que no hay.
    """
    if not cuerpo.confirmar:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Aplicar la memoria exige confirmación explícita",
        )
    _activo(s, asset_id)
    memoria = _leer(s, asset_id)

    propuesta = _propuesta_limpia(dict(memoria["propuesta"] or {}))
    if propuesta:
        asignaciones = ", ".join(f"{campo} = :{campo}" for campo in propuesta)
        s.execute(
            text(  # noqa: S608 — los nombres salen de CAMPOS_PROPONIBLES, no del usuario
                f"UPDATE asset SET {asignaciones}, memoria_validada_at = now(), "
                "memoria_validada_por = :_u, updated_at = now() WHERE id = :_a"
            ),
            {**propuesta, "_u": str(usuario.id), "_a": str(asset_id)},
        )
    else:
        s.execute(
            text(
                "UPDATE asset SET memoria_validada_at = now(), memoria_validada_por = :u, "
                "updated_at = now() WHERE id = :a"
            ),
            {"u": str(usuario.id), "a": str(asset_id)},
        )

    s.execute(
        text(
            "UPDATE memoria_tecnica SET status = 'VALIDADA', validada_at = now(), "
            "validada_por = :u, updated_at = now() WHERE asset_id = :a"
        ),
        {"u": str(usuario.id), "a": str(asset_id)},
    )
    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, after_data, severity) VALUES (:o, :u, 'ASSET_UPDATED', 'asset', :a, "
            "CAST(:d AS jsonb), 'INFO')"
        ),
        {
            "o": str(usuario.organization_id),
            "u": str(usuario.id),
            "a": str(asset_id),
            "d": json.dumps({"memoria_validada": True, "campos": sorted(propuesta)}, default=str),
        },
    )
    return _leer(s, asset_id)


# ─────────────────────────────────────────────────────────────────────────────
#  El esqueleto del CAPEX `[REQ]`
# ─────────────────────────────────────────────────────────────────────────────


class Esqueleto(BaseModel):
    creadas: int
    omitidas: int
    categorias: int
    avisos: list[str]


@router.post(
    "/assets/{asset_id}/memoria/generar-capex",
    status_code=status.HTTP_201_CREATED,
    response_model=Esqueleto,
)
def generar_capex(asset_id: uuid.UUID, s: SesionDep, usuario: UsuarioDep) -> Any:
    """`[REQ]` Crea el esqueleto del CAPEX desde la memoria.

    Una fila por objeto que la memoria enumera, en **BORRADOR**, para que el
    gestor técnico la complete: importe, riesgo, zona y plazo. Una categoría sin
    objetos también genera su fila, porque una categoría presente en el edificio
    y sin revisar es justo lo que no puede olvidarse.

    `[REQ]` **Es idempotente y no pisa trabajo hecho.** Volver a generarlo no
    duplica las filas que ya existen ni toca las que alguien haya rellenado: se
    cuentan como omitidas y se dice cuántas. Regenerar tras ampliar la memoria
    es lo normal, y que eso borrara importes ya tecleados sería indefendible.

    `[LIM]` Las filas nacen en la zona `GENERAL` y sin importe. La memoria
    enumera objetos, no dice dónde están ni cuánto cuestan; poner una zona
    adivinada la haría pasar por sabida.

    `[LIM]` Nacen en BORRADOR normal —lo decidió el cliente—, así que **cuentan
    en los totales y salen en el Excel de trabajo con importe cero** desde que
    se generan.
    """
    activo = _activo(s, asset_id)
    memoria = _leer(s, asset_id)

    zona = s.execute(
        text(
            "SELECT z.id FROM zone z JOIN zone_typology zt ON zt.zone_id = z.id "
            "WHERE z.code = :c AND zt.typology_id = :t"
        ),
        {"c": ZONA_DE_ARRANQUE, "t": str(activo["typology_id"])},
    ).scalar_one_or_none()
    if zona is None:  # pragma: no cover - el catálogo la tiene en las seis tipologías
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"La tipología de este activo no admite la zona «{ZONA_DE_ARRANQUE}», "
            "con la que nacen las filas del esqueleto",
        )

    # Lo que ya existe, por título: es lo que hace idempotente la generación.
    # Por título y no por código porque dos objetos de la misma categoría
    # comparten código de catálogo con frecuencia —o no tienen ninguno— y lo que
    # distingue una fila de otra es lo que la memoria llamó a cada cosa.
    ya_estan = {
        fila[0]
        for fila in s.execute(
            text("SELECT title FROM finding WHERE asset_id = :a AND deleted_at IS NULL"),
            {"a": str(asset_id)},
        ).all()
    }

    creadas = omitidas = 0
    avisos: list[str] = []
    for categoria in memoria["categorias"]:
        objetos = categoria["objetos"] or [
            {"nombre": categoria["capex_name"], "capex_code_id": None, "notes": None}
        ]
        if not categoria["objetos"]:
            avisos.append(
                f"«{categoria['capex_name']}» no enumera objetos en la memoria: se genera "
                "una sola fila con el nombre del capítulo."
            )
        for objeto in objetos:
            if objeto["nombre"] in ya_estan:
                omitidas += 1
                continue
            s.execute(
                text(
                    "INSERT INTO finding (organization_id, project_id, asset_id, "
                    "capex_code_id, zone_id, title, description, created_by) "
                    "VALUES (:o, :p, :a, :c, :z, :t, :d, :u)"
                ),
                {
                    "o": str(usuario.organization_id),
                    "p": str(activo["project_id"]),
                    "a": str(asset_id),
                    # El código del objeto si lo tiene; si no, el del capítulo,
                    # que es lo más concreto que se sabe de él.
                    "c": str(objeto["capex_code_id"] or categoria["capex_code_id"]),
                    "z": str(zona),
                    "t": objeto["nombre"],
                    "d": "Generado desde la memoria técnica. Pendiente de revisar en visita.",
                    "u": str(usuario.id),
                },
            )
            ya_estan.add(objeto["nombre"])
            creadas += 1

    return {
        "creadas": creadas,
        "omitidas": omitidas,
        "categorias": len(memoria["categorias"]),
        "avisos": avisos,
    }


__all__ = ["CAMPOS_PROPONIBLES", "ZONA_DE_ARRANQUE", "router"]

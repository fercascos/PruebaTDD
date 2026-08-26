"""El árbol físico de un activo: zonas, plantas y espacios.

`[REC]` §8.4 · Responde la pregunta que `zone` no puede responder: **¿dónde
estaba exactamente esto?** `zone` clasifica —«Cubierta»— y sirve para agregar en
el informe; el árbol localiza —«Cubierta / Sala de máquinas 2»— y sirve para
volver seis meses después.

Las rutas `ltree` las calcula un disparador y no este módulo. Es deliberado: una
ruta escrita a mano que no case con `parent_id` produce un árbol que se lee
distinto según por dónde se mire, y ese fallo no da la cara hasta que alguien
mueve una rama.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core.deps import SesionDep, UsuarioDep

router = APIRouter(tags=["Ubicaciones del activo"])


class TipoDeNodo(StrEnum):
    ZONA = "ZONA"
    PLANTA = "PLANTA"
    ESPACIO = "ESPACIO"


class Nodo(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    parent_id: uuid.UUID | None
    node_type: TipoDeNodo
    zone_id: uuid.UUID | None
    zone_name: str | None
    code: str | None
    name: str
    level_order: int
    #: Cuántos antepasados tiene. Lo calcula la base a partir de `path`, así que
    #: la pantalla puede sangrar el árbol sin recorrerlo ella.
    profundidad: int
    #: «Cubierta › Sala de máquinas 2». Se arma en la consulta porque hacerlo en
    #: la interfaz obligaría a tener el árbol entero cargado para pintar una
    #: sola fila.
    ruta_legible: str


class CrearNodo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_type: TipoDeNodo
    name: str = Field(min_length=1, max_length=160)
    parent_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    code: str | None = Field(default=None, max_length=60)
    level_order: int = 0


class ActualizarNodo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    parent_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    code: str | None = Field(default=None, max_length=60)
    level_order: int | None = None
    node_type: TipoDeNodo | None = None


_CAMPOS = """
    SELECT n.id, n.asset_id, n.parent_id, CAST(n.node_type AS text) AS node_type,
           n.zone_id, z.name_es AS zone_name, n.code, n.name, n.level_order,
           nlevel(n.path) - 1 AS profundidad,
           (SELECT string_agg(a.name, ' › ' ORDER BY nlevel(a.path))
              FROM location_node a
             WHERE a.path OPERATOR(public.@>) n.path AND a.deleted_at IS NULL) AS ruta_legible
    FROM location_node n
    LEFT JOIN zone z ON z.id = n.zone_id
"""


def _leer(s: Session, node_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text(f"{_CAMPOS} WHERE n.id = :i AND n.deleted_at IS NULL"),  # noqa: S608
            {"i": str(node_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ubicación no encontrada")
    return dict(fila)


@router.get("/assets/{asset_id}/locations", response_model=list[Nodo])
def listar(asset_id: uuid.UUID, s: SesionDep) -> Any:
    """El árbol entero del activo, **en orden de recorrido**.

    Se ordena por `path`, así que cada hijo sale justo detrás de su padre y la
    pantalla solo tiene que sangrar según `profundidad`. Devolverlo anidado
    obligaría a la interfaz a aplanarlo para pintar un desplegable, que es el
    uso más frecuente.
    """
    filas = (
        s.execute(
            text(  # noqa: S608
                f"{_CAMPOS} WHERE n.asset_id = :a AND n.deleted_at IS NULL "
                "ORDER BY n.path, n.level_order, n.name"
            ),
            {"a": str(asset_id)},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.post(
    "/assets/{asset_id}/locations",
    status_code=status.HTTP_201_CREATED,
    response_model=Nodo,
)
def crear(asset_id: uuid.UUID, cuerpo: CrearNodo, s: SesionDep, usuario: UsuarioDep) -> Any:
    if (
        s.execute(
            text("SELECT 1 FROM asset WHERE id = :a AND deleted_at IS NULL"), {"a": str(asset_id)}
        ).first()
        is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activo no encontrado")

    if cuerpo.parent_id is not None:
        # El padre tiene que ser del MISMO activo. La clave ajena no lo impide,
        # y un árbol con ramas de otro edificio dentro es indetectable después.
        padre = s.execute(
            text("SELECT asset_id FROM location_node WHERE id = :p AND deleted_at IS NULL"),
            {"p": str(cuerpo.parent_id)},
        ).scalar()
        if padre is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El padre no existe")
        if str(padre) != str(asset_id):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "El nodo padre pertenece a otro activo: un árbol no puede cruzar edificios",
            )

    nuevo = s.execute(
        text(
            "INSERT INTO location_node (organization_id, asset_id, parent_id, node_type, "
            "zone_id, code, name, level_order, path) "
            "VALUES (:o, :a, :p, CAST(:t AS location_node_type), :z, :c, :n, :orden, "
            # `path` lo pisa el disparador; hace falta un valor porque la
            # columna es NOT NULL.
            "        text2ltree('x')) RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "a": str(asset_id),
            "p": str(cuerpo.parent_id) if cuerpo.parent_id else None,
            "t": cuerpo.node_type.value,
            "z": str(cuerpo.zone_id) if cuerpo.zone_id else None,
            "c": cuerpo.code,
            "n": cuerpo.name.strip(),
            "orden": cuerpo.level_order,
        },
    ).scalar_one()
    return _leer(s, uuid.UUID(str(nuevo)))


@router.patch("/locations/{node_id}", response_model=Nodo)
def actualizar(node_id: uuid.UUID, cuerpo: ActualizarNodo, s: SesionDep) -> Any:
    """Renombrar o mover un nodo.

    Mover recalcula la ruta del nodo por el disparador, **pero no la de sus
    descendientes**: eso se hace aquí abajo, en la misma transacción. Dejarlo a
    medias produciría un árbol donde un hijo cuelga de dos sitios a la vez según
    se mire por `parent_id` o por `path`.
    """
    actual = _leer(s, node_id)
    cambios = cuerpo.model_dump(exclude_unset=True)
    if not cambios:
        return actual

    if "parent_id" in cambios and cambios["parent_id"] is not None:
        if str(cambios["parent_id"]) == str(node_id):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Un nodo no puede ser su propio padre"
            )
        padre = s.execute(
            text("SELECT asset_id FROM location_node WHERE id = :p AND deleted_at IS NULL"),
            {"p": str(cambios["parent_id"])},
        ).scalar()
        if padre is None or str(padre) != str(actual["asset_id"]):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "El nodo padre no existe o pertenece a otro activo",
            )

    ruta_vieja = s.execute(
        text("SELECT path::text FROM location_node WHERE id = :i"), {"i": str(node_id)}
    ).scalar_one()

    piezas = []
    for campo in cambios:
        if campo == "node_type":
            piezas.append("node_type = CAST(:node_type AS location_node_type)")
        else:
            piezas.append(f"{campo} = :{campo}")
    parametros = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in cambios.items()}
    if "node_type" in parametros and parametros["node_type"] is not None:
        parametros["node_type"] = TipoDeNodo(parametros["node_type"]).value
    parametros["_id"] = str(node_id)

    try:
        s.execute(
            text(  # noqa: S608
                f"UPDATE location_node SET {', '.join(piezas)}, updated_at = now() WHERE id = :_id"
            ),
            parametros,
        )
    except Exception as exc:  # noqa: BLE001 — el disparador avisa de los ciclos
        if "dentro de sí mismo" in str(exc):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Ese movimiento metería el nodo dentro de sí mismo",
            ) from exc
        raise

    if "parent_id" in cambios:
        ruta_nueva = s.execute(
            text("SELECT path::text FROM location_node WHERE id = :i"), {"i": str(node_id)}
        ).scalar_one()
        # Los descendientes cuelgan por `path`, no por `parent_id`: hay que
        # reescribirles el prefijo o quedarían colgando de donde estaba el nodo.
        s.execute(
            text(
                "UPDATE location_node SET path = text2ltree(:nueva) OPERATOR(public.||) "
                "  subpath(path, nlevel(text2ltree(:vieja))) "
                "WHERE path OPERATOR(public.<@) text2ltree(:vieja) AND id <> :i"
            ),
            {"nueva": ruta_nueva, "vieja": ruta_vieja, "i": str(node_id)},
        )

    return _leer(s, node_id)


@router.delete("/locations/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(node_id: uuid.UUID, s: SesionDep) -> None:
    """Borrado lógico, **y arrastra a los descendientes**.

    Dejar vivos los hijos de un nodo borrado produciría espacios sin planta que
    aparecen en el desplegable sin que se entienda de dónde salen. Las fotos no
    se tocan: su `location_node_id` pasa a `NULL` por la clave ajena y el token
    `[Espacio]` vuelve a omitirse, que es lo que hacía antes.
    """
    _leer(s, node_id)
    s.execute(
        text(
            "UPDATE location_node SET deleted_at = now() "
            "WHERE path OPERATOR(public.<@) (SELECT path FROM location_node WHERE id = :i) "
            "  AND deleted_at IS NULL"
        ),
        {"i": str(node_id)},
    )

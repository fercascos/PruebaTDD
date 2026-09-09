"""El descriptivo de cada objeto, pendiente de validar `[REQ]` §3.2 d.

Lo pidió el cliente sobre el inventario del activo: que la aplicación **traiga de
la documentación el descriptivo de cada objeto de Hard Cost que encuentre**, lo
enseñe marcado como pendiente de validar por el gestor técnico, se pueda editar y
se marque como validado con una casilla.

## Por qué es una tabla y no un campo de `memoria_objeto`

Es de ahí de donde sale el texto la primera vez, pero son dos cosas con dos
ciclos de vida. `memoria_objeto` es **lo que la memoria enumeró**, y se rehace
entera cada vez que se vuelve a extraer el documento —lo hace `PUT
/assets/{id}/memoria`, que borra y reinserta—. El descriptivo es **texto del
gestor técnico**: lo corrige, lo firma y responde de él. Guardarlos en la misma
fila significaría perder el trabajo de una persona cada vez que se refresca el de
una máquina.

## Qué hace «traer de la documentación»

Recorre los objetos que la memoria técnica enumeró y, **para los que tienen
código de nivel 3 dentro de Hard Costs**, crea o completa su descriptivo. El
texto es lo que la memoria dijo de ese objeto: su nombre, su cantidad y sus
notas, que es lo que hay.

Es **idempotente y no pisa trabajo hecho**: una fila ya validada no se toca
nunca, y una con texto escrito tampoco. Volver a traerlo tras ampliar la memoria
es lo normal, y que eso borrase lo que alguien ha corregido sería indefendible.
La respuesta dice cuántas creó, cuántas completó y cuántas respetó.

`[LIM]` **La única documentación que alimenta esto hoy es la memoria técnica.**
Es el documento que la aplicación sabe leer objeto a objeto; el plan de
autoprotección declara medios —que van al inventario de equipo— y el resto de la
documentación se revisa, no se disecciona. Cuando haya otro extractor que
produzca texto por objeto, entra por aquí sin cambiar la tabla ni la pantalla.

`[LIM]` Y hereda la procedencia de la memoria, **`es_simulada` incluido**: si la
extracción fue simulada, el descriptivo nace marcado como simulado y la pantalla
lo dice. Un texto de mentira que pase por bueno es peor que no tener texto.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core.deps import SesionDep, UsuarioDep

router = APIRouter(tags=["Memoria técnica"])

#: `[REQ]` «de cada objeto de **Hard Cost**». El descriptivo describe una parte
#: física del edificio; un soft cost es un honorario y no se describe.
TIPO_DE_COSTE = "HC"


class Descriptivo(BaseModel):
    id: uuid.UUID
    capex_code_id: uuid.UUID
    capex_code: str
    capex_name: str
    #: El capítulo al que pertenece, para agrupar la rejilla sin recalcularlo.
    chapter_code: str
    chapter_name: str
    texto: str
    document_id: uuid.UUID | None
    origen: str | None
    es_simulada: bool
    validado: bool
    validado_at: str | None
    validado_por: uuid.UUID | None
    validado_por_nombre: str | None
    row_version: int


class LineaEditada(BaseModel):
    """Una fila de la rejilla, tal como la manda la pantalla."""

    model_config = ConfigDict(extra="forbid")

    capex_code_id: uuid.UUID
    texto: str = Field(default="", max_length=4000)
    #: La casilla. `[REQ]` Validar es un acto de una persona, así que la API
    #: apunta **quién** y **cuándo**; la pantalla solo dice sí o no.
    validado: bool = False


class Edicion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lineas: list[LineaEditada]


class Traidos(BaseModel):
    creados: int
    completados: int
    respetados: int
    avisos: list[str]


_CAMPOS = """
    d.id, d.capex_code_id, cc.code AS capex_code, cc.name_es AS capex_name,
    cap.code AS chapter_code, cap.name_es AS chapter_name,
    d.texto, d.document_id, d.origen, d.es_simulada,
    d.validado_at IS NOT NULL AS validado,
    CAST(d.validado_at AS text) AS validado_at, d.validado_por,
    u.full_name AS validado_por_nombre, d.row_version
"""

_DESDE = """
    FROM descriptivo_objeto d
    JOIN capex_code cc ON cc.id = d.capex_code_id
    JOIN capex_code cap ON cap.id = cc.parent_id
    LEFT JOIN app_user u ON u.id = d.validado_por
"""


def _activo(s: Session, asset_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text("SELECT id, project_id FROM asset WHERE id = :i AND deleted_at IS NULL"),
            {"i": str(asset_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activo no encontrado")
    return dict(fila)


def _listar(s: Session, asset_id: uuid.UUID) -> list[dict[str, Any]]:
    filas = (
        s.execute(
            text(  # noqa: S608
                f"SELECT {_CAMPOS} {_DESDE} WHERE d.asset_id = :a ORDER BY cc.code"
            ),
            {"a": str(asset_id)},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.get("/assets/{asset_id}/descriptivos", response_model=list[Descriptivo])
def listar(asset_id: uuid.UUID, s: SesionDep) -> Any:
    """Los descriptivos del activo, ordenados por código.

    Por código y no por si están validados: la rejilla se lee siguiendo el árbol
    del CAPEX —H01, H02, H03…—, y reordenar por estado movería las filas de
    sitio cada vez que alguien marca una casilla, que es la peor forma de perder
    el hilo en una tabla que se rellena de arriba abajo.
    """
    _activo(s, asset_id)
    return _listar(s, asset_id)


@router.put("/assets/{asset_id}/descriptivos", response_model=list[Descriptivo])
def guardar(asset_id: uuid.UUID, cuerpo: Edicion, s: SesionDep, usuario: UsuarioDep) -> Any:
    """Guarda la rejilla entera: los textos y las casillas, de una vez.

    `[REC]` Una sola llamada para las dos cosas porque en la pantalla son un solo
    gesto: se corrige el texto y se marca la casilla en la misma fila. Con dos
    endpoints, quien edita y valida a la vez tendría dos peticiones capaces de
    fallar por separado, y una fila validada con el texto viejo.

    **Validar y desvalidar son simétricos.** Quitar la casilla borra el testigo:
    dejar quién validó en una fila que ya no está validada es guardar una firma
    de algo que no está firmado.
    """
    activo = _activo(s, asset_id)

    codigos = [str(linea.capex_code_id) for linea in cuerpo.lineas]
    if codigos:
        niveles = dict(
            s.execute(
                text("SELECT id, level FROM capex_code WHERE id = ANY(CAST(:ids AS uuid[]))"),
                {"ids": codigos},
            ).all()
        )
        for linea in cuerpo.lineas:
            nivel = niveles.get(linea.capex_code_id)
            if nivel is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"El código {linea.capex_code_id} no existe",
                )
            if nivel != 3:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "Un descriptivo describe un **objeto** del árbol (nivel 3). El código "
                    f"{linea.capex_code_id} es de nivel {nivel}.",
                )
            # `[REQ]` La restricción de la base dice lo mismo, y aquí se dice
            # antes para poder explicarlo: un 23514 de PostgreSQL no cuenta que
            # lo que falta es escribir el texto antes de firmarlo.
            if linea.validado and not linea.texto.strip():
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "No se puede marcar como validado un descriptivo vacío: sería firmar "
                    "una casilla en blanco.",
                )

    for linea in cuerpo.lineas:
        s.execute(
            text(
                "INSERT INTO descriptivo_objeto (organization_id, asset_id, capex_code_id, "
                "  texto, validado_at, validado_por, created_by) "
                "VALUES (:o, :a, :c, :t, "
                "  CASE WHEN :v THEN now() END, CASE WHEN :v THEN CAST(:u AS uuid) END, :u) "
                "ON CONFLICT (asset_id, capex_code_id) DO UPDATE SET "
                "  texto = EXCLUDED.texto, "
                # La fecha de validación **se conserva** si ya estaba validado:
                # volver a guardar el texto no es volver a validarlo, y mover la
                # fecha borraría cuándo se firmó de verdad.
                "  validado_at = CASE WHEN :v THEN COALESCE(descriptivo_objeto.validado_at, now())"
                "                     END, "
                "  validado_por = CASE WHEN :v "
                "                      THEN COALESCE(descriptivo_objeto.validado_por, "
                "                                    CAST(:u AS uuid)) END, "
                "  updated_at = now()"
            ),
            {
                "o": str(usuario.organization_id),
                "a": str(asset_id),
                "c": str(linea.capex_code_id),
                "t": linea.texto.strip(),
                "v": linea.validado,
                "u": str(usuario.id),
            },
        )
    _ = activo
    return _listar(s, asset_id)


@router.post(
    "/assets/{asset_id}/descriptivos/desde-documentacion",
    status_code=status.HTTP_201_CREATED,
    response_model=Traidos,
)
def desde_documentacion(asset_id: uuid.UUID, s: SesionDep, usuario: UsuarioDep) -> Any:
    """Trae de la memoria técnica el descriptivo de cada objeto de Hard Cost.

    Ver la cabecera del módulo: idempotente, no pisa lo validado ni lo escrito, y
    hereda la procedencia de la memoria —`es_simulada` incluido—.
    """
    _activo(s, asset_id)

    memoria = (
        s.execute(
            text(
                "SELECT id, document_id, origen, es_simulada FROM memoria_tecnica "
                "WHERE asset_id = :a"
            ),
            {"a": str(asset_id)},
        )
        .mappings()
        .first()
    )
    if memoria is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Este activo no tiene memoria técnica, que es de donde salen hoy los "
            "descriptivos. Cárguela o rellénela primero.",
        )

    objetos = (
        s.execute(
            text(
                "SELECT mo.capex_code_id, mo.nombre, mo.cantidad, mo.unidad, mo.notes, "
                "       cc.code AS capex_code "
                "FROM memoria_objeto mo "
                "JOIN memoria_categoria mc ON mc.id = mo.memoria_categoria_id "
                "JOIN capex_code cc ON cc.id = mo.capex_code_id "
                "WHERE mc.memoria_id = :m AND cc.level = 3 "
                # Solo Hard Costs: un soft cost es un honorario y no se describe.
                "  AND cc.path OPERATOR(public.<@) CAST(:hc AS ltree) "
                "ORDER BY mo.orden, mo.nombre"
            ),
            {"m": str(memoria["id"]), "hc": TIPO_DE_COSTE},
        )
        .mappings()
        .all()
    )

    ya_estan = {
        str(fila[0]): (fila[1], fila[2])
        for fila in s.execute(
            text(
                "SELECT capex_code_id, texto, validado_at IS NOT NULL "
                "FROM descriptivo_objeto WHERE asset_id = :a"
            ),
            {"a": str(asset_id)},
        ).all()
    }

    creados = completados = respetados = 0
    avisos: list[str] = []
    # Un objeto puede salir dos veces si la memoria lo enumera en dos
    # categorías. Se junta lo que dice de él en un solo descriptivo: dos filas
    # del mismo objeto no caben —lo impide el UNIQUE— y quedarse con una sola
    # perdería la mitad de lo que dice el documento.
    por_codigo: dict[str, list[str]] = {}
    for objeto in objetos:
        por_codigo.setdefault(str(objeto["capex_code_id"]), []).append(_frase(objeto))

    for codigo, frases in por_codigo.items():
        texto = " ".join(frases)
        anterior = ya_estan.get(codigo)
        if anterior is not None:
            viejo, validado = anterior
            if validado or (viejo or "").strip():
                respetados += 1
                continue
        s.execute(
            text(
                "INSERT INTO descriptivo_objeto (organization_id, asset_id, capex_code_id, "
                "  texto, document_id, origen, es_simulada, created_by) "
                "VALUES (:o, :a, :c, :t, :doc, :ori, :sim, :u) "
                "ON CONFLICT (asset_id, capex_code_id) DO UPDATE SET "
                "  texto = EXCLUDED.texto, document_id = EXCLUDED.document_id, "
                "  origen = EXCLUDED.origen, es_simulada = EXCLUDED.es_simulada, "
                "  updated_at = now()"
            ),
            {
                "o": str(usuario.organization_id),
                "a": str(asset_id),
                "c": codigo,
                "t": texto,
                "doc": str(memoria["document_id"]) if memoria["document_id"] else None,
                "ori": memoria["origen"],
                "sim": memoria["es_simulada"],
                "u": str(usuario.id),
            },
        )
        if anterior is None:
            creados += 1
        else:
            completados += 1

    sin_codigo = s.execute(
        text(
            "SELECT count(*) FROM memoria_objeto mo "
            "JOIN memoria_categoria mc ON mc.id = mo.memoria_categoria_id "
            "WHERE mc.memoria_id = :m AND mo.capex_code_id IS NULL"
        ),
        {"m": str(memoria["id"])},
    ).scalar_one()
    if sin_codigo:
        avisos.append(
            f"{sin_codigo} objetos de la memoria no están codificados contra el catálogo, "
            "así que no tienen descriptivo. Codifíquelos en la memoria y vuelva a traerlos."
        )
    if memoria["es_simulada"]:
        avisos.append(
            "La extracción de esta memoria es SIMULADA: los descriptivos nacen marcados "
            "como tales y no deben validarse sin leer el documento."
        )
    return {
        "creados": creados,
        "completados": completados,
        "respetados": respetados,
        "avisos": avisos,
    }


def _frase(objeto: Any) -> str:
    """Lo que la memoria dice de un objeto, en una frase.

    El nombre con sus palabras y no el del catálogo: «Enfriadora Marca X de
    450 kW» es lo que hace falta seis meses después, y «Producción de
    climatización» ya está en la columna de al lado.
    """
    partes = [str(objeto["nombre"]).strip()]
    if objeto["cantidad"] is not None:
        # La columna es NUMERIC(12,2), así que «2 unidades» llega como
        # `Decimal('2.00')` y se escribiría «2,00 ud». `normalize()` quita los
        # ceros de la escala y `:f` deshace la notación exponencial que
        # `normalize()` introduce al hacerlo —`Decimal('100.00')` se convierte
        # en `1E+2`—, que es peor que el problema que resuelve.
        cantidad = Decimal(str(objeto["cantidad"])).normalize()
        partes.append(f"({f'{cantidad:f}'.replace('.', ',')} {objeto['unidad'] or 'ud'})")
    if objeto["notes"]:
        partes.append(f"— {str(objeto['notes']).strip()}")
    return " ".join(partes)


__all__ = ["TIPO_DE_COSTE", "router"]

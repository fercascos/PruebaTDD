"""API del inventario de equipo `[REQ]` §7 / P-15.

**Es opcional, y eso se nota en que no aparece en ninguna otra parte.** Ningún
hallazgo lo exige, ninguna línea de CAPEX lo referencia y ningún informe se
bloquea por no tenerlo. Un encargo entero se puede entregar sin dar de alta un
solo equipo. Está aquí porque en una visita a un edificio con instalaciones
alguien apunta el fabricante, el modelo y el año de la enfriadora en una
libreta, y esa libreta acaba siendo la única fuente para justificar por qué se
propone sustituirla.

**La vida residual no se teclea** (P-15). Se guarda el año de instalación y la
vida útil esperada; lo que queda se calcula al leer, en `service.py`. Ver ahí
por qué no puede ser una columna generada.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core import concurrencia as cc
from tdd.core.deps import SesionDep, UsuarioDep
from tdd.equipment import importacion, service

router = APIRouter(tags=["Inventario de equipo"])


class Equipo(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    asset_id: uuid.UUID
    technical_system_id: uuid.UUID | None
    technical_system_name: str | None
    zone_id: uuid.UUID | None
    zone_name: str | None
    tag: str | None
    equipment_type: str
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    install_year: int | None
    expected_life_years: int | None
    condition: str | None
    obsolescence: str | None
    criticality: str | None
    quantity: Decimal
    unit: str
    has_documentation: bool
    notes: str | None
    #: La versión sobre la que se escribe. Va también como `ETag`.
    row_version: int = 1

    # Calculado, nunca almacenado. P-15.
    end_of_life_year: int | None
    remaining_life_years: int | None
    vencido: bool
    horizonte_code: str | None
    horizonte_name: str | None
    vida_resumen: str


class DatosDeEquipo(BaseModel):
    """`extra="forbid"`: un campo mal escrito se rechaza en vez de perderse."""

    model_config = ConfigDict(extra="forbid")

    asset_id: uuid.UUID
    equipment_type: str = Field(min_length=1, max_length=120)
    technical_system_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    tag: str | None = Field(default=None, max_length=40)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    install_year: int | None = Field(default=None, ge=1800, le=2200)
    expected_life_years: int | None = Field(default=None, gt=0, le=200)
    condition: str | None = None
    obsolescence: str | None = None
    criticality: str | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit: str = Field(default="ud", min_length=1, max_length=20)
    has_documentation: bool = False
    notes: str | None = None


class CambioDeEquipo(BaseModel):
    """Todo opcional: un `PATCH` corrige un campo sin reenviar la ficha entera."""

    model_config = ConfigDict(extra="forbid")

    equipment_type: str | None = Field(default=None, min_length=1, max_length=120)
    technical_system_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    tag: str | None = Field(default=None, max_length=40)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    serial_number: str | None = Field(default=None, max_length=120)
    install_year: int | None = Field(default=None, ge=1800, le=2200)
    expected_life_years: int | None = Field(default=None, gt=0, le=200)
    condition: str | None = None
    obsolescence: str | None = None
    criticality: str | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    has_documentation: bool | None = None
    notes: str | None = None


_CAMPOS = """
    e.id, e.project_id, e.asset_id, e.technical_system_id, e.zone_id, e.tag,
    e.equipment_type, e.manufacturer, e.model, e.serial_number,
    e.install_year, e.expected_life_years, e.end_of_life_year,
    CAST(e.condition AS text) AS condition,
    CAST(e.obsolescence AS text) AS obsolescence,
    CAST(e.criticality AS text) AS criticality,
    e.quantity, e.unit, e.has_documentation, e.notes, e.row_version,
    ts.name_es AS technical_system_name, z.name_es AS zone_name
"""

_DESDE = """
    FROM equipment e
    LEFT JOIN technical_system ts ON ts.id = e.technical_system_id
    LEFT JOIN zone z ON z.id = e.zone_id
"""

#: Las enumeraciones de la base. Se repiten aquí para poder devolver un 422 que
#: diga los valores válidos, en vez de un error de tipo de PostgreSQL que
#: menciona un nombre de tipo interno.
VALORES = {
    "condition": ["BUENO", "ACEPTABLE", "DEFICIENTE", "MUY_DEFICIENTE", "FUERA_DE_SERVICIO"],
    "obsolescence": ["ACTUAL", "PROXIMO_A_OBSOLETO", "OBSOLETO", "SIN_REPUESTOS"],
    "criticality": ["ALTA", "MEDIA", "BAJA"],
}


def _comprobar_enumerados(datos: dict[str, Any]) -> None:
    for campo, validos in VALORES.items():
        valor = datos.get(campo)
        if valor is not None and valor not in validos:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"«{campo}» no admite «{valor}». Valores válidos: {', '.join(validos)}.",
            )


def _horizontes(s: Session) -> list[service.Horizonte]:
    filas = (
        s.execute(
            text(
                "SELECT code, name_es, year_from, year_to FROM time_horizon "
                "WHERE is_execution_term ORDER BY sort_order"
            )
        )
        .mappings()
        .all()
    )
    return [service.Horizonte(**dict(f)) for f in filas]


def _con_vida(fila: Any, horizontes: list[service.Horizonte], *, anio: int) -> dict[str, Any]:
    vida = service.calcular_vida(fila["end_of_life_year"], horizontes, anio_actual=anio)
    return {
        **dict(fila),
        "end_of_life_year": vida.end_of_life_year,
        "remaining_life_years": vida.remaining_life_years,
        "vencido": vida.vencido,
        "horizonte_code": vida.horizonte_code,
        "horizonte_name": vida.horizonte_name,
        "vida_resumen": vida.resumen,
    }


def _leer(s: Session, equipment_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text(f"SELECT {_CAMPOS} {_DESDE} WHERE e.id = :i AND e.deleted_at IS NULL"),  # noqa: S608
            {"i": str(equipment_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    return _con_vida(fila, _horizontes(s), anio=date.today().year)


@router.get("/projects/{project_id}/equipment", response_model=list[Equipo])
def listar(
    project_id: uuid.UUID,
    s: SesionDep,
    asset_id: uuid.UUID | None = None,
    technical_system_id: uuid.UUID | None = None,
    q: str | None = None,
    solo_vencidos: bool = False,
) -> Any:
    """El inventario del encargo, con filtros.

    `solo_vencidos` compara contra el año en curso en SQL y no contra un valor
    guardado: un inventario cargado en 2025 tiene que seguir diciendo la verdad
    en 2027 sin que nadie lo recalcule.
    """
    filas = (
        s.execute(
            text(
                f"SELECT {_CAMPOS} {_DESDE} "  # noqa: S608
                "WHERE e.project_id = :p AND e.deleted_at IS NULL "
                "  AND (CAST(:a AS uuid) IS NULL OR e.asset_id = CAST(:a AS uuid)) "
                "  AND (CAST(:ts AS uuid) IS NULL OR e.technical_system_id = CAST(:ts AS uuid)) "
                "  AND (CAST(:q AS text) IS NULL "
                "       OR e.search_vector @@ plainto_tsquery('spanish', CAST(:q AS text))) "
                "  AND (NOT :v OR (e.end_of_life_year IS NOT NULL "
                "                  AND e.end_of_life_year < EXTRACT(YEAR FROM current_date))) "
                "ORDER BY ts.sort_order NULLS LAST, e.tag NULLS LAST, e.equipment_type"
            ),
            {
                "p": str(project_id),
                "a": str(asset_id) if asset_id else None,
                "ts": str(technical_system_id) if technical_system_id else None,
                "q": q,
                "v": solo_vencidos,
            },
        )
        .mappings()
        .all()
    )
    horizontes = _horizontes(s)
    anio = date.today().year
    return [_con_vida(f, horizontes, anio=anio) for f in filas]


@router.post(
    "/projects/{project_id}/equipment",
    status_code=status.HTTP_201_CREATED,
    response_model=Equipo,
)
def crear(project_id: uuid.UUID, cuerpo: DatosDeEquipo, s: SesionDep, usuario: UsuarioDep) -> Any:
    datos = cuerpo.model_dump()
    _comprobar_enumerados(datos)

    # El activo tiene que ser del encargo. Sin esto se podría colgar un equipo
    # de un activo de otro proyecto de la misma organización, y el inventario
    # dejaría de cuadrar sin que nada avisara.
    if (
        s.execute(
            text("SELECT 1 FROM asset WHERE id = :a AND project_id = :p AND deleted_at IS NULL"),
            {"a": str(cuerpo.asset_id), "p": str(project_id)},
        ).first()
        is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El activo no pertenece a este proyecto")

    nuevo = s.execute(
        text(
            "INSERT INTO equipment (organization_id, project_id, asset_id, technical_system_id, "
            "zone_id, tag, equipment_type, manufacturer, model, serial_number, install_year, "
            "expected_life_years, condition, obsolescence, criticality, quantity, unit, "
            "has_documentation, notes, created_by) "
            "VALUES (:o, :p, :a, :ts, :z, :tag, :et, :man, :mod, :sn, :iy, :el, "
            "  CAST(:cond AS equipment_condition), CAST(:obs AS equipment_obsolescence), "
            "  CAST(:crit AS equipment_criticality), :qty, :u, :hd, :n, :cb) "
            "RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "p": str(project_id),
            "a": str(cuerpo.asset_id),
            "ts": str(cuerpo.technical_system_id) if cuerpo.technical_system_id else None,
            "z": str(cuerpo.zone_id) if cuerpo.zone_id else None,
            "tag": (cuerpo.tag or "").strip() or None,
            "et": cuerpo.equipment_type.strip(),
            "man": cuerpo.manufacturer,
            "mod": cuerpo.model,
            "sn": cuerpo.serial_number,
            "iy": cuerpo.install_year,
            "el": cuerpo.expected_life_years,
            "cond": cuerpo.condition,
            "obs": cuerpo.obsolescence,
            "crit": cuerpo.criticality,
            "qty": cuerpo.quantity,
            "u": cuerpo.unit,
            "hd": cuerpo.has_documentation,
            "n": cuerpo.notes,
            "cb": str(usuario.id),
        },
    ).scalar_one()
    return _leer(s, nuevo)


@router.get("/equipment/{equipment_id}", response_model=Equipo)
def leer(equipment_id: uuid.UUID, s: SesionDep, respuesta: Response) -> Any:
    fila = _leer(s, equipment_id)
    cc.poner(respuesta, fila.get("row_version"))
    return fila


@router.patch("/equipment/{equipment_id}", response_model=Equipo)
def modificar(
    equipment_id: uuid.UUID,
    cuerpo: CambioDeEquipo,
    s: SesionDep,
    request: Request,
    respuesta: Response,
) -> Any:
    """`If-Match` opcional: la importación masiva desde XLSX escribe sin haber
    leído antes, y exigirle una versión que no tiene solo añadiría una lectura
    previa que tampoco elimina la carrera."""
    actual = _leer(s, equipment_id)
    cc.comprobar(
        request,
        s,
        tabla="equipment",
        fila_id=equipment_id,
        version_actual=actual.get("row_version"),
        que="una ficha de equipo",
    )
    cambios = cuerpo.model_dump(exclude_unset=True)
    if not cambios:
        cc.poner(respuesta, actual.get("row_version"))
        return actual
    _comprobar_enumerados(cambios)

    enumerados = {
        "condition": "equipment_condition",
        "obsolescence": "equipment_obsolescence",
        "criticality": "equipment_criticality",
    }
    trozos = []
    for campo in cambios:
        if campo in enumerados:
            trozos.append(f"{campo} = CAST(:{campo} AS {enumerados[campo]})")
        else:
            trozos.append(f"{campo} = :{campo}")
    parametros: dict[str, Any] = {
        k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in cambios.items()
    }
    if "tag" in parametros:
        parametros["tag"] = (parametros["tag"] or "").strip() or None
    parametros["i"] = str(equipment_id)

    hay = s.execute(
        text(  # noqa: S608
            f"UPDATE equipment SET {', '.join(trozos)}, updated_at = now() "
            "WHERE id = :i AND deleted_at IS NULL RETURNING id"
        ),
        parametros,
    ).first()
    if hay is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    nuevo = _leer(s, equipment_id)
    cc.poner(respuesta, nuevo.get("row_version"))
    return nuevo


@router.delete("/equipment/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(equipment_id: uuid.UUID, s: SesionDep) -> None:
    """Borrado lógico.

    La ficha se ha escrito en una visita a la que no se vuelve. Borrarla de
    verdad significaría volver al edificio para recuperar el número de serie de
    una enfriadora.
    """
    hay = s.execute(
        text(
            "UPDATE equipment SET deleted_at = now(), updated_at = now() "
            "WHERE id = :i AND deleted_at IS NULL RETURNING id"
        ),
        {"i": str(equipment_id)},
    ).first()
    if hay is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")


# ─────────────────────────────────────────────────────────────────────────────
#  Importación desde XLSX `[REQ]` §7 · docs/15 lo daba por pendiente
# ─────────────────────────────────────────────────────────────────────────────
#
# El inventario de una nave con instalaciones llega en una hoja que alguien
# rellenó durante la visita, no fila a fila en un formulario. Tres endpoints:
# la plantilla que se descarga, la previsualización —que **no escribe nada**— y
# la aplicación, que es una llamada aparte y explícita.

#: Un XLSX de inventario es texto: cinco mil filas no llegan a esto. El límite
#: existe para que un fichero equivocado —un vídeo renombrado -- no se cargue
#: entero en memoria antes de que nadie mire qué es.
MAX_BYTES_XLSX = 10 * 1024 * 1024


class FilaImportada(BaseModel):
    fila: int
    estado: str
    errores: list[str]
    avisos: list[str]
    crudo: dict[str, str]
    existente_id: uuid.UUID | None = None


class Previsualizacion(BaseModel):
    resumen: str
    hoja: str
    #: `[LIM]` Solo se lee la primera hoja del libro.
    total_hojas: int
    columnas_ignoradas: list[str]
    columnas_ausentes: list[str]
    filas: list[FilaImportada]
    nuevas: int
    ya_existen: int
    con_error: int
    aviso: str = (
        "Nada se ha guardado todavía. Al aplicar, los equipos que ya existen no "
        "se tocan salvo que lo pida expresamente."
    )


def _catalogos(s: Session, project_id: uuid.UUID) -> tuple[Any, Any, Any]:
    activos = [
        importacion.Activo(id=str(f["id"]), name=f["name"], asset_code=f["asset_code"])
        for f in s.execute(
            text(
                "SELECT id, name, asset_code FROM asset "
                "WHERE project_id = :p AND deleted_at IS NULL ORDER BY name"
            ),
            {"p": str(project_id)},
        )
        .mappings()
        .all()
    ]
    sistemas = [
        importacion.Sistema(id=str(f["id"]), code=f["code"], name_es=f["name_es"])
        for f in s.execute(
            text("SELECT id, code, name_es FROM technical_system ORDER BY sort_order")
        )
        .mappings()
        .all()
    ]
    # Las etiquetas ya ocupadas, para poder decir «esta ya existe» ANTES de
    # intentar el INSERT y chocar contra el índice único.
    existentes = {
        (str(f["asset_id"]), importacion.clave(f["tag"])): str(f["id"])
        for f in s.execute(
            text(
                "SELECT id, asset_id, tag FROM equipment "
                "WHERE project_id = :p AND tag IS NOT NULL AND deleted_at IS NULL"
            ),
            {"p": str(project_id)},
        )
        .mappings()
        .all()
    }
    return activos, sistemas, existentes


def _analizar_subida(contenido: bytes, s: Session, project_id: uuid.UUID) -> Any:
    from tdd.exports import equipo_xlsx

    if len(contenido) > MAX_BYTES_XLSX:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"El fichero supera el máximo de {MAX_BYTES_XLSX // (1024 * 1024)} MB",
        )
    try:
        hoja = equipo_xlsx.leer(contenido)
    except equipo_xlsx.LibroIlegible as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    activos, sistemas, existentes = _catalogos(s, project_id)
    analisis = importacion.analizar(
        hoja.cabeceras,
        hoja.filas,
        activos=activos,
        sistemas=sistemas,
        etiquetas_existentes=existentes,
    )
    return hoja, analisis


def _a_respuesta(hoja: Any, analisis: Any) -> dict[str, Any]:
    return {
        "resumen": analisis.resumen(),
        "hoja": hoja.nombre,
        "total_hojas": hoja.total_hojas,
        "columnas_ignoradas": analisis.columnas_ignoradas,
        "columnas_ausentes": analisis.columnas_ausentes,
        "filas": [
            {
                "fila": f.fila,
                "estado": str(f.estado),
                "errores": f.errores,
                "avisos": f.avisos,
                "crudo": f.crudo,
                "existente_id": f.existente_id,
            }
            for f in analisis.filas
        ],
        "nuevas": len(analisis.nuevas),
        "ya_existen": len(analisis.ya_existen),
        "con_error": len(analisis.con_error),
    }


@router.get(
    "/projects/{project_id}/equipment/import/plantilla.xlsx",
    response_class=Response,
    responses={
        200: {
            "content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}},
            "description": "Libro vacío con las columnas y los valores admitidos.",
        }
    },
)
def plantilla_de_importacion(project_id: uuid.UUID, s: SesionDep) -> Response:
    """La hoja que se descarga para rellenar.

    Lleva dentro **los activos de este encargo y los 14 sistemas técnicos**. Sin
    eso, quien la rellena escribe el nombre del edificio de memoria y la mitad
    de las filas fallan al importar por una tilde.
    """
    from tdd.exports import equipo_xlsx

    activos, sistemas, _ = _catalogos(s, project_id)
    binario = equipo_xlsx.plantilla(
        [a.name for a in activos], [f"{x.name_es}  ({x.code})" for x in sistemas]
    )
    return Response(
        content=binario,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="inventario-plantilla.xlsx"'},
    )


@router.post("/projects/{project_id}/equipment/import/preview", response_model=Previsualizacion)
def previsualizar_importacion(
    project_id: uuid.UUID,
    s: SesionDep,
    archivo: Annotated[UploadFile, File(alias="file")],
) -> Any:
    """`[REQ]` Lee la hoja y dice qué va a pasar. **No escribe nada.**

    Es una llamada aparte a propósito. Una importación que mete trescientas
    filas y luego informa de que doce dieron error obliga a limpiar a mano lo
    que ya entró, y en una tabla con borrado lógico eso es peor todavía.
    """
    hoja, analisis = _analizar_subida(archivo.file.read(), s, project_id)
    return _a_respuesta(hoja, analisis)


class Resultado(BaseModel):
    creados: int
    actualizados: int
    omitidos: int
    resumen: str
    previsualizacion: Previsualizacion


@router.post("/projects/{project_id}/equipment/import", response_model=Resultado)
def importar(
    project_id: uuid.UUID,
    s: SesionDep,
    usuario: UsuarioDep,
    archivo: Annotated[UploadFile, File(alias="file")],
    confirmar: Annotated[bool, Form()] = False,
    actualizar_existentes: Annotated[bool, Form()] = False,
) -> Any:
    """Aplica la importación. Exige `confirmar` y vuelve a analizar la hoja.

    **Se reanaliza en vez de fiarse de lo previsualizado.** Entre la
    previsualización y la aplicación pueden pasar minutos y otra persona puede
    haber dado de alta el mismo equipo; aceptar un plan calculado antes sería
    escribir sobre un estado que ya no existe.

    `[REQ]` **Nada se sobrescribe solo.** Las filas cuya etiqueta ya está en ese
    activo se omiten salvo que `actualizar_existentes` venga en verdadero, que
    es una casilla que alguien tiene que marcar. La ficha que hay en la base la
    escribió alguien en una visita a la que no se vuelve.
    """
    if not confirmar:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Revise la previsualización y confirme la importación.",
        )
    hoja, analisis = _analizar_subida(archivo.file.read(), s, project_id)

    creados = 0
    for fila in analisis.nuevas:
        v = fila.valores
        s.execute(
            text(
                "INSERT INTO equipment (organization_id, project_id, asset_id, "
                "technical_system_id, tag, equipment_type, manufacturer, model, serial_number, "
                "install_year, expected_life_years, condition, obsolescence, criticality, "
                "quantity, unit, has_documentation, notes, created_by) "
                "VALUES (:o, :p, :a, :ts, :tag, :et, :man, :mod, :sn, :iy, :el, "
                "  CAST(:cond AS equipment_condition), CAST(:obs AS equipment_obsolescence), "
                "  CAST(:crit AS equipment_criticality), :qty, :u, :hd, :n, :cb)"
            ),
            {
                "o": str(usuario.organization_id),
                "p": str(project_id),
                "a": v["asset_id"],
                "ts": v["technical_system_id"],
                "tag": v["tag"],
                "et": v["equipment_type"],
                "man": v["manufacturer"],
                "mod": v["model"],
                "sn": v["serial_number"],
                "iy": v["install_year"],
                "el": v["expected_life_years"],
                "cond": v["condition"],
                "obs": v["obsolescence"],
                "crit": v["criticality"],
                "qty": v["quantity"],
                "u": v["unit"],
                "hd": v["has_documentation"],
                "n": v["notes"],
                "cb": str(usuario.id),
            },
        )
        creados += 1

    actualizados = 0
    if actualizar_existentes:
        for fila in analisis.ya_existen:
            v = fila.valores
            s.execute(
                text(
                    "UPDATE equipment SET technical_system_id = :ts, equipment_type = :et, "
                    "manufacturer = :man, model = :mod, serial_number = :sn, install_year = :iy, "
                    "expected_life_years = :el, "
                    "condition = CAST(:cond AS equipment_condition), "
                    "obsolescence = CAST(:obs AS equipment_obsolescence), "
                    "criticality = CAST(:crit AS equipment_criticality), "
                    "quantity = :qty, unit = :u, has_documentation = :hd, notes = :n, "
                    "updated_at = now() WHERE id = :i AND deleted_at IS NULL"
                ),
                {
                    "ts": v["technical_system_id"],
                    "et": v["equipment_type"],
                    "man": v["manufacturer"],
                    "mod": v["model"],
                    "sn": v["serial_number"],
                    "iy": v["install_year"],
                    "el": v["expected_life_years"],
                    "cond": v["condition"],
                    "obs": v["obsolescence"],
                    "crit": v["criticality"],
                    "qty": v["quantity"],
                    "u": v["unit"],
                    "hd": v["has_documentation"],
                    "n": v["notes"],
                    "i": fila.existente_id,
                },
            )
            actualizados += 1

    omitidos = len(analisis.con_error) + (0 if actualizar_existentes else len(analisis.ya_existen))

    # Queda en la auditoría: una importación mueve muchas filas de golpe y es
    # justo lo que alguien querrá reconstruir dentro de seis meses.
    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, after_data, severity) VALUES (:o, :u, 'EQUIPMENT_IMPORTED', 'project', "
            ":i, CAST(:d AS jsonb), 'AVISO')"
        ),
        {
            "o": str(usuario.organization_id),
            "u": str(usuario.id),
            "i": str(project_id),
            "d": (
                f'{{"creados": {creados}, "actualizados": {actualizados}, '
                f'"omitidos": {omitidos}, "hoja": "{hoja.nombre}"}}'
            ),
        },
    )

    partes = [f"{creados} equipos creados"]
    if actualizados:
        partes.append(f"{actualizados} actualizados")
    if omitidos:
        partes.append(f"{omitidos} omitidos")
    return {
        "creados": creados,
        "actualizados": actualizados,
        "omitidos": omitidos,
        "resumen": " · ".join(partes),
        "previsualizacion": _a_respuesta(hoja, analisis),
    }

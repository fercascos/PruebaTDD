"""API de activos y equipo del proyecto.

Dos cosas de este módulo merecen explicación.

**La ficha del activo es la UNIÓN de §3.1.3 y §3.3.1** `[REQ]` P-02. Los campos
que no aplican a una tipología no se borran al reclasificar: se guardan siempre
y la interfaz decide qué enseñar. Así, cambiar una nave por un edificio de
oficinas y volver atrás no destruye lo ya introducido, que es exactamente lo
que pasaría con una tabla por tipología.

**La tipología manda sobre las zonas** `[REQ]`. No es un adorno del catálogo:
al crear un hallazgo se comprueba que la zona esté permitida para la tipología
del activo, y aquí se expone la lista para que la interfaz no ofrezca opciones
que después va a rechazar.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core import concurrencia as cc
from tdd.core.deps import SesionDep, UsuarioDep

router = APIRouter(tags=["Activos"])

_CAMPOS = """
    id, project_id, typology_id, name, asset_code, main_use,
    address_line, city, province, postal_code, country_code,
    latitude, longitude, geocode_source,
    plot_area_sqm, total_built_sqm, lettable_area_sqm, warehouse_area_sqm,
    office_area_sqm, warehouse_height_m, floors_above, floors_below,
    year_built, year_last_refurb, description, notes, main_photo_id, row_version,
    cadastral_reference, developer, project_date, secondary_use,
    footprint_area_sqm, urbanised_area_sqm, usable_area_sqm, max_height_m,
    loading_docks, parking_spaces, memoria_validada_at, memoria_validada_por
"""


class DatosDeActivo(BaseModel):
    """`extra="forbid"`: un campo mal escrito se rechaza en vez de perderse.

    Un `superficie_almacen` que la API ignora en silencio produce una ficha
    incompleta que nadie detecta hasta el informe.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    typology_id: uuid.UUID
    asset_code: str | None = Field(default=None, max_length=60)
    main_use: str | None = Field(default=None, max_length=120)
    address_line: str | None = Field(default=None, max_length=240)
    city: str | None = Field(default=None, max_length=120)
    province: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=20)
    country_code: str = Field(default="ES", min_length=2, max_length=2)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    geocode_source: str | None = Field(default=None, max_length=40)
    plot_area_sqm: Decimal | None = Field(default=None, ge=0)
    total_built_sqm: Decimal | None = Field(default=None, ge=0)
    lettable_area_sqm: Decimal | None = Field(default=None, ge=0)
    warehouse_area_sqm: Decimal | None = Field(default=None, ge=0)
    office_area_sqm: Decimal | None = Field(default=None, ge=0)
    warehouse_height_m: Decimal | None = Field(default=None, ge=0)
    floors_above: int | None = Field(default=None, ge=0, le=200)
    floors_below: int | None = Field(default=None, ge=0, le=20)
    year_built: int | None = Field(default=None, ge=1500, le=2100)
    year_last_refurb: int | None = Field(default=None, ge=1500, le=2100)
    description: str | None = None
    notes: str | None = None

    # `[REQ]` Lo que aporta la memoria técnica del edificio. Tres de estos
    # campos se parecen a otros de arriba y NO son lo mismo; el comentario está
    # aquí porque es donde alguien va a teclear el valor equivocado:
    #   · `footprint_area_sqm` es la HUELLA, no la construida total.
    #   · `usable_area_sqm` es la ÚTIL, no la alquilable.
    #   · `max_height_m` es la del EDIFICIO, no la del almacén.
    cadastral_reference: str | None = Field(default=None, max_length=30)
    developer: str | None = Field(default=None, max_length=200)
    project_date: date | None = None
    secondary_use: str | None = Field(default=None, max_length=120)
    footprint_area_sqm: Decimal | None = Field(default=None, ge=0)
    urbanised_area_sqm: Decimal | None = Field(default=None, ge=0)
    usable_area_sqm: Decimal | None = Field(default=None, ge=0)
    max_height_m: Decimal | None = Field(default=None, ge=0)
    loading_docks: int | None = Field(default=None, ge=0, le=500)
    parking_spaces: int | None = Field(default=None, ge=0, le=100_000)

    @model_validator(mode="after")
    def _coherencia(self) -> DatosDeActivo:
        """Las mismas reglas que la base de datos, pero con mensaje legible.

        No es duplicación: el `CHECK` impide que entre un dato incoherente por
        cualquier vía; esto devuelve un `422` que dice qué campo revisar.
        """
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Las coordenadas se dan completas: latitud y longitud")
        if (
            self.year_last_refurb is not None
            and self.year_built is not None
            and self.year_last_refurb < self.year_built
        ):
            raise ValueError("El año de reforma no puede ser anterior al de construcción")
        if (
            self.warehouse_area_sqm is not None
            and self.total_built_sqm is not None
            and self.warehouse_area_sqm > self.total_built_sqm
        ):
            raise ValueError("La superficie de almacén no puede superar la construida total")
        return self


class ActualizarActivo(DatosDeActivo):
    """Todo opcional salvo lo que se envíe. `name` y `typology_id` incluidos."""

    name: str | None = Field(default=None, min_length=1, max_length=200)  # type: ignore[assignment]
    typology_id: uuid.UUID | None = None  # type: ignore[assignment]
    country_code: str | None = Field(default=None, min_length=2, max_length=2)  # type: ignore[assignment]


class Activo(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    typology_id: uuid.UUID
    name: str
    asset_code: str | None
    main_use: str | None
    address_line: str | None
    city: str | None
    province: str | None
    postal_code: str | None
    country_code: str
    latitude: Decimal | None
    longitude: Decimal | None
    geocode_source: str | None
    plot_area_sqm: Decimal | None
    total_built_sqm: Decimal | None
    lettable_area_sqm: Decimal | None
    warehouse_area_sqm: Decimal | None
    office_area_sqm: Decimal | None
    warehouse_height_m: Decimal | None
    floors_above: int | None
    floors_below: int | None
    year_built: int | None
    year_last_refurb: int | None
    description: str | None
    notes: str | None
    main_photo_id: uuid.UUID | None
    #: La versión sobre la que se escribe. Va también como `ETag`.
    row_version: int = 1

    #: Lo que aporta la memoria técnica.
    cadastral_reference: str | None = None
    developer: str | None = None
    project_date: date | None = None
    secondary_use: str | None = None
    footprint_area_sqm: Decimal | None = None
    urbanised_area_sqm: Decimal | None = None
    usable_area_sqm: Decimal | None = None
    max_height_m: Decimal | None = None
    loading_docks: int | None = None
    parking_spaces: int | None = None
    #: `[REQ]` El testigo de la revisión humana. Mientras sea `None`, la ficha
    #: enseña los datos de la memoria como **sin validar**: uno extraído por una
    #: máquina no puede parecerse a uno tecleado por un técnico.
    memoria_validada_at: datetime | None = None
    memoria_validada_por: uuid.UUID | None = None


def _proyecto_existe(s: Session, project_id: uuid.UUID) -> None:
    if (
        s.execute(
            text("SELECT 1 FROM project WHERE id = :p AND deleted_at IS NULL"),
            {"p": str(project_id)},
        ).first()
        is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")


def _obtener(s: Session, asset_id: uuid.UUID) -> Any:
    fila = (
        s.execute(
            text(f"SELECT {_CAMPOS} FROM asset WHERE id = :i AND deleted_at IS NULL"),  # noqa: S608
            {"i": str(asset_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activo no encontrado")
    return dict(fila)


def _tipologia_valida(s: Session, typology_id: uuid.UUID) -> None:
    if (
        s.execute(
            text("SELECT 1 FROM asset_typology WHERE id = :t"), {"t": str(typology_id)}
        ).first()
        is None
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Tipología desconocida")


@router.post(
    "/projects/{project_id}/assets", status_code=status.HTTP_201_CREATED, response_model=Activo
)
def crear(project_id: uuid.UUID, cuerpo: DatosDeActivo, s: SesionDep, usuario: UsuarioDep) -> Any:
    _proyecto_existe(s, project_id)
    _tipologia_valida(s, cuerpo.typology_id)
    datos = cuerpo.model_dump()
    columnas = ", ".join(datos)
    valores = ", ".join(f":{c}" for c in datos)
    fila = s.execute(
        text(  # noqa: S608 — los nombres salen del esquema Pydantic, no del usuario
            f"INSERT INTO asset (organization_id, project_id, {columnas}) "
            f"VALUES (:_org, :_proy, {valores}) RETURNING id"
        ),
        {**datos, "_org": str(usuario.organization_id), "_proy": str(project_id)},
    ).scalar_one()
    return _obtener(s, fila)


@router.get("/projects/{project_id}/assets", response_model=list[Activo])
def listar(
    project_id: uuid.UUID,
    s: SesionDep,
    q: str | None = Query(default=None, description="Busca en nombre, código y ciudad"),
) -> Any:
    _proyecto_existe(s, project_id)
    filas = (
        s.execute(
            text(  # noqa: S608
                f"SELECT {_CAMPOS} FROM asset WHERE project_id = :p AND deleted_at IS NULL "
                "AND (CAST(:q AS text) IS NULL "
                "     OR name ILIKE '%' || :q || '%' "
                "     OR COALESCE(asset_code, '') ILIKE '%' || :q || '%' "
                "     OR COALESCE(city, '') ILIKE '%' || :q || '%') "
                "ORDER BY name"
            ),
            {"p": str(project_id), "q": q},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.get("/assets/{asset_id}", response_model=Activo)
def obtener(asset_id: uuid.UUID, s: SesionDep, respuesta: Response) -> Any:
    fila = _obtener(s, asset_id)
    cc.poner(respuesta, fila.get("row_version"))
    return fila


@router.patch("/assets/{asset_id}", response_model=Activo)
def actualizar(
    asset_id: uuid.UUID,
    cuerpo: ActualizarActivo,
    s: SesionDep,
    request: Request,
    respuesta: Response,
) -> Any:
    """`If-Match` **opcional aquí**, a diferencia de hallazgos y líneas.

    La ficha de un activo la edita casi siempre una sola persona, y las
    importaciones escriben sin haber leído antes. Si la cabecera viene, se
    honra; si no, se deja pasar. La razón está en `core/concurrencia`.
    """
    actual = _obtener(s, asset_id)
    cc.comprobar(
        request,
        s,
        tabla="asset",
        fila_id=asset_id,
        version_actual=actual.get("row_version"),
        que="un activo",
    )
    cambios = cuerpo.model_dump(exclude_unset=True)
    if not cambios:
        cc.poner(respuesta, actual.get("row_version"))
        return actual
    if "typology_id" in cambios and cambios["typology_id"] is not None:
        _tipologia_valida(s, cambios["typology_id"])
    asignaciones = ", ".join(f"{c} = :{c}" for c in cambios)
    s.execute(
        text(f"UPDATE asset SET {asignaciones}, updated_at = now() WHERE id = :_id"),  # noqa: S608
        {**cambios, "_id": str(asset_id)},
    )
    nuevo = _obtener(s, asset_id)
    cc.poner(respuesta, nuevo.get("row_version"))
    return nuevo


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def borrar(asset_id: uuid.UUID, s: SesionDep) -> None:
    """Borrado lógico. Un activo con hallazgos ya redactados no desaparece: se
    marca, y los hallazgos siguen ahí para el informe ya emitido."""
    _obtener(s, asset_id)
    s.execute(
        text("UPDATE asset SET deleted_at = now() WHERE id = :i AND deleted_at IS NULL"),
        {"i": str(asset_id)},
    )


class ZonaPermitida(BaseModel):
    id: uuid.UUID
    code: str
    name_es: str


@router.get("/assets/{asset_id}/allowed-zones", response_model=list[ZonaPermitida])
def zonas_permitidas(asset_id: uuid.UUID, s: SesionDep) -> Any:
    """`[REQ]` Las zonas dependen de la tipología del activo.

    Se expone para que la interfaz no ofrezca una zona que después el alta del
    hallazgo va a rechazar. Ofrecer y luego rechazar es la forma más rápida de
    que alguien deje de fiarse de los desplegables.
    """
    activo = _obtener(s, asset_id)
    filas = (
        s.execute(
            text(
                "SELECT z.id, z.code, z.name_es FROM zone z "
                "JOIN zone_typology zt ON zt.zone_id = z.id "
                "WHERE zt.typology_id = :t ORDER BY z.sort_order, z.name_es"
            ),
            {"t": str(activo["typology_id"])},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


# ─────────────────────────────────────────────────────────────────────────────
#  Zonas del activo: privadas y comunes `[REQ]`
# ─────────────────────────────────────────────────────────────────────────────


class ZonaDelActivo(BaseModel):
    zone_id: uuid.UUID
    tenure: Literal["PRIVADA", "COMUN"]
    area_sqm: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class ZonaDelActivoLeida(ZonaDelActivo):
    id: uuid.UUID
    zone_code: str
    zone_name: str


@router.get("/assets/{asset_id}/zones", response_model=list[ZonaDelActivoLeida])
def zonas_del_activo(asset_id: uuid.UUID, s: SesionDep) -> Any:
    """Qué zonas tiene este edificio y cuáles son privadas y cuáles comunes."""
    _obtener(s, asset_id)
    filas = (
        s.execute(
            text(
                "SELECT az.id, az.zone_id, CAST(az.tenure AS text) AS tenure, az.area_sqm, "
                "az.notes, z.code AS zone_code, z.name_es AS zone_name "
                "FROM asset_zone az JOIN zone z ON z.id = az.zone_id "
                "WHERE az.asset_id = :a ORDER BY z.sort_order, z.name_es"
            ),
            {"a": str(asset_id)},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.put("/assets/{asset_id}/zones", response_model=list[ZonaDelActivoLeida])
def fijar_zonas_del_activo(
    asset_id: uuid.UUID,
    cuerpo: list[ZonaDelActivo],
    s: SesionDep,
    usuario: UsuarioDep,
) -> Any:
    """Sustituye la clasificación entera del activo. **Idempotente.**

    Se manda la lista completa y no un alta por zona porque así es como llega:
    de una memoria técnica que declara las zonas del edificio de una vez. Un
    `POST` por zona obligaría a la interfaz a calcular qué sobra y qué falta, y
    ese cálculo repetido es donde aparecen las clasificaciones a medias.

    `[REQ]` Se rechaza una zona que la tipología del activo no admite. La
    plantilla del cliente ofrece una lista de zonas distinta por tipo de
    edificio, y una zona fuera de esa lista deja la celda vacía en el Excel sin
    que nadie se entere: mejor un `422` aquí.
    """
    activo = _obtener(s, asset_id)

    permitidas = {
        fila[0]
        for fila in s.execute(
            text(
                "SELECT z.id FROM zone z JOIN zone_typology zt ON zt.zone_id = z.id "
                "WHERE zt.typology_id = :t"
            ),
            {"t": str(activo["typology_id"])},
        ).all()
    }
    pedidas = [z.zone_id for z in cuerpo]
    if len(set(pedidas)) != len(pedidas):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Una zona no puede declararse dos veces en el mismo activo",
        )
    if fuera := sorted(str(z) for z in set(pedidas) - permitidas):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"La tipología de este activo no admite estas zonas: {', '.join(fuera)}",
        )

    s.execute(text("DELETE FROM asset_zone WHERE asset_id = :a"), {"a": str(asset_id)})
    for z in cuerpo:
        s.execute(
            text(
                "INSERT INTO asset_zone (organization_id, asset_id, zone_id, tenure, "
                "area_sqm, notes) VALUES (:o, :a, :z, CAST(:t AS zone_tenure), :s, :n)"
            ),
            {
                "o": str(usuario.organization_id),
                "a": str(asset_id),
                "z": str(z.zone_id),
                "t": z.tenure,
                "s": z.area_sqm,
                "n": z.notes,
            },
        )
    return zonas_del_activo(asset_id, s)


@router.put("/assets/{asset_id}/main-photo", response_model=Activo)
def fijar_foto_principal(asset_id: uuid.UUID, photo_id: uuid.UUID, s: SesionDep) -> Any:
    """La imagen que encabeza la ficha y la portada del activo en el informe."""
    _obtener(s, asset_id)
    valida = s.execute(
        text(
            "SELECT 1 FROM photo WHERE id = :f AND asset_id = :a AND deleted_at IS NULL "
            "AND status = 'LISTA'"
        ),
        {"f": str(photo_id), "a": str(asset_id)},
    ).first()
    if valida is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "La fotografía debe pertenecer a este activo y estar lista",
        )
    s.execute(
        text("UPDATE asset SET main_photo_id = :f, updated_at = now() WHERE id = :a"),
        {"f": str(photo_id), "a": str(asset_id)},
    )
    return _obtener(s, asset_id)


# ─────────────────────────────────────────────────────────────────────────────
#  Equipo del proyecto
# ─────────────────────────────────────────────────────────────────────────────


class AltaDeMiembro(BaseModel):
    user_id: uuid.UUID
    role_code: str = "CONSULTOR"
    is_project_lead: bool = False


class Miembro(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    role_code: str
    is_project_lead: bool
    #: `[REQ]` §7 · El máximo entre el rol de organización y el del proyecto.
    effective_role: str


#: Escala de permisos, de menor a mayor. El rol efectivo es el **máximo** entre
#: el de organización y el del proyecto: un LECTOR de la organización puede
#: dirigir un proyecto concreto, y eso no le da poder sobre los demás.
_ESCALA = ["LECTOR", "REVISOR", "TECNICO_ESPECIALISTA", "CONSULTOR", "DIRECTOR", "ADMIN"]

#: Los roles de organización y de proyecto no se llaman igual en todos los
#: casos; esto los lleva a la misma escala antes de compararlos.
_EQUIVALENCIA_ORG = {"DIRECTOR_PROYECTO": "DIRECTOR"}


def rol_efectivo(rol_org: str, rol_proyecto: str | None) -> str:
    """`[REQ]` §7 · El máximo de los dos, en la escala común."""
    org = _EQUIVALENCIA_ORG.get(rol_org, rol_org)
    candidatos = [r for r in (org, rol_proyecto) if r in _ESCALA]
    if not candidatos:
        return "LECTOR"
    return max(candidatos, key=_ESCALA.index)


@router.get("/projects/{project_id}/members", response_model=list[Miembro])
def listar_equipo(project_id: uuid.UUID, s: SesionDep) -> Any:
    _proyecto_existe(s, project_id)
    filas = (
        s.execute(
            text(
                "SELECT m.id, m.user_id, u.full_name, u.email, "
                "CAST(m.role_code AS text) AS role_code, m.is_project_lead, "
                "CAST(u.org_role AS text) AS org_role "
                "FROM project_member m JOIN app_user u ON u.id = m.user_id "
                "WHERE m.project_id = :p AND m.removed_at IS NULL "
                "ORDER BY m.is_project_lead DESC, u.full_name"
            ),
            {"p": str(project_id)},
        )
        .mappings()
        .all()
    )
    return [
        {
            **{k: v for k, v in f.items() if k != "org_role"},
            "effective_role": rol_efectivo(f["org_role"], f["role_code"]),
        }
        for f in filas
    ]


@router.post(
    "/projects/{project_id}/members", status_code=status.HTTP_201_CREATED, response_model=Miembro
)
def anadir_miembro(
    project_id: uuid.UUID, cuerpo: AltaDeMiembro, s: SesionDep, usuario: UsuarioDep
) -> Any:
    """Añade a alguien al equipo, o le devuelve el sitio si estaba retirado.

    Reincorporar en vez de crear una fila nueva conserva la fecha de alta
    original y evita que el índice único choque con el histórico.
    """
    _proyecto_existe(s, project_id)
    if cuerpo.is_project_lead and cuerpo.role_code != "DIRECTOR":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Quien dirige el proyecto debe tener el rol DIRECTOR",
        )
    existe = s.execute(
        text("SELECT 1 FROM app_user WHERE id = :u AND is_active"), {"u": str(cuerpo.user_id)}
    ).first()
    if existe is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Usuario desconocido o inactivo")

    if cuerpo.is_project_lead:
        # Solo puede haber uno. Se cede el puesto en vez de fallar: nombrar a
        # otro director es una acción normal, no un error.
        s.execute(
            text(
                "UPDATE project_member SET is_project_lead = FALSE "
                "WHERE project_id = :p AND is_project_lead AND removed_at IS NULL"
            ),
            {"p": str(project_id)},
        )

    fila = s.execute(
        text(
            "INSERT INTO project_member (organization_id, project_id, user_id, role_code, "
            "is_project_lead, assigned_by) "
            "VALUES (:o, :p, :u, CAST(:r AS project_role), :l, :a) "
            "ON CONFLICT (project_id, user_id) WHERE removed_at IS NULL "
            "DO UPDATE SET role_code = EXCLUDED.role_code, "
            "              is_project_lead = EXCLUDED.is_project_lead "
            "RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "p": str(project_id),
            "u": str(cuerpo.user_id),
            "r": cuerpo.role_code,
            "l": cuerpo.is_project_lead,
            "a": str(usuario.id),
        },
    ).scalar_one()

    detalle = (
        s.execute(
            text(
                "SELECT m.id, m.user_id, u.full_name, u.email, "
                "CAST(m.role_code AS text) AS role_code, m.is_project_lead, "
                "CAST(u.org_role AS text) AS org_role "
                "FROM project_member m JOIN app_user u ON u.id = m.user_id WHERE m.id = :i"
            ),
            {"i": str(fila)},
        )
        .mappings()
        .one()
    )
    return {
        **{k: v for k, v in detalle.items() if k != "org_role"},
        "effective_role": rol_efectivo(detalle["org_role"], detalle["role_code"]),
    }


@router.delete("/projects/{project_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def retirar_miembro(project_id: uuid.UUID, member_id: uuid.UUID, s: SesionDep) -> None:
    """Retirada lógica: lo que esa persona firmó sigue atribuido a ella."""
    hay = s.execute(
        text(
            "UPDATE project_member SET removed_at = now(), is_project_lead = FALSE "
            "WHERE id = :i AND project_id = :p AND removed_at IS NULL RETURNING id"
        ),
        {"i": str(member_id), "p": str(project_id)},
    ).first()
    if hay is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Miembro no encontrado")


class AsignacionDeActivo(BaseModel):
    project_member_id: uuid.UUID
    specialty: str | None = Field(default=None, max_length=60)


@router.post("/assets/{asset_id}/assignments", status_code=status.HTTP_201_CREATED)
def asignar_activo(
    asset_id: uuid.UUID, cuerpo: AsignacionDeActivo, s: SesionDep, usuario: UsuarioDep
) -> Any:
    """`[REQ]` Un activo con varios técnicos por especialidad, y una persona en
    varios activos."""
    _obtener(s, asset_id)
    miembro = s.execute(
        text("SELECT 1 FROM project_member WHERE id = :m AND removed_at IS NULL"),
        {"m": str(cuerpo.project_member_id)},
    ).first()
    if miembro is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "El miembro no pertenece al equipo"
        )
    s.execute(
        text(
            "INSERT INTO asset_assignment (organization_id, asset_id, project_member_id, "
            "specialty, assigned_by) VALUES (:o, :a, :m, :e, :u) "
            "ON CONFLICT DO NOTHING"
        ),
        {
            "o": str(usuario.organization_id),
            "a": str(asset_id),
            "m": str(cuerpo.project_member_id),
            "e": cuerpo.specialty,
            "u": str(usuario.id),
        },
    )
    return {"asset_id": asset_id, **cuerpo.model_dump()}


@router.get("/assets/{asset_id}/assignments")
def listar_asignaciones(asset_id: uuid.UUID, s: SesionDep) -> Any:
    _obtener(s, asset_id)
    filas = (
        s.execute(
            text(
                "SELECT a.id, a.project_member_id, a.specialty, u.full_name, u.email "
                "FROM asset_assignment a "
                "JOIN project_member m ON m.id = a.project_member_id "
                "JOIN app_user u ON u.id = m.user_id "
                "WHERE a.asset_id = :a ORDER BY u.full_name"
            ),
            {"a": str(asset_id)},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]

"""API de fotografías `[REQ]` §15 · bloque 2.

> *«que se puedan subir desde el carrete del móvil, desde el ordenador, hacer
> fotos directamente, etc.»*

Los tres orígenes son **el mismo endpoint**: `POST /projects/{id}/photos` con
`multipart/form-data`. En el navegador la diferencia está en el `input` que lo
dispara, no en el servidor:

| Origen | Cómo lo abre la PWA | Lo que cambia aquí |
|---|---|---|
| Ordenador | `<input type="file" multiple>` | Volumen: importa el aviso de duplicado |
| Carrete del móvil | `…accept="image/*" multiple` | Llegan **HEIC** y coordenadas GPS |
| Cámara en directo | `…capture="environment"` | Llega **orientación EXIF** que aplicar |

Un solo endpoint porque el servidor no debe fiarse de lo que el cliente diga
sobre la procedencia: valida el MIME real, calcula el hash él mismo y aplica la
orientación siempre. `origin` se guarda como dato descriptivo, no como permiso.

`[LIM]` En el MVP la subida es **directa y síncrona**: el binario viaja en la
petición y los derivados se generan en el acto. La secuencia con URL firmada y
worker de §15.3 —antivirus incluido— **no está implementada**. Es aceptable
mientras el volumen sea el de una visita, y deja de serlo con 400 fotos: está
anotado como pendiente y el contrato de la API no cambia al moverlo al worker.

`[LIM]` **El antivirus (ClamAV) no está integrado.** Ninguna foto pasa hoy por
`CUARENTENA`; el estado existe y la máquina de estados lo contempla, pero nada
lo activa todavía. No se afirma lo contrario.
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core.deps import SesionDep, UsuarioActual, UsuarioDep
from tdd.evidence import images, storage
from tdd.evidence.naming import (
    PLANTILLA_POR_DEFECTO,
    iniciales,
    resolver_colisiones,
    sanear,
)
from tdd.evidence.service import (
    ContextoDeFoto,
    EstadoDeFoto,
    FotoConocida,
    FotoParaInforme,
    PurgaNoPermitida,
    TipoDeDuplicado,
    TransicionDeFotoNoPermitida,
    agrupar_duplicados,
    avisos_previos_al_informe,
    buscar_duplicado,
    comprobar_purga,
    comprobar_transicion,
    planificar_renombrado,
)

router = APIRouter(tags=["Fotografías"])


def obtener_almacen(request: Request) -> storage.AlmacenDeObjetos:
    """El almacén lo aporta la aplicación: la suite inyecta el de memoria."""
    return request.app.state.object_store  # type: ignore[no-any-return]


AlmacenDep = Annotated[storage.AlmacenDeObjetos, Depends(obtener_almacen)]

#: `[SUP]` Tamaño máximo por fichero. Una foto de móvil ronda 3-5 MB; 50 deja
#: sitio de sobra para una réflex sin abrir la puerta a subir un vídeo.
MAX_BYTES = 50 * 1024 * 1024

#: `[REQ]` §10.7 · Lote máximo del alta por intención.
MAX_LOTE = 50

DERIVADOS_AL_SUBIR = ("MINIATURA_320", "VISTA_1600")

#: `[LIM]` Tope de la descarga directa en ZIP. Por encima hace falta el worker
#: de §15.7, que no está construido.
MAX_ZIP_BYTES = 400 * 1024 * 1024


# ─────────────────────────────────────────────────────────────────────────────
#  Esquemas
# ─────────────────────────────────────────────────────────────────────────────


class DuplicadoDetectado(BaseModel):
    tipo: str
    photo_id: uuid.UUID
    distancia: int
    display_name: str
    mensaje: str


class Foto(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    asset_id: uuid.UUID | None
    zone_id: uuid.UUID | None
    #: `[REQ]` §3.2 · La clasificación transversal. Alimenta el token
    #: `[Sistema]` del renombrado, que sin esto escribía siempre «SinSistema».
    technical_system_id: uuid.UUID | None = None
    status: str
    origin: str
    original_filename: str
    display_name: str
    file_extension: str
    mime_type: str
    sha256: str
    phash: str | None
    byte_size: int
    width_px: int | None
    height_px: int | None
    taken_at: datetime | None
    gps_latitude: float | None
    gps_longitude: float | None
    camera_model: str | None
    caption: str | None
    tags: list[str]
    include_in_report: bool
    report_order: int | None
    #: Presente solo en la respuesta de subida.
    duplicado: DuplicadoDetectado | None = None
    #: Avisos no bloqueantes de la subida (por ejemplo, foto sin activo).
    avisos: list[str] = Field(default_factory=list)


class ActualizarFoto(BaseModel):
    """`[REQ]` §10.7 · `storage_key` y `sha256` **no son escribibles**.

    `extra="forbid"` los rechaza con `422` en vez de ignorarlos en silencio: si
    un cliente los envía, está construido sobre una idea equivocada del modelo
    y conviene que se entere.
    """

    model_config = ConfigDict(extra="forbid")

    asset_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    technical_system_id: uuid.UUID | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    caption: str | None = None
    description: str | None = None
    photo_category: str | None = Field(default=None, max_length=60)
    tags: list[str] | None = None
    include_in_report: bool | None = None
    report_order: int | None = None
    report_section: str | None = Field(default=None, max_length=60)


class PeticionDeRenombrado(BaseModel):
    photo_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    template: str = PLANTILLA_POR_DEFECTO
    #: `[REQ]` La previsualización es obligatoria: por defecto **no escribe**.
    dry_run: bool = True
    numerar_desde: int | None = None


class CambioPropuesto(BaseModel):
    photo_id: uuid.UUID
    antes: str
    despues: str
    cambia: bool
    omitidos: list[str]


class ResultadoDeRenombrado(BaseModel):
    dry_run: bool
    cambios: list[CambioPropuesto]
    colisiones_resueltas: list[str]
    aplicados: int
    fallidos: list[dict[str, str]]


class GrupoDeDuplicados(BaseModel):
    photo_ids: list[uuid.UUID]


class EntidadEnlazable(StrEnum):
    """`[REQ]` A qué se puede enlazar una fotografía.

    Es un enumerado y no una cadena libre porque la columna es un `ENUM` de
    PostgreSQL: con un `str` suelto, escribir `finding` en minúsculas producía
    un **500** en vez de un `422` diciendo qué valores valen. Aquí los valores
    salen en el OpenAPI y el error los enumera solo.
    """

    ASSET = "ASSET"
    ZONE = "ZONE"
    FINDING = "FINDING"
    CAPEX_ITEM = "CAPEX_ITEM"
    REPORT_SECTION = "REPORT_SECTION"
    ASSET_VISIT = "ASSET_VISIT"
    DOC_REQUEST_ITEM = "DOC_REQUEST_ITEM"


class PapelDeLaFoto(StrEnum):
    EVIDENCIA = "EVIDENCIA"
    GENERAL = "GENERAL"
    DETALLE = "DETALLE"
    ANTES = "ANTES"
    DESPUES = "DESPUES"


class Enlace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: EntidadEnlazable
    entity_id: uuid.UUID
    role: PapelDeLaFoto = PapelDeLaFoto.EVIDENCIA
    sort_order: int = 0


# ─────────────────────────────────────────────────────────────────────────────
#  Auxiliares
# ─────────────────────────────────────────────────────────────────────────────

_COLUMNAS = """
    id, project_id, asset_id, zone_id, technical_system_id,
    status::text AS status, origin::text AS origin,
    original_filename, display_name, file_extension, mime_type, sha256, phash,
    byte_size, width_px, height_px, taken_at, gps_latitude, gps_longitude,
    camera_model, caption, tags, include_in_report, report_order
"""


def _fila_a_foto(fila: Any) -> dict[str, Any]:
    d = dict(fila._mapping)
    for clave in ("gps_latitude", "gps_longitude"):
        if d.get(clave) is not None:
            d[clave] = float(d[clave])
    d["tags"] = list(d.get("tags") or [])
    return d


def _catalogo_del_proyecto(s: Session, project_id: uuid.UUID) -> list[FotoConocida]:
    filas = s.execute(
        text(
            "SELECT id, sha256, phash, display_name FROM photo "
            "WHERE project_id = :p AND deleted_at IS NULL"
        ),
        {"p": str(project_id)},
    ).all()
    return [
        FotoConocida(id=f.id, sha256=f.sha256, phash=f.phash, display_name=f.display_name)
        for f in filas
    ]


def _obtener(s: Session, photo_id: uuid.UUID) -> Any:
    fila = s.execute(
        text(f"SELECT {_COLUMNAS}, deleted_at FROM photo WHERE id = :i"), {"i": str(photo_id)}
    ).first()
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fotografía no encontrada")
    return fila


def _proyecto_existe(s: Session, project_id: uuid.UUID) -> None:
    hay = s.execute(
        text("SELECT 1 FROM project WHERE id = :p AND deleted_at IS NULL"), {"p": str(project_id)}
    ).first()
    if hay is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")


def _auditar(
    s: Session, usuario: UsuarioActual, accion: str, photo_id: uuid.UUID, detalle: dict[str, Any]
) -> None:
    """`[REQ]` §10.7 regla 3 · toda descarga y todo renombrado quedan registrados."""
    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, after_data) VALUES (:o, :u, :a, 'photo', :e, CAST(:p AS jsonb))"
        ),
        {
            "o": str(usuario.organization_id),
            "u": str(usuario.id),
            "a": accion,
            "e": str(photo_id),
            "p": _json(detalle),
        },
    )


def _json(datos: dict[str, Any]) -> str:
    return json.dumps(datos, ensure_ascii=False, default=str)


# ─────────────────────────────────────────────────────────────────────────────
#  Subida · los tres orígenes
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/projects/{project_id}/photos",
    status_code=status.HTTP_201_CREATED,
    response_model=Foto,
    summary="Subir una fotografía (ordenador, carrete del móvil o cámara en directo)",
)
def subir(  # noqa: PLR0913 — son campos de formulario, no parámetros de diseño
    project_id: uuid.UUID,
    s: SesionDep,
    usuario: UsuarioDep,
    almacen: AlmacenDep,
    archivo: Annotated[UploadFile, File(alias="file")],
    origin: Annotated[str, Form()] = "ORDENADOR",
    asset_id: Annotated[uuid.UUID | None, Form()] = None,
    zone_id: Annotated[uuid.UUID | None, Form()] = None,
    technical_system_id: Annotated[uuid.UUID | None, Form()] = None,
    caption: Annotated[str | None, Form()] = None,
) -> Any:
    """Da de alta la foto y sus derivados. **El original se guarda tal cual llegó.**

    Orden deliberado: primero se lee y valida el binario, después se decide si
    es duplicado y solo al final se escribe. Así una foto rechazada no deja
    rastro ni en la base ni en el almacén.
    """
    _proyecto_existe(s, project_id)
    datos = archivo.file.read()
    if len(datos) > MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"El archivo supera el máximo de {MAX_BYTES // (1024 * 1024)} MB",
        )
    try:
        meta = images.leer(datos)
    except images.ImagenNoValida as exc:
        # 415 y no 422: el problema es el tipo de contenido, no el formulario.
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc

    duplicado = buscar_duplicado(meta.sha256, meta.phash, _catalogo_del_proyecto(s, project_id))
    if duplicado is not None and duplicado.tipo is TipoDeDuplicado.EXACTO:
        # 409 y no 400: la petición es correcta, el conflicto es con el estado
        # del proyecto. No hay forma de forzarlo, y es deliberado: el índice
        # `UNIQUE (project_id, sha256) WHERE deleted_at IS NULL` lo impide en la
        # base de datos, así que un «subir de todas formas» solo produciría un
        # error más feo y más tarde. El fichero ya está: se enlaza o se
        # clasifica el que hay.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{duplicado.mensaje} (fotografía {duplicado.photo_id})",
        )

    photo_id = uuid.uuid4()
    extension = meta.extension
    clave = storage.clave_de_original(usuario.organization_id, project_id, photo_id, extension)
    almacen.guardar(clave, datos)

    objeto_id = s.execute(
        text(
            "INSERT INTO stored_object (organization_id, project_id, kind, storage_key, sha256, "
            "byte_size, mime_type, is_original) "
            "VALUES (:o, :p, 'PHOTO_ORIGINAL', :k, :h, :b, :m, TRUE) RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "p": str(project_id),
            "k": clave,
            "h": meta.sha256,
            "b": meta.byte_size,
            "m": meta.mime_type,
        },
    ).scalar_one()

    nombre_original = archivo.filename or f"{photo_id}.{extension}"
    # El nombre visible arranca del nombre de llegada, saneado y sin extensión:
    # el consultor reconoce su foto, y el renombrado en lote vendrá después.
    visible = sanear(nombre_original.rsplit(".", 1)[0])[:200] or f"Foto{photo_id.hex[:8]}"
    # `foto.jpg.jpg` deja `foto.jpg`, que volvería a llevar extensión. Se repite
    # hasta que no quede ninguna: la extensión la pone el servidor al servir.
    while visible.lower().endswith(f".{extension}"):
        visible = visible[: -len(extension) - 1] or f"Foto{photo_id.hex[:8]}"

    s.execute(
        text(
            """
            INSERT INTO photo (
                id, organization_id, project_id, asset_id, zone_id, technical_system_id,
                stored_object_id,
                origin, status, original_filename, display_name, file_extension, mime_type,
                sha256, phash, byte_size, width_px, height_px, taken_at,
                gps_latitude, gps_longitude, camera_make, camera_model, orientation,
                exif_raw, caption, duplicate_of_photo_id, uploaded_by
            ) VALUES (
                :id, :org, :proy, :activo, :zona, :sistema, :objeto,
                CAST(:origen AS photo_origin), 'LISTA', :llegada, :visible, :ext, :mime,
                :sha, :phash, :bytes, :ancho, :alto, :fecha,
                :lat, :lon, :marca, :modelo, :orient,
                CAST(:exif AS jsonb), :pie, :dup, :usuario
            )
            """
        ),
        {
            "id": str(photo_id),
            "org": str(usuario.organization_id),
            "proy": str(project_id),
            "activo": str(asset_id) if asset_id else None,
            "sistema": str(technical_system_id) if technical_system_id else None,
            "zona": str(zone_id) if zone_id else None,
            "objeto": str(objeto_id),
            "origen": origin if origin in _ORIGENES else "ORDENADOR",
            "llegada": nombre_original[:260],
            "visible": visible,
            "ext": extension,
            "mime": meta.mime_type,
            "sha": meta.sha256,
            "phash": meta.phash,
            "bytes": meta.byte_size,
            "ancho": meta.ancho,
            "alto": meta.alto,
            # [REQ] Si el EXIF no trae fecha, queda NULL. No se sustituye por
            # `now()` ni por la fecha del fichero: sería inventar la evidencia.
            "fecha": meta.taken_at,
            "lat": meta.coordenadas.latitud if meta.coordenadas else None,
            "lon": meta.coordenadas.longitud if meta.coordenadas else None,
            "marca": meta.fabricante,
            "modelo": meta.camara,
            "orient": meta.orientacion,
            "exif": _json(meta.exif_legible),
            "pie": caption,
            "dup": str(duplicado.photo_id) if duplicado else None,
            "usuario": str(usuario.id),
        },
    )

    # v1 · ORIGINAL. La única versión con binario garantizado y la única que no
    # se puede borrar ni modificar.
    s.execute(
        text(
            "INSERT INTO photo_version (organization_id, photo_id, version_number, version_type, "
            "stored_object_id, display_name, is_current, created_by) "
            "VALUES (:o, :f, 1, 'ORIGINAL', :obj, :n, TRUE, :u)"
        ),
        {
            "o": str(usuario.organization_id),
            "f": str(photo_id),
            "obj": str(objeto_id),
            "n": visible,
            "u": str(usuario.id),
        },
    )

    _generar_derivados(s, almacen, usuario, project_id, photo_id, datos)
    _auditar(s, usuario, "PHOTO_UPLOADED", photo_id, {"origin": origin, "sha256": meta.sha256})

    respuesta = _fila_a_foto(_obtener(s, photo_id))
    if duplicado is not None:
        respuesta["duplicado"] = {
            "tipo": duplicado.tipo.value,
            "photo_id": duplicado.photo_id,
            "distancia": duplicado.distancia,
            "display_name": duplicado.display_name,
            "mensaje": duplicado.mensaje,
        }
    avisos: list[str] = []
    if asset_id is None:
        # [REQ] §10.7 regla 4 · sin activo se acepta CON AVISO, no con error.
        avisos.append("La fotografía no está asignada a ningún activo.")
    if meta.taken_at is None:
        avisos.append("La fotografía no trae fecha en el EXIF: el campo queda vacío.")
    respuesta["avisos"] = avisos
    return respuesta


#: Los tres que pidió el cliente, más el que hará falta el día que alguien
#: traiga una carpeta de un encargo anterior.
_ORIGENES = {"ORDENADOR", "CARRETE", "CAMARA", "IMPORTACION"}


def _generar_derivados(
    s: Session,
    almacen: storage.AlmacenDeObjetos,
    usuario: UsuarioActual,
    project_id: uuid.UUID,
    photo_id: uuid.UUID,
    datos: bytes,
) -> None:
    """Miniatura y vista previa. **Sin metadatos y con la orientación aplicada.**

    Los derivados son desechables: si se pierden se regeneran desde el original.
    Por eso su `stored_object` va con `is_original = FALSE` y sí se puede borrar.
    """
    for clase in DERIVADOS_AL_SUBIR:
        lado = storage.LADO_DE_DERIVADO[clase]
        try:
            binario = images.generar_derivado(datos, lado_maximo=lado, sin_metadatos=True)
        except Exception:  # noqa: BLE001 — un derivado fallido no invalida el original
            continue
        clave = storage.clave_de_derivado(usuario.organization_id, project_id, photo_id, clase)
        almacen.guardar(clave, binario)
        objeto = s.execute(
            text(
                "INSERT INTO stored_object (organization_id, project_id, kind, storage_key, "
                "sha256, byte_size, mime_type, is_original) "
                "VALUES (:o, :p, 'PHOTO_DERIVATIVE', :k, :h, :b, 'image/jpeg', FALSE) RETURNING id"
            ),
            {
                "o": str(usuario.organization_id),
                "p": str(project_id),
                "k": clave,
                "h": images.sha256_de(binario),
                "b": len(binario),
            },
        ).scalar_one()
        s.execute(
            text(
                "INSERT INTO photo_derivative (organization_id, photo_id, kind, stored_object_id, "
                "byte_size, has_metadata) "
                "VALUES (:o, :f, CAST(:k AS photo_derivative_kind), :obj, :b, FALSE)"
            ),
            {
                "o": str(usuario.organization_id),
                "f": str(photo_id),
                "k": clase,
                "obj": str(objeto),
                "b": len(binario),
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Consulta
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/projects/{project_id}/photos", response_model=list[Foto])
def listar(  # noqa: PLR0913 — filtros de §10.7, cada uno independiente
    project_id: uuid.UUID,
    s: SesionDep,
    asset_id: uuid.UUID | None = None,
    zone_id: uuid.UUID | None = None,
    technical_system_id: uuid.UUID | None = None,
    estado: str | None = Query(default=None, alias="status"),
    include_in_report: bool | None = None,
    has_gps: bool | None = None,
    papelera: bool = Query(default=False, alias="trash"),
    limite: int = Query(default=200, ge=1, le=1000, alias="limit"),
) -> Any:
    _proyecto_existe(s, project_id)
    filas = s.execute(
        text(
            f"""
            SELECT {_COLUMNAS} FROM photo
            WHERE project_id = :p
              AND (CASE WHEN :papelera THEN deleted_at IS NOT NULL ELSE deleted_at IS NULL END)
              AND (CAST(:activo AS uuid) IS NULL OR asset_id = CAST(:activo AS uuid))
              AND (CAST(:zona AS uuid) IS NULL OR zone_id = CAST(:zona AS uuid))
              AND (CAST(:sistema AS uuid) IS NULL
                   OR technical_system_id = CAST(:sistema AS uuid))
              AND (CAST(:estado AS text) IS NULL OR status::text = CAST(:estado AS text))
              AND (CAST(:informe AS boolean) IS NULL
                   OR include_in_report = CAST(:informe AS boolean))
              AND (CAST(:gps AS boolean) IS NULL
                   OR (gps_latitude IS NOT NULL) = CAST(:gps AS boolean))
            ORDER BY COALESCE(report_order, 2147483647), uploaded_at
            LIMIT :limite
            """
        ),
        {
            "p": str(project_id),
            "papelera": papelera,
            "activo": str(asset_id) if asset_id else None,
            "sistema": str(technical_system_id) if technical_system_id else None,
            "zona": str(zone_id) if zone_id else None,
            "estado": estado,
            "informe": include_in_report,
            "gps": has_gps,
            "limite": limite,
        },
    ).all()
    return [_fila_a_foto(f) for f in filas]


@router.get("/photos/{photo_id}", response_model=Foto)
def obtener(photo_id: uuid.UUID, s: SesionDep) -> Any:
    return _fila_a_foto(_obtener(s, photo_id))


@router.patch("/photos/{photo_id}", response_model=Foto)
def actualizar(
    photo_id: uuid.UUID, cuerpo: ActualizarFoto, s: SesionDep, usuario: UsuarioDep
) -> Any:
    """Clasificación, pie y selección para el informe.

    Renombrar es un `UPDATE` de `display_name`: **no se mueve un solo byte** y
    la extensión no se toca porque no está en este esquema.
    """
    actual = _obtener(s, photo_id)
    cambios = cuerpo.model_dump(exclude_unset=True)
    if not cambios:
        return _fila_a_foto(actual)

    if "display_name" in cambios:
        nombre = sanear(cambios["display_name"] or "")
        if not nombre:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "El nombre queda vacío tras el saneado",
            )
        if nombre.lower().endswith("." + actual.file_extension.lower()):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "El nombre visible se envía sin extensión: la fija el servidor",
            )
        cambios["display_name"] = nombre

    asignaciones = ", ".join(f"{c} = :{c}" for c in cambios)
    s.execute(
        text(f"UPDATE photo SET {asignaciones}, updated_at = now() WHERE id = :photo_id"),
        {**{k: v for k, v in cambios.items()}, "photo_id": str(photo_id)},
    )
    if "display_name" in cambios and cambios["display_name"] != actual.display_name:
        _registrar_renombrado(s, usuario, photo_id, actual.display_name, cambios["display_name"])
    return _fila_a_foto(_obtener(s, photo_id))


def _registrar_renombrado(
    s: Session, usuario: UsuarioActual, photo_id: uuid.UUID, antes: str, despues: str
) -> None:
    """Nueva versión `RENOMBRADA` **sin binario** y traza en auditoría."""
    s.execute(
        text("UPDATE photo_version SET is_current = FALSE WHERE photo_id = :f AND is_current"),
        {"f": str(photo_id)},
    )
    s.execute(
        text(
            "INSERT INTO photo_version (organization_id, photo_id, version_number, version_type, "
            "stored_object_id, display_name, is_current, created_by) "
            "SELECT :o, :f, COALESCE(MAX(version_number), 0) + 1, 'RENOMBRADA', NULL, :n, TRUE, :u "
            "FROM photo_version WHERE photo_id = :f"
        ),
        {"o": str(usuario.organization_id), "f": str(photo_id), "n": despues, "u": str(usuario.id)},
    )
    _auditar(s, usuario, "PHOTO_RENAMED", photo_id, {"antes": antes, "despues": despues})


# ─────────────────────────────────────────────────────────────────────────────
#  Renombrado en lote §15.4
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/photos/bulk-rename", response_model=ResultadoDeRenombrado)
def renombrar_en_lote(cuerpo: PeticionDeRenombrado, s: SesionDep, usuario: UsuarioDep) -> Any:
    """`[REQ]` Con `dry_run` (por defecto) devuelve la tabla antes/después **sin escribir**.

    Fallo parcial: el lote **no se deshace en bloque**. Se renombran las
    permitidas y se informa de las fallidas con su motivo. Es lo que un
    consultor espera: 38 de 40 es mejor que 0 de 40.
    """
    filas = s.execute(
        text(
            """
            SELECT p.id, p.display_name, p.file_extension, p.photo_category,
                   pr.internal_code AS proyecto, pr.name AS proyecto_nombre,
                   COALESCE(a.asset_code, a.name) AS activo, z.code AS zona,
                   ts.code AS sistema,
                   -- [Capitulo] es el capítulo de coste, «H08», no el código
                   -- entero: `HC.H08.03` sale de un elemento de nivel 3, y su
                   -- capítulo es el nivel 2. `split_part` lo saca de los dos.
                   split_part(COALESCE(cap.code, cc.code), '.', 2) AS capitulo,
                   u.full_name AS autor_nombre,
                   p.tags, p.taken_at, p.uploaded_at
            FROM photo p
            JOIN project pr ON pr.id = p.project_id
            LEFT JOIN asset a ON a.id = p.asset_id
            LEFT JOIN zone  z ON z.id = p.zone_id
            LEFT JOIN technical_system ts ON ts.id = p.technical_system_id
            LEFT JOIN capex_code cc ON cc.id = p.capex_code_id
            LEFT JOIN capex_code cap ON cap.id = cc.parent_id AND cc.level = 3
            LEFT JOIN app_user u ON u.id = p.uploaded_by
            WHERE p.id = ANY(CAST(:ids AS uuid[])) AND p.deleted_at IS NULL
            ORDER BY p.uploaded_at
            """
        ),
        {"ids": "{" + ",".join(str(i) for i in cuerpo.photo_ids) + "}"},
    ).all()

    contextos = [
        ContextoDeFoto(
            photo_id=f.id,
            nombre_actual=f.display_name,
            extension=f.file_extension,
            valores={
                "proyecto": f.proyecto,
                "proyecto_nombre": f.proyecto_nombre,
                "activo": f.activo,
                "zona": f.zona,
                # `[Sistema]`, `[Capitulo]` y `[Autor]` estaban en la tabla de
                # tokens de la documentación y ninguno se rellenaba: el primero
                # porque el dato no se guardaba —lo arregla la migración 0003— y
                # los otros dos porque esta consulta no los traía. La plantilla
                # por defecto lleva `[Sistema]`, así que **todo renombrado en
                # lote escribía «SinSistema»**.
                "sistema": f.sistema,
                "capitulo": f.capitulo or None,
                "categoria": f.photo_category,
                "etiqueta": (f.tags or [None])[0],
                "fecha": (f.taken_at or f.uploaded_at).strftime("%Y%m%d"),
                "hora": f.taken_at.strftime("%H%M") if f.taken_at else None,
                "autor": iniciales(f.autor_nombre),
            },
        )
        for f in filas
    ]
    plan = planificar_renombrado(
        contextos, plantilla=cuerpo.template, numerar_desde=cuerpo.numerar_desde
    )

    cambios = [
        CambioPropuesto(
            photo_id=c.photo_id,
            antes=c.antes,
            despues=c.despues,
            cambia=c.cambia,
            omitidos=list(c.omitidos),
        )
        for c in plan.cambios
    ]
    resultado = ResultadoDeRenombrado(
        dry_run=cuerpo.dry_run,
        cambios=cambios,
        colisiones_resueltas=list(plan.colisiones_resueltas),
        aplicados=0,
        fallidos=[],
    )
    if cuerpo.dry_run:
        return resultado

    aplicados = 0
    fallidos: list[dict[str, str]] = []
    for cambio in plan.cambios:
        if not cambio.cambia:
            continue
        try:
            with s.begin_nested():
                s.execute(
                    text("UPDATE photo SET display_name = :n, updated_at = now() WHERE id = :i"),
                    {"n": cambio.despues, "i": str(cambio.photo_id)},
                )
                _registrar_renombrado(s, usuario, cambio.photo_id, cambio.antes, cambio.despues)
            aplicados += 1
        except Exception as exc:  # noqa: BLE001 — se informa por foto, no se aborta el lote
            fallidos.append({"photo_id": str(cambio.photo_id), "motivo": type(exc).__name__})
    resultado.aplicados = aplicados
    resultado.fallidos = fallidos
    return resultado


# ─────────────────────────────────────────────────────────────────────────────
#  Duplicados, papelera y enlaces
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/projects/{project_id}/photos/duplicates", response_model=list[GrupoDeDuplicados])
def duplicados(project_id: uuid.UUID, s: SesionDep) -> Any:
    """Grupos por `sha256` y por `phash`. **Solo informa: no borra nada.**"""
    _proyecto_existe(s, project_id)
    grupos = agrupar_duplicados(_catalogo_del_proyecto(s, project_id))
    return [{"photo_ids": g} for g in grupos]


class PuntoDelMapa(BaseModel):
    """Una fotografía situada. Lo mínimo para pintarla y saber cuál es."""

    id: uuid.UUID
    latitude: float
    longitude: float
    display_name: str
    caption: str | None
    taken_at: datetime | None
    asset_id: uuid.UUID | None
    asset_name: str | None
    zone_name: str | None


class Mapa(BaseModel):
    puntos: list[PuntoDelMapa]
    #: `[REQ]` §15.6 · Cuántas fotografías **no** tienen coordenadas.
    #:
    #: Sin este número, un mapa con cuatro chinchetas parece decir «se hicieron
    #: cuatro fotos», cuando lo que dice es «cuatro traían GPS». La diferencia
    #: importa: en un sótano no hay señal, y muchos móviles llegan con la
    #: localización desactivada. La fecha y las coordenadas no se infieren
    #: nunca, así que lo honesto es decir cuántas faltan.
    sin_coordenadas: int
    #: Encuadre para que el mapa abra sobre las fotos y no sobre el Atlántico.
    #: `None` cuando no hay ninguna situada.
    encuadre: dict[str, float] | None = None


@router.get("/projects/{project_id}/photos/map", response_model=Mapa)
def mapa(project_id: uuid.UUID, s: SesionDep, asset_id: uuid.UUID | None = None) -> Any:
    """`[REQ]` §15.9 · Las fotografías situadas sobre el terreno.

    Endpoint propio y no un filtro sobre el listado: para pintar cuatrocientas
    chinchetas hacen falta seis campos, no los treinta de la ficha, y el
    recuento de las que **no** tienen coordenadas se calcula aquí de una vez en
    lugar de hacer que el cliente lo deduzca.
    """
    _proyecto_existe(s, project_id)
    filas = (
        s.execute(
            text(
                "SELECT p.id, p.gps_latitude AS latitude, p.gps_longitude AS longitude, "
                "p.display_name, p.caption, p.taken_at, p.asset_id, "
                "a.name AS asset_name, z.name_es AS zone_name "
                "FROM photo p "
                "LEFT JOIN asset a ON a.id = p.asset_id "
                "LEFT JOIN zone z ON z.id = p.zone_id "
                "WHERE p.project_id = :p AND p.deleted_at IS NULL "
                "  AND p.gps_latitude IS NOT NULL AND p.gps_longitude IS NOT NULL "
                "  AND (CAST(:a AS uuid) IS NULL OR p.asset_id = CAST(:a AS uuid)) "
                "ORDER BY p.taken_at NULLS LAST, p.uploaded_at"
            ),
            {"p": str(project_id), "a": str(asset_id) if asset_id else None},
        )
        .mappings()
        .all()
    )
    sin_coordenadas = s.execute(
        text(
            "SELECT count(*) FROM photo WHERE project_id = :p AND deleted_at IS NULL "
            "  AND (gps_latitude IS NULL OR gps_longitude IS NULL) "
            "  AND (CAST(:a AS uuid) IS NULL OR asset_id = CAST(:a AS uuid))"
        ),
        {"p": str(project_id), "a": str(asset_id) if asset_id else None},
    ).scalar_one()

    puntos = [dict(f) for f in filas]
    encuadre = None
    if puntos:
        lats = [float(p["latitude"]) for p in puntos]
        lons = [float(p["longitude"]) for p in puntos]
        encuadre = {
            "sur": min(lats),
            "norte": max(lats),
            "oeste": min(lons),
            "este": max(lons),
        }
    return {"puntos": puntos, "sin_coordenadas": sin_coordenadas, "encuadre": encuadre}


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def a_la_papelera(photo_id: uuid.UUID, s: SesionDep, usuario: UsuarioDep) -> None:
    """`[REQ]` El borrado es **siempre lógico**. El original sigue ahí."""
    fila = _obtener(s, photo_id)
    try:
        comprobar_transicion(EstadoDeFoto(fila.status), EstadoDeFoto.PAPELERA)
    except TransicionDeFotoNoPermitida as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    s.execute(
        text(
            "UPDATE photo SET status = 'PAPELERA', deleted_at = now(), "
            "include_in_report = FALSE, updated_at = now() WHERE id = :i"
        ),
        {"i": str(photo_id)},
    )
    _auditar(s, usuario, "PHOTO_TRASHED", photo_id, {"desde": fila.status})


@router.post("/photos/{photo_id}/restore", response_model=Foto)
def restaurar(photo_id: uuid.UUID, s: SesionDep, usuario: UsuarioDep) -> Any:
    fila = _obtener(s, photo_id)
    try:
        comprobar_transicion(EstadoDeFoto(fila.status), EstadoDeFoto.LISTA)
    except TransicionDeFotoNoPermitida as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    s.execute(
        text(
            "UPDATE photo SET status = 'LISTA', deleted_at = NULL, updated_at = now() WHERE id = :i"
        ),
        {"i": str(photo_id)},
    )
    _auditar(s, usuario, "PHOTO_RESTORED", photo_id, {})
    return _fila_a_foto(_obtener(s, photo_id))


@router.post("/photos/{photo_id}/links", status_code=status.HTTP_201_CREATED)
def enlazar(photo_id: uuid.UUID, cuerpo: Enlace, s: SesionDep, usuario: UsuarioDep) -> Any:
    """`[REQ]` Una foto se asocia a varias entidades y con distinto papel."""
    _obtener(s, photo_id)
    s.execute(
        text(
            "INSERT INTO photo_link (organization_id, photo_id, entity_type, entity_id, role, "
            "sort_order, created_by) VALUES (:o, :f, CAST(:t AS photo_link_entity), :e, "
            "CAST(:r AS photo_role), :s, :u) ON CONFLICT (photo_id, entity_type, entity_id) "
            "DO UPDATE SET role = EXCLUDED.role, sort_order = EXCLUDED.sort_order"
        ),
        {
            "o": str(usuario.organization_id),
            "f": str(photo_id),
            "t": cuerpo.entity_type.value,
            "e": str(cuerpo.entity_id),
            "r": cuerpo.role.value,
            "s": cuerpo.sort_order,
            "u": str(usuario.id),
        },
    )
    return {"photo_id": photo_id, **cuerpo.model_dump(mode="json")}


class Variante(StrEnum):
    """Qué versión del archivo se pide.

    Los derivados se generaban al subir la foto pero **no los servía nadie**: la
    rejilla de miniaturas pedía el original de cada una, y una visita de 400
    fotos son 400 archivos de 4 MB para pintar recuadros de 320 píxeles.
    """

    ORIGINAL = "ORIGINAL"
    MINIATURA = "MINIATURA_320"
    VISTA = "VISTA_1600"


@router.get("/photos/{photo_id}/download")
def descargar(
    photo_id: uuid.UUID,
    s: SesionDep,
    usuario: UsuarioDep,
    almacen: AlmacenDep,
    variante: Variante = Variante.ORIGINAL,
) -> Any:
    """`[REQ]` Toda descarga genera `audit_log`.

    `[LIM]` Devuelve el binario en la respuesta. En producción debe ser un
    `302` a una URL firmada de 5 minutos (§10.7); eso depende del adaptador S3,
    que no está implementado.
    """
    fila = _obtener(s, photo_id)
    clave: str | None = None
    if variante is not Variante.ORIGINAL:
        clave = s.execute(
            text(
                "SELECT o.storage_key FROM photo_derivative d "
                "JOIN stored_object o ON o.id = d.stored_object_id "
                "WHERE d.photo_id = :i AND d.kind = CAST(:k AS photo_derivative_kind)"
            ),
            {"i": str(photo_id), "k": variante.value},
        ).scalar_one_or_none()
        # Si el derivado no está —una foto subida antes de que existieran, o un
        # formato del que no se pudo generar—, se sirve el original. Devolver un
        # 404 dejaría el hueco vacío en la rejilla, que parece un fallo de la
        # foto y no de una miniatura que falta.
    if clave is None:
        clave = s.execute(
            text(
                "SELECT o.storage_key FROM stored_object o "
                "JOIN photo p ON p.stored_object_id = o.id WHERE p.id = :i"
            ),
            {"i": str(photo_id)},
        ).scalar_one()
        variante = Variante.ORIGINAL

    datos = almacen.leer(clave)
    # Solo el original cuenta como «descarga» en la auditoría: anotar cada
    # miniatura llenaría el registro de ruido y taparía las descargas de verdad.
    if variante is Variante.ORIGINAL:
        _auditar(s, usuario, "PHOTO_DOWNLOADED", photo_id, {"bytes": len(datos)})

    nombre = f"{fila.display_name}.{fila.file_extension}"
    return Response(
        content=datos,
        # Los derivados son siempre JPEG: se generan así, aunque el original sea
        # HEIC o PNG. Devolver el MIME del original haría que el navegador no
        # pintara un HEIC que en realidad ya venía convertido.
        media_type=fila.mime_type if variante is Variante.ORIGINAL else "image/jpeg",
        headers={
            # `inline` en los derivados: se piden para mirarlos en pantalla, y
            # con `attachment` el navegador ofrecería guardar cada miniatura.
            "Content-Disposition": (
                f'attachment; filename="{nombre}"'
                if variante is Variante.ORIGINAL
                else f'inline; filename="{nombre}"'
            )
        },
    )


@router.get("/projects/{project_id}/photos/report-warnings")
def avisos_de_informe(project_id: uuid.UUID, s: SesionDep) -> Any:
    """Lo que conviene mirar antes de generar el PPTX (§15.10)."""
    _proyecto_existe(s, project_id)
    filas = s.execute(
        text(
            "SELECT id, status::text AS status, include_in_report, asset_id, caption, "
            "gps_latitude, gps_longitude FROM photo "
            "WHERE project_id = :p AND deleted_at IS NULL"
        ),
        {"p": str(project_id)},
    ).all()
    fotos = [
        FotoParaInforme(
            id=f.id,
            estado=EstadoDeFoto(f.status),
            include_in_report=f.include_in_report,
            asset_id=f.asset_id,
            caption=f.caption,
            gps=(float(f.gps_latitude), float(f.gps_longitude)) if f.gps_latitude else None,
        )
        for f in filas
    ]
    avisos = avisos_previos_al_informe(fotos)
    return [
        {
            "codigo": a.codigo,
            "severidad": a.severidad.value,
            "mensaje": a.mensaje,
            "photo_id": a.photo_id,
        }
        for a in avisos
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  Versiones §15.2
# ─────────────────────────────────────────────────────────────────────────────


class Version(BaseModel):
    id: uuid.UUID
    version_number: int
    version_type: str
    display_name: str
    #: `NULL` cuando la versión solo cambia metadatos: renombrar **no duplica
    #: el binario**.
    stored_object_id: uuid.UUID | None
    annotations: dict[str, Any] | None
    is_current: bool
    created_at: datetime


@router.get("/photos/{photo_id}/versions", response_model=list[Version])
def listar_versiones(photo_id: uuid.UUID, s: SesionDep) -> Any:
    _obtener(s, photo_id)
    filas = (
        s.execute(
            text(
                "SELECT id, version_number, CAST(version_type AS text) AS version_type, "
                "display_name, stored_object_id, annotations, is_current, created_at "
                "FROM photo_version WHERE photo_id = :f ORDER BY version_number"
            ),
            {"f": str(photo_id)},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


class Anotaciones(BaseModel):
    """`[REC]` §15.2 · Capa **vectorial**, no píxeles quemados.

    Editables, reversibles, ocupan bytes en lugar de megabytes, y el original
    sigue limpio. Se rasteriza solo cuando hace falta —informe o exportación—
    y ese JPEG es un derivado desechable.
    """

    model_config = ConfigDict(extra="forbid")

    annotations: dict[str, Any]
    notes: str | None = None


@router.post(
    "/photos/{photo_id}/versions/annotate",
    status_code=status.HTTP_201_CREATED,
    response_model=list[Version],
)
def anotar(photo_id: uuid.UUID, cuerpo: Anotaciones, s: SesionDep, usuario: UsuarioDep) -> Any:
    """Añade una versión anotada. **El original no se toca.**

    `[REQ]` §15.2 · La capa se valida forma a forma. Antes bastaba con que el
    JSON trajera una clave `shapes` y dentro podía ir cualquier cosa: quien
    rasteriza después solo tiene malas opciones ante un dato imposible —adivinar,
    reventar, o dibujar algo que nadie pidió—, y el sitio donde se descubriría
    sería el informe ya entregado.
    """
    from tdd.evidence.anotaciones import AnotacionInvalida
    from tdd.evidence.anotaciones import leer as leer_capa

    _obtener(s, photo_id)
    try:
        capa = leer_capa(cuerpo.annotations)
    except AnotacionInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    s.execute(
        text("UPDATE photo_version SET is_current = FALSE WHERE photo_id = :f AND is_current"),
        {"f": str(photo_id)},
    )
    s.execute(
        text(
            "INSERT INTO photo_version (organization_id, photo_id, version_number, version_type, "
            "stored_object_id, display_name, annotations, notes, is_current, created_by) "
            "SELECT :o, :f, COALESCE(MAX(pv.version_number), 0) + 1, 'ANOTADA', NULL, "
            "  (SELECT display_name FROM photo WHERE id = :f), CAST(:a AS jsonb), :n, TRUE, :u "
            "FROM photo_version pv WHERE pv.photo_id = :f"
        ),
        {
            "o": str(usuario.organization_id),
            "f": str(photo_id),
            # Se guarda lo NORMALIZADO, no lo que llegó: así lo que se lee al
            # editar es exactamente lo que se va a pintar en el informe.
            "a": _json(capa.como_json()),
            "n": cuerpo.notes,
            "u": str(usuario.id),
        },
    )
    _auditar(s, usuario, "PHOTO_ANNOTATED", photo_id, {"formas": len(capa.formas)})
    return listar_versiones(photo_id, s)


@router.post("/photo-versions/{version_id}/restore", response_model=list[Version])
def restaurar_version(version_id: uuid.UUID, s: SesionDep, usuario: UsuarioDep) -> Any:
    """`[REQ]` §15.2 · Restaurar **crea una versión nueva**; no reescribe la
    historia.

    Que el estado anterior desaparezca del historial sería exactamente lo que
    una evidencia técnica no puede permitirse.
    """
    origen = (
        s.execute(
            text(
                "SELECT photo_id, CAST(version_type AS text) AS version_type, display_name, "
                "annotations, stored_object_id FROM photo_version WHERE id = :i"
            ),
            {"i": str(version_id)},
        )
        .mappings()
        .first()
    )
    if origen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Versión no encontrada")

    photo_id = origen["photo_id"]
    s.execute(
        text("UPDATE photo_version SET is_current = FALSE WHERE photo_id = :f AND is_current"),
        {"f": str(photo_id)},
    )
    # La versión nueva es RESTAURADA salvo que reponga el estado original, en
    # cuyo caso es un simple renombrado al nombre de llegada.
    tipo = "ANOTADA" if origen["annotations"] else "RENOMBRADA"
    s.execute(
        text(
            "INSERT INTO photo_version (organization_id, photo_id, version_number, version_type, "
            "stored_object_id, display_name, annotations, notes, is_current, created_by) "
            "SELECT :o, :f, COALESCE(MAX(version_number), 0) + 1, CAST(:t AS photo_version_type), "
            "  NULL, :n, CAST(:a AS jsonb), :nota, TRUE, :u "
            "FROM photo_version WHERE photo_id = :f"
        ),
        {
            "o": str(usuario.organization_id),
            "f": str(photo_id),
            "t": tipo,
            "n": origen["display_name"],
            "a": _json(origen["annotations"]) if origen["annotations"] else None,
            "nota": f"Restaurada desde la versión {version_id}",
            "u": str(usuario.id),
        },
    )
    s.execute(
        text("UPDATE photo SET display_name = :n, updated_at = now() WHERE id = :i"),
        {"n": origen["display_name"], "i": str(photo_id)},
    )
    _auditar(s, usuario, "PHOTO_VERSION_RESTORED", photo_id, {"desde": str(version_id)})
    return listar_versiones(photo_id, s)


# ─────────────────────────────────────────────────────────────────────────────
#  Clasificación en lote
# ─────────────────────────────────────────────────────────────────────────────


class ActualizacionEnLote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    photo_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    asset_id: uuid.UUID | None = None
    zone_id: uuid.UUID | None = None
    #: Clasificar «las de la cubierta» de una vez es lo que hace usable una
    #: visita de 400 fotos, y es justo lo que alimenta el nombre del fichero.
    technical_system_id: uuid.UUID | None = None
    photo_category: str | None = Field(default=None, max_length=60)
    include_in_report: bool | None = None
    report_section: str | None = Field(default=None, max_length=60)
    #: Se **añaden** a las existentes. Sustituirlas borraría en silencio el
    #: trabajo de clasificación de otra persona.
    add_tags: list[str] = Field(default_factory=list)


@router.post("/photos/bulk-update", response_model=list[Foto])
def actualizar_en_lote(cuerpo: ActualizacionEnLote, s: SesionDep) -> Any:
    """Clasificación y etiquetas en lote.

    Es la operación que hace usable una visita de 400 fotos: seleccionar las de
    la cubierta y asignarlas de una vez, en lugar de abrir cuatrocientas fichas.
    """
    cambios = cuerpo.model_dump(exclude_unset=True, exclude={"photo_ids", "add_tags"})
    ids = "{" + ",".join(str(i) for i in cuerpo.photo_ids) + "}"

    if cambios:
        asignaciones = ", ".join(f"{c} = :{c}" for c in cambios)
        s.execute(
            text(  # noqa: S608
                f"UPDATE photo SET {asignaciones}, updated_at = now() "
                "WHERE id = ANY(CAST(:ids AS uuid[])) AND deleted_at IS NULL"
            ),
            {**cambios, "ids": ids},
        )
    if cuerpo.add_tags:
        s.execute(
            text(
                "UPDATE photo SET "
                "  tags = ARRAY(SELECT DISTINCT unnest(tags || CAST(:t AS text[]))), "
                "  updated_at = now() "
                "WHERE id = ANY(CAST(:ids AS uuid[])) AND deleted_at IS NULL"
            ),
            {"t": "{" + ",".join(f'"{t}"' for t in cuerpo.add_tags) + "}", "ids": ids},
        )

    filas = s.execute(
        text(f"SELECT {_COLUMNAS} FROM photo WHERE id = ANY(CAST(:ids AS uuid[]))"),  # noqa: S608
        {"ids": ids},
    ).all()
    return [_fila_a_foto(f) for f in filas]


# ─────────────────────────────────────────────────────────────────────────────
#  Descarga en lote §15.7
# ─────────────────────────────────────────────────────────────────────────────


class DescargaEnLote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    photo_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    #: `[REQ]` §15.6 · Activado por defecto: la exportación para el cliente no
    #: lleva GPS ni número de serie del dispositivo.
    strip_metadata: bool = True
    #: Usar el nombre visible en vez del de llegada. Es lo que hace navegable
    #: un ZIP de 400 fotos.
    use_display_names: bool = True


@router.post("/projects/{project_id}/photos/download-batch")
def descargar_en_lote(
    project_id: uuid.UUID,
    cuerpo: DescargaEnLote,
    s: SesionDep,
    usuario: UsuarioDep,
    almacen: AlmacenDep,
) -> Any:
    """`[REQ]` ZIP con las fotos seleccionadas.

    `[LIM]` Se construye **en la propia petición**. §15.7 pide hacerlo en el
    worker con enlace caducable, y con 400 fotos esto tardará y ocupará memoria.
    El límite de 500 y el tope de tamaño evitan lo peor, pero mover esto al
    worker sigue pendiente y no se afirma lo contrario.
    """
    _proyecto_existe(s, project_id)
    filas = (
        s.execute(
            text(
                "SELECT p.id, p.display_name, p.original_filename, p.file_extension, "
                "o.storage_key FROM photo p JOIN stored_object o ON o.id = p.stored_object_id "
                "WHERE p.project_id = :proy AND p.id = ANY(CAST(:ids AS uuid[])) "
                "  AND p.deleted_at IS NULL AND p.status = 'LISTA' ORDER BY p.report_order, "
                "  p.uploaded_at"
            ),
            {
                "proy": str(project_id),
                "ids": "{" + ",".join(str(i) for i in cuerpo.photo_ids) + "}",
            },
        )
        .mappings()
        .all()
    )
    if not filas:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Ninguna de las fotografías indicadas está disponible"
        )

    nombres = [
        f"{f['display_name']}.{f['file_extension']}"
        if cuerpo.use_display_names
        else f["original_filename"]
        for f in filas
    ]
    # Dentro de un ZIP dos ficheros pueden llamarse igual, y al descomprimir uno
    # pisa al otro sin avisar. El sufijo alfabético lo evita.
    nombres = resolver_colisiones(nombres)

    memoria = io.BytesIO()
    total = 0
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        for fila, nombre in zip(filas, nombres, strict=True):
            datos = almacen.leer(fila["storage_key"])
            if cuerpo.strip_metadata:
                # [REQ] §15.6 · Se elimina GPS, número de serie y propietario.
                # Se hace regenerando la imagen: `exif=None` al guardar no basta,
                # porque `save` arrastra el bloque original si existe.
                try:
                    datos = images.generar_derivado(
                        datos, lado_maximo=4096, calidad=92, sin_metadatos=True
                    )
                except Exception:  # noqa: BLE001 — si no se puede limpiar, no se incluye
                    continue
            total += len(datos)
            if total > MAX_ZIP_BYTES:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    "La selección supera el tamaño máximo de descarga directa. "
                    "Reduzca el número de fotografías.",
                )
            z.writestr(nombre, datos)

    _auditar(
        s,
        usuario,
        "PHOTO_BATCH_DOWNLOADED",
        filas[0]["id"],
        {"fotos": len(filas), "sin_metadatos": cuerpo.strip_metadata},
    )
    return Response(
        content=memoria.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="fotografias.zip"'},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Purga §15.9
# ─────────────────────────────────────────────────────────────────────────────


class Purga(BaseModel):
    """La purga es física e irreversible, así que la autorización es explícita."""

    model_config = ConfigDict(extra="forbid")

    confirmar: bool = False
    motivo: str = Field(min_length=10, max_length=500)


@router.post("/photos/{photo_id}/purge", status_code=status.HTTP_204_NO_CONTENT)
def purgar(
    photo_id: uuid.UUID, cuerpo: Purga, s: SesionDep, usuario: UsuarioDep, almacen: AlmacenDep
) -> None:
    """`[REQ]` §15.9 · Borra el binario y **conserva el registro de auditoría**.

    Lo que queda: identificador, hash, quién la subió, quién la purgó y con qué
    autorización. Sin contenido. Un registro que también desapareciera dejaría
    la purga sin rastro, que es justo lo contrario de lo que se busca.
    """
    if not cuerpo.confirmar:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "La purga es irreversible y exige confirmación explícita",
        )
    if usuario.org_role not in ("ADMIN", "DIRECTOR_PROYECTO"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Solo un administrador o director puede autorizar una purga"
        )

    fila = (
        s.execute(
            text(
                "SELECT p.status::text AS status, p.deleted_at, p.sha256, p.uploaded_by, "
                "o.storage_key, "
                "EXISTS (SELECT 1 FROM photo_link pl WHERE pl.photo_id = p.id "
                "        AND pl.entity_type = 'REPORT_SECTION') AS en_informe "
                "FROM photo p JOIN stored_object o ON o.id = p.stored_object_id WHERE p.id = :i"
            ),
            {"i": str(photo_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fotografía no encontrada")

    try:
        comprobar_purga(
            estado=EstadoDeFoto(fila["status"]),
            borrada_el=fila["deleted_at"],
            ahora=datetime.now(UTC),
            referenciada_por_informe_emitido=fila["en_informe"],
        )
    except PurgaNoPermitida as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, str(exc), headers={"X-Motivo": exc.codigo}
        ) from exc

    # El registro de auditoría va ANTES de borrar: si el borrado falla a medias,
    # queda constancia del intento en lugar de un hueco silencioso.
    _auditar(
        s,
        usuario,
        "PHOTO_PURGED",
        photo_id,
        {
            "sha256": fila["sha256"],
            "subida_por": str(fila["uploaded_by"]),
            "purgada_por": str(usuario.id),
            "motivo": cuerpo.motivo,
        },
    )
    # Los derivados sí se borran del almacén: son regenerables y ya no lo serán.
    for clave in (
        s.execute(
            text(
                "SELECT o.storage_key FROM photo_derivative d "
                "JOIN stored_object o ON o.id = d.stored_object_id WHERE d.photo_id = :i"
            ),
            {"i": str(photo_id)},
        )
        .scalars()
        .all()
    ):
        almacen.borrar(clave)

    s.execute(
        text(
            "UPDATE photo SET status = 'PURGADA', purged_at = now(), exif_raw = NULL, "
            "gps_latitude = NULL, gps_longitude = NULL, caption = NULL, updated_at = now() "
            "WHERE id = :i"
        ),
        {"i": str(photo_id)},
    )

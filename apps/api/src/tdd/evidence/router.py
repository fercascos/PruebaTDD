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

import json
import uuid
from datetime import datetime
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
from tdd.evidence.naming import PLANTILLA_POR_DEFECTO, sanear
from tdd.evidence.service import (
    ContextoDeFoto,
    EstadoDeFoto,
    FotoConocida,
    FotoParaInforme,
    TipoDeDuplicado,
    TransicionDeFotoNoPermitida,
    agrupar_duplicados,
    avisos_previos_al_informe,
    buscar_duplicado,
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


class Enlace(BaseModel):
    entity_type: str
    entity_id: uuid.UUID
    role: str = "EVIDENCIA"
    sort_order: int = 0


# ─────────────────────────────────────────────────────────────────────────────
#  Auxiliares
# ─────────────────────────────────────────────────────────────────────────────

_COLUMNAS = """
    id, project_id, asset_id, zone_id, status::text AS status, origin::text AS origin,
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
                id, organization_id, project_id, asset_id, zone_id, stored_object_id,
                origin, status, original_filename, display_name, file_extension, mime_type,
                sha256, phash, byte_size, width_px, height_px, taken_at,
                gps_latitude, gps_longitude, camera_make, camera_model, orientation,
                exif_raw, caption, duplicate_of_photo_id, uploaded_by
            ) VALUES (
                :id, :org, :proy, :activo, :zona, :objeto,
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
                   a.name AS activo, z.code AS zona, p.tags, p.taken_at, p.uploaded_at
            FROM photo p
            JOIN project pr ON pr.id = p.project_id
            LEFT JOIN asset a ON a.id = p.asset_id
            LEFT JOIN zone  z ON z.id = p.zone_id
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
                "categoria": f.photo_category,
                "etiqueta": (f.tags or [None])[0],
                "fecha": (f.taken_at or f.uploaded_at).strftime("%Y%m%d"),
                "hora": f.taken_at.strftime("%H%M") if f.taken_at else None,
                "autor": None,
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
            "t": cuerpo.entity_type,
            "e": str(cuerpo.entity_id),
            "r": cuerpo.role,
            "s": cuerpo.sort_order,
            "u": str(usuario.id),
        },
    )
    return {"photo_id": photo_id, **cuerpo.model_dump()}


@router.get("/photos/{photo_id}/download")
def descargar(photo_id: uuid.UUID, s: SesionDep, usuario: UsuarioDep, almacen: AlmacenDep) -> Any:
    """`[REQ]` Toda descarga genera `audit_log`.

    `[LIM]` Devuelve el binario en la respuesta. En producción debe ser un
    `302` a una URL firmada de 5 minutos (§10.7); eso depende del adaptador S3,
    que no está implementado.
    """
    fila = _obtener(s, photo_id)
    clave = s.execute(
        text(
            "SELECT o.storage_key FROM stored_object o "
            "JOIN photo p ON p.stored_object_id = o.id WHERE p.id = :i"
        ),
        {"i": str(photo_id)},
    ).scalar_one()
    datos = almacen.leer(clave)
    _auditar(s, usuario, "PHOTO_DOWNLOADED", photo_id, {"bytes": len(datos)})
    return Response(
        content=datos,
        media_type=fila.mime_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{fila.display_name}.{fila.file_extension}"'
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

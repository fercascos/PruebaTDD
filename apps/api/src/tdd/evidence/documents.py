"""Documentos `[REQ]` §15.11.

Comparten con las fotografías todo lo que importa —original inmutable, MIME
real, hash, borrado lógico, descarga auditada— y se diferencian en cuatro
cosas, que son justo las que justifican tener módulo propio:

1. **Sin derivados de imagen.** La previsualización de PDF se hace en el
   cliente; el servidor no rasteriza nada.
2. **Nivel de confidencialidad** que condiciona quién puede descargarlos.
3. **Versionado explícito.** Las rondas de Q&A y la documentación recibida se
   sustituyen con frecuencia, y hay que saber cuál era la vigente **en la fecha
   del informe**. Sin esto, un informe firmado sobre la versión 2 de un plano
   parecería basarse en la 5.
4. **Clasificación automática desde la fase**: adjuntar un documento a una
   línea del checklist le asigna su `doc_type` sin que el usuario lo elija.

`[REQ]` **Se rechazan ejecutables, ficheros con macros y comprimidos.** La
comprobación mira el contenido, no la extensión: renombrar `.exe` a `.pdf` es
lo primero que se intenta.
"""

from __future__ import annotations

import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core.deps import SesionDep, UsuarioActual, UsuarioDep
from tdd.evidence import images, storage
from tdd.evidence.naming import sanear
from tdd.evidence.router import AlmacenDep

router = APIRouter(tags=["Documentos"])

#: `[SUP]` Un plano en PDF ronda los 20-40 MB; 100 deja margen sin abrir la
#: puerta a subir una copia de seguridad entera.
MAX_BYTES_DOCUMENTO = 100 * 1024 * 1024

#: Extensiones admitidas `[REQ]` §15.11.
EXTENSIONES_ADMITIDAS = frozenset(
    {"pdf", "docx", "doc", "xlsx", "xls", "dwg", "dxf", "jpg", "jpeg", "png", "tif", "tiff", "txt"}
)

#: Firmas de contenido que se rechazan **sin mirar la extensión**.
#: `[REQ]` Renombrar `.exe` a `.pdf` es lo primero que se intenta.
_FIRMAS_PROHIBIDAS: tuple[tuple[bytes, str], ...] = (
    (b"MZ", "ejecutable de Windows"),
    (b"\x7fELF", "ejecutable de Linux"),
    (b"\xca\xfe\xba\xbe", "ejecutable de macOS"),
    (b"#!", "script ejecutable"),
    (b"Rar!", "archivo comprimido"),
    (b"7z\xbc\xaf\x27\x1c", "archivo comprimido"),
    (b"\x1f\x8b", "archivo comprimido"),
)

#: `[REQ]` Contenedores OOXML que llevan macros. Un `.docm` disfrazado de
#: `.docx` se detecta por su contenido, no por su nombre.
_MARCAS_DE_MACRO = (b"vbaProject.bin", b"vbaData.xml")


class ContenidoRechazado(ValueError):
    """El fichero no puede aceptarse por lo que contiene."""


def comprobar_contenido(datos: bytes, *, extension: str) -> None:
    """`[REQ]` Rechaza ejecutables, macros y comprimidos anidados.

    El orden importa: primero la firma binaria —que no se puede falsear
    renombrando— y solo después la extensión declarada.
    """
    if not datos:
        raise ContenidoRechazado("El fichero está vacío")

    cabecera = datos[:8]
    for firma, que_es in _FIRMAS_PROHIBIDAS:
        if cabecera.startswith(firma):
            raise ContenidoRechazado(
                f"No se admiten {que_es}s. El contenido del fichero es un {que_es}, "
                "independientemente de su extensión."
            )

    es_ooxml = cabecera.startswith(b"PK\x03\x04")
    if es_ooxml and any(marca in datos for marca in _MARCAS_DE_MACRO):
        # [REQ] Un `.docm` renombrado a `.docx` sigue llevando el proyecto VBA
        # dentro del contenedor; buscarlo ahí es lo único que lo detecta.
        raise ContenidoRechazado("No se admiten documentos con macros")
    if es_ooxml and extension not in {"docx", "xlsx", "pptx", "dwg", "dxf"}:
        raise ContenidoRechazado(
            "El fichero es un contenedor comprimido. Solo se admiten como documentos "
            "ofimáticos, no como archivo suelto: un ZIP anidado puede ser una bomba "
            "de descompresión."
        )

    if extension not in EXTENSIONES_ADMITIDAS:
        raise ContenidoRechazado(
            f"Extensión «{extension}» no admitida. Se aceptan: "
            f"{', '.join(sorted(EXTENSIONES_ADMITIDAS))}"
        )


class Documento(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    asset_id: uuid.UUID | None
    doc_request_item_id: uuid.UUID | None
    qa_round_id: uuid.UUID | None
    original_filename: str
    display_name: str
    file_extension: str
    mime_type: str
    sha256: str
    byte_size: int
    doc_type: str
    confidentiality: str
    status: str
    version_number: int
    supersedes_document_id: uuid.UUID | None
    notes: str | None
    uploaded_by: uuid.UUID


class ActualizarDocumento(BaseModel):
    """`storage_key` y `sha256` no aparecen: no son escribibles."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    doc_type: str | None = None
    confidentiality: str | None = None
    asset_id: uuid.UUID | None = None
    notes: str | None = None


_CAMPOS = """
    id, project_id, asset_id, doc_request_item_id, qa_round_id, original_filename,
    display_name, file_extension, mime_type, sha256, byte_size,
    CAST(doc_type AS text) AS doc_type, CAST(confidentiality AS text) AS confidentiality,
    CAST(status AS text) AS status, version_number, supersedes_document_id, notes, uploaded_by
"""

#: `[REC]` §15.11 · Adjuntar a una línea del checklist clasifica el documento
#: solo. La correspondencia va por el código de la categoría documental.
_TIPO_POR_CATEGORIA = {
    "LICENCIAS": "LICENCIA_URBANISTICA",
    "URBANISMO": "LICENCIA_URBANISTICA",
    "PROYECTOS": "PROYECTO",
    "PROYECTO": "PROYECTO",
    "MANTENIMIENTO": "CONTRATO_MANTENIMIENTO",
    "LEGALIZACIONES": "LEGALIZACION",
    "LEGALIZACION": "LEGALIZACION",
    "CERTIFICADOS": "CERTIFICADO",
    "GARANTIAS": "GARANTIA",
    "PLANOS": "PLANO",
    "INFORMES": "INFORME_PREVIO",
}


def _leer(s: Session, document_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text(f"SELECT {_CAMPOS} FROM document WHERE id = :i"),  # noqa: S608
            {"i": str(document_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    return dict(fila)


def _auditar(
    s: Session, usuario: UsuarioActual, accion: str, document_id: uuid.UUID, detalle: dict[str, Any]
) -> None:
    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, after_data) VALUES (:o, :u, :a, 'document', :e, CAST(:p AS jsonb))"
        ),
        {
            "o": str(usuario.organization_id),
            "u": str(usuario.id),
            "a": accion,
            "e": str(document_id),
            "p": json.dumps(detalle, ensure_ascii=False, default=str),
        },
    )


@router.post(
    "/projects/{project_id}/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=Documento,
)
def subir(  # noqa: PLR0913 — son campos de formulario, no parámetros de diseño
    project_id: uuid.UUID,
    s: SesionDep,
    usuario: UsuarioDep,
    almacen: AlmacenDep,
    archivo: Annotated[UploadFile, File(alias="file")],
    doc_type: Annotated[str | None, Form()] = None,
    confidentiality: Annotated[str, Form()] = "INTERNO",
    asset_id: Annotated[uuid.UUID | None, Form()] = None,
    doc_request_item_id: Annotated[uuid.UUID | None, Form()] = None,
    qa_round_id: Annotated[uuid.UUID | None, Form()] = None,
    supersedes_document_id: Annotated[uuid.UUID | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
) -> Any:
    """Sube un documento. **El original se guarda tal cual llegó.**"""
    if (
        s.execute(
            text("SELECT 1 FROM project WHERE id = :p AND deleted_at IS NULL"),
            {"p": str(project_id)},
        ).first()
        is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")

    datos = archivo.file.read()
    if len(datos) > MAX_BYTES_DOCUMENTO:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"El archivo supera el máximo de {MAX_BYTES_DOCUMENTO // (1024 * 1024)} MB",
        )
    nombre = archivo.filename or "documento"
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    try:
        comprobar_contenido(datos, extension=extension)
    except ContenidoRechazado as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc

    sha = images.sha256_de(datos)
    ya_esta = s.execute(
        text(
            "SELECT id, display_name FROM document WHERE project_id = :p AND sha256 = :h "
            "AND deleted_at IS NULL"
        ),
        {"p": str(project_id), "h": sha},
    ).first()
    if ya_esta is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Este documento ya está en el proyecto como «{ya_esta.display_name}» "
            f"({ya_esta.id}). Para sustituirlo, súbalo indicando a cuál reemplaza.",
        )

    # [REC] Clasificación automática desde la fase: si el documento se adjunta a
    # una línea del checklist, hereda su tipo. Elegirlo a mano cuando el sistema
    # ya lo sabe es trabajo repetido y una fuente de incoherencias.
    tipo = doc_type
    if tipo is None and doc_request_item_id is not None:
        codigo = s.execute(
            text(
                "SELECT c.code FROM doc_request_item d "
                "JOIN doc_request_category c ON c.id = d.category_id WHERE d.id = :i"
            ),
            {"i": str(doc_request_item_id)},
        ).scalar()
        tipo = _TIPO_POR_CATEGORIA.get((codigo or "").upper())
    if tipo is None and qa_round_id is not None:
        tipo = "QA"
    tipo = tipo or "OTRO"

    version = 1
    if supersedes_document_id is not None:
        anterior = s.execute(
            text("SELECT version_number FROM document WHERE id = :i"),
            {"i": str(supersedes_document_id)},
        ).scalar()
        if anterior is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "El documento al que sustituye no existe"
            )
        version = int(anterior) + 1

    document_id = uuid.uuid4()
    clave = storage.clave_de_documento(usuario.organization_id, project_id, document_id, extension)
    almacen.guardar(clave, datos)

    objeto = s.execute(
        text(
            "INSERT INTO stored_object (organization_id, project_id, kind, storage_key, sha256, "
            "byte_size, mime_type, is_original) "
            "VALUES (:o, :p, 'DOCUMENT', :k, :h, :b, :m, TRUE) RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "p": str(project_id),
            "k": clave,
            "h": sha,
            "b": len(datos),
            "m": archivo.content_type or "application/octet-stream",
        },
    ).scalar_one()

    visible = sanear(nombre.rsplit(".", 1)[0])[:200] or f"Documento{document_id.hex[:8]}"
    s.execute(
        text(
            "INSERT INTO document (id, organization_id, project_id, asset_id, "
            "doc_request_item_id, qa_round_id, stored_object_id, original_filename, display_name, "
            "file_extension, mime_type, sha256, byte_size, doc_type, confidentiality, "
            "version_number, supersedes_document_id, notes, uploaded_by) "
            "VALUES (:id, :o, :p, :a, :sol, :qa, :obj, :llegada, :visible, :ext, :mime, :sha, "
            ":bytes, CAST(:tipo AS doc_type), CAST(:conf AS doc_confidentiality), :ver, :sust, "
            ":notas, :u)"
        ),
        {
            "id": str(document_id),
            "o": str(usuario.organization_id),
            "p": str(project_id),
            "a": str(asset_id) if asset_id else None,
            "sol": str(doc_request_item_id) if doc_request_item_id else None,
            "qa": str(qa_round_id) if qa_round_id else None,
            "obj": str(objeto),
            "llegada": nombre[:260],
            "visible": visible,
            "ext": extension or "bin",
            "mime": archivo.content_type or "application/octet-stream",
            "sha": sha,
            "bytes": len(datos),
            "tipo": tipo,
            "conf": confidentiality,
            "ver": version,
            "sust": str(supersedes_document_id) if supersedes_document_id else None,
            "notas": notes,
            "u": str(usuario.id),
        },
    )
    _auditar(s, usuario, "DOCUMENT_UPLOADED", document_id, {"sha256": sha, "doc_type": tipo})

    # Recibir el documento adelanta la línea del checklist: es la razón por la
    # que existe esa línea, y marcarla a mano después se olvida siempre.
    if doc_request_item_id is not None:
        s.execute(
            text(
                "UPDATE doc_request_item SET status = 'RECIBIDA', "
                "received_at = COALESCE(received_at, now()) "
                "WHERE id = :i AND status IN ('SOLICITADA', 'PARCIAL')"
            ),
            {"i": str(doc_request_item_id)},
        )
    return _leer(s, document_id)


@router.get("/projects/{project_id}/documents", response_model=list[Documento])
def listar(
    project_id: uuid.UUID,
    s: SesionDep,
    doc_type: str | None = None,
    asset_id: uuid.UUID | None = None,
    solo_vigentes: bool = Query(default=True, alias="current_only"),
) -> Any:
    """Por defecto **solo la versión vigente** de cada documento.

    Un listado que mezcle las cinco versiones de un plano no ayuda a nadie: lo
    normal es querer la última, y el historial se pide expresamente.
    """
    filas = (
        s.execute(
            text(  # noqa: S608
                f"""
                SELECT {_CAMPOS} FROM document d
                WHERE d.project_id = :p AND d.deleted_at IS NULL
                  AND (CAST(:tipo AS text) IS NULL OR d.doc_type::text = CAST(:tipo AS text))
                  AND (CAST(:activo AS uuid) IS NULL OR d.asset_id = CAST(:activo AS uuid))
                  AND (NOT :vigentes OR NOT EXISTS (
                        SELECT 1 FROM document s2
                        WHERE s2.supersedes_document_id = d.id AND s2.deleted_at IS NULL))
                ORDER BY d.uploaded_at DESC
                """
            ),
            {
                "p": str(project_id),
                "tipo": doc_type,
                "activo": str(asset_id) if asset_id else None,
                "vigentes": solo_vigentes,
            },
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.get("/documents/{document_id}", response_model=Documento)
def obtener(document_id: uuid.UUID, s: SesionDep) -> Any:
    return _leer(s, document_id)


@router.get("/documents/{document_id}/versions", response_model=list[Documento])
def versiones(document_id: uuid.UUID, s: SesionDep) -> Any:
    """`[REC]` La cadena completa, para saber cuál era la vigente en la fecha
    del informe."""
    _leer(s, document_id)
    filas = (
        s.execute(
            text(  # noqa: S608
                f"""
                -- PostgreSQL solo admite UNA referencia recursiva por CTE, así
                -- que la cadena se recorre en dos: hacia atrás (a qué sustituía)
                -- y hacia delante (quién la sustituyó). Unirlas da la cadena
                -- completa desde cualquier eslabón.
                WITH RECURSIVE hacia_atras AS (
                    SELECT id, supersedes_document_id FROM document WHERE id = :i
                    UNION
                    SELECT d.id, d.supersedes_document_id FROM document d
                    JOIN hacia_atras a ON a.supersedes_document_id = d.id
                ),
                hacia_delante AS (
                    SELECT id FROM document WHERE id = :i
                    UNION
                    SELECT d.id FROM document d
                    JOIN hacia_delante f ON d.supersedes_document_id = f.id
                )
                SELECT {_CAMPOS} FROM document
                WHERE id IN (SELECT id FROM hacia_atras UNION SELECT id FROM hacia_delante)
                ORDER BY version_number
                """
            ),
            {"i": str(document_id)},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.patch("/documents/{document_id}", response_model=Documento)
def actualizar(document_id: uuid.UUID, cuerpo: ActualizarDocumento, s: SesionDep) -> Any:
    actual = _leer(s, document_id)
    cambios = cuerpo.model_dump(exclude_unset=True)
    if not cambios:
        return actual
    if "display_name" in cambios:
        cambios["display_name"] = sanear(cambios["display_name"] or "") or actual["display_name"]
    piezas = []
    for campo in cambios:
        if campo == "doc_type":
            piezas.append("doc_type = CAST(:doc_type AS doc_type)")
        elif campo == "confidentiality":
            piezas.append("confidentiality = CAST(:confidentiality AS doc_confidentiality)")
        else:
            piezas.append(f"{campo} = :{campo}")
    s.execute(
        text(f"UPDATE document SET {', '.join(piezas)} WHERE id = :_id"),  # noqa: S608
        {**cambios, "_id": str(document_id)},
    )
    return _leer(s, document_id)


@router.get("/documents/{document_id}/download")
def descargar(
    document_id: uuid.UUID, s: SesionDep, usuario: UsuarioDep, almacen: AlmacenDep
) -> Any:
    """`[REQ]` Toda descarga queda auditada, y la confidencialidad condiciona
    quién puede hacerla.

    `RESTRINGIDO` solo lo descarga quien administra o dirige: es el nivel que se
    reserva a lo que no debería salir del núcleo del equipo.
    """
    doc = _leer(s, document_id)
    if doc["confidentiality"] == "RESTRINGIDO" and usuario.org_role not in (
        "ADMIN",
        "DIRECTOR_PROYECTO",
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Este documento está marcado como restringido y su perfil no puede descargarlo",
        )
    clave = s.execute(
        text(
            "SELECT o.storage_key FROM stored_object o "
            "JOIN document d ON d.stored_object_id = o.id WHERE d.id = :i"
        ),
        {"i": str(document_id)},
    ).scalar_one()
    datos = almacen.leer(clave)
    _auditar(
        s,
        usuario,
        "DOCUMENT_DOWNLOADED",
        document_id,
        {"bytes": len(datos), "confidentiality": doc["confidentiality"]},
    )
    return Response(
        content=datos,
        media_type=doc["mime_type"],
        headers={
            "Content-Disposition": (
                f'attachment; filename="{doc["display_name"]}.{doc["file_extension"]}"'
            )
        },
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def a_la_papelera(document_id: uuid.UUID, s: SesionDep, usuario: UsuarioDep) -> None:
    """Borrado lógico, igual que en las fotografías."""
    doc = _leer(s, document_id)
    if doc["status"] == "PAPELERA":
        raise HTTPException(status.HTTP_409_CONFLICT, "El documento ya está en la papelera")
    s.execute(
        text("UPDATE document SET status = 'PAPELERA', deleted_at = now() WHERE id = :i"),
        {"i": str(document_id)},
    )
    _auditar(s, usuario, "DOCUMENT_TRASHED", document_id, {})

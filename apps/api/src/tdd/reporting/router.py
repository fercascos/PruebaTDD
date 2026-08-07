"""API del bloque 4 · plantillas, mapeo, avisos y generación.

El flujo, y por qué está partido en cuatro pasos en vez de un botón:

1. **Registrar y analizar la plantilla.** Sin saber qué marcadores tiene, el
   mapeo sería adivinar.
2. **Mapear.** Qué dato alimenta cada marcador. Se guarda y se reutiliza.
3. **Previsualizar los avisos.** Antes de generar nada. Es donde se ve que
   quedan doce precios sin validar.
4. **Generar.** Congela el snapshot y produce el PPTX y el XLSX.

`[REQ]` §17.6 · **Un informe emitido es inmutable.** No se puede reaprobar, ni
regenerar encima, ni borrar: lo que se hace es generar una versión nueva que lo
sustituye. Lo garantiza un disparador, no una comprobación en este fichero.
"""

from __future__ import annotations

import contextlib
import json
import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.core.deps import SesionDep, UsuarioActual, UsuarioDep
from tdd.evidence import anotaciones, guardia, images
from tdd.evidence.router import AlmacenDep, AntivirusDep
from tdd.reporting import generator
from tdd.reporting import snapshot as snap
from tdd.reporting.warnings import (
    Aviso,
    EstadoDelInforme,
    evaluar,
    motivos_de_bloqueo,
    puede_generarse,
    resumir,
)

router = APIRouter(tags=["Informes"])

#: `[SUP]` Una plantilla real del cliente ronda los 15-25 MB.
MAX_BYTES_PLANTILLA = 80 * 1024 * 1024

#: `[REQ]` §17.8 · Un PPTX es un ZIP: se acota lo que puede descomprimirse para
#: que una «bomba» no agote la memoria del servidor.
MAX_DESCOMPRIMIDO_BYTES = 200 * 1024 * 1024


# ─────────────────────────────────────────────────────────────────────────────
#  Plantillas
# ─────────────────────────────────────────────────────────────────────────────


class Plantilla(BaseModel):
    id: uuid.UUID
    name: str
    language: str
    sha256: str
    slide_count: int | None
    analysis: dict[str, Any] | None
    is_active: bool


def _plantilla(s: Session, template_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(
            text(
                "SELECT id, name, language, sha256, slide_count, analysis, is_active, "
                "stored_object_id FROM report_template WHERE id = :i"
            ),
            {"i": str(template_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plantilla no encontrada")
    return dict(fila)


def _comprobar_zip(datos: bytes) -> None:
    """`[REQ]` §17.8 · Un PPTX es un ZIP con XML: dos vectores clásicos."""
    import zipfile

    try:
        with zipfile.ZipFile(io_bytes(datos)) as z:
            total = sum(info.file_size for info in z.infolist())
    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "El fichero no es un PPTX válido"
        ) from exc
    if total > MAX_DESCOMPRIMIDO_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "La plantilla se descomprime a un tamaño desproporcionado y se rechaza",
        )


def io_bytes(datos: bytes) -> Any:
    import io

    return io.BytesIO(datos)


@router.post("/report-templates", status_code=status.HTTP_201_CREATED, response_model=Plantilla)
def registrar_plantilla(
    s: SesionDep,
    usuario: UsuarioDep,
    almacen: AlmacenDep,
    av: AntivirusDep,
    archivo: Annotated[UploadFile, File(alias="file")],
    name: Annotated[str, Form()],
    language: Annotated[str, Form()] = "es",
) -> Any:
    """Sube la plantilla y **la analiza en el acto**.

    Analizar al registrar y no al generar es deliberado: si la plantilla tiene
    problemas, se descubren ahora y no cuando alguien espera un informe.
    """
    datos = archivo.file.read()
    if len(datos) > MAX_BYTES_PLANTILLA:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La plantilla supera el tamaño máximo"
        )
    # `[REQ]` §18.5 · Se analiza **antes** de `_comprobar_zip`, no después.
    # Una plantilla es un ZIP con XML dentro que llega de fuera, y comprobarla
    # significa abrirla: el analizador de ZIP es él mismo superficie de ataque
    # (bombas de descompresión, rutas con `..`). Lo que viene de fuera se
    # analiza antes de interpretarlo, no después.
    guardia.rechazar_si_infectado(
        av,
        datos,
        s=s,
        organization_id=usuario.organization_id,
        actor_id=usuario.id,
        nombre=archivo.filename or "",
        entidad="report_template",
    )
    _comprobar_zip(datos)
    try:
        analisis = generator.analizar(datos)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"No se ha podido leer la plantilla: {exc}"
        ) from exc

    template_id = uuid.uuid4()
    sha = images.sha256_de(datos)
    clave = f"{usuario.organization_id}/templates/{template_id}.pptx"
    almacen.guardar(clave, datos)
    objeto = s.execute(
        text(
            "INSERT INTO stored_object (organization_id, kind, storage_key, sha256, byte_size, "
            "mime_type, is_original) VALUES (:o, 'TEMPLATE', :k, :h, :b, :m, TRUE) RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "k": clave,
            "h": sha,
            "b": len(datos),
            "m": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        },
    ).scalar_one()

    s.execute(
        text(
            "INSERT INTO report_template (id, organization_id, name, language, stored_object_id, "
            "sha256, slide_count, analysis, analyzed_at, created_by) "
            "VALUES (:id, :o, :n, :l, :obj, :h, :sc, CAST(:a AS jsonb), now(), :u)"
        ),
        {
            "id": str(template_id),
            "o": str(usuario.organization_id),
            "n": name,
            "l": language,
            "obj": str(objeto),
            "h": sha,
            "sc": analisis["slide_count"],
            "a": json.dumps(analisis, ensure_ascii=False),
            "u": str(usuario.id),
        },
    )
    return _plantilla(s, template_id)


@router.get("/report-templates", response_model=list[Plantilla])
def listar_plantillas(s: SesionDep) -> Any:
    filas = (
        s.execute(
            text(
                "SELECT id, name, language, sha256, slide_count, analysis, is_active "
                "FROM report_template WHERE is_active ORDER BY name, language"
            )
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.get("/report-templates/{template_id}", response_model=Plantilla)
def obtener_plantilla(template_id: uuid.UUID, s: SesionDep) -> Any:
    return _plantilla(s, template_id)


# ─────────────────────────────────────────────────────────────────────────────
#  Mapeo
# ─────────────────────────────────────────────────────────────────────────────

#: Campos que el generador sabe rellenar. Se valida el mapeo contra esta lista
#: **al guardarlo**: descubrir en la generación que una expresión no existe es
#: tarde, y §17.7 lo declara bloqueante justo por eso.
CAMPOS_DISPONIBLES = frozenset(
    {
        "project.code",
        "project.name",
        "project.client",
        "project.currency",
        "project.asset_count",
        "report.generated_at",
        "capex.total",
        "capex.corto",
        "capex.medio",
        "capex.largo",
        "capex.mejoras",
        "capex.otro",
        "asset.name",
        "asset.city",
        "asset.year_built",
        "asset.total_built_sqm",
    }
)


class Mapeo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    #: {marcador de la plantilla: campo del snapshot}
    bindings: dict[str, str]
    photo_rules: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class MapeoLeido(BaseModel):
    id: uuid.UUID
    template_id: uuid.UUID
    name: str
    bindings: dict[str, str]
    photo_rules: dict[str, Any]
    is_default: bool


@router.post(
    "/report-templates/{template_id}/mappings",
    status_code=status.HTTP_201_CREATED,
    response_model=MapeoLeido,
)
def crear_mapeo(template_id: uuid.UUID, cuerpo: Mapeo, s: SesionDep, usuario: UsuarioDep) -> Any:
    """Valida las expresiones **antes de guardar**."""
    plantilla = _plantilla(s, template_id)
    desconocidos = sorted(set(cuerpo.bindings.values()) - CAMPOS_DISPONIBLES)
    if desconocidos:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Estas expresiones no corresponden a ningún campo: {', '.join(desconocidos)}. "
            f"Disponibles: {', '.join(sorted(CAMPOS_DISPONIBLES))}",
        )
    marcadores = set((plantilla["analysis"] or {}).get("placeholders", []))
    sobrantes = sorted(set(cuerpo.bindings) - marcadores)
    if sobrantes and marcadores:
        # Se avisa pero no se bloquea: la plantilla puede cambiar y un mapeo
        # con una entrada de más no rompe nada.
        pass

    if cuerpo.is_default:
        s.execute(
            text("UPDATE template_mapping SET is_default = FALSE WHERE template_id = :t"),
            {"t": str(template_id)},
        )
    nuevo = s.execute(
        text(
            "INSERT INTO template_mapping (organization_id, template_id, name, bindings, "
            "photo_rules, is_default) "
            "VALUES (:o, :t, :n, CAST(:b AS jsonb), CAST(:p AS jsonb), :d) "
            "ON CONFLICT (template_id, name) DO UPDATE SET bindings = EXCLUDED.bindings, "
            "  photo_rules = EXCLUDED.photo_rules, is_default = EXCLUDED.is_default, "
            "  version = template_mapping.version + 1 "
            "RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "t": str(template_id),
            "n": cuerpo.name,
            "b": json.dumps(cuerpo.bindings, ensure_ascii=False),
            "p": json.dumps(cuerpo.photo_rules, ensure_ascii=False),
            "d": cuerpo.is_default,
        },
    ).scalar_one()
    return dict(
        s.execute(
            text(
                "SELECT id, template_id, name, bindings, photo_rules, is_default "
                "FROM template_mapping WHERE id = :i"
            ),
            {"i": str(nuevo)},
        )
        .mappings()
        .one()
    )


@router.get("/report-templates/{template_id}/mappings", response_model=list[MapeoLeido])
def listar_mapeos(template_id: uuid.UUID, s: SesionDep) -> Any:
    _plantilla(s, template_id)
    filas = (
        s.execute(
            text(
                "SELECT id, template_id, name, bindings, photo_rules, is_default "
                "FROM template_mapping WHERE template_id = :t ORDER BY is_default DESC, name"
            ),
            {"t": str(template_id)},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


# ─────────────────────────────────────────────────────────────────────────────
#  Avisos previos
# ─────────────────────────────────────────────────────────────────────────────


def _reunir_estado(
    s: Session, project_id: uuid.UUID, plantilla: dict[str, Any], bindings: dict[str, str]
) -> EstadoDelInforme:
    """Lee de la base todo lo que §17.7 necesita para decidir."""
    analisis = plantilla["analysis"] or {}
    marcadores = set(analisis.get("placeholders", []))
    sin_mapear = tuple(sorted(marcadores - set(bindings)))
    invalidas = tuple(sorted(set(bindings.values()) - CAMPOS_DISPONIBLES))

    fotos = (
        s.execute(
            text(
                "SELECT id, CAST(status AS text) AS status, asset_id, caption "
                "FROM photo WHERE project_id = :p AND deleted_at IS NULL AND include_in_report"
            ),
            {"p": str(project_id)},
        )
        .mappings()
        .all()
    )
    con_fotos = {f["asset_id"] for f in fotos if f["asset_id"]}
    activos = (
        s.execute(
            text("SELECT id FROM asset WHERE project_id = :p AND deleted_at IS NULL"),
            {"p": str(project_id)},
        )
        .scalars()
        .all()
    )

    precios = s.execute(
        text(
            "SELECT count(*) AS lineas, COALESCE(sum(ci.amount), 0) AS importe "
            "FROM capex_item ci JOIN finding f ON f.id = ci.finding_id "
            "WHERE ci.project_id = :p AND f.deleted_at IS NULL "
            "  AND f.status IN ('EN_REVISION', 'VALIDADO') "
            "  AND ci.price_status <> 'VALIDADO' AND ci.amount > 0"
        ),
        {"p": str(project_id)},
    ).one()

    # [REC] Reclasificar un activo puede dejar hallazgos con una zona que ya no
    # corresponde. Salir en el informe con una zona imposible es peor que parar.
    zonas_rotas = (
        s.execute(
            text(
                "SELECT f.id FROM finding f JOIN asset a ON a.id = f.asset_id "
                "WHERE f.project_id = :p AND f.deleted_at IS NULL "
                "  AND f.status IN ('EN_REVISION', 'VALIDADO') "
                "  AND NOT EXISTS (SELECT 1 FROM zone_typology zt "
                "                  WHERE zt.zone_id = f.zone_id AND zt.typology_id = a.typology_id)"
            ),
            {"p": str(project_id)},
        )
        .scalars()
        .all()
    )

    # Lo que el informe se deja fuera por estado. El snapshot solo publica
    # `EN_REVISION` y `VALIDADO`, así que un encargo entero en borrador genera
    # un documento con la tabla vacía y un total de cero. Contarlo aquí es lo
    # que permite decirlo antes de generar en vez de después de enviarlo.
    borradores = s.execute(
        text(
            "SELECT count(DISTINCT f.id) AS hallazgos, COALESCE(sum(ci.amount), 0) AS importe "
            "FROM finding f LEFT JOIN capex_item ci ON ci.finding_id = f.id "
            "WHERE f.project_id = :p AND f.deleted_at IS NULL "
            "  AND CAST(f.status AS text) = 'BORRADOR'"
        ),
        {"p": str(project_id)},
    ).one()

    pendientes = s.execute(
        text(
            "SELECT count(*) FROM doc_request_item d "
            "JOIN project_phase ph ON ph.id = d.project_phase_id "
            "WHERE ph.project_id = :p AND d.status = 'SOLICITADA'"
        ),
        {"p": str(project_id)},
    ).scalar_one()

    from tdd.reporting.fonts import comprobar_familias

    ausentes = tuple(f for f, ok in comprobar_familias().items() if not ok)

    return EstadoDelInforme(
        marcadores_sin_mapear=sin_mapear,
        expresiones_invalidas=invalidas,
        plantilla_analizada=bool(analisis),
        fotos_no_utilizables=tuple(
            f["id"] for f in fotos if f["status"] in ("CUARENTENA", "ERROR")
        ),
        fotos_sin_activo=tuple(f["id"] for f in fotos if f["asset_id"] is None),
        fotos_sin_pie=tuple(f["id"] for f in fotos if not (f["caption"] or "").strip()),
        activos_sin_fotos=tuple(a for a in activos if a not in con_fotos),
        lineas_con_precio_sin_validar=precios.lineas,
        importe_sin_validar=Decimal(precios.importe),
        lineas_con_zona_a_revisar=tuple(zonas_rotas),
        fuentes_ausentes=ausentes,
        solicitudes_pendientes=pendientes,
        hallazgos_en_borrador=borradores.hallazgos,
        importe_en_borrador=Decimal(borradores.importe),
    )


def _a_json(avisos: list[Aviso]) -> list[dict[str, Any]]:
    return [
        {
            "codigo": a.codigo,
            "severidad": a.severidad.value,
            "mensaje": a.mensaje,
            "entidad": a.entidad,
            "entidad_id": str(a.entidad_id) if a.entidad_id else None,
            "bloquea": a.bloquea,
        }
        for a in avisos
    ]


class PeticionDeInforme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: uuid.UUID
    mapping_id: uuid.UUID | None = None
    #: Insertar las fotografías marcadas para el informe. Se puede desactivar
    #: para producir un borrador rápido de solo texto y tabla.
    incluir_fotos: bool = True


@router.post("/projects/{project_id}/reports/preflight")
def previsualizar(project_id: uuid.UUID, cuerpo: PeticionDeInforme, s: SesionDep) -> Any:
    """`[REQ]` §17.7 · Los avisos **antes** de generar nada.

    Es donde se ve que quedan doce precios sin validar, y el sitio donde eso
    todavía se puede arreglar sin haber mandado nada al cliente.
    """
    _proyecto(s, project_id)
    plantilla = _plantilla(s, cuerpo.template_id)
    bindings = _bindings(s, cuerpo)
    avisos = evaluar(_reunir_estado(s, project_id, plantilla, bindings))
    resumen = resumir(avisos)
    return {
        "can_generate": puede_generarse(avisos),
        "blockers": motivos_de_bloqueo(avisos),
        "summary": {
            "total": resumen.total,
            "blocking": resumen.bloqueantes,
            "by_severity": resumen.por_severidad,
        },
        "warnings": _a_json(avisos),
    }


def _proyecto(s: Session, project_id: uuid.UUID) -> None:
    if (
        s.execute(
            text("SELECT 1 FROM project WHERE id = :p AND deleted_at IS NULL"),
            {"p": str(project_id)},
        ).first()
        is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proyecto no encontrado")


def _bindings(s: Session, cuerpo: PeticionDeInforme) -> dict[str, str]:
    if cuerpo.mapping_id is None:
        fila = s.execute(
            text(
                "SELECT bindings FROM template_mapping WHERE template_id = :t "
                "ORDER BY is_default DESC LIMIT 1"
            ),
            {"t": str(cuerpo.template_id)},
        ).scalar()
    else:
        fila = s.execute(
            text("SELECT bindings FROM template_mapping WHERE id = :i"),
            {"i": str(cuerpo.mapping_id)},
        ).scalar()
    return dict(fila or {})


# ─────────────────────────────────────────────────────────────────────────────
#  Generación
# ─────────────────────────────────────────────────────────────────────────────


class VersionDeInforme(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    version_number: int
    status: str
    template_id: uuid.UUID
    pptx_sha256: str | None
    data_snapshot_sha256: str
    warnings: list[dict[str, Any]]
    is_locked: bool
    supersedes_version_id: uuid.UUID | None
    generated_by: uuid.UUID


_VERSION = """
    SELECT id, project_id, version_number, CAST(status AS text) AS status, template_id,
           pptx_sha256, data_snapshot_sha256, warnings, is_locked, supersedes_version_id,
           generated_by
    FROM report_version
"""


def _version(s: Session, version_id: uuid.UUID) -> dict[str, Any]:
    fila = (
        s.execute(text(f"{_VERSION} WHERE id = :i"), {"i": str(version_id)}).mappings().first()  # noqa: S608
    )
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Versión de informe no encontrada")
    return dict(fila)


@router.post(
    "/projects/{project_id}/reports",
    status_code=status.HTTP_201_CREATED,
    response_model=VersionDeInforme,
)
def generar(
    project_id: uuid.UUID,
    cuerpo: PeticionDeInforme,
    s: SesionDep,
    usuario: UsuarioDep,
    almacen: AlmacenDep,
) -> Any:
    """Congela el snapshot y produce el PPTX y el XLSX.

    **Se niega si hay avisos bloqueantes.** Es el único momento en que la
    aplicación impide seguir, y lo hace porque el resultado sería un documento
    incorrecto —marcadores literales, fotos no verificadas— que iría al cliente.
    """
    _proyecto(s, project_id)
    plantilla = _plantilla(s, cuerpo.template_id)
    bindings = _bindings(s, cuerpo)

    avisos = evaluar(_reunir_estado(s, project_id, plantilla, bindings))
    if not puede_generarse(avisos):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "No se puede generar el informe: " + "; ".join(motivos_de_bloqueo(avisos)),
        )

    # [REQ] §17.6 · El snapshot ES la versión de los datos del informe. Todo lo
    # que viene después lee de aquí, no de la base.
    congelado = snap.construir(s, project_id)
    huella_snapshot = snap.huella(congelado)

    clave_plantilla = s.execute(
        text("SELECT storage_key FROM stored_object WHERE id = :i"),
        {"i": str(plantilla["stored_object_id"])},
    ).scalar_one()
    bytes_plantilla = almacen.leer(clave_plantilla)

    fotos: list[generator.FotoParaInsertar] = []
    if cuerpo.incluir_fotos:
        for foto in congelado.get("photos", []):
            clave = s.execute(
                text(
                    "SELECT o.storage_key FROM photo p "
                    "JOIN stored_object o ON o.id = p.stored_object_id WHERE p.id = :i"
                ),
                {"i": str(foto["id"])},
            ).scalar()
            if clave is None:
                continue
            try:
                # [REQ] §15.6 · Lo que entra en el PPTX son solo píxeles: el
                # derivado va sin EXIF y con la orientación ya aplicada.
                datos = images.generar_derivado(
                    almacen.leer(clave), lado_maximo=1600, sin_metadatos=True
                )
            except Exception:  # noqa: BLE001 — una foto ilegible no tumba el informe
                continue

            # `[REQ]` §15.2 · Las anotaciones se **queman aquí**, sobre el
            # derivado desechable. Es el único momento en que dejan de ser
            # vectores: el original sigue limpio y la capa se puede volver a
            # editar. Antes se guardaban y no las pintaba nadie, así que anotar
            # una foto producía un JSON que no llegaba al informe.
            capa_bruta = foto.get("annotations")
            if capa_bruta:
                # La capa se valida al guardarla. Si aun así llega algo raro —un
                # snapshot anterior a que existiera esa validación—, se inserta
                # la foto limpia: mejor sin flechas que sin foto.
                with contextlib.suppress(anotaciones.AnotacionInvalida):
                    datos = anotaciones.rasterizar(datos, anotaciones.leer(capa_bruta))

            fotos.append(
                generator.FotoParaInsertar(
                    photo_id=str(foto["id"]), datos=datos, caption=str(foto.get("caption") or "")
                )
            )

    resultado = generator.generar(bytes_plantilla, congelado, fotos=fotos)

    anterior = s.execute(
        text(
            "SELECT id FROM report_version WHERE project_id = :p "
            "ORDER BY version_number DESC LIMIT 1"
        ),
        {"p": str(project_id)},
    ).scalar()

    version_id = uuid.uuid4()
    objeto_pptx = _guardar(
        s,
        almacen,
        usuario,
        project_id,
        f"reports/{version_id}.pptx",
        resultado.pptx,
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    objeto_xlsx = _guardar(
        s,
        almacen,
        usuario,
        project_id,
        f"reports/{version_id}.xlsx",
        resultado.xlsx,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    s.execute(
        text(
            "INSERT INTO report_version (id, organization_id, project_id, version_number, status, "
            "template_id, template_sha256, mapping_id, data_snapshot, data_snapshot_sha256, "
            "stored_object_id, pptx_sha256, xlsx_object_id, warnings, supersedes_version_id, "
            "generated_by) "
            "SELECT :id, :o, :p, COALESCE(MAX(version_number), 0) + 1, 'GENERADO', :t, :th, :m, "
            "  CAST(:snap AS jsonb), :sh, :obj, :hash, :xlsx, CAST(:w AS jsonb), :sup, :u "
            "FROM report_version WHERE project_id = :p"
        ),
        {
            "id": str(version_id),
            "o": str(usuario.organization_id),
            "p": str(project_id),
            "t": str(cuerpo.template_id),
            "th": plantilla["sha256"],
            "m": str(cuerpo.mapping_id) if cuerpo.mapping_id else None,
            "snap": json.dumps(congelado, ensure_ascii=False),
            "sh": huella_snapshot,
            "obj": str(objeto_pptx),
            "hash": images.sha256_de(resultado.pptx),
            "xlsx": str(objeto_xlsx),
            "w": json.dumps(_a_json(avisos), ensure_ascii=False),
            "sup": str(anterior) if anterior else None,
            "u": str(usuario.id),
        },
    )
    _auditar(s, usuario, "REPORT_GENERATED", version_id, {"snapshot": huella_snapshot})
    return _version(s, version_id)


def _guardar(
    s: Session,
    almacen: Any,
    usuario: UsuarioActual,
    project_id: uuid.UUID,
    sufijo: str,
    datos: bytes,
    mime: str,
) -> uuid.UUID:
    clave = f"{usuario.organization_id}/{project_id}/{sufijo}"
    almacen.guardar(clave, datos)
    return s.execute(  # type: ignore[return-value]
        text(
            "INSERT INTO stored_object (organization_id, project_id, kind, storage_key, sha256, "
            "byte_size, mime_type, is_original) "
            "VALUES (:o, :p, 'REPORT', :k, :h, :b, :m, FALSE) RETURNING id"
        ),
        {
            "o": str(usuario.organization_id),
            "p": str(project_id),
            "k": clave,
            "h": images.sha256_de(datos),
            "b": len(datos),
            "m": mime,
        },
    ).scalar_one()


def _auditar(
    s: Session, usuario: UsuarioActual, accion: str, version_id: uuid.UUID, detalle: dict[str, Any]
) -> None:
    s.execute(
        text(
            "INSERT INTO audit_log (organization_id, actor_user_id, action, entity_type, "
            "entity_id, after_data) VALUES (:o, :u, :a, 'report_version', :e, CAST(:p AS jsonb))"
        ),
        {
            "o": str(usuario.organization_id),
            "u": str(usuario.id),
            "a": accion,
            "e": str(version_id),
            "p": json.dumps(detalle, ensure_ascii=False, default=str),
        },
    )


@router.get("/projects/{project_id}/reports", response_model=list[VersionDeInforme])
def listar_versiones(project_id: uuid.UUID, s: SesionDep) -> Any:
    _proyecto(s, project_id)
    filas = (
        s.execute(
            text(f"{_VERSION} WHERE project_id = :p ORDER BY version_number DESC"),  # noqa: S608
            {"p": str(project_id)},
        )
        .mappings()
        .all()
    )
    return [dict(f) for f in filas]


@router.get("/reports/{version_id}", response_model=VersionDeInforme)
def obtener_version(version_id: uuid.UUID, s: SesionDep) -> Any:
    return _version(s, version_id)


@router.get("/reports/{version_id}/download")
def descargar(
    version_id: uuid.UUID,
    s: SesionDep,
    usuario: UsuarioDep,
    almacen: AlmacenDep,
    formato: str = "pptx",
) -> Any:
    """Descarga el informe **exactamente como se generó**.

    De un informe emitido esto sigue devolviendo el mismo fichero años después:
    es lo que hace verificable el `pptx_sha256` que se guardó al generarlo.
    """
    version = _version(s, version_id)
    columna = "stored_object_id" if formato == "pptx" else "xlsx_object_id"
    clave = s.execute(
        text(  # noqa: S608 — `columna` sale de un literal, no del usuario
            f"SELECT o.storage_key FROM stored_object o "
            f"JOIN report_version r ON r.{columna} = o.id WHERE r.id = :i"
        ),
        {"i": str(version_id)},
    ).scalar()
    if clave is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Esta versión no tiene fichero {formato}")

    datos = almacen.leer(clave)
    _auditar(s, usuario, "REPORT_DOWNLOADED", version_id, {"formato": formato})
    extension = "pptx" if formato == "pptx" else "xlsx"
    mime = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if formato == "pptx"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return Response(
        content=datos,
        media_type=mime,
        headers={
            "Content-Disposition": (
                f'attachment; filename="informe-v{version["version_number"]}.{extension}"'
            )
        },
    )


class CambioDeEstadoDeInforme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: str


#: El ciclo de vida del informe. De `EMITIDO` no se sale: lo que se hace es
#: generar una versión nueva que lo sustituye.
_TRANSICIONES = {
    "GENERADO": {"EN_REVISION"},
    "EN_REVISION": {"APROBADO", "GENERADO"},
    "APROBADO": {"EMITIDO", "EN_REVISION"},
    "EMITIDO": set(),
    "ERROR": set(),
    "GENERANDO": {"GENERADO", "ERROR"},
}


@router.post("/reports/{version_id}/transitions", response_model=VersionDeInforme)
def cambiar_estado(
    version_id: uuid.UUID, cuerpo: CambioDeEstadoDeInforme, s: SesionDep, usuario: UsuarioDep
) -> Any:
    """`[REQ]` §17.6 · Emitir **bloquea el informe para siempre**.

    Aprobar y emitir exigen persona identificada. El bloqueo lo garantiza un
    disparador en la base de datos: aunque alguien escriba un `UPDATE` nuevo
    dentro de seis meses, el informe emitido sigue siendo el que se entregó.
    """
    version = _version(s, version_id)
    if version["is_locked"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "El informe está emitido y es inmutable. Genere una versión nueva.",
        )
    destinos = _TRANSICIONES.get(version["status"], set())
    if cuerpo.to not in destinos:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Un informe en «{version['status']}» no puede pasar a «{cuerpo.to}». "
            f"Destinos posibles: {', '.join(sorted(destinos)) or 'ninguno'}",
        )
    if cuerpo.to in ("APROBADO", "EMITIDO") and usuario.org_role not in (
        "ADMIN",
        "DIRECTOR_PROYECTO",
        "REVISOR",
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Aprobar o emitir un informe exige perfil de revisor, director o administrador",
        )

    piezas = ["status = CAST(:e AS report_status)"]
    if cuerpo.to == "APROBADO":
        piezas += ["approved_by = :u", "approved_at = now()"]
    if cuerpo.to == "EMITIDO":
        # `is_locked` y `EMITIDO` van juntos por `CHECK`: el disparador impide
        # cualquier cambio posterior a partir de este mismo UPDATE.
        piezas += [
            "issued_by = :u",
            "issued_at = now()",
            "is_locked = TRUE",
            "approved_by = COALESCE(approved_by, :u)",
            "approved_at = COALESCE(approved_at, now())",
        ]
    s.execute(
        text(f"UPDATE report_version SET {', '.join(piezas)} WHERE id = :i"),  # noqa: S608
        {"e": cuerpo.to, "u": str(usuario.id), "i": str(version_id)},
    )
    _auditar(
        s,
        usuario,
        f"REPORT_{cuerpo.to}",
        version_id,
        {"desde": version["status"], "hasta": cuerpo.to},
    )
    return _version(s, version_id)


@router.get("/reports/{version_id}/diff/{otra_id}")
def comparar_versiones(version_id: uuid.UUID, otra_id: uuid.UUID, s: SesionDep) -> Any:
    """`[REQ]` §17.6 · Qué cambió entre dos versiones.

    Lo que de verdad se mira: qué hallazgos entraron o salieron y **cuánto se
    movió el CAPEX en cada plazo**.
    """
    snapshots = {}
    for identificador in (version_id, otra_id):
        fila = s.execute(
            text("SELECT data_snapshot FROM report_version WHERE id = :i"),
            {"i": str(identificador)},
        ).scalar()
        if fila is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Versión {identificador} no encontrada")
        snapshots[identificador] = fila
    return snap.comparar(snapshots[version_id], snapshots[otra_id])

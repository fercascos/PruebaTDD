"""Producir los ficheros de una versión de informe ya congelada.

Esto es **lo que tarda**: preparar las fotos, clonar diapositivas y escribir el
PPTX y el XLSX. Vive aparte del router por una razón concreta: lo llama el
worker, y el worker no debe importar el router.

`[REQ]` §17.6 · Se lee **del snapshot guardado en la fila**, no de la base viva.
Entre que alguien pulsa «Generar» y el worker coge la tarea pueden pasar
segundos o minutos; si leyera la base, el informe reflejaría datos posteriores a
la petición y dejaría de corresponder a la versión congelada.
"""

from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tdd.evidence import anotaciones, images
from tdd.reporting import generator

PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class VersionInexistente(LookupError):
    """La fila desapareció entre encolar la tarea y cogerla."""


@dataclass(frozen=True, slots=True)
class Producido:
    pptx_object_id: uuid.UUID
    xlsx_object_id: uuid.UUID
    pptx_sha256: str


def guardar_objeto(
    s: Session,
    almacen: Any,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    sufijo: str,
    datos: bytes,
    mime: str,
) -> uuid.UUID:
    clave = f"{organization_id}/{project_id}/{sufijo}"
    almacen.guardar(clave, datos)
    return uuid.UUID(
        str(
            s.execute(
                text(
                    "INSERT INTO stored_object (organization_id, project_id, kind, storage_key, "
                    "sha256, byte_size, mime_type, is_original) "
                    "VALUES (:o, :p, 'REPORT', :k, :h, :b, :m, FALSE) RETURNING id"
                ),
                {
                    "o": str(organization_id),
                    "p": str(project_id),
                    "k": clave,
                    "h": images.sha256_de(datos),
                    "b": len(datos),
                    "m": mime,
                },
            ).scalar_one()
        )
    )


def fotos_del_snapshot(
    s: Session, almacen: Any, congelado: dict[str, Any]
) -> list[generator.FotoParaInsertar]:
    """Los derivados que van al PPTX, con las anotaciones ya quemadas.

    `[REQ]` §15.6 · Lo que entra son solo píxeles: sin EXIF y con la orientación
    ya aplicada. `[REQ]` §15.2 · Las anotaciones se queman **aquí**, sobre el
    derivado desechable: el original sigue limpio y la capa se puede reeditar.
    """
    salida: list[generator.FotoParaInsertar] = []
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
            datos = images.generar_derivado(
                almacen.leer(clave), lado_maximo=1600, sin_metadatos=True
            )
        except Exception:  # noqa: BLE001 — una foto ilegible no tumba el informe
            continue

        capa = foto.get("annotations")
        if capa:
            # La capa se valida al guardarla. Si aun así llega algo raro —un
            # snapshot anterior a esa validación—, entra la foto limpia: mejor
            # sin flechas que sin foto.
            with contextlib.suppress(anotaciones.AnotacionInvalida):
                datos = anotaciones.rasterizar(datos, anotaciones.leer(capa))

        salida.append(
            generator.FotoParaInsertar(
                photo_id=str(foto["id"]), datos=datos, caption=str(foto.get("caption") or "")
            )
        )
    return salida


def producir(s: Session, almacen: Any, version_id: uuid.UUID, *, incluir_fotos: bool) -> Producido:
    """Genera los ficheros de una versión y los deja guardados.

    **No cambia el estado de la versión.** Eso lo hace quien llama, que es el
    único que sabe si hubo fallo: separarlo permite que un error deje la fila en
    `ERROR` en una transacción distinta de la que reventó.
    """
    fila = (
        s.execute(
            text(
                "SELECT rv.organization_id, rv.project_id, rv.data_snapshot, "
                "       o.storage_key AS clave_plantilla "
                "FROM report_version rv "
                "JOIN report_template t ON t.id = rv.template_id "
                "JOIN stored_object o ON o.id = t.stored_object_id "
                "WHERE rv.id = :i"
            ),
            {"i": str(version_id)},
        )
        .mappings()
        .first()
    )
    if fila is None:
        raise VersionInexistente(f"La versión {version_id} ya no existe")

    congelado = dict(fila["data_snapshot"])
    fotos = fotos_del_snapshot(s, almacen, congelado) if incluir_fotos else []
    resultado = generator.generar(almacen.leer(fila["clave_plantilla"]), congelado, fotos=fotos)

    comun = {
        "organization_id": uuid.UUID(str(fila["organization_id"])),
        "project_id": uuid.UUID(str(fila["project_id"])),
    }
    return Producido(
        pptx_object_id=guardar_objeto(
            s,
            almacen,
            **comun,
            sufijo=f"reports/{version_id}.pptx",
            datos=resultado.pptx,
            mime=PPTX,
        ),
        xlsx_object_id=guardar_objeto(
            s,
            almacen,
            **comun,
            sufijo=f"reports/{version_id}.xlsx",
            datos=resultado.xlsx,
            mime=XLSX,
        ),
        pptx_sha256=images.sha256_de(resultado.pptx),
    )


def marcar_generado(s: Session, version_id: uuid.UUID, producido: Producido) -> None:
    s.execute(
        text(
            "UPDATE report_version SET status = 'GENERADO', stored_object_id = :obj, "
            "pptx_sha256 = :hash, xlsx_object_id = :xlsx WHERE id = :i"
        ),
        {
            "obj": str(producido.pptx_object_id),
            "hash": producido.pptx_sha256,
            "xlsx": str(producido.xlsx_object_id),
            "i": str(version_id),
        },
    )


def marcar_error(s: Session, version_id: uuid.UUID) -> None:
    """Deja la versión en `ERROR` para que la pantalla deje de esperar.

    `[REQ]` §17 · «`FALLIDA` con mensaje sin datos internos; sin versión a
    medias.» El motivo técnico vive en `job.last_error`, que solo ve quien
    opera; la pantalla dice que falló y ofrece volver a pedirlo.
    """
    s.execute(
        text("UPDATE report_version SET status = 'ERROR' WHERE id = :i"), {"i": str(version_id)}
    )

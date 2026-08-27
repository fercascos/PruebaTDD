"""Choques con una restricción de unicidad, traducidos a algo que se entienda.

`[REQ]` §13 · Repetir el código de un encargo es un error **del usuario**, no
del servidor. Sin esto salía un `500` genérico: la pantalla decía «error
interno», el usuario volvía a pulsar, y el código que ya estaba cogido no se
mencionaba por ningún lado. Se descubrió dando de alta dos veces el encargo
«2026-014» con la aplicación en marcha.

Vive en **un solo sitio** a propósito. La alternativa —una consulta previa en
cada endpoint— tiene dos problemas: hay que acordarse en cada uno, y entre la
consulta y el `INSERT` cabe otra petición, así que la comprobación previa no
elimina la carrera. Aquí se traduce el fallo que la base de datos ya garantiza.

`[REQ]` El mensaje **no incluye el SQL ni el nombre de la tabla**: solo el
campo en lenguaje llano. Lo técnico queda en el registro.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

#: Restricción → qué decirle a quien está rellenando el formulario.
#: La clave es el nombre que PostgreSQL le da al índice único.
MENSAJES: dict[str, str] = {
    "project_organization_id_internal_code_key": (
        "Ya existe un encargo con ese código interno. Use otro."
    ),
    "app_user_organization_id_email_key": "Ya existe una cuenta con ese correo.",
    "asset_codigo_uniq": "Ya hay un activo con ese código del cliente en el encargo.",
    "client_organization_id_name_key": "Ya existe un cliente con ese nombre.",
    "project_phase_project_id_phase_definition_id_key": (
        "Esa fase ya está activada en el encargo."
    ),
    "report_template_organization_id_name_language_key": (
        "Ya existe una plantilla con ese nombre en ese idioma."
    ),
    "template_mapping_template_id_name_key": ("Esa plantilla ya tiene un marcador con ese nombre."),
    "capex_item_finding_id_time_horizon_id_key": (
        # P-05 y P-44: una actuación puede tener varias líneas, pero una sola
        # por horizonte. Repetir horizonte es intentar dos importes para el
        # mismo plazo, que es justo lo que la tabla del informe no admite.
        "Esa actuación ya tiene un importe para ese horizonte temporal. "
        "Edite la línea existente en vez de añadir otra."
    ),
    "qa_question_qa_round_id_number_key": "Ya existe una pregunta con ese número en la ronda.",
    "qa_round_project_phase_id_round_number_key": "Ya existe una ronda con ese número.",
    "photo_link_photo_id_entity_type_entity_id_key": (
        "La fotografía ya está vinculada a ese elemento."
    ),
    "report_version_project_id_version_number_key": "Ya existe una versión con ese número.",
}

GENERICO = "El dato que intenta guardar ya existe y no puede repetirse."


def mensaje_de(exc: IntegrityError) -> str | None:
    """El texto para el usuario, o `None` si no es un choque de unicidad.

    Función pura sobre el error: se puede probar sin levantar la aplicación.
    """
    original = getattr(exc, "orig", None)
    # `psycopg` expone el SQLSTATE en `sqlstate`. 23505 es unique_violation:
    # cualquier otro fallo de integridad (clave ajena, restricción `CHECK`) no
    # es un choque de nombres y no debe convertirse en un 409.
    if getattr(original, "sqlstate", None) != "23505":
        return None
    diagnostico = getattr(original, "diag", None)
    restriccion = getattr(diagnostico, "constraint_name", None) or ""
    return MENSAJES.get(restriccion, GENERICO)


def registrar(app: Any) -> None:
    """Engancha el traductor a la aplicación."""

    # `app` llega como `Any` —para no arrastrar aquí el tipo de FastAPI—, así
    # que su decorador tampoco está anotado. La función de dentro sí lo está,
    # que es lo que se puede comprobar.
    @app.exception_handler(IntegrityError)  # type: ignore[untyped-decorator]
    async def _conflicto(request: Request, exc: IntegrityError) -> JSONResponse:
        texto = mensaje_de(exc)
        if texto is None:
            # No es un choque de unicidad: se deja caer al manejador general,
            # que devuelve un 500 sin filtrar detalles. Convertir en 409 un
            # fallo de clave ajena diría al usuario que reintente con otro
            # nombre cuando el problema es otro.
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "type": "https://api.tdd.example/errors/internal",
                    "title": "Error interno",
                    "status": 500,
                    "instance": str(request.url.path),
                },
            )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "type": "https://api.tdd.example/errors/conflict",
                "title": "Conflicto",
                "status": 409,
                "detail": texto,
                "instance": str(request.url.path),
            },
        )

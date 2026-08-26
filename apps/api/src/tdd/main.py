"""Composición de la aplicación."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from tdd.assets.router import router as assets_router
from tdd.assets.ubicaciones import router as ubicaciones_router
from tdd.capex.router import router as capex_router
from tdd.catalogs.router import router as catalogs_router
from tdd.core.config import get_settings
from tdd.core.conflictos import registrar as registrar_conflictos
from tdd.core.db import crear_fabrica_de_sesiones, crear_motor
from tdd.equipment.router import router as equipment_router
from tdd.evidence import antivirus, storage
from tdd.evidence.documents import router as documents_router
from tdd.evidence.router import router as evidence_router
from tdd.findings.router import router as findings_router
from tdd.identity.directorio import router as directorio_router
from tdd.identity.router import router as identity_router
from tdd.notificaciones import correo
from tdd.phases.operations import router as phase_ops_router
from tdd.phases.router import router as phases_router
from tdd.pricing.router import router as pricing_router
from tdd.projects.router import router as projects_router
from tdd.reporting.router import router as reporting_router
from tdd.reporting.snapshot import ProyectoInexistente
from tdd.revision_documental.router import router as revision_documental_router
from tdd.suggestions.router import router as suggestions_router


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL no está definida. Copie .env.example a .env y rellénela.")
    engine = crear_motor(
        str(settings.database_url),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    app.state.engine = engine
    app.state.session_factory = crear_fabrica_de_sesiones(engine)
    app.state.object_store = storage.construir(settings)
    app.state.correo = correo.construir(
        host=settings.smtp_host,
        puerto=settings.smtp_port,
        remitente=settings.mail_from,
        usuario=settings.smtp_user,
        clave=settings.smtp_password,
    )
    app.state.antivirus = antivirus.construir(
        habilitado=settings.antivirus_enabled,
        host=settings.clamav_host,
        puerto=settings.clamav_port,
        timeout=settings.clamav_timeout_seconds,
    )
    try:
        yield
    finally:
        engine.dispose()


def crear_app() -> FastAPI:
    app = FastAPI(
        title="API de due diligence técnica inmobiliaria",
        version="0.1.0",
        lifespan=ciclo_de_vida,
        description=(
            "Gestión de proyectos de TDD: encargo y fases, evidencia fotográfica, "
            "CAPEX con trazabilidad e informes PPTX."
        ),
    )

    @app.exception_handler(Exception)
    async def _sin_filtrar_detalles(request: Request, exc: Exception) -> JSONResponse:
        """[REQ] Ningún error expone SQL, rutas, trazas ni nombres de bucket.

        El detalle técnico va al log, correlacionado por `X-Request-Id`.
        """
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "type": "https://api.tdd.example/errors/internal",
                "title": "Error interno",
                "status": 500,
                "instance": str(request.url.path),
            },
        )

    # Repetir el código de un encargo es un error del usuario, no del servidor:
    # sin este traductor salía un 500 genérico que no decía qué campo repetir.
    registrar_conflictos(app)

    @app.exception_handler(ProyectoInexistente)
    async def _proyecto_inexistente(request: Request, exc: ProyectoInexistente) -> JSONResponse:
        """Un encargo de otra organización es un 404, no un error interno.

        La RLS lo oculta y la consulta no devuelve nada; sin esto, pedir el
        Excel de un encargo ajeno rompía con un 500 en vez de decir que no
        existe. Vive aquí y no en cada endpoint para que ningún consumidor
        futuro del snapshot tenga que acordarse.
        """
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "type": "https://api.tdd.example/errors/not-found",
                "title": "No encontrado",
                "status": 404,
                "detail": "Proyecto no encontrado",
                "instance": str(request.url.path),
            },
        )

    @app.get("/health", tags=["Operación"])
    def salud() -> dict[str, Any]:
        return {"status": "ok"}

    api = "/api/v1"
    app.include_router(identity_router, prefix=api)
    app.include_router(directorio_router, prefix=api)
    app.include_router(catalogs_router, prefix=api)
    app.include_router(projects_router, prefix=api)
    app.include_router(phases_router, prefix=api)
    app.include_router(phase_ops_router, prefix=api)
    app.include_router(assets_router, prefix=api)
    app.include_router(ubicaciones_router, prefix=api)
    app.include_router(equipment_router, prefix=api)
    app.include_router(findings_router, prefix=api)
    app.include_router(capex_router, prefix=api)
    app.include_router(pricing_router, prefix=api)
    app.include_router(evidence_router, prefix=api)
    app.include_router(documents_router, prefix=api)
    app.include_router(reporting_router, prefix=api)
    app.include_router(revision_documental_router, prefix=api)
    app.include_router(suggestions_router, prefix=api)
    return app


app = crear_app()

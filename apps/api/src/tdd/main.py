"""Composición de la aplicación."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from tdd.assets.router import router as assets_router
from tdd.capex.router import router as capex_router
from tdd.catalogs.router import router as catalogs_router
from tdd.core.config import get_settings
from tdd.core.db import crear_fabrica_de_sesiones, crear_motor
from tdd.evidence.documents import router as documents_router
from tdd.evidence.router import router as evidence_router
from tdd.evidence.storage import AlmacenEnDisco
from tdd.findings.router import router as findings_router
from tdd.identity.router import router as identity_router
from tdd.phases.operations import router as phase_ops_router
from tdd.phases.router import router as phases_router
from tdd.projects.router import router as projects_router
from tdd.reporting.router import router as reporting_router
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
    # [LIM] Almacén sobre disco: el adaptador S3 con Object Lock (barrera 4 de
    # las fotografías) no está implementado ni probado. Ver evidence/storage.py.
    app.state.object_store = AlmacenEnDisco(settings.storage_local_dir)
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

    @app.get("/health", tags=["Operación"])
    def salud() -> dict[str, Any]:
        return {"status": "ok"}

    api = "/api/v1"
    app.include_router(identity_router, prefix=api)
    app.include_router(catalogs_router, prefix=api)
    app.include_router(projects_router, prefix=api)
    app.include_router(phases_router, prefix=api)
    app.include_router(phase_ops_router, prefix=api)
    app.include_router(assets_router, prefix=api)
    app.include_router(findings_router, prefix=api)
    app.include_router(capex_router, prefix=api)
    app.include_router(evidence_router, prefix=api)
    app.include_router(documents_router, prefix=api)
    app.include_router(reporting_router, prefix=api)
    app.include_router(suggestions_router, prefix=api)
    return app


app = crear_app()

"""Composición de la aplicación ESG."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from esg.conector.azure import LectorAzure
from esg.conector.puerto import LectorNoConfigurado
from esg.conector.router import router as conector_router
from esg.core.config import Settings, get_settings
from esg.core.db import crear_fabrica_de_sesiones, crear_motor
from esg.core.errores import NO_PROCESABLE
from esg.core.security import construir_verificador
from esg.estructura.router import router as estructura_router
from esg.identidad.router import router as identidad_router
from esg.indicadores.router import router as indicadores_router
from esg.ingesta.router import router as ingesta_router

log = logging.getLogger("esg")


def construir_lector(settings: Settings) -> Any:
    """El lector de facturas que toque, o el que dice que no está configurado.

    Falta de configuración **no** es fallo de arranque: una instalación sin
    lector tiene que poder cargar ficheros con normalidad. El que pulse
    «importar facturas» recibe un 503 que explica qué falta.
    """
    if settings.lector_facturas_url:
        return LectorAzure(
            url=settings.lector_facturas_url,
            api_key=settings.lector_facturas_api_key,
            timeout=settings.lector_facturas_timeout_seconds,
        )
    return LectorNoConfigurado()


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL no está definida. Copie .env.example a .env.")
    motor = crear_motor(
        str(settings.database_url),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    app.state.engine = motor
    app.state.session_factory = crear_fabrica_de_sesiones(motor)
    app.state.verificador = construir_verificador(settings)
    app.state.lector_de_facturas = construir_lector(settings)
    if settings.auth_mode == "local":
        log.warning("AUTH_MODE=local: los tokens los firma esta aplicación. Solo para desarrollo.")
    try:
        yield
    finally:
        motor.dispose()


def crear_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Dashboard ESG de activos inmobiliarios",
        version="0.1.0",
        lifespan=ciclo_de_vida,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origenes_permitidos,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(identidad_router)
    app.include_router(estructura_router)
    app.include_router(indicadores_router)
    app.include_router(ingesta_router)
    app.include_router(conector_router)

    if settings.auth_mode == "local":
        # Solo se monta con AUTH_MODE=local, que la configuración no deja usar
        # fuera de desarrollo. Un despliegue no puede tener esta ruta ni
        # apagada: no está.
        from esg.identidad.desarrollo import router as desarrollo_router

        app.include_router(desarrollo_router)

    @app.get("/health", include_in_schema=False)
    def salud() -> dict[str, str]:
        return {"estado": "vivo"}

    @app.exception_handler(ValueError)
    async def valor_invalido(request: Request, exc: ValueError) -> JSONResponse:
        """Un `ValueError` del dominio es culpa de quien llama, no del servidor.

        Sin esto, `validar_enumerado` —que es la forma que tiene el dominio de
        decir «ese tipo no existe»— salía como 500, y un 500 se investiga como
        una avería.
        """
        return JSONResponse(
            status_code=NO_PROCESABLE,
            content={"detail": str(exc)},
        )

    return app


app = crear_app()

"""Composición de la aplicación."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import text as sa_text

from tdd.assets.router import router as assets_router
from tdd.assets.ubicaciones import router as ubicaciones_router
from tdd.capex.router import router as capex_router
from tdd.catalogs.router import router as catalogs_router
from tdd.core import metricas, observabilidad
from tdd.core.config import get_settings
from tdd.core.conflictos import registrar as registrar_conflictos
from tdd.core.db import crear_fabrica_de_sesiones, crear_motor
from tdd.equipment.router import router as equipment_router
from tdd.evidence import antivirus, storage
from tdd.evidence.documents import router as documents_router
from tdd.evidence.router import router as evidence_router
from tdd.extraccion.router import router as extraccion_router
from tdd.findings.router import router as findings_router
from tdd.identity.directorio import router as directorio_router
from tdd.identity.router import router as identity_router
from tdd.memoria.router import router as memoria_router
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
    # Lo primero: si algo del arranque falla, que el fallo salga con el formato
    # bueno y no con el que `uvicorn` tenga puesto por omisión.
    observabilidad.configurar(entorno=settings.app_env, nivel=settings.log_level)
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
        ca_fichero=settings.smtp_ca_file,
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
        """`[REQ]` Ningún error expone SQL, rutas, trazas ni nombres de bucket.

        Y el detalle técnico **va al log**, con su traza. Esto lo prometía esta
        misma documentación desde el principio y no ocurría: la excepción se
        descartaba entera, así que un `500` en producción no dejaba nada que
        mirar. Era la peor combinación posible —no decirle nada al usuario y no
        guardar nada para nosotros—, y por eso se registra aquí con
        `exc_info`, que es lo que arrastra la traza completa.

        El identificador se devuelve **al cliente**, en el cuerpo y en la
        cabecera. Es lo que convierte «me ha dado un error» en «me ha dado el
        error 3f2a9c…», que se busca en un panel en un segundo.
        """
        traza = observabilidad.traza_de(request)
        # Se vuelve a poner en el contexto para que el registro de abajo salga
        # con ella: aquí ya se ha restaurado, porque este manejador corre por
        # fuera de nuestro middleware.
        testigo = observabilidad.peticion_actual.set(traza)
        logging.getLogger("tdd.error").exception(
            "Error no controlado en %s %s",
            request.method,
            request.url.path,
            extra={"ruta": str(request.url.path), "metodo": request.method},
        )
        observabilidad.peticion_actual.reset(testigo)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "type": "https://api.tdd.example/errors/internal",
                "title": "Error interno",
                "status": 500,
                "instance": str(request.url.path),
                # Un identificador opaco: no dice nada de dentro y lo dice todo
                # a quien tenga acceso al registro.
                "request_id": traza,
            },
            headers={observabilidad.CABECERA: traza} if traza else None,
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
        """**Vida**: ¿sigue este proceso en pie?

        No mira la base a propósito. Si PostgreSQL se cae, este proceso no está
        roto y reiniciarlo no arregla nada; un orquestador que use esto como
        sonda de vida entraría en un bucle de reinicios que solo empeora la
        situación. Para «¿puede atender?» está `/ready`.
        """
        return {"status": "ok"}

    @app.get("/ready", tags=["Operación"])
    def disponible(respuesta: Response) -> dict[str, Any]:
        """**Disponibilidad**: ¿puede este proceso atender de verdad?

        Comprueba lo que hace falta para responder una petición cualquiera: la
        base y el almacén. Es lo que debe mirar un balanceador antes de mandar
        tráfico, y lo que hay que mirar tras un despliegue.

        Responde `503` si algo falta, con **qué** falta. Un `503` sin detalle
        obliga a entrar en la máquina para averiguar cuál de las dos cosas es.
        """
        piezas: dict[str, str] = {}
        try:
            with app.state.engine.connect() as conn:
                conn.execute(sa_text("SELECT 1"))
            piezas["base"] = "ok"
        except Exception as exc:  # noqa: BLE001 — cualquier fallo cuenta igual
            piezas["base"] = f"error: {type(exc).__name__}"
        try:
            almacen = app.state.object_store
            # Una clave que no existe: `existe()` no escribe nada y ejercita la
            # conexión con el almacén, que es lo que se quiere saber.
            almacen.existe("comprobacion/disponibilidad")
            piezas["almacen"] = "ok"
        except Exception as exc:  # noqa: BLE001
            piezas["almacen"] = f"error: {type(exc).__name__}"

        listo = all(v == "ok" for v in piezas.values())
        if not listo:
            respuesta.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "ok" if listo else "no disponible", "piezas": piezas}

    @app.get("/metrics", tags=["Operación"], include_in_schema=False)
    def metricas_() -> Response:
        """Lo que lee Prometheus.

        `[LIM]` **Sin autenticar**, como es habitual: no lleva datos de negocio,
        solo contadores y duraciones por ruta. Aun así no debe publicarse en
        Internet: revela el mapa de rutas y el volumen de uso. Se cierra en el
        proxy o en la red, no aquí.
        """
        metricas.medir_cola(app.state.engine)
        return Response(content=metricas.exponer(), media_type=metricas.TIPO_MIME)

    api = "/api/v1"
    app.include_router(identity_router, prefix=api)
    app.include_router(directorio_router, prefix=api)
    app.include_router(catalogs_router, prefix=api)
    app.include_router(projects_router, prefix=api)
    app.include_router(phases_router, prefix=api)
    app.include_router(phase_ops_router, prefix=api)
    app.include_router(assets_router, prefix=api)
    app.include_router(ubicaciones_router, prefix=api)
    app.include_router(memoria_router, prefix=api)
    app.include_router(extraccion_router, prefix=api)
    app.include_router(equipment_router, prefix=api)
    app.include_router(findings_router, prefix=api)
    app.include_router(capex_router, prefix=api)
    app.include_router(pricing_router, prefix=api)
    app.include_router(evidence_router, prefix=api)
    app.include_router(documents_router, prefix=api)
    app.include_router(reporting_router, prefix=api)
    app.include_router(revision_documental_router, prefix=api)
    app.include_router(suggestions_router, prefix=api)

    def _medir(scope: Any, metodo: str, estado: int, segundos: float) -> None:
        """De cada petición, a los contadores. La ruta con plantilla."""
        ruta = metricas.plantilla_de_ruta(scope)
        metricas.PETICIONES.labels(metodo=metodo, ruta=ruta, estado=str(estado)).inc()
        metricas.DURACION.labels(metodo=metodo, ruta=ruta).observe(segundos)

    # `add_middleware` y no envolver `app` a mano: así FastAPI lo coloca dentro
    # de su propia pila y el `ContextVar` sigue puesto cuando corren los
    # manejadores de excepción, que es donde el identificador más falta hace.
    app.add_middleware(observabilidad.TrazaDePeticion, al_terminar=_medir)
    return app


app = crear_app()

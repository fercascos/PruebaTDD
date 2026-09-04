"""Infraestructura de pruebas.

Las pruebas marcadas `@pytest.mark.db` corren contra **PostgreSQL real**. No
hay alternativa: lo que se quiere comprobar —la Row Level Security con ámbitos,
el `EXCLUDE` que impide solapar periodos, los `CHECK`, el trigger que acota el
inicio de sesión— no existe fuera de PostgreSQL. Contra un doble en memoria
todas esas pruebas pasarían sin comprobar nada.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from esg.conector.memoria import LectorEnMemoria
from esg.core.config import Settings, get_settings
from esg.core.db import ContextoRLS, aplicar_contexto
from esg.core.security import VerificadorLocal, emitir_token_local
from esg.identidad.permisos import permisos_de
from esg.main import crear_app

RAIZ = Path(__file__).resolve().parents[3]
ESQUEMA = RAIZ / "apps" / "esg-api" / "src" / "esg" / "db" / "schema.sql"

URL_ADMIN = os.environ.get("TEST_DATABASE_URL")
USUARIO_APP = "esg_app"
CLAVE_APP = "prueba-local-sin-valor-real"  # noqa: S105 — base efímera de pruebas

SECRETO = "secreto-solo-para-la-suite-de-pruebas-0123456789"  # noqa: S105

#: Usuarios de prueba: etiqueta → (organización, rol).
PERFILES = {
    "admin_a": ("org_a", "ADMIN"),
    "gestor_a": ("org_a", "GESTOR"),
    "analista_a": ("org_a", "ANALISTA"),
    "lector_a": ("org_a", "LECTOR"),
    # El cliente externo: sin ámbito no ve nada, con ámbito ve su cartera.
    "cliente_a": ("org_a", "CLIENTE"),
    "cliente_sin_ambito_a": ("org_a", "CLIENTE"),
    # Sin `sub_oidc`: sirve para probar el emparejamiento del primer acceso.
    "recien_invitado_a": ("org_a", "LECTOR"),
    "admin_b": ("org_b", "ADMIN"),
}


def correo_de(etiqueta: str) -> str:
    org = PERFILES[etiqueta][0]
    return f"{etiqueta}@{org}.example"


def _url_como_app(url_admin: str) -> str:
    cola = url_admin.split("@", 1)[1]
    return f"postgresql+psycopg://{USUARIO_APP}:{CLAVE_APP}@{cola}"


@pytest.fixture(scope="session")
def motor_admin() -> Iterator[Engine]:
    if not URL_ADMIN:
        pytest.skip("TEST_DATABASE_URL no definida: se omiten las pruebas de base de datos")
    engine = create_engine(URL_ADMIN, future=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text(ESQUEMA.read_text(encoding="utf-8")))
        # El usuario de aplicación NO es propietario y NO tiene BYPASSRLS: si
        # lo tuviera, toda la seguridad de este esquema sería decorativa.
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {USUARIO_APP}"))
        conn.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "
                + USUARIO_APP
            )
        )
        conn.execute(
            text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {USUARIO_APP}")
        )
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def motor_app(motor_admin: Engine) -> Iterator[Engine]:
    engine = create_engine(_url_como_app(str(URL_ADMIN)), future=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def fabrica(motor_app: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=motor_app, expire_on_commit=False, future=True)


@pytest.fixture(scope="session")
def datos(motor_admin: Engine) -> dict[str, uuid.UUID]:
    """Dos organizaciones, sus usuarios y una cartera con dos activos.

    Se siembra como administrador de la base **a propósito**: dar de alta la
    primera organización es justo lo que la RLS impide hacer a la aplicación.
    """
    ids: dict[str, uuid.UUID] = {}
    with motor_admin.begin() as conn:
        for etiqueta, slug in (("org_a", "alfa"), ("org_b", "beta")):
            ids[etiqueta] = conn.execute(
                text("INSERT INTO organizacion (nombre, slug) VALUES (:n, :s) RETURNING id"),
                {"n": slug.title(), "s": slug},
            ).scalar_one()

        for etiqueta, (org, rol) in PERFILES.items():
            sujeto = None if etiqueta == "recien_invitado_a" else f"local:{correo_de(etiqueta)}"
            emisor = None if sujeto is None else "esg-local"
            ids[etiqueta] = conn.execute(
                text(
                    "INSERT INTO usuario (organizacion_id, email, nombre, rol, emisor_oidc, "
                    "sub_oidc) VALUES (:o, :e, :n, CAST(:r AS rol_usuario), :em, :s) RETURNING id"
                ),
                {
                    "o": ids[org],
                    "e": correo_de(etiqueta),
                    "n": etiqueta,
                    "r": rol,
                    "em": emisor,
                    "s": sujeto,
                },
            ).scalar_one()

        ids["cartera_a"] = conn.execute(
            text(
                "INSERT INTO cartera (organizacion_id, nombre, codigo) "
                "VALUES (:o, 'Cartera Ibérica', 'IB') RETURNING id"
            ),
            {"o": ids["org_a"]},
        ).scalar_one()
        ids["cartera_a2"] = conn.execute(
            text(
                "INSERT INTO cartera (organizacion_id, nombre, codigo) "
                "VALUES (:o, 'Cartera Levante', 'LV') RETURNING id"
            ),
            {"o": ids["org_a"]},
        ).scalar_one()
        ids["cartera_b"] = conn.execute(
            text(
                "INSERT INTO cartera (organizacion_id, nombre, codigo) "
                "VALUES (:o, 'Cartera de Beta', 'BT') RETURNING id"
            ),
            {"o": ids["org_b"]},
        ).scalar_one()

        for etiqueta, cartera, codigo, nombre, superficie in (
            ("torre", "cartera_a", "A-001", "Torre Norte", 10000),
            ("nave", "cartera_a2", "A-002", "Nave Sur", 20000),
            ("edificio_b", "cartera_b", "B-001", "Sede Beta", 5000),
        ):
            org = "org_b" if etiqueta == "edificio_b" else "org_a"
            ids[etiqueta] = conn.execute(
                text(
                    "INSERT INTO activo (organizacion_id, cartera_id, codigo, nombre, "
                    "tipologia, superficie_alquilable_m2) VALUES (:o, :c, :cod, :n, 'OFICINAS', "
                    ":s) RETURNING id"
                ),
                {
                    "o": ids[org],
                    "c": ids[cartera],
                    "cod": codigo,
                    "n": nombre,
                    "s": superficie,
                },
            ).scalar_one()

        for etiqueta, activo, vector, codigo, unidad in (
            ("luz_torre", "torre", "ELECTRICIDAD", "ES0031000000001", "kWh"),
            ("agua_torre", "torre", "AGUA", "CT-AGUA-01", "m3"),
            ("gas_torre", "torre", "GAS", "ES0021000000001", "m3"),
            ("luz_nave", "nave", "ELECTRICIDAD", "ES0031000000002", "kWh"),
        ):
            ids[etiqueta] = conn.execute(
                text(
                    "INSERT INTO punto_de_suministro (organizacion_id, activo_id, vector, "
                    "codigo, unidad_de_factura) VALUES (:o, :a, CAST(:v AS vector_esg), :c, :u) "
                    "RETURNING id"
                ),
                {
                    "o": ids["org_a"],
                    "a": ids[activo],
                    "v": vector,
                    "c": codigo,
                    "u": unidad,
                },
            ).scalar_one()

        # El cliente ve la Cartera Ibérica y nada más. El otro cliente, nada.
        conn.execute(
            text(
                "INSERT INTO ambito_de_visibilidad (organizacion_id, usuario_id, cartera_id) "
                "VALUES (:o, :u, :c)"
            ),
            {"o": ids["org_a"], "u": ids["cliente_a"], "c": ids["cartera_a"]},
        )
    return ids


@pytest.fixture
def como(fabrica: sessionmaker[Session], datos: dict[str, uuid.UUID]):
    """Sesión actuando como el usuario indicado.  `with como("gestor_a") as s:`"""

    @contextmanager
    def _abrir(etiqueta: str) -> Iterator[Session]:
        org, rol = PERFILES[etiqueta]
        ctx = ContextoRLS(
            organizacion_id=datos[org],
            usuario_id=datos[etiqueta],
            permisos=permisos_de(rol),
        )
        s = fabrica()
        try:
            s.begin()
            aplicar_contexto(s, ctx)
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    return _abrir


@asynccontextmanager
async def _sin_ciclo_de_vida(app: FastAPI):  # type: ignore[no-untyped-def]
    """El motor lo pone la fixture: la aplicación no lee DATABASE_URL aquí."""
    yield


def montar_app(
    motor: Engine, fabrica: sessionmaker[Session], lector: LectorEnMemoria | None = None
) -> FastAPI:
    app = crear_app()
    app.router.lifespan_context = _sin_ciclo_de_vida
    app.state.engine = motor
    app.state.session_factory = fabrica
    app.state.verificador = VerificadorLocal(secreto=SECRETO)
    app.state.lector_de_facturas = lector or LectorEnMemoria()
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="test", app_secret_key=SECRETO, auth_mode="local"
    )
    return app


@pytest.fixture(scope="session")
def cliente(motor_app: Engine, fabrica: sessionmaker[Session]) -> Iterator[TestClient]:
    with TestClient(montar_app(motor_app, fabrica)) as c:
        yield c


@pytest.fixture(scope="session")
def cab(datos: dict[str, uuid.UUID]):
    """Cabecera `Authorization` de un usuario de prueba."""

    def _cabecera(etiqueta: str) -> dict[str, str]:
        correo = correo_de(etiqueta)
        token = emitir_token_local(
            secreto=SECRETO, sujeto=f"local:{correo}", email=correo, nombre=etiqueta
        )
        return {"Authorization": f"Bearer {token}"}

    return _cabecera

"""Infraestructura de pruebas.

Las pruebas marcadas `@pytest.mark.db` corren contra **PostgreSQL real**, no
contra SQLite ni contra un doble. No hay alternativa: la Row Level Security, los
`CHECK`, los triggers y las columnas generadas son justo lo que se quiere
comprobar, y ninguna de esas cosas existe fuera de PostgreSQL.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from tdd.catalogs.seeding import sembrar_catalogos
from tdd.core.config import Settings, get_settings
from tdd.core.db import ContextoRLS, aplicar_contexto
from tdd.core.security import crear_token
from tdd.evidence.storage import AlmacenEnMemoria
from tdd.main import crear_app
from tdd.phases.seeding import sembrar_fases

RAIZ = Path(__file__).resolve().parents[3]
ESQUEMA = RAIZ / "apps" / "api" / "src" / "tdd" / "db" / "schema.sql"

URL_ADMIN = os.environ.get("TEST_DATABASE_URL")
USUARIO_APP = "tdd_app"
CLAVE_APP = "prueba-local-sin-valor-real"  # noqa: S105 — base efímera de pruebas


def _url_como_app(url_admin: str) -> str:
    """Misma base, pero conectando como el usuario de aplicación."""
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
        sembrar_catalogos(conn)
        sembrar_fases(conn)

        # El usuario de aplicación NO es propietario de las tablas y NO tiene
        # BYPASSRLS. Si lo tuviera, las políticas no se le aplicarían y toda la
        # seguridad de este esquema sería decorativa. `test_el_usuario_de_
        # aplicacion_no_puede_saltarse_la_rls` lo verifica.
        conn.execute(text("GRANT USAGE ON SCHEMA public TO " + USUARIO_APP))
        conn.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "
                + USUARIO_APP
            )
        )
        conn.execute(
            text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO " + USUARIO_APP)
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
def datos_base(motor_admin: Engine) -> dict[str, uuid.UUID]:
    """Dos organizaciones con sus usuarios. Es el escenario del aislamiento."""
    ids: dict[str, uuid.UUID] = {}
    with motor_admin.begin() as conn:
        for etiqueta, slug in (("org_a", "alfa"), ("org_b", "beta")):
            ids[etiqueta] = conn.execute(
                text("INSERT INTO organization (name, slug) VALUES (:n, :s) RETURNING id"),
                {"n": slug.title(), "s": slug},
            ).scalar_one()

        usuarios = [
            ("admin_a", "org_a", "admin@alfa.example", "ADMIN", True),
            # [REQ] Un ADMIN SIN la marca explícita. Existe porque su ausencia
            # ocultó un fallo real: la API le dejaba pasar y la RLS le
            # bloqueaba la escritura, y salía un 500 en vez de un permiso.
            ("admin_sin_marca_a", "org_a", "admin2@alfa.example", "ADMIN", False),
            ("consultor_a", "org_a", "consultor@alfa.example", "CONSULTOR", False),
            ("consultor2_a", "org_a", "otro@alfa.example", "CONSULTOR", False),
            ("lector_a", "org_a", "lector@alfa.example", "LECTOR", False),
            ("admin_b", "org_b", "admin@beta.example", "ADMIN", True),
        ]
        for etiqueta, org, email, rol, gestiona in usuarios:
            ids[etiqueta] = conn.execute(
                text(
                    "INSERT INTO app_user (organization_id, email, full_name, password_hash, "
                    "org_role, can_manage_suggestions) "
                    "VALUES (:o, :e, :n, 'x', CAST(:r AS org_role), :g) RETURNING id"
                ),
                {"o": ids[org], "e": email, "n": etiqueta, "r": rol, "g": gestiona},
            ).scalar_one()

        for etiqueta, org, nombre in (("cliente_a", "org_a", "Inversora Ficticia S.L."),):
            ids[etiqueta] = conn.execute(
                text("INSERT INTO client (organization_id, name) VALUES (:o, :n) RETURNING id"),
                {"o": ids[org], "n": nombre},
            ).scalar_one()

        ids["proyecto_a"] = conn.execute(
            text(
                "INSERT INTO project (organization_id, client_id, internal_code, name) "
                "VALUES (:o, :c, '2026-014', 'TDD Cartera Norte') RETURNING id"
            ),
            {"o": ids["org_a"], "c": ids["cliente_a"]},
        ).scalar_one()
    return ids


@pytest.fixture
def como(fabrica: sessionmaker[Session], datos_base: dict[str, uuid.UUID]):
    """Devuelve una sesión actuando como el usuario indicado.

    Uso:  with como("consultor_a") as s: ...
    """
    org_de = {
        "admin_a": "org_a",
        "admin_sin_marca_a": "org_a",
        "consultor_a": "org_a",
        "consultor2_a": "org_a",
        "lector_a": "org_a",
        "admin_b": "org_b",
    }
    # El permiso EFECTIVO: un ADMIN atiende el buzón aunque no lleve la marca.
    # Es lo mismo que calcula `UsuarioActual.gestiona_sugerencias`.
    gestiona = {"admin_a", "admin_b", "admin_sin_marca_a"}

    @contextmanager
    def _abrir(usuario: str) -> Iterator[Session]:
        ctx = ContextoRLS(
            organization_id=datos_base[org_de[usuario]],
            user_id=datos_base[usuario],
            can_manage_suggestions=usuario in gestiona,
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


# ─────────────────────────────────────────────────────────────────────────────
#  Cliente HTTP compartido por las pruebas de API
# ─────────────────────────────────────────────────────────────────────────────

#: Secreto de firma solo para la suite. No se parece a nada de producción.
SECRETO_PRUEBAS = "secreto-solo-para-la-suite-de-pruebas-0123456789"  # noqa: S105

#: Rol y permiso de gestión de sugerencias por usuario de prueba.
PERFILES = {
    "admin_a": ("org_a", "ADMIN", True),
    "admin_sin_marca_a": ("org_a", "ADMIN", False),
    "admin_b": ("org_b", "ADMIN", True),
    "consultor_a": ("org_a", "CONSULTOR", False),
    "consultor2_a": ("org_a", "CONSULTOR", False),
    "lector_a": ("org_a", "LECTOR", False),
}


@asynccontextmanager
async def _sin_ciclo_de_vida(app):  # type: ignore[no-untyped-def]
    """El motor lo aporta la fixture: la aplicación no debe leer DATABASE_URL."""
    yield


@pytest.fixture(scope="session")
def cliente(motor_app: Engine, fabrica: sessionmaker[Session]) -> Iterator[TestClient]:
    app = crear_app()
    app.router.lifespan_context = _sin_ciclo_de_vida
    app.state.engine = motor_app
    app.state.session_factory = fabrica
    # El almacén de objetos se inyecta: la suite no escribe binarios en disco.
    app.state.object_store = AlmacenEnMemoria()
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="test", app_secret_key=SECRETO_PRUEBAS
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def cab(datos_base: dict[str, uuid.UUID]):
    """Cabecera `Authorization` para un usuario de prueba.

    Uso:  cliente.get("/api/v1/...", headers=cab("consultor_a"))
    """

    def _cabecera(usuario: str) -> dict[str, str]:
        org, rol, gestiona = PERFILES[usuario]
        token = crear_token(
            secreto=SECRETO_PRUEBAS,
            user_id=datos_base[usuario],
            organization_id=datos_base[org],
            org_role=rol,
            can_manage_suggestions=gestiona,
            ttl_minutos=15,
        )
        return {"Authorization": f"Bearer {token}"}

    return _cabecera

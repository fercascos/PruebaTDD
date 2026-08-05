"""Motor, sesión y **contexto de organización por petición**.

La pieza crítica de este módulo es `sesion_con_contexto`. La Row Level Security
de PostgreSQL decide qué filas ve una consulta a partir de tres variables de
sesión; si no se fijan, el usuario no ve **nada**. Ese es el fallo seguro que se
busca: olvidarse produce una lista vacía, no una fuga.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True, slots=True)
class ContextoRLS:
    """Lo que la base de datos necesita saber para aplicar sus políticas."""

    organization_id: uuid.UUID
    user_id: uuid.UUID
    can_manage_suggestions: bool = False


def crear_motor(url: str, *, pool_size: int = 10, max_overflow: int = 20) -> Engine:
    return create_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        future=True,
    )


def crear_fabrica_de_sesiones(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def aplicar_contexto(session: Session, ctx: ContextoRLS) -> None:
    """Fija las variables de sesión que leen las políticas RLS.

    `SET LOCAL` acota el valor **a la transacción en curso**: cuando la
    transacción termina, la conexión vuelve al pool sin arrastrar el contexto
    del usuario anterior. Con `SET` a secas, una conexión reutilizada podría
    servir datos de otra organización, que es exactamente el fallo que la RLS
    debía impedir.
    """
    session.execute(
        text("SELECT set_config('app.current_org_id', :v, TRUE)"),
        {"v": str(ctx.organization_id)},
    )
    session.execute(
        text("SELECT set_config('app.current_user_id', :v, TRUE)"),
        {"v": str(ctx.user_id)},
    )
    session.execute(
        text("SELECT set_config('app.can_manage_suggestions', :v, TRUE)"),
        {"v": "true" if ctx.can_manage_suggestions else "false"},
    )


@contextmanager
def sesion_con_contexto(
    factory: sessionmaker[Session], ctx: ContextoRLS
) -> Iterator[Session]:
    """Abre una sesión con el contexto RLS ya aplicado, dentro de transacción."""
    session = factory()
    try:
        session.begin()
        aplicar_contexto(session, ctx)
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

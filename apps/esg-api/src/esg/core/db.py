"""Motor, sesión y **contexto de RLS por petición**.

La pieza crítica es `aplicar_contexto`. Las políticas del esquema deciden qué
filas ve —y qué filas puede escribir— cada consulta a partir de cinco variables
de sesión. Sin fijarlas, no se ve nada: ese es el fallo seguro que se busca.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from esg.identidad.permisos import Permisos


@dataclass(frozen=True, slots=True)
class ContextoRLS:
    organizacion_id: uuid.UUID
    usuario_id: uuid.UUID
    permisos: Permisos


def crear_motor(url: str, *, pool_size: int = 10, max_overflow: int = 20) -> Engine:
    return create_engine(
        url, pool_size=pool_size, max_overflow=max_overflow, pool_pre_ping=True, future=True
    )


def crear_fabrica_de_sesiones(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def aplicar_contexto(session: Session, ctx: ContextoRLS) -> None:
    """Fija las variables de sesión que leen las políticas.

    `set_config(..., TRUE)` es `SET LOCAL`: el valor muere con la transacción.
    Con `SET` a secas, una conexión devuelta al pool arrastraría el contexto
    del usuario anterior y podría servir datos de otra organización, que es
    exactamente lo que la RLS venía a impedir.
    """
    valores = {
        "app.organizacion_id": str(ctx.organizacion_id),
        "app.usuario_id": str(ctx.usuario_id),
        "app.ve_todo": _bool(ctx.permisos.ve_todo),
        "app.escribe_estructura": _bool(ctx.permisos.escribe_estructura),
        "app.escribe_datos": _bool(ctx.permisos.escribe_datos),
    }
    for clave, valor in valores.items():
        session.execute(
            text("SELECT set_config(:k, :v, TRUE)"),
            {"k": clave, "v": valor},
        )


def _bool(v: bool) -> str:
    return "true" if v else "false"


@contextmanager
def sesion_con_contexto(factory: sessionmaker[Session], ctx: ContextoRLS) -> Iterator[Session]:
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

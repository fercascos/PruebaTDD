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

#: Los idiomas que la aplicación sabe servir. Lista cerrada a propósito: un
#: valor cualquiera en `app.idioma` no rompe nada —`nombre()` cae al
#: castellano—, pero tenerla escrita deja claro qué se espera.
IDIOMAS = frozenset({"es", "en"})


@dataclass(frozen=True, slots=True)
class ContextoRLS:
    """Lo que la base de datos necesita saber para aplicar sus políticas."""

    organization_id: uuid.UUID
    user_id: uuid.UUID
    can_manage_suggestions: bool = False
    #: `[REQ]` 0030 · En qué idioma devuelve `nombre()` los catálogos. Viaja
    #: por aquí y no por el argumento de cada consulta por la misma razón que
    #: la organización: hay tres lectores —API, informe PPTX y exportación
    #: XLSX— y el tercero corre en un worker, sin petición HTTP. Un solo
    #: canal, un solo sitio donde olvidarse, y olvidarse devuelve castellano,
    #: que es un fallo visible y no una fuga.
    idioma: str = "es"


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
    # `[REQ]` 0030 · Lo lee la función `nombre(name_es, name_en)`. Se valida
    # aquí contra la lista cerrada en vez de confiar en quien construye el
    # contexto: el valor sale de una cabecera HTTP, y lo que llega de fuera no
    # entra en una variable de sesión sin mirarlo. Cualquier otra cosa es
    # castellano, que es el idioma del producto.
    fijar_idioma(session, ctx.idioma)


def fijar_idioma(session: Session, idioma: str) -> None:
    """Fija el idioma en que `nombre(name_es, name_en)` devuelve los catálogos.

    Lo llama `aplicar_contexto()` al abrir cada petición, y además dos rutas
    que **mandan sobre la cabecera**, a propósito:

    * Generar un informe lo fija al idioma de **la plantilla elegida**: la
      plantilla es la elección del idioma, y por eso hay una por idioma.
    * Exportar el CAPEX a XLSX lo fija al del desplegable de la pantalla, que
      es el que elige cuál de las dos plantillas del cliente se rellena.

    En los dos casos sería un error seguir el idioma de la interfaz: alguien
    que trabaja en castellano y pide el entregable en inglés quiere el
    entregable en inglés.

    Se valida contra la lista cerrada en vez de confiar en quien lo llama: el
    valor viene de una cabecera HTTP o de un parámetro de consulta, y lo que
    llega de fuera no entra en una variable de sesión sin mirarlo. Cualquier
    otra cosa es castellano, que es el idioma del producto.

    `TRUE` es el tercer argumento de `set_config`: *is_local*. Ata el valor a
    la transacción en curso, así que la conexión vuelve al pool sin arrastrar
    el idioma del usuario anterior. Es la misma razón que en el contexto RLS.
    """
    session.execute(
        text("SELECT set_config('app.idioma', :v, TRUE)"),
        {"v": idioma if idioma in IDIOMAS else "es"},
    )


@contextmanager
def sesion_con_contexto(factory: sessionmaker[Session], ctx: ContextoRLS) -> Iterator[Session]:
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

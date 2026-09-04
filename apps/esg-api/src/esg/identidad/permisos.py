"""Qué puede hacer cada rol. **Un solo sitio**, y no por elegancia.

Estos tres permisos viajan a dos destinos: a la API, que devuelve 403, y a las
variables de sesión que leen las políticas RLS de PostgreSQL. Cuando el cálculo
está en dos sitios y discrepan, el usuario no ve un permiso denegado: ve un 500
—«new row violates row-level security policy»— y nadie entiende por qué.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

ROLES: Final = ("ADMIN", "GESTOR", "ANALISTA", "LECTOR", "CLIENTE")


@dataclass(frozen=True, slots=True)
class Permisos:
    #: Ve toda la organización. `False` obliga a pasar por
    #: `ambito_de_visibilidad`: sin ámbito, no ve nada. Es el fallo seguro.
    ve_todo: bool
    #: Da de alta carteras, activos, suministros, usuarios y ámbitos.
    escribe_estructura: bool
    #: Carga consumos: lecturas, ocupación e importaciones.
    escribe_datos: bool


_POR_ROL: Final[dict[str, Permisos]] = {
    "ADMIN": Permisos(ve_todo=True, escribe_estructura=True, escribe_datos=True),
    "GESTOR": Permisos(ve_todo=True, escribe_estructura=True, escribe_datos=True),
    # Carga y analiza consumos, pero no da de alta activos: el inventario lo
    # mantiene quien responde de él.
    "ANALISTA": Permisos(ve_todo=True, escribe_estructura=False, escribe_datos=True),
    "LECTOR": Permisos(ve_todo=True, escribe_estructura=False, escribe_datos=False),
    # El rol pensado para el día que esto se abra a clientes. Nace ya, y no el
    # día que haga falta, porque toda la aplicación está construida encima:
    # añadirlo después sería revisar cada consulta.
    "CLIENTE": Permisos(ve_todo=False, escribe_estructura=False, escribe_datos=False),
}


def permisos_de(rol: str) -> Permisos:
    """`[REQ]` Un rol desconocido no es un error: es el permiso más pequeño.

    Un rol que llegue de una versión más nueva de la base de datos —o de un
    token viejo— no debe abrir puertas. Se degrada a «no ve nada y no escribe
    nada», que es visible al instante y no filtra.
    """
    return _POR_ROL.get(rol, Permisos(ve_todo=False, escribe_estructura=False, escribe_datos=False))

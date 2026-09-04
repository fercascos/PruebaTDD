"""Códigos de estado que se usan en varios sitios.

`422` está aquí como número y no como la constante de Starlette
porque Starlette ha renombrado esa constante —ahora es `..._UNPROCESSABLE_
CONTENT`— y usar cualquiera de las dos ata el código a una versión concreta. El
número no cambia desde el RFC 4918.
"""

from __future__ import annotations

from typing import Final

NO_PROCESABLE: Final = 422

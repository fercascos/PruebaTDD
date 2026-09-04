"""Rutas de desarrollo. **No se montan fuera de `AUTH_MODE=local`.**

Existen para poder recorrer la aplicación entera —y para que el frontend se
pueda desarrollar— sin un directorio de Azure delante. No es un modo degradado
que se pueda dejar encendido: `Settings` no admite `AUTH_MODE=local` en
`staging` ni en `production`, así que en un despliegue estas rutas **no
existen**, ni siquiera devolviendo 403.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from esg.core.deps import SettingsDep
from esg.core.security import emitir_token_local

router = APIRouter(prefix="/api/v1/desarrollo", tags=["desarrollo"])


class Entrada(BaseModel):
    email: EmailStr


class TokenFuera(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/token", response_model=TokenFuera)
def token_de_desarrollo(datos: Entrada, settings: SettingsDep) -> TokenFuera:
    """Firma un token para un usuario que ya esté dado de alta.

    No crea la ficha: si el correo no está, el emparejamiento fallará después
    con el mismo mensaje que con Azure. Así el camino de desarrollo se parece
    al de verdad hasta en los errores.
    """
    if settings.auth_mode != "local":  # pragma: no cover — la ruta ni se monta
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No disponible")
    return TokenFuera(
        access_token=emitir_token_local(
            secreto=settings.app_secret_key,
            sujeto=f"local:{datos.email}",
            email=str(datos.email),
            nombre=str(datos.email).split("@")[0],
        )
    )

"""Configuración. Todo del entorno; ni un secreto en el código."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # ── Aplicación ──────────────────────────────────────────────────────────
    app_env: Literal["local", "test", "staging", "production"] = "local"
    app_secret_key: str = Field(default="", repr=False)
    app_base_url: str = "http://localhost:5174"
    log_level: str = "INFO"

    database_url: PostgresDsn | None = None
    database_migration_url: PostgresDsn | None = None
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # ── Identidad ───────────────────────────────────────────────────────────
    #: `entra` verifica el token contra el JWKS del tenant de Azure. `local`
    #: acepta tokens HS256 firmados por esta misma aplicación, y **solo existe
    #: para desarrollo y para la suite**: el validador de abajo impide
    #: arrancar con él fuera de local, porque un despliegue con `local` acepta
    #: cualquier token que alguien se firme con el secreto que encuentre.
    auth_mode: Literal["entra", "local"] = "local"
    #: Identificador del directorio de Azure (Entra ID). Con él se construye el
    #: emisor y la dirección del JWKS si no se dan a mano.
    azure_tenant_id: str = ""
    #: `[REQ]` El identificador de ESTA aplicación en Entra ID. Es el `aud` que
    #: debe traer el token: sin comprobarlo, un token legítimo emitido para
    #: OTRA aplicación del mismo directorio entraría aquí como válido.
    azure_client_id: str = ""
    #: Vacío = se deduce del tenant. Se puede fijar para un directorio B2C o
    #: para un emisor propio de cliente.
    azure_issuer: str = ""
    azure_jwks_url: str = ""
    #: Cuánto se guarda el juego de claves públicas de Azure. Azure las rota;
    #: pedirlas en cada petición es un viaje de red por llamada, y no pedirlas
    #: nunca deja fuera a todo el mundo el día de la rotación.
    azure_jwks_ttl_seconds: int = 3600
    #: Ventana de tolerancia para el desfase de reloj al validar `exp`/`nbf`.
    token_leeway_seconds: int = 60

    # ── Conector con el lector de facturas (Azure) ──────────────────────────
    #: Vacío = no hay conector configurado y el endpoint responde 503 diciendo
    #: eso, en vez de fallar contra una dirección inventada.
    lector_facturas_url: str = ""
    lector_facturas_api_key: str = Field(default="", repr=False)
    lector_facturas_timeout_seconds: float = 30.0
    #: Por debajo de esta confianza, la lectura entra como PENDIENTE_REVISION
    #: en vez de CONFIRMADA. La IA acierta mucho; «mucho» no es «siempre», y un
    #: consumo mal leído no se distingue de uno bueno una vez está en la suma.
    lector_facturas_confianza_minima: float = 0.85

    # ── Interfaz ────────────────────────────────────────────────────────────
    cors_origenes: str = "http://localhost:5174"

    @property
    def origenes_permitidos(self) -> list[str]:
        return [o.strip() for o in self.cors_origenes.split(",") if o.strip()]

    @property
    def emisor_esperado(self) -> str:
        if self.azure_issuer:
            return self.azure_issuer
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}/v2.0"

    @property
    def jwks_url(self) -> str:
        if self.azure_jwks_url:
            return self.azure_jwks_url
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}/discovery/v2.0/keys"

    @field_validator("auth_mode")
    @classmethod
    def _entra_fuera_de_local(cls, v: str, info) -> str:  # type: ignore[no-untyped-def]
        """`[REQ]` Fuera de local, la identidad la pone Azure.

        Sin esto, un despliegue mal configurado arrancaría aceptando tokens
        firmados con `APP_SECRET_KEY` —que está en el fichero de entorno del
        servidor— y nadie lo notaría: la aplicación funcionaría igual de bien
        para quien tuviera ese secreto.
        """
        env = info.data.get("app_env", "local")
        if v == "local" and env in ("staging", "production"):
            raise ValueError(
                "AUTH_MODE=local no se admite fuera de desarrollo: fuera de local la "
                "identidad la emite Entra ID (AUTH_MODE=entra)."
            )
        return v

    @field_validator("azure_client_id")
    @classmethod
    def _client_id_requerido_con_entra(cls, v: str, info) -> str:  # type: ignore[no-untyped-def]
        """Con Entra, el `aud` es obligatorio. Y no es burocracia.

        Un directorio corporativo emite tokens para decenas de aplicaciones. Si
        no se comprueba para cuál se emitió este, el token que la intranet dio a
        un empleado para otra cosa abre también este dashboard.
        """
        if info.data.get("auth_mode") == "entra" and not v:
            raise ValueError("AUTH_MODE=entra exige AZURE_CLIENT_ID (el `aud` del token).")
        return v

    @field_validator("app_secret_key")
    @classmethod
    def _secreto_fuera_de_local(cls, v: str, info) -> str:  # type: ignore[no-untyped-def]
        env = info.data.get("app_env", "local")
        if env in ("staging", "production") and len(v) < 32:
            raise ValueError(
                "APP_SECRET_KEY debe tener al menos 32 caracteres fuera de local. "
                "Generar con: openssl rand -hex 32"
            )
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()

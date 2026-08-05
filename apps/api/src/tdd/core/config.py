"""Configuración de la aplicación.

Todos los valores se leen del entorno. No hay ni un secreto en el código: ver
`.env.example`, que documenta cada variable sin un solo valor real.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
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
    app_base_url: str = "http://localhost:5173"
    log_level: str = "INFO"

    # ── Base de datos ───────────────────────────────────────────────────────
    database_url: PostgresDsn | None = None
    database_migration_url: PostgresDsn | None = None
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # ── Autenticación ───────────────────────────────────────────────────────
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14

    # ── Almacenamiento de objetos ───────────────────────────────────────────
    # [LIM] Solo está implementado el adaptador sobre disco. El de S3 con
    # Object Lock —la cuarta barrera que protege los originales— no existe
    # todavía y no se afirma que funcione.
    storage_local_dir: Path = Path("./var/objetos")
    max_upload_mb: int = 50
    photo_trash_purge_days: int = 30

    # ── Precios ─────────────────────────────────────────────────────────────
    # P-06: no hay ninguna fuente externa. La bandera existe para que el
    # arranque falle si alguien intenta habilitar una sin pasar por la revisión
    # de condiciones de uso, que vive en la base de datos.
    price_source_http_timeout_seconds: int = 10
    price_source_user_agent: str = ""

    # ── Fuentes corporativas ────────────────────────────────────────────────
    corporate_fonts_required: str = (
        "Gotham Light,Gotham Book,Gotham Medium,Gotham Bold,Gotham Black,Gotham Ultra"
    )
    font_fallback_warn: bool = True
    pptx_embed_fonts: bool = False  # P-39 pendiente: contrato de licencia sin verificar

    @property
    def required_font_families(self) -> list[str]:
        return [f.strip() for f in self.corporate_fonts_required.split(",") if f.strip()]

    @field_validator("app_secret_key")
    @classmethod
    def _secret_required_outside_local(cls, v: str, info) -> str:  # type: ignore[no-untyped-def]
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

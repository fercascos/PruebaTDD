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

    # ── Correo saliente ─────────────────────────────────────────────────────
    # Sin `SMTP_HOST` o sin `MAIL_FROM` no se envía nada: se registra en el log
    # que NO se ha enviado. Una aplicación recién desplegada sin SMTP no debe
    # fallar al pedir una recuperación —dejaría a la gente fuera sin saber por
    # qué— ni fingir que ha mandado un correo que nadie va a recibir.
    # [LIM] El adaptador SMTP no se ha probado contra un servidor real.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = Field(default="", repr=False)
    mail_from: str = ""

    # ── Almacenamiento de objetos ───────────────────────────────────────────
    # `disco` es el adaptador de desarrollo; `s3` el de producción, con Object
    # Lock sobre los originales. [LIM] El de S3 está probado contra `moto`, un
    # simulador: eso ejercita el código, no demuestra que un bucket concreto
    # esté bien creado. Para eso está `AlmacenS3.comprobar()`, que corre contra
    # el bucket real al arrancar.
    storage_backend: Literal["disco", "s3"] = "disco"
    storage_local_dir: Path = Path("./var/objetos")
    storage_endpoint_url: str = ""
    storage_region: str = ""
    storage_bucket: str = ""
    storage_access_key_id: str = Field(default="", repr=False)
    storage_secret_access_key: str = Field(default="", repr=False)
    storage_signed_url_ttl_seconds: int = 300
    storage_enable_object_lock: bool = True
    # GOVERNANCE y no COMPLIANCE: ver el comentario de `MODOS_DE_BLOQUEO` en
    # evidence/storage.py. COMPLIANCE impediría atender un derecho de supresión
    # durante los años que dure la retención.
    storage_object_lock_mode: Literal["GOVERNANCE", "COMPLIANCE"] = "GOVERNANCE"
    storage_object_lock_days: int = 3650
    max_upload_mb: int = 50
    photo_trash_purge_days: int = 30

    # ── Antivirus ───────────────────────────────────────────────────────────
    # Desactivado por defecto y **se nota**: sin él, cada fichero queda
    # `NO_ANALIZADO`, que no es lo mismo que limpio, y el informe lo avisa.
    # [LIM] El adaptador de ClamAV no se ha probado contra un ClamAV real.
    antivirus_enabled: bool = False
    clamav_host: str = ""
    clamav_port: int = 3310
    clamav_timeout_seconds: float = 30.0

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

    @field_validator("storage_bucket")
    @classmethod
    def _bucket_requerido_con_s3(cls, v: str, info) -> str:  # type: ignore[no-untyped-def]
        """Elegir el adaptador de S3 sin bucket no arranca a medias.

        Sin esto, la aplicación levantaría y fallaría en la primera subida, que
        es en una visita y sin cobertura para depurar.
        """
        if info.data.get("storage_backend") == "s3" and not v:
            raise ValueError("STORAGE_BACKEND=s3 exige STORAGE_BUCKET")
        return v

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

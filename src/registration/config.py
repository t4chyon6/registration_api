"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import (
    AnyHttpUrl,
    Field,
    PositiveFloat,
    PositiveInt,
    PostgresDsn,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["critical", "error", "warning", "info", "debug", "trace"]


class Settings(BaseSettings):
    """Represent all runtime configuration for the application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: PostgresDsn
    database_pool_min_size: PositiveInt = 2
    database_pool_max_size: PositiveInt = 10

    activation_code_ttl_seconds: PositiveInt = 60

    email_service_url: AnyHttpUrl
    email_service_timeout: PositiveFloat = 5.0
    email_service_max_retries: PositiveInt = 3
    email_service_retry_max_wait: float = Field(default=10.0, ge=0.0)

    argon2_memory_cost: int = Field(default=65536, ge=8)
    argon2_time_cost: PositiveInt = 3
    argon2_parallelism: PositiveInt = 4
    argon2_hash_len: int = Field(default=32, ge=16)
    argon2_salt_len: int = Field(default=16, ge=16)
    max_resend_attempts: PositiveInt = 5
    resend_cooldown_seconds: int = Field(default=60, ge=0)

    log_level: LogLevel = "info"
    debug: bool = False

    @model_validator(mode="after")
    def validate_database_pool_bounds(self) -> Self:
        """Validate that the configured database pool bounds are coherent."""
        if self.database_pool_min_size > self.database_pool_max_size:
            msg = "DATABASE_POOL_MIN_SIZE must be <= DATABASE_POOL_MAX_SIZE"
            raise ValueError(msg)
        return self

    @property
    def database_dsn(self) -> str:
        """Return the PostgreSQL DSN as a plain string for asyncpg."""
        return str(self.database_url)

    @property
    def email_base_url(self) -> str:
        """Return the email service base URL as a plain string for httpx."""
        return str(self.email_service_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()  # ty: ignore[missing-argument]

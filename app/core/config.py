"""Application settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    app_name: str = "Financial Portfolio Tracker API"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = Field(
        default="postgresql+asyncpg://portfolio:portfolio@localhost:5432/portfolio_db",
        description="Async SQLAlchemy database URL.",
    )
    test_database_url: str = Field(
        default="postgresql+asyncpg://portfolio:portfolio@localhost:5433/portfolio_test_db",
        description="Async SQLAlchemy database URL used by integration tests.",
    )
    database_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "change-me-in-local-env"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    price_api_key: str | None = None
    price_cache_ttl_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()


settings = get_settings()

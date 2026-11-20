"""Application configuration.

All settings are loaded from environment variables (and an optional `.env`
file). See `.env.example` for the full list of supported keys.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "Arloraka Coffee - Sales Contribution API"
    environment: str = "development"
    debug: bool = True

    # --- Database (PostgreSQL) ---
    # Not used yet. Wired up in `app/db/session.py` for later integration.
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/arloraka_cafe"
    )

    # --- Auth / JWT ---
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- CORS (frontend Next.js) ---
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse the comma-separated `CORS_ORIGINS` value into a list."""
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

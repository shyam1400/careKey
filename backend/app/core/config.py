from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration. Secrets belong in .env, never in source."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CareKey API"
    environment: str = "development"
    database_url: str = Field(
        default="postgresql+psycopg://carekey:carekey@localhost:5432/carekey",
        description="SQLAlchemy URL using the psycopg (v3) driver.",
    )
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    local_storage_dir: str = "./storage"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = Field(
        default=None,
        description="Server-only Supabase key used for private Storage operations; never expose to the browser.",
    )
    supabase_storage_bucket: str = "medical-documents"
    osrm_base_url: str | None = None
    firebase_project_id: str | None = Field(
        default=None,
        description="Firebase project ID (FIREBASE_PROJECT_ID).",
    )
    firebase_credentials_path: str | None = Field(
        default=None,
        description=(
            "Path to a Firebase service-account JSON file "
            "(FIREBASE_CREDENTIALS_PATH). Never put the JSON contents in env."
        ),
    )
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None

    @property
    def twilio_configured(self) -> bool:
        return all((self.twilio_account_sid, self.twilio_auth_token, self.twilio_from_number))

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

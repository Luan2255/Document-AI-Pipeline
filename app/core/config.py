"""Load validated application settings from environment variables."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralize database, LLM, upload, and OCR configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://document_ai:document_ai@localhost:5432/document_ai"
    llm_api_key: SecretStr | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 45
    max_upload_size_bytes: int = 15 * 1024 * 1024
    max_pdf_pages: int = 20
    ocr_languages: str = "por+eng"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance for the application process."""

    return Settings()
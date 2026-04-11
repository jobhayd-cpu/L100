from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://legaluser:legalpass@localhost:5432/legaldb"
    database_url_sync: str = "postgresql://legaluser:legalpass@localhost:5432/legaldb"

    # Embeddings / LLM
    openai_api_key: Optional[str] = None
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    chat_model: str = "gpt-4o"

    # OCR
    tesseract_cmd: str = "tesseract"
    ocr_lang: str = "spa"

    # App
    log_level: str = "INFO"

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

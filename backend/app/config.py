from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

# Project root is two levels up from this file (backend/app/config.py -> Jestify/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = "postgresql+asyncpg://jestify:devpassword@localhost:5432/jestify"
    REDIS_URL: str = "redis://localhost:6379/0"
    ANTHROPIC_API_KEY: str = ""
    FISH_API_KEY: str = ""
    FISH_MODEL: str = "s1"
    FISH_VOICE_ID_LEBRON: str = "ea9a7ea97af942eab87c974d422263fe"
    FISH_VOICE_ID_GOKU: str = ""
    FISH_VOICE_ID_PETER: str = ""
    FISH_VOICE_ID_TAYLOR: str = ""
    CONTEXT7_API_KEY: str = ""
    DOCUMENT_EXTRACT_TIMEOUT_SECONDS: int = 30
    STORAGE_PATH: str = str(PROJECT_ROOT / "storage")
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

# Normalize STORAGE_PATH so relative values in .env are project-root relative.
_storage_path = Path(settings.STORAGE_PATH)
if not _storage_path.is_absolute():
    _storage_path = (PROJECT_ROOT / _storage_path).resolve()
settings.STORAGE_PATH = str(_storage_path)

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
    CONTEXT7_API_KEY: str = ""
    STORAGE_PATH: str = "./storage"
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

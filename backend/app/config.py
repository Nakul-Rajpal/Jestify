from pathlib import Path
from pydantic import field_validator
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
    JOB_QUEUE_WARNING_SECONDS: int = 45
    JOB_QUEUE_FAIL_SECONDS: int = 300
    STORAGE_PATH: str = str(PROJECT_ROOT / "storage")
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_asyncpg_prefix(cls, v: str) -> str:
        """Ensure asyncpg driver prefix regardless of how the URL is provided."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    @field_validator("STORAGE_PATH", mode="before")
    @classmethod
    def resolve_storage_path(cls, v: str) -> str:
        """Resolve relative STORAGE_PATH values relative to the project root."""
        path = Path(v)
        if not path.is_absolute():
            path = (PROJECT_ROOT / path).resolve()
        return str(path)


settings = Settings()

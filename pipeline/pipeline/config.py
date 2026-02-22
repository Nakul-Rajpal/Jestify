"""Pipeline configuration settings."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # …/Jestify
PIPELINE_ROOT = Path(__file__).resolve().parents[1]  # …/Jestify/pipeline

_raw_storage_path = os.getenv("STORAGE_PATH", str(PROJECT_ROOT / "storage"))
_storage_path = Path(_raw_storage_path)
if not _storage_path.is_absolute():
    _storage_path = (PROJECT_ROOT / _storage_path).resolve()
STORAGE_PATH: str = str(_storage_path)

_raw_assets_path = os.getenv("ASSETS_PATH", str(PIPELINE_ROOT / "assets"))
_assets_path = Path(_raw_assets_path)
if not _assets_path.is_absolute():
    _assets_path = (PROJECT_ROOT / _assets_path).resolve()
ASSETS_PATH: str = str(_assets_path)

# --------------------------------------------------------------------------- #
# Redis / Celery
# --------------------------------------------------------------------------- #
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/jestify")
FISH_API_KEY: str = os.getenv("FISH_API_KEY", "")
FISH_MODEL: str = os.getenv("FISH_MODEL", "s1")

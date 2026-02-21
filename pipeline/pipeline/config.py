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

STORAGE_PATH: str = os.getenv("STORAGE_PATH", str(PROJECT_ROOT / "storage"))
ASSETS_PATH: str = os.getenv("ASSETS_PATH", str(PIPELINE_ROOT / "assets"))

# --------------------------------------------------------------------------- #
# Redis / Celery
# --------------------------------------------------------------------------- #
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

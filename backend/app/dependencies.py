from typing import Optional

from .database import get_db  # noqa: F401 — re-exported for convenience


async def get_current_user() -> Optional[dict]:
    """
    Placeholder authentication dependency.
    Returns None for now; will be replaced with real auth later.
    """
    return None

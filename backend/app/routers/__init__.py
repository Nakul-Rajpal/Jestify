"""Collect and export all API routers."""

from .characters import router as characters_router
from .documents import router as documents_router
from .generate import router as generate_router
from .jobs import router as jobs_router
from .library import router as library_router
from .voices import router as voices_router

all_routers = [
    characters_router,
    documents_router,
    generate_router,
    jobs_router,
    library_router,
    voices_router,
]

__all__ = [
    "characters_router",
    "documents_router",
    "generate_router",
    "jobs_router",
    "library_router",
    "voices_router",
    "all_routers",
]

"""Fetches live Manim documentation from Context7 REST API."""

import json
import logging
import time
from typing import Optional

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

CONTEXT7_API_BASE = "https://context7.com/api/v2"
MANIM_LIBRARY_NAME = "manim community"

_docs_cache: dict[str, str] = {}


async def _resolve_library_id(library_name: str) -> Optional[str]:
    """Resolve a library name to a Context7 library ID via /search."""
    logger.info("[context7] Resolving library ID for: '%s'", library_name)
    logger.info("[context7]   API base: %s", CONTEXT7_API_BASE)
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{CONTEXT7_API_BASE}/search"
            logger.info("[context7]   GET %s?query=%s", url, library_name)
            resp = await client.get(url, params={"query": library_name})
            elapsed = time.perf_counter() - t0
            logger.info("[context7]   Response: %d in %.1fs", resp.status_code, elapsed)
            resp.raise_for_status()
            data = resp.json()

            results = data if isinstance(data, list) else data.get("results", [])
            logger.info("[context7]   Found %d results", len(results))

            if results:
                for r in results:
                    rid = r.get("id", "")
                    if "community" in rid.lower() or "stable" in rid.lower():
                        logger.info("[context7]   Resolved '%s' -> %s (preferred match)", library_name, rid)
                        return rid
                rid = results[0].get("id", "")
                logger.info("[context7]   Resolved '%s' -> %s (first result)", library_name, rid)
                return rid

            logger.warning("[context7]   No library found for '%s'", library_name)
            return None
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        logger.error("[context7]   Resolve failed after %.1fs: %s", elapsed, exc)
        return None


async def _get_library_docs(
    library_id: str,
    query: str,
    max_tokens: int = 5000,
) -> Optional[str]:
    """Fetch documentation for a resolved library from Context7."""
    logger.info("[context7] Fetching docs: lib=%s, query='%s', max_tokens=%d", library_id, query, max_tokens)
    t0 = time.perf_counter()
    try:
        headers = {}
        if settings.CONTEXT7_API_KEY:
            headers["Authorization"] = f"Bearer {settings.CONTEXT7_API_KEY}"
            logger.info("[context7]   Using API key: %s...", settings.CONTEXT7_API_KEY[:10])
        else:
            logger.warning("[context7]   No CONTEXT7_API_KEY configured")

        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{CONTEXT7_API_BASE}/context"
            logger.info("[context7]   GET %s", url)
            resp = await client.get(
                url,
                params={
                    "libraryId": library_id,
                    "query": query,
                    "tokens": str(max_tokens),
                },
                headers=headers,
            )
            elapsed = time.perf_counter() - t0
            logger.info("[context7]   Response: %d in %.1fs (%d bytes)", resp.status_code, elapsed, len(resp.content))
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            logger.info("[context7]   Content-Type: %s", content_type)

            if "text/plain" in content_type:
                logger.info("[context7]   Returning plain text (%d chars)", len(resp.text))
                return resp.text

            try:
                data = resp.json()
                if isinstance(data, dict):
                    result = (
                        data.get("context")
                        or data.get("content")
                        or json.dumps(data, indent=2)
                    )
                    logger.info("[context7]   Returning JSON content (%d chars)", len(result))
                    return result
                result = str(data)
                logger.info("[context7]   Returning stringified data (%d chars)", len(result))
                return result
            except Exception:
                logger.info("[context7]   Returning raw text (%d chars)", len(resp.text))
                return resp.text
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        logger.error("[context7]   Fetch docs failed after %.1fs: %s", elapsed, exc)
        return None


async def get_manim_docs(
    topic: str = "Scene animations MathTex Axes Create FadeIn",
    max_tokens: int = 5000,
) -> str:
    """Fetch live Manim documentation from Context7."""
    cache_key = f"manim:{topic}:{max_tokens}"
    if cache_key in _docs_cache:
        cached = _docs_cache[cache_key]
        logger.info("[context7] Cache HIT for '%s' (%d chars)", topic, len(cached))
        return cached

    logger.info("[context7] Cache MISS — fetching live docs for '%s'", topic)
    t0 = time.perf_counter()

    lib_id = await _resolve_library_id(MANIM_LIBRARY_NAME)
    if not lib_id:
        logger.warning("[context7] Could not resolve library, returning empty docs")
        return ""

    docs = await _get_library_docs(lib_id, topic, max_tokens)
    elapsed = time.perf_counter() - t0

    if docs and len(docs) > 100:
        logger.info("[context7] Fetched %d chars of Manim docs in %.1fs", len(docs), elapsed)
        _docs_cache[cache_key] = docs
        return docs

    logger.warning("[context7] Got short/empty response (%d chars) in %.1fs", len(docs or ""), elapsed)
    return ""


def clear_docs_cache() -> None:
    """Clear the documentation cache between pipeline runs."""
    count = len(_docs_cache)
    _docs_cache.clear()
    logger.info("[context7] Cache cleared (%d entries removed)", count)

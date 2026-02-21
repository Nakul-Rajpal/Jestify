"""Fish Audio API client helpers used by backend endpoints."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import parse, request, error

from shared.contracts.api_types import VoiceInfo

from ..config import settings


@dataclass
class FishAudioService:
    """Small REST client for Fish Audio voice metadata."""

    api_key: str = settings.FISH_API_KEY
    model: str = settings.FISH_MODEL
    base_url: str = "https://api.fish.audio"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key.strip())

    def list_voices(self, self_only: bool = True) -> list[VoiceInfo]:
        """Return available Fish voice models for selection in the UI."""
        if not self.is_configured:
            return []

        query = parse.urlencode({"self": str(self_only).lower()})
        url = f"{self.base_url}/model?{query}"
        req = request.Request(
            url=url,
            method="GET",
            headers={
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        try:
            with request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"Fish Audio list voices failed ({exc.code}): {body[:300]}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"Fish Audio list voices request failed: {exc}") from exc

        items = payload.get("items", [])
        voices: list[VoiceInfo] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            voices.append(self._to_voice_info(item))
        return voices

    @staticmethod
    def _to_voice_info(item: dict[str, Any]) -> VoiceInfo:
        voice_id = str(item.get("_id") or item.get("id") or "")
        name = (
            item.get("title")
            or item.get("name")
            or item.get("display_name")
            or "Unnamed Voice"
        )
        description = item.get("description") or item.get("train_mode") or ""
        language = None
        langs = item.get("languages")
        if isinstance(langs, list) and langs:
            language = str(langs[0])
        elif isinstance(item.get("language"), str):
            language = item["language"]

        visibility = str(item.get("visibility") or "").lower()
        is_public = bool(
            item.get("is_public")
            or item.get("public")
            or visibility == "public"
        )

        return VoiceInfo(
            id=voice_id,
            name=str(name),
            description=str(description),
            is_public=is_public,
            language=language,
        )

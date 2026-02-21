"""Router for listing available Fish Audio voices."""

from fastapi import APIRouter, HTTPException, Query

from shared.contracts.api_types import VoiceListResponse

from ..services.fish_audio import FishAudioService

router = APIRouter(prefix="/voices", tags=["voices"])


@router.get("", response_model=VoiceListResponse)
async def list_voices(
    self_only: bool = Query(
        default=True,
        description="When true, return only voices from the authenticated Fish account.",
    ),
) -> VoiceListResponse:
    service = FishAudioService()
    if not service.is_configured:
        return VoiceListResponse(voices=[])

    try:
        voices = service.list_voices(self_only=self_only)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return VoiceListResponse(voices=voices)

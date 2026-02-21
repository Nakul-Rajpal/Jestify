"""Router for character-related endpoints."""

from fastapi import APIRouter

from shared.contracts.character_schema import CHARACTER_PERSONALITIES
from shared.contracts.api_types import CharacterInfo, CharacterListResponse

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("", response_model=CharacterListResponse)
async def list_characters() -> CharacterListResponse:
    """Return the list of available characters with their personality info."""
    characters = []
    for char_id, personality in CHARACTER_PERSONALITIES.items():
        characters.append(
            CharacterInfo(
                id=char_id,
                name=personality.display_name,
                description=f"{personality.tone}. Uses analogies from {personality.analogy_domain}.",
                thumbnail_url=f"/static/characters/{char_id.value}.png",
                personality_summary=(
                    f"Voice: {personality.voice_style}. "
                    f"Catchphrases: {', '.join(personality.catchphrases)}"
                ),
            )
        )
    return CharacterListResponse(characters=characters)

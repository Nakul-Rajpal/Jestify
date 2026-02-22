"""Maps character + action to the correct sprite file in the assets directory."""

import logging
from pathlib import Path

from pipeline.config import ASSETS_PATH

logger = logging.getLogger(__name__)

_ASSETS = Path(ASSETS_PATH)

_ACTION_SPRITE_MAP: dict[str, str] = {
    "talking": "talking.png",
    "pointing": "pointing.png",
    "idle": "idle.png",
}

_DEFAULT_SPRITE = "idle.png"


def get_sprite_path(character_id: str, action: str) -> str:
    """Return the absolute path to a character sprite for the given action."""
    filename = _ACTION_SPRITE_MAP.get(action, _DEFAULT_SPRITE)
    if action not in _ACTION_SPRITE_MAP:
        logger.warning("[sprites] Unknown action '%s' for character '%s', using default '%s'", action, character_id, _DEFAULT_SPRITE)

    sprite_path = _ASSETS / "characters" / character_id / filename
    exists = sprite_path.exists()
    logger.info("[sprites] Sprite: character=%s, action=%s -> %s (exists=%s)", character_id, action, sprite_path, exists)

    if not exists:
        logger.warning("[sprites] Sprite file NOT FOUND: %s", sprite_path)
        char_dir = _ASSETS / "characters" / character_id
        if char_dir.exists():
            available = list(char_dir.iterdir())
            logger.warning("[sprites]   Available in %s: %s", char_dir, [f.name for f in available])
        else:
            logger.warning("[sprites]   Character directory missing: %s", char_dir)
            assets_dir = _ASSETS / "characters"
            if assets_dir.exists():
                logger.warning("[sprites]   Available characters: %s", [d.name for d in assets_dir.iterdir()])
            else:
                logger.warning("[sprites]   Assets/characters directory missing: %s", assets_dir)

    return str(sprite_path)

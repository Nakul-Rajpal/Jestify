"""Maps character + action to the correct sprite file in the assets directory."""

from pathlib import Path

from pipeline.config import ASSETS_PATH

_ASSETS = Path(ASSETS_PATH)

# Supported character actions and their sprite filenames.
_ACTION_SPRITE_MAP: dict[str, str] = {
    "talking": "talking.png",
    "pointing": "pointing.png",
    "idle": "idle.png",
}

_DEFAULT_SPRITE = "idle.png"


def get_sprite_path(character_id: str, action: str) -> str:
    """Return the absolute path to a character sprite for the given action.

    Parameters
    ----------
    character_id : str
        Character identifier (e.g. ``"spongebob"``).
    action : str
        The character action (``"talking"``, ``"pointing"``, ``"idle"``).

    Returns
    -------
    str
        Absolute path to the PNG sprite file.  Note: the file may not
        exist yet if sprites have not been added to the assets directory.
    """
    filename = _ACTION_SPRITE_MAP.get(action, _DEFAULT_SPRITE)
    return str(_ASSETS / "characters" / character_id / filename)

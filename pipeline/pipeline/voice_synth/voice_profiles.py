"""Voice profile mappings for each character.

Each character has a reference audio clip and transcript used by Fish Audio
for voice cloning.  The ``ref_audio_path`` files will be added to
``pipeline/assets/characters/<id>/voice_ref.wav`` by the team.
"""

from pathlib import Path

from pipeline.config import ASSETS_PATH

_ASSETS = Path(ASSETS_PATH)


CHARACTER_VOICE_PROFILES: dict[str, dict] = {
    "lebron": {
        "ref_audio_path": str(_ASSETS / "characters" / "lebron" / "voice_ref.wav"),
        "ref_transcript": (
            "Stay focused and trust the process. "
            "Let's break this down step by step."
        ),
        "language": "English",
    },
    "goku": {
        "ref_audio_path": str(_ASSETS / "characters" / "goku" / "voice_ref.wav"),
        "ref_transcript": (
            "This is awesome! "
            "Let's train and power up our understanding."
        ),
        "language": "English",
    },
    "peter": {
        "ref_audio_path": str(_ASSETS / "characters" / "peter" / "voice_ref.wav"),
        "ref_transcript": (
            "Alright, here's the thing. "
            "This is actually way simpler than it looks."
        ),
        "language": "English",
    },
    "taylor": {
        "ref_audio_path": str(_ASSETS / "characters" / "taylor" / "voice_ref.wav"),
        "ref_transcript": (
            "Let's walk through this step by step. "
            "Once you see the pattern, it all makes sense."
        ),
        "language": "English",
    },
}

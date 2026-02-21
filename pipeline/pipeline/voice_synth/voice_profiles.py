"""Voice profile mappings for each character.

Each character has a reference audio clip and transcript that will be
used by Qwen3-TTS for voice cloning.  The ``ref_audio_path`` files will
be added to ``pipeline/assets/characters/<id>/voice_ref.wav`` by the team.
"""

from pathlib import Path

from pipeline.config import ASSETS_PATH

_ASSETS = Path(ASSETS_PATH)


CHARACTER_VOICE_PROFILES: dict[str, dict] = {
    "spongebob": {
        "ref_audio_path": str(_ASSETS / "characters" / "spongebob" / "voice_ref.wav"),
        "ref_transcript": (
            "I'm ready, I'm ready, I'm ready! "
            "Today we're going to learn something really fun!"
        ),
        "language": "English",
    },
    "superman": {
        "ref_audio_path": str(_ASSETS / "characters" / "superman" / "voice_ref.wav"),
        "ref_transcript": (
            "Up, up, and away! "
            "Let me show you the power of knowledge."
        ),
        "language": "English",
    },
    "einstein": {
        "ref_audio_path": str(_ASSETS / "characters" / "einstein" / "voice_ref.wav"),
        "ref_transcript": (
            "Imagination is more important than knowledge. "
            "Let us explore this beautiful idea together."
        ),
        "language": "English",
    },
    "pirate": {
        "ref_audio_path": str(_ASSETS / "characters" / "pirate" / "voice_ref.wav"),
        "ref_transcript": (
            "Arrr, ye scallywags! "
            "Gather round and I'll teach ye the secrets of the seven seas!"
        ),
        "language": "English",
    },
}

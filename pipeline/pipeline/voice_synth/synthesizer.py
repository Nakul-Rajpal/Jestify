"""Voice synthesiser -- PLACEHOLDER implementation.

The real implementation will use Qwen3-TTS with voice cloning from
per-character reference audio clips.  For now this module generates
silent WAV files with an estimated duration so that the rest of the
pipeline can be tested end-to-end.
"""

import logging
import struct
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

# Rough estimate: 150 words per minute for narration speed.
_WORDS_PER_MINUTE = 150


class VoiceSynthesizer:
    """Placeholder text-to-speech synthesiser.

    TODO: Replace with Qwen3-TTS integration.
    The real implementation will:
        1. Load the character's reference audio clip and transcript
           from ``voice_profiles.CHARACTER_VOICE_PROFILES``.
        2. Use Qwen3-TTS voice cloning to synthesize the narration
           text in the character's voice.
        3. Write the output as a WAV/MP3 to *output_path*.
    """

    def synthesize(
        self,
        text: str,
        character_id: str,
        output_path: str,
    ) -> str:
        """Synthesize speech for *text* and write to *output_path*.

        Parameters
        ----------
        text : str
            Narration text to speak.
        character_id : str
            Character identifier (e.g. ``"spongebob"``).  Will be used
            to select the voice profile once Qwen3-TTS is integrated.
        output_path : str
            Destination file path for the generated audio.

        Returns
        -------
        str
            The absolute path to the output audio file.
        """
        duration = self._estimate_duration(text)
        logger.info(
            "PLACEHOLDER: generating %0.1fs silent WAV for character '%s' -> %s",
            duration,
            character_id,
            output_path,
        )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_silent_wav(output_path, duration)

        return str(Path(output_path).resolve())

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    @staticmethod
    def _estimate_duration(text: str) -> float:
        """Estimate audio duration from word count."""
        word_count = len(text.split())
        duration = (word_count / _WORDS_PER_MINUTE) * 60.0
        return max(duration, 1.0)  # minimum 1 second

    @staticmethod
    def _write_silent_wav(
        path: str,
        duration_seconds: float,
        sample_rate: int = 22050,
        channels: int = 1,
        sample_width: int = 2,
    ) -> None:
        """Write a silent (zero-filled) WAV file."""
        num_frames = int(sample_rate * duration_seconds)
        silent_data = b"\x00" * (num_frames * channels * sample_width)

        with wave.open(path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(silent_data)

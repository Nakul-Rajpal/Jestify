"""Voice synthesiser using Fish Audio, macOS ``say`` command, or edge-tts.

Generates real speech audio from narration text.  Falls back to a
silent WAV only if no TTS backend is available.
"""

import json
import logging
import platform
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from urllib import request, error

from pipeline.config import FISH_API_KEY, FISH_MODEL

logger = logging.getLogger(__name__)

_WORDS_PER_MINUTE = 150


class VoiceSynthesizer:
    """Text-to-speech synthesiser with automatic backend selection.

    Backends (tried in order):
    1. **edge-tts** — high-quality Microsoft neural voices (pip install edge-tts)
    2. **macOS say** — built-in on macOS, decent quality, zero dependencies
    3. **silent fallback** — generates a silent WAV when nothing else works
    """

    def __init__(self) -> None:
        self._fish_api_key = FISH_API_KEY
        self._fish_model = FISH_MODEL
        self._backend = self._detect_backend()
        logger.info("VoiceSynthesizer using backend: %s", self._backend)

    @staticmethod
    def _detect_backend() -> str:
        # Check edge-tts first (best quality)
        try:
            import edge_tts  # noqa: F401
            return "edge-tts"
        except ImportError:
            pass

        # macOS say command
        if platform.system() == "Darwin" and shutil.which("say"):
            return "macos-say"

        return "silent"

    def synthesize(
        self,
        text: str,
        character_id: str,
        voice_id: str | None,
        output_path: str,
    ) -> str:
        """Synthesize speech for *text* and write a WAV to *output_path*."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if voice_id and self._fish_api_key:
            try:
                self._synthesize_fish_audio(text, voice_id, output_path)
                logger.info("Voice synthesized: %s (fish-audio)", output_path)
                return str(Path(output_path).resolve())
            except Exception as exc:
                logger.warning(
                    "Fish Audio synthesis failed for voice %s, falling back: %s",
                    voice_id,
                    exc,
                )

        try:
            if self._backend == "edge-tts":
                self._synthesize_edge_tts(text, character_id, output_path)
            elif self._backend == "macos-say":
                self._synthesize_macos_say(text, output_path)
            else:
                logger.warning("No TTS backend available — generating silent WAV")
                duration = self._estimate_duration(text)
                self._write_silent_wav(output_path, duration)
        except Exception as exc:
            logger.warning("Local TTS backend failed, generating silent WAV: %s", exc)
            duration = self._estimate_duration(text)
            self._write_silent_wav(output_path, duration)

        logger.info("Voice synthesized: %s (%s)", output_path, self._backend)
        return str(Path(output_path).resolve())

    # ------------------------------------------------------------------ #
    # Backend: Fish Audio
    # ------------------------------------------------------------------ #

    def _synthesize_fish_audio(self, text: str, voice_id: str, output_path: str) -> None:
        payload = {
            "text": text,
            "reference_id": voice_id,
            "format": "wav",
        }
        req = request.Request(
            url="https://api.fish.audio/v1/tts",
            method="POST",
            headers={
                "Authorization": f"Bearer {self._fish_api_key}",
                "Content-Type": "application/json",
                "model": self._fish_model,
            },
            data=json.dumps(payload).encode("utf-8"),
        )
        try:
            with request.urlopen(req, timeout=120) as resp:
                audio_bytes = resp.read()
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"Fish Audio TTS failed ({exc.code}): {body[:300]}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"Fish Audio request failed: {exc}") from exc

        if not audio_bytes:
            raise RuntimeError("Fish Audio returned empty audio payload")

        # Most responses should already be WAV with format="wav".
        if audio_bytes[:4] == b"RIFF":
            Path(output_path).write_bytes(audio_bytes)
            return

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(audio_bytes)

        try:
            self._convert_audio_to_wav(tmp_path, output_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    # ------------------------------------------------------------------ #
    # Backend: edge-tts (best quality)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _synthesize_edge_tts(text: str, character_id: str, output_path: str) -> None:
        import asyncio
        import edge_tts

        # Map characters to fitting voices
        voice_map = {
            "lebron": "en-US-ChristopherNeural",
            "goku": "en-US-GuyNeural",
            "peter": "en-US-DavisNeural",
            "rogan": "en-US-EricNeural",
        }
        voice = voice_map.get(character_id, "en-US-GuyNeural")

        async def _run():
            communicate = edge_tts.Communicate(text, voice)
            # edge-tts outputs MP3; save to temp then convert to WAV
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_mp3 = tmp.name
            await communicate.save(tmp_mp3)

            # Convert MP3 to WAV with ffmpeg
            cmd = [
                "ffmpeg", "-y", "-i", tmp_mp3,
                "-ar", "22050", "-ac", "1",
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            Path(tmp_mp3).unlink(missing_ok=True)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg MP3→WAV failed: {result.stderr[:500]}")

        asyncio.run(_run())

    # ------------------------------------------------------------------ #
    # Backend: macOS say command
    # ------------------------------------------------------------------ #

    @staticmethod
    def _synthesize_macos_say(text: str, output_path: str) -> None:
        # say outputs AIFF; we convert to WAV via ffmpeg
        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
            tmp_aiff = tmp.name

        # Use a decent macOS voice — "Samantha" is clear and widely available
        cmd_say = [
            "say",
            "-v", "Samantha",
            "-r", "170",        # words per minute (natural pace)
            "-o", tmp_aiff,
            text,
        ]

        logger.info("Running: say -v Samantha -r 170 -o %s ...", tmp_aiff)
        result = subprocess.run(cmd_say, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error("say failed: %s", result.stderr)
            raise RuntimeError(f"macOS say failed: {result.stderr[:500]}")

        # Convert AIFF to WAV
        cmd_ffmpeg = [
            "ffmpeg", "-y", "-i", tmp_aiff,
            "-ar", "22050", "-ac", "1",
            output_path,
        ]
        result = subprocess.run(cmd_ffmpeg, capture_output=True, text=True, timeout=30)
        Path(tmp_aiff).unlink(missing_ok=True)

        if result.returncode != 0:
            logger.error("ffmpeg AIFF→WAV failed: %s", result.stderr)
            raise RuntimeError(f"ffmpeg AIFF→WAV failed: {result.stderr[:500]}")

    @staticmethod
    def _convert_audio_to_wav(input_path: str, output_path: str) -> None:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-ar", "22050", "-ac", "1",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg conversion failed: {result.stderr[:500]}")

    # ------------------------------------------------------------------ #
    # Fallback: silent WAV
    # ------------------------------------------------------------------ #

    @staticmethod
    def _estimate_duration(text: str) -> float:
        word_count = len(text.split())
        return max((word_count / _WORDS_PER_MINUTE) * 60.0, 1.0)

    @staticmethod
    def _write_silent_wav(
        path: str,
        duration_seconds: float,
        sample_rate: int = 22050,
        channels: int = 1,
        sample_width: int = 2,
    ) -> None:
        num_frames = int(sample_rate * duration_seconds)
        silent_data = b"\x00" * (num_frames * channels * sample_width)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(silent_data)

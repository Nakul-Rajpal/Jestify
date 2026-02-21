"""Voice synthesiser using macOS ``say`` command or edge-tts.

Generates real speech audio from narration text.  Falls back to a
silent WAV only if no TTS backend is available.
"""

import logging
import platform
import shutil
import subprocess
import tempfile
import time
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

_WORDS_PER_MINUTE = 150


class VoiceSynthesizer:
    """Text-to-speech synthesiser with automatic backend selection."""

    def __init__(self) -> None:
        logger.info("[voice] Detecting TTS backend...")
        self._backend = self._detect_backend()
        logger.info("[voice] Selected backend: %s", self._backend)

    @staticmethod
    def _detect_backend() -> str:
        try:
            import edge_tts  # noqa: F401
            logger.info("[voice]   edge-tts available (pip package found)")
            return "edge-tts"
        except ImportError:
            logger.info("[voice]   edge-tts not installed")

        if platform.system() == "Darwin" and shutil.which("say"):
            logger.info("[voice]   macOS 'say' command available")
            return "macos-say"

        logger.warning("[voice]   No TTS backend found, will use silent fallback")
        return "silent"

    def synthesize(
        self,
        text: str,
        character_id: str,
        output_path: str,
    ) -> str:
        """Synthesize speech for *text* and write a WAV to *output_path*."""
        word_count = len(text.split())
        logger.info("[voice] ┌─ Synthesize: backend=%s, character=%s", self._backend, character_id)
        logger.info("[voice] │  Text: %d chars, %d words", len(text), word_count)
        logger.info("[voice] │  Preview: %.150s...", text)
        logger.info("[voice] │  Output: %s", output_path)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        t0 = time.perf_counter()

        if self._backend == "edge-tts":
            self._synthesize_edge_tts(text, character_id, output_path)
        elif self._backend == "macos-say":
            self._synthesize_macos_say(text, output_path)
        else:
            logger.warning("[voice] │  No TTS backend — generating silent WAV")
            duration = self._estimate_duration(text)
            logger.info("[voice] │  Estimated speech duration: %.1fs", duration)
            self._write_silent_wav(output_path, duration)

        elapsed = time.perf_counter() - t0
        out_file = Path(output_path)
        if out_file.exists():
            logger.info(
                "[voice] └─ OK: %s (%.1f KB, %.1fs)",
                output_path, out_file.stat().st_size / 1024, elapsed,
            )
        else:
            logger.error("[voice] └─ Output file missing after synthesis: %s", output_path)

        return str(out_file.resolve())

    @staticmethod
    def _synthesize_edge_tts(text: str, character_id: str, output_path: str) -> None:
        import asyncio
        import edge_tts

        voice_map = {
            "spongebob": "en-US-GuyNeural",
            "superman": "en-US-ChristopherNeural",
            "einstein": "en-GB-RyanNeural",
            "pirate": "en-AU-WilliamNeural",
        }
        voice = voice_map.get(character_id, "en-US-GuyNeural")
        logger.info("[voice] │  edge-tts voice: %s (character: %s)", voice, character_id)

        async def _run():
            communicate = edge_tts.Communicate(text, voice)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_mp3 = tmp.name
            logger.info("[voice] │  Saving edge-tts MP3 to: %s", tmp_mp3)
            await communicate.save(tmp_mp3)

            mp3_size = Path(tmp_mp3).stat().st_size / 1024
            logger.info("[voice] │  MP3 generated: %.1f KB", mp3_size)

            cmd = [
                "ffmpeg", "-y", "-i", tmp_mp3,
                "-ar", "22050", "-ac", "1",
                output_path,
            ]
            logger.info("[voice] │  Converting MP3->WAV: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            Path(tmp_mp3).unlink(missing_ok=True)
            if result.returncode != 0:
                logger.error("[voice] │  ffmpeg MP3->WAV failed (exit %d): %s", result.returncode, result.stderr[:500])
                raise RuntimeError(f"ffmpeg MP3->WAV failed: {result.stderr[:500]}")

        asyncio.run(_run())

    @staticmethod
    def _synthesize_macos_say(text: str, output_path: str) -> None:
        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
            tmp_aiff = tmp.name

        cmd_say = ["say", "-v", "Samantha", "-r", "170", "-o", tmp_aiff, text]
        logger.info("[voice] │  Running: say -v Samantha -r 170 -o %s (%d chars)", tmp_aiff, len(text))

        result = subprocess.run(cmd_say, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error("[voice] │  'say' failed (exit %d): %s", result.returncode, result.stderr)
            raise RuntimeError(f"macOS say failed: {result.stderr[:500]}")

        aiff_size = Path(tmp_aiff).stat().st_size / 1024
        logger.info("[voice] │  AIFF generated: %.1f KB", aiff_size)

        cmd_ffmpeg = [
            "ffmpeg", "-y", "-i", tmp_aiff,
            "-ar", "22050", "-ac", "1",
            output_path,
        ]
        logger.info("[voice] │  Converting AIFF->WAV: %s", " ".join(cmd_ffmpeg))
        result = subprocess.run(cmd_ffmpeg, capture_output=True, text=True, timeout=30)
        Path(tmp_aiff).unlink(missing_ok=True)

        if result.returncode != 0:
            logger.error("[voice] │  ffmpeg AIFF->WAV failed (exit %d): %s", result.returncode, result.stderr)
            raise RuntimeError(f"ffmpeg AIFF->WAV failed: {result.stderr[:500]}")

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
        logger.info("[voice] │  Silent WAV written: %s (%.1fs, %d frames)", path, duration_seconds, num_frames)

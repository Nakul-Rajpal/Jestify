"""Voice synthesiser using Fish Audio, macOS ``say`` command, or edge-tts.

Generates real speech audio from narration text.  Falls back to a
silent WAV only if no TTS backend is available.
"""

import json
import logging
import os
import platform
import shutil
import ssl
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from urllib import request, error

from pipeline.config import FISH_API_KEY, FISH_MODEL
from shared.contracts.character_schema import CHARACTER_PERSONALITIES
from shared.contracts.enums import Character

logger = logging.getLogger(__name__)

_WORDS_PER_MINUTE = 150


class VoiceSynthesizer:
    """Text-to-speech synthesiser with automatic backend selection."""

    def __init__(self) -> None:
        self._sanitize_ssl_env()
        self._fish_api_key = FISH_API_KEY
        self._fish_model = FISH_MODEL
        self._fish_timeout_seconds = int(os.getenv("FISH_TIMEOUT_SECONDS", "20"))
        self._fish_fallback_voice_id = os.getenv("FISH_FALLBACK_VOICE_ID", "").strip() or None
        self._fish_global_voice_ids = self._collect_global_fish_voice_ids()
        self._allow_silent_fallback = os.getenv("ALLOW_SILENT_FALLBACK", "false").lower() in {"1", "true", "yes"}
        logger.info("[voice] Detecting local TTS backends...")
        self._local_backends = self._detect_local_backends()
        logger.info("[voice] Local backends: %s", self._local_backends or ["none"])
        logger.info("[voice] Allow silent fallback: %s", self._allow_silent_fallback)
        logger.info("[voice] Fish timeout: %ss", self._fish_timeout_seconds)
        if self._fish_fallback_voice_id:
            logger.info("[voice] Fish fallback voice id configured: %s", self._fish_fallback_voice_id)
        if self._fish_global_voice_ids:
            logger.info("[voice] Fish configured voice ids discovered: %d", len(self._fish_global_voice_ids))

    @staticmethod
    def _sanitize_ssl_env() -> None:
        for env_key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
            env_val = os.getenv(env_key)
            if env_val and not Path(env_val).exists():
                logger.warning(
                    "[voice] %s points to missing file '%s'; unsetting",
                    env_key,
                    env_val,
                )
                os.environ.pop(env_key, None)

    @staticmethod
    def _resolve_fish_voice_id(character_id: str, voice_id: str | None) -> str | None:
        """Resolve a Fish Audio voice ID: use explicit voice_id, else character default."""
        if voice_id:
            return voice_id
        try:
            char_enum = Character(character_id)
            personality = CHARACTER_PERSONALITIES.get(char_enum)
            if personality and personality.fish_voice_id:
                logger.info("[voice]   Using character default fish_voice_id for %s", character_id)
                return personality.fish_voice_id
        except (ValueError, KeyError):
            pass
        return None

    @staticmethod
    def _collect_global_fish_voice_ids() -> list[str]:
        ids: list[str] = []
        for key in (
            "FISH_VOICE_ID_LEBRON",
            "FISH_VOICE_ID_GOKU",
            "FISH_VOICE_ID_PETER",
            "FISH_VOICE_ID_TAYLOR",
        ):
            value = os.getenv(key, "").strip()
            if value and value not in ids:
                ids.append(value)
        return ids

    @staticmethod
    def _detect_local_backends() -> list[str]:
        backends: list[str] = []
        try:
            import edge_tts  # noqa: F401
            logger.info("[voice]   edge-tts available (pip package found)")
            backends.append("edge-tts")
        except ImportError:
            logger.info("[voice]   edge-tts not installed")

        if platform.system() == "Darwin" and shutil.which("say"):
            logger.info("[voice]   macOS 'say' command available")
            backends.append("macos-say")

        if not backends:
            logger.warning("[voice]   No local TTS backend found")
        return backends

    def synthesize(
        self,
        text: str,
        character_id: str,
        output_path: str,
        voice_id: str | None = None,
    ) -> str:
        """Synthesize speech for *text* and write a WAV to *output_path*."""
        word_count = len(text.split())
        logger.info("[voice] ┌─ Synthesize: character=%s", character_id)
        logger.info("[voice] │  Text: %d chars, %d words", len(text), word_count)
        logger.info("[voice] │  Preview: %.150s...", text)
        logger.info("[voice] │  Output: %s", output_path)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        t0 = time.perf_counter()
        errors: list[str] = []

        # Resolve Fish voice ID: explicit > character default
        resolved_voice_id = self._resolve_fish_voice_id(character_id, voice_id)
        if resolved_voice_id:
            logger.info("[voice] │  Fish voice ID: %s", resolved_voice_id)

        # Try Fish Audio first if a voice ID is available.
        fish_voice_candidates: list[str] = []
        if resolved_voice_id:
            fish_voice_candidates.append(resolved_voice_id)
        if self._fish_fallback_voice_id and self._fish_fallback_voice_id not in fish_voice_candidates:
            fish_voice_candidates.append(self._fish_fallback_voice_id)
        for candidate in self._fish_global_voice_ids:
            if candidate not in fish_voice_candidates:
                fish_voice_candidates.append(candidate)

        if fish_voice_candidates and self._fish_api_key:
            for fish_voice_id in fish_voice_candidates:
                try:
                    self._synthesize_fish_audio(text, fish_voice_id, output_path)
                    elapsed = time.perf_counter() - t0
                    out_file = Path(output_path)
                    logger.info(
                        "[voice] └─ OK (fish-audio voice=%s): %s (%.1f KB, %.1fs)",
                        fish_voice_id, output_path, out_file.stat().st_size / 1024, elapsed,
                    )
                    return str(out_file.resolve())
                except Exception as exc:
                    msg = f"fish voice {fish_voice_id}: {exc}"
                    errors.append(msg)
                    logger.warning("[voice] │  Fish Audio failed (%s)", msg)

        # Fall back to local TTS backends in sequence.
        for backend in self._local_backends:
            try:
                if backend == "edge-tts":
                    self._synthesize_edge_tts(text, character_id, output_path)
                elif backend == "macos-say":
                    self._synthesize_macos_say(text, output_path)
                else:
                    continue
                elapsed = time.perf_counter() - t0
                out_file = Path(output_path)
                logger.info(
                    "[voice] └─ OK (%s): %s (%.1f KB, %.1fs)",
                    backend, output_path, out_file.stat().st_size / 1024, elapsed,
                )
                return str(out_file.resolve())
            except Exception as exc:
                msg = f"{backend}: {exc}"
                errors.append(msg)
                logger.warning("[voice] │  Local backend failed (%s)", msg)

        # Final fallback behavior.
        if not self._allow_silent_fallback:
            detail = "; ".join(errors[:4]) if errors else "no TTS backends available"
            raise RuntimeError(
                "Voice synthesis failed and silent fallback is disabled. "
                f"Attempts: {detail}. "
                "Set ALLOW_SILENT_FALLBACK=true to permit silent audio."
            )
        logger.warning("[voice] │  All voice backends failed, generating silent WAV")
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

    # ------------------------------------------------------------------ #
    # Backend: Fish Audio
    # ------------------------------------------------------------------ #

    def _synthesize_fish_audio(self, text: str, voice_id: str, output_path: str) -> None:
        errors: list[str] = []
        audio_bytes: bytes | None = None
        for voice_key in ("reference_id", "voice_id"):
            payload = {
                "text": text,
                voice_key: voice_id,
                "format": "wav",
                "model": self._fish_model,
            }
            req = request.Request(
                url="https://api.fish.audio/v1/tts",
                method="POST",
                headers={
                    "Authorization": f"Bearer {self._fish_api_key}",
                    "Content-Type": "application/json",
                },
                data=json.dumps(payload).encode("utf-8"),
            )
            try:
                with request.urlopen(
                    req,
                    timeout=self._fish_timeout_seconds,
                    context=self._build_ssl_context(),
                ) as resp:
                    audio_bytes = resp.read()
                if audio_bytes:
                    break
                errors.append(f"{voice_key}: empty response")
            except error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="ignore")
                errors.append(f"{voice_key} HTTP {exc.code}: {body[:180]}")
            except error.URLError as exc:
                errors.append(f"{voice_key} URL error: {exc}")

        if not audio_bytes:
            raise RuntimeError(f"Fish Audio request failed. Attempts: {'; '.join(errors)}")

        # Most responses should already be WAV with format="wav".
        if audio_bytes[:4] == b"RIFF":
            Path(output_path).write_bytes(audio_bytes)
            self._assert_nonempty_wav(output_path, "fish-audio")
            return

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(audio_bytes)

        try:
            self._convert_audio_to_wav(tmp_path, output_path)
            self._assert_nonempty_wav(output_path, "fish-audio-converted")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @staticmethod
    def _build_ssl_context() -> ssl.SSLContext:
        """Use certifi CA bundle when available to avoid local trust-store issues."""
        try:
            import certifi

            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl.create_default_context()

    # ------------------------------------------------------------------ #
    # Backend: edge-tts (best quality)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _synthesize_edge_tts(text: str, character_id: str, output_path: str) -> None:
        import asyncio
        import edge_tts

        voice_map = {
            "lebron": "en-US-ChristopherNeural",
            "goku": "en-US-GuyNeural",
            "peter": "en-US-DavisNeural",
            "taylor": "en-US-AnaNeural",
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
            VoiceSynthesizer._assert_nonempty_wav(output_path, "edge-tts")

        asyncio.run(_run())

    # ------------------------------------------------------------------ #
    # Backend: macOS say
    # ------------------------------------------------------------------ #

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
        VoiceSynthesizer._assert_nonempty_wav(output_path, "macos-say")

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

    @staticmethod
    def _assert_nonempty_wav(path: str, backend_label: str) -> None:
        wav_path = Path(path)
        if not wav_path.exists():
            raise RuntimeError(f"{backend_label} produced no WAV output")
        if wav_path.stat().st_size < 1024:
            raise RuntimeError(f"{backend_label} produced tiny WAV ({wav_path.stat().st_size} bytes)")
        try:
            with wave.open(str(wav_path), "rb") as wf:
                duration = wf.getnframes() / max(wf.getframerate(), 1)
            if duration < 0.15:
                raise RuntimeError(f"{backend_label} produced near-empty WAV ({duration:.3f}s)")
        except wave.Error as exc:
            raise RuntimeError(f"{backend_label} output is not a readable WAV: {exc}") from exc

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
        logger.info("[voice] │  Silent WAV written: %s (%.1fs, %d frames)", path, duration_seconds, num_frames)

"""Voice synthesiser using Fish Audio, macOS ``say`` command, or edge-tts.

Generates real speech audio from narration text.  Falls back to a
silent WAV only if no TTS backend is available.
"""

import json
import logging
import os
import platform
import re
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
        self._strict_selected_voice_only = (
            os.getenv("STRICT_SELECTED_VOICE_ONLY", "true").lower()
            in {"1", "true", "yes"}
        )
        self._fish_fallback_voice_id = os.getenv("FISH_FALLBACK_VOICE_ID", "").strip() or None
        self._fish_voice_ids_by_character = self._collect_character_voice_ids()
        self._use_personality_fish_ids = (
            os.getenv("USE_PERSONALITY_FISH_IDS", "false").lower()
            in {"1", "true", "yes"}
        )
        self._allow_cross_character_voice_fallback = (
            os.getenv("ALLOW_CROSS_CHARACTER_VOICE_FALLBACK", "false").lower()
            in {"1", "true", "yes"}
        )
        self._require_fish_characters = self._parse_character_list(
            os.getenv("REQUIRE_FISH_VOICE_FOR_CHARACTERS", "")
        )
        self._allow_silent_fallback = os.getenv("ALLOW_SILENT_FALLBACK", "false").lower() in {"1", "true", "yes"}
        logger.info("[voice] Detecting local TTS backends...")
        self._local_backends = self._detect_local_backends()
        logger.info("[voice] Local backends: %s", self._local_backends or ["none"])
        logger.info("[voice] Strict selected voice only: %s", self._strict_selected_voice_only)
        logger.info("[voice] Allow silent fallback: %s", self._allow_silent_fallback)
        logger.info("[voice] Use personality fish ids: %s", self._use_personality_fish_ids)
        logger.info(
            "[voice] Allow cross-character Fish fallback: %s",
            self._allow_cross_character_voice_fallback,
        )
        logger.info("[voice] Require Fish for characters: %s", sorted(self._require_fish_characters))
        logger.info("[voice] Fish timeout: %ss", self._fish_timeout_seconds)
        if self._fish_fallback_voice_id:
            logger.info("[voice] Fish fallback voice id configured: %s", self._fish_fallback_voice_id)
        if self._fish_voice_ids_by_character:
            logger.info(
                "[voice] Fish character voice ids configured: %s",
                sorted(self._fish_voice_ids_by_character.keys()),
            )

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
    def _collect_character_voice_ids() -> dict[str, str]:
        mapping = {
            "lebron": os.getenv("FISH_VOICE_ID_LEBRON", "").strip(),
            "goku": os.getenv("FISH_VOICE_ID_GOKU", "").strip(),
            "peter": os.getenv("FISH_VOICE_ID_PETER", "").strip(),
            "taylor": os.getenv("FISH_VOICE_ID_TAYLOR", "").strip(),
        }
        return {k: v for k, v in mapping.items() if v}

    @staticmethod
    def _is_probable_fish_voice_id(value: str) -> bool:
        v = value.strip()
        return bool(re.fullmatch(r"[0-9a-fA-F]{32}", v))

    @staticmethod
    def _character_key(value: str) -> str:
        norm = re.sub(r"[^a-z]", "", value.lower())
        aliases = {
            "lebron": "lebron",
            "lebronjames": "lebron",
            "goku": "goku",
            "peter": "peter",
            "petergriffin": "peter",
            "taylor": "taylor",
            "taylorswift": "taylor",
        }
        return aliases.get(norm, norm)

    @classmethod
    def _parse_character_list(cls, raw: str) -> set[str]:
        values = set()
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            values.add(cls._character_key(part))
        return values

    def _build_fish_voice_candidates(self, character_id: str, requested_voice_id: str | None) -> list[str]:
        candidates: list[str] = []
        character_key = self._character_key(character_id)

        def add(candidate: str | None, source: str) -> None:
            if not candidate:
                return
            value = candidate.strip()
            if not value:
                return
            if not self._is_probable_fish_voice_id(value):
                logger.warning("[voice] │  Ignoring invalid Fish voice from %s: %s", source, value)
                return
            if value not in candidates:
                candidates.append(value)

        # 1) Explicit request voice_id, if valid ID.
        add(requested_voice_id, "request.voice_id")

        # 2) If request.voice_id looks like an alias ("peter griffin"), map to character env voice.
        if requested_voice_id and not self._is_probable_fish_voice_id(requested_voice_id):
            alias_key = self._character_key(requested_voice_id)
            add(self._fish_voice_ids_by_character.get(alias_key), f"voice alias '{requested_voice_id}'")

        # 3) Character-specific env voice.
        add(self._fish_voice_ids_by_character.get(character_key), f"env.{character_key}")

        # Strict mode: only selected/requested voice path. No additional IDs.
        if self._strict_selected_voice_only:
            return candidates

        # 4) Optional character personality default voice (off by default;
        # these IDs in source can get stale vs current env configuration).
        if self._use_personality_fish_ids:
            add(self._resolve_fish_voice_id(character_id, None), f"personality.{character_key}")

        # 5) Optional global fallback voice(s), only when explicitly enabled.
        if self._allow_cross_character_voice_fallback:
            add(self._fish_fallback_voice_id, "FISH_FALLBACK_VOICE_ID")
            for key in ("lebron", "goku", "peter", "taylor"):
                if key == character_key:
                    continue
                add(self._fish_voice_ids_by_character.get(key), f"env.{key}")

        return candidates

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
        character_key = self._character_key(character_id)

        fish_voice_candidates = self._build_fish_voice_candidates(character_id, voice_id)
        if fish_voice_candidates:
            logger.info("[voice] │  Fish voice candidates (%d): %s", len(fish_voice_candidates), fish_voice_candidates[:4])
        else:
            raise RuntimeError(
                "No Fish voice candidate is configured for this request. "
                "Set the desired voice ID and retry."
            )

        if not self._fish_api_key:
            raise RuntimeError("FISH_API_KEY is not configured. Fish voice synthesis cannot run.")

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

        detail = "; ".join(errors[:4]) if errors else "no Fish voice candidates configured"
        raise RuntimeError(
            f"Selected Fish voice failed for character '{character_key}'. "
            f"No fallback audio is enabled. Attempts: {detail}"
        )

    # ------------------------------------------------------------------ #
    # Backend: Fish Audio
    # ------------------------------------------------------------------ #

    def _synthesize_fish_audio(self, text: str, voice_id: str, output_path: str) -> None:
        errors: list[str] = []
        # Try both commonly used Fish payload keys and a few payload variants
        # (same selected voice id, no fallback voice).
        payload_variants = [
            {"format": "wav", "model": self._fish_model},
            {"format": "wav"},
            {"format": "mp3", "model": self._fish_model},
            {"format": "mp3"},
        ]

        for voice_key in ("reference_id", "voice_id"):
            for variant in payload_variants:
                payload = {
                    "text": text,
                    voice_key: voice_id,
                    **variant,
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
            except error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="ignore")
                errors.append(
                    f"{voice_key}/{variant.get('format','default')} HTTP {exc.code}: {body[:140]}"
                )
                continue
            except error.URLError as exc:
                errors.append(f"{voice_key}/{variant.get('format','default')} URL error: {exc}")
                continue

            if not audio_bytes:
                errors.append(f"{voice_key}/{variant.get('format','default')}: empty response")
                continue

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                tmp_wav_path = tmp_wav.name

            try:
                if audio_bytes[:4] == b"RIFF":
                    Path(tmp_wav_path).write_bytes(audio_bytes)
                else:
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
                        tmp_mp3_path = tmp_mp3.name
                        tmp_mp3.write(audio_bytes)
                    try:
                        self._convert_audio_to_wav(tmp_mp3_path, tmp_wav_path)
                    finally:
                        Path(tmp_mp3_path).unlink(missing_ok=True)

                self._assert_nonempty_wav(
                    tmp_wav_path,
                    f"fish-audio[{voice_key}/{variant.get('format','default')}]",
                )
                Path(output_path).write_bytes(Path(tmp_wav_path).read_bytes())
                return
            except Exception as exc:
                errors.append(f"{voice_key}/{variant.get('format','default')}: {exc}")
            finally:
                Path(tmp_wav_path).unlink(missing_ok=True)

        raise RuntimeError(f"Fish Audio request failed. Attempts: {'; '.join(errors)}")

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
        size_bytes = wav_path.stat().st_size
        if size_bytes < 512:
            raise RuntimeError(f"{backend_label} produced tiny WAV ({size_bytes} bytes)")

        # Prefer ffprobe for duration because some WAV variants report 0 frames
        # via Python's wave module even when audio is valid/playable.
        ffprobe_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nokey=1:noprint_wrappers=1",
            str(wav_path),
        ]
        try:
            probe = subprocess.run(
                ffprobe_cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if probe.returncode == 0:
                raw = (probe.stdout or "").strip()
                if raw:
                    duration = float(raw)
                    if duration >= 0.05:
                        return
                    raise RuntimeError(
                        f"{backend_label} produced near-empty WAV ({duration:.3f}s, {size_bytes} bytes)"
                    )
        except Exception:
            # Fall back to wave module checks below.
            pass

        try:
            with wave.open(str(wav_path), "rb") as wf:
                duration = wf.getnframes() / max(wf.getframerate(), 1)
            if duration < 0.05:
                raise RuntimeError(
                    f"{backend_label} produced near-empty WAV ({duration:.3f}s, {size_bytes} bytes)"
                )
        except wave.Error as exc:
            # If container isn't parseable by wave but file is reasonably sized,
            # let ffmpeg/compositor consume it.
            if size_bytes >= 4096:
                return
            raise RuntimeError(
                f"{backend_label} output is not a readable WAV ({size_bytes} bytes): {exc}"
            ) from exc

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

"""Composites character sprites and audio onto animation clips using FFmpeg."""

import logging
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class CharacterCompositor:
    """Overlays a character PNG sprite onto a ManimGL animation clip
    and mixes in the synthesized voice audio track.
    """

    def composite(
        self,
        animation_clip: str,
        character_sprite: str,
        audio_file: str,
        output_path: str,
        position: str = "bottom-right",
        scale: float = 0.25,
    ) -> str:
        """Composite character sprite and audio onto the animation clip."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        sprite = Path(character_sprite)

        logger.info("[compositor] ┌─ Compositing")
        logger.info("[compositor] │  Animation clip: %s (exists=%s)", animation_clip, Path(animation_clip).exists())
        logger.info("[compositor] │  Sprite: %s (exists=%s)", character_sprite, sprite.exists())
        logger.info("[compositor] │  Audio: %s (exists=%s)", audio_file, Path(audio_file).exists())
        logger.info("[compositor] │  Output: %s", output_path)
        logger.info("[compositor] │  Position: %s, Scale: %.2f", position, scale)

        if Path(animation_clip).exists():
            clip_size = Path(animation_clip).stat().st_size / (1024 * 1024)
            logger.info("[compositor] │  Animation clip size: %.1f MB", clip_size)
        else:
            logger.error("[compositor] │  Animation clip MISSING: %s", animation_clip)

        if Path(audio_file).exists():
            audio_size = Path(audio_file).stat().st_size / 1024
            logger.info("[compositor] │  Audio file size: %.1f KB", audio_size)
        else:
            logger.error("[compositor] │  Audio file MISSING: %s", audio_file)

        overlay_pos = self._overlay_position(position)

        if sprite.exists():
            sprite_size = sprite.stat().st_size / 1024
            logger.info("[compositor] │  Sprite size: %.1f KB", sprite_size)
            filter_complex = (
                f"[1:v]scale=iw*{scale}:ih*{scale}[sprite];"
                f"[0:v][sprite]overlay={overlay_pos}[vout];"
                f"[2:a]apad[aout]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", animation_clip,
                "-i", character_sprite,
                "-i", audio_file,
                "-filter_complex", filter_complex,
                "-map", "[vout]", "-map", "[aout]",
                "-c:v", "libx264", "-preset", "fast",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                output_path,
            ]
            logger.info("[compositor] │  Mode: sprite overlay + audio mix")
        else:
            logger.warning("[compositor] │  Sprite not found, using audio-only composite")
            cmd = [
                "ffmpeg", "-y",
                "-i", animation_clip,
                "-i", audio_file,
                "-filter_complex", "[1:a]apad[aout]",
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                output_path,
            ]

        logger.info("[compositor] │  Command: %s", " ".join(cmd))

        t0 = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        elapsed = time.perf_counter() - t0

        if result.stdout.strip():
            logger.info("[compositor] │  stdout: %s", result.stdout.strip()[:500])
        if result.stderr.strip():
            level = logging.ERROR if result.returncode != 0 else logging.DEBUG
            logger.log(level, "[compositor] │  stderr: %s", result.stderr.strip()[:1000])

        if result.returncode != 0:
            logger.error(
                "[compositor] └─ FAILED (exit %d, %.1fs)", result.returncode, elapsed,
            )
            raise RuntimeError(
                f"FFmpeg compositing failed (exit {result.returncode}):\n"
                f"{result.stderr[:2000]}"
            )

        out_size = Path(output_path).stat().st_size / (1024 * 1024)
        logger.info(
            "[compositor] └─ OK: %s (%.1f MB, %.1fs)", output_path, out_size, elapsed,
        )
        return str(Path(output_path).resolve())

    @staticmethod
    def _overlay_position(position: str) -> str:
        positions = {
            "bottom-right": "main_w-overlay_w-10:main_h-overlay_h-10",
            "bottom-left": "10:main_h-overlay_h-10",
            "top-right": "main_w-overlay_w-10:10",
            "top-left": "10:10",
        }
        return positions.get(position, positions["bottom-right"])

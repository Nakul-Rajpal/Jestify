"""Composites character sprites and audio onto animation clips using FFmpeg."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class CharacterCompositor:
    """Overlays a character PNG sprite onto a ManimGL animation clip
    and mixes in the synthesized voice audio track.

    The character is positioned in the bottom-right corner by default.
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
        """Composite character sprite and audio onto the animation clip.

        Parameters
        ----------
        animation_clip : str
            Path to the ManimGL-rendered MP4 video.
        character_sprite : str
            Path to the character PNG sprite image.
        audio_file : str
            Path to the synthesized voice WAV file.
        output_path : str
            Destination path for the composited MP4 video.
        position : str
            Where to place the character.  Supported values:
            ``"bottom-right"`` (default), ``"bottom-left"``,
            ``"top-right"``, ``"top-left"``.
        scale : float
            Fraction of the video width for the sprite.

        Returns
        -------
        str
            Absolute path to the composited output file.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        sprite = Path(character_sprite)

        # Build the FFmpeg overlay filter
        overlay_pos = self._overlay_position(position)

        if sprite.exists():
            # Full composite: overlay sprite + mix audio
            filter_complex = (
                f"[1:v]scale=iw*{scale}:ih*{scale}[sprite];"
                f"[0:v][sprite]overlay={overlay_pos}[vout]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", animation_clip,
                "-i", character_sprite,
                "-i", audio_file,
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", "2:a",
                "-c:v", "libx264",
                "-preset", "fast",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                output_path,
            ]
        else:
            # No sprite available -- just mix audio into the animation clip
            logger.warning(
                "Character sprite not found at %s -- mixing audio only",
                character_sprite,
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", animation_clip,
                "-i", audio_file,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                output_path,
            ]

        logger.info("Compositing: %s", " ".join(cmd))

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error("FFmpeg stderr:\n%s", result.stderr)
            raise RuntimeError(
                f"FFmpeg compositing failed (exit {result.returncode}):\n"
                f"{result.stderr[:2000]}"
            )

        return str(Path(output_path).resolve())

    @staticmethod
    def _overlay_position(position: str) -> str:
        """Return FFmpeg overlay position expression string.

        The sprite is placed with 10px padding from the chosen corner.
        """
        positions = {
            "bottom-right": "main_w-overlay_w-10:main_h-overlay_h-10",
            "bottom-left": "10:main_h-overlay_h-10",
            "top-right": "main_w-overlay_w-10:10",
            "top-left": "10:10",
        }
        return positions.get(position, positions["bottom-right"])

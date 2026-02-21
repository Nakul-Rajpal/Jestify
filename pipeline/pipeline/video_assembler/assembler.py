"""Assembles composited scene clips into a single final video using FFmpeg."""

import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class VideoAssembler:
    """Joins multiple scene clips into one continuous video.

    Uses FFmpeg's concat demuxer to concatenate the clips and encodes
    the result as H.264 at 1080p resolution.
    """

    def assemble(
        self,
        scene_clips: list[str],
        output_path: str,
        intro_title: str | None = None,
    ) -> str:
        """Assemble scene clips into the final video.

        Parameters
        ----------
        scene_clips : list[str]
            Ordered list of composited MP4 clip paths.
        output_path : str
            Destination path for the final video.
        intro_title : str, optional
            Title text (reserved for future title-card generation).

        Returns
        -------
        str
            Absolute path to the final assembled video.
        """
        if not scene_clips:
            raise ValueError("No scene clips provided for assembly")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if intro_title:
            logger.info("Video title: '%s' (title card not yet implemented)", intro_title)

        # Write the concat list file
        concat_file = self._write_concat_file(scene_clips)

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            output_path,
        ]

        logger.info("Assembling %d clips -> %s", len(scene_clips), output_path)

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            logger.error("FFmpeg stderr:\n%s", result.stderr)
            raise RuntimeError(
                f"FFmpeg assembly failed (exit {result.returncode}):\n"
                f"{result.stderr[:2000]}"
            )

        logger.info("Final video written to %s", output_path)
        return str(Path(output_path).resolve())

    @staticmethod
    def _write_concat_file(clips: list[str]) -> str:
        """Write a temporary FFmpeg concat list file and return its path."""
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="concat_")
        with open(fd, "w", encoding="utf-8") as f:
            for clip in clips:
                abs_clip = str(Path(clip).resolve())
                f.write(f"file '{abs_clip}'\n")
        return path

"""Assembles composited scene clips into a single final video using FFmpeg."""

import logging
import subprocess
import tempfile
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class VideoAssembler:
    """Joins multiple scene clips into one continuous video."""

    def assemble(
        self,
        scene_clips: list[str],
        output_path: str,
        intro_title: str | None = None,
    ) -> str:
        """Assemble scene clips into the final video."""
        logger.info("[assembler] ┌─ Assembling final video")
        logger.info("[assembler] │  Clips: %d", len(scene_clips))
        logger.info("[assembler] │  Output: %s", output_path)

        if not scene_clips:
            logger.error("[assembler] └─ No scene clips provided")
            raise ValueError("No scene clips provided for assembly")

        for i, clip in enumerate(scene_clips):
            exists = Path(clip).exists()
            size = Path(clip).stat().st_size / (1024 * 1024) if exists else 0
            logger.info("[assembler] │  Clip %d: %s (exists=%s, %.1f MB)", i + 1, clip, exists, size)
            if not exists:
                logger.error("[assembler] │  MISSING clip: %s", clip)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if intro_title:
            logger.info("[assembler] │  Title: '%s'", intro_title)

        concat_file = self._write_concat_file(scene_clips)
        concat_contents = Path(concat_file).read_text()
        logger.info("[assembler] │  Concat file: %s", concat_file)
        logger.info("[assembler] │  Concat contents:\n%s", concat_contents)

        fast_copy_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path,
        ]

        cmd = [
            "ffmpeg", "-y",
            "-fflags", "+genpts",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-map", "0:v:0", "-map", "0:a:0?",
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-af", "aresample=async=1:first_pts=0",
            "-c:v", "libx264", "-preset", "superfast", "-crf", "26",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]

        logger.info("[assembler] │  Fast-path command: %s", " ".join(fast_copy_cmd))
        logger.info("[assembler] │  Fallback command: %s", " ".join(cmd))

        t0 = time.perf_counter()
        result = subprocess.run(fast_copy_cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning(
                "[assembler] │  Fast-path concat-copy failed (exit %d), falling back to transcode",
                result.returncode,
            )
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        elapsed = time.perf_counter() - t0

        if result.stdout.strip():
            logger.info("[assembler] │  stdout: %s", result.stdout.strip()[:500])
        if result.stderr.strip():
            level = logging.ERROR if result.returncode != 0 else logging.DEBUG
            logger.log(level, "[assembler] │  stderr: %s", result.stderr.strip()[:1000])

        if result.returncode != 0:
            logger.error("[assembler] └─ FAILED (exit %d, %.1fs)", result.returncode, elapsed)
            raise RuntimeError(
                f"FFmpeg assembly failed (exit {result.returncode}):\n"
                f"{result.stderr[:2000]}"
            )

        out_path = Path(output_path)
        out_size = out_path.stat().st_size / (1024 * 1024)
        logger.info(
            "[assembler] └─ OK: %s (%.1f MB, %.1fs)", output_path, out_size, elapsed,
        )
        return str(out_path.resolve())

    @staticmethod
    def _write_concat_file(clips: list[str]) -> str:
        """Write a temporary FFmpeg concat list file and return its path."""
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="concat_")
        with open(fd, "w", encoding="utf-8") as f:
            for clip in clips:
                abs_clip = str(Path(clip).resolve())
                f.write(f"file '{abs_clip}'\n")
        return path

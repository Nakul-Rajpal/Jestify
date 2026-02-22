"""FFmpeg / ffprobe utility helpers."""

import json
import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)


def ensure_ffmpeg() -> None:
    """Check that ``ffmpeg`` and ``ffprobe`` are installed and on PATH."""
    for tool in ("ffmpeg", "ffprobe"):
        path = shutil.which(tool)
        if path is None:
            logger.error("[ffmpeg_helpers] '%s' NOT FOUND on PATH", tool)
            logger.error("[ffmpeg_helpers] PATH: %s", os.environ.get("PATH", ""))
            raise EnvironmentError(
                f"'{tool}' is not installed or not found on PATH. "
                "Please install FFmpeg (https://ffmpeg.org/) and ensure "
                "it is available in your system PATH."
            )
        logger.info("[ffmpeg_helpers] %s -> %s", tool, path)
    logger.info("[ffmpeg_helpers] ffmpeg and ffprobe are available")


def get_video_duration(path: str) -> float:
    """Return the duration of a video file in seconds using ffprobe."""
    logger.info("[ffmpeg_helpers] Probing duration of: %s", path)

    if not os.path.exists(path):
        logger.error("[ffmpeg_helpers] File does not exist: %s", path)
        raise RuntimeError(f"Video file does not exist: {path}")

    file_size = os.path.getsize(path) / (1024 * 1024)
    logger.info("[ffmpeg_helpers] File size: %.1f MB", file_size)

    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        logger.error("[ffmpeg_helpers] ffprobe failed (exit %d): %s", result.returncode, result.stderr[:500])
        raise RuntimeError(
            f"ffprobe failed for '{path}' (exit {result.returncode}):\n"
            f"{result.stderr[:1000]}"
        )

    try:
        info = json.loads(result.stdout)
        duration_str = info["format"]["duration"]
        duration = float(duration_str)
        format_name = info["format"].get("format_name", "unknown")
        bit_rate = info["format"].get("bit_rate", "unknown")
        logger.info(
            "[ffmpeg_helpers] Duration: %.1fs, format: %s, bitrate: %s",
            duration, format_name, bit_rate,
        )
        return duration
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.error("[ffmpeg_helpers] Failed to parse ffprobe output: %s", exc)
        logger.error("[ffmpeg_helpers] ffprobe stdout: %s", result.stdout[:500])
        raise RuntimeError(
            f"Could not parse duration from ffprobe output for '{path}'"
        ) from exc

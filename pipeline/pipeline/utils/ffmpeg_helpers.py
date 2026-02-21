"""FFmpeg / ffprobe utility helpers."""

import json
import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


def ensure_ffmpeg() -> None:
    """Check that ``ffmpeg`` and ``ffprobe`` are installed and on PATH.

    Raises
    ------
    EnvironmentError
        If either tool is missing.
    """
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise EnvironmentError(
                f"'{tool}' is not installed or not found on PATH. "
                "Please install FFmpeg (https://ffmpeg.org/) and ensure "
                "it is available in your system PATH."
            )
    logger.debug("ffmpeg and ffprobe are available")


def get_video_duration(path: str) -> float:
    """Return the duration of a video file in seconds using ffprobe.

    Parameters
    ----------
    path : str
        Path to the video file.

    Returns
    -------
    float
        Duration in seconds.

    Raises
    ------
    RuntimeError
        If ffprobe fails or returns no duration.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed for '{path}' (exit {result.returncode}):\n"
            f"{result.stderr[:1000]}"
        )

    try:
        info = json.loads(result.stdout)
        duration_str = info["format"]["duration"]
        return float(duration_str)
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise RuntimeError(
            f"Could not parse duration from ffprobe output for '{path}'"
        ) from exc

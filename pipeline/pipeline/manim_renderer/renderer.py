"""Executes ManimGL via subprocess to render scene files into MP4 clips."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Default render timeout: 5 minutes per scene
_RENDER_TIMEOUT_SECONDS = 300


class ManimRenderer:
    """Renders a generated ManimGL scene Python file into an MP4 video.

    Uses ``xvfb-run`` to provide a virtual display so rendering works in
    headless server environments.
    """

    def __init__(self, timeout: int = _RENDER_TIMEOUT_SECONDS):
        self._timeout = timeout

    def render_scene(self, scene_py_path: str, class_name: str) -> str:
        """Render a ManimGL scene and return the path to the output MP4.

        Parameters
        ----------
        scene_py_path : str
            Path to the generated ``.py`` file containing the ManimGL scene.
        class_name : str
            The ManimGL ``Scene`` subclass name to render.

        Returns
        -------
        str
            Absolute path to the rendered ``.mp4`` file.

        Raises
        ------
        RuntimeError
            If ManimGL exits with a non-zero code or times out.
        """
        scene_py = Path(scene_py_path).resolve()
        output_dir = scene_py.parent / "media"

        cmd = [
            "xvfb-run", "-a",
            "manimgl",
            str(scene_py),
            class_name,
            "-o",
            "--file_name", class_name,
            "--video_dir", str(output_dir),
        ]

        logger.info("Rendering: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(scene_py.parent),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"ManimGL render timed out after {self._timeout}s "
                f"for {scene_py_path}::{class_name}"
            ) from exc

        if result.returncode != 0:
            logger.error("ManimGL stderr:\n%s", result.stderr)
            raise RuntimeError(
                f"ManimGL render failed (exit {result.returncode}) "
                f"for {scene_py_path}::{class_name}:\n{result.stderr[:2000]}"
            )

        # Locate the output file -- ManimGL writes into output_dir
        mp4_path = self._find_output_mp4(output_dir, class_name)
        logger.info("Rendered %s -> %s", class_name, mp4_path)
        return mp4_path

    @staticmethod
    def _find_output_mp4(output_dir: Path, class_name: str) -> str:
        """Search the output directory for the rendered MP4 file."""
        # ManimGL typically outputs to <video_dir>/1080p30/<ClassName>.mp4
        # or similar resolution sub-directories.
        candidates = list(output_dir.rglob(f"{class_name}.mp4"))
        if candidates:
            return str(candidates[0])

        # Fallback: return any mp4 found
        all_mp4s = list(output_dir.rglob("*.mp4"))
        if all_mp4s:
            return str(all_mp4s[0])

        raise FileNotFoundError(
            f"No MP4 output found in {output_dir} for class {class_name}"
        )

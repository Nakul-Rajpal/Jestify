"""Executes ManimGL via subprocess to render scene files into MP4 clips."""

import logging
import os
import platform
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Default render timeout: 5 minutes per scene
_RENDER_TIMEOUT_SECONDS = 300


class ManimRenderer:
    """Renders a generated ManimGL scene Python file into an MP4 video."""

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

        logger.info("[render] Scene file: %s", scene_py)
        logger.info("[render] Class name: %s", class_name)
        logger.info("[render] Output directory: %s", output_dir)

        # Read and log the generated scene source
        try:
            source = scene_py.read_text()
            logger.info("[render] Scene source (%d chars):\n%s", len(source), source[:1000])
        except Exception as e:
            logger.warning("[render] Could not read scene file: %s", e)

        # Build command - skip xvfb-run on macOS (not needed, not available)
        cmd = []
        if platform.system() == "Linux" and shutil.which("xvfb-run"):
            cmd.extend(["xvfb-run", "-a"])
            logger.info("[render] Using xvfb-run for headless rendering")
        else:
            logger.info("[render] Running ManimGL directly (platform: %s)", platform.system())

        # Find manimgl executable
        manimgl_path = shutil.which("manimgl")
        if not manimgl_path:
            raise RuntimeError(
                "manimgl executable not found. "
                "Make sure manimgl is installed: pip install manimgl"
            )
        # `which` may return a relative path (e.g. ".venv/bin/manimgl").
        # Rendering runs from a temp scene directory, so force absolute.
        manimgl_exec = Path(manimgl_path).expanduser()
        if not manimgl_exec.is_absolute():
            manimgl_exec = (Path.cwd() / manimgl_exec).resolve()
        if not manimgl_exec.exists():
            raise RuntimeError(
                f"manimgl executable path does not exist: {manimgl_exec}"
            )
        logger.info("[render] ManimGL executable: %s", manimgl_exec)

        cmd.extend([
            str(manimgl_exec),
            str(scene_py),
            class_name,
            "-o",
            "--file_name", class_name,
            "--video_dir", str(output_dir),
        ])

        logger.info("[render] Running command: %s", " ".join(cmd))

        # Ensure LaTeX binaries (MacTeX) are on the PATH for the subprocess
        env = os.environ.copy()
        tex_bin = "/Library/TeX/texbin"
        if tex_bin not in env.get("PATH", ""):
            env["PATH"] = tex_bin + ":" + env.get("PATH", "")

        # On macOS, suppress manimgl's auto-open of rendered files.
        # ManimGL's -o flag writes to file AND calls `open <file>` afterward.
        # We inject a no-op `open` script at the front of PATH so that call
        # does nothing, while the real rendering still works.
        noop_dir = None
        if platform.system() == "Darwin":
            noop_dir = Path(tempfile.mkdtemp(prefix="jestify_noop_"))
            noop_open = noop_dir / "open"
            noop_open.write_text("#!/bin/sh\nexit 0\n")
            noop_open.chmod(noop_open.stat().st_mode | stat.S_IEXEC)
            env["PATH"] = str(noop_dir) + ":" + env["PATH"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(scene_py.parent),
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            logger.error("[render] TIMEOUT after %ds for %s::%s", self._timeout, scene_py_path, class_name)
            raise RuntimeError(
                f"ManimGL render timed out after {self._timeout}s "
                f"for {scene_py_path}::{class_name}"
            ) from exc
        finally:
            if noop_dir and noop_dir.exists():
                shutil.rmtree(noop_dir, ignore_errors=True)

        logger.info("[render] Exit code: %d", result.returncode)

        if result.stdout:
            logger.info("[render] stdout:\n%s", result.stdout[:2000])
        if result.stderr:
            logger.info("[render] stderr:\n%s", result.stderr[-4000:])

        if result.returncode != 0:
            logger.error("[render] FAILED for %s::%s (exit %d)", scene_py_path, class_name, result.returncode)
            raise RuntimeError(
                f"ManimGL render failed (exit {result.returncode}) "
                f"for {scene_py_path}::{class_name}:\n{result.stderr[-4000:]}"
            )

        # Locate the output file
        mp4_path = self._find_output_mp4(output_dir, class_name)
        logger.info("[render] SUCCESS: %s -> %s", class_name, mp4_path)
        return mp4_path

    @staticmethod
    def _find_output_mp4(output_dir: Path, class_name: str) -> str:
        """Search the output directory for the rendered MP4 file."""
        logger.info("[render] Searching for output MP4 in: %s", output_dir)

        # List all files in output_dir for debugging
        if output_dir.exists():
            all_files = list(output_dir.rglob("*"))
            logger.info("[render] Files in output dir: %s", [str(f) for f in all_files[:20]])
        else:
            logger.warning("[render] Output directory does not exist: %s", output_dir)

        # ManimGL typically outputs to <video_dir>/1080p30/<ClassName>.mp4
        candidates = list(output_dir.rglob(f"{class_name}.mp4"))
        if candidates:
            logger.info("[render] Found exact match: %s", candidates[0])
            return str(candidates[0])

        # Fallback: return any mp4 found
        all_mp4s = list(output_dir.rglob("*.mp4"))
        if all_mp4s:
            logger.info("[render] Using fallback MP4: %s", all_mp4s[0])
            return str(all_mp4s[0])

        raise FileNotFoundError(
            f"No MP4 output found in {output_dir} for class {class_name}"
        )

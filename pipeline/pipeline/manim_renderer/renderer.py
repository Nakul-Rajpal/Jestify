"""Renders Manim scene files into MP4 clips.

Supports both Manim Community Edition (preferred) and ManimGL as fallback.
"""

import logging
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_RENDER_TIMEOUT_SECONDS = 300


class ManimRenderer:
    """Renders a Manim scene Python file into an MP4 video."""

    def __init__(self, timeout: int = _RENDER_TIMEOUT_SECONDS):
        self._timeout = timeout
        self._engine = self._detect_engine()
        self._check_dependencies()
        self._texmfcnf, self._texmfdist = self._find_tex_paths()
        if self._texmfcnf:
            logger.info("[render] TEXMFCNF: %s", self._texmfcnf)
            os.environ["TEXMFCNF"] = self._texmfcnf
        else:
            logger.warning("[render] Could not find texmf.cnf — MathTex may fail")
        if self._texmfdist:
            logger.info("[render] TEXMFDIST: %s", self._texmfdist)
            os.environ["TEXMFDIST"] = self._texmfdist

    def _detect_engine(self) -> str:
        """Detect which Manim engine is available (prefer CE)."""
        manim_path = shutil.which("manim")
        manimgl_path = shutil.which("manimgl")

        if manim_path:
            logger.info("[render] Detected ManimCE: %s", manim_path)
            return "ce"
        elif manimgl_path:
            logger.info("[render] Detected ManimGL: %s", manimgl_path)
            return "gl"
        else:
            raise RuntimeError(
                "Neither 'manim' (Community Edition) nor 'manimgl' found on PATH. "
                "Install one: pip install manim  OR  pip install manimgl"
            )

    def _check_dependencies(self) -> None:
        """Verify required system binaries are available."""
        logger.info("[render] Checking system dependencies...")
        for binary in ("ffmpeg", "ffprobe"):
            path = shutil.which(binary)
            if path:
                logger.info("[render]   %s -> %s", binary, path)
            else:
                logger.error("[render]   %s -> MISSING", binary)
                raise RuntimeError(
                    f"Missing required dependency: {binary}. "
                    f"Install: brew install ffmpeg (macOS) / apt install ffmpeg (Linux)"
                )
        logger.info("[render] All dependencies OK (engine=%s)", self._engine)

    def render_scene(self, scene_py_path: str, class_name: str) -> str:
        """Render a Manim scene and return the path to the output MP4."""
        scene_py = Path(scene_py_path).resolve()
        output_dir = scene_py.parent / "media"

        logger.info("[render] ┌─ Rendering %s", class_name)
        logger.info("[render] │  Scene file: %s", scene_py)
        logger.info("[render] │  Engine: %s", self._engine)
        logger.info("[render] │  Output dir: %s", output_dir)
        logger.info("[render] │  Timeout: %ds", self._timeout)

        if not scene_py.exists():
            logger.error("[render] │  Scene file does not exist!")
            raise FileNotFoundError(f"Scene file not found: {scene_py}")

        source = scene_py.read_text()
        logger.info("[render] │  Source: %d chars, %d lines", len(source), source.count("\n") + 1)
        logger.info("[render] │  Full source:\n%s", source)

        if self._engine == "ce":
            cmd = self._build_ce_command(scene_py, class_name, output_dir)
        else:
            cmd = self._build_gl_command(scene_py, class_name, output_dir)

        logger.info("[render] │  Command: %s", " ".join(cmd))
        logger.info("[render] │  Working dir: %s", scene_py.parent)

        env = os.environ.copy()
        if self._texmfcnf:
            env["TEXMFCNF"] = self._texmfcnf
        if self._texmfdist:
            env["TEXMFDIST"] = self._texmfdist
        logger.info("[render] │  TEXMFCNF=%s TEXMFDIST=%s", self._texmfcnf, self._texmfdist)

        t0 = time.perf_counter()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(scene_py.parent),
                env=env,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - t0
            logger.error("[render] └─ TIMEOUT after %.1fs for %s", elapsed, class_name)
            raise RuntimeError(
                f"Manim render timed out after {self._timeout}s for {class_name}"
            )

        elapsed = time.perf_counter() - t0
        logger.info("[render] │  Exit code: %d (%.1fs)", result.returncode, elapsed)

        if result.stdout.strip():
            logger.info("[render] │  stdout:\n%s", result.stdout.strip()[-2000:])
        if result.stderr.strip():
            level = logging.ERROR if result.returncode != 0 else logging.INFO
            logger.log(level, "[render] │  stderr:\n%s", result.stderr.strip()[-2000:])

        if result.returncode != 0:
            logger.error("[render] └─ FAILED %s (exit %d, %.1fs)", class_name, result.returncode, elapsed)
            raise RuntimeError(
                f"Manim render failed (exit {result.returncode}) for {class_name}:\n"
                f"{result.stderr[-3000:]}"
            )

        mp4_path = self._find_output_mp4(output_dir, class_name)
        mp4_size = Path(mp4_path).stat().st_size
        logger.info(
            "[render] └─ SUCCESS %s -> %s (%.1f MB, %.1fs)",
            class_name, mp4_path, mp4_size / (1024 * 1024), elapsed,
        )
        return mp4_path

    def _build_ce_command(self, scene_py: Path, class_name: str, output_dir: Path) -> list[str]:
        """Build command for Manim Community Edition."""
        manim_path = shutil.which("manim")
        cmd = []
        if platform.system() == "Linux" and shutil.which("xvfb-run"):
            cmd.extend(["xvfb-run", "-a"])
        cmd.extend([
            manim_path,
            "render",
            str(scene_py),
            class_name,
            "-qm",
            "--format=mp4",
            f"--media_dir={output_dir}",
        ])
        return cmd

    def _build_gl_command(self, scene_py: Path, class_name: str, output_dir: Path) -> list[str]:
        """Build command for ManimGL (fallback)."""
        manimgl_path = shutil.which("manimgl")
        cmd = []
        if platform.system() == "Linux" and shutil.which("xvfb-run"):
            cmd.extend(["xvfb-run", "-a"])
        cmd.extend([
            manimgl_path,
            str(scene_py),
            class_name,
            "-o",
            "--file_name", class_name,
            "--video_dir", str(output_dir),
        ])
        return cmd

    @staticmethod
    def _find_tex_paths() -> tuple[str | None, str | None]:
        """Locate texmf.cnf dir (TEXMFCNF) and texmf-dist dir (TEXMFDIST).

        dvisvgm needs TEXMFCNF to find texmf.cnf and TEXMFDIST to find
        PostScript headers (tex.pro, etc.) and font map files.
        """
        texmfcnf = os.environ.get("TEXMFCNF")
        texmfdist = os.environ.get("TEXMFDIST")
        if texmfcnf and texmfdist:
            return texmfcnf, texmfdist

        try:
            result = subprocess.run(
                ["kpsewhich", "texmf.cnf"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                cnf_dir = Path(result.stdout.strip()).parent
                texmfcnf = texmfcnf or (str(cnf_dir) + ":")
                texmfdist = texmfdist or str(cnf_dir.parent)
                return texmfcnf, texmfdist
        except Exception:
            pass
        for candidate in Path("/opt/homebrew/Cellar/texlive").glob("*/share/texmf-dist/web2c"):
            if (candidate / "texmf.cnf").exists():
                texmfcnf = texmfcnf or (str(candidate) + ":")
                texmfdist = texmfdist or str(candidate.parent)
                return texmfcnf, texmfdist
        return texmfcnf, texmfdist

    @staticmethod
    def _find_output_mp4(output_dir: Path, class_name: str) -> str:
        """Search the output directory for the rendered MP4 file."""
        logger.info("[render] │  Searching for MP4 in: %s", output_dir)

        if output_dir.exists():
            all_files = sorted(output_dir.rglob("*.mp4"))
            logger.info("[render] │  MP4 files found: %s", [str(f) for f in all_files])
        else:
            logger.error("[render] │  Output directory does not exist: %s", output_dir)

        candidates = list(output_dir.rglob(f"{class_name}.mp4"))
        if candidates:
            logger.info("[render] │  Exact match: %s", candidates[0])
            return str(candidates[0])

        all_mp4s = list(output_dir.rglob("*.mp4"))
        if all_mp4s:
            best = max(all_mp4s, key=lambda f: f.stat().st_mtime)
            logger.warning("[render] │  No exact match, using newest MP4: %s", best)
            return str(best)

        all_files = list(output_dir.rglob("*")) if output_dir.exists() else []
        raise FileNotFoundError(
            f"No MP4 output found in {output_dir} for class {class_name}. "
            f"Files present: {[str(f) for f in all_files]}"
        )

"""Renders Manim scene files into MP4 clips.

Uses ManimCE (Community Edition) as the primary engine.  A GL→CE
compatibility patch auto-corrects common ManimGL patterns before render.
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
        self._ensure_texlive_on_path()
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

    @staticmethod
    def _ensure_texlive_on_path():
        """Add TeX Live bin directory to PATH if not already present."""
        tex_bin_dirs = [
            "/usr/local/texlive/2025/bin/universal-darwin",
            "/usr/local/texlive/2024/bin/universal-darwin",
            "/usr/local/texlive/2025/bin/x86_64-linux",
            "/usr/local/texlive/2024/bin/x86_64-linux",
            "/Library/TeX/texbin",
        ]
        current_path = os.environ.get("PATH", "")
        for d in tex_bin_dirs:
            if Path(d).is_dir() and d not in current_path:
                os.environ["PATH"] = d + ":" + current_path
                current_path = os.environ["PATH"]
                logger.info("[render] Added TeX Live to PATH: %s", d)
                break

    def _detect_engine(self) -> str:
        """Detect which Manim engine is available (prefer ManimCE)."""
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
                "Install: pip install manim  (recommended) OR  pip install manimgl"
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

        # When running under ManimCE, rewrite ManimGL-specific code
        if self._engine == "ce":
            source = self._patch_gl_to_ce(source)
            scene_py.write_text(source, encoding="utf-8")
            logger.info("[render] │  Patched source for ManimCE compatibility")

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
            clean_err = self._extract_traceback(result.stderr)
            logger.error("[render] └─ FAILED %s (exit %d, %.1fs)", class_name, result.returncode, elapsed)
            logger.error("[render]   Traceback:\n%s", clean_err)
            raise RuntimeError(
                f"Manim render failed (exit {result.returncode}) for {class_name}:\n"
                f"{clean_err[-3000:]}"
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
            "-w",
            "--file_name", class_name,
            "--video_dir", str(output_dir),
            "-r", "1920x1080",
            "-c", "#000000",
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
        # Check /usr/local/texlive (MacTeX / manual TeX Live installs)
        for year in ("2025", "2024", "2023"):
            web2c = Path(f"/usr/local/texlive/{year}/texmf-dist/web2c")
            if (web2c / "texmf.cnf").exists():
                texmfcnf = texmfcnf or (str(web2c) + ":")
                texmfdist = texmfdist or str(web2c.parent)
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

    @staticmethod
    def _extract_traceback(stderr: str) -> str:
        """Extract the Python traceback from Manim stderr, ignoring progress bars."""
        lines = stderr.split("\n")
        tb_start = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("Traceback (most recent call last)"):
                tb_start = i
        if tb_start >= 0:
            return "\n".join(lines[tb_start:]).strip()
        return stderr.strip()[-500:]

    @staticmethod
    def _patch_gl_to_ce(source: str) -> str:
        """Rewrite ManimGL-specific code to work with ManimCE.

        This is a safety net — the LLM prompt already targets ManimCE, but if
        any GL patterns slip through, this patch fixes them before render.
        """
        import re as _re

        # ── Imports ──────────────────────────────────────────────────────
        source = source.replace("from manimlib import *", "from manim import *")
        source = source.replace("from manimlib import ", "from manim import ")

        # Ensure numpy import (many scenes use np)
        if "import numpy" not in source:
            source = source.replace(
                "from manim import *",
                "from manim import *\nimport numpy as np",
                1,
            )

        # ── Animation renames (GL → CE) ─────────────────────────────────
        source = _re.sub(r'\bShowCreation\(', 'Create(', source)
        source = _re.sub(r'\bUncreate\(', 'Unwrite(', source)
        source = _re.sub(r'\bWiggleOutThenIn\(', 'Wiggle(', source)

        # ── axes.get_graph() → axes.plot() ──────────────────────────────
        source = _re.sub(r'\.get_graph\(', '.plot(', source)

        # ── Remove ManimGL-specific self.camera.background_color lines ──
        # ManimCE handles background via config or Scene defaults
        source = _re.sub(
            r'^[ \t]*self\.camera\.background_color\s*=\s*\w+\s*\n?',
            '',
            source,
            flags=_re.MULTILINE,
        )

        # ── Enforce minimum font_size ────────────────────────────────────
        def _floor_fontsize(m: _re.Match) -> str:
            fs = int(m.group(1))
            return f"font_size={max(fs, 24)}"

        source = _re.sub(r'font_size\s*=\s*(\d+)', _floor_fontsize, source)

        # ── Enforce minimum .scale() on text ─────────────────────────────
        def _floor_scale(m: _re.Match) -> str:
            s = float(m.group(1))
            return f".scale({max(s, 0.8)})"

        source = _re.sub(r'\.scale\(\s*(0\.\d+)\s*\)', _floor_scale, source)

        # ── Remove plugin imports (from manim_* import ...) ──────────────
        source = _re.sub(r'^from\s+manim_\w+\s+import\s+.*$', '# removed plugin import', source, flags=_re.MULTILINE)

        # ── Guard unguarded lambda division: 1/x → safe version ──────────
        def _guard_division(m: _re.Match) -> str:
            var = m.group(1)
            expr = m.group(2)
            return f'lambda {var}: ({expr}) if abs({var}) > 0.01 else 0'

        source = _re.sub(
            r'lambda\s+(\w)\s*:\s*((?:[^,\n]*/\s*\1)(?:[^,\n]*))',
            _guard_division,
            source,
        )

        # ── LAYOUT ENFORCEMENT ───────────────────────────────────────────

        # Cap Text/MathTex width after assignment:
        #   var = Text(...)  →  var = Text(...)\n  var.set(width=min(var.width, 10.0))
        def _inject_text_width_cap(m: _re.Match) -> str:
            indent = m.group(1)
            var = m.group(2)
            rest = m.group(3)
            line = f"{indent}{var} = {rest}"
            # Don't double-inject if already capped
            if "set_width" not in rest and "set(width" not in rest:
                line += f"\n{indent}{var}.set(width=min({var}.width, 10.0))"
            return line

        source = _re.sub(
            r'^([ \t]+)(\w+)\s*=\s*((?:Text|MathTex)\s*\([^)]*\)(?:\.[a-z_]+\([^)]*\))*)\s*$',
            _inject_text_width_cap,
            source,
            flags=_re.MULTILINE,
        )

        # Cap VGroup height after .arrange():
        #   group.arrange(DOWN, ...)  →  group.arrange(DOWN, ...)\n  group.set(height=min(group.height, 5.5))
        def _inject_vgroup_height_cap(m: _re.Match) -> str:
            indent = m.group(1)
            var = m.group(2)
            arrange_call = m.group(3)
            line = f"{indent}{var}{arrange_call}"
            if "set_height" not in arrange_call and "set(height" not in arrange_call:
                line += f"\n{indent}if {var}.height > 5.5: {var}.set(height=5.5)"
            return line

        source = _re.sub(
            r'^([ \t]+)(\w+)(\.arrange\([^)]*\)(?:\.[a-z_]+\([^)]*\))*)\s*$',
            _inject_vgroup_height_cap,
            source,
            flags=_re.MULTILINE,
        )

        # Inject Axes x_length/y_length if missing
        def _inject_axes_sizing(m: _re.Match) -> str:
            full = m.group(0)
            if "x_length" not in full and "y_length" not in full:
                # Insert before the closing paren
                full = _re.sub(
                    r'\)\s*$',
                    ', x_length=10, y_length=5)',
                    full,
                )
            return full

        source = _re.sub(
            r'Axes\([^)]*\)',
            _inject_axes_sizing,
            source,
        )

        # Replace .to_edge(UP) on title-like variables with .move_to(UP * 3.2)
        source = _re.sub(
            r'(title\w*)\.to_edge\(\s*UP\s*(?:,\s*buff\s*=\s*[\d.]+)?\s*\)',
            r'\1.move_to(UP * 3.2)',
            source,
        )

        # ── Inject final FadeOut if construct() doesn't end with one ─────
        if 'def construct(self)' in source and 'FadeOut(m) for m in self.mobjects' not in source:
            source = source.rstrip()
            indent = "        "
            source += (
                f"\n{indent}self.play(*[FadeOut(m) for m in self.mobjects], run_time=1.5)"
                f"\n{indent}self.wait(1)\n"
            )

        return source

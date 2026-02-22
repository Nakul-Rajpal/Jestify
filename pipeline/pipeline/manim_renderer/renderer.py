"""Renders Manim scene files into MP4 clips.

Uses ManimGL (3Blue1Brown's fork) as the primary engine.  A CE→GL
compatibility patch auto-corrects common ManimCE patterns before render.
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
        """Detect which Manim engine is available (prefer ManimGL)."""
        manimgl_path = shutil.which("manimgl")
        manim_path = shutil.which("manim")

        if manimgl_path:
            logger.info("[render] Detected ManimGL: %s", manimgl_path)
            return "gl"
        elif manim_path:
            logger.info("[render] Detected ManimCE: %s", manim_path)
            return "ce"
        else:
            raise RuntimeError(
                "Neither 'manimgl' nor 'manim' (Community Edition) found on PATH. "
                "Install: pip install manimgl  (recommended) OR  pip install manim"
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

        # When running under ManimGL, rewrite ManimCE-specific code
        if self._engine == "gl":
            source = self._patch_ce_to_gl(source)
            scene_py.write_text(source, encoding="utf-8")
            logger.info("[render] │  Patched source for ManimGL compatibility")

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
        if self._engine == "gl":
            env["DISPLAY"] = ""
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
        """Build command for ManimGL."""
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
        """Extract the Python traceback from ManimGL stderr, ignoring progress bars."""
        lines = stderr.split("\n")
        tb_start = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("Traceback (most recent call last)"):
                tb_start = i
        if tb_start >= 0:
            return "\n".join(lines[tb_start:]).strip()
        return stderr.strip()[-500:]

    @staticmethod
    def _patch_ce_to_gl(source: str) -> str:
        """Rewrite ManimCE-specific code to work with ManimGL.

        This is a safety net — the LLM prompt already targets ManimGL, but if
        any CE patterns slip through, this patch fixes them before render.
        """
        import re as _re

        # ── Imports ──────────────────────────────────────────────────────
        source = source.replace("from manim import *", "from manimlib import *")
        source = source.replace("from manim import ", "from manimlib import ")

        # Ensure numpy import (many scenes use np)
        if "import numpy" not in source:
            source = source.replace(
                "from manimlib import *",
                "from manimlib import *\nimport numpy as np",
                1,
            )

        # ── Animation renames (CE → GL) ─────────────────────────────────
        source = _re.sub(r'\bCreate\(', 'ShowCreation(', source)
        source = _re.sub(r'\bCircumscribe\(', 'Indicate(', source)
        source = _re.sub(r'\bUnwrite\(', 'Uncreate(', source)
        source = _re.sub(r'\bWiggle\(', 'WiggleOutThenIn(', source)

        # ── MathTex → Tex ────────────────────────────────────────────────
        source = _re.sub(r'\bMathTex\(', 'Tex(', source)

        # ── axes.plot() → axes.get_graph() ───────────────────────────────
        source = _re.sub(r'\.plot\(', '.get_graph(', source)

        # ── Strip x_length / y_length from Axes() ───────────────────────
        # ManimGL's Axes doesn't accept these; it uses x_range/y_range only.
        source = _re.sub(r',\s*x_length\s*=\s*[\d.]+', '', source)
        source = _re.sub(r',\s*y_length\s*=\s*[\d.]+', '', source)
        source = _re.sub(r'x_length\s*=\s*[\d.]+\s*,\s*', '', source)
        source = _re.sub(r'y_length\s*=\s*[\d.]+\s*,\s*', '', source)

        # ── Strip tips=False from Axes() (not supported in ManimGL) ─────
        source = _re.sub(r',\s*tips\s*=\s*(?:True|False)', '', source)
        source = _re.sub(r'tips\s*=\s*(?:True|False)\s*,\s*', '', source)

        # ── Fix Tex() constructor kwargs ─────────────────────────────────
        # ManimGL's Tex() doesn't accept color= or font_size=.
        # Convert: Tex(r"...", color=BLUE) → Tex(r"...").set_color(BLUE)
        # Convert: Tex(r"...", font_size=N) → Tex(r"...").scale(N/36)
        def _fix_tex_kwargs(m: _re.Match) -> str:
            prefix = m.group(1)  # Tex( or TexText(
            content = m.group(2)  # everything inside parens

            color_match = _re.search(r',\s*color\s*=\s*([A-Z_]+)', content)
            fontsize_match = _re.search(r',\s*font_size\s*=\s*(\d+)', content)

            # Remove the kwargs from constructor
            cleaned = _re.sub(r',\s*color\s*=\s*[A-Z_]+', '', content)
            cleaned = _re.sub(r',\s*font_size\s*=\s*\d+', '', cleaned)

            result = f"{prefix}{cleaned})"
            if color_match:
                result += f".set_color({color_match.group(1)})"
            if fontsize_match:
                fs = max(int(fontsize_match.group(1)), 24)
                scale = round(fs / 36, 2)
                if scale != 1.0:
                    result += f".scale({scale})"
            return result

        source = _re.sub(
            r'((?:Tex|TexText)\s*\()([^)]*(?:color\s*=|font_size\s*=)[^)]*)\)',
            _fix_tex_kwargs,
            source,
        )

        # ── Enforce minimum font_size ────────────────────────────────────
        # Replace any font_size below 24 with 24
        def _floor_fontsize(m: _re.Match) -> str:
            fs = int(m.group(1))
            return f"font_size={max(fs, 24)}"

        source = _re.sub(r'font_size\s*=\s*(\d+)', _floor_fontsize, source)

        # ── Enforce minimum .scale() on text ─────────────────────────────
        def _floor_scale(m: _re.Match) -> str:
            s = float(m.group(1))
            return f".scale({max(s, 0.8)})"

        source = _re.sub(r'\.scale\(\s*(0\.\d+)\s*\)', _floor_scale, source)

        # ── Strip axis_config={...} from Axes() ─────────────────────────
        # ManimGL Axes doesn't accept axis_config dicts
        # Handle nested dicts with a non-greedy match up to the matching }
        source = _re.sub(
            r',\s*axis_config\s*=\s*\{[^}]*\}', '', source
        )
        source = _re.sub(
            r'axis_config\s*=\s*\{[^}]*\}\s*,?\s*', '', source
        )

        # ── Strip include_numbers / include_tip from Axes() ─────────────
        source = _re.sub(r',\s*include_numbers\s*=\s*(?:True|False)', '', source)
        source = _re.sub(r'include_numbers\s*=\s*(?:True|False)\s*,?\s*', '', source)
        source = _re.sub(r',\s*include_tip\s*=\s*(?:True|False)', '', source)
        source = _re.sub(r'include_tip\s*=\s*(?:True|False)\s*,?\s*', '', source)

        # ── Replace .get_axis_labels() with VGroup() (preserve indentation) ─
        source = _re.sub(
            r'^([ \t]*\w+\s*=\s*)\w+\.get_axis_labels\([^)]*\)',
            r'\1VGroup()',
            source,
            flags=_re.MULTILINE,
        )

        # ── Strip .add_coordinates() calls (replace line with pass) ──────
        source = _re.sub(
            r'^([ \t]*)\w+\.add_coordinates\([^)]*\)',
            r'\1pass  # add_coordinates removed',
            source,
            flags=_re.MULTILINE,
        )

        # ── Replace axes.get_area() with VMobject() (preserve indentation) ─
        source = _re.sub(
            r'^([ \t]*\w+\s*=\s*)\w+\.get_area\([^)]*\)',
            r'\1VMobject()',
            source,
            flags=_re.MULTILINE,
        )

        # ── Enforce Axes scaling so graphs fit within the frame ──────────
        # Find `var = Axes(...)` lines and inject .set_height/.set_width
        # if the code doesn't already scale them.
        def _inject_axes_scaling(m: _re.Match) -> str:
            indent = m.group(1)
            var_name = m.group(2)
            axes_call = m.group(3)
            rest_of_line = m.group(4) if m.group(4) else ""
            line = f"{indent}{var_name} = {axes_call}{rest_of_line}"
            if "set_height" not in rest_of_line and "set_width" not in rest_of_line:
                line += f"\n{indent}{var_name}.set_height(5.0).set_width(10.0)"
            return line

        source = _re.sub(
            r'^([ \t]*)(\w+)\s*=\s*(Axes\([^)]*\))(.*?)$',
            _inject_axes_scaling,
            source,
            flags=_re.MULTILINE,
        )

        # ── Remove plugin imports (from manim_* import ...) ──────────────
        source = _re.sub(r'^from\s+manim_\w+\s+import\s+.*$', '# removed plugin import', source, flags=_re.MULTILINE)

        # ── Remove always_redraw() lines entirely ─────────────────────────
        # always_redraw is not in ManimGL; comment out the entire line
        source = _re.sub(
            r'^([ \t]*)(\w+\s*=\s*always_redraw\s*\(.*\))',
            r'\1pass  # removed: \2',
            source,
            flags=_re.MULTILINE,
        )

        # ── Strip num_decimal_places from DecimalNumber ──────────────────
        source = _re.sub(r',\s*num_decimal_places\s*=\s*\d+', '', source)
        source = _re.sub(r'num_decimal_places\s*=\s*\d+\s*,\s*', '', source)

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

        # ── Inject self.camera.background_color = BLACK if missing ────────
        if 'def construct(self)' in source and 'background_color' not in source:
            source = _re.sub(
                r'(def construct\(self\):\s*\n)',
                r'\1        self.camera.background_color = BLACK\n',
                source,
                count=1,
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

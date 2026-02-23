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
        self._fps = self._env_int("MANIM_FPS", 12, min_value=8, max_value=24)
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
    def _env_int(name: str, default: int, min_value: int = 1, max_value: int = 10_000) -> int:
        try:
            value = int(os.getenv(name, str(default)))
            return max(min_value, min(max_value, value))
        except Exception:
            return default

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
        logger.info("[render] │  FPS: %d", self._fps)

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
            "-ql",
            "--fps", str(self._fps),
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
                cnf_path = Path(result.stdout.strip())
                cnf_dir = cnf_path.parent
                texmfcnf = texmfcnf or (str(cnf_dir) + ":")
                # Look for texmf-dist alongside or under cnf_dir
                texmf_dist_candidate = cnf_dir / "texmf-dist"
                if texmf_dist_candidate.is_dir():
                    texmfdist = texmfdist or str(texmf_dist_candidate)
                else:
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

        # ── Nuclear MathTex/Tex → Text monkey-patch ─────────────────────
        # ManimCE internally creates MathTex in dozens of methods (axis
        # labels, graph labels, number lines, etc.).  Patching module
        # namespaces does NOT work because NumberLine.__init__ captures
        # MathTex as a default-parameter value at class-definition time.
        #
        # The fix: patch MathTex.__new__ on the CLASS OBJECT itself.
        # Any code that instantiates MathTex (even via the captured default)
        # calls __new__, which now returns a Text object.  Since the
        # returned object is not a MathTex instance, Python skips __init__
        # entirely — no LaTeX compilation ever runs.
        if "_tex_shim_new" not in source:
            _shim = (
                '\n# ── MathTex/Tex → Text shim (LaTeX not available) ──\n'
                'import re as _re_mp\n'
                'import manim.mobject.text.tex_mobject as _texm\n'
                'def _clean_tex(combined):\n'
                '    combined = _re_mp.sub(r"\\\\frac\\{([^}]*)\\}\\{([^}]*)\\}", r"(\\1)/(\\2)", combined)\n'
                '    combined = _re_mp.sub(r"\\\\sqrt\\{([^}]*)\\}", "\\u221a(\\\\1)", combined)\n'
                '    for _cmd, _sym in [("cdot","\\u00b7"),("times","\\u00d7"),("pm","\\u00b1"),'
                '("infty","\\u221e"),("pi","\\u03c0"),("sum","\\u03a3"),("int","\\u222b"),'
                '("rightarrow","\\u2192"),("Rightarrow","\\u21d2"),("leq","\\u2264"),'
                '("geq","\\u2265"),("neq","\\u2260"),("approx","\\u2248"),'
                '("alpha","\\u03b1"),("beta","\\u03b2"),("gamma","\\u03b3"),'
                '("theta","\\u03b8"),("Delta","\\u0394"),("lambda","\\u03bb"),'
                '("sigma","\\u03c3"),("omega","\\u03c9"),("mu","\\u03bc"),("epsilon","\\u03b5")]:\n'
                '        combined = combined.replace("\\\\" + _cmd, _sym)\n'
                '    combined = _re_mp.sub(r"\\\\[a-zA-Z]+\\{([^}]*)\\}", r"\\1", combined)\n'
                '    combined = _re_mp.sub(r"\\\\[a-zA-Z]+", "", combined)\n'
                '    combined = _re_mp.sub(r"[{}]", "", combined)\n'
                '    for _s, _r in [("^2","\\u00b2"),("^3","\\u00b3"),("^n","\\u207f"),'
                '("^{-1}","\\u207b\\u00b9"),("^0","\\u2070"),("^4","\\u2074")]:\n'
                '        combined = combined.replace(_s, _r)\n'
                '    for _s, _r in [("_0","\\u2080"),("_1","\\u2081"),("_2","\\u2082"),'
                '("_3","\\u2083"),("_n","\\u2099"),("_i","\\u1d62"),("_x","\\u2093")]:\n'
                '        combined = combined.replace(_s, _r)\n'
                '    combined = _re_mp.sub(r"\\s+", " ", combined).strip() or "\\u2026"\n'
                '    return combined\n'
                '\n'
                'def _tex_shim_new(cls, *args, **kwargs):\n'
                '    """Return a Text object instead of compiling LaTeX."""\n'
                '    tex_strings = [a for a in args if isinstance(a, (str, int, float))]\n'
                '    if not tex_strings:\n'
                '        tex_strings = ["\\u2026"]\n'
                '    combined = _clean_tex(" ".join(str(s) for s in tex_strings))\n'
                '    safe_kw = {k: v for k, v in kwargs.items()\n'
                '               if k in ("color","font_size","weight","slant")}\n'
                '    safe_kw.setdefault("font_size", 36)\n'
                '    return Text(combined, **safe_kw)\n'
                '\n'
                '# Patch the CLASS OBJECTS so even default-parameter references work\n'
                '_texm.MathTex.__new__ = staticmethod(_tex_shim_new)\n'
                'if hasattr(_texm, "SingleStringMathTex"):\n'
                '    _texm.SingleStringMathTex.__new__ = staticmethod(_tex_shim_new)\n'
                '# Also override names in local scope for any direct calls\n'
                'MathTex = _tex_shim_new\n'
                'Tex = _tex_shim_new\n'
                '# ── end shim ──\n'
            )
            # Insert after the last import line
            import_end = 0
            for i, line in enumerate(source.split('\n')):
                if line.startswith('import ') or line.startswith('from '):
                    import_end = i
            lines = source.split('\n')
            lines.insert(import_end + 1, _shim)
            source = '\n'.join(lines)

        # ── Animation renames (GL → CE) ─────────────────────────────────
        source = _re.sub(r'\bShowCreation\(', 'Create(', source)
        source = _re.sub(r'\bUncreate\(', 'Unwrite(', source)
        source = _re.sub(r'\bWiggleOutThenIn\(', 'Wiggle(', source)

        # ── axes.get_graph() → axes.plot() ──────────────────────────────
        source = _re.sub(r'\.get_graph\(', '.plot(', source)

        # ── Change Scene → MovingCameraScene for camera-follow support ──
        source = _re.sub(
            r'class\s+(\w+)\s*\(\s*Scene\s*\)',
            r'class \1(MovingCameraScene)',
            source,
        )

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
        #   var = Text(...)  →  var = Text(...)\n  var.set(width=min(var.width, 8.5))
        def _inject_text_width_cap(m: _re.Match) -> str:
            indent = m.group(1)
            var = m.group(2)
            rest = m.group(3)
            line = f"{indent}{var} = {rest}"
            # Don't double-inject if already capped
            if "set_width" not in rest and "set(width" not in rest:
                line += f"\n{indent}{var}.set(width=min({var}.width, 8.5))"
            return line

        source = _re.sub(
            r'^([ \t]+)(\w+)\s*=\s*((?:Text|MathTex)\s*\([^)]*\)(?:\.[a-z_]+\([^)]*\))*)\s*$',
            _inject_text_width_cap,
            source,
            flags=_re.MULTILINE,
        )

        # Cap VGroup height after .arrange():
        #   group.arrange(DOWN, ...)  →  group.arrange(DOWN, ...)\n  group.set(height=min(group.height, 4.8))
        def _inject_vgroup_height_cap(m: _re.Match) -> str:
            indent = m.group(1)
            var = m.group(2)
            arrange_call = m.group(3)
            line = f"{indent}{var}{arrange_call}"
            if "set_height" not in arrange_call and "set(height" not in arrange_call:
                line += f"\n{indent}if {var}.height > 4.8: {var}.set(height=4.8)"
            return line

        source = _re.sub(
            r'^([ \t]+)(\w+)(\.arrange\([^)]*\)(?:\.[a-z_]+\([^)]*\))*)\s*$',
            _inject_vgroup_height_cap,
            source,
            flags=_re.MULTILINE,
        )

        # Ensure down-stacked groups have enough vertical breathing room.
        def _raise_arrange_down_buff(m: _re.Match) -> str:
            val = float(m.group(1))
            val = max(val, 0.7)
            return f"arrange(DOWN, buff={val:.2f})"

        source = _re.sub(
            r'arrange\(\s*DOWN\s*,\s*buff\s*=\s*([0-9]*\.?[0-9]+)\s*\)',
            _raise_arrange_down_buff,
            source,
        )
        source = _re.sub(
            r'arrange\(\s*DOWN\s*\)',
            'arrange(DOWN, buff=0.70)',
            source,
        )

        # Keep next_to spacing above a minimum to avoid text collisions.
        def _raise_next_to_buff(m: _re.Match) -> str:
            before = m.group(1)
            val = float(m.group(2))
            val = max(val, 0.45)
            return f"{before}buff={val:.2f}"

        source = _re.sub(
            r'(\.next_to\([^)]*?,\s*[^,)]*?,\s*)buff\s*=\s*([0-9]*\.?[0-9]+)',
            _raise_next_to_buff,
            source,
        )

        # Graph caption safety: if next_to(..., DOWN) is used, enforce a larger
        # buffer so labels don't sit on top of axes/ticks.
        def _raise_next_to_down_buff(m: _re.Match) -> str:
            target = m.group(1)
            raw_buff = m.group(2)
            buff = float(raw_buff) if raw_buff is not None else 0.0
            buff = max(buff, 0.85)
            return f".next_to({target}, DOWN, buff={buff:.2f})"

        source = _re.sub(
            r'\.next_to\(\s*([^,\)]+?)\s*,\s*DOWN\s*(?:,\s*buff\s*=\s*([0-9]*\.?[0-9]+))?\s*\)',
            _raise_next_to_down_buff,
            source,
        )

        # If text is positioned DOWN relative to axes/graph anchors, flip it UP.
        # This prevents narration labels from landing on axis/tick regions.
        def _avoid_axes_down_overlap(m: _re.Match) -> str:
            target = m.group(1).strip()
            raw_buff = m.group(2)
            buff = float(raw_buff) if raw_buff is not None else 0.0
            buff = max(buff, 0.85)
            if "axes" in target or "c2p(" in target:
                return f".next_to({target}, UP, buff={buff:.2f})"
            return f".next_to({target}, DOWN, buff={buff:.2f})"

        source = _re.sub(
            r'\.next_to\(\s*(.+?)\s*,\s*DOWN\s*(?:,\s*buff\s*=\s*([0-9]*\.?[0-9]+))?\s*\)',
            _avoid_axes_down_overlap,
            source,
        )

        # Avoid placing labels/captions too low where they can overlap graph axes.
        def _clamp_deep_down_move(m: _re.Match) -> str:
            val = float(m.group(1))
            if val > 1.9:
                val = 1.9
            return f"move_to(DOWN * {val:.2f})"

        source = _re.sub(
            r'move_to\(\s*DOWN\s*\*\s*([0-9]*\.?[0-9]+)\s*\)',
            _clamp_deep_down_move,
            source,
        )

        # Clamp all DOWN vector magnitudes so large shifts can't drop captions
        # into graph axes or below frame bounds.
        def _clamp_down_vector(m: _re.Match) -> str:
            val = float(m.group(1))
            if val > 1.9:
                val = 1.9
            return f"DOWN * {val:.2f}"

        source = _re.sub(
            r'DOWN\s*\*\s*([0-9]*\.?[0-9]+)',
            _clamp_down_vector,
            source,
        )

        def _raise_down_edge_buff(m: _re.Match) -> str:
            raw = m.group(1)
            val = float(raw) if raw is not None else 0.0
            val = max(val, 1.0)
            return f".to_edge(DOWN, buff={val:.2f})"

        source = _re.sub(
            r'\.to_edge\(\s*DOWN\s*(?:,\s*buff\s*=\s*([0-9]*\.?[0-9]+))?\s*\)',
            _raise_down_edge_buff,
            source,
        )

        # Reserve upper-left for character sprite overlay.
        def _shift_ul_corner(m: _re.Match) -> str:
            raw = m.group(1)
            buff = float(raw) if raw is not None else 0.0
            buff = max(buff, 0.9)
            return f".to_corner(UL, buff={buff:.2f}).shift(RIGHT * 1.2 + DOWN * 0.5)"

        source = _re.sub(
            r'\.to_corner\(\s*UL\s*(?:,\s*buff\s*=\s*([0-9]*\.?[0-9]+))?\s*\)',
            _shift_ul_corner,
            source,
        )

        # Keep hard-left placements away from the sprite region.
        def _raise_left_edge_buff(m: _re.Match) -> str:
            raw = m.group(1)
            buff = float(raw) if raw is not None else 0.0
            buff = max(buff, 1.0)
            return f".to_edge(LEFT, buff={buff:.2f})"

        source = _re.sub(
            r'\.to_edge\(\s*LEFT\s*(?:,\s*buff\s*=\s*([0-9]*\.?[0-9]+))?\s*\)',
            _raise_left_edge_buff,
            source,
        )

        # Lift graph axes slightly so lower captions have breathing room.
        def _lift_axes_from_bottom(m: _re.Match) -> str:
            var = m.group(1)
            val = float(m.group(2))
            val = min(val, 0.15)
            return f"{var}.move_to(DOWN * {val:.2f})"

        source = _re.sub(
            r'((?:axes|ax)\w*)\.move_to\(\s*DOWN\s*\*\s*([0-9]*\.?[0-9]+)\s*\)',
            _lift_axes_from_bottom,
            source,
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

        # ── Convert axis label string args to Text() to avoid hidden MathTex ──
        # ManimCE's get_x_axis_label("x") internally creates MathTex("x")
        # which requires LaTeX. Pass Text() objects instead.
        def _axis_label_to_text(m: _re.Match) -> str:
            method = m.group(1)
            quote = m.group(2)
            label_str = m.group(3)
            return f'{method}(Text("{label_str}", font_size=28)'
        source = _re.sub(
            r'(\.get_[xy]_axis_label)\(\s*(["\'])([^"\']*)\2',
            _axis_label_to_text,
            source,
        )
        # get_axis_labels(x_label="x", y_label="f(x)") → keyword args
        def _axis_labels_kwargs_to_text(m: _re.Match) -> str:
            kw = m.group(1)
            label_str = m.group(3)
            return f'{kw}=Text("{label_str}", font_size=28)'
        source = _re.sub(
            r'([xy]_label)\s*=\s*(["\'])([^"\']*)\2',
            _axis_labels_kwargs_to_text,
            source,
        )
        # get_axis_labels("x", "f(x)") → positional string args
        def _get_axis_labels_positional(m: _re.Match) -> str:
            q1 = m.group(1)
            s1 = m.group(2)
            q2 = m.group(3)
            s2 = m.group(4)
            return f'get_axis_labels(Text("{s1}", font_size=28), Text("{s2}", font_size=28))'
        source = _re.sub(
            r'get_axis_labels\(\s*(["\'])([^"\']*)\1\s*,\s*(["\'])([^"\']*)\3\s*\)',
            _get_axis_labels_positional,
            source,
        )

        # ── get_graph_label: string label arg → Text() ──
        # get_graph_label(graph, "f(x)") — positional 2nd arg
        source = _re.sub(
            r'(\.get_graph_label\(\s*\w[\w.]*\s*,\s*)(["\'])([^"\']*)\2',
            r'\1Text("\3", font_size=28)',
            source,
        )
        # get_graph_label(..., label="f(x)") — keyword arg
        source = _re.sub(
            r'(\.get_graph_label\([^)]*?)label\s*=\s*(["\'])([^"\']*)\2',
            r'\1label=Text("\3", font_size=28)',
            source,
        )

        # ── get_T_label: string label arg → Text() ──
        # get_T_label(x_val, graph, "label") — positional 3rd arg
        source = _re.sub(
            r'(\.get_T_label\(\s*[\w.]+\s*,\s*\w[\w.]*\s*,\s*)(["\'])([^"\']*)\2',
            r'\1Text("\3", font_size=28)',
            source,
        )
        # get_T_label(..., label="label") — keyword arg
        source = _re.sub(
            r'(\.get_T_label\([^)]*?)label\s*=\s*(["\'])([^"\']*)\2',
            r'\1label=Text("\3", font_size=28)',
            source,
        )

        # ── Inject mob size clamping (no camera zoom — zoom caused oscillation) ──
        if '_fit_mob_to_frame' not in source:
            _frame_safety = (
                '\n# ── Auto-frame: clamp oversized mobjects ──\n'
                '_SAFE_MOB_W = 12.0\n'
                '_SAFE_MOB_H = 6.0\n'
                '\n'
                'def _fit_mob_to_frame(mob):\n'
                '    """Scale down any mobject that exceeds safe dimensions."""\n'
                '    try:\n'
                '        if mob.width > _SAFE_MOB_W:\n'
                '            mob.set(width=_SAFE_MOB_W)\n'
                '        if mob.height > _SAFE_MOB_H:\n'
                '            mob.set(height=_SAFE_MOB_H)\n'
                '    except Exception:\n'
                '        pass\n'
                '# ── end auto-frame ──\n'
            )
            _fr_lines = source.split('\n')
            _fr_class_idx = None
            for _fri, _frl in enumerate(_fr_lines):
                if _re.match(r'^class\s+', _frl):
                    _fr_class_idx = _fri
                    break
            if _fr_class_idx is not None:
                _fr_lines.insert(_fr_class_idx, _frame_safety)
                source = '\n'.join(_fr_lines)

        # ── Inject final FadeOut if construct() doesn't end with one ─────
        if 'def construct(self)' in source and 'FadeOut(m) for m in self.mobjects' not in source:
            source = source.rstrip()
            indent = "        "
            source += (
                f"\n{indent}self.play(*[FadeOut(m) for m in self.mobjects], run_time=1.5)"
                f"\n{indent}self.wait(1)\n"
            )

        return source

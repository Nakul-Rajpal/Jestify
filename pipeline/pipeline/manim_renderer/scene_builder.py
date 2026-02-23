"""Generates runnable Manim scene Python files from SceneInstruction data.

Primary approach: use the LLM-generated ``manim_code`` after sanitizing and AST
validation. If generation fails, fall back to *visual* scene templates (not
text-only) so output still contains meaningful animations.
"""

import ast
import logging
import re
from pathlib import Path

from shared.contracts.pipeline_schema import SceneInstruction

logger = logging.getLogger(__name__)


class SceneBuilder:
    """Translates a ``SceneInstruction`` into a runnable Manim scene file."""

    def build_scene_file(
        self, scene: SceneInstruction, output_py_path: str
    ) -> str:
        """Build a ``.py`` scene file and return the Manim class name."""
        logger.info("[scene_builder] ┌─ Building scene file")
        logger.info("[scene_builder] │  Scene index: %d", scene.scene_index)
        logger.info("[scene_builder] │  Scene type: %s", scene.manim_scene_type)
        logger.info("[scene_builder] │  Duration hint: %.0fs", scene.duration_hint_seconds)
        logger.info("[scene_builder] │  Has manim_code: %s", bool(scene.manim_code))
        logger.info("[scene_builder] │  Output: %s", output_py_path)

        if scene.manim_code:
            source, class_name = self._use_llm_code(scene)
        else:
            source, class_name = self._build_fallback(scene)

        Path(output_py_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_py_path).write_text(source, encoding="utf-8")

        logger.info("[scene_builder] │  Class name: %s", class_name)
        logger.info("[scene_builder] │  Source: %d chars, %d lines", len(source), source.count("\n") + 1)
        logger.info("[scene_builder] │  Full source:\n%s", source)
        logger.info("[scene_builder] └─ OK: %s", output_py_path)
        return class_name

    def _use_llm_code(self, scene: SceneInstruction) -> tuple[str, str]:
        """Sanitize and validate LLM-generated ManimCE code."""
        source = scene.manim_code or ""
        logger.info("[scene_builder] │  LLM code: %d chars", len(source))

        source = self._sanitize_code(source)

        # Always convert MathTex/Tex → Text to prevent LaTeX compilation errors.
        # This runs BEFORE AST validation so the resulting code is valid Python.
        source = self._replace_latex_with_text(source)
        source = self._normalize_timing(source, scene.duration_hint_seconds)

        class_name = self._extract_class_name(source)
        if not class_name:
            expected = f"Scene{scene.scene_index:03d}"
            logger.warning("[scene_builder] │  No Scene class found, wrapping in %s", expected)
            source = self._wrap_in_scene_class(source, expected)
            class_name = expected

        if "from manim import" not in source and "from manimlib import" not in source:
            source = "from manim import *\nimport numpy as np\n\n" + source
            logger.info("[scene_builder] │  Added missing 'from manim import *'")

        # Enforce minimum font_size of 24 on all Text/MathTex objects
        source = self._enforce_font_floor(source)

        # Fix unterminated strings before AST validation
        source = self._fix_unterminated_strings(source)

        errors = self._validate_ast(source)
        if errors:
            logger.warning("[scene_builder] │  AST validation issues: %s", errors)
            logger.info("[scene_builder] │  Attempting auto-fix...")
            source = self._auto_fix_code(source)
            # Re-extract class name after patching (import line may have changed)
            patched_class = self._extract_class_name(source)
            if patched_class:
                class_name = patched_class
            errors = self._validate_ast(source)
            if errors:
                logger.error("[scene_builder] │  Auto-fix did not resolve: %s", errors)
                # Raise so the orchestrator retries with LLM code repair
                # instead of silently falling back to a static template.
                raise ValueError(
                    f"LLM-generated code has AST errors after auto-fix: {errors}"
                )
            logger.info("[scene_builder] │  Auto-fix resolved all issues")

        return source, class_name

    @staticmethod
    def _enforce_font_floor(source: str) -> str:
        """Clamp any font_size below 24 up to 24."""
        def _clamp(m: re.Match) -> str:
            fs = int(m.group(1))
            return f"font_size={max(fs, 24)}"
        return re.sub(r'font_size\s*=\s*(\d+)', _clamp, source)

    @staticmethod
    def _normalize_timing(source: str, target_seconds: float) -> str:
        """Scale literal run_time/self.wait durations down to match target scene length."""
        run_matches = list(re.finditer(r'run_time\s*=\s*(\d+(?:\.\d+)?)', source))
        wait_matches = list(re.finditer(r'self\.wait\(\s*(\d+(?:\.\d+)?)\s*\)', source))
        if not run_matches and not wait_matches:
            return source

        run_total = sum(float(m.group(1)) for m in run_matches)
        wait_total = sum(float(m.group(1)) for m in wait_matches)
        estimated_total = run_total + wait_total
        target = max(6.0, float(target_seconds or 0))

        if estimated_total <= 0 or estimated_total <= target * 1.15:
            return source

        scale = max(0.25, min(1.0, target / estimated_total))

        def _fmt(value: float) -> str:
            s = f"{value:.2f}"
            return s.rstrip("0").rstrip(".")

        def _scale_run(m: re.Match) -> str:
            current = float(m.group(1))
            scaled = max(0.3, min(1.5, current * scale))
            return f"run_time={_fmt(scaled)}"

        def _scale_wait(m: re.Match) -> str:
            current = float(m.group(1))
            scaled = max(0.15, min(1.0, current * scale))
            return f"self.wait({_fmt(scaled)})"

        source = re.sub(r'run_time\s*=\s*(\d+(?:\.\d+)?)', _scale_run, source)
        source = re.sub(r'self\.wait\(\s*(\d+(?:\.\d+)?)\s*\)', _scale_wait, source)
        logger.info(
            "[scene_builder] │  Timing normalized: %.1fs -> target %.1fs (scale=%.2f)",
            estimated_total, target, scale,
        )
        return source

    def _sanitize_code(self, source: str) -> str:
        """Clean up common LLM code generation issues."""
        source = source.replace("\\n", "\n")

        if source.startswith("```python"):
            source = source[len("```python"):]
        if source.startswith("```"):
            source = source[3:]
        if source.endswith("```"):
            source = source[:-3]
        source = source.strip()

        # Keep whatever import the LLM used — renderer._patch_gl_to_ce()
        # will normalise to manim when running under ManimCE.

        return source

    _LATEX_TO_UNICODE = {
        r"\frac": "/", r"\sqrt": "√", r"\pi": "π", r"\alpha": "α",
        r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\theta": "θ",
        r"\lambda": "λ", r"\sigma": "σ", r"\Sigma": "Σ", r"\Delta": "Δ",
        r"\Omega": "Ω", r"\infty": "∞", r"\int": "∫", r"\sum": "Σ",
        r"\prod": "∏", r"\partial": "∂", r"\times": "×", r"\div": "÷",
        r"\pm": "±", r"\neq": "≠", r"\leq": "≤", r"\geq": "≥",
        r"\approx": "≈", r"\rightarrow": "→", r"\leftarrow": "←",
        r"\Rightarrow": "⇒", r"\cdot": "·", r"\ldots": "…",
    }

    def _replace_latex_with_text(self, source: str) -> str:
        """Replace MathTex/Tex calls with Text equivalents before rendering.

        This prevents dvisvgm crashes by ensuring no LaTeX compilation is ever
        attempted, regardless of what the LLM generated.
        """
        had_latex = bool(re.search(r'\b(MathTex|Tex)\s*\(', source))
        if not had_latex:
            return source

        logger.warning("[scene_builder] │  Pre-render: replacing MathTex/Tex → Text()")

        def _latex_to_text(m: re.Match) -> str:
            content = m.group(2)
            clean = content.strip().strip("r").strip("'\"").strip()
            for latex_cmd, uni in self._LATEX_TO_UNICODE.items():
                clean = clean.replace(latex_cmd, uni)
            clean = re.sub(r"\\text\{([^}]*)\}", r"\1", clean)
            clean = re.sub(r"\\begin\{[^}]*\}", "", clean)
            clean = re.sub(r"\\end\{[^}]*\}", "", clean)
            clean = re.sub(r"\\\\", " ", clean)
            clean = clean.replace("^{", "^").replace("_{", "_")
            clean = re.sub(r"[\\{}]", "", clean)
            clean = re.sub(r"\^(\w)", lambda x: {"0": "⁰", "1": "¹", "2": "²",
                "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸",
                "9": "⁹", "n": "ⁿ", "x": "ˣ", "i": "ⁱ"}.get(x.group(1), "^" + x.group(1)), clean)
            clean = re.sub(r"_(\w)", lambda x: {"0": "₀", "1": "₁", "2": "₂",
                "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈",
                "9": "₉", "n": "ₙ", "i": "ᵢ", "x": "ₓ"}.get(x.group(1), "_" + x.group(1)), clean)
            clean = re.sub(r"\s+", " ", clean).strip()
            if not clean:
                clean = "..."
            return f'Text("{clean}", font_size=36)'

        source = re.sub(
            r'\b(MathTex|Tex)\s*\(\s*(r?(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"]*"|\'[^\']*\')(?:\s*,\s*r?(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"]*"|\'[^\']*\'))*)\s*(?:,\s*font_size\s*=\s*\d+)?\s*\)',
            _latex_to_text,
            source,
        )
        source = re.sub(r'\bTransformMatchingTex\b', 'ReplacementTransform', source)
        source = re.sub(r'\bWrite\b', 'Write', source)

        logger.info("[scene_builder] │  Post-sanitize: %d chars", len(source))
        return source

    def _extract_class_name(self, source: str) -> str | None:
        """Extract the Scene subclass name from source code."""
        match = re.search(r"class\s+(\w+)\s*\(\s*\w*Scene\w*\s*\)", source)
        if match:
            return match.group(1)
        match = re.search(r"class\s+(\w+)\s*\(\s*Scene\s*\)", source)
        if match:
            return match.group(1)
        return None

    def _wrap_in_scene_class(self, code: str, class_name: str) -> str:
        """Wrap loose code in a Scene class."""
        lines = code.split("\n")
        import_lines = []
        body_lines = []
        for line in lines:
            if line.strip().startswith("import ") or line.strip().startswith("from "):
                import_lines.append(line)
            else:
                body_lines.append(line)

        indented_body = "\n".join("        " + l for l in body_lines if l.strip())

        return "\n".join(import_lines) + f"""

class {class_name}(MovingCameraScene):
    def construct(self):
{indented_body}
"""

    def _validate_ast(self, source: str) -> list[str]:
        """Parse source with AST and return list of error messages."""
        errors = []
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            errors.append(f"SyntaxError at line {e.lineno}: {e.msg}")
            return errors

        has_scene_class = False
        has_construct = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = ""
                    if isinstance(base, ast.Name):
                        base_name = base.id
                    elif isinstance(base, ast.Attribute):
                        base_name = base.attr
                    if "Scene" in base_name:
                        has_scene_class = True
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                if item.name == "construct":
                                    has_construct = True

            # Detect banned plugin imports: from manim_* import ...
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("manim_"):
                    errors.append(f"Banned plugin import: from {node.module}")

        if not has_scene_class:
            errors.append("No Scene subclass found")
        if not has_construct:
            errors.append("No construct() method found")
        return errors

    @staticmethod
    def _fix_unterminated_strings(source: str) -> str:
        """Fix unterminated string literals caused by newlines inside strings.

        LLMs sometimes produce strings that span multiple lines without
        triple-quoting, e.g.::

            Text("Hello
            World", font_size=36)

        This joins such lines back together (replacing the embedded newline
        with a space) so the string is valid single-line Python.
        """
        lines = source.split("\n")
        fixed_lines: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()

            # Skip comment-only and blank lines
            if stripped.startswith("#") or not stripped:
                fixed_lines.append(line)
                i += 1
                continue

            # Check if this line has an unterminated string
            in_string: str | None = None
            escape_next = False
            in_triple = False
            j = 0
            while j < len(line):
                ch = line[j]
                if escape_next:
                    escape_next = False
                    j += 1
                    continue
                if ch == "\\":
                    escape_next = True
                    j += 1
                    continue
                if in_string is None:
                    if ch == "#":
                        break  # rest is a comment
                    if ch in ('"', "'"):
                        if line[j:j+3] in ('"""', "'''"):
                            in_triple = True
                            break  # don't mess with triple-quoted strings
                        in_string = ch
                elif ch == in_string:
                    in_string = None
                j += 1

            if in_string is not None and not in_triple:
                # String was opened but not closed — join with next lines
                # until the string closes or we run out of lines (max 3 joins)
                joined = line
                joins = 0
                while in_string is not None and i + 1 < len(lines) and joins < 3:
                    i += 1
                    joins += 1
                    next_line = lines[i].strip()
                    joined = joined.rstrip() + " " + next_line

                    # Re-check if the string is now closed
                    in_string_check: str | None = None
                    escape_next_check = False
                    for ch in joined:
                        if escape_next_check:
                            escape_next_check = False
                            continue
                        if ch == "\\":
                            escape_next_check = True
                            continue
                        if in_string_check is None:
                            if ch == "#":
                                break
                            if ch in ('"', "'"):
                                if ch * 3 in joined:
                                    break
                                in_string_check = ch
                        elif ch == in_string_check:
                            in_string_check = None
                    in_string = in_string_check

                logger.info(
                    "[scene_builder] │  Joined %d line(s) to fix unterminated string",
                    joins,
                )
                fixed_lines.append(joined)
            else:
                fixed_lines.append(line)
            i += 1
        return "\n".join(fixed_lines)

    @staticmethod
    def _auto_fix_code(source: str) -> str:
        """Apply transforms to fix common LLM code issues early.

        This gives us a chance to salvage LLM code before falling back to templates.
        """
        from pipeline.manim_renderer.renderer import ManimRenderer
        source = ManimRenderer._patch_gl_to_ce(source)
        source = SceneBuilder._fix_unterminated_strings(source)
        return source

    @staticmethod
    def _extract_key_phrases(narration: str, count: int = 3) -> list[str]:
        """Pull short, distinct phrases from narration for use in visuals."""
        sentences = re.split(r'[.!?]+', narration)
        phrases: list[str] = []
        for s in sentences:
            s = s.strip()
            if len(s) < 8 or len(s) > 80:
                continue
            phrases.append(s)
            if len(phrases) >= count:
                break
        while len(phrases) < count:
            phrases.append(f"Key point {len(phrases) + 1}")
        return [p[:72] for p in phrases]

    def _build_fallback(self, scene: SceneInstruction) -> tuple[str, str]:
        """Generate a topic-aware fallback scene derived from scene metadata."""
        class_name = f"Scene{scene.scene_index:03d}"
        scene_type = (scene.manim_scene_type or "").lower().strip()
        title = scene.manim_parameters.get("title", "")
        if not title:
            first_sentence = re.split(r'[.!?]', scene.narration_text)[0].strip()
            title = first_sentence[:72] if first_sentence else "Concept Visual"
        title_escaped = title.replace('"', '\\"').replace("'", "\\'")[:80]
        duration = max(8, int(scene.duration_hint_seconds or 10))
        hold = max(0.8, duration - 8)

        phrases = self._extract_key_phrases(scene.narration_text)
        p1 = phrases[0].replace('"', '\\"')
        p2 = phrases[1].replace('"', '\\"')
        p3 = phrases[2].replace('"', '\\"')

        logger.info(
            "[scene_builder] │  Building topic-aware fallback: %s (type=%s, phrases=%s)",
            class_name, scene_type, phrases,
        )

        if scene_type == "graph":
            x_label = scene.manim_parameters.get("x_label", "x")
            y_label = scene.manim_parameters.get("y_label", "f(x)")
            x_label_e = x_label.replace('"', '\\"')[:20]
            y_label_e = y_label.replace('"', '\\"')[:20]
            body = f"""
        # Graph Layout: axes at grid MAIN_AREA
        axes = Axes(
            x_range=[-4, 4, 1], y_range=[-3, 10, 1],
            x_length=10, y_length=5,
            tips=True,
        )
        axes.move_to(DOWN * 0.3)
        x_lab = Text("{x_label_e}", font_size=28).next_to(axes.x_axis, RIGHT, buff=0.2)
        y_lab = Text("{y_label_e}", font_size=28).next_to(axes.y_axis, UP, buff=0.2)
        self.play(Create(axes), Write(x_lab), Write(y_lab), run_time=2.5)
        self.wait(1)

        graph = axes.plot(lambda x: x**2, color=BLUE, x_range=[-3, 3])
        graph2 = axes.plot(lambda x: 2*x, color=GREEN, x_range=[-3, 3])
        lbl1 = Text("{p1[:40]}", font_size=26, color=BLUE).next_to(axes.c2p(2, 4), RIGHT, buff=0.2)
        lbl2 = Text("{p2[:40]}", font_size=26, color=GREEN).next_to(axes.c2p(2.5, 5), RIGHT, buff=0.2)
        self.play(Create(graph), run_time=2.5)
        self.play(Write(lbl1), run_time=1.5)
        self.play(graph.animate.set_opacity(0.3), run_time=0.5)
        self.play(Create(graph2), run_time=2.0)
        self.play(Write(lbl2), run_time=1.5)
        self.wait(1)
        self.play(graph.animate.set_opacity(1.0), run_time=0.5)

        moving_dot = Dot(color=YELLOW).move_to(axes.c2p(-2, 4))
        self.play(FadeIn(moving_dot), run_time=1)
        self.play(MoveAlongPath(moving_dot, graph), run_time=3)
        self.wait(1)

        note = Text("{p3[:48]}", font_size=26, color=YELLOW).next_to(axes, UP, buff=0.6)
        self.play(Write(note), run_time=2)
        self.wait({hold})
"""
        elif scene_type == "equation":
            body = f"""
        # Full Center: equations at grid MAIN_AREA
        step1 = Text("{p1[:60]}", font_size=38).move_to(DOWN * 0.3)
        step2 = Text("{p2[:60]}", font_size=38).move_to(DOWN * 0.3)
        step3 = Text("{p3[:60]}", font_size=38).move_to(DOWN * 0.3)

        self.play(Write(step1), run_time=2.5)
        self.wait(1.5)
        self.play(ReplacementTransform(step1, step2), run_time=2.5)
        self.wait(1.5)
        self.play(ReplacementTransform(step2, step3), run_time=2.5)
        box = SurroundingRectangle(step3, color=YELLOW, buff=0.25)
        self.play(Create(box), run_time=1.5)
        self.play(Indicate(step3, color=YELLOW), run_time=1.2)
        self.wait({hold})
"""
        elif scene_type in {"diagram", "concept_reveal", "summary"}:
            colors = ["BLUE", "GREEN", "TEAL"]
            body = f"""
        # Vertical Stack: cards at grid MAIN_AREA
        card1 = RoundedRectangle(width=6, height=1.0, corner_radius=0.15, color={colors[0]})
        card2 = RoundedRectangle(width=6, height=1.0, corner_radius=0.15, color={colors[1]})
        card3 = RoundedRectangle(width=6, height=1.0, corner_radius=0.15, color={colors[2]})
        cards = VGroup(card1, card2, card3).arrange(DOWN, buff=0.4)
        cards.move_to(DOWN * 0.3)
        t1 = Text("{p1[:52]}", font_size=30).move_to(card1)
        t2 = Text("{p2[:52]}", font_size=30).move_to(card2)
        t3 = Text("{p3[:52]}", font_size=30).move_to(card3)

        # Progressive reveal with dimming
        self.play(FadeIn(card1, shift=UP*0.3), Write(t1), run_time=2.0)
        self.wait(0.8)
        self.play(VGroup(card1, t1).animate.set_opacity(0.3), run_time=0.5)
        self.play(FadeIn(card2, shift=UP*0.3), Write(t2), run_time=2.0)
        self.wait(0.8)
        self.play(VGroup(card2, t2).animate.set_opacity(0.3), run_time=0.5)
        self.play(FadeIn(card3, shift=UP*0.3), Write(t3), run_time=2.0)
        self.wait(0.8)

        # Restore all and emphasize
        self.play(
            VGroup(card1, t1).animate.set_opacity(1.0),
            VGroup(card2, t2).animate.set_opacity(1.0),
            run_time=0.8,
        )
        arrow = Arrow(card1.get_bottom(), card3.get_top(), color=WHITE, buff=0.15)
        self.play(GrowArrow(arrow), run_time=1.6)
        self.play(Indicate(card3, color=YELLOW), run_time=1.4)
        self.wait({hold})
"""
        else:
            body = f"""
        # Generic layout: plane at MAIN_AREA, text overlay
        plane = NumberPlane(
            x_range=[-5,5,1], y_range=[-3,3,1],
            background_line_style={{"stroke_opacity": 0.35}}
        )
        plane.move_to(DOWN * 0.3)
        self.play(Create(plane), run_time=2.2)
        self.wait(0.8)

        point1 = Text("{p1[:44]}", font_size=30, color=BLUE)
        point2 = Text("{p2[:44]}", font_size=30, color=GREEN)
        point3 = Text("{p3[:44]}", font_size=30, color=YELLOW)
        points = VGroup(point1, point2, point3).arrange(DOWN, buff=0.5)
        points.move_to(DOWN * 0.3)

        # Staggered reveal with dimming
        bg1 = BackgroundRectangle(point1, color=BLACK, fill_opacity=0.7, buff=0.15)
        self.play(FadeIn(bg1), Write(point1), run_time=2.0)
        self.wait(0.8)
        self.play(VGroup(bg1, point1).animate.set_opacity(0.3), run_time=0.5)
        bg2 = BackgroundRectangle(point2, color=BLACK, fill_opacity=0.7, buff=0.15)
        self.play(FadeIn(bg2), Write(point2), run_time=2.0)
        self.wait(0.8)
        self.play(VGroup(bg2, point2).animate.set_opacity(0.3), run_time=0.5)
        bg3 = BackgroundRectangle(point3, color=BLACK, fill_opacity=0.7, buff=0.15)
        self.play(FadeIn(bg3), Write(point3), run_time=2.0)
        self.wait(0.8)

        # Restore all
        self.play(
            VGroup(bg1, point1).animate.set_opacity(1.0),
            VGroup(bg2, point2).animate.set_opacity(1.0),
            run_time=0.8,
        )
        self.play(Indicate(point3, color=YELLOW, scale_factor=1.15), run_time=1.4)
        self.wait({hold})
"""

        source = f'''from manim import *
import numpy as np

class {class_name}(MovingCameraScene):
    def construct(self):
        # TITLE at grid TITLE_POS
        title = Text("{title_escaped}", font_size=42)
        self.play(Write(title), run_time=1.8)
        self.wait(0.8)
        self.play(title.animate.move_to(UP * 3.2), run_time=1)
        self.wait(0.8)
{body}
        # CLEANUP — mandatory
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=1.2)
        self.wait(1)
'''
        return source, class_name

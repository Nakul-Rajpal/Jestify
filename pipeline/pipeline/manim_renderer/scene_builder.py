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
        """Sanitize and validate LLM-generated Manim code."""
        source = scene.manim_code or ""
        logger.info("[scene_builder] │  LLM code: %d chars", len(source))

        source = self._sanitize_code(source)

        class_name = self._extract_class_name(source)
        if not class_name:
            expected = f"Scene{scene.scene_index:03d}"
            logger.warning("[scene_builder] │  No Scene class found, wrapping in %s", expected)
            source = self._wrap_in_scene_class(source, expected)
            class_name = expected

        if "from manim import" not in source:
            source = "from manim import *\n\n" + source
            logger.info("[scene_builder] │  Added missing 'from manim import *'")

        errors = self._validate_ast(source)
        if errors:
            logger.error("[scene_builder] │  AST validation failed: %s", errors)
            logger.info("[scene_builder] │  Falling back to template")
            return self._build_fallback(scene)

        return source, class_name

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

        source = re.sub(r"from manimlib import \*", "from manim import *", source)

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

class {class_name}(Scene):
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

        if not has_scene_class:
            errors.append("No Scene subclass found")
        if not has_construct:
            errors.append("No construct() method found")
        return errors

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
        duration = max(20, int(scene.duration_hint_seconds))
        hold = max(4, duration - 14)

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
        axes = Axes(
            x_range=[-4, 4, 1], y_range=[-3, 10, 1],
            x_length=9, y_length=5, axis_config={{"include_numbers": True}},
        ).shift(DOWN * 0.3)
        x_lab = Text("{x_label_e}", font_size=24).next_to(axes.x_axis, RIGHT, buff=0.2)
        y_lab = Text("{y_label_e}", font_size=24).next_to(axes.y_axis, UP, buff=0.2)
        self.play(Create(axes), Write(x_lab), Write(y_lab), run_time=2.5)
        self.wait(1)

        graph = axes.plot(lambda x: x**2, x_range=[-3, 3], color=BLUE)
        graph2 = axes.plot(lambda x: 2*x, x_range=[-3, 3], color=GREEN)
        lbl1 = Text("{p1[:40]}", font_size=22, color=BLUE).next_to(axes.c2p(2, 4), RIGHT, buff=0.2)
        lbl2 = Text("{p2[:40]}", font_size=22, color=GREEN).next_to(axes.c2p(2.5, 5), RIGHT, buff=0.2)
        self.play(Create(graph), run_time=2.5)
        self.play(Write(lbl1), run_time=1.2)
        self.play(Create(graph2), run_time=2.0)
        self.play(Write(lbl2), run_time=1.2)
        self.wait(1)

        moving_dot = Dot(color=YELLOW).move_to(axes.c2p(-2, 4))
        self.play(FadeIn(moving_dot), run_time=1)
        self.play(MoveAlongPath(moving_dot, graph), run_time=3)
        self.wait(1)

        area = axes.get_area(graph, x_range=[0, 2], color=BLUE_E, opacity=0.35)
        note = Text("{p3[:48]}", font_size=22, color=YELLOW).to_edge(DOWN, buff=0.4)
        self.play(FadeIn(area), Write(note), run_time=2)
        self.wait({hold})
"""
        elif scene_type == "equation":
            body = f"""
        step1 = Text("{p1[:60]}", font_size=38)
        step2 = Text("{p2[:60]}", font_size=38)
        step3 = Text("{p3[:60]}", font_size=38)
        step2.move_to(step1)
        step3.move_to(step1)

        self.play(Write(step1), run_time=2.5)
        self.wait(1.5)
        self.play(Transform(step1, step2), run_time=2.5)
        self.wait(1.5)
        self.play(Transform(step1, step3), run_time=2.5)
        box = SurroundingRectangle(step3, color=YELLOW, buff=0.25)
        self.play(Create(box), run_time=1.2)
        self.wait({hold})
"""
        elif scene_type in {"diagram", "concept_reveal", "summary"}:
            colors = ["BLUE", "GREEN", "TEAL"]
            body = f"""
        card1 = RoundedRectangle(width=5.5, height=1.2, corner_radius=0.15, color={colors[0]})
        card2 = RoundedRectangle(width=5.5, height=1.2, corner_radius=0.15, color={colors[1]})
        card3 = RoundedRectangle(width=5.5, height=1.2, corner_radius=0.15, color={colors[2]})
        cards = VGroup(card1, card2, card3).arrange(DOWN, buff=0.4).shift(DOWN*0.3)
        t1 = Text("{p1[:52]}", font_size=26).move_to(card1)
        t2 = Text("{p2[:52]}", font_size=26).move_to(card2)
        t3 = Text("{p3[:52]}", font_size=26).move_to(card3)

        self.play(FadeIn(card1), Write(t1), run_time=2.0)
        self.wait(0.6)
        self.play(FadeIn(card2), Write(t2), run_time=2.0)
        self.wait(0.6)
        self.play(FadeIn(card3), Write(t3), run_time=2.0)
        self.wait(0.6)
        arrow = Arrow(card1.get_bottom(), card3.get_top(), color=WHITE, buff=0.15)
        self.play(GrowArrow(arrow), run_time=1.6)
        self.play(Indicate(card3, color=YELLOW), run_time=1.4)
        self.wait({hold})
"""
        else:
            body = f"""
        plane = NumberPlane(
            x_range=[-5,5,1], y_range=[-3,3,1],
            background_line_style={{"stroke_opacity": 0.35}}
        ).shift(DOWN*0.2)
        self.play(Create(plane), run_time=2.2)
        self.wait(0.8)

        point1 = Text("{p1[:44]}", font_size=26, color=BLUE)
        point2 = Text("{p2[:44]}", font_size=26, color=GREEN)
        point3 = Text("{p3[:44]}", font_size=26, color=YELLOW)
        points = VGroup(point1, point2, point3).arrange(DOWN, buff=0.5).shift(UP*0.5)
        for pt in [point1, point2, point3]:
            bg = BackgroundRectangle(pt, color=BLACK, fill_opacity=0.7, buff=0.15)
            self.play(FadeIn(bg), Write(pt), run_time=2.0)
            self.wait(0.8)
        self.play(Indicate(point3, color=YELLOW, scale_factor=1.15), run_time=1.4)
        self.wait({hold})
"""

        source = f'''from manim import *

class {class_name}(Scene):
    def construct(self):
        title = Text("{title_escaped}", font_size=42)
        self.play(Write(title), run_time=1.8)
        self.wait(0.8)
        self.play(title.animate.to_edge(UP, buff=0.5), run_time=1)
        self.wait(0.8)
{body}
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=1.2)
        self.wait(1)
'''
        return source, class_name

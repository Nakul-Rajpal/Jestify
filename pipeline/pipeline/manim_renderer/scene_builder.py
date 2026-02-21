"""Generates ManimGL scene Python files from SceneInstruction data.

Produces 3Blue1Brown-quality animations with camera movements, color
highlighting, annotations, and staggered reveals.  All on-screen text
uses ``Text()`` (Pango/Cairo, supports Unicode) while mathematics
uses ``Tex()`` (LaTeX).
"""

import logging
import re
from pathlib import Path

from shared.contracts.pipeline_schema import SceneInstruction

logger = logging.getLogger(__name__)

# ManimGL colour constants we accept from the LLM
_VALID_COLORS = frozenset({
    "BLUE", "BLUE_A", "BLUE_B", "BLUE_C", "BLUE_D", "BLUE_E",
    "RED", "RED_A", "RED_B", "RED_C", "RED_D", "RED_E",
    "GREEN", "GREEN_A", "GREEN_B", "GREEN_C", "GREEN_D", "GREEN_E",
    "YELLOW", "YELLOW_A", "YELLOW_B", "YELLOW_C", "YELLOW_D", "YELLOW_E",
    "GOLD", "GOLD_A", "GOLD_B", "GOLD_C", "GOLD_D", "GOLD_E",
    "TEAL", "TEAL_A", "TEAL_B", "TEAL_C", "TEAL_D", "TEAL_E",
    "PURPLE", "PURPLE_A", "PURPLE_B", "PURPLE_C", "PURPLE_D", "PURPLE_E",
    "MAROON", "MAROON_A", "MAROON_B", "MAROON_C", "MAROON_D", "MAROON_E",
    "ORANGE", "PINK", "GREY", "GREY_A", "GREY_B", "GREY_C", "GREY_D",
    "WHITE", "BLACK",
})


class SceneBuilder:
    """Translates a ``SceneInstruction`` into a runnable ManimGL scene file.

    Each ``manim_scene_type`` has a dedicated template method that produces
    valid ManimGL Python source code.  The generated file is written to
    *output_py_path* and the ManimGL scene class name is returned.
    """

    # Map scene types to builder methods
    _BUILDERS: dict[str, str] = {
        "equation": "_build_equation",
        "graph": "_build_graph",
        "diagram": "_build_diagram",
        "text": "_build_concept_reveal",       # legacy alias
        "geometry": "_build_geometry",
        "concept_reveal": "_build_concept_reveal",
        "number_line": "_build_number_line",
        "coordinate_plane": "_build_coordinate_plane",
        "comparison": "_build_comparison",
        "summary": "_build_summary",
    }

    def build_scene_file(
        self, scene: SceneInstruction, output_py_path: str
    ) -> str:
        """Build a ``.py`` scene file and return the ManimGL class name."""

        # If the scene has direct ManimGL code from Claude, use it
        if scene.manim_code:
            return self._build_from_raw_code(scene, output_py_path)

        # Otherwise fall back to template-based builders
        scene_type = scene.manim_scene_type
        builder_name = self._BUILDERS.get(scene_type)

        if builder_name is None:
            logger.warning(
                "Unknown scene type '%s', falling back to concept_reveal",
                scene_type,
            )
            builder_name = "_build_concept_reveal"

        builder = getattr(self, builder_name)
        class_name, source = builder(scene.manim_parameters, scene.scene_index)

        # Pad scene with extra wait time to approach the target duration.
        # The animation content itself takes roughly 15-20s; pad the rest
        # so the rendered clip is closer to the narration length.
        target = scene.duration_hint_seconds
        anim_estimate = 20  # conservative estimate of animation seconds
        pad = max(2, target - anim_estimate)
        # Insert a long wait before the final empty line
        source = source.rstrip("\n") + f"\n        self.wait({pad})\n"

        Path(output_py_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_py_path).write_text(source, encoding="utf-8")

        logger.info(
            "[scene_builder] Built scene file %s (class=%s, type=%s)",
            output_py_path, class_name, scene_type,
        )
        logger.info(
            "[scene_builder] Generated source (%d chars):\n%s",
            len(source), source,
        )

        return class_name

    def _build_from_raw_code(
        self, scene: SceneInstruction, output_py_path: str
    ) -> str:
        """Write Claude-generated ManimGL code directly to file.

        Extracts the class name from the code and ensures the import header
        is present.
        """
        source = scene.manim_code

        # Ensure the import header is present
        if "from manimlib import" not in source:
            source = "from manimlib import *\nimport numpy as np\n\n" + source

        # ---- Auto-fix common ManimGL mistakes from LLM-generated code ----
        # Process line-by-line to fix Tex() issues.
        fixed_lines = []
        for line in source.split('\n'):
            if 'Tex(' in line and 'Text(' not in line:
                # Remove font_size kwarg (Tex uses .scale() instead)
                line = re.sub(r',\s*font_size\s*=\s*[\d.]+', '', line)
                # Convert color kwarg to .set_color() chain
                color_match = re.search(r',\s*color\s*=\s*(\w+)', line)
                if color_match:
                    color_val = color_match.group(1)
                    line = re.sub(r',\s*color\s*=\s*\w+', '', line)
                    # Append .set_color() after the Tex(...) call
                    line = line.rstrip()
                    if line.endswith(')'):
                        line = line + f'.set_color({color_val})'
                # Fix over-escaped backslashes from JSON double-escaping.
                # LaTeX needs \\ (2 backslashes) for row breaks, but Claude
                # often produces \\\\ (4 backslashes). Reduce 4+ to 2.
                while '\\\\\\\\' in line:
                    line = line.replace('\\\\\\\\', '\\\\')
            fixed_lines.append(line)
        source = '\n'.join(fixed_lines)

        # Extract the class name from the source (first `class XYZ(Scene):`)
        class_match = re.search(r"class\s+(\w+)\s*\(\s*Scene\s*\)", source)
        if class_match:
            class_name = class_match.group(1)
        else:
            # Fallback: wrap in a generic class if no Scene class found
            class_name = f"Scene{scene.scene_index}"
            logger.warning(
                "[scene_builder] No Scene class found in manim_code, "
                "wrapping in %s",
                class_name,
            )
            indented = "\n".join(
                f"        {line}" if line.strip() else ""
                for line in source.split("\n")
            )
            source = (
                "from manimlib import *\n"
                "import numpy as np\n\n"
                f"class {class_name}(Scene):\n"
                f"    def construct(self):\n"
                f"{indented}\n"
            )

        Path(output_py_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_py_path).write_text(source, encoding="utf-8")

        logger.info(
            "[scene_builder] Built scene file from raw code %s (class=%s)",
            output_py_path, class_name,
        )
        logger.info(
            "[scene_builder] Raw source (%d chars):\n%s",
            len(source), source[:2000],
        )

        return class_name

    # ------------------------------------------------------------------ #
    # Shared helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _safe(text: str) -> str:
        """Escape a string for embedding inside a Python double-quoted string."""
        return text.replace("\\", "\\\\").replace('"', '\\"')

    @classmethod
    def _safe_tex(cls, text: str) -> str:
        """Sanitize and escape a LaTeX string for embedding in r\"...\".

        Strips complex environments that ManimGL cannot handle, then
        escapes double quotes (backslashes stay literal in raw strings).
        """
        text = cls._sanitize_tex(text)
        return text.replace('"', '\\"')

    @staticmethod
    def _sanitize_tex(text: str) -> str:
        r"""Sanitize LaTeX for ManimGL's Tex class.

        ManimGL cannot handle complex environments like \begin{pmatrix},
        \begin{align}, \begin{cases}, etc.  Also cannot handle \text{},
        \mathrm{}, \textbf{}, or semicolons inside math.  Strip them
        all down to simple inline math that Tex can render.
        """
        # Replace \begin{pmatrix}...\end{pmatrix} with a flat representation
        def _flatten_matrix(m: re.Match) -> str:
            body = m.group(1)
            # rows separated by \\, cols by &
            rows = [r.strip() for r in re.split(r"\\\\", body)]
            flat_rows = []
            for row in rows:
                cols = [c.strip() for c in row.split("&")]
                flat_rows.append(", ".join(cols))
            # Use comma-separated rows (semicolons are NOT valid LaTeX)
            return "[" + ", ".join(flat_rows) + "]"

        for env in ("pmatrix", "bmatrix", "vmatrix", "Bmatrix", "matrix"):
            text = re.sub(
                rf"\\begin\{{{env}\}}(.*?)\\end\{{{env}\}}",
                _flatten_matrix,
                text,
                flags=re.DOTALL,
            )

        # Replace \begin{cases}...\end{cases} with simple comma list
        def _flatten_cases(m: re.Match) -> str:
            body = m.group(1)
            rows = [r.strip() for r in re.split(r"\\\\", body)]
            parts = []
            for row in rows:
                cleaned = row.replace("&", ",\\ ")
                parts.append(cleaned)
            return ",\\ ".join(parts)

        text = re.sub(
            r"\\begin\{cases\}(.*?)\\end\{cases\}",
            _flatten_cases,
            text,
            flags=re.DOTALL,
        )

        # Strip any remaining \begin{...}...\end{...} environments
        text = re.sub(r"\\begin\{[^}]+\}", "", text)
        text = re.sub(r"\\end\{[^}]+\}", "", text)

        # Strip \text{...}, \mathrm{...}, \textbf{...}, \textit{...}
        # Replace with just the inner content (no braces)
        for cmd in ("text", "mathrm", "textbf", "textit", "mbox", "hbox"):
            text = re.sub(rf"\\{cmd}\{{([^}}]*)\}}", r" \1 ", text)

        # Replace semicolons with commas (semicolons crash LaTeX math mode)
        text = text.replace(";", ",")

        # Strip double-backslash row breaks that might remain (invalid in Tex)
        text = text.replace("\\\\", " ")

        # Collapse multiple spaces
        text = re.sub(r"  +", " ", text)

        return text.strip()

    @staticmethod
    def _col(color: str) -> str:
        """Return a validated ManimGL colour constant name."""
        return color if color in _VALID_COLORS else "WHITE"

    @staticmethod
    def _ascii_safe(text: str) -> str:
        """Replace common Unicode math symbols with ASCII equivalents.

        ManimGL Text() *can* handle Unicode via Pango, but some fonts
        lack glyphs for subscript digits, Greek letters, etc.  This
        converts the most common offenders to safe ASCII representations.
        """
        _map = {
            "\u03bb": "lambda", "\u03b1": "alpha", "\u03b2": "beta",
            "\u03b3": "gamma", "\u03b4": "delta", "\u03b5": "epsilon",
            "\u03c3": "sigma", "\u03c4": "tau", "\u03c9": "omega",
            "\u03bc": "mu", "\u03c0": "pi", "\u03b8": "theta",
            "\u2081": "_1", "\u2082": "_2", "\u2083": "_3",
            "\u2084": "_4", "\u2080": "_0",
            "\u00b2": "^2", "\u00b3": "^3",
            "\u2192": "->", "\u2190": "<-", "\u2194": "<->",
            "\u2265": ">=", "\u2264": "<=", "\u2260": "!=",
            "\u221e": "inf",
        }
        for uc, asc in _map.items():
            text = text.replace(uc, asc)
        return text

    @staticmethod
    def _pos3(raw) -> list:
        """Ensure a position list has exactly 3 elements."""
        pos = list(raw) if raw else [0, 0, 0]
        return pos + [0] * (3 - len(pos))

    def _emit_title(self, title: str | None, lines: list[str]) -> None:
        """Append a title at the top of the scene."""
        if not title:
            return
        safe = self._safe(title)
        lines.append(f'        title = Text("{safe}", font_size=42).to_edge(UP)')
        lines.append("        self.play(Write(title))")
        lines.append("        self.wait(2)")

    @staticmethod
    def _emit_camera_focus(target_var: str, height: float, lines: list[str]) -> None:
        """Append a camera-zoom animation focusing on *target_var*."""
        lines.append(
            f"        self.play("
            f"self.camera.frame.animate.set_height({height})"
            f".move_to({target_var}), run_time=1.5)"
        )
        lines.append("        self.wait(1)")

    @staticmethod
    def _emit_dim_previous(
        var_names: list[str],
        opacity: float,
        lines: list[str],
    ) -> None:
        """Append animation to dim/restore a list of variable names."""
        if not var_names:
            return
        targets = ", ".join(f"{v}.animate.set_opacity({opacity})" for v in var_names)
        lines.append(f"        self.play({targets}, run_time=0.4)")

    @staticmethod
    def _emit_tex_safe(
        var_name: str,
        latex: str,
        lines: list[str],
        *,
        color: str | None = None,
        scale: float | None = None,
        position_suffix: str = "",
    ) -> None:
        """Append a Tex() line using .set_color()/.scale() (never constructor args)."""
        chain = f'        {var_name} = Tex(r"{latex}")'
        if scale is not None:
            chain += f".scale({scale})"
        if color is not None:
            chain += f".set_color({color})"
        if position_suffix:
            chain += position_suffix
        lines.append(chain)

    # ------------------------------------------------------------------ #
    # Template builders — each returns (class_name, full_source_code)
    # ------------------------------------------------------------------ #

    # ── equation ────────────────────────────────────────────────────── #

    def _build_equation(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Rich equation scene: step header, step-by-step transforms with
        surrounding rectangles, colour highlighting, annotations, and
        camera zoom — much more than just bare LaTeX."""
        class_name = f"EquationScene{scene_index}"

        # --- parameter extraction ------------------------------------
        steps = params.get("steps")
        if steps is None:
            latex = params.get("latex", r"x = 1")
            steps = [latex] if isinstance(latex, str) else list(latex)
        elif isinstance(steps, str):
            steps = [steps]

        title = params.get("title", "")
        color_map: dict[str, str] = params.get("color_map", {})
        highlight_steps: list[int] = params.get("highlight_steps", [])
        annotations: list[dict] = params.get("annotations", [])

        # --- source code ---------------------------------------------
        lines = [
            "from manimlib import *",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
        ]

        self._emit_title(title, lines)

        # Step counter label in the corner
        total = len(steps)
        if total > 1:
            lines.append(
                f'        step_label = Text("Step 1/{total}", font_size=20, color=GREY_B)'
                f".to_corner(UR)"
            )
            lines.append("        self.play(FadeIn(step_label))")

        for i, latex_str in enumerate(steps):
            safe_latex = self._safe_tex(latex_str)
            var = f"eq{i}"
            lines.append(f'        {var} = Tex(r"{safe_latex}")')

            # Colour-code parts
            for tex_substr, col_name in color_map.items():
                safe_sub = self._safe_tex(tex_substr)
                lines.append(
                    f'        {var}.set_color_by_tex(r"{safe_sub}", {self._col(col_name)})'
                )

            if i == 0:
                lines.append(f"        self.play(Write({var}), run_time=2)")
                # Camera focus on the equation
                self._emit_camera_focus(var, 5, lines)
                # Add surrounding rectangle for first step
                lines.append(
                    f"        rect{i} = SurroundingRectangle({var}, color=BLUE, buff=0.2)"
                )
                lines.append(f"        self.play(ShowCreation(rect{i}))")
                lines.append("        self.wait(3)")
                lines.append(f"        self.play(FadeOut(rect{i}))")
            else:
                prev = f"eq{i - 1}"
                # Update step counter
                if total > 1:
                    lines.append(
                        f'        new_step_label = Text("Step {i + 1}/{total}", '
                        f'font_size=20, color=GREY_B).to_corner(UR)'
                    )
                    lines.append(
                        "        self.play("
                        f"TransformMatchingTex({prev}, {var}), "
                        "Transform(step_label, new_step_label), "
                        "run_time=2)"
                    )
                    lines.append("        step_label = new_step_label")
                else:
                    lines.append(
                        f"        self.play(TransformMatchingTex({prev}, {var}), run_time=2)"
                    )

            # Emphasis on highlighted steps
            if i in highlight_steps:
                lines.append(
                    f"        highlight_rect = SurroundingRectangle({var}, color=YELLOW, buff=0.25)"
                )
                lines.append(f"        self.play(ShowCreation(highlight_rect))")
                lines.append(f"        self.play(Indicate({var}, scale_factor=1.05, color=YELLOW))")
                lines.append("        self.wait(2)")
                lines.append("        self.play(FadeOut(highlight_rect))")
            else:
                lines.append("        self.wait(3)")

        # Annotations (Brace + label)
        last_eq = f"eq{len(steps) - 1}" if steps else "eq0"
        for j, ann in enumerate(annotations):
            direction = ann.get("direction", "UP")
            ann_text = self._safe(ann.get("text", ""))
            lines.append(f"        brace{j} = Brace({last_eq}, {direction})")
            lines.append(
                f'        brace_label{j} = Text("{ann_text}", font_size=24)'
                f".next_to(brace{j}, {direction})"
            )
            lines.append(
                f"        self.play(GrowFromCenter(brace{j}), FadeIn(brace_label{j}))"
            )
            lines.append("        self.wait(3)")

        # Final emphasis: flash the last equation
        if steps:
            lines.append(
                f"        final_rect = SurroundingRectangle({last_eq}, color=GREEN, buff=0.3)"
            )
            lines.append("        self.play(ShowCreation(final_rect))")
            lines.append("        self.wait(2)")

        lines.append("        self.wait(2)")
        lines.append("")

        return class_name, "\n".join(lines)

    # ── graph ───────────────────────────────────────────────────────── #

    def _build_graph(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Rich graph scene: axes with axis labels, primary curve with
        animated tracing dot, shaded areas with value annotations,
        tangent lines with slope labels, and secondary function overlays
        with legends."""
        class_name = f"GraphScene{scene_index}"

        func_str = params.get("func_str") or params.get("function", "x**2")
        x_range = list(params.get("x_range", [-5, 5, 1]))
        y_range = list(params.get("y_range", [-5, 5, 1]))
        if len(x_range) == 2:
            x_range.append(1)
        if len(y_range) == 2:
            y_range.append(1)

        title = params.get("title", "")
        color = self._col(params.get("color", "BLUE"))
        label = params.get("label", "")
        show_area: dict | None = params.get("show_area")
        show_tangent: dict | None = params.get("show_tangent")
        trace_dot: bool = params.get("trace_dot", False)
        secondary_funcs: list[dict] = params.get("secondary_funcs", [])

        lines = [
            "from manimlib import *",
            "import numpy as np",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
        ]

        self._emit_title(title, lines)

        # Axes with labels
        lines.append(f"        axes = Axes(x_range={x_range}, y_range={y_range})")
        lines.append("        axes.add_coordinate_labels()")
        lines.append('        x_label = Text("x", font_size=24).next_to(axes.x_axis, RIGHT)')
        lines.append('        y_label = Text("y", font_size=24).next_to(axes.y_axis, UP)')
        lines.append("        self.play(ShowCreation(axes), run_time=2)")
        lines.append("        self.play(FadeIn(x_label), FadeIn(y_label))")
        self._emit_camera_focus("axes", 8, lines)
        lines.append("        self.wait(2)")

        # Primary graph — wrap function to catch domain errors
        lines.append(f"        def _graph_func(x):")
        lines.append(f"            try:")
        lines.append(f"                _val = {func_str}")
        lines.append(f"                return _val if np.isfinite(_val) else 0")
        lines.append(f"            except Exception:")
        lines.append(f"                return 0")
        lines.append(
            f"        graph = axes.get_graph(_graph_func, color={color})"
        )
        # Animated drawing of the curve
        lines.append("        self.play(ShowCreation(graph), run_time=3)")

        # Graph label
        if label:
            safe_label = self._safe(self._ascii_safe(label))
            lines.append(
                f'        graph_label = Text("{safe_label}", font_size=24, color={color})'
                f".next_to(graph.get_end(), UR, buff=0.2)"
            )
            lines.append("        self.play(FadeIn(graph_label))")

        lines.append("        self.wait(3)")

        # Tracing dot — even if not explicitly requested, add a brief one
        if trace_dot:
            lines.append("        # Tracing dot along the curve")
            lines.append("        trace_dot = Dot(color=YELLOW, radius=0.08)")
            lines.append("        trace_dot.move_to(graph.get_start())")
            lines.append("        self.play(FadeIn(trace_dot))")
            lines.append("        self.play(MoveAlongPath(trace_dot, graph), run_time=4)")
            lines.append("        self.wait(2)")
            lines.append("        self.play(FadeOut(trace_dot))")

        # Mark some key points on the graph (x=0, midpoint of range)
        mid_x = (x_range[0] + x_range[1]) / 2
        lines.append(f"        # Key point marker")
        lines.append(f"        _kf = lambda x: {func_str}")
        lines.append(f"        try:")
        lines.append(f"            _ky = round(_kf({mid_x}), 2)")
        lines.append(f"        except Exception:")
        lines.append(f"            _ky = 0")
        lines.append(f"        key_dot = Dot(axes.i2gp({mid_x}, graph), color=RED, radius=0.08)")
        lines.append(f"        self.play(FadeIn(key_dot, scale=2))")
        lines.append(
            f'        key_label = Text(f"({mid_x}, {{_ky}})", '
            f"font_size=18, color=RED).next_to(key_dot, UR, buff=0.1)"
        )
        lines.append("        self.play(FadeIn(key_label))")
        lines.append("        self.wait(2)")

        # Shaded area with value annotation
        if show_area:
            a_min = show_area.get("x_min", x_range[0])
            a_max = show_area.get("x_max", x_range[1])
            a_col = self._col(show_area.get("color", "BLUE_E"))
            a_opa = show_area.get("opacity", 0.3)
            lines.append(
                f"        area = axes.get_area(graph, "
                f"x_range=[{a_min}, {a_max}], "
                f"color={a_col}, opacity={a_opa})"
            )
            lines.append("        self.play(FadeIn(area), run_time=2)")
            lines.append("        self.wait(2)")
            # Add boundary lines — use the graph function safely
            lines.append(f"        _af = lambda x: {func_str}")
            lines.append(f"        try:")
            lines.append(f"            _y_left = _af({a_min})")
            lines.append(f"            _y_right = _af({a_max})")
            lines.append(f"        except Exception:")
            lines.append(f"            _y_left, _y_right = 0, 0")
            lines.append(
                f"        left_line = DashedLine("
                f"axes.c2p({a_min}, 0), axes.c2p({a_min}, _y_left), "
                f"color=GREY)"
            )
            lines.append(
                f"        right_line = DashedLine("
                f"axes.c2p({a_max}, 0), axes.c2p({a_max}, _y_right), "
                f"color=GREY)"
            )
            lines.append(
                "        self.play(ShowCreation(left_line), ShowCreation(right_line))"
            )
            lines.append("        self.wait(2)")

        # Tangent line with slope annotation
        if show_tangent:
            tx = show_tangent.get("x_value", 0)
            t_col = self._col(show_tangent.get("color", "YELLOW"))
            t_len = show_tangent.get("length", 4)
            lines.append(f"        # Tangent at x={tx}")
            lines.append(f"        _h = 0.0001")
            lines.append(f"        _f = lambda x: {func_str}")
            lines.append(f"        _slope = (_f({tx} + _h) - _f({tx} - _h)) / (2 * _h)")
            lines.append(f"        _y0 = _f({tx})")
            lines.append(f"        tan_func = lambda x: _slope * (x - {tx}) + _y0")
            lines.append(
                f"        tan_graph = axes.get_graph("
                f"tan_func, "
                f"x_range=[{tx} - {t_len / 2}, {tx} + {t_len / 2}], "
                f"color={t_col})"
            )
            lines.append(
                f"        tan_dot = Dot(axes.i2gp({tx}, graph), color={t_col}, radius=0.1)"
            )
            lines.append(
                "        self.play(FadeIn(tan_dot, scale=2), ShowCreation(tan_graph), run_time=1.5)"
            )
            # Slope label
            lines.append(
                f'        slope_label = Text(f"slope = {{round(_slope, 2)}}", '
                f'font_size=20, color={t_col}).next_to(tan_dot, UR, buff=0.2)'
            )
            lines.append("        self.play(FadeIn(slope_label))")
            lines.append("        self.wait(3)")

        # Secondary functions with legend
        for j, sf in enumerate(secondary_funcs):
            sf_str = sf.get("func_str", "x")
            sf_col = self._col(sf.get("color", "GREEN"))
            sf_label = sf.get("label", "")
            lines.append(
                f"        sec_graph{j} = axes.get_graph("
                f"lambda x: {sf_str}, color={sf_col})"
            )
            lines.append(f"        self.play(ShowCreation(sec_graph{j}), run_time=2)")
            if sf_label:
                safe_sf = self._safe(self._ascii_safe(sf_label))
                lines.append(
                    f'        sec_label{j} = Text("{safe_sf}", font_size=24, color={sf_col})'
                    f".next_to(sec_graph{j}.get_end(), UR, buff=0.2)"
                )
                lines.append(f"        self.play(FadeIn(sec_label{j}))")
            lines.append("        self.wait(2)")

        # Final camera zoom out to show everything
        lines.append("        self.play(self.camera.frame.animate.set_height(10), run_time=1.5)")
        lines.append("        self.wait(2)")
        lines.append("")

        return class_name, "\n".join(lines)

    # ── diagram ─────────────────────────────────────────────────────── #

    def _build_diagram(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Nodes inside coloured rounded rectangles with edge labels and
        staggered LaggedStart animations."""
        class_name = f"DiagramScene{scene_index}"

        nodes = params.get("nodes", [{"label": "A", "position": [0, 0, 0]}])
        edges = params.get("edges", [])
        edge_labels: list[str] = params.get("edge_labels", [])

        # Label-to-index map
        label_to_idx: dict[str, int] = {}
        for i, node in enumerate(nodes):
            lbl = node.get("label", f"N{i}") if isinstance(node, dict) else f"N{i}"
            label_to_idx[lbl] = i

        lines = [
            "from manimlib import *",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
            "        nodes = VGroup()",
        ]

        for i, node in enumerate(nodes):
            if isinstance(node, dict):
                label = node.get("label", f"N{i}")
                raw_pos = node.get("position", [0, 0, 0])
                col = self._col(node.get("color", "BLUE"))
            else:
                label, raw_pos, col = f"N{i}", [0, 0, 0], "BLUE"
            pos = self._pos3(raw_pos)
            safe_label = self._safe(label)

            lines.append(f"        # Node {i}")
            lines.append(
                f"        box{i} = RoundedRectangle("
                f"corner_radius=0.2, width=2.5, height=0.8, "
                f"color={col}, fill_opacity=0.15)"
            )
            lines.append(
                f'        lbl{i} = Text("{safe_label}", font_size=28, color={col})'
            )
            lines.append(f"        lbl{i}.move_to(box{i})")
            lines.append(f"        node{i} = VGroup(box{i}, lbl{i})")
            lines.append(f"        node{i}.move_to([{pos[0]}, {pos[1]}, {pos[2]}])")
            lines.append(f"        nodes.add(node{i})")

        # Staggered node reveal
        lines.append("        self.play(LaggedStartMap(FadeIn, nodes, lag_ratio=0.3))")
        lines.append("        self.wait(2)")

        # Edges
        for ei, edge in enumerate(edges):
            try:
                from_idx, to_idx = self._resolve_edge(edge, label_to_idx, len(nodes))
            except (ValueError, KeyError, IndexError) as e:
                logger.warning("[scene_builder] Skipping invalid edge %s: %s", edge, e)
                continue

            lines.append(
                f"        edge_{from_idx}_{to_idx} = Arrow("
                f"node{from_idx}.get_right(), node{to_idx}.get_left(), "
                f"buff=0.15, color=GREY)"
            )
            lines.append(
                f"        self.play(ShowCreation(edge_{from_idx}_{to_idx}))"
            )

            # Edge label
            if ei < len(edge_labels) and edge_labels[ei]:
                safe_el = self._safe(edge_labels[ei])
                lines.append(
                    f'        el_{from_idx}_{to_idx} = Text("{safe_el}", font_size=20)'
                    f".next_to(edge_{from_idx}_{to_idx}, UP, buff=0.1)"
                )
                lines.append(f"        self.play(FadeIn(el_{from_idx}_{to_idx}))")

        lines.append("        self.wait(1)")
        lines.append("")

        return class_name, "\n".join(lines)

    @staticmethod
    def _resolve_edge(
        edge, label_to_idx: dict[str, int], num_nodes: int
    ) -> tuple[int, int]:
        """Resolve an edge to (from_index, to_index) regardless of format."""
        if isinstance(edge, dict):
            src = edge.get("from", edge.get("source", edge.get("from_idx", 0)))
            dst = edge.get("to", edge.get("target", edge.get("to_idx", 1)))
            if isinstance(src, str):
                src = label_to_idx.get(src, 0)
            if isinstance(dst, str):
                dst = label_to_idx.get(dst, 0)
            return int(src), int(dst)
        elif isinstance(edge, (list, tuple)):
            return int(edge[0]), int(edge[1])
        else:
            raise ValueError(f"Unknown edge format: {edge}")

    # ── geometry ────────────────────────────────────────────────────── #

    def _build_geometry(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Geometric constructions with labels, fill, and staggered animation."""
        class_name = f"GeometryScene{scene_index}"
        shapes = params.get("shapes", [{"type": "circle"}])
        title = params.get("title", "")

        lines = [
            "from manimlib import *",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
            "        shapes = VGroup()",
        ]

        self._emit_title(title, lines)

        for i, shape in enumerate(shapes):
            shape_type = shape.get("type", "circle")
            color = self._col(shape.get("color", "WHITE"))
            raw_pos = shape.get("position", [0, 0, 0])
            pos = self._pos3(raw_pos)
            fill_op = shape.get("fill_opacity", 0.0)
            label = shape.get("label", "")

            if shape_type == "circle":
                radius = shape.get("radius", 1.0)
                lines.append(
                    f"        shape{i} = Circle(radius={radius}, color={color}, "
                    f"fill_opacity={fill_op})"
                    f".move_to([{pos[0]}, {pos[1]}, {pos[2]}])"
                )
            elif shape_type == "square":
                side = shape.get("side_length", 2.0)
                lines.append(
                    f"        shape{i} = Square(side_length={side}, color={color}, "
                    f"fill_opacity={fill_op})"
                    f".move_to([{pos[0]}, {pos[1]}, {pos[2]}])"
                )
            elif shape_type == "triangle":
                lines.append(
                    f"        shape{i} = Triangle(color={color}, "
                    f"fill_opacity={fill_op})"
                    f".move_to([{pos[0]}, {pos[1]}, {pos[2]}])"
                )
            elif shape_type == "line":
                raw_start = shape.get("start", [-2, 0, 0])
                raw_end = shape.get("end", [2, 0, 0])
                start = self._pos3(raw_start)
                end = self._pos3(raw_end)
                lines.append(
                    f"        shape{i} = Line("
                    f"[{start[0]}, {start[1]}, {start[2]}], "
                    f"[{end[0]}, {end[1]}, {end[2]}], color={color})"
                )
            else:
                lines.append(
                    f"        shape{i} = Circle(color={color}, "
                    f"fill_opacity={fill_op})"
                    f".move_to([{pos[0]}, {pos[1]}, {pos[2]}])"
                )

            lines.append(f"        shapes.add(shape{i})")

            if label:
                safe_lbl = self._safe(label)
                lines.append(
                    f'        slbl{i} = Text("{safe_lbl}", font_size=22)'
                    f".next_to(shape{i}, DOWN, buff=0.2)"
                )
                lines.append(f"        shapes.add(slbl{i})")

        # Staggered reveal
        lines.append("        self.play(LaggedStartMap(ShowCreation, shapes, lag_ratio=0.25))")
        self._emit_camera_focus("shapes", 7, lines)
        lines.append("        self.wait(1)")
        lines.append("")

        return class_name, "\n".join(lines)

    # ── concept_reveal (replaces "text") ────────────────────────────── #

    def _build_concept_reveal(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Concept cards with per-card reveal and dimming of previous cards
        to focus attention on the active item."""
        class_name = f"ConceptRevealScene{scene_index}"

        title = params.get("title", "")
        concepts: list[dict | str] = params.get(
            "concepts",
            params.get("bullets", ["Concept 1"]),
        )
        arrangement = params.get("arrangement", "vertical")

        lines = [
            "from manimlib import *",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
        ]

        self._emit_title(title, lines)

        lines.append("        concepts = VGroup()")

        emphasis_indices: list[int] = []
        for i, concept in enumerate(concepts):
            if isinstance(concept, dict):
                text = concept.get("text", f"Concept {i + 1}")
                col = self._col(concept.get("color", "BLUE"))
                if concept.get("emphasis", False):
                    emphasis_indices.append(i)
            else:
                text = str(concept)
                col = "BLUE"

            safe_text = self._safe(text)
            lines.append(f"        # Concept {i}")
            lines.append(
                f"        cbox{i} = RoundedRectangle("
                f"corner_radius=0.2, width=6, height=1.0, "
                f"color={col}, fill_opacity=0.12)"
            )
            lines.append(
                f'        ctxt{i} = Text("{safe_text}", font_size=30, color={col})'
            )
            lines.append(f"        ctxt{i}.move_to(cbox{i})")
            lines.append(f"        c{i} = VGroup(cbox{i}, ctxt{i})")
            lines.append(f"        concepts.add(c{i})")

        # Arrange
        if arrangement == "grid" and len(concepts) >= 4:
            lines.append("        # Arrange in 2-column grid")
            lines.append("        left = VGroup(*[concepts[i] for i in range(0, len(concepts), 2)])")
            lines.append("        right = VGroup(*[concepts[i] for i in range(1, len(concepts), 2)])")
            lines.append("        left.arrange(DOWN, buff=0.4)")
            lines.append("        right.arrange(DOWN, buff=0.4)")
            lines.append("        VGroup(left, right).arrange(RIGHT, buff=0.6).center()")
        else:
            lines.append("        concepts.arrange(DOWN, buff=0.4)")
            lines.append("        concepts.center()")

        # Shift down if title present
        if title:
            lines.append("        concepts.shift(DOWN * 0.3)")

        # Reveal concepts one at a time, dimming previous cards
        num_concepts = len(concepts)
        for i in range(num_concepts):
            if i == 0:
                lines.append(
                    f"        self.play(FadeIn(c0, shift=UP*0.3), run_time=0.6)"
                )
            else:
                self._emit_dim_previous(
                    [f"c{j}" for j in range(i)], 0.3, lines
                )
                lines.append(
                    f"        self.play(FadeIn(c{i}, shift=UP*0.3), run_time=0.6)"
                )
            lines.append("        self.wait(1.5)")

        # Restore full opacity on all cards
        if num_concepts > 1:
            self._emit_dim_previous(
                [f"c{j}" for j in range(num_concepts)], 1.0, lines
            )
            lines.append("        self.wait(1)")

        # Emphasis
        for idx in emphasis_indices:
            lines.append(f"        self.play(Indicate(c{idx}, scale_factor=1.08, color=YELLOW))")
            lines.append("        self.wait(1)")

        self._emit_camera_focus("concepts", 7, lines)
        lines.append("        self.wait(1)")
        lines.append("")

        return class_name, "\n".join(lines)

    # ── number_line ─────────────────────────────────────────────────── #

    def _build_number_line(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Animated number line with labelled points, shaded intervals,
        and a travelling dot."""
        class_name = f"NumberLineScene{scene_index}"

        title = params.get("title", "")
        nl_range = params.get("range", [-5, 5, 1])
        if len(nl_range) == 2:
            nl_range.append(1)
        points: list[dict] = params.get("points", [])
        intervals: list[dict] = params.get("intervals", [])
        animate_dot: dict | None = params.get("animate_dot")

        lines = [
            "from manimlib import *",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
        ]

        self._emit_title(title, lines)

        lines.append(
            f"        nl = NumberLine(x_range={nl_range}, "
            f"length=10, include_numbers=True)"
        )
        lines.append("        self.play(ShowCreation(nl), run_time=1.5)")
        self._emit_camera_focus("nl", 6, lines)

        # Labelled points
        for i, pt in enumerate(points):
            val = pt.get("value", 0)
            lbl = self._safe(pt.get("label", str(val)))
            col = self._col(pt.get("color", "YELLOW"))
            lines.append(
                f"        pt{i} = Dot(nl.n2p({val}), color={col}, radius=0.1)"
            )
            lines.append(
                f'        pt_lbl{i} = Text("{lbl}", font_size=22, color={col})'
                f".next_to(pt{i}, UP, buff=0.2)"
            )
            lines.append(f"        self.play(FadeIn(pt{i}), FadeIn(pt_lbl{i}))")

        # Intervals
        for i, iv in enumerate(intervals):
            start = iv.get("start", 0)
            end = iv.get("end", 1)
            col = self._col(iv.get("color", "GREEN"))
            lbl = iv.get("label", "")
            lines.append(
                f"        iv{i} = Line(nl.n2p({start}), nl.n2p({end}), "
                f"stroke_width=8, color={col})"
            )
            lines.append(f"        self.play(ShowCreation(iv{i}), run_time=1)")
            if lbl:
                safe_lbl = self._safe(lbl)
                lines.append(
                    f'        iv_lbl{i} = Text("{safe_lbl}", font_size=20, color={col})'
                    f".next_to(iv{i}, DOWN, buff=0.2)"
                )
                lines.append(f"        self.play(FadeIn(iv_lbl{i}))")

        # Animated travelling dot
        if animate_dot:
            ad_from = animate_dot.get("from", nl_range[0])
            ad_to = animate_dot.get("to", nl_range[1])
            ad_col = self._col(animate_dot.get("color", "WHITE"))
            lines.append(
                f"        adot = Dot(nl.n2p({ad_from}), color={ad_col}, radius=0.12)"
            )
            lines.append("        self.play(FadeIn(adot))")
            lines.append(
                f"        self.play(adot.animate.move_to(nl.n2p({ad_to})), run_time=2.5)"
            )

        lines.append("        self.wait(1)")
        lines.append("")

        return class_name, "\n".join(lines)

    # ── coordinate_plane ────────────────────────────────────────────── #

    def _build_coordinate_plane(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """NumberPlane grid with vectors, points, and optional parametric curves."""
        class_name = f"CoordPlaneScene{scene_index}"

        title = params.get("title", "")
        x_range = params.get("x_range", [-5, 5, 1])
        y_range = params.get("y_range", [-5, 5, 1])
        vectors: list[dict] = params.get("vectors", [])
        points: list[dict] = params.get("points", [])
        parametric_curve: dict | None = params.get("parametric_curve")

        lines = [
            "from manimlib import *",
            "import numpy as np",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
        ]

        self._emit_title(title, lines)

        lines.append(
            f"        plane = NumberPlane(x_range={x_range}, y_range={y_range})"
        )
        lines.append("        self.play(ShowCreation(plane), run_time=1.5)")
        self._emit_camera_focus("plane", 9, lines)

        # Vectors
        for i, vec in enumerate(vectors):
            end = self._pos3(vec.get("end", [1, 1, 0]))
            col = self._col(vec.get("color", "YELLOW"))
            lbl = vec.get("label", "")
            lines.append(
                f"        vec{i} = Arrow(ORIGIN, [{end[0]}, {end[1]}, {end[2]}], "
                f"color={col}, buff=0)"
            )
            lines.append(f"        self.play(ShowCreation(vec{i}), run_time=1)")
            if lbl:
                safe_lbl = self._safe_tex(lbl)
                lines.append(
                    f'        vlbl{i} = Tex(r"{safe_lbl}").set_color({col})'
                    f".next_to(vec{i}.get_end(), UP, buff=0.15)"
                )
                lines.append(f"        self.play(FadeIn(vlbl{i}))")

        # Points
        for i, pt in enumerate(points):
            pos = self._pos3(pt.get("position", [0, 0, 0]))
            col = self._col(pt.get("color", "RED"))
            lbl = pt.get("label", "")
            lines.append(
                f"        dot{i} = Dot([{pos[0]}, {pos[1]}, {pos[2]}], "
                f"color={col}, radius=0.08)"
            )
            lines.append(f"        self.play(FadeIn(dot{i}))")
            if lbl:
                safe_lbl = self._safe(lbl)
                lines.append(
                    f'        dlbl{i} = Text("{safe_lbl}", font_size=20, color={col})'
                    f".next_to(dot{i}, UR, buff=0.1)"
                )
                lines.append(f"        self.play(FadeIn(dlbl{i}))")

        # Parametric curve
        if parametric_curve:
            pc_func = parametric_curve.get(
                "func", "lambda t: [np.cos(t), np.sin(t), 0]"
            )
            pc_range = parametric_curve.get("t_range", [0, 6.28])
            pc_col = self._col(parametric_curve.get("color", "BLUE"))
            lines.append(
                f"        pcurve = ParametricCurve("
                f"{pc_func}, "
                f"t_range=[{pc_range[0]}, {pc_range[1]}], "
                f"color={pc_col})"
            )
            lines.append("        self.play(ShowCreation(pcurve), run_time=2)")

        lines.append("        self.wait(1)")
        lines.append("")

        return class_name, "\n".join(lines)

    # ── comparison ──────────────────────────────────────────────────── #

    def _build_comparison(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Split-screen comparison with a vertical dividing line, dimming
        logic, and safe-zone-compliant spacing."""
        class_name = f"ComparisonScene{scene_index}"

        title = params.get("title", "")
        left = params.get("left", {"label": "A", "content_tex": "x^2"})
        right = params.get("right", {"label": "B", "content_tex": "2x"})
        connector = params.get("connector", r"\Rightarrow")

        def _side(prefix: str, data: dict, x_pos: float, ls: list[str]) -> None:
            lbl = self._safe(data.get("label", ""))
            tex = self._safe_tex(data.get("content_tex", "x"))
            col = self._col(data.get("color", "BLUE"))

            ls.append(
                f'        {prefix}_label = Text("{lbl}", font_size=34, '
                f"weight=BOLD, color={col}).move_to([{x_pos}, 2.0, 0])"
            )
            self._emit_tex_safe(
                f"{prefix}_tex", tex, ls,
                color=col,
                position_suffix=f".move_to([{x_pos}, 0.5, 0])",
            )
            ls.append(
                f"        {prefix}_box = SurroundingRectangle("
                f"{prefix}_tex, color={col}, buff=0.3)"
            )

        lines = [
            "from manimlib import *",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
        ]

        self._emit_title(title, lines)

        # Vertical dividing line
        lines.append(
            "        divider = Line(UP*2.5, DOWN*2.5, "
            "color=GREY_B, stroke_width=1).move_to(ORIGIN)"
        )

        _side("left", left, -3.2, lines)
        _side("right", right, 3.2, lines)

        # Connector
        safe_conn = self._safe_tex(connector)
        self._emit_tex_safe(
            "conn", safe_conn, lines,
            scale=1.8,
            position_suffix=".move_to([0, -1.0, 0])",
        )

        # Animate left side
        lines.append(
            "        self.play(FadeIn(left_label), Write(left_tex), run_time=1)"
        )
        lines.append("        self.play(ShowCreation(left_box))")
        lines.append("        self.wait(2)")

        # Draw divider
        lines.append("        self.play(ShowCreation(divider), run_time=0.5)")
        lines.append("        self.wait(0.5)")

        # Dim left side to focus on right
        self._emit_dim_previous(
            ["left_label", "left_tex", "left_box"], 0.3, lines
        )

        # Connector
        lines.append("        self.play(Write(conn))")
        lines.append("        self.wait(1)")

        # Animate right side
        lines.append(
            "        self.play(FadeIn(right_label), Write(right_tex), run_time=1)"
        )
        lines.append("        self.play(ShowCreation(right_box))")
        lines.append("        self.wait(2)")

        # Restore left side for final view
        self._emit_dim_previous(
            ["left_label", "left_tex", "left_box"], 1.0, lines
        )

        self._emit_camera_focus("conn", 8, lines)
        lines.append("        self.wait(1)")
        lines.append("")

        return class_name, "\n".join(lines)

    # ── summary ─────────────────────────────────────────────────────── #

    def _build_summary(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """End-of-video recap: key items fade in one by one, final item
        gets Flash emphasis, camera pulls back."""
        class_name = f"SummaryScene{scene_index}"

        title = params.get("title", "Summary")
        items: list[dict] = params.get("items", [])
        if not items:
            # Fallback for missing items
            items = [{"tex": "?", "label": "No data", "color": "WHITE"}]

        lines = [
            "from manimlib import *",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
        ]

        self._emit_title(title, lines)

        lines.append("        items = VGroup()")

        for i, item in enumerate(items):
            tex = self._safe_tex(item.get("tex", "x"))
            lbl = self._safe(item.get("label", ""))
            col = self._col(item.get("color", "BLUE"))

            lines.append(f"        # Item {i}")
            lines.append(
                f"        dot{i} = Dot(radius=0.06, color={col})"
            )
            lines.append(
                f'        itex{i} = Tex(r"{tex}").set_color({col})'
            )
            if lbl:
                lines.append(
                    f'        ilbl{i} = Text("  — {lbl}", font_size=22, color=GREY_B)'
                )
                lines.append(
                    f"        row{i} = VGroup(dot{i}, itex{i}, ilbl{i})"
                    f".arrange(RIGHT, buff=0.2)"
                )
            else:
                lines.append(
                    f"        row{i} = VGroup(dot{i}, itex{i})"
                    f".arrange(RIGHT, buff=0.2)"
                )
            lines.append(f"        items.add(row{i})")

        lines.append("        items.arrange(DOWN, buff=0.5, aligned_edge=LEFT)")
        lines.append("        items.center()")
        if title:
            lines.append("        items.shift(DOWN * 0.3)")

        # Staggered fade in
        lines.append(
            "        self.play(LaggedStartMap(FadeIn, items, lag_ratio=0.35), run_time=2.5)"
        )
        lines.append("        self.wait(2)")

        # Flash the last item for emphasis
        if items:
            last = len(items) - 1
            lines.append(f"        self.play(Indicate(row{last}, color=YELLOW))")

        # Camera pulls back
        lines.append(
            "        self.play("
            "self.camera.frame.animate.set_height(9), run_time=1.5)"
        )
        lines.append("        self.wait(1)")
        lines.append("")

        return class_name, "\n".join(lines)

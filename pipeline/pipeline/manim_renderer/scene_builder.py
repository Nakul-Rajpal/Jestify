"""Generates ManimGL scene Python files from SceneInstruction data."""

import logging
from pathlib import Path

from shared.contracts.pipeline_schema import SceneInstruction

logger = logging.getLogger(__name__)


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
        "text": "_build_text",
        "geometry": "_build_geometry",
    }

    def build_scene_file(
        self, scene: SceneInstruction, output_py_path: str
    ) -> str:
        """Build a ``.py`` scene file and return the ManimGL class name."""
        scene_type = scene.manim_scene_type
        builder_name = self._BUILDERS.get(scene_type)

        if builder_name is None:
            logger.warning(
                "Unknown scene type '%s', falling back to text", scene_type
            )
            builder_name = "_build_text"

        builder = getattr(self, builder_name)
        class_name, source = builder(scene.manim_parameters, scene.scene_index)

        Path(output_py_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_py_path).write_text(source, encoding="utf-8")

        logger.info("[scene_builder] Built scene file %s (class=%s, type=%s)", output_py_path, class_name, scene_type)
        logger.info("[scene_builder] Generated source (%d chars):\n%s", len(source), source)

        return class_name

    # --------------------------------------------------------------------- #
    # Template builders -- each returns (class_name, full_source_code)
    # --------------------------------------------------------------------- #

    def _build_equation(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """LaTeX rendering with step-by-step transforms."""
        class_name = f"EquationScene{scene_index}"
        steps = params.get("steps", None)
        # LLM may use "latex" (single string) instead of "steps" (list)
        if steps is None:
            latex = params.get("latex", r"x = 1")
            steps = [latex] if isinstance(latex, str) else list(latex)
        elif isinstance(steps, str):
            steps = [steps]
        title = params.get("title", "")

        lines = [
            "from manimlib import *",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
        ]

        if title:
            safe_title = title.replace('"', '\\"')
            lines.append(f'        title = Text("{safe_title}").to_edge(UP)')
            lines.append("        self.play(Write(title))")
            lines.append("        self.wait(0.5)")

        for i, latex in enumerate(steps):
            safe_latex = latex.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'        eq{i} = Tex(r"{safe_latex}")')
            if i == 0:
                lines.append(f"        self.play(Write(eq{i}))")
            else:
                lines.append(f"        self.play(TransformMatchingTex(eq{i - 1}, eq{i}))")
            lines.append("        self.wait(1)")

        lines.append("        self.wait(1)")
        lines.append("")

        return class_name, "\n".join(lines)

    def _build_graph(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Function plotting on axes."""
        class_name = f"GraphScene{scene_index}"
        func_str = params.get("func_str", None) or params.get("function", "x**2")
        x_range = params.get("x_range", [-5, 5, 1])
        y_range = params.get("y_range", [-5, 5, 1])
        # Ensure ranges have 3 elements [min, max, step]
        if len(x_range) == 2:
            x_range = [x_range[0], x_range[1], 1]
        if len(y_range) == 2:
            y_range = [y_range[0], y_range[1], 1]
        title = params.get("title", "")
        color = params.get("color", "BLUE")

        lines = [
            "from manimlib import *",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
        ]

        if title:
            safe_title = title.replace('"', '\\"')
            lines.append(f'        title = Text("{safe_title}").to_edge(UP)')
            lines.append("        self.play(Write(title))")
            lines.append("        self.wait(0.5)")

        lines.append(f"        axes = Axes(")
        lines.append(f"            x_range={x_range},")
        lines.append(f"            y_range={y_range},")
        lines.append(f"        )")
        lines.append(f"        axes.add_coordinate_labels()")
        lines.append(f"        graph = axes.get_graph(lambda x: {func_str}, color={color})")
        lines.append(f"        self.play(ShowCreation(axes))")
        lines.append(f"        self.wait(0.5)")
        lines.append(f"        self.play(ShowCreation(graph), run_time=2)")
        lines.append(f"        self.wait(1)")
        lines.append("")

        return class_name, "\n".join(lines)

    def _build_diagram(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Nodes + edges diagrams."""
        class_name = f"DiagramScene{scene_index}"
        nodes = params.get("nodes", [{"label": "A", "position": [0, 0, 0]}])
        edges = params.get("edges", [])

        lines = [
            "from manimlib import *",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
        ]

        # Build label-to-index mapping for edge resolution
        label_to_idx: dict[str, int] = {}
        for i, node in enumerate(nodes):
            label = node.get("label", f"N{i}") if isinstance(node, dict) else f"N{i}"
            label_to_idx[label] = i

        for i, node in enumerate(nodes):
            if isinstance(node, dict):
                label = node.get("label", f"N{i}")
                raw_pos = node.get("position", [0, 0, 0])
            else:
                label = f"N{i}"
                raw_pos = [0, 0, 0]
            pos = list(raw_pos) + [0] * (3 - len(raw_pos))
            safe_label = label.replace('"', '\\"')
            lines.append(f'        node{i} = Text("{safe_label}").move_to([{pos[0]}, {pos[1]}, {pos[2]}])')
            lines.append(f"        self.play(FadeIn(node{i}))")

        lines.append("        self.wait(0.5)")

        for edge in edges:
            try:
                from_idx, to_idx = self._resolve_edge(edge, label_to_idx, len(nodes))
                lines.append(f"        edge_{from_idx}_{to_idx} = Arrow(node{from_idx}.get_center(), node{to_idx}.get_center(), buff=0.3)")
                lines.append(f"        self.play(ShowCreation(edge_{from_idx}_{to_idx}))")
            except (ValueError, KeyError, IndexError) as e:
                logger.warning("[scene_builder] Skipping invalid edge %s: %s", edge, e)

        lines.append("        self.wait(1)")
        lines.append("")

        return class_name, "\n".join(lines)

    @staticmethod
    def _resolve_edge(edge, label_to_idx: dict[str, int], num_nodes: int) -> tuple[int, int]:
        """Resolve an edge to (from_index, to_index) regardless of format.

        Handles:
          - [0, 1]               -- index pair
          - {"from": "A", "to": "B"}   -- label dict
          - {"from": 0, "to": 1}       -- index dict
          - [0, 1, "label"]             -- index pair with extra data
        """
        if isinstance(edge, dict):
            src = edge.get("from", edge.get("source", edge.get("from_idx", 0)))
            dst = edge.get("to", edge.get("target", edge.get("to_idx", 1)))
            # Resolve labels to indices
            if isinstance(src, str):
                src = label_to_idx.get(src, 0)
            if isinstance(dst, str):
                dst = label_to_idx.get(dst, 0)
            return int(src), int(dst)
        elif isinstance(edge, (list, tuple)):
            return int(edge[0]), int(edge[1])
        else:
            raise ValueError(f"Unknown edge format: {edge}")

    def _build_text(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Animated bullet points."""
        class_name = f"TextScene{scene_index}"
        bullets = params.get("bullets", ["Point 1"])
        title = params.get("title", "")

        lines = [
            "from manimlib import *",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
        ]

        if title:
            safe_title = title.replace('"', '\\"')
            lines.append(f'        title = Text("{safe_title}", font_size=48).to_edge(UP)')
            lines.append("        self.play(Write(title))")
            lines.append("        self.wait(0.5)")

        for i, bullet_text in enumerate(bullets):
            safe = bullet_text.replace('"', '\\"')
            y_offset = 1.5 - i * 0.8
            lines.append(f'        bullet{i} = Text("\\u2022 {safe}", font_size=32).move_to([0, {y_offset}, 0])')
            lines.append(f"        self.play(FadeIn(bullet{i}, shift=RIGHT))")
            lines.append("        self.wait(0.5)")

        lines.append("        self.wait(1)")
        lines.append("")

        return class_name, "\n".join(lines)

    def _build_geometry(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Geometric constructions."""
        class_name = f"GeometryScene{scene_index}"
        shapes = params.get("shapes", [{"type": "circle"}])
        title = params.get("title", "")

        lines = [
            "from manimlib import *",
            "",
            f"class {class_name}(Scene):",
            "    def construct(self):",
        ]

        if title:
            safe_title = title.replace('"', '\\"')
            lines.append(f'        title = Text("{safe_title}").to_edge(UP)')
            lines.append("        self.play(Write(title))")
            lines.append("        self.wait(0.5)")

        for i, shape in enumerate(shapes):
            shape_type = shape.get("type", "circle")
            color = shape.get("color", "WHITE")
            raw_pos = shape.get("position", [0, 0, 0])
            pos = list(raw_pos) + [0] * (3 - len(raw_pos))

            if shape_type == "circle":
                radius = shape.get("radius", 1.0)
                lines.append(f"        shape{i} = Circle(radius={radius}, color={color}).move_to([{pos[0]}, {pos[1]}, {pos[2]}])")
            elif shape_type == "square":
                side = shape.get("side_length", 2.0)
                lines.append(f"        shape{i} = Square(side_length={side}, color={color}).move_to([{pos[0]}, {pos[1]}, {pos[2]}])")
            elif shape_type == "triangle":
                lines.append(f"        shape{i} = Triangle(color={color}).move_to([{pos[0]}, {pos[1]}, {pos[2]}])")
            elif shape_type == "line":
                raw_start = shape.get("start", [-2, 0, 0])
                raw_end = shape.get("end", [2, 0, 0])
                start = list(raw_start) + [0] * (3 - len(raw_start))
                end = list(raw_end) + [0] * (3 - len(raw_end))
                lines.append(f"        shape{i} = Line([{start[0]}, {start[1]}, {start[2]}], [{end[0]}, {end[1]}, {end[2]}], color={color})")
            else:
                lines.append(f"        shape{i} = Circle(color={color}).move_to([{pos[0]}, {pos[1]}, {pos[2]}])")

            lines.append(f"        self.play(ShowCreation(shape{i}))")
            lines.append("        self.wait(0.5)")

        lines.append("        self.wait(1)")
        lines.append("")

        return class_name, "\n".join(lines)

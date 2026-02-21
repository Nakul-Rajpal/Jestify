"""Generates ManimGL scene Python files from SceneInstruction data."""

import logging
import textwrap
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
        """Build a ``.py`` scene file and return the ManimGL class name.

        Parameters
        ----------
        scene : SceneInstruction
            Scene data from the generated script.
        output_py_path : str
            Destination path for the generated Python file.

        Returns
        -------
        str
            The class name of the generated ManimGL scene.
        """
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
        logger.info("Built scene file %s (class=%s)", output_py_path, class_name)

        return class_name

    # --------------------------------------------------------------------- #
    # Template builders -- each returns (class_name, full_source_code)
    # --------------------------------------------------------------------- #

    def _build_equation(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """LaTeX rendering with step-by-step transforms.

        Expected params:
            steps: list[str]  -- LaTeX strings for each step
            title: str        -- optional title text
        """
        class_name = f"EquationScene{scene_index}"
        steps = params.get("steps", [r"x = 1"])
        title = params.get("title", "")

        # Build the transform chain
        step_lines = []
        for i, latex in enumerate(steps):
            safe_latex = latex.replace("\\", "\\\\").replace('"', '\\"')
            if i == 0:
                step_lines.append(
                    f'        eq{i} = Tex(r"{safe_latex}")'
                )
                step_lines.append(f"        self.play(Write(eq{i}))")
                step_lines.append("        self.wait(1)")
            else:
                step_lines.append(
                    f'        eq{i} = Tex(r"{safe_latex}")'
                )
                step_lines.append(
                    f"        self.play(TransformMatchingTex(eq{i - 1}, eq{i}))"
                )
                step_lines.append("        self.wait(1)")

        title_block = ""
        if title:
            safe_title = title.replace('"', '\\"')
            title_block = textwrap.dedent(f"""\
                title = Text("{safe_title}").to_edge(UP)
                self.play(Write(title))
                self.wait(0.5)
        """)

        steps_code = "\n".join(step_lines)

        source = textwrap.dedent(f"""\
            from manimlib import *

            class {class_name}(Scene):
                def construct(self):
                    {textwrap.indent(title_block, "        ").strip()}
            {steps_code}
                    self.wait(1)
        """)

        return class_name, source

    def _build_graph(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Function plotting on axes.

        Expected params:
            func_str: str          -- Python expression in terms of x (e.g. "x**2")
            x_range: list[float]   -- [min, max, step]
            y_range: list[float]   -- [min, max, step]
            title: str             -- optional
            color: str             -- optional, default "BLUE"
        """
        class_name = f"GraphScene{scene_index}"
        func_str = params.get("func_str", "x**2")
        x_range = params.get("x_range", [-5, 5, 1])
        y_range = params.get("y_range", [-5, 5, 1])
        title = params.get("title", "")
        color = params.get("color", "BLUE")

        title_block = ""
        if title:
            safe_title = title.replace('"', '\\"')
            title_block = textwrap.dedent(f"""\
                title = Text("{safe_title}").to_edge(UP)
                self.play(Write(title))
                self.wait(0.5)
            """)

        source = textwrap.dedent(f"""\
            from manimlib import *

            class {class_name}(Scene):
                def construct(self):
                    {textwrap.indent(title_block, "            ").strip()}
                    axes = Axes(
                        x_range={x_range},
                        y_range={y_range},
                    )
                    axes.add_coordinate_labels()

                    graph = axes.get_graph(lambda x: {func_str}, color={color})

                    self.play(ShowCreation(axes))
                    self.wait(0.5)
                    self.play(ShowCreation(graph), run_time=2)
                    self.wait(1)
        """)

        return class_name, source

    def _build_diagram(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Nodes + edges diagrams.

        Expected params:
            nodes: list[dict]  -- [{label, position: [x,y,z]}]
            edges: list[list]  -- [[from_idx, to_idx], ...]
        """
        class_name = f"DiagramScene{scene_index}"
        nodes = params.get("nodes", [{"label": "A", "position": [0, 0, 0]}])
        edges = params.get("edges", [])

        node_lines = []
        for i, node in enumerate(nodes):
            label = node.get("label", f"N{i}")
            raw_pos = node.get("position", [0, 0, 0])
            # Normalize to 3D — handle [x,y] or [x,y,z]
            pos = list(raw_pos) + [0] * (3 - len(raw_pos))
            safe_label = label.replace('"', '\\"')
            node_lines.append(
                f'        node{i} = Text("{safe_label}").move_to([{pos[0]}, {pos[1]}, {pos[2]}])'
            )
            node_lines.append(
                f"        self.play(FadeIn(node{i}))"
            )

        edge_lines = []
        for from_idx, to_idx in edges:
            edge_lines.append(
                f"        edge_{from_idx}_{to_idx} = Arrow(node{from_idx}.get_center(), node{to_idx}.get_center(), buff=0.3)"
            )
            edge_lines.append(
                f"        self.play(ShowCreation(edge_{from_idx}_{to_idx}))"
            )

        nodes_code = "\n".join(node_lines)
        edges_code = "\n".join(edge_lines)

        source = textwrap.dedent(f"""\
            from manimlib import *

            class {class_name}(Scene):
                def construct(self):
            {nodes_code}
                    self.wait(0.5)
            {edges_code}
                    self.wait(1)
        """)

        return class_name, source

    def _build_text(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Animated bullet points.

        Expected params:
            bullets: list[str]  -- text for each bullet
            title: str          -- optional heading
        """
        class_name = f"TextScene{scene_index}"
        bullets = params.get("bullets", ["Point 1"])
        title = params.get("title", "")

        title_block = ""
        if title:
            safe_title = title.replace('"', '\\"')
            title_block = textwrap.dedent(f"""\
                title = Text("{safe_title}", font_size=48).to_edge(UP)
                self.play(Write(title))
                self.wait(0.5)
            """)

        bullet_lines = []
        for i, bullet_text in enumerate(bullets):
            safe = bullet_text.replace('"', '\\"')
            y_offset = 1.5 - i * 0.8
            bullet_lines.append(
                f'        bullet{i} = Text("\\u2022 {safe}", font_size=32).move_to([0, {y_offset}, 0])'
            )
            bullet_lines.append(
                f"        self.play(FadeIn(bullet{i}, shift=RIGHT))"
            )
            bullet_lines.append("        self.wait(0.5)")

        bullets_code = "\n".join(bullet_lines)

        source = textwrap.dedent(f"""\
            from manimlib import *

            class {class_name}(Scene):
                def construct(self):
                    {textwrap.indent(title_block, "            ").strip()}
            {bullets_code}
                    self.wait(1)
        """)

        return class_name, source

    def _build_geometry(
        self, params: dict, scene_index: int
    ) -> tuple[str, str]:
        """Geometric constructions.

        Expected params:
            shapes: list[dict]  -- [{type: "circle"|"square"|"triangle"|"line", ...}]
            title: str          -- optional
        """
        class_name = f"GeometryScene{scene_index}"
        shapes = params.get("shapes", [{"type": "circle"}])
        title = params.get("title", "")

        title_block = ""
        if title:
            safe_title = title.replace('"', '\\"')
            title_block = textwrap.dedent(f"""\
                title = Text("{safe_title}").to_edge(UP)
                self.play(Write(title))
                self.wait(0.5)
            """)

        shape_lines = []
        for i, shape in enumerate(shapes):
            shape_type = shape.get("type", "circle")
            color = shape.get("color", "WHITE")
            raw_pos = shape.get("position", [0, 0, 0])
            pos = list(raw_pos) + [0] * (3 - len(raw_pos))

            if shape_type == "circle":
                radius = shape.get("radius", 1.0)
                shape_lines.append(
                    f"        shape{i} = Circle(radius={radius}, color={color}).move_to([{pos[0]}, {pos[1]}, {pos[2]}])"
                )
            elif shape_type == "square":
                side = shape.get("side_length", 2.0)
                shape_lines.append(
                    f"        shape{i} = Square(side_length={side}, color={color}).move_to([{pos[0]}, {pos[1]}, {pos[2]}])"
                )
            elif shape_type == "triangle":
                shape_lines.append(
                    f"        shape{i} = Triangle(color={color}).move_to([{pos[0]}, {pos[1]}, {pos[2]}])"
                )
            elif shape_type == "line":
                raw_start = shape.get("start", [-2, 0, 0])
                raw_end = shape.get("end", [2, 0, 0])
                start = list(raw_start) + [0] * (3 - len(raw_start))
                end = list(raw_end) + [0] * (3 - len(raw_end))
                shape_lines.append(
                    f"        shape{i} = Line([{start[0]}, {start[1]}, {start[2]}], [{end[0]}, {end[1]}, {end[2]}], color={color})"
                )
            else:
                shape_lines.append(
                    f"        shape{i} = Circle(color={color}).move_to([{pos[0]}, {pos[1]}, {pos[2]}])"
                )

            shape_lines.append(
                f"        self.play(ShowCreation(shape{i}))"
            )
            shape_lines.append("        self.wait(0.5)")

        shapes_code = "\n".join(shape_lines)

        source = textwrap.dedent(f"""\
            from manimlib import *

            class {class_name}(Scene):
                def construct(self):
                    {textwrap.indent(title_block, "            ").strip()}
            {shapes_code}
                    self.wait(1)
        """)

        return class_name, source

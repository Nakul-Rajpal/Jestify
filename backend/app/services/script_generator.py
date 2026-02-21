"""Service for generating educational scripts using the Anthropic Claude API.

Scene types are designed for 3Blue1Brown-quality ManimGL animations.
The LLM must analyze the source material and create graphs, equations,
and visual content that directly explain the material.
"""

import json
import logging
from typing import Optional

import anthropic

from shared.contracts.character_schema import CHARACTER_PERSONALITIES
from shared.contracts.enums import Character, Difficulty
from shared.contracts.pipeline_schema import GeneratedScript

from ..config import settings

logger = logging.getLogger(__name__)

# Model to use for script generation
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# -------------------------------------------------------------------- #
# Difficulty-specific instructions
# -------------------------------------------------------------------- #

DIFFICULTY_INSTRUCTIONS: dict[Difficulty, str] = {
    Difficulty.BEGINNER: (
        "Explain concepts at a beginner level. Use simple language, avoid jargon, "
        "and break down ideas into the most fundamental building blocks. "
        "Assume no prior knowledge of the topic."
    ),
    Difficulty.INTERMEDIATE: (
        "Explain concepts at an intermediate level. You can use some technical terms "
        "but always briefly clarify them. Build on foundational knowledge and make "
        "connections between concepts."
    ),
    Difficulty.ADVANCED: (
        "Explain concepts at an advanced level. Use proper technical terminology, "
        "explore nuances, edge cases, and deeper implications. Assume a solid "
        "foundation in the subject area."
    ),
}

# -------------------------------------------------------------------- #
# Available ManimGL scene types — 10 types
# -------------------------------------------------------------------- #

AVAILABLE_SCENE_TYPES = """\
Available ManimGL scene types (10 types). Choose the most visual one for each concept.
You MUST use "graph" scenes when the material involves any functions, data, or \
quantitative relationships. Graphs are the most important visual tool.

1. "equation" — Step-by-step LaTeX equation transforms with colour highlighting and annotations.
   Parameters:
   {
     "steps": ["x^2 + 1", "x^2 + 1 = 0", "x^2 = -1"],
     "title": "Solving the Quadratic Equation",
     "color_map": {"x^2": "YELLOW", "-1": "RED"},
     "highlight_steps": [1],
     "annotations": [{"target_tex": "x^2", "text": "squared variable", "direction": "UP"}]
   }
   Use for: derivations, proofs, algebraic manipulation.

2. "graph" — Function plotting with area shading, tangent lines, tracing dots, and overlays.
   THIS IS THE MOST IMPORTANT SCENE TYPE. Use it whenever the material involves functions,
   data trends, rates of change, optimization, or any quantitative relationship.
   Parameters:
   {
     "func_str": "x**2",
     "x_range": [-5, 5, 1], "y_range": [0, 25, 5],
     "title": "The Parabola and Its Derivative",
     "color": "BLUE",
     "show_area": {"x_min": 0, "x_max": 3, "color": "BLUE_E", "opacity": 0.3},
     "show_tangent": {"x_value": 2, "color": "YELLOW"},
     "trace_dot": true,
     "label": "f(x) = x^2",
     "secondary_funcs": [{"func_str": "2*x", "color": "GREEN", "label": "f'(x) = 2x"}]
   }
   IMPORTANT: func_str must be valid Python using x as the variable. Use ** for powers,
   np.sin/np.cos/np.exp/np.log for math functions. Examples:
   - "x**2 - 3*x + 2"
   - "np.sin(x)"
   - "np.exp(-x**2)"
   - "1 / (1 + np.exp(-x))"

3. "diagram" — Nodes inside coloured boxes connected by labelled arrows.
   Parameters:
   {
     "nodes": [
       {"label": "Input", "position": [-4, 0], "color": "BLUE"},
       {"label": "Process", "position": [0, 0], "color": "GREEN"},
       {"label": "Output", "position": [4, 0], "color": "RED"}
     ],
     "edges": [[0, 1], [1, 2]],
     "edge_labels": ["data", "result"]
   }
   Use for: flowcharts, process diagrams, system architecture.

4. "concept_reveal" — Visual concept cards with coloured boxes and emphasis animations.
   Parameters:
   {
     "title": "Key Concepts",
     "concepts": [
       {"text": "Derivative", "color": "BLUE", "emphasis": true},
       {"text": "Integral", "color": "GREEN", "emphasis": false},
       {"text": "Limit", "color": "YELLOW", "emphasis": false}
     ],
     "arrangement": "vertical"
   }
   arrangement options: "vertical", "horizontal", "grid"
   Use for: introducing key terms, listing properties, definitions. ALWAYS use this instead of "text".

5. "geometry" — Geometric shapes with labels, fill, and staggered construction animation.
   Parameters:
   {
     "shapes": [
       {"type": "circle", "radius": 2.0, "color": "BLUE", "position": [0, 0], "fill_opacity": 0.2, "label": "r = 2"},
       {"type": "line", "start": [0, 0], "end": [2, 0], "color": "YELLOW", "label": "radius"}
     ],
     "title": "Circle Construction"
   }
   Shape types: circle, square, triangle, line.
   Use for: geometric proofs, shape properties, spatial reasoning.

6. "number_line" — Animated number line with labelled points, shaded intervals, and travelling dot.
   Parameters:
   {
     "title": "The Number Line",
     "range": [-5, 5, 1],
     "points": [
       {"value": 2, "label": "a = 2", "color": "YELLOW"},
       {"value": -1, "label": "b = -1", "color": "RED"}
     ],
     "intervals": [
       {"start": -1, "end": 2, "color": "GREEN", "label": "interval"}
     ],
     "animate_dot": {"from": -3, "to": 3, "color": "WHITE"}
   }
   Use for: inequalities, intervals, limits, sequences.

7. "coordinate_plane" — 2D grid with vectors, points, and parametric curves.
   Parameters:
   {
     "title": "Coordinate System",
     "x_range": [-5, 5, 1], "y_range": [-5, 5, 1],
     "vectors": [
       {"end": [3, 2], "color": "YELLOW", "label": "\\vec{v}"}
     ],
     "points": [
       {"position": [1, 1], "label": "P(1,1)", "color": "RED"}
     ],
     "parametric_curve": {
       "func": "lambda t: [np.cos(t), np.sin(t), 0]",
       "t_range": [0, 6.28],
       "color": "BLUE"
     }
   }
   Use for: vectors, linear algebra, parametric equations, coordinate geometry.

8. "comparison" — Side-by-side layout comparing two mathematical objects with a connector.
   Parameters:
   {
     "title": "Comparison",
     "left": {"label": "Before", "content_tex": "\\int_0^1 x\\,dx", "color": "BLUE"},
     "right": {"label": "After", "content_tex": "\\frac{1}{2}", "color": "GREEN"},
     "connector": "\\Rightarrow"
   }
   Use for: before/after transformations, equivalent expressions, method comparison.

9. "summary" — End-of-video recap with key results and emphasis animation.
   Parameters:
   {
     "title": "Summary",
     "items": [
       {"tex": "f(x) = x^2", "label": "Quadratic function", "color": "BLUE"},
       {"tex": "f'(x) = 2x", "label": "Derivative", "color": "GREEN"},
       {"tex": "\\int_0^1 x^2\\,dx = \\frac{1}{3}", "label": "Integral", "color": "YELLOW"}
     ]
   }
   Use for: the LAST scene of every video — always end with a summary.

IMPORTANT — NEVER use "text" as a scene type. Use "concept_reveal" instead.
Valid values: equation, graph, diagram, concept_reveal, geometry, number_line, \
coordinate_plane, comparison, summary.
"""

# -------------------------------------------------------------------- #
# Scene composition guidelines (3B1B quality)
# -------------------------------------------------------------------- #

SCENE_COMPOSITION_GUIDELINES = """\
ANIMATION QUALITY GUIDELINES — follow strictly:

1. NEVER use plain bullet points or text-only scenes. Every concept MUST be visualized
   with mathematical objects, shapes, graphs, or coloured concept cards.
2. ANALYZE THE SOURCE MATERIAL CAREFULLY. Identify:
   - What mathematical functions or relationships are described
   - What types of problems are being solved
   - What graphs would help explain the concepts
   Then CREATE GRAPH SCENES that directly visualize these relationships.
3. AT LEAST ONE SCENE MUST BE A "graph" TYPE with actual mathematical functions
   from the source material. If the material covers:
   - Calculus: plot the function AND its derivative using secondary_funcs
   - Algebra: plot the equation to show its roots/behavior
   - Statistics: plot the distribution or trend
   - Physics: plot the relationship (distance-time, force-displacement, etc.)
   - Economics: plot supply/demand, cost functions, etc.
4. For mathematical derivations: use "equation" with color_map to highlight the parts
   that change between steps, and annotations to explain what terms mean.
5. For function analysis: use "graph" with show_area, show_tangent, or trace_dot
   to bring the function to life — do not just plot a static curve.
6. For introducing concepts: use "concept_reveal" with coloured boxes and emphasis.
7. For the LAST scene of every video: use "summary" to recap key results visually.
8. Each scene should have ONE clear visual focus.
9. Use colour deliberately:
   - BLUE for primary functions and concepts
   - YELLOW for highlights, emphasis, and tangent lines
   - GREEN for secondary elements, derivatives, and results
   - RED for warnings, constraints, negative values
10. Scene flow should build progressively:
    concept_reveal (introduce) → equation (derive) → graph (visualize) → summary (recap).
"""


class ScriptGenerator:
    """Generates structured educational scripts using Claude."""

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def generate(
        self,
        extracted_text: str,
        character: Character,
        difficulty: Difficulty,
        user_prompt: Optional[str] = None,
    ) -> GeneratedScript:
        """Generate an educational script from the provided text."""
        personality = CHARACTER_PERSONALITIES[character]
        difficulty_instruction = DIFFICULTY_INSTRUCTIONS[difficulty]

        system_prompt = self._build_system_prompt(personality, difficulty_instruction)
        user_message = self._build_user_message(extracted_text, user_prompt)

        logger.info(
            "Generating script: character=%s, difficulty=%s, text_length=%d",
            character.value,
            difficulty.value,
            len(extracted_text),
        )

        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        response_text = response.content[0].text
        script_data = self._parse_response(response_text)

        script_data["character"] = character.value
        script_data["difficulty"] = difficulty.value
        script_data["language"] = "en"

        return GeneratedScript(**script_data)

    def _build_system_prompt(self, personality, difficulty_instruction: str) -> str:
        """Build the system prompt for 3B1B-quality script generation."""
        return f"""\
You are an educational content script writer. Your job is to create engaging, \
educational video scripts that will be animated using ManimGL (a math animation \
library). The animations must be of 3Blue1Brown quality — rich, visual, and \
mathematically precise.

You MUST carefully analyze the source material to understand what mathematical \
concepts, functions, and relationships it contains, then create scenes that \
VISUALLY explain them with graphs, equations, and animations — NOT just text.

CHARACTER PERSONA:
- Name: {personality.display_name}
- Voice Style: {personality.voice_style}
- Analogy Domain: {personality.analogy_domain}
- Catchphrases: {', '.join(personality.catchphrases)}
- Tone: {personality.tone}

You MUST write all narration text in the voice and style of this character. \
Use their catchphrases naturally, draw analogies from their domain, and \
maintain their tone throughout.

DIFFICULTY LEVEL:
{difficulty_instruction}

{AVAILABLE_SCENE_TYPES}

{SCENE_COMPOSITION_GUIDELINES}

OUTPUT FORMAT:
You must respond with ONLY a valid JSON object (no markdown, no extra text) with this exact structure:
{{
    "title": "A catchy educational title",
    "total_scenes": <number of scenes>,
    "scenes": [
        {{
            "scene_index": 0,
            "narration_text": "What the character says during this scene",
            "manim_scene_type": "equation|graph|diagram|concept_reveal|geometry|number_line|coordinate_plane|comparison|summary",
            "manim_parameters": {{ ... parameters specific to the scene type ... }},
            "duration_hint_seconds": 10.0,
            "character_action": "talking|pointing|idle"
        }}
    ],
    "intro_text": "An engaging introduction by the character",
    "outro_text": "A memorable closing by the character"
}}

STRICT RULES:
- Target a ~5 minute video: create exactly 4-5 scenes.
- Set duration_hint_seconds to 60-90 per scene (this controls the actual video length!).
- The LAST scene MUST be "summary" — always end with a visual recap.
- NEVER use "text" as manim_scene_type — use "concept_reveal" instead.
- AT LEAST ONE scene MUST be a "graph" type that plots actual functions from the material.
- AT LEAST ONE scene MUST be an "equation" type showing derivation steps from the material.
- Include color_map in equation scenes to highlight changing parts.
- In graph scenes, use show_area, show_tangent, trace_dot, or secondary_funcs — never a bare static plot.
- func_str in graph scenes must be valid Python: use ** for powers, np.sin/np.cos/np.exp/np.log for math.

LATEX RULES (CRITICAL — violations cause rendering failures):
- Use ONLY simple inline LaTeX. Examples: "x^2 + 3x - 1", "\\frac{{a}}{{b}}", "\\sum_{{n=1}}^{{N}} a_n"
- NEVER use LaTeX environments: NO \\begin{{...}} or \\end{{...}} of any kind.
- NEVER use: pmatrix, bmatrix, matrix, align, cases, array, tabular, gathered, split.
- For matrices: write them as plain text like "A = [0, 4, 3; 0, -6, 2]" or split into separate equations.
- For piecewise functions: use separate equation steps instead of \\begin{{cases}}.
- Keep each LaTeX string to a SINGLE LINE of math — no multi-line constructs.
- Use single backslashes: \\frac, \\sum, \\int — NOT double backslashes.
- Keep narration concise: 2-3 sentences per scene.
"""

    def _build_user_message(self, extracted_text: str, user_prompt: Optional[str]) -> str:
        """Build the user message with source material."""
        message = f"""\
Please create an educational video script based on the following source material.
IMPORTANT: Carefully analyze what mathematical concepts, functions, and problems \
are in this material. Then create graph scenes that plot the actual functions and \
equation scenes that show the actual derivations from the material.

--- SOURCE MATERIAL ---
{extracted_text}
--- END SOURCE MATERIAL ---
"""
        if user_prompt:
            message += f"""
Additional instructions from the user:
{user_prompt}
"""

        message += """
Remember: respond with ONLY the JSON object, no markdown code fences or extra text.
At least one scene must be a "graph" that plots functions from the material.
"""
        return message

    def _parse_response(self, response_text: str) -> dict:
        """Parse the LLM response text into a dictionary."""
        text = response_text.strip()

        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s", e)
            logger.error("Response text: %s", text[:500])
            raise ValueError(f"LLM did not return valid JSON: {e}")

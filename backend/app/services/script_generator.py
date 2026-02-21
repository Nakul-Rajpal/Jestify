"""Service for generating educational scripts using the Anthropic Claude API.

Claude generates complete ManimGL Python code for each scene, producing
3Blue1Brown-quality animations with full LaTeX support (bmatrix, align, etc.).
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
# ManimGL code generation reference
# -------------------------------------------------------------------- #

MANIMGL_REFERENCE = r"""
You write complete ManimGL Python code for each scene. Each scene is a standalone
Python file with one Scene class. The code will be executed by ManimGL to render
an animation clip.

EXAMPLE OF HIGH-QUALITY MANIMGL CODE:

```python
from manimlib import *
import numpy as np

class SVDDecomposition(Scene):
    def construct(self):
        # --- Title ---
        title = Text("Singular Value Decomposition", font_size=48, color=BLUE)
        subtitle = Text("Finding U, Sigma, and V", font_size=36).next_to(title, DOWN)
        self.play(Write(title), FadeIn(subtitle, UP))
        self.wait(3)
        self.play(FadeOut(title), FadeOut(subtitle))

        # --- Show the matrix ---
        matrix_a = Tex(r"A = \begin{bmatrix} 0 & 4 & 3 \\ 0 & -6 & 2 \end{bmatrix}")
        matrix_a.to_edge(UP)
        self.play(Write(matrix_a))
        self.wait(4)

        # --- Compute A^T A ---
        ata_text = Tex(r"A^T A = \begin{bmatrix} 0 & 0 \\ 4 & -6 \\ 3 & 2 \end{bmatrix} \begin{bmatrix} 0 & 4 & 3 \\ 0 & -6 & 2 \end{bmatrix}")
        ata_result = Tex(r"A^T A = \begin{bmatrix} 0 & 0 & 0 \\ 0 & 52 & 0 \\ 0 & 0 & 13 \end{bmatrix}")

        self.play(Write(ata_text))
        self.wait(5)
        self.play(ReplacementTransform(ata_text, ata_result))

        hint = Text("It's a diagonal matrix!", color=YELLOW, font_size=30).next_to(ata_result, DOWN)
        self.play(Write(hint))
        self.wait(4)

        # --- Eigenvalues ---
        eigenvalues = Tex(r"\lambda_1 = 52, \quad \lambda_2 = 13, \quad \lambda_3 = 0")
        eigenvalues.next_to(hint, DOWN * 2)
        self.play(Write(eigenvalues))
        self.wait(4)

        self.play(FadeOut(Group(matrix_a, ata_result, hint, eigenvalues)))
```

KEY MANIMGL PATTERNS TO USE:
- `from manimlib import *` and `import numpy as np` at the top
- One class per file inheriting from `Scene`
- `Tex(r"...")` for LaTeX math (supports \begin{bmatrix}, \frac, etc.)
- `Text("...", font_size=N, color=COLOR)` for plain text
- `self.play(Write(...))` to animate writing
- `self.play(ReplacementTransform(old, new))` for morphing between expressions
- `self.play(FadeIn(...))`, `self.play(FadeOut(...))` for appear/disappear
- `self.play(FadeOut(Group(...)))` to fade out multiple objects at once
- `.to_edge(UP/DOWN/LEFT/RIGHT)`, `.next_to(obj, DOWN)`, `.shift(UP * 2)`
- `self.wait(N)` for pauses (use 3-5 seconds for explanation pauses)
- `Axes(x_range=[...], y_range=[...])` for graphs
- `axes.get_graph(func, color=COLOR)` for plotting
- `ShowCreation(obj)` for drawing shapes/graphs
- `Indicate(obj, color=YELLOW)` for emphasis
- `SurroundingRectangle(obj, color=COLOR)` for highlighting
- `VGroup(...)` and `.arrange(DOWN, buff=0.5)` for grouping
- `Brace(obj, direction)` with `.next_to()` for annotations

COLORS: BLUE, RED, GREEN, YELLOW, ORANGE, PURPLE, TEAL, GOLD, MAROON, PINK, WHITE, GREY
Variants: BLUE_A through BLUE_E, etc.

FULL LATEX SUPPORT:
- \begin{bmatrix}...\end{bmatrix} for matrices
- \begin{pmatrix}...\end{pmatrix} for parenthesized matrices
- \frac{a}{b}, \sum_{n=1}^{N}, \int_a^b, \sqrt{x}
- \lambda, \sigma, \vec{v}, \hat{x}, \bar{x}
- \text{...} for text within math
- \quad for spacing
- \\ for row breaks in matrices

IMPORTANT RULES:
1. Always start with `from manimlib import *` — never `from manim import *`
2. Use `self.wait(3)` to `self.wait(8)` generously between steps for narration time
3. Use `FadeOut(Group(...))` to clear the screen between major sections
4. Build animations progressively — show one thing at a time
5. Use color deliberately: BLUE=primary, YELLOW=highlight, GREEN=result, RED=emphasis
6. Keep each scene focused on ONE major concept with 3-6 animation steps
7. Always escape backslashes properly in raw strings: Tex(r"\frac{1}{2}")
8. CRITICAL: `Tex()` does NOT accept `font_size`. Only `Text()` accepts `font_size`.
   - WRONG: `Tex(r"\frac{1}{2}", font_size=40)` — THIS WILL CRASH
   - RIGHT: `Tex(r"\frac{1}{2}").scale(1.5)` — use `.scale()` for Tex sizing
   - RIGHT: `Text("Hello", font_size=40)` — font_size is only for Text
9. `Tex()` also does NOT accept `color` as a constructor argument.
   - WRONG: `Tex(r"\frac{1}{2}", color=BLUE)` — THIS WILL CRASH
   - RIGHT: `Tex(r"\frac{1}{2}").set_color(BLUE)` — use `.set_color()` instead
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
            max_tokens=16384,
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
        """Build the system prompt for direct ManimGL code generation."""
        return f"""\
You are an educational content script writer and ManimGL programmer. Your job is \
to create engaging educational video scripts with complete, runnable ManimGL Python \
code for each scene. The animations must be of 3Blue1Brown quality — rich, visual, \
and mathematically precise.

You MUST carefully analyze the source material to understand what mathematical \
concepts, functions, and relationships it contains, then write ManimGL code that \
VISUALLY explains them with proper LaTeX, matrices, graphs, and step-by-step animations.

CHARACTER PERSONA:
- Name: {personality.display_name}
- Voice Style: {personality.voice_style}
- Analogy Domain: {personality.analogy_domain}
- Catchphrases: {', '.join(personality.catchphrases)}
- Tone: {personality.tone}
- Background & Lore: {personality.background}

You MUST write all narration text in the voice and style of this character. \
Maintain their tone throughout and use catchphrases sparingly — only where they \
feel natural, not forced into every sentence.

CRITICAL — ANALOGY QUALITY RULES:
- Draw analogies from SPECIFIC events, relationships, and experiences in the \
character's Background & Lore above — not just surface-level domain keywords.
- Every analogy must MAP the educational concept to a concrete story or situation \
from the character's history. For example, if explaining exponential growth as \
SpongeBob, relate it to how Plankton's schemes escalate in complexity, or how \
SpongeBob's jellyfish collection grows — do NOT just say "this is like flipping \
Krabby Patties."
- Each scene should have at least one DEEP analogy that connects the concept \
being taught to a specific narrative moment from the character's background.
- Avoid generic catchphrase-only references. The analogy should help the student \
UNDERSTAND the concept better, not just be entertaining.

DIFFICULTY LEVEL:
{difficulty_instruction}

{MANIMGL_REFERENCE}

OUTPUT FORMAT:
You must respond with ONLY a valid JSON object (no markdown, no extra text) with this structure:
{{{{
    "title": "A catchy educational title",
    "total_scenes": <number of scenes>,
    "scenes": [
        {{{{
            "scene_index": 0,
            "narration_text": "What the character says during this scene (for voice synthesis)",
            "manim_scene_type": "custom",
            "manim_code": "<COMPLETE Python code for this scene — a standalone .py file with one Scene class>",
            "duration_hint_seconds": 60,
            "character_action": "talking"
        }}}}
    ],
    "intro_text": "An engaging introduction by the character",
    "outro_text": "A memorable closing by the character"
}}}}

CRITICAL RULES:
- Create 3-5 scenes for a ~5 minute video.
- Set duration_hint_seconds to 40-90 per scene.
- manim_scene_type should be "custom" for all scenes (the code handles everything).
- manim_code must be a COMPLETE, STANDALONE Python file:
  - Starts with `from manimlib import *` and `import numpy as np`
  - Contains exactly ONE class inheriting from Scene
  - The class name should be descriptive (e.g., MatrixMultiplication, EigenvalueDecomp)
  - The construct method contains all animations
- Use self.wait() generously (3-8 seconds) between steps so the narration has time.
- Use FadeOut(Group(...)) to clear screen between major sections within a scene.
- The last scene should be a summary/recap of key results.
- narration_text is what the character SAYS during this scene — written in their voice.
  Keep it natural and matching the character persona. 2-4 sentences per scene.
- character_action: "talking" (explaining), "pointing" (showing something specific), "idle" (pausing)

MANIM_CODE STRING RULES:
- manim_code is a JSON string. Use standard JSON string escaping.
- Use \n for newlines, \\ for a single backslash, \\\\ for a double backslash.
- Prefer single quotes in Python code to avoid escaping double quotes.
- IMPORTANT: In LaTeX matrices, row breaks use \\ (two backslashes).
  In the JSON string, encode this as \\\\ (four characters in the JSON).
"""

    def _build_user_message(self, extracted_text: str, user_prompt: Optional[str]) -> str:
        """Build the user message with source material."""
        message = f"""\
Create an educational video script with complete ManimGL code based on this material.
Analyze the mathematical content carefully and write ManimGL scenes that visually \
explain the concepts with proper LaTeX, step-by-step animations, and clean transitions.

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
Each scene's manim_code must be a complete, runnable ManimGL Python file.
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
        except json.JSONDecodeError:
            pass

        # Attempt repair: fix common LLM JSON issues in manim_code strings
        repaired = self._repair_json(text)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s", e)
            logger.error("Response text (first 1000 chars): %s", text[:1000])
            raise ValueError(f"LLM did not return valid JSON: {e}")

    @staticmethod
    def _repair_json(text: str) -> str:
        """Attempt to repair common JSON issues from LLM output.

        The main problem: manim_code values contain Python source with
        backslashes (LaTeX), newlines, and quotes that the LLM sometimes
        fails to escape correctly for JSON.
        """
        import re

        # Strategy: find each "manim_code": "..." value and re-escape it.
        # We locate the string boundaries by tracking quotes carefully.
        result = []
        i = 0
        key_pattern = re.compile(r'"manim_code"\s*:\s*"')

        while i < len(text):
            m = key_pattern.search(text, i)
            if not m:
                result.append(text[i:])
                break

            # Append everything before this manim_code value
            result.append(text[i:m.end()])
            i = m.end()

            # Now extract the raw string value by finding the closing quote.
            # We need to handle the LLM's potentially broken escaping.
            raw_chars = []
            while i < len(text):
                ch = text[i]
                if ch == '\\':
                    # Look ahead
                    if i + 1 < len(text):
                        next_ch = text[i + 1]
                        if next_ch in ('"', '\\', '/', 'b', 'f', 'n', 'r', 't'):
                            # Valid JSON escape - keep as-is
                            raw_chars.append(ch)
                            raw_chars.append(next_ch)
                            i += 2
                            continue
                        elif next_ch == 'u':
                            # Unicode escape - keep as-is
                            raw_chars.append(text[i:i+6])
                            i += 6
                            continue
                        else:
                            # Invalid escape (e.g. bare \S, \l, etc.)
                            # Double the backslash to make it valid JSON
                            raw_chars.append('\\\\')
                            i += 1
                            continue
                    else:
                        raw_chars.append('\\\\')
                        i += 1
                        continue
                elif ch == '"':
                    # Check if this is the end of the value.
                    # Look ahead for : or , or } to confirm.
                    rest = text[i+1:].lstrip()
                    if rest and rest[0] in (',', '}', ']'):
                        # This is the closing quote
                        result.append(''.join(raw_chars))
                        result.append('"')
                        i += 1
                        break
                    elif not rest:
                        result.append(''.join(raw_chars))
                        result.append('"')
                        i += 1
                        break
                    else:
                        # Embedded unescaped quote - escape it
                        raw_chars.append('\\"')
                        i += 1
                        continue
                elif ch == '\n':
                    # Literal newline inside a JSON string - replace with \n
                    raw_chars.append('\\n')
                    i += 1
                    continue
                elif ch == '\r':
                    raw_chars.append('\\r')
                    i += 1
                    continue
                elif ch == '\t':
                    raw_chars.append('\\t')
                    i += 1
                    continue
                else:
                    raw_chars.append(ch)
                    i += 1
                    continue
            else:
                # Reached end of text without finding closing quote
                result.append(''.join(raw_chars))

        return ''.join(result)

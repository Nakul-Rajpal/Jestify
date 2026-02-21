"""Service for generating educational scripts using the Anthropic Claude API.

Two-phase generation:
  Phase 1 — Narration: Rich, lecture-style script (8-15 sentences/scene)
  Phase 2 — ManimGL:  Complete animation code timed to match the narration
"""

import json
import logging
from typing import Callable, Optional

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
# ManimGL code generation reference (used only in Phase 2)
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
    """Generates structured educational scripts using Claude.

    Two-phase process:
      1. Generate narration (lecture-style, 8-15 sentences/scene)
      2. Generate ManimGL code aligned to the narration timing
    """

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate(
        self,
        extracted_text: str,
        character: Character,
        difficulty: Difficulty,
        user_prompt: Optional[str] = None,
        on_progress: Optional[Callable[[str, int], None]] = None,
    ) -> GeneratedScript:
        """Generate a full educational script (narration + ManimGL code).

        Two sequential LLM calls:
          Call 1 — narration only (no code)
          Call 2 — ManimGL code matched to the narration
        """
        personality = CHARACTER_PERSONALITIES[character]
        difficulty_instruction = DIFFICULTY_INSTRUCTIONS[difficulty]

        logger.info(
            "Generating script: character=%s, difficulty=%s, text_length=%d",
            character.value,
            difficulty.value,
            len(extracted_text),
        )

        # ---- Phase 1: narration ---------------------------------------- #
        narration_data = self._generate_narration(
            extracted_text, personality, difficulty_instruction, user_prompt
        )

        narration_data["character"] = character.value
        narration_data["difficulty"] = difficulty.value
        narration_data["language"] = "en"
        narration_script = GeneratedScript(**narration_data)

        logger.info(
            "Phase 1 complete: %d scenes, title='%s'",
            narration_script.total_scenes,
            narration_script.title,
        )

        if on_progress:
            on_progress("generating_animations", 15)

        # ---- Phase 2: ManimGL code ------------------------------------ #
        complete_script = self._generate_manim_code(
            narration_script, extracted_text, difficulty_instruction
        )

        logger.info("Phase 2 complete: ManimGL code generated for all scenes")
        return complete_script

    # ------------------------------------------------------------------ #
    # Phase 1 — Narration generation
    # ------------------------------------------------------------------ #

    def _generate_narration(
        self,
        extracted_text: str,
        personality,
        difficulty_instruction: str,
        user_prompt: Optional[str],
    ) -> dict:
        """Call 1: generate narration-only script (no manim_code)."""
        system_prompt = self._build_narration_system_prompt(
            personality, difficulty_instruction
        )
        user_message = self._build_narration_user_message(extracted_text, user_prompt)

        logger.info("Phase 1: Calling Claude for narration script...")

        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        return self._parse_response(response.content[0].text)

    def _build_narration_system_prompt(
        self, personality, difficulty_instruction: str
    ) -> str:
        return f"""\
You are an educational content script writer. Your job is to create engaging, \
lecture-style educational video scripts. You do NOT generate any code — only \
narration text and scene structure.

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
from the character's history.
- Each scene should have at least one DEEP analogy that connects the concept \
being taught to a specific narrative moment from the character's background.
- Avoid generic catchphrase-only references. The analogy should help the student \
UNDERSTAND the concept better, not just be entertaining.

DIFFICULTY LEVEL:
{difficulty_instruction}

NARRATION WRITING RULES:
- Write 8-15 sentences of narration per scene. This is a LECTURE — the character \
talks continuously throughout. There should be NO silent gaps.
- The narration should flow naturally as if the character is giving a live lesson.
- Explain concepts step by step: introduce, build intuition with analogies, show \
the math/logic, then summarize the key takeaway.
- Each sentence should advance the explanation. Do not repeat yourself or pad \
with filler phrases.
- The narration is what will be spoken aloud via text-to-speech, so write in a \
conversational, speakable style — not academic writing.
- Include verbal cues that reference what the viewer will see on screen, e.g. \
"Look at this matrix here", "Watch what happens when we multiply", \
"See how the graph curves upward?"
- Total narration across all scenes should cover 3-5 minutes of spoken content \
(approximately 450-750 words total, or 90-150 words per scene).

OUTPUT FORMAT:
You must respond with ONLY a valid JSON object (no markdown, no extra text):
{{{{
    "title": "A catchy educational title",
    "total_scenes": <number of scenes>,
    "scenes": [
        {{{{
            "scene_index": 0,
            "narration_text": "Full lecture narration for this scene. 8-15 sentences...",
            "manim_scene_type": "custom",
            "duration_hint_seconds": 60,
            "character_action": "talking"
        }}}}
    ],
    "intro_text": "An engaging introduction by the character",
    "outro_text": "A memorable closing by the character"
}}}}

CRITICAL RULES:
- Create 3-5 scenes for a ~5 minute video.
- Set duration_hint_seconds to 40-90 per scene (estimate from narration length).
- DO NOT include any "manim_code" field — leave it out entirely.
- narration_text must be 8-15 sentences of continuous, lecture-style narration.
- character_action: "talking" (explaining), "pointing" (showing something), "idle" (pausing)
"""

    def _build_narration_user_message(
        self, extracted_text: str, user_prompt: Optional[str]
    ) -> str:
        message = f"""\
Create an educational video script based on this material. Write rich, detailed \
narration that explains the concepts step by step. Do NOT generate any code.

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
"""
        return message

    # ------------------------------------------------------------------ #
    # Phase 2 — ManimGL code generation
    # ------------------------------------------------------------------ #

    def _generate_manim_code(
        self,
        narration_script: GeneratedScript,
        extracted_text: str,
        difficulty_instruction: str,
    ) -> GeneratedScript:
        """Call 2: generate ManimGL code for each scene, timed to narration."""
        system_prompt = self._build_manim_system_prompt(difficulty_instruction)
        user_message = self._build_manim_user_message(narration_script, extracted_text)

        logger.info("Phase 2: Calling Claude for ManimGL code...")

        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16384,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        manim_entries = self._parse_manim_response(response.content[0].text)

        # Merge manim_code back into the narration script
        code_by_index = {
            entry["scene_index"]: entry["manim_code"] for entry in manim_entries
        }

        updated_scenes = []
        for scene in narration_script.scenes:
            code = code_by_index.get(scene.scene_index)
            if code:
                updated_scenes.append(scene.model_copy(update={"manim_code": code}))
            else:
                logger.warning(
                    "No manim_code returned for scene_index=%d", scene.scene_index
                )
                updated_scenes.append(scene)

        return narration_script.model_copy(update={"scenes": updated_scenes})

    def _build_manim_system_prompt(self, difficulty_instruction: str) -> str:
        return f"""\
You are an expert ManimGL programmer. Your job is to write complete, runnable \
ManimGL Python code for each scene of an educational video. You will be given \
the narration script for each scene — your code must produce animations that \
visually accompany and reinforce what the narrator is saying.

The animations must be of 3Blue1Brown quality — rich, visual, and mathematically \
precise.

You MUST carefully analyze both the source material AND the narration script to \
understand what concepts are being explained, then write ManimGL code that \
VISUALLY demonstrates them with proper LaTeX, matrices, graphs, and step-by-step \
animations.

DIFFICULTY LEVEL (affects visual complexity):
{difficulty_instruction}

{MANIMGL_REFERENCE}

CRITICAL TIMING RULES:
- Your code's self.wait() calls must create enough total pause time to cover \
the narration for that scene. The narration will be played as audio over the \
animation.
- Calculate: the narration has roughly 150 words per minute of spoken audio. \
Count the words in the narration_text and divide by 2.5 to estimate seconds, \
then distribute self.wait() calls throughout your animations to match.
- NEVER have long stretches of animation with no self.wait() — the viewer needs \
time to absorb what they see while listening to the narration.
- Spread self.wait() calls between EVERY major animation step, using 3-8 second \
pauses. The total wait time across the scene should roughly match the narration \
duration.
- Each scene's animation should feel choreographed to the narration — when the \
narrator says "look at this matrix", a matrix should be appearing on screen.

OUTPUT FORMAT:
You must respond with ONLY a valid JSON array (no markdown, no extra text). \
Each element corresponds to a scene by scene_index and contains the manim_code:
[
    {{{{
        "scene_index": 0,
        "manim_code": "<COMPLETE Python code for scene 0>"
    }}}},
    {{{{
        "scene_index": 1,
        "manim_code": "<COMPLETE Python code for scene 1>"
    }}}}
]

CRITICAL RULES:
- Output one entry per scene, matching the scene_index values from the narration.
- manim_code must be a COMPLETE, STANDALONE Python file:
  - Starts with `from manimlib import *` and `import numpy as np`
  - Contains exactly ONE class inheriting from Scene
  - The class name should be descriptive (e.g., MatrixMultiplication, EigenvalueDecomp)
  - The construct method contains all animations
- Use self.wait() generously (3-8 seconds) between steps so the narration has time.
- Use FadeOut(Group(...)) to clear screen between major sections within a scene.
- The last scene's code should be a visual summary/recap.

MANIM_CODE STRING RULES:
- manim_code is a JSON string. Use standard JSON string escaping.
- Use \\n for newlines, \\\\ for a single backslash.
- Prefer single quotes in Python code to avoid escaping double quotes.
- IMPORTANT: In LaTeX matrices, row breaks use \\\\ (two backslashes).
  In the JSON string, encode this as \\\\\\\\ (four characters in the JSON).
"""

    def _build_manim_user_message(
        self, narration_script: GeneratedScript, extracted_text: str
    ) -> str:
        scenes_text = ""
        for scene in narration_script.scenes:
            word_count = len(scene.narration_text.split())
            estimated_seconds = max(int(word_count / 2.5), 30)
            scenes_text += f"""
--- SCENE {scene.scene_index} ---
Narration ({word_count} words, ~{estimated_seconds}s of audio):
{scene.narration_text}
Duration hint: {scene.duration_hint_seconds}s
---
"""

        return f"""\
Generate ManimGL Python code for each scene of this educational video.

VIDEO TITLE: {narration_script.title}

NARRATION SCRIPT (your code must visually accompany this):
{scenes_text}

SOURCE MATERIAL (for mathematical/conceptual accuracy):
--- SOURCE MATERIAL ---
{extracted_text[:8000]}
--- END SOURCE MATERIAL ---

Remember: respond with ONLY the JSON array, no markdown code fences or extra text.
Each scene's manim_code must be a complete, runnable ManimGL Python file.
Your animations should be timed to match the narration — use self.wait() calls \
so the total animation duration covers the spoken narration for each scene.
"""

    def _parse_manim_response(self, response_text: str) -> list[dict]:
        """Parse Phase 2 response — a JSON array of {{scene_index, manim_code}}."""
        text = response_text.strip()

        # Strip markdown fences
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        def _extract_list(obj):
            if isinstance(obj, list):
                return obj
            if isinstance(obj, dict) and "scenes" in obj:
                return obj["scenes"]
            raise ValueError("Expected JSON array of scene entries")

        try:
            return _extract_list(json.loads(text))
        except (json.JSONDecodeError, ValueError):
            pass

        # Attempt repair for manim_code escaping issues
        repaired = self._repair_json(text)
        try:
            return _extract_list(json.loads(repaired))
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to parse Phase 2 (ManimGL) response: %s", e)
            logger.error("Response text (first 1000 chars): %s", text[:1000])
            raise ValueError(f"Phase 2 LLM did not return valid JSON: {e}")

    # ------------------------------------------------------------------ #
    # Shared helpers
    # ------------------------------------------------------------------ #

    def _parse_response(self, response_text: str) -> dict:
        """Parse a JSON object response from the LLM."""
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

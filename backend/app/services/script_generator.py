"""Service for generating educational scripts using the Anthropic Claude API.

Uses a two-API-call architecture:
  Call 1 — Generate the narration script in the character's voice (no code).
  Call 2 — Generate synchronized ManimCE code based on the narration.
"""

import asyncio
import json
import logging
import re
import time
from typing import Optional

import anthropic

from shared.contracts.character_schema import CHARACTER_PERSONALITIES
from shared.contracts.enums import Character, Difficulty
from shared.contracts.pipeline_schema import GeneratedScript

from ..config import settings
from .context7_docs import get_manim_docs

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-20250514"

DIFFICULTY_INSTRUCTIONS: dict[Difficulty, str] = {
    Difficulty.BEGINNER: (
        "Explain concepts at a beginner level. Use simple language, avoid jargon, "
        "and break down ideas into the most fundamental building blocks."
    ),
    Difficulty.INTERMEDIATE: (
        "Explain at an intermediate level. Use some technical terms "
        "but always briefly clarify them. Build on foundational knowledge."
    ),
    Difficulty.ADVANCED: (
        "Explain at an advanced level. Use proper technical terminology, "
        "explore nuances, edge cases, and deeper implications."
    ),
}

# Built-in ManimCE reference so the LLM always has a baseline even if
# Context7 is unavailable.
MANIMCE_REFERENCE = r"""
MANIM COMMUNITY EDITION (ManimCE) — QUICK API REFERENCE
========================================================
You write complete ManimCE Python code. Import: from manim import *

TEXT MOBJECTS (use Text() for EVERYTHING — LaTeX is NOT available):
  Text("hello", font_size=36)           — titles, labels, prose (Pango/Cairo)
  Text("x² + 1 = 0", font_size=36)     — math with Unicode superscripts
  Text("f(x) = x²", font_size=36)      — functions
  Text("∫₀¹ x dx = ½", font_size=36)   — integrals with Unicode
  Text("Σᵢ₌₁ⁿ xᵢ", font_size=36)      — summations with Unicode
  NEVER use MathTex() or Tex() — they require LaTeX which is not installed.
  Use Unicode for math: x², x₁, √, π, Σ, ∫, →, ⇒, ≤, ≥, ≠, ≈, ∞, ±, ×, ÷
  Superscripts: ⁰¹²³⁴⁵⁶⁷⁸⁹ⁿˣⁱ  Subscripts: ₀₁₂₃₄₅₆₇₈₉ₙₓᵢ
  Fractions: write as a/b or use ½ ⅓ ¼ for common fractions
  Text() accepts color= and font_size= as constructor args:
    Text("x² + 1 = 0", color=BLUE, font_size=36)

SHAPES & GEOMETRY:
  Axes(x_range=[a,b,s], y_range=[c,d,s], x_length=7, y_length=5)
  IMPORTANT: Use small ranges like [-3,3,1]. NEVER wider than [-5,5,1].
  You can use x_length and y_length to control Axes size.
  You can also use axis_config, tips, include_numbers for Axes customisation.
  NumberPlane(x_range, y_range)
  NumberLine(x_range)
  Dot(point), Line(start, end), Arrow(start, end)
  Circle(radius=1.0), Square(side_length=1.0), Rectangle(width, height)
  RoundedRectangle(corner_radius=0.15, width=4, height=2)
  VGroup(mob1, mob2, ...)               — group mobjects together
  SurroundingRectangle(mob, color=YELLOW, buff=0.15)
  Brace(mob, direction)
  DashedLine(start, end)
  Polygon(*points), RegularPolygon(n=6)
  Arc(angle), AnnularSector(inner_radius, outer_radius, angle)

POSITIONING:
  mob.to_edge(UP/DOWN/LEFT/RIGHT, buff=0.5)
  mob.to_corner(UL/UR/DL/DR, buff=0.5)
  mob.next_to(other, DOWN, buff=0.3)
  mob.move_to(point_or_mob)
  mob.shift(RIGHT * 2 + UP * 1)
  VGroup(...).arrange(DOWN, buff=0.4)
  VGroup(...).arrange_in_grid(n_rows, n_cols, buff=0.3)

DIRECTIONS: UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR, ORIGIN

ANIMATIONS (ManimCE names):
  Write(mob), Create(mob), FadeIn(mob), FadeOut(mob)
  FadeIn(mob, shift=UP*0.3)            — directional fade in
  Transform(src, dst), ReplacementTransform(src, dst)
  TransformMatchingShapes(old, new)     — morph shapes
  Indicate(mob, color=YELLOW, scale_factor=1.2)
  Circumscribe(mob, color=YELLOW)       — draw a circle around mobject
  GrowFromCenter(mob), GrowArrow(arrow)
  MoveAlongPath(dot, path)
  LaggedStart(*anims, lag_ratio=0.2)    — staggered reveals (MANDATORY for lists)
  AnimationGroup(*anims)
  Flash(point, color=YELLOW)
  Unwrite(mob)                          — reverse of Write
  Wiggle(mob)                           — wiggle effect
  ApplyWave(mob)                        — wave effect

  IMPORTANT: Use Create() NOT ShowCreation(). Use Unwrite() NOT Uncreate().

PLAY:
  self.play(Create(mob), run_time=2)
  self.play(mob.animate.shift(RIGHT*2), run_time=1.5)
  self.play(mob.animate.set_color(YELLOW))
  self.play(mob.animate.set_opacity(0.3))  — dim previous elements
  self.wait(2)

AXES METHODS (ManimCE):
  graph = axes.plot(lambda x: x**2, color=BLUE, x_range=[-3,3])
  dot = Dot(axes.c2p(x, y))             — coordinate to point
  axes.input_to_graph_point(x_val, graph) — get point on graph at x
  area = axes.get_area(graph, x_range=[0, 2], color=BLUE, opacity=0.3)
  axes.add_coordinates()                 — show numbers on axes

  AXIS LABELS — MUST pass Text() objects, NOT strings (strings trigger hidden LaTeX):
    x_lab = axes.get_x_axis_label(Text("x", font_size=28))
    y_lab = axes.get_y_axis_label(Text("f(x)", font_size=28))
    WRONG: axes.get_x_axis_label("x")  ← crashes with LaTeX error!
    RIGHT: axes.get_x_axis_label(Text("x", font_size=28))

  GRAPH LABELS — use .next_to() with Text(), NOT get_graph_label() with strings:
    graph_label = Text("f(x) = x²", color=BLUE, font_size=28)
    graph_label.next_to(axes.c2p(2, 4), RIGHT)
    If you MUST use get_graph_label(), pass a Text() object:
    WRONG: axes.get_graph_label(graph, "f(x)")  ← hidden LaTeX!
    RIGHT: axes.get_graph_label(graph, Text("f(x)", font_size=28))

COLORS:
  BLUE, BLUE_A/B/C/D/E, RED, RED_A-E, GREEN, GREEN_A-E,
  YELLOW, YELLOW_A-E, GOLD, GOLD_A-E, TEAL, TEAL_A-E,
  PURPLE, PURPLE_A-E, MAROON, MAROON_A-E, ORANGE, PINK,
  GREY, GREY_A-D, WHITE, BLACK, GREY_BROWN

SCENE CLASS:
  class MyScene(Scene):
      def construct(self):
          ...
"""


def _fetch_live_manim_docs(source_text: str) -> str:
    """Fetch live Manim docs from Context7 based on the source material."""
    topic = "manim Scene Text Axes NumberPlane Create FadeIn Write Transform animations plot VGroup ReplacementTransform physics chemistry circuit automata data structures"
    logger.info("[script_gen] Fetching live Manim docs from Context7 (topic: %s)", topic)
    try:
        docs = asyncio.run(get_manim_docs(topic=topic, max_tokens=5000))
        if docs:
            logger.info("[script_gen] Context7 returned %d chars of live Manim docs", len(docs))
            return docs
        logger.warning("[script_gen] Context7 returned empty docs")
    except Exception as exc:
        logger.warning("[script_gen] Context7 fetch failed: %s — using built-in reference", exc)
    return ""


class ScriptGenerator:
    """Generates structured educational scripts with complete Manim code per scene.

    Uses a two-API-call architecture:
      Call 1 — Generate narration script in the character's voice (no code).
      Call 2 — Generate synchronized ManimCE code based on the narration.
    """

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # ──────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────

    def generate(
        self,
        extracted_text: str,
        character: Character,
        difficulty: Difficulty,
        user_prompt: Optional[str] = None,
    ) -> GeneratedScript:
        logger.info("[script_gen] ┌─ Generating script (two-call architecture)")
        logger.info("[script_gen] │  Character: %s", character.value)
        logger.info("[script_gen] │  Difficulty: %s", difficulty.value)
        logger.info("[script_gen] │  Source text: %d chars", len(extracted_text))
        logger.info("[script_gen] │  Model: %s", CLAUDE_MODEL)

        personality = CHARACTER_PERSONALITIES[character]
        difficulty_instruction = DIFFICULTY_INSTRUCTIONS[difficulty]

        t0 = time.perf_counter()
        live_docs = _fetch_live_manim_docs(extracted_text)
        docs_elapsed = time.perf_counter() - t0
        logger.info("[script_gen] │  Context7 fetch: %.1fs, %d chars", docs_elapsed, len(live_docs))

        # ── Call 1: Generate narration script (no code) ──────────────
        logger.info("[script_gen] │")
        logger.info("[script_gen] │  ── CALL 1: Narration ──")
        narration_data, narr_elapsed = self._generate_narration(
            extracted_text, personality, difficulty_instruction, user_prompt,
        )
        narration_errors = self._validate_narration(narration_data, personality)
        if narration_errors:
            logger.warning("[script_gen] │  Narration issues: %s", narration_errors)
            feedback = (
                "Regenerate the full JSON and fix ALL issues:\n- "
                + "\n- ".join(narration_errors)
            )
            narr_user = self._build_narration_user_message(extracted_text, user_prompt)
            retry_msg = f"{narr_user}\n\n{feedback}"
            narr_sys = self._build_narration_system_prompt(personality, difficulty_instruction)
            resp, retry_elapsed = self._request_script(narr_sys, retry_msg, max_tokens=4096)
            narr_elapsed += retry_elapsed
            narration_data = self._parse_response(resp)
            remaining = self._validate_narration(narration_data, personality)
            if remaining:
                logger.warning("[script_gen] │  Narration issues remain: %s. Continuing.", remaining)

        logger.info("[script_gen] │  Narration OK — %d scenes, title: %s",
                     len(narration_data.get("scenes", [])), narration_data.get("title"))

        # ── Call 2: Generate ManimCE code (narration as input) ───────
        logger.info("[script_gen] │")
        logger.info("[script_gen] │  ── CALL 2: Code generation ──")
        code_data, code_elapsed = self._generate_code(narration_data, live_docs)
        code_errors = self._validate_code(code_data)
        if code_errors:
            logger.warning("[script_gen] │  Code issues: %s", code_errors)
            feedback = (
                "Regenerate the full JSON array and fix ALL issues:\n- "
                + "\n- ".join(code_errors)
            )
            code_user = self._build_code_user_message(narration_data)
            retry_msg = f"{code_user}\n\n{feedback}"
            code_sys = self._build_code_system_prompt(live_docs)
            resp, retry_elapsed = self._request_script(code_sys, retry_msg, max_tokens=16384)
            code_elapsed += retry_elapsed
            code_data = self._parse_response(resp)
            if isinstance(code_data, list):
                code_data = {"scenes": code_data}
            remaining = self._validate_code(code_data)
            if remaining:
                logger.warning("[script_gen] │  Code issues remain: %s. Continuing.", remaining)

        # ── Merge narration + code into final GeneratedScript ────────
        narration_scenes = narration_data.get("scenes", [])
        code_scenes = code_data.get("scenes", []) if isinstance(code_data, dict) else code_data
        merged_scenes = []
        for ns in narration_scenes:
            idx = ns["scene_index"]
            cs = next((c for c in code_scenes if c.get("scene_index") == idx), None)
            merged_scenes.append({
                "scene_index": idx,
                "narration_text": ns.get("narration_text", ""),
                "manim_scene_type": ns.get("manim_scene_type", "custom"),
                "manim_parameters": ns.get("manim_parameters", {}),
                "duration_hint_seconds": ns.get("duration_hint_seconds", 30),
                "character_action": ns.get("character_action", "talking"),
                "manim_code": cs.get("manim_code", "") if cs else "",
            })

        script_data = {
            "title": narration_data.get("title", "Untitled"),
            "total_scenes": len(merged_scenes),
            "scenes": merged_scenes,
            "intro_text": narration_data.get("intro_text", ""),
            "outro_text": narration_data.get("outro_text", ""),
            "character": character.value,
            "difficulty": difficulty.value,
            "language": "en",
        }

        script = GeneratedScript(**script_data)
        total_elapsed = docs_elapsed + narr_elapsed + code_elapsed
        logger.info("[script_gen] │  Title: %s", script.title)
        logger.info("[script_gen] │  Total scenes: %d", script.total_scenes)
        for i, s in enumerate(script.scenes):
            has_code = bool(s.manim_code)
            code_len = len(s.manim_code) if s.manim_code else 0
            logger.info(
                "[script_gen] │  Scene %d: type=%s, duration=%.0fs, has_code=%s (%d chars)",
                i + 1, s.manim_scene_type, s.duration_hint_seconds, has_code, code_len,
            )
        logger.info("[script_gen] └─ Script generation complete (%.1fs total: narr=%.1fs, code=%.1fs)",
                     total_elapsed, narr_elapsed, code_elapsed)
        return script

    # ──────────────────────────────────────────────────────────────────
    # Call 1 — Narration generation
    # ──────────────────────────────────────────────────────────────────

    def _generate_narration(
        self,
        extracted_text: str,
        personality,
        difficulty_instruction: str,
        user_prompt: Optional[str],
    ) -> tuple[dict, float]:
        """Call 1: generate narration script only (no Manim code)."""
        sys_prompt = self._build_narration_system_prompt(personality, difficulty_instruction)
        user_msg = self._build_narration_user_message(extracted_text, user_prompt)
        logger.info("[script_gen] │  Narration system prompt: %d chars", len(sys_prompt))
        logger.info("[script_gen] │  Narration user message: %d chars", len(user_msg))
        resp, elapsed = self._request_script(sys_prompt, user_msg, max_tokens=4096)
        logger.info("[script_gen] │  Narration response: %d chars (%.1fs)", len(resp), elapsed)
        return self._parse_response(resp), elapsed

    def _build_narration_system_prompt(self, personality, difficulty_instruction: str) -> str:
        return f"""\
You are an expert educational script writer. You write narration scripts for \
animated educational videos — like 3Blue1Brown but voiced by a specific character.

Your job is to write ONLY the narration (what the character says out loud). \
You do NOT write any code or animation instructions. A separate system will \
generate the animations to match your narration.

CHARACTER PERSONA:
- Name: {personality.display_name}
- Tone: {personality.tone}
- Catchphrases: {', '.join(personality.catchphrases)}
- Analogy Domain: {personality.analogy_domain}
- Background: {personality.background}

Write narration in this character's voice. Use their catchphrases naturally. \
The audience should FEEL like {personality.display_name} is personally teaching them.

=== NARRATION RULES (MANDATORY) ===
1. ANALOGY HOOK (Scene 0 ONLY): Open Scene 0 with a vivid analogy from the \
   character's world ({personality.analogy_domain}). For example, if the character \
   is a basketball player teaching derivatives: "Think of derivatives like reading \
   a defense — you need to see what's changing and react in real time."
   After Scene 0, DROP the extended analogy — teach the actual content directly.

2. CONTINUOUS FLOW: Narration must flow as a continuous lecture. Each scene picks \
   up where the previous left off. Use transition phrases like "Now that we \
   understand X, let's look at Y" or "Building on that idea..." No dead air, \
   no abrupt topic switches, no repeated introductions.

3. NARRATION LENGTH: Each scene's narration_text MUST be 3-5 sentences \
   (60-120 words). Target ~150 words per minute. For a 30-second scene, \
   write ~75 words. NEVER shorter than 40 words.

4. CHARACTER VOICE: The narration must sound like the character is personally \
   explaining the topic. NOT a generic textbook. Use catchphrases, tone, and \
   personality consistently throughout ALL scenes.

5. VISUAL DESCRIPTIONS: For each scene, write a visual_description field that \
   describes what SHOULD appear on screen. Be specific about what kind of \
   animation or diagram would best illustrate the narration. Examples:
   - "Show a graph of f(x) = x² with a tangent line sliding along the curve"
   - "Display a tree diagram with the root labeled 'Algorithm' and three children"
   - "Build up the equation step by step: first show x², then transform to 2x"
   The visual_description guides the animation generator to create visuals that \
   are synchronized with the narration.

DIFFICULTY: {difficulty_instruction}

=== VIDEO STRUCTURE (MANDATORY) ===
- Generate 5 to 7 scenes for a video totaling 1.5 to 3 minutes.
- Scene 0: Concept introduction (20-30s) — hook with character analogy + key concepts
- Scene 1 or 2: GRAPH SCENE (MANDATORY) — describe a graph/plot that visualizes a \
  function, trend, or relationship. Set manim_scene_type="graph". \
  Even non-math topics can have graphs: growth rates, timelines, comparisons.
- Scene 2 or 3: EQUATION/TRANSFORM SCENE — describe step-by-step derivation or \
  concept evolution. Set manim_scene_type="equation".
- Remaining scenes: Core teaching content (30-45s each) — diagrams, visual structures
- Last scene: Summary/recap (20-30s) — key takeaways

=== OUTPUT FORMAT ===
Respond with ONLY valid JSON (no markdown fences, no extra text):
{{
    "title": "Catchy educational title",
    "total_scenes": <number>,
    "scenes": [
        {{
            "scene_index": 0,
            "narration_text": "What the character says during this scene...",
            "visual_description": "What should appear on screen during this scene...",
            "manim_scene_type": "equation|graph|diagram|concept_reveal|geometry|summary",
            "duration_hint_seconds": 30,
            "character_action": "talking"
        }}
    ],
    "intro_text": "Engaging introduction",
    "outro_text": "Memorable closing"
}}
"""

    def _build_narration_user_message(self, extracted_text: str, user_prompt: Optional[str]) -> str:
        message = f"""\
Write a narration script with 5-7 scenes based on this source material.
Analyze the material carefully — identify the key concepts, relationships, \
and problems, then write engaging narration that TEACHES them.

--- SOURCE MATERIAL ---
{extracted_text}
--- END SOURCE MATERIAL ---

REQUIREMENTS:
1. Generate 5-7 scenes with narration_text and visual_description for each
2. Total video duration: 1.5 to 3 minutes (sum of duration_hint_seconds)
3. Each scene must have 30-60 seconds of narration
4. MANDATORY: At least one scene with manim_scene_type="graph"
5. Include at least one equation/derivation scene
6. Last scene must be a summary/recap
7. visual_description must be specific enough for an animation generator
8. Stay in character throughout — this should sound like a real person teaching
"""
        if user_prompt:
            message += f"\nAdditional instructions: {user_prompt}\n"
        message += "\nRespond with ONLY the JSON object. No markdown fences."
        return message

    def _validate_narration(self, script_data: dict, personality=None) -> list[str]:
        """Validate narration-only output from Call 1."""
        errors: list[str] = []
        scenes = script_data.get("scenes") or []
        if len(scenes) < 4:
            errors.append("Need at least 4 scenes; target 5-7 for 1 minute+.")
            return errors

        for idx, scene in enumerate(scenes):
            narration = (scene.get("narration_text") or "").strip()
            word_count = len(narration.split())
            if word_count < 40:
                errors.append(
                    f"Scene {idx+1} narration_text too short ({word_count} words). "
                    "Must be 3-5 sentences (60-120 words) to fill the scene duration."
                )
            if idx == 0 and personality and hasattr(personality, "analogy_domain"):
                domain_phrases = personality.analogy_domain.lower().split(", ")
                domain_words: set[str] = set()
                for phrase in domain_phrases:
                    domain_words.add(phrase)
                    domain_words.update(phrase.split())
                narration_lower = narration.lower()
                if not any(kw in narration_lower for kw in domain_words):
                    errors.append(
                        f"Scene 1 narration must open with an analogy from the character's "
                        f"domain ({personality.analogy_domain}). Use a hook that connects "
                        f"the topic to {personality.display_name}'s world."
                    )

        total_duration = sum(
            float(s.get("duration_hint_seconds", 0) or 0) for s in scenes
        )
        if total_duration < 55:
            errors.append(f"Total duration too short ({total_duration:.1f}s). Target >= 60s.")

        has_graph = any(
            str(s.get("manim_scene_type") or "").lower() == "graph" for s in scenes
        )
        if not has_graph:
            errors.append("At least one scene must have manim_scene_type='graph'.")

        return errors

    # ──────────────────────────────────────────────────────────────────
    # Call 2 — Code generation
    # ──────────────────────────────────────────────────────────────────

    def _generate_code(
        self, narration_data: dict, live_manim_docs: str,
    ) -> tuple[dict, float]:
        """Call 2: generate ManimCE code for each scene based on narration."""
        sys_prompt = self._build_code_system_prompt(live_manim_docs)
        user_msg = self._build_code_user_message(narration_data)
        logger.info("[script_gen] │  Code system prompt: %d chars", len(sys_prompt))
        logger.info("[script_gen] │  Code user message: %d chars", len(user_msg))
        resp, elapsed = self._request_script(sys_prompt, user_msg, max_tokens=16384)
        logger.info("[script_gen] │  Code response: %d chars (%.1fs)", len(resp), elapsed)
        data = self._parse_response(resp)
        if isinstance(data, list):
            data = {"scenes": data}
        return data, elapsed

    def _build_code_system_prompt(self, live_manim_docs: str = "") -> str:
        live_docs_section = ""
        if live_manim_docs:
            live_docs_section = f"""
================================================================================
SUPPLEMENTARY MANIM DOCS (from Context7 — ManimCE documentation)
================================================================================
{live_manim_docs}
================================================================================
"""

        return f"""\
You are an expert ManimCE (Manim Community Edition) animation developer \
producing 3Blue1Brown-quality video scenes. You generate COMPLETE, RUNNABLE \
Python code for each scene.

You will receive a narration script with visual descriptions for each scene. \
Your job is to write ManimCE code that SYNCHRONIZES with the narration — \
when the narrator mentions a concept, the corresponding visual MUST appear \
at that exact moment in the animation.

=== SYNCHRONIZATION RULES (CRITICAL) ===
1. Read the narration carefully. Break it into logical segments.
2. For each segment of narration (~1-2 sentences), create a corresponding \
   animation sequence with matching timing.
3. Use self.wait() and run_time values to pace animations with the narration.
4. The narrator speaks at ~150 words per minute. A 30-word segment ≈ 12 seconds.
5. When the narrator says "look at this graph", the graph should be appearing.
6. When the narrator says "notice how X changes", X should be animating.
7. Match the total animation duration to duration_hint_seconds for each scene.

{MANIMCE_REFERENCE}
{live_docs_section}

=== STRICT TYPOGRAPHY & LEGIBILITY RULES ===
- No walls of text — use bullet points, keywords, or short phrases only
- Minimum font sizes: headers 40-48, body 28-36, absolute minimum 24
- Use weight=BOLD for titles: Text("Title", font_size=44, weight=BOLD)
- Max 4-5 visual elements on screen at once
- NEVER display paragraphs of text. Use progressive reveal instead.

=== GRID LAYOUT SYSTEM (MANDATORY) ===
Frame: 14.2 x 8 units. Safe zone: x in [-6.0, 6.0], y in [-3.2, 3.2].

Named grid positions — use these for ALL placement:
  TITLE_POS    = UP * 3.2               — title bar (always here)
  SUBTITLE_POS = UP * 2.3               — section headers / subtitle
  MAIN_AREA    = DOWN * 0.3             — primary content below title
  LEFT_PANEL   = LEFT * 3.2             — split-screen left
  RIGHT_PANEL  = RIGHT * 3.2            — split-screen right

Layout patterns — pick ONE per scene:
  Full Center:    Title at UP*3.2, single content at DOWN*0.3
  Split Screen:   Title at UP*3.2, text at LEFT*3.2, visual at RIGHT*3.2
  Vertical Stack: Title at UP*3.2, VGroup.arrange(DOWN, buff=0.4).move_to(DOWN*0.3)
  Graph Layout:   Title at UP*3.2, axes.move_to(DOWN*0.3)

Size safety — apply AFTER building groups:
  - VGroup with 4+ items:  group.set_height(min(group.get_height(), 5.5))
  - Horizontal with 3+ items: group.set_width(min(group.get_width(), 12.0))
  - NEVER .shift() with magnitude > 3.5
  - NEVER place content below y = -3.0 or above y = 3.5

=== COGNITIVE LOAD & FOCUS ANIMATION ===
- Dim previous elements when new content appears:
    self.play(prev_group.animate.set_opacity(0.3))
- Restore when revisiting: self.play(prev_group.animate.set_opacity(1.0))
- Emphasis animations:
    Indicate(mob, color=YELLOW)        — "Notice this..."
    Circumscribe(mob, color=YELLOW)    — "This is critical..."
    SurroundingRectangle(mob, color)    — persistent highlight
- ALWAYS use LaggedStart for revealing lists:
    self.play(LaggedStart(*[FadeIn(b, shift=UP*0.3) for b in bullets], lag_ratio=0.2))
  NEVER FadeIn an entire VGroup at once.

=== SCENE LIFECYCLE — CLEAR BEFORE BUILD (MANDATORY) ===
Every construct() follows: TITLE -> BUILD -> (optional TRANSITION) -> CLEANUP.

1. Each scene starts with a blank frame.
2. Title always first: title.move_to(UP * 3.2) then build content below.
3. When a scene has two logical ideas, FadeOut ALL non-title elements between them.
4. The LAST two lines of EVERY construct() MUST be:
     self.play(*[FadeOut(m) for m in self.mobjects], run_time=1.5)
     self.wait(1)

=== VISUAL-FIRST RULE — NEVER PLAIN TEXT WALLS (CRITICAL) ===
Convert textual information into VISUAL STRUCTURES whenever possible.
If content is a list → build a TREE, TABLE, or FLOWCHART, NOT stacked Text lines.
If content describes relationships → use ARROWS, CONNECTORS, and DIAGRAMS.
MANDATORY: At least 3 out of 5-7 scenes MUST use visual structures.

=== TEXT OVERLAP PREVENTION (CRITICAL) ===
1. Before placing NEW content, ALWAYS FadeOut or dim existing content.
2. NEVER two Text objects at same y-position without 0.5+ units gap.
3. MAXIMUM 4 text elements visible simultaneously.

=== COLOR THEME ===
Background is BLACK. Use high contrast:
  TITLES: WHITE or GOLD. BODY: WHITE. PRIMARY: BLUE. SECONDARY: GREEN.
  HIGHLIGHT: YELLOW. RESULT: GREEN_B. WARNING: RED.

=== ARRAYS, BOXES & LABELED CELLS ===
Create cells as VGroup(rect, label) — label.move_to(rect.get_center()).
Build as VGroup of cells, then arrange once.

=== IMPORTANT RULES ===
1. Import MUST be: from manim import *
2. Class names: Scene000, Scene001, Scene002, etc.
3. Use Create() NOT ShowCreation(). Use Unwrite() NOT Uncreate().
4. NEVER use MathTex(), Tex(), or any LaTeX-based text. LaTeX is NOT installed.
   Use Text() for ALL text including math. Use Unicode for math symbols.
5. Use axes.plot() NOT axes.get_graph(). Use axes.c2p() for coordinates.
6. AXIS LABELS: Always pass Text() objects to get_x_axis_label(), etc.
   WRONG: axes.get_x_axis_label("x")
   RIGHT: axes.get_x_axis_label(Text("x", font_size=28))
7. GRAPH LABELS: Use Text().next_to(), NOT get_graph_label() with strings.
8. Guard lambdas: lambda x: 1/x if abs(x) > 0.01 else 0
9. No plugins. Only manim and numpy imports.
10. NEVER use TransformMatchingTex — use ReplacementTransform.
11. Minimum font_size: 24. Never .scale() below 0.8 on text.
12. Every self.play() MUST have run_time=1.5 to 3 seconds.
13. Add self.wait(2) after important reveals.
14. TEXT WIDTH SAFETY: text.set_width(min(text.width, 10.0)) on any Text.

=== OUTPUT FORMAT ===
Respond with ONLY valid JSON (no markdown fences, no extra text):
{{
    "scenes": [
        {{
            "scene_index": 0,
            "manim_code": "from manim import *\\nimport numpy as np\\n\\nclass Scene000(Scene):\\n    def construct(self):\\n        ..."
        }}
    ]
}}

Each scene's manim_code MUST be COMPLETE, RUNNABLE ManimCE Python code:
- Start with: from manim import * and import numpy as np
- Define ONE Scene subclass named Scene{{NNN}} (Scene000, Scene001, etc.)
- 40-80+ lines of animation code
- Duration must match duration_hint_seconds
- End with FadeOut cleanup
"""

    def _build_code_user_message(self, narration_data: dict) -> str:
        scenes = narration_data.get("scenes", [])
        title = narration_data.get("title", "Untitled")

        scene_blocks = []
        for s in scenes:
            idx = s.get("scene_index", 0)
            dur = s.get("duration_hint_seconds", 30)
            stype = s.get("manim_scene_type", "custom")
            narration = s.get("narration_text", "")
            visual = s.get("visual_description", "")
            scene_blocks.append(
                f"SCENE {idx} ({dur}s, {stype}):\n"
                f"Narration: \"{narration}\"\n"
                f"Visual description: \"{visual}\""
            )

        scenes_text = "\n\n".join(scene_blocks)

        return f"""\
Generate ManimCE code for each scene of the video "{title}".

The narration and visual descriptions are provided below. Your code MUST \
synchronize with the narration — when the narrator mentions a concept, the \
corresponding visual should appear at that moment.

{scenes_text}

REQUIREMENTS:
1. Generate complete, runnable ManimCE code for EVERY scene
2. MANDATORY: At least one scene MUST use Axes(...) + axes.plot(...)
3. Include at least one scene with ReplacementTransform for equation/concept evolution
4. At least 3 scenes must have visual structures (graphs, diagrams, trees, tables)
5. Each scene needs >= 4 self.play() calls with explicit run_time
6. NEVER use MathTex or Tex — use Text() with Unicode for math
7. End every scene with FadeOut cleanup

Respond with ONLY the JSON object. No markdown fences.
"""

    def _validate_code(self, code_data: dict) -> list[str]:
        """Validate code output from Call 2."""
        errors: list[str] = []
        scenes = code_data.get("scenes") or []
        if not scenes:
            errors.append("No scenes in code output.")
            return errors

        has_graph = False
        has_transform = False
        visual_structure_count = 0

        for idx, scene in enumerate(scenes):
            code = scene.get("manim_code") or ""
            scene_num = scene.get("scene_index", idx)

            if len(code) < 400:
                errors.append(f"Scene {scene_num}: manim_code too short ({len(code)} chars).")

            play_calls = len(re.findall(r"\bself\.play\(", code))
            if play_calls < 4:
                errors.append(f"Scene {scene_num}: needs more animations (>= 4 self.play calls, has {play_calls}).")

            # Detect graph and transform scenes
            if "Axes(" in code and "plot(" in code:
                has_graph = True
            if "Transform" in code:
                has_transform = True

            # Visual structures
            if any(tok in code for tok in (
                "Arrow(", "RoundedRectangle(", "Square(", "Circle(",
                "Axes(", "NumberPlane(", "Dot(", "Line(", "Brace(",
                "SurroundingRectangle(", "Polygon(", "RegularPolygon(",
                "plot(", "VGroup(",
            )):
                visual_structure_count += 1

            # ManimGL patterns
            if "from manimlib import" in code and "from manim import" not in code:
                errors.append(f"Scene {scene_num}: uses 'from manimlib import' — MUST use 'from manim import *'.")
            if re.search(r'\bShowCreation\(', code):
                errors.append(f"Scene {scene_num}: uses ShowCreation() — MUST use Create().")
            if re.search(r'\.get_graph\(', code):
                errors.append(f"Scene {scene_num}: uses .get_graph() — MUST use .plot().")

            # Crash-prone patterns
            if re.search(r'\b(?:MathTex|Tex)\s*\(', code):
                errors.append(f"Scene {scene_num}: uses MathTex/Tex — MUST use Text() with Unicode.")
            if re.search(r'\bTransformMatchingTex\(', code):
                errors.append(f"Scene {scene_num}: uses TransformMatchingTex — use ReplacementTransform.")
            if re.search(r'\.get_graph_label\(\s*\w[\w.]*\s*,\s*["\']', code):
                errors.append(f"Scene {scene_num}: get_graph_label() with string arg triggers LaTeX.")
            if re.search(r'from\s+manim_\w+\s+import', code):
                errors.append(f"Scene {scene_num}: imports a manim plugin — only manim and numpy allowed.")
            if re.search(r'lambda\s+\w\s*:\s*[^,\n]*/\s*\w(?!\s*if)', code):
                errors.append(f"Scene {scene_num}: unguarded division in lambda — guard with abs(x) > 0.01.")

            # Missing cleanup
            if "FadeOut(m) for m in self.mobjects" not in code:
                errors.append(f"Scene {scene_num}: missing final FadeOut cleanup.")

            # Text density check
            text_creates = len(re.findall(r'\b(?:Text|MathTex|Tex)\s*\(', code))
            bulk_fadeouts = len(re.findall(r'FadeOut\(\w+\)\s+for\s+\w+\s+in\s+self\.mobjects', code))
            individual_fadeouts = len(re.findall(r'\bFadeOut\s*\(', code)) - bulk_fadeouts
            opacity_dims = len(re.findall(r'\.set_opacity\s*\(\s*0\.', code))
            has_containers = any(tok in code for tok in (
                "RoundedRectangle(", "Square(", "VGroup(", "arrange(",
            ))
            density_threshold = 12 if has_containers else 8
            total_cleanup = individual_fadeouts + bulk_fadeouts + opacity_dims
            if text_creates > density_threshold and total_cleanup < 2:
                errors.append(
                    f"Scene {scene_num}: creates {text_creates} text objects but only "
                    f"{total_cleanup} cleanup actions. Add FadeOut or dim old content."
                )

        if not has_graph:
            errors.append("Missing graph scene with Axes and plotted functions.")
        if not has_transform:
            errors.append("Missing equation/derivation scene with Transform steps.")
        if visual_structure_count < 3:
            errors.append(
                f"Only {visual_structure_count} scenes have visual structures. Need at least 3."
            )

        return errors

    # ──────────────────────────────────────────────────────────────────
    # Shared helpers
    # ──────────────────────────────────────────────────────────────────

    def _request_script(
        self, system_prompt: str, user_message: str, max_tokens: int = 16384,
    ) -> tuple[str, float]:
        t0 = time.perf_counter()
        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as e:
            logger.error("[script_gen] │  Claude API call FAILED: %s", e)
            raise
        elapsed = time.perf_counter() - t0
        logger.info("[script_gen] │  Claude API response in %.1fs", elapsed)
        logger.info(
            "[script_gen] │  Usage: input=%d tokens, output=%d tokens",
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        logger.info("[script_gen] │  Stop reason: %s", response.stop_reason)
        return response.content[0].text, elapsed

    def _parse_response(self, response_text: str) -> dict:
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
            logger.error("[script_gen] Failed to parse JSON: %s", e)
            logger.error("[script_gen] Response text: %s", text[:1000])
            raise ValueError(f"LLM did not return valid JSON: {e}")

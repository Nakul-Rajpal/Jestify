"""Service for generating educational scripts using the Anthropic Claude API.

Uses a two-API-call architecture:
  Call 1 — Generate the narration script in the character's voice (no code).
  Call 2 — Generate synchronized ManimCE code based on the narration.
"""

import asyncio
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import anthropic
import httpx

from shared.contracts.character_schema import CHARACTER_PERSONALITIES
from shared.contracts.enums import Character, Difficulty
from shared.contracts.pipeline_schema import GeneratedScript

from ..config import settings
from .context7_docs import get_manim_docs
from .fewshot_examples import NARRATION_FEWSHOT, CODE_FEWSHOT

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-20250514"          # narration (creative writing)
CODE_MODEL = os.getenv("CODE_MODEL", "claude-opus-4-6")  # code gen
MAX_CODE_WORKERS = int(os.getenv("MAX_CODE_WORKERS", "8"))  # parallel scene code gen
FAST_MODE = os.getenv("FAST_GENERATION_MODE", "true").lower() in {"1", "true", "yes"}
ENABLE_CONTEXT7 = os.getenv("ENABLE_CONTEXT7_DOCS", "false").lower() in {"1", "true", "yes"}
MAX_SOURCE_CHARS = int(os.getenv("MAX_SOURCE_CHARS", "8000"))
FAST_CODE_MAX_TOKENS = int(os.getenv("FAST_CODE_MAX_TOKENS", "8192"))

# Ollama integration — set CODE_PROVIDER=ollama to use a local manim-finetuned model
CODE_PROVIDER = os.getenv("CODE_PROVIDER", "anthropic").lower()  # "anthropic" or "ollama"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CODE_MODEL = os.getenv("OLLAMA_CODE_MODEL", "maternion/manim-coder")


class _DifficultyConfig:
    """Per-difficulty scene count and timing configuration."""

    __slots__ = (
        "target_scenes", "min_scene_seconds", "max_scene_seconds",
        "total_min_seconds", "total_max_seconds", "min_visual_structure_scenes",
        "code_max_tokens", "min_words_per_scene", "max_words_per_scene",
        "min_play_calls",
    )

    def __init__(
        self, target_scenes: int, min_scene_seconds: int,
        max_scene_seconds: int, code_max_tokens: int,
        min_words_per_scene: int, max_words_per_scene: int,
        min_play_calls: int,
    ):
        self.target_scenes = target_scenes
        self.min_scene_seconds = min_scene_seconds
        self.max_scene_seconds = max_scene_seconds
        self.total_min_seconds = target_scenes * min_scene_seconds
        self.total_max_seconds = target_scenes * max_scene_seconds
        self.min_visual_structure_scenes = max(2, target_scenes // 2)
        self.code_max_tokens = code_max_tokens
        # Narration length (drives TTS audio duration — ~150 WPM)
        self.min_words_per_scene = min_words_per_scene
        self.max_words_per_scene = max_words_per_scene
        # Minimum self.play() calls per scene (drives animation duration)
        self.min_play_calls = min_play_calls


# Frontend promises: beginner ~2min, intermediate ~4min, advanced ~8min
# Word counts calibrated to TTS at ~150 WPM:
#   45 words ≈ 18s, 60 words ≈ 24s, 80 words ≈ 32s, 100 words ≈ 40s, 120 words ≈ 48s
DIFFICULTY_CONFIGS: dict[Difficulty, _DifficultyConfig] = {
    Difficulty.BEGINNER: _DifficultyConfig(
        target_scenes=5, min_scene_seconds=20,
        max_scene_seconds=28, code_max_tokens=FAST_CODE_MAX_TOKENS,
        min_words_per_scene=50, max_words_per_scene=70,
        min_play_calls=4,
    ),
    Difficulty.INTERMEDIATE: _DifficultyConfig(
        target_scenes=8, min_scene_seconds=25,
        max_scene_seconds=35, code_max_tokens=FAST_CODE_MAX_TOKENS * 2,
        min_words_per_scene=65, max_words_per_scene=90,
        min_play_calls=5,
    ),
    Difficulty.ADVANCED: _DifficultyConfig(
        target_scenes=12, min_scene_seconds=30,
        max_scene_seconds=45, code_max_tokens=FAST_CODE_MAX_TOKENS * 3,
        min_words_per_scene=75, max_words_per_scene=110,
        min_play_calls=6,
    ),
}

# Backwards-compatible defaults (used where difficulty isn't available)
FAST_TARGET_SCENES = DIFFICULTY_CONFIGS[Difficulty.BEGINNER].target_scenes
FAST_MIN_SCENE_SECONDS = DIFFICULTY_CONFIGS[Difficulty.BEGINNER].min_scene_seconds
FAST_MAX_SCENE_SECONDS = DIFFICULTY_CONFIGS[Difficulty.BEGINNER].max_scene_seconds
TARGET_TOTAL_MIN_SECONDS = DIFFICULTY_CONFIGS[Difficulty.BEGINNER].total_min_seconds
TARGET_TOTAL_MAX_SECONDS = DIFFICULTY_CONFIGS[Difficulty.BEGINNER].total_max_seconds
MIN_VISUAL_STRUCTURE_SCENES = DIFFICULTY_CONFIGS[Difficulty.BEGINNER].min_visual_structure_scenes

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
MANIM COMMUNITY EDITION (ManimCE v0.19–v0.20) — JESTIFY QUICK REFERENCE
=========================================================================
Import: from manim import *   Base class: MovingCameraScene (always)

TEXT — LaTeX is NOT installed. Use Text() for EVERYTHING including math:
  Text("f(x) = x²", font_size=36, color=BLUE)
  Text("∫₀¹ x dx = ½", font_size=36)   Text("Σᵢ₌₁ⁿ xᵢ", font_size=36)
  MarkupText('<b>Bold</b> <span foreground="blue">colored</span>')
  Unicode math: x² x₁ √ π Σ ∫ → ⇒ ≤ ≥ ≠ ≈ ∞ ± × ÷  ½ ⅓ ¼
  Superscripts: ⁰¹²³⁴⁵⁶⁷⁸⁹ⁿˣⁱ   Subscripts: ₀₁₂₃₄₅₆₇₈₉ₙₓᵢ
  NEVER: MathTex(), Tex(), or get_graph_label()/get_x_axis_label() with plain strings.

SHAPES:
  Circle(radius=1.0), Square(side_length=1.0), Rectangle(width, height)
  RoundedRectangle(corner_radius=0.15, width=4, height=2)
  Polygon(*points), RegularPolygon(n=6), Arc(angle=PI/2)
  Dot(point), Line(start, end), Arrow(start, end), DashedLine(start, end)
  NumberPlane(x_range, y_range), NumberLine(x_range)
  Brace(mob, direction), SurroundingRectangle(mob, color=YELLOW, buff=0.15)
  VGroup(mob1, mob2, ...)   — group and transform together

AXES & GRAPHS:
  Axes(x_range=[-3,3,1], y_range=[-1,9,2], x_length=7, y_length=5,
       axis_config={"include_numbers": True})
  NEVER use x_range wider than [-5,5,1].
  # Axis labels — MUST be Text(), never plain strings (strings crash with LaTeX error):
  x_lab = axes.get_x_axis_label(Text("x", font_size=28))
  y_lab = axes.get_y_axis_label(Text("f(x)", font_size=28))
  graph = axes.plot(lambda x: x**2, color=BLUE, x_range=[-3, 3])
  # For singularities: axes.plot(lambda x: 1/x if abs(x) > 0.01 else 0, ...)
  dot = Dot(axes.c2p(x, y))
  area = axes.get_area(graph, x_range=[0, 2], color=BLUE, opacity=0.3)
  # Graph labels — always use Text().next_to(), not get_graph_label() with strings:
  graph_label = Text("f(x) = x²", color=BLUE, font_size=28)
  graph_label.next_to(axes.c2p(2, 4), RIGHT)

NODE GRAPHS & TREES (labels MUST be Text dict, never labels=True):
  Graph([1,2,3,4,5], [(1,2),(1,3),(2,4),(2,5)],
        labels={v: Text(str(v), font_size=20) for v in range(1,6)},
        layout="tree", root_vertex=1, vertex_config={"color": BLUE, "radius": 0.3})
  Layouts: "spring", "circular", "tree", "kamada_kawai"
  DiGraph(vertices, edges, labels={v: Text(...) ...})  — directed graph

MATRICES (entries auto-render as Text, never build manually):
  IntegerMatrix([[1,2],[3,4]], left_bracket="(", right_bracket=")")
  DecimalMatrix([[1.5,2.0],[3.1,4.0]])
  Matrix([[1,2],[3,4]])   NEVER: MathTable, MathTex inside matrices.

TABLES:
  Table([["A","B"],["C","D"]], row_labels=[Text("R1"), Text("R2")],
        col_labels=[Text("C1"), Text("C2")], include_outer_lines=True)
  t.add_highlighted_cell((2,2), color=GREEN)   NEVER: MathTable.

BAR CHARTS:
  BarChart(values=[10,20,30], bar_names=["A","B","C"], y_range=[0,35,5])
  chart.get_bar_labels(font_size=30, label_constructor=Text)

POSITIONING:
  mob.to_edge(UP/DOWN/LEFT/RIGHT, buff=0.5)
  mob.next_to(other, DOWN, buff=0.3)
  mob.move_to(point), mob.shift(RIGHT*2 + UP*1)
  VGroup(...).arrange(DOWN, buff=0.4)
  VGroup(...).arrange_in_grid(n_rows, n_cols, buff=0.3)
  Directions: UP DOWN LEFT RIGHT UL UR DL DR ORIGIN

ANIMATIONS:
  Write(mob), Create(mob), FadeIn(mob, shift=UP*0.3), FadeOut(mob)
  ReplacementTransform(src, dst)   — swap text/shapes in-place (no overlap)
  Transform(src, dst), GrowArrow(arrow), GrowFromCenter(mob)
  Indicate(mob, color=YELLOW, scale_factor=1.2)
  Circumscribe(mob, color=YELLOW), Flash(point, color=YELLOW)
  LaggedStart(*anims, lag_ratio=0.2)   — staggered reveals, MANDATORY for lists
  AnimationGroup(*anims)
  mob.animate.shift(RIGHT*2), mob.animate.set_color(YELLOW)
  mob.animate.set_opacity(0.3)         — dim previous elements
  Use Create() NOT ShowCreation().   NEVER TransformMatchingTex.

VALUETRACKER (animated number displays, no LaTeX):
  tracker = ValueTracker(0)
  display = always_redraw(lambda: Text(f"{tracker.get_value():.1f}", font_size=36))
  self.add(display); self.play(tracker.animate.set_value(100), run_time=2)

COLORS: BLUE/RED/GREEN/YELLOW/GOLD/TEAL/PURPLE/MAROON/ORANGE/PINK/GREY/WHITE/BLACK
  Variants: BLUE_A–E, RED_A–E, etc.  Titles: GOLD or WHITE  Highlights: YELLOW
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
        # Some local environments set SSL_CERT_FILE / REQUESTS_CA_BUNDLE to a
        # stale path, which causes httpx/ssl to raise bare FileNotFoundError.
        for env_key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
            env_val = os.getenv(env_key)
            if env_val and not Path(env_val).exists():
                logger.warning(
                    "[script_gen] %s points to missing file '%s'; unsetting for Anthropic client",
                    env_key,
                    env_val,
                )
                os.environ.pop(env_key, None)

        verify: bool | str = True
        try:
            import certifi

            ca_bundle = certifi.where()
            if Path(ca_bundle).exists():
                verify = ca_bundle
            else:
                logger.warning(
                    "[script_gen] certifi bundle path does not exist: %s; using system trust store",
                    ca_bundle,
                )
        except Exception as exc:
            logger.warning("[script_gen] certifi unavailable (%s); using system trust store", exc)

        try:
            http_client = httpx.Client(
                verify=verify,
                timeout=httpx.Timeout(600.0, connect=30.0),
            )
            self.client = anthropic.Anthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                http_client=http_client,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Anthropic client init failed: missing SSL certificate file. "
                "Unset SSL_CERT_FILE/REQUESTS_CA_BUNDLE/CURL_CA_BUNDLE or install certifi."
            ) from exc

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
        logger.info("[script_gen] │  Fast mode: %s", FAST_MODE)

        personality = CHARACTER_PERSONALITIES[character]
        difficulty_instruction = DIFFICULTY_INSTRUCTIONS[difficulty]
        dcfg = DIFFICULTY_CONFIGS[difficulty]
        logger.info(
            "[script_gen] │  Difficulty config: %d scenes, %d-%ds/scene, target %d-%ds total",
            dcfg.target_scenes, dcfg.min_scene_seconds, dcfg.max_scene_seconds,
            dcfg.total_min_seconds, dcfg.total_max_seconds,
        )

        if len(extracted_text) > MAX_SOURCE_CHARS:
            logger.info(
                "[script_gen] │  Truncating source text from %d -> %d chars for speed",
                len(extracted_text),
                MAX_SOURCE_CHARS,
            )
            extracted_text = extracted_text[:MAX_SOURCE_CHARS]

        t0 = time.perf_counter()
        live_docs = _fetch_live_manim_docs(extracted_text) if ENABLE_CONTEXT7 else ""
        docs_elapsed = time.perf_counter() - t0
        logger.info(
            "[script_gen] │  Context7 fetch: %s (%.1fs, %d chars)",
            "enabled" if ENABLE_CONTEXT7 else "disabled",
            docs_elapsed,
            len(live_docs),
        )

        # ── Call 1: Generate narration script (no code) ──────────────
        logger.info("[script_gen] │")
        logger.info("[script_gen] │  ── CALL 1: Narration ──")
        narration_data, narr_elapsed = self._generate_narration(
            extracted_text, personality, difficulty_instruction, user_prompt, dcfg,
        )
        narration_errors = self._validate_narration(narration_data, personality, dcfg)
        if narration_errors and not FAST_MODE:
            logger.warning("[script_gen] │  Narration issues: %s", narration_errors)
            feedback = (
                "Regenerate the full JSON and fix ALL issues:\n- "
                + "\n- ".join(narration_errors)
            )
            narr_user = self._build_narration_user_message(extracted_text, user_prompt, dcfg)
            retry_msg = f"{narr_user}\n\n{feedback}"
            narr_sys = self._build_narration_system_prompt(personality, difficulty_instruction, dcfg)
            resp, retry_elapsed = self._request_script(narr_sys, retry_msg, max_tokens=4096)
            narr_elapsed += retry_elapsed
            narration_data = self._parse_response(resp)
            remaining = self._validate_narration(narration_data, personality, dcfg)
            if remaining:
                logger.warning("[script_gen] │  Narration issues remain: %s. Continuing.", remaining)

        logger.info("[script_gen] │  Narration OK — %d scenes, title: %s",
                     len(narration_data.get("scenes", [])), narration_data.get("title"))

        if FAST_MODE:
            narration_scenes = narration_data.get("scenes") or []
            narration_data["scenes"] = self._optimize_scenes_for_speed(narration_scenes, dcfg)
            narration_data["total_scenes"] = len(narration_data["scenes"])
            logger.info(
                "[script_gen] │  Fast mode trimmed narration to %d scenes",
                narration_data["total_scenes"],
            )

        # ── Call 2: Generate ManimCE code (narration as input) ───────
        logger.info("[script_gen] │")
        logger.info("[script_gen] │  ── CALL 2: Code generation ──")
        code_data, code_elapsed = self._generate_code(narration_data, live_docs, dcfg)
        code_errors = self._validate_code(code_data, dcfg)
        if code_errors:
            logger.warning("[script_gen] │  Code issues (non-blocking): %s", code_errors)

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
        if FAST_MODE:
            merged_scenes = self._optimize_scenes_for_speed(merged_scenes, dcfg)

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
        dcfg: _DifficultyConfig,
    ) -> tuple[dict, float]:
        """Call 1: generate narration script only (no Manim code)."""
        sys_prompt = self._build_narration_system_prompt(personality, difficulty_instruction, dcfg)
        user_msg = self._build_narration_user_message(extracted_text, user_prompt, dcfg)
        logger.info("[script_gen] │  Narration system prompt: %d chars", len(sys_prompt))
        logger.info("[script_gen] │  Narration user message: %d chars", len(user_msg))
        # Scale max_tokens with scene count
        narr_max_tokens = max(2048, dcfg.target_scenes * 400)
        resp, elapsed = self._request_script(sys_prompt, user_msg, max_tokens=narr_max_tokens)
        logger.info("[script_gen] │  Narration response: %d chars (%.1fs)", len(resp), elapsed)
        return self._parse_response(resp), elapsed

    def _build_narration_system_prompt(
        self, personality, difficulty_instruction: str, dcfg: _DifficultyConfig,
    ) -> str:
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

3. NO REPETITION (CRITICAL): Each scene MUST cover NEW content. Never repeat \
   concepts, examples, or explanations from earlier scenes. If Scene 1 explains \
   what a derivative is, Scene 2 must move FORWARD (e.g., the power rule), not \
   re-explain derivatives. Before writing each scene, mentally check: "Did I \
   already cover this?" If yes, skip it and teach the NEXT concept.

4. PROGRESSIVE COVERAGE: Work through the source material IN ORDER. \
   Scene 0 introduces the topic, then each subsequent scene covers the next \
   logical concept from the source material. By the final scene, you should \
   have covered all the key ideas. Think of it as a lecture outline — each \
   scene is the next section, not a remix of the same section.

5. NARRATION LENGTH: Each scene's narration_text MUST be {dcfg.min_words_per_scene}-{dcfg.max_words_per_scene} words \
   (this controls video duration via text-to-speech — longer narration = longer scene). \
   Count your words carefully. Do NOT go under {dcfg.min_words_per_scene} words per scene.

6. CHARACTER VOICE: The narration must sound like the character is personally \
   explaining the topic. NOT a generic textbook. Use catchphrases, tone, and \
   personality consistently throughout ALL scenes.

7. VISUAL DESCRIPTIONS: For each scene, write a visual_description field that \
   describes what SHOULD appear on screen. Be specific about what kind of \
   animation or diagram would best illustrate the narration. Examples:
   - "Show a graph of f(x) = x² with a tangent line sliding along the curve"
   - "Display a tree diagram with the root labeled 'Algorithm' and three children"
   - "Build up the equation step by step: first show x², then transform to 2x"
   The visual_description guides the animation generator to create visuals that \
   are synchronized with the narration.

DIFFICULTY: {difficulty_instruction}

=== VIDEO STRUCTURE (MANDATORY) ===
- Generate exactly {dcfg.target_scenes} scenes for a video totaling about {dcfg.total_min_seconds} to {dcfg.total_max_seconds} seconds.
- Scene 0: Concept introduction ({dcfg.min_scene_seconds}-{dcfg.max_scene_seconds}s) — hook with character analogy + key concepts
- Scene 1 or 2: GRAPH SCENE (MANDATORY) — describe a graph/plot that visualizes a \
  function, trend, or relationship. Set manim_scene_type="graph". \
  Even non-math topics can have graphs: growth rates, timelines, comparisons.
- Scene 2 or 3: EQUATION/TRANSFORM SCENE — describe step-by-step derivation or \
  concept evolution. Set manim_scene_type="equation".
- Remaining scenes: Core teaching content ({dcfg.min_scene_seconds}-{dcfg.max_scene_seconds}s each) — diagrams, visual structures
- Last scene: Summary/recap ({dcfg.min_scene_seconds}-{dcfg.max_scene_seconds}s) — key takeaways

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

{NARRATION_FEWSHOT}
"""

    def _build_narration_user_message(
        self, extracted_text: str, user_prompt: Optional[str],
        dcfg: _DifficultyConfig | None = None,
    ) -> str:
        cfg = dcfg or DIFFICULTY_CONFIGS[Difficulty.BEGINNER]
        message = f"""\
Write a concise narration script with exactly {cfg.target_scenes} scenes based on this source material.
Analyze the material carefully — identify the key concepts, relationships, \
and problems, then write engaging narration that TEACHES them.

--- SOURCE MATERIAL ---
{extracted_text}
--- END SOURCE MATERIAL ---

REQUIREMENTS:
1. Generate exactly {cfg.target_scenes} scenes with narration_text and visual_description for each
2. Total video duration: {cfg.total_min_seconds} to {cfg.total_max_seconds} seconds (sum of duration_hint_seconds)
3. Each scene's duration_hint_seconds MUST be {cfg.min_scene_seconds}-{cfg.max_scene_seconds}
4. CRITICAL — NARRATION LENGTH: Each scene's narration_text MUST be {cfg.min_words_per_scene}-{cfg.max_words_per_scene} words. \
This directly controls video length via text-to-speech. Short narration = short video. Count carefully.
5. MANDATORY: At least one scene with manim_scene_type="graph"
6. Include at least one equation/derivation scene
7. Last scene must be a summary/recap
8. visual_description must be specific enough for an animation generator
9. Stay in character throughout — this should sound like a real person teaching
10. CRITICAL — NO REPETITION: Each scene MUST teach NEW content. Cover the source material \
progressively — Scene 0 introduces, each next scene advances to the next concept. \
NEVER re-explain something already covered in a previous scene. If you run out of \
source material, go deeper (examples, applications) rather than repeating.
"""
        if user_prompt:
            message += f"\nAdditional instructions: {user_prompt}\n"
        message += "\nRespond with ONLY the JSON object. No markdown fences."
        return message

    def _validate_narration(self, script_data: dict, personality=None, dcfg: "_DifficultyConfig | None" = None) -> list[str]:
        """Validate narration-only output from Call 1."""
        cfg = dcfg or DIFFICULTY_CONFIGS[Difficulty.BEGINNER]
        errors: list[str] = []
        scenes = script_data.get("scenes") or []
        if len(scenes) < cfg.target_scenes:
            errors.append(f"Need at least {cfg.target_scenes} scenes.")
            return errors

        for idx, scene in enumerate(scenes):
            narration = (scene.get("narration_text") or "").strip()
            word_count = len(narration.split())
            if word_count < cfg.min_words_per_scene - 10:
                errors.append(
                    f"Scene {idx+1} narration_text too short ({word_count} words). "
                    f"Must be {cfg.min_words_per_scene}-{cfg.max_words_per_scene} words."
                )
            if word_count > cfg.max_words_per_scene + 30:
                errors.append(
                    f"Scene {idx+1} narration_text too long ({word_count} words). "
                    f"Keep each scene to {cfg.min_words_per_scene}-{cfg.max_words_per_scene} words."
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

        # ── Content repetition check ──
        # Extract significant phrases (4+ word n-grams) from each scene and
        # flag if two non-adjacent scenes share too many of them.
        _stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "and",
            "but", "or", "nor", "not", "so", "yet", "both", "either",
            "neither", "each", "every", "all", "any", "this", "that",
            "these", "those", "it", "its", "we", "you", "they", "them",
            "our", "your", "their", "he", "she", "his", "her", "i", "me",
            "my", "us", "about", "up", "out", "just", "like", "know",
            "now", "let", "look", "see", "think", "get", "make", "go",
            "here", "there", "when", "how", "what", "which", "who",
            "where", "why", "than", "then", "also", "very", "more",
            "some", "one", "two", "new", "way", "well", "right",
        }

        def _extract_content_words(text: str) -> set[str]:
            """Extract meaningful content words from narration text."""
            words = re.findall(r'[a-z]+', text.lower())
            return {w for w in words if w not in _stop_words and len(w) > 3}

        scene_words = []
        for scene in scenes:
            narration = (scene.get("narration_text") or "").strip()
            scene_words.append(_extract_content_words(narration))

        for i in range(len(scene_words)):
            for j in range(i + 2, len(scene_words)):  # skip adjacent (natural overlap)
                if not scene_words[i] or not scene_words[j]:
                    continue
                overlap = scene_words[i] & scene_words[j]
                smaller = min(len(scene_words[i]), len(scene_words[j]))
                if smaller > 0 and len(overlap) / smaller > 0.5:
                    errors.append(
                        f"Scenes {i} and {j} share too much content "
                        f"({len(overlap)} overlapping words: "
                        f"{', '.join(sorted(overlap)[:5])}...). "
                        f"Each scene must teach NEW concepts — no repetition."
                    )

        total_duration = sum(
            float(s.get("duration_hint_seconds", 0) or 0) for s in scenes
        )
        if total_duration < (cfg.total_min_seconds - 10):
            errors.append(
                f"Total duration too short ({total_duration:.1f}s). "
                f"Target >= {cfg.total_min_seconds}s."
            )

        has_graph = any(
            str(s.get("manim_scene_type") or "").lower() == "graph" for s in scenes
        )
        if not has_graph:
            errors.append("At least one scene must have manim_scene_type='graph'.")

        return errors

    def _optimize_scenes_for_speed(self, scenes: list[dict], dcfg: "_DifficultyConfig | None" = None) -> list[dict]:
        """Trim scene count and cap durations based on difficulty config."""
        cfg = dcfg or DIFFICULTY_CONFIGS[Difficulty.BEGINNER]
        optimized = []
        for i, scene in enumerate(scenes[:cfg.target_scenes]):
            dur = int(float(scene.get("duration_hint_seconds", cfg.max_scene_seconds) or cfg.max_scene_seconds))
            scene = dict(scene)
            scene["scene_index"] = i
            scene["duration_hint_seconds"] = max(cfg.min_scene_seconds, min(dur, cfg.max_scene_seconds))
            optimized.append(scene)
        return optimized

    # ──────────────────────────────────────────────────────────────────
    # Call 2 — Code generation
    # ──────────────────────────────────────────────────────────────────

    def _generate_code(
        self, narration_data: dict, live_manim_docs: str, dcfg: "_DifficultyConfig | None" = None,
    ) -> tuple[dict, float]:
        """Call 2: generate ManimCE code. Anthropic=parallel, Ollama=sequential."""
        cfg = dcfg or DIFFICULTY_CONFIGS[Difficulty.BEGINNER]
        scenes = narration_data.get("scenes", [])
        title = narration_data.get("title", "Untitled")

        if CODE_PROVIDER == "ollama":
            return self._generate_code_ollama(scenes, cfg)

        # ── Anthropic path: parallel per-scene calls ──
        sys_prompt = self._build_code_system_prompt(live_manim_docs, cfg)
        logger.info(
            "[script_gen] │  Code provider: anthropic, model: %s (parallel, %d scenes)",
            CODE_MODEL, len(scenes),
        )
        logger.info("[script_gen] │  Code system prompt: %d chars", len(sys_prompt))

        t0 = time.perf_counter()
        results: dict[int, dict] = {}
        errors: dict[int, str] = {}

        # Build a lookup for adjacent scene context
        scene_by_idx = {s.get("scene_index", i): s for i, s in enumerate(scenes)}

        def _gen_one(scene_data: dict) -> tuple[int, dict]:
            idx = scene_data.get("scene_index", 0)
            prev_scene = scene_by_idx.get(idx - 1)
            next_scene = scene_by_idx.get(idx + 1)
            user_msg = self._build_single_scene_user_message(
                scene_data, title, cfg, prev_scene=prev_scene, next_scene=next_scene,
            )
            resp_text, _ = self._request_code(sys_prompt, user_msg, max_tokens=4096)
            parsed = self._parse_response(resp_text)
            # Handle both {"scene_index":0,"manim_code":"..."} and {"scenes":[...]}
            if isinstance(parsed, dict) and "scenes" in parsed:
                scene_result = parsed["scenes"][0] if parsed["scenes"] else {}
            elif isinstance(parsed, list):
                scene_result = parsed[0] if parsed else {}
            else:
                scene_result = parsed
            scene_result["scene_index"] = idx
            return idx, scene_result

        workers = min(MAX_CODE_WORKERS, len(scenes))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_gen_one, s): s.get("scene_index", i) for i, s in enumerate(scenes)}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    scene_idx, scene_result = future.result()
                    results[scene_idx] = scene_result
                    logger.info("[script_gen] │  Scene %d code: %d chars", scene_idx, len(scene_result.get("manim_code", "")))
                except Exception as e:
                    errors[idx] = str(e)
                    logger.error("[script_gen] │  Scene %d code gen FAILED: %s", idx, e)

        elapsed = time.perf_counter() - t0
        logger.info("[script_gen] │  All code generated in %.1fs (%d OK, %d failed)", elapsed, len(results), len(errors))

        # Assemble in scene order
        ordered_scenes = [results[i] for i in sorted(results.keys())]
        return {"scenes": ordered_scenes}, elapsed

    def _generate_code_ollama(
        self, scenes: list[dict], dcfg: "_DifficultyConfig",
    ) -> tuple[dict, float]:
        """Generate ManimCE code via Ollama — sequential calls with simplified prompts."""
        logger.info(
            "[script_gen] │  Code provider: ollama, model: %s (sequential, %d scenes)",
            OLLAMA_CODE_MODEL, len(scenes),
        )

        t0 = time.perf_counter()
        results: dict[int, dict] = {}
        errors: dict[int, str] = {}

        for scene_data in scenes:
            idx = scene_data.get("scene_index", 0)
            narration = scene_data.get("narration_text", "")
            visual = scene_data.get("visual_description", "")
            stype = scene_data.get("manim_scene_type", "custom")
            dur = scene_data.get("duration_hint_seconds", 20)

            try:
                code, elapsed_one = self._request_code_ollama(
                    idx, narration, visual, stype, dur,
                )
                results[idx] = {"scene_index": idx, "manim_code": code}
                logger.info(
                    "[script_gen] │  Scene %d code: %d chars (%.1fs)",
                    idx, len(code), elapsed_one,
                )
            except Exception as e:
                errors[idx] = str(e)
                logger.error("[script_gen] │  Scene %d ollama FAILED: %s", idx, e)

        elapsed = time.perf_counter() - t0
        logger.info(
            "[script_gen] │  All code generated in %.1fs (%d OK, %d failed)",
            elapsed, len(results), len(errors),
        )

        ordered_scenes = [results[i] for i in sorted(results.keys())]
        return {"scenes": ordered_scenes}, elapsed

    def _build_code_system_prompt(self, live_manim_docs: str = "", dcfg: "_DifficultyConfig | None" = None) -> str:
        cfg = dcfg or DIFFICULTY_CONFIGS[Difficulty.BEGINNER]
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
4. The narrator speaks at ~150 words per minute. Keep each scene concise.
5. When the narrator says "look at this graph", the graph should be appearing.
6. When the narrator says "notice how X changes", X should be animating.
7. Match the total animation duration to duration_hint_seconds for each scene.

{MANIMCE_REFERENCE}
{live_docs_section}

=== LAYOUT & VISUAL RULES ===
Frame: 14.2 x 8 units. Safe zone: x in [-6.0, 6.0], y in [-3.2, 3.2].
There is NO camera auto-zoom — you MUST keep all content within the safe zone.
Oversized mobjects are clamped, but the camera stays fixed.
- Title at UP*3.2, main content at DOWN*0.3, sprite safe zone: x<=-4.2, y>=1.4
- Font sizes: headers 40-48, body 28-36, minimum 24. Use weight=BOLD for titles.
- Max 2 text elements on screen at any time. Use LaggedStart for lists, NEVER bulk FadeIn.
- Use visual structures (graphs, diagrams, tables) NOT text walls.
- Colors on BLACK: TITLES=WHITE/GOLD, PRIMARY=BLUE, SECONDARY=GREEN, HIGHLIGHT=YELLOW.

=== TEXT OVERLAP PREVENTION (CRITICAL — READ CAREFULLY) ===
Text overlapping is the #1 visual quality issue. You MUST follow these rules:
1. BEFORE adding any new Text(), ALWAYS FadeOut the previous text in that region.
   WRONG: self.play(Write(text_a)) ... self.play(Write(text_b))  # text_b lands on text_a!
   RIGHT: self.play(Write(text_a)) ... self.play(FadeOut(text_a)) ... self.play(Write(text_b))
2. Use ReplacementTransform to swap text in-place (old becomes new, no overlap):
   self.play(ReplacementTransform(old_text, new_text), run_time=1.2)
3. If you MUST keep old content visible while adding new content, position them in \
   SEPARATE non-overlapping regions (e.g., old at UP*1.5, new at DOWN*1.0).
4. For graph scenes: place labels ONLY with .next_to() relative to the graph element. \
   NEVER place free-floating Text near a graph — it WILL overlap axes/labels.
5. When transitioning between content sections, do a section cleanup first:
   self.play(*[FadeOut(m) for m in self.mobjects if m is not title], run_time=0.8)
6. NEVER have more than 1 descriptive text + 1 title visible simultaneously. \
   If you need to show a new explanation, FadeOut the old one first.
7. For progressive reveals (bullet points), use VGroup.arrange(DOWN) so items \
   stack vertically with automatic spacing — NEVER position them manually at the \
   same coordinates.

=== SCENE LIFECYCLE (MANDATORY) ===
1. Title first: title.move_to(UP * 3.2)
2. Build content below title — keep a SINGLE content region, clear it between sections
3. BETWEEN SECTIONS: FadeOut ALL old content (except title) before adding new content:
     self.play(*[FadeOut(m) for m in self.mobjects if m is not title], run_time=0.8)
4. KEEP FINAL CONTENT VISIBLE: Do NOT FadeOut at the end of the scene. \
   Leave your last visual content on screen. The rendering system handles transitions \
   automatically. End with self.wait(2) so the final frame holds.

=== IMPORTANT RULES ===
1. Imports: from manim import * and import numpy as np only. No other imports.
2. Class name: Scene000, Scene001, Scene002, etc. ONE class per file.
3. NEVER use MathTex(), Tex(), labels=True on graphs, or plain strings in axis label methods.
4. Every self.play() MUST have run_time=1.0–2.5 seconds.
5. Each scene needs >= {cfg.min_play_calls} self.play() calls to reach duration_hint_seconds.
6. DURATION: Add self.wait(1)–self.wait(2) between sections to match duration_hint_seconds. \
   The narration audio runs over the animation — short animations cut the video.
7. TEXT WIDTH SAFETY: text.set_width(min(text.width, 8.5)) on any Text mobject.
8. TEXT OVERLAP (see section above): FadeOut old text before adding new text in same region. \
   Use ReplacementTransform to swap in-place. Never let two Text objects overlap.
9. SECTION CLEANUP: self.play(*[FadeOut(m) for m in self.mobjects if m is not title], run_time=0.8)
10. KEEP FINAL CONTENT VISIBLE: Never FadeOut at end. End with self.wait(2).
11. Minimum font_size: 24. Weight=BOLD for titles.

=== OUTPUT FORMAT ===
Respond with ONLY valid JSON (no markdown fences, no extra text):
{{
    "scene_index": 0,
    "manim_code": "from manim import *\\nimport numpy as np\\n\\nclass Scene000(MovingCameraScene):\\n    def construct(self):\\n        ..."
}}

The manim_code MUST be COMPLETE, RUNNABLE ManimCE Python code:
- Start with: from manim import * and import numpy as np
- Define ONE MovingCameraScene subclass named Scene{{NNN}} (Scene000, Scene001, etc.)
- 25-55 lines of animation code
- Duration must match duration_hint_seconds
- KEEP final content visible — do NOT FadeOut at the end. End with self.wait(2)

{CODE_FEWSHOT}
"""

    def _build_code_user_message(self, narration_data: dict, dcfg: "_DifficultyConfig | None" = None) -> str:
        cfg = dcfg or DIFFICULTY_CONFIGS[Difficulty.BEGINNER]
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
4. At least {cfg.min_visual_structure_scenes} scenes must have visual structures (graphs, diagrams, trees, tables)
5. Each scene needs >= {cfg.min_play_calls} self.play() calls with explicit run_time (1.0-2.5s each)
6. CRITICAL: Animation duration MUST match duration_hint_seconds. Add self.wait() pauses between sections.
7. NEVER use MathTex or Tex — use Text() with Unicode for math
8. KEEP final content visible at the end — do NOT FadeOut. End with self.wait(2)

Respond with ONLY the JSON object. No markdown fences.
"""

    def _build_single_scene_user_message(
        self, scene_data: dict, title: str, dcfg: "_DifficultyConfig | None" = None,
        prev_scene: dict | None = None, next_scene: dict | None = None,
    ) -> str:
        """Build a user message for a single scene's code generation."""
        cfg = dcfg or DIFFICULTY_CONFIGS[Difficulty.BEGINNER]
        idx = scene_data.get("scene_index", 0)
        dur = scene_data.get("duration_hint_seconds", 30)
        stype = scene_data.get("manim_scene_type", "custom")
        narration = scene_data.get("narration_text", "")
        visual = scene_data.get("visual_description", "")

        scene_type_hint = ""
        if stype == "graph":
            scene_type_hint = "\nMANDATORY: This scene MUST use Axes(...) + axes.plot(...)."
        elif stype == "equation":
            scene_type_hint = "\nMANDATORY: This scene MUST use ReplacementTransform for step-by-step derivation."

        # Provide adjacent scene context so code gen knows what comes before/after
        context_block = ""
        if prev_scene or next_scene:
            context_block = "\nCONTEXT (for visual continuity — do NOT duplicate content):"
            if prev_scene:
                prev_narr = (prev_scene.get("narration_text") or "")[:120]
                prev_type = prev_scene.get("manim_scene_type", "custom")
                context_block += (
                    f"\n  PREVIOUS Scene {prev_scene.get('scene_index', '?')} ({prev_type}): "
                    f"\"{prev_narr}...\""
                )
            if next_scene:
                next_narr = (next_scene.get("narration_text") or "")[:120]
                next_type = next_scene.get("manim_scene_type", "custom")
                context_block += (
                    f"\n  NEXT Scene {next_scene.get('scene_index', '?')} ({next_type}): "
                    f"\"{next_narr}...\""
                )
            context_block += (
                "\n  Your scene must cover ONLY what its narration says — "
                "do NOT repeat visuals or content from adjacent scenes."
            )

        return f"""\
Generate ManimCE code for Scene {idx} of the video "{title}".

SCENE {idx} ({dur}s, {stype}):
Narration: "{narration}"
Visual description: "{visual}"
{scene_type_hint}{context_block}
REQUIREMENTS:
1. Complete, runnable ManimCE code with class Scene{idx:03d}(MovingCameraScene)
2. >= {cfg.min_play_calls} self.play() calls with explicit run_time (1.0-2.5s each)
3. Animation duration MUST fill {dur} seconds. Add self.wait() pauses between sections.
4. NEVER use MathTex or Tex — use Text() with Unicode for math
5. KEEP final content visible — do NOT FadeOut at the end. End with self.wait(2)

Respond with ONLY a JSON object: {{"scene_index": {idx}, "manim_code": "..."}}
No markdown fences.
"""

    def _request_code(
        self, system_prompt: str, user_message: str, max_tokens: int = 4096,
    ) -> tuple[str, float]:
        """Make an API call using the fast CODE_MODEL for code generation (Anthropic only)."""
        t0 = time.perf_counter()
        try:
            response = self.client.messages.create(
                model=CODE_MODEL,
                max_tokens=max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as e:
            logger.error("[script_gen] │  Code API call FAILED: %s", e)
            raise
        elapsed = time.perf_counter() - t0
        cache_read = getattr(response.usage, "cache_read_input_tokens", 0)
        cache_create = getattr(response.usage, "cache_creation_input_tokens", 0)
        logger.info(
            "[script_gen] │  Code API: %.1fs, in=%d, out=%d, cache_read=%d, cache_create=%d",
            elapsed, response.usage.input_tokens, response.usage.output_tokens,
            cache_read, cache_create,
        )
        return response.content[0].text, elapsed

    # ──────────────────────────────────────────────────────────────────
    # Ollama integration — simplified prompt for local manim-finetuned model
    # ──────────────────────────────────────────────────────────────────

    def _request_code_ollama(
        self, scene_index: int, narration: str, visual_desc: str,
        scene_type: str, duration: int,
    ) -> tuple[str, float]:
        """Call local Ollama with a short, focused prompt the model can handle."""
        # The manim-finetuned model works best with simple, direct prompts
        type_hint = ""
        if scene_type == "graph":
            type_hint = "\n- MUST use Axes() + axes.plot() for graphing. Label axes with Text()."
        elif scene_type == "equation":
            type_hint = "\n- MUST use ReplacementTransform to show step-by-step derivation."
        elif scene_type == "diagram":
            type_hint = "\n- Use shapes (Rectangle, Circle, Arrow, etc.) to build a diagram."

        prompt = f"""\
Write a complete ManimCE Python scene class called Scene{scene_index:03d} that inherits from MovingCameraScene.

The animation should visualize: {visual_desc}

Rules:
- Start with: from manim import *
- import numpy as np
- Use Text() for all text (never MathTex or Tex). Use Unicode for math symbols.
- Use Create() not ShowCreation(). Use axes.plot() not get_graph().
- Keep content within safe zone: x in [-6,6], y in [-3.2,3.2]
- Minimum font_size=24. Use weight=BOLD for titles.
- Every self.play() must have run_time=1.0 to 2.5
- Total animation should last ~{duration} seconds. Use self.wait() to fill time.
- End with self.wait(2). Do NOT FadeOut at the end.
- FadeOut old text before writing new text in the same area.{type_hint}

Write ONLY the Python code, nothing else."""

        t0 = time.perf_counter()
        logger.info(
            "[script_gen] │  Ollama request: scene=%d, model=%s",
            scene_index, OLLAMA_CODE_MODEL,
        )
        try:
            resp = httpx.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": OLLAMA_CODE_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are a ManimCE animation expert. Write complete, runnable Python code. Output ONLY code, no explanations."},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {
                        "num_predict": max(2048, int(FAST_CODE_MAX_TOKENS / 2)),
                        "temperature": 0.3,
                        "top_p": 0.8,
                        "top_k": 40,
                        "repeat_penalty": 1.1,
                    },
                },
                timeout=httpx.Timeout(300.0, connect=10.0),
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error("[script_gen] │  Ollama API call FAILED: %s", e)
            raise
        elapsed = time.perf_counter() - t0
        data = resp.json()
        text = data.get("message", {}).get("content", "")
        eval_count = data.get("eval_count", 0)
        prompt_count = data.get("prompt_eval_count", 0)
        logger.info(
            "[script_gen] │  Ollama API: %.1fs, prompt_tokens=%d, eval_tokens=%d",
            elapsed, prompt_count, eval_count,
        )

        # Extract Python code from response — model may wrap in markdown fences
        code = self._extract_code_from_ollama_response(text, scene_index)
        return code, elapsed

    @staticmethod
    def _extract_code_from_ollama_response(text: str, scene_index: int) -> str:
        """Extract clean Python code from Ollama response, handling markdown fences."""
        # Try to extract from ```python ... ``` blocks
        fence_match = re.search(r'```(?:python)?\s*\n(.*?)```', text, re.DOTALL)
        if fence_match:
            code = fence_match.group(1).strip()
        else:
            # No fences — use the raw text, strip any leading prose
            lines = text.strip().split('\n')
            code_start = 0
            for i, line in enumerate(lines):
                if line.strip().startswith(('from manim', 'import ', 'class Scene')):
                    code_start = i
                    break
            code = '\n'.join(lines[code_start:]).strip()

        # Validate it looks like Python code
        if 'from manim' not in code and 'class Scene' not in code:
            raise ValueError(
                f"Ollama response for scene {scene_index} did not contain valid Manim code. "
                f"Response starts with: {text[:200]}"
            )

        # Ensure it has the right class name
        if f'class Scene{scene_index:03d}' not in code:
            code = re.sub(
                r'class\s+Scene\w*\s*\(',
                f'class Scene{scene_index:03d}(',
                code,
                count=1,
            )

        return code

    def _validate_code(self, code_data: dict, dcfg: "_DifficultyConfig | None" = None) -> list[str]:
        """Validate code output from Call 2."""
        cfg = dcfg or DIFFICULTY_CONFIGS[Difficulty.BEGINNER]
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
            if play_calls < cfg.min_play_calls:
                errors.append(f"Scene {scene_num}: needs more animations (>= {cfg.min_play_calls} self.play calls, has {play_calls}).")

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
        if visual_structure_count < cfg.min_visual_structure_scenes:
            errors.append(
                f"Only {visual_structure_count} scenes have visual structures. "
                f"Need at least {cfg.min_visual_structure_scenes}."
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
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_message}],
            )
        except Exception as e:
            logger.error("[script_gen] │  Claude API call FAILED: %s", e)
            raise
        elapsed = time.perf_counter() - t0
        logger.info("[script_gen] │  Claude API response in %.1fs", elapsed)
        cache_read = getattr(response.usage, "cache_read_input_tokens", 0)
        cache_create = getattr(response.usage, "cache_creation_input_tokens", 0)
        logger.info(
            "[script_gen] │  Usage: input=%d, output=%d, cache_read=%d, cache_creation=%d",
            response.usage.input_tokens,
            response.usage.output_tokens,
            cache_read,
            cache_create,
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

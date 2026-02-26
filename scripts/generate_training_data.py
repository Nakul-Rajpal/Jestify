#!/usr/bin/env python3
"""Generate synthetic (narration_scene → manim_code) training pairs for finetuning.

This script:
  1. Iterates over topics in data/topics.json
  2. For each topic × difficulty, calls the narration model (Claude Sonnet 4)
  3. For each scene in the narration, calls the code model (Claude Opus via Anthropic or AWS Bedrock)
  4. Validates each generated code by running an actual Manim render subprocess
  5. Saves all results (pass and fail) to data/training/jestify_dataset.jsonl

Usage:
  # Standard run (uses ANTHROPIC_API_KEY from .env):
  python scripts/generate_training_data.py

  # AWS Bedrock (set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION in .env):
  CODE_PROVIDER=bedrock python scripts/generate_training_data.py

  # Dry run (no API calls, test pipeline logic):
  python scripts/generate_training_data.py --dry-run

  # Small sample first (Checkpoint 2 — review before full run):
  python scripts/generate_training_data.py --max-topics 5

Options:
  --dry-run         Skip API calls, generate dummy data to test pipeline
  --max-topics N    Process only the first N topics (use for sample review)
  --difficulties    Comma-separated list: beginner,intermediate,advanced (default: beginner,intermediate)
  --characters      Comma-separated list: lebron,goku,peter,taylor (default: lebron,goku)
  --resume          Resume from last checkpoint (skips already-generated topics)
  --output FILE     Output JSONL file path (default: data/training/jestify_dataset.jsonl)
"""

import argparse
import ast
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Add project root to path so we can import shared contracts ──────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Load env vars from .env ──────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── Model configuration ──────────────────────────────────────────────────────
NARRATION_MODEL = "claude-sonnet-4-20250514"
CODE_MODEL_ANTHROPIC = os.getenv("CODE_MODEL", "claude-opus-4-6")
# Bedrock model IDs — update if AWS Bedrock changes the model ID format
CODE_MODEL_BEDROCK = os.getenv("BEDROCK_CODE_MODEL", "anthropic.claude-opus-4-5-20250514-v1:0")
NARRATION_MODEL_BEDROCK = os.getenv("BEDROCK_NARRATION_MODEL", "anthropic.claude-sonnet-4-20250514-v1:0")

CODE_PROVIDER = os.getenv("CODE_PROVIDER", "anthropic").lower()  # "anthropic" or "bedrock"
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

MAX_RENDER_TIMEOUT = int(os.getenv("MAX_RENDER_TIMEOUT", "90"))  # seconds per Manim render


# ── Clients ──────────────────────────────────────────────────────────────────

def _build_anthropic_client():
    import anthropic
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _build_bedrock_client():
    import anthropic
    return anthropic.AnthropicBedrock(aws_region=AWS_REGION)


def _get_clients():
    """Return (narration_client, code_client, narration_model_id, code_model_id)."""
    if CODE_PROVIDER == "bedrock":
        logger.info("Using AWS Bedrock for API calls (region: %s)", AWS_REGION)
        client = _build_bedrock_client()
        return client, client, NARRATION_MODEL_BEDROCK, CODE_MODEL_BEDROCK
    else:
        logger.info("Using Anthropic direct API for API calls")
        client = _build_anthropic_client()
        return client, client, NARRATION_MODEL, CODE_MODEL_ANTHROPIC


# ── Prompts ───────────────────────────────────────────────────────────────────

def _build_narration_prompt(topic: str, difficulty: str, character: str) -> tuple[str, str]:
    """Return (system_prompt, user_message) for narration generation."""
    character_personas = {
        "lebron": {
            "display_name": "LeBron James",
            "tone": "Motivational, coach-like, strategic",
            "catchphrases": ["Let's lock in", "Stay focused", "Great fundamentals", "That's the play"],
            "analogy_domain": "basketball, teamwork, strategy, game reading",
            "background": "NBA champion and cultural icon who uses sports analogies to explain everything",
        },
        "goku": {
            "display_name": "Goku",
            "tone": "Playful, enthusiastic, battle-ready, always training",
            "catchphrases": ["Let's get stronger", "That was awesome", "Time to train", "Power level over 9000"],
            "analogy_domain": "training intensity, power levels, martial arts, transformations",
            "background": "Saiyan warrior who frames all learning as power-ups and training arcs",
        },
        "peter": {
            "display_name": "Peter Griffin",
            "tone": "Humorous, casual, exaggerated, self-deprecating",
            "catchphrases": ["Hehehe", "No way", "Alright check this out", "That really grinds my gears"],
            "analogy_domain": "family life, TV shows, food, awkward social situations",
            "background": "Family Guy dad who explains concepts through absurd everyday comparisons",
        },
        "taylor": {
            "display_name": "Taylor Swift",
            "tone": "Expressive, structured, story-driven, detail-oriented",
            "catchphrases": ["Let's break this down", "See the pattern", "Here's the key idea", "This is the era of"],
            "analogy_domain": "songwriting, albums, eras, storytelling arcs, emotional journeys",
            "background": "Pop superstar who frames concepts as songs, eras, and emotional narratives",
        },
    }
    difficulty_instructions = {
        "beginner": "Explain at a beginner level. Use simple language, avoid jargon, and break down into the most fundamental building blocks. 5 scenes.",
        "intermediate": "Explain at an intermediate level. Use some technical terms but always briefly clarify them. Build on foundational knowledge. 8 scenes.",
        "advanced": "Explain at an advanced level. Use proper technical terminology, explore nuances, edge cases, and deeper implications. 12 scenes.",
    }
    scene_counts = {"beginner": 5, "intermediate": 8, "advanced": 12}
    word_counts = {
        "beginner": (50, 70),
        "intermediate": (65, 90),
        "advanced": (75, 110),
    }
    p = character_personas[character]
    d_instr = difficulty_instructions[difficulty]
    n_scenes = scene_counts[difficulty]
    min_words, max_words = word_counts[difficulty]

    system_prompt = f"""\
You are an expert educational script writer creating narration for animated videos like 3Blue1Brown.
Write ONLY narration (what the character says). A separate system generates the animations.

CHARACTER: {p["display_name"]}
Tone: {p["tone"]}
Catchphrases: {", ".join(p["catchphrases"])}
Analogy Domain: {p["analogy_domain"]}
Background: {p["background"]}

RULES:
1. Scene 0: Open with a vivid analogy from the character's domain ({p["analogy_domain"]}). Then drop it.
2. Continuous flow: each scene picks up where the previous left off.
3. No repetition: each scene covers NEW content, never re-explains earlier scenes.
4. Narration length: {min_words}-{max_words} words per scene (drives TTS audio duration).
5. Include 1 mandatory GRAPH scene (manim_scene_type="graph") and 1 EQUATION scene.
6. Last scene: summary with key takeaways.

DIFFICULTY: {d_instr}

Output ONLY valid JSON (no markdown):
{{
  "title": "Catchy title",
  "total_scenes": {n_scenes},
  "scenes": [
    {{
      "scene_index": 0,
      "narration_text": "...",
      "visual_description": "Specific description of what should animate on screen...",
      "manim_scene_type": "concept_reveal|graph|equation|diagram|geometry|summary",
      "duration_hint_seconds": 22,
      "character_action": "talking"
    }}
  ],
  "intro_text": "...",
  "outro_text": "..."
}}"""

    user_message = f"""Generate a {n_scenes}-scene educational video narration about: {topic}
Character: {p["display_name"]} | Difficulty: {difficulty}
Make it engaging, educational, and distinctly in the character's voice."""

    return system_prompt, user_message


def _build_code_prompt(
    scene: dict, title: str, difficulty: str, dcfg_min_play: int
) -> tuple[str, str]:
    """Return (system_prompt, user_message) for code generation using distilled prompt."""
    # Import the distilled reference and few-shot from the backend
    try:
        from app.services.script_generator import MANIMCE_REFERENCE
        from app.services.fewshot_examples import CODE_FEWSHOT
    except ImportError:
        # Fallback: load from file directly
        sg_path = ROOT / "backend" / "app" / "services" / "script_generator.py"
        content = sg_path.read_text()
        ref_match = re.search(r'MANIMCE_REFERENCE = r"""(.*?)"""', content, re.DOTALL)
        MANIMCE_REFERENCE = ref_match.group(1) if ref_match else ""
        fe_path = ROOT / "backend" / "app" / "services" / "fewshot_examples.py"
        fe_content = fe_path.read_text()
        cf_match = re.search(r'CODE_FEWSHOT = r"""(.*?)"""', fe_content, re.DOTALL)
        CODE_FEWSHOT = cf_match.group(1) if cf_match else ""

    system_prompt = f"""\
You are an expert ManimCE animation developer producing educational video scenes.
Generate COMPLETE, RUNNABLE Python code for ONE scene.

{MANIMCE_REFERENCE}

=== LAYOUT & VISUAL RULES ===
Frame: 14.2x8 units. Safe zone: x in [-6.0, 6.0], y in [-3.2, 3.2].
Title at UP*3.2, main content at DOWN*0.3, character safe zone: x<=-4.2.
Font: headers 40-48 (BOLD), body 28-36, minimum 24.
Colors on BLACK: TITLES=GOLD, PRIMARY=BLUE, SECONDARY=GREEN, HIGHLIGHT=YELLOW.

=== TEXT OVERLAP PREVENTION ===
1. ALWAYS FadeOut old text BEFORE adding new text in the same region.
2. Use ReplacementTransform to swap text in-place.
3. Section cleanup: self.play(*[FadeOut(m) for m in self.mobjects if m is not title], run_time=0.8)
4. NEVER have 2+ descriptive texts visible simultaneously.

=== SCENE LIFECYCLE ===
1. Title first at UP*3.2.
2. KEEP FINAL CONTENT VISIBLE — do NOT FadeOut at end.
3. End with self.wait(2).

=== RULES ===
1. Imports: from manim import * and import numpy as np only.
2. Class name: Scene{{NNN}} (three-digit zero-padded index).
3. Every self.play() MUST have run_time=1.0–2.5.
4. Min {dcfg_min_play} self.play() calls per scene to fill duration.
5. Add self.wait() pauses to match duration_hint_seconds exactly.
6. text.set_width(min(text.width, 8.5)) on every Text mobject.
7. NEVER use MathTex, Tex, or plain strings in axis label methods.

Output ONLY valid JSON (no markdown):
{{"scene_index": N, "manim_code": "from manim import *\\n..."}}

{CODE_FEWSHOT}"""

    idx = scene.get("scene_index", 0)
    stype = scene.get("manim_scene_type", "custom")
    dur = scene.get("duration_hint_seconds", 22)
    narration = scene.get("narration_text", "")
    visual = scene.get("visual_description", "")

    user_message = f"""Generate ManimCE code for Scene {idx} of '{title}' ({stype}, {dur}s).
Difficulty: {difficulty}

Narration: \"{narration}\"
Visual: \"{visual}\""""

    return system_prompt, user_message


# ── API call helpers ──────────────────────────────────────────────────────────

def _call_api(
    client, model_id: str, system_prompt: str, user_message: str,
    max_tokens: int = 4096, dry_run: bool = False
) -> str:
    """Call the Anthropic (or Bedrock) messages API and return response text."""
    if dry_run:
        return '{"scene_index": 0, "manim_code": "from manim import *\\nclass Scene000(MovingCameraScene):\\n    def construct(self):\\n        t = Text(\\"Hello\\", font_size=36)\\n        self.play(Write(t), run_time=1.0)\\n        self.wait(2)"}'
    resp = client.messages.create(
        model=model_id,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": user_message}],
        system=system_prompt,
    )
    return resp.content[0].text


def _parse_json_response(text: str) -> Optional[dict]:
    """Extract and parse JSON from a model response (handles markdown fences)."""
    text = text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object within the text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


# ── Manim render validation ───────────────────────────────────────────────────

def _check_constraints(code: str) -> list[str]:
    """Static constraint checks without running Manim. Returns list of violations."""
    violations = []
    if re.search(r'\bMathTex\s*\(', code):
        violations.append("uses MathTex (LaTeX not installed)")
    if re.search(r'\bTex\s*\(', code):
        violations.append("uses Tex (LaTeX not installed)")
    if re.search(r'get_x_axis_label\s*\(\s*["\']', code):
        violations.append("get_x_axis_label with plain string (triggers LaTeX)")
    if re.search(r'get_y_axis_label\s*\(\s*["\']', code):
        violations.append("get_y_axis_label with plain string (triggers LaTeX)")
    if re.search(r'get_graph_label\s*\([^,)]+,\s*["\']', code):
        violations.append("get_graph_label with plain string label (triggers LaTeX)")
    if not re.search(r'class\s+Scene\d{3}\s*\(', code):
        violations.append("class not named Scene{NNN}")
    if not re.search(r'MovingCameraScene', code):
        violations.append("not inheriting from MovingCameraScene")
    play_calls = re.findall(r'self\.play\(', code)
    if len(play_calls) < 3:
        violations.append(f"too few self.play() calls ({len(play_calls)})")
    if not re.search(r'self\.wait\s*\(\s*2\s*\)', code):
        violations.append("missing self.wait(2) at end")
    play_lines = re.findall(r'self\.play\(.*?\)', code, re.DOTALL)
    no_runtime = [l for l in play_lines if 'run_time' not in l]
    if len(no_runtime) > 2:
        violations.append(f"{len(no_runtime)} self.play() calls missing run_time=")
    return violations


def _validate_render(
    manim_code: str, scene_index: int, tmpdir: str, dry_run: bool = False
) -> dict:
    """Run actual Manim render and return {success, error, render_time_s}."""
    if dry_run:
        return {"success": True, "error": None, "render_time_s": 0.1}

    scene_file = Path(tmpdir) / f"scene_{scene_index:03d}.py"
    # Apply GL→CE patches (reuse existing logic)
    patched_code = _patch_gl_to_ce(manim_code)
    scene_file.write_text(patched_code)

    class_name = f"Scene{scene_index:03d}"
    cmd = [
        "manim", "render",
        str(scene_file), class_name,
        "-ql", "--fps=12",
        "--media_dir", tmpdir,
        "--disable_caching",
    ]
    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=MAX_RENDER_TIMEOUT
        )
        elapsed = time.perf_counter() - t0
        success = result.returncode == 0
        error = None
        if not success:
            # Extract last 600 chars of stderr (most relevant error info)
            stderr = result.stderr or ""
            error = stderr[-600:].strip()
        return {"success": success, "error": error, "render_time_s": round(elapsed, 2)}
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Render timed out after {MAX_RENDER_TIMEOUT}s",
            "render_time_s": MAX_RENDER_TIMEOUT,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc), "render_time_s": 0}


def _patch_gl_to_ce(code: str) -> str:
    """Minimal GL→CE compatibility patches (mirrors pipeline/manim_renderer/renderer.py)."""
    replacements = [
        (r'\bShowCreation\b', 'Create'),
        (r'\bUncreate\b', 'Unwrite'),
        (r'\bTransformMatchingTex\b', 'ReplacementTransform'),
        (r'\bManimColor\b', 'ManimColor'),
        (r'from manimlib', 'from manim'),
        (r'from manimlib\.imports', 'from manim'),
    ]
    for pattern, replacement in replacements:
        code = re.sub(pattern, replacement, code)
    return code


# ── Checkpoint / resume logic ─────────────────────────────────────────────────

def _load_checkpoint(output_path: Path) -> set:
    """Load set of already-generated (topic, difficulty, character) keys."""
    done = set()
    if output_path.exists():
        with open(output_path) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    done.add((rec["topic"], rec["difficulty"], rec["character"]))
                except Exception:
                    pass
    return done


# ── Main generation loop ──────────────────────────────────────────────────────

def generate_dataset(args):
    topics_path = ROOT / "data" / "topics.json"
    with open(topics_path) as f:
        all_topics = json.load(f)["topics"]

    if args.max_topics:
        all_topics = all_topics[: args.max_topics]

    difficulties = [d.strip() for d in args.difficulties.split(",")]
    characters = [c.strip() for c in args.characters.split(",")]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    already_done = _load_checkpoint(output_path) if args.resume else set()
    if already_done:
        logger.info("Resuming — %d topic/diff/char combos already done", len(already_done))

    narr_client, code_client, narr_model, code_model = _get_clients()

    total_combos = len(all_topics) * len(difficulties) * len(characters)
    logger.info(
        "Starting generation: %d topics × %d difficulties × %d characters = %d combinations",
        len(all_topics), len(difficulties), len(characters), total_combos,
    )
    logger.info("Output: %s", output_path)

    combo_count = 0
    scene_count = 0
    success_count = 0

    with open(output_path, "a") as out_f, tempfile.TemporaryDirectory() as tmpdir:
        for topic_entry in all_topics:
            topic = topic_entry["topic"]
            domain = topic_entry.get("domain", "general")

            for difficulty in difficulties:
                for character in characters:
                    key = (topic, difficulty, character)
                    if key in already_done:
                        logger.info("Skipping (already done): %s / %s / %s", topic, difficulty, character)
                        continue

                    combo_count += 1
                    logger.info(
                        "[%d/%d] Topic: %s | Difficulty: %s | Character: %s",
                        combo_count, total_combos, topic, difficulty, character,
                    )

                    # ── Step 1: Generate narration ──────────────────────────
                    narr_sys, narr_user = _build_narration_prompt(topic, difficulty, character)
                    try:
                        narr_text = _call_api(
                            narr_client, narr_model, narr_sys, narr_user,
                            max_tokens=max(2048, 12 * 400), dry_run=args.dry_run,
                        )
                        narration_data = _parse_json_response(narr_text)
                    except Exception as exc:
                        logger.error("Narration API failed for %s: %s", topic, exc)
                        continue

                    if not narration_data or "scenes" not in narration_data:
                        logger.warning("Could not parse narration JSON for %s", topic)
                        continue

                    scenes = narration_data.get("scenes", [])
                    title = narration_data.get("title", topic)
                    logger.info("  Narration OK — %d scenes, title: %s", len(scenes), title)

                    # ── Step 2: Generate code for each scene ────────────────
                    dcfg_min_play = {"beginner": 4, "intermediate": 5, "advanced": 6}.get(difficulty, 4)

                    for scene in scenes:
                        idx = scene.get("scene_index", 0)
                        stype = scene.get("manim_scene_type", "custom")
                        code_sys, code_user = _build_code_prompt(
                            scene, title, difficulty, dcfg_min_play
                        )

                        try:
                            code_text = _call_api(
                                code_client, code_model, code_sys, code_user,
                                max_tokens=4096, dry_run=args.dry_run,
                            )
                            code_data = _parse_json_response(code_text)
                        except Exception as exc:
                            logger.error("  Code API failed for scene %d: %s", idx, exc)
                            code_data = None

                        manim_code = ""
                        if code_data:
                            manim_code = code_data.get("manim_code", "")
                            if not manim_code and "scenes" in code_data:
                                manim_code = code_data["scenes"][0].get("manim_code", "") if code_data["scenes"] else ""

                        # ── Step 3: Static constraint validation ─────────────
                        constraint_violations = _check_constraints(manim_code) if manim_code else ["empty code"]

                        # ── Step 4: Actual Manim render ───────────────────────
                        render_result = _validate_render(
                            manim_code, idx, tmpdir, dry_run=args.dry_run
                        )

                        scene_count += 1
                        if render_result["success"]:
                            success_count += 1

                        # ── Step 5: Write record ─────────────────────────────
                        record = {
                            "id": str(uuid.uuid4()),
                            "topic": topic,
                            "domain": domain,
                            "difficulty": difficulty,
                            "character": character,
                            "title": title,
                            "scene_index": idx,
                            "scene_type": stype,
                            "duration_hint_seconds": scene.get("duration_hint_seconds", 22),
                            "narration_text": scene.get("narration_text", ""),
                            "visual_description": scene.get("visual_description", ""),
                            "manim_code": manim_code,
                            "render_success": render_result["success"],
                            "render_error": render_result["error"],
                            "render_time_s": render_result["render_time_s"],
                            "constraint_violations": constraint_violations,
                            "model_used": code_model,
                            "generated_at": datetime.utcnow().isoformat() + "Z",
                        }
                        out_f.write(json.dumps(record) + "\n")
                        out_f.flush()

                        status = "✓" if render_result["success"] else "✗"
                        logger.info(
                            "  Scene %d (%s): %s render=%.1fs violations=%s",
                            idx, stype, status, render_result["render_time_s"],
                            constraint_violations or "none",
                        )

    # ── Summary ────────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("═" * 60)
    logger.info("Generation complete!")
    logger.info("  Total scenes generated: %d", scene_count)
    logger.info("  Render successes:       %d (%.1f%%)",
                success_count, 100 * success_count / max(scene_count, 1))
    logger.info("  Output file:            %s", output_path)
    logger.info("═" * 60)
    logger.info("")
    logger.info("Next step: python scripts/inspect_dataset.py --stats")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, test pipeline logic only")
    parser.add_argument("--max-topics", type=int, default=None, help="Process only first N topics (for sample review)")
    parser.add_argument("--difficulties", default="beginner,intermediate", help="Comma-separated difficulty levels")
    parser.add_argument("--characters", default="lebron,goku", help="Comma-separated character names")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--output", default=str(ROOT / "data" / "training" / "jestify_dataset.jsonl"),
                        help="Output JSONL file path")
    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN MODE — no API calls will be made")

    generate_dataset(args)


if __name__ == "__main__":
    main()

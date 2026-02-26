#!/usr/bin/env python3
"""A/B test: generate the same video with Claude Opus vs finetuned local model.

Generates a complete video (all scenes) using both CODE_PROVIDER=anthropic
and CODE_PROVIDER=ollama, then renders both. Use this for the Checkpoint 5
side-by-side comparison before switching to the local model in production.

Usage:
  # Test with a topic string:
  python scripts/ab_test.py --topic "Derivatives" --difficulty beginner

  # Test with an existing PDF/text:
  python scripts/ab_test.py --text "Quicksort works by picking a pivot..."

  # Use a specific Ollama model:
  python scripts/ab_test.py --topic "Binary search" --ollama-model jestify-manim-coder
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_generation(
    source_text: str,
    difficulty: str,
    character: str,
    code_provider: str,
    code_model: str,
) -> dict:
    """Run the full script generation pipeline with a given CODE_PROVIDER."""
    # Temporarily override the environment variables used by ScriptGenerator
    original_provider = os.environ.get("CODE_PROVIDER")
    original_model = os.environ.get("CODE_MODEL")
    original_ollama_model = os.environ.get("OLLAMA_CODE_MODEL")

    os.environ["CODE_PROVIDER"] = code_provider
    if code_provider == "ollama":
        os.environ["OLLAMA_CODE_MODEL"] = code_model
    else:
        os.environ["CODE_MODEL"] = code_model

    try:
        from app.services.script_generator import ScriptGenerator
        from shared.contracts.enums import Character, Difficulty

        char_map = {
            "lebron": Character.LEBRON,
            "goku": Character.GOKU,
            "peter": Character.PETER,
            "taylor": Character.TAYLOR,
        }
        diff_map = {
            "beginner": Difficulty.BEGINNER,
            "intermediate": Difficulty.INTERMEDIATE,
            "advanced": Difficulty.ADVANCED,
        }

        generator = ScriptGenerator()
        t0 = time.perf_counter()

        # Only generate narration + code (no rendering in this script)
        result = generator.generate(
            extracted_text=source_text,
            character=char_map.get(character, Character.LEBRON),
            difficulty=diff_map.get(difficulty, Difficulty.BEGINNER),
        )
        elapsed = round(time.perf_counter() - t0, 2)

        return {
            "success": True,
            "script": result,
            "generation_time_s": elapsed,
            "provider": code_provider,
            "model": code_model,
            "error": None,
        }
    except Exception as exc:
        logger.error("Generation failed with %s: %s", code_provider, exc)
        return {
            "success": False,
            "script": None,
            "generation_time_s": None,
            "provider": code_provider,
            "model": code_model,
            "error": str(exc),
        }
    finally:
        # Restore original env
        if original_provider is None:
            os.environ.pop("CODE_PROVIDER", None)
        else:
            os.environ["CODE_PROVIDER"] = original_provider
        if original_model is None:
            os.environ.pop("CODE_MODEL", None)
        elif original_model:
            os.environ["CODE_MODEL"] = original_model
        if original_ollama_model is None:
            os.environ.pop("OLLAMA_CODE_MODEL", None)
        elif original_ollama_model:
            os.environ["OLLAMA_CODE_MODEL"] = original_ollama_model


def compare_results(anthropic_result: dict, ollama_result: dict):
    """Print a side-by-side comparison of both generation runs."""
    print(f"\n{'='*70}")
    print("A/B TEST RESULTS")
    print(f"{'='*70}")
    print(f"{'Metric':<30} {'Claude Opus':>18}  {'Local Model':>18}")
    print("-" * 70)

    a_ok = anthropic_result.get("success")
    o_ok = ollama_result.get("success")
    print(f"{'Generation success':<30} {'✓' if a_ok else '✗':>18}  {'✓' if o_ok else '✗':>18}")

    a_time = anthropic_result.get("generation_time_s")
    o_time = ollama_result.get("generation_time_s")
    print(f"{'Generation time (s)':<30} {str(a_time)+' s':>18}  {str(o_time)+' s':>18}")

    if a_ok and o_ok:
        a_script = anthropic_result["script"]
        o_script = ollama_result["script"]

        a_scenes = len(a_script.scenes) if a_script else 0
        o_scenes = len(o_script.scenes) if o_script else 0
        print(f"{'Scenes generated':<30} {a_scenes:>18}  {o_scenes:>18}")

        if a_script and o_script:
            # Count successful code generations (non-empty manim_code)
            a_code_ok = sum(1 for s in a_script.scenes if s.manim_code and len(s.manim_code) > 100)
            o_code_ok = sum(1 for s in o_script.scenes if s.manim_code and len(s.manim_code) > 100)
            print(f"{'Scenes with code (>100 chars)':<30} {a_code_ok:>18}  {o_code_ok:>18}")

            # Avg code length
            a_avg_len = sum(len(s.manim_code or "") for s in a_script.scenes) / max(a_scenes, 1)
            o_avg_len = sum(len(s.manim_code or "") for s in o_script.scenes) / max(o_scenes, 1)
            print(f"{'Avg code length (chars)':<30} {a_avg_len:>18.0f}  {o_avg_len:>18.0f}")

    print("-" * 70)
    print()

    if a_ok and o_ok:
        a_script = anthropic_result["script"]
        o_script = ollama_result["script"]

        # Save both scripts to temp files for manual inspection
        out_dir = ROOT / "data" / "ab_test_output"
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        a_path = out_dir / f"anthropic_{ts}.json"
        o_path = out_dir / f"ollama_{ts}.json"

        if a_script:
            a_path.write_text(json.dumps(a_script.model_dump() if hasattr(a_script, "model_dump") else str(a_script), indent=2))
        if o_script:
            o_path.write_text(json.dumps(o_script.model_dump() if hasattr(o_script, "model_dump") else str(o_script), indent=2))

        print(f"Scripts saved for inspection:")
        print(f"  Claude Opus: {a_path}")
        print(f"  Local model: {o_path}")
        print()
        print("To render and watch both videos:")
        print("  The scripts above contain the Manim code — copy a scene's manim_code")
        print("  to a .py file and run: manim render <file.py> Scene000 -ql")

    if not a_ok:
        print(f"Claude Opus error: {anthropic_result.get('error')}")
    if not o_ok:
        print(f"Local model error: {ollama_result.get('error')}")

    print(f"\n{'='*70}")
    if a_ok and o_ok:
        print("Checkpoint 5 complete. Review the output JSONs, then decide:")
        print("  Deploy: set CODE_PROVIDER=ollama in .env to switch to local model")
    print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--topic", default="Introduction to derivatives",
                        help="Topic string to use as source material")
    parser.add_argument("--text", default=None,
                        help="Raw text to use as source (overrides --topic)")
    parser.add_argument("--difficulty", default="beginner",
                        choices=["beginner", "intermediate", "advanced"])
    parser.add_argument("--character", default="lebron",
                        choices=["lebron", "goku", "peter", "taylor"])
    parser.add_argument("--ollama-model", default=os.getenv("OLLAMA_CODE_MODEL", "jestify-manim-coder"),
                        help="Ollama model name for the local model")
    parser.add_argument("--claude-model", default=os.getenv("CODE_MODEL", "claude-opus-4-6"),
                        help="Claude model name for the Anthropic baseline")
    parser.add_argument("--anthropic-only", action="store_true",
                        help="Only run the Anthropic baseline (skip Ollama)")
    parser.add_argument("--ollama-only", action="store_true",
                        help="Only run the Ollama model (skip Anthropic)")
    args = parser.parse_args()

    source_text = args.text or f"""
{args.topic}

This is an educational topic. Please create a comprehensive educational video
that covers the key concepts, provides clear examples, and helps students
understand the material at a {args.difficulty} level.
"""

    logger.info("Starting A/B test: topic='%s', difficulty=%s, character=%s",
                args.topic, args.difficulty, args.character)

    anthropic_result = {"success": False, "error": "skipped", "generation_time_s": None, "script": None, "provider": "anthropic", "model": args.claude_model}
    ollama_result = {"success": False, "error": "skipped", "generation_time_s": None, "script": None, "provider": "ollama", "model": args.ollama_model}

    if not args.ollama_only:
        logger.info("\n--- Running Claude Opus (baseline) ---")
        anthropic_result = run_generation(
            source_text, args.difficulty, args.character,
            code_provider="anthropic", code_model=args.claude_model,
        )
        logger.info("Claude Opus: %s in %.1fs",
                    "✓" if anthropic_result["success"] else "✗",
                    anthropic_result.get("generation_time_s") or 0)

    if not args.anthropic_only:
        logger.info("\n--- Running local Ollama model (%s) ---", args.ollama_model)
        ollama_result = run_generation(
            source_text, args.difficulty, args.character,
            code_provider="ollama", code_model=args.ollama_model,
        )
        logger.info("Ollama (%s): %s in %.1fs",
                    args.ollama_model,
                    "✓" if ollama_result["success"] else "✗",
                    ollama_result.get("generation_time_s") or 0)

    compare_results(anthropic_result, ollama_result)


if __name__ == "__main__":
    main()
